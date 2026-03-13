import asyncio
import sys
import json
import re
from copy import deepcopy
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.file_utils import read_jsonl
from schema import MarkdownResponse, AnalysisResponse
from shiyu_assistant.log_compression import (
    compress_log_messages,
    format_compressed_payload,
    calculate_key_field_hit_rate,
)
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from llm_client import LLMClient

TRUNCATION_PLACEHOLDER = "...[truncated]..."
BOXED_RE = re.compile(r"\\boxed\s*\{[^}]+\}")
DATE_TOKEN_RE = re.compile(
    r"\b20\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])\b"
)
URL_TOKEN_RE = re.compile(r"https?://[^\s)\]>\"'\\]+")
FORMAT_NOISE_MARKERS = (
    "must end with this exact format",
    "do not use any other format",
    "we are now ending this session",
    "you must not initiate any further tool use",
    "summarize all working history",
    "output the final answer in the format",
    "the original question is repeated here for reference",
)

DEFAULT_FACTOR_PROMPT_MAX_CHARS = 3200
RELAXED_FACTOR_PROMPT_MAX_CHARS = 6200
SUPER_RELAXED_FACTOR_PROMPT_MAX_CHARS = 8200
DEFAULT_FACTOR_KEY_FIELD_HIT_RATE_THRESHOLD = 0.90
MAX_FACTOR_BACKFILL_ITEMS = 8

AGGRESSIVE_FACTOR_LOG_SECTION_LIMITS: dict[str, dict[str, int]] = {
    "task_context": {"max_items": 3, "max_chars": 150},
    "tool_trace_compact": {"max_items": 6, "max_chars": 160},
    "key_findings": {"max_items": 12, "max_chars": 180},
    "key_field_backfill": {"max_items": 80, "max_chars": 600},
    "error_summary": {"max_items": 4, "max_chars": 150},
    "final_decision": {"max_items": 4, "max_chars": 170},
    "residual_context": {"max_items": 2, "max_chars": 140},
}


def _truncate_middle(text: str, max_chars: int) -> str:
    if not isinstance(text, str):
        return ""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= len(TRUNCATION_PLACEHOLDER) + 2:
        return text[:max_chars]
    head_len = (max_chars - len(TRUNCATION_PLACEHOLDER)) // 2
    tail_len = max_chars - len(TRUNCATION_PLACEHOLDER) - head_len
    return f"{text[:head_len]}{TRUNCATION_PLACEHOLDER}{text[-tail_len:]}"


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - numerator / denominator))


def _format_factor_prompt_stats(payload: dict[str, Any], factor_log_path: str) -> str:
    stats = payload.get("prompt_compression_stats", {})
    task_id = Path(factor_log_path).parent.parent.name
    factor_name = Path(factor_log_path).stem
    return (
        "[FactorPromptStats] "
        f"task={task_id} "
        f"factor={factor_name} "
        f"raw={stats.get('raw_prompt_chars', 'n/a')} "
        f"compressed={stats.get('compressed_prompt_chars', 'n/a')} "
        f"reduction={stats.get('prompt_reduction_ratio', 'n/a')} "
        f"hit={stats.get('key_field_hit_rate', 'n/a')} "
        f"backfill={stats.get('backfill_count', 0)}"
    )


def _normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for item in items:
        normalized = item.strip()
        key = _normalize_key(normalized)
        if not normalized or key in seen:
            continue
        seen.add(key)
        results.append(normalized)
    return results


def _is_format_noise(content: str) -> bool:
    lowered = content.lower()
    return any(marker in lowered for marker in FORMAT_NOISE_MARKERS)


def _minify_json_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return text.strip()
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _render_compact_payload(payload: dict[str, Any], max_chars: int, profile: str) -> str:
    direct = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(direct) <= max_chars:
        return direct
    rendered = format_compressed_payload(payload, max_chars=max_chars, profile=profile)
    return _minify_json_text(rendered)


def _is_priority_line(line: str) -> bool:
    lowered = line.lower()
    if any(
        marker in lowered
        for marker in (
            "recover_boxed",
            "recover_url",
            "recover_date",
            "boxed:",
            "\\boxed",
            "url:",
            "key_numbers_dates",
            "strict_final_boxed",
            "strict_final_source",
        )
    ):
        return True
    if URL_TOKEN_RE.search(line):
        return True
    if DATE_TOKEN_RE.search(line):
        return True
    return False


def _line_priority_score(line: str, section: str) -> int:
    lowered = line.lower()
    score = 0
    if _is_priority_line(line):
        score += 80
    if section == "final_decision":
        score += 20
    if section in {"key_findings"} and any(
        token in lowered for token in ("evidence", "signal", "confidence", "source")
    ):
        score += 8
    if section in {"error_summary"} and any(
        token in lowered for token in ("error", "failed", "timeout", "429", "403")
    ):
        score += 6
    if "assistant@" in lowered or "tool@" in lowered:
        score += 3
    return score


def _prune_section_items(
    items: list[Any],
    section: str,
    max_items: int,
    max_line_chars: int,
) -> list[str]:
    if section == "key_field_backfill":
        results: list[str] = []
        seen: set[str] = set()
        for item in items:
            line = str(item).strip()
            if not line:
                continue
            if _normalize_key(line).startswith("- recover_url:"):
                line = _truncate_middle(line, 1000)
            elif _normalize_key(line).startswith("- recover_"):
                line = _truncate_middle(line, 300)
            else:
                line = _truncate_middle(line, max_line_chars)
            key = _normalize_key(line)
            if not key or key in seen:
                continue
            seen.add(key)
            results.append(line)
            if len(results) >= max_items:
                break
        return results

    prepared: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, item in enumerate(items):
        line = str(item).strip()
        if not line or _is_format_noise(line):
            continue
        if _normalize_key(line).startswith("- recover_"):
            line = _truncate_middle(line, 600)
        else:
            line = _truncate_middle(line, max_line_chars)
        key = _normalize_key(line)
        if not key or key in seen:
            continue
        seen.add(key)
        prepared.append(
            {
                "idx": idx,
                "line": line,
                "score": _line_priority_score(line, section),
                "priority": _is_priority_line(line),
            }
        )

    if not prepared:
        return []

    priority_rows = sorted(
        (row for row in prepared if row["priority"]),
        key=lambda row: (row["score"], row["idx"]),
        reverse=True,
    )
    normal_rows = sorted(
        (row for row in prepared if not row["priority"]),
        key=lambda row: (row["score"], row["idx"]),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    for row in priority_rows + normal_rows:
        if len(selected) >= max_items:
            break
        selected.append(row)

    selected.sort(key=lambda row: row["idx"])
    return [row["line"] for row in selected]


def _apply_factor_section_pruning(
    payload: dict[str, Any],
    section_limits: dict[str, dict[str, int]],
) -> dict[str, Any]:
    pruned = deepcopy(payload)
    for section, limits in section_limits.items():
        items = pruned.get(section)
        if isinstance(items, list):
            pruned[section] = _prune_section_items(
                items,
                section=section,
                max_items=int(limits.get("max_items", 8)),
                max_line_chars=int(limits.get("max_chars", 160)),
            )
            if not pruned[section]:
                pruned.pop(section, None)

    pruned.pop("compression_metrics", None)
    meta = pruned.get("meta")
    if isinstance(meta, dict):
        compact_meta = {}
        if "total_messages" in meta:
            compact_meta["total_messages"] = meta["total_messages"]
        if compact_meta:
            pruned["meta"] = compact_meta
        else:
            pruned.pop("meta", None)
    return pruned


def _parse_missing_field_entry(entry: str) -> tuple[str, str] | None:
    if not isinstance(entry, str) or ":" not in entry:
        return None
    field_type, value = entry.split(":", 1)
    field_type = field_type.strip().lower()
    value = value.strip()
    if not field_type or not value:
        return None
    if field_type == "url":
        matched = URL_TOKEN_RE.search(value)
        value = matched.group(0).strip() if matched else value
    elif field_type == "date":
        matched = DATE_TOKEN_RE.search(value)
        value = matched.group(0).strip() if matched else value
    elif field_type == "boxed":
        matched = BOXED_RE.search(value)
        value = matched.group(0).strip() if matched else value
    else:
        return None
    return (field_type, value) if value else None


def _inject_missing_key_fields(
    payload: dict[str, Any],
    missing_examples: list[str],
    section_name: str,
    max_items: int = MAX_FACTOR_BACKFILL_ITEMS,
) -> int:
    if max_items <= 0:
        return 0
    section_items = payload.get(section_name)
    if not isinstance(section_items, list):
        section_items = []
    existing_keys = {_normalize_key(str(item)) for item in section_items}
    injected = 0

    for raw in missing_examples:
        if injected >= max_items:
            break
        parsed = _parse_missing_field_entry(raw)
        if not parsed:
            continue
        field_type, value = parsed
        if field_type == "boxed":
            line = f"- recover_boxed: {value}"
        elif field_type == "url":
            line = f"- recover_url: {value}"
        else:
            line = f"- recover_date: {value}"
        if field_type != "url":
            line = _truncate_middle(line, 220)
        key = _normalize_key(line)
        if not key or key in existing_keys:
            continue
        section_items.append(line)
        existing_keys.add(key)
        injected += 1

    payload[section_name] = section_items
    return injected


def _hit_rate(hit: dict[str, Any]) -> float:
    try:
        return float(hit.get("hit_rate", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _normalize_url(url: str) -> str:
    normalized = url.strip().replace("\\/", "/")
    normalized = normalized.strip("`'\"<>[](){}")
    normalized = normalized.rstrip(".,;:!?)\\")
    return normalized if normalized.lower().startswith(("http://", "https://")) else ""


def _extract_urls(text: str, max_items: int = 36) -> list[str]:
    urls: list[str] = []
    for matched in URL_TOKEN_RE.findall(text):
        normalized = _normalize_url(matched)
        if not normalized:
            continue
        urls.append(normalized)
        if len(urls) >= max_items:
            break
    return _dedupe_keep_order(urls)


def _extract_dates(text: str, max_items: int = 24) -> list[str]:
    return _dedupe_keep_order(DATE_TOKEN_RE.findall(text))[:max_items]


def _extract_boxed(text: str, max_items: int = 20) -> list[str]:
    return _dedupe_keep_order(BOXED_RE.findall(text))[:max_items]


def _inject_raw_key_fields(
    payload: dict[str, Any],
    raw_text: str,
    section_name: str,
    max_urls: int = 24,
    max_dates: int = 18,
    max_boxed: int = 12,
) -> int:
    section_items = payload.get(section_name)
    if not isinstance(section_items, list):
        section_items = []

    existing_keys = {_normalize_key(str(item)) for item in section_items}
    injected = 0

    candidates: list[str] = []
    for boxed in _extract_boxed(raw_text, max_items=max_boxed):
        candidates.append(f"- recover_boxed: {boxed}")
    for url in _extract_urls(raw_text, max_items=max_urls):
        candidates.append(f"- recover_url: {url}")
    for date in _extract_dates(raw_text, max_items=max_dates):
        candidates.append(f"- recover_date: {date}")

    for line in candidates:
        key = _normalize_key(line)
        if not key or key in existing_keys:
            continue
        section_items.append(line)
        existing_keys.add(key)
        injected += 1

    payload[section_name] = section_items
    return injected


def _build_prompt_text(log_content: str, use_alternative_prompt: bool) -> tuple[str, str]:
    if use_alternative_prompt:
        # shiyu_dev框架提示词
        sys_prompt = """
        你是一个日志分析专家。你正在分析一个多智能体预测系统中**某个子智能体**的执行日志。
        该系统由主智能体统筹调度和任务分解，调用子智能体对子任务进行分析。

        请按以下结构输出分析：

        ## 1. 流程梳理
        - 子智能体执行了哪些步骤，找到了哪些关键数据/指标
        - 决策依据是什么，逻辑链是否合理
        - **结论评估**：最终结论是否有充分证据支撑？置信度与实际证据强度是否匹配？是否遗漏了本应探索的重要方向？

        ## 2. 错误检查
        按严重程度**从高到低**列出每个错误，每条须包含：
        - 严重程度标签（🔴 致命 / 🟡 警告 / 🟢 观察）
        - 错误描述
        - 日志定位 `[msg@N]`（N 为消息编号，如 assistant@12、tool@36）

        **严重程度判定标准**：
        - 🔴 致命 = 导致任务目标根本无法达成，或产出误导性结论（如：逻辑前提错误、核心数据完全无效、违规导致关键步骤失败）
        - 🟡 警告 = 不影响核心结论但造成效率损失或质量下降（如：低效重复调用、非关键工具报错、信息源单一）
        - 🟢 观察 = 值得记录的小问题或改进点，不影响当前任务结果

        你需要输出一个JSON结构，包含两个字段：
        - `error_summary`: **一句话**概括最严重的错误，以"🔴 致命：..." / "🟡 警告：..." / "🟢 无严重错误"开头。不换行、不用列表。
        - `content`: 纯markdown分析报告（须包含上述"流程梳理"和"错误检查"两部分）。

        【极其重要 - 搜索】：你具备联网搜索能力（search_web工具）。当日志中出现你不确定的事实（时间/休市日、API字段、报错码、业务公式、事件细节等），你**必须**主动调用 search_web 进行交叉验证，不要靠猜测下结论！按重要性排序，优先搜索最可能导致严重误判的疑点。
        """
        user_prompt = f"""
        子智能体日志：
        {log_content}
        请给出结构化分析结果：
        """
    else:
        # galaxy框架提示词
        sys_prompt = """
        你是一个日志分析专家。你正在分析一个多智能体预测系统中**某个子智能体**的执行日志。
        该系统由专家智能体调用多个子智能体分别执行子任务，最后由专家智能体聚合结果。

        请按以下结构输出分析：

        ## 1. 流程梳理
        - 子智能体执行了哪些步骤，找到了哪些关键数据/指标
        - 决策依据是什么，逻辑链是否合理
        - **结论评估**：最终结论是否有充分证据支撑？置信度与实际证据强度是否匹配？是否遗漏了本应探索的重要方向？

        ## 2. 错误检查
        按严重程度**从高到低**列出每个错误，每条须包含：
        - 严重程度标签（🔴 致命 / 🟡 警告 / 🟢 观察）
        - 错误描述
        - 日志定位 `[msg@N]`（N 为消息编号，如 assistant@12、tool@36）

        **严重程度判定标准**：
        - 🔴 致命 = 导致任务目标根本无法达成，或产出误导性结论（如：逻辑前提错误、核心数据完全无效、违规导致关键步骤失败）
        - 🟡 警告 = 不影响核心结论但造成效率损失或质量下降（如：低效重复调用、非关键工具报错、信息源单一）
        - 🟢 观察 = 值得记录的小问题或改进点，不影响当前任务结果

        你需要输出一个JSON结构，包含两个字段：
        - `error_summary`: **一句话**概括最严重的错误，以"🔴 致命：..." / "🟡 警告：..." / "🟢 无严重错误"开头。不换行、不用列表。
        - `content`: 纯markdown分析报告（须包含上述"流程梳理"和"错误检查"两部分）。

        【极其重要 - 搜索】：你具备联网搜索能力（search_web工具）。当日志中出现你不确定的事实（时间/休市日、API字段、报错码、业务公式、事件细节等），你**必须**主动调用 search_web 进行交叉验证，不要靠猜测下结论！按重要性排序，优先搜索最可能导致严重误判的疑点。
        """
        user_prompt = f"""
        以下是你需要分析的子智能体的日志：
        {log_content}
        现在，请你给出你的结构化分析结果：
        """
    return sys_prompt, user_prompt


def build_factor_prompt_payload(
    path: str,
    use_alternative_prompt: bool = False,
    key_field_hit_rate_threshold: float = DEFAULT_FACTOR_KEY_FIELD_HIT_RATE_THRESHOLD,
) -> dict[str, Any]:
    """
    Build prompt messages and compression artifacts for factor log analysis.

    Args:
        path: Path to the factor log file (jsonl).
        use_alternative_prompt: Whether to use alternative prompt templates.
        key_field_hit_rate_threshold: Minimum key-field hit rate before relaxing budgets.

    Returns:
        Dict containing prompt messages and compression artifacts.
    """
    log_rows = read_jsonl(path)
    raw_log_text = json.dumps(log_rows, ensure_ascii=False)
    raw_log_block = str(log_rows)
    raw_sys_prompt, raw_user_prompt = _build_prompt_text(raw_log_block, use_alternative_prompt)

    compressed_log_raw = compress_log_messages(log_rows, source_path=path)
    compressed_log = _apply_factor_section_pruning(
        compressed_log_raw,
        AGGRESSIVE_FACTOR_LOG_SECTION_LIMITS,
    )

    factor_max_chars = DEFAULT_FACTOR_PROMPT_MAX_CHARS
    backfill_count = 0
    compressed_log_text = _render_compact_payload(
        compressed_log,
        max_chars=factor_max_chars,
        profile="factor",
    )
    key_field_hit = calculate_key_field_hit_rate(raw_log_text, compressed_log_text)

    backfill_count += _inject_missing_key_fields(
        compressed_log,
        key_field_hit.get("missing_examples", []),
        section_name="key_field_backfill",
        max_items=MAX_FACTOR_BACKFILL_ITEMS,
    )
    if backfill_count:
        compressed_log = _apply_factor_section_pruning(
            compressed_log,
            AGGRESSIVE_FACTOR_LOG_SECTION_LIMITS,
        )
        compressed_log_text = _render_compact_payload(
            compressed_log,
            max_chars=factor_max_chars,
            profile="factor",
        )
        key_field_hit = calculate_key_field_hit_rate(raw_log_text, compressed_log_text)

    if _hit_rate(key_field_hit) < key_field_hit_rate_threshold:
        factor_max_chars = RELAXED_FACTOR_PROMPT_MAX_CHARS
        backfill_count += _inject_raw_key_fields(
            compressed_log,
            raw_log_text,
            section_name="key_field_backfill",
        )
        compressed_log = _apply_factor_section_pruning(
            compressed_log,
            AGGRESSIVE_FACTOR_LOG_SECTION_LIMITS,
        )
        compressed_log_text = _render_compact_payload(
            compressed_log,
            max_chars=factor_max_chars,
            profile="factor",
        )
        key_field_hit = calculate_key_field_hit_rate(raw_log_text, compressed_log_text)

        extra_backfill = _inject_missing_key_fields(
            compressed_log,
            key_field_hit.get("missing_examples", []),
            section_name="key_field_backfill",
            max_items=MAX_FACTOR_BACKFILL_ITEMS,
        )
        extra_backfill += _inject_raw_key_fields(
            compressed_log,
            raw_log_text,
            section_name="key_field_backfill",
            max_urls=36,
            max_dates=24,
            max_boxed=16,
        )
        backfill_count += extra_backfill
        if extra_backfill:
            compressed_log = _apply_factor_section_pruning(
                compressed_log,
                AGGRESSIVE_FACTOR_LOG_SECTION_LIMITS,
            )
            compressed_log_text = _render_compact_payload(
                compressed_log,
                max_chars=factor_max_chars,
                profile="factor",
            )
            key_field_hit = calculate_key_field_hit_rate(raw_log_text, compressed_log_text)

        if _hit_rate(key_field_hit) < key_field_hit_rate_threshold:
            factor_max_chars = SUPER_RELAXED_FACTOR_PROMPT_MAX_CHARS
            backfill_count += _inject_raw_key_fields(
                compressed_log,
                raw_log_text,
                section_name="key_field_backfill",
                max_urls=48,
                max_dates=32,
                max_boxed=20,
            )
            compressed_log = _apply_factor_section_pruning(
                compressed_log,
                AGGRESSIVE_FACTOR_LOG_SECTION_LIMITS,
            )
            compressed_log_text = _render_compact_payload(
                compressed_log,
                max_chars=factor_max_chars,
                profile="factor",
            )
            key_field_hit = calculate_key_field_hit_rate(raw_log_text, compressed_log_text)

    metrics = compressed_log_raw.get("compression_metrics", {})
    compression_header = (
        f"raw_chars={metrics.get('raw_chars', 'n/a')}, "
        f"compressed_chars={metrics.get('compressed_chars', 'n/a')}, "
        f"reduction_ratio={metrics.get('reduction_ratio', 0.0)}, "
        f"key_field_hit_rate={key_field_hit.get('hit_rate', 'n/a')}"
    )

    log_content = f"{compression_header}\n{compressed_log_text}"
    sys_prompt, user_prompt = _build_prompt_text(log_content, use_alternative_prompt)
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]

    raw_prompt_chars = len(raw_sys_prompt) + len(raw_user_prompt)
    compressed_prompt_chars = len(sys_prompt) + len(user_prompt)
    prompt_reduction_ratio = round(_safe_ratio(compressed_prompt_chars, raw_prompt_chars), 4)

    return {
        "messages": messages,
        "compressed_log": compressed_log,
        "compressed_log_text": compressed_log_text,
        "compression_header": compression_header,
        "key_field_hit_rate": key_field_hit,
        "prompt_compression_stats": {
            "raw_prompt_chars": raw_prompt_chars,
            "compressed_prompt_chars": compressed_prompt_chars,
            "prompt_reduction_ratio": prompt_reduction_ratio,
            "key_field_hit_rate": key_field_hit.get("hit_rate", "n/a"),
            "budget_chars": factor_max_chars,
            "backfill_count": backfill_count,
        },
    }


def factor_analysis_prompt(path: str, use_alternative_prompt: bool = False) -> list[dict]:
    payload = build_factor_prompt_payload(path, use_alternative_prompt)
    return payload["messages"]

async def analyze_factor_log(client: 'LLMClient', path: str, use_alternative_prompt: bool = False) -> tuple[str, str]:
    """
    Asynchronously analyze a factor log using the LLM client.
    
    Args:
        client: The LLMClient instance (async).
        path: Path to the log file (jsonl).
        use_alternative_prompt: Whether to use alternative prompt templates.
        
    Returns:
        tuple[str, str]: A tuple containing (markdown_content, error_summary).
    """
    loop = asyncio.get_running_loop()
    payload = await loop.run_in_executor(
        None,
        lambda: build_factor_prompt_payload(path, use_alternative_prompt),
    )
    print(_format_factor_prompt_stats(payload, path))
    messages = payload["messages"]
    
    # Using chat_structured to enforce AnalysisResponse schema with web search enabled
    try:
        response = await client.chat_structured(
            messages,
            response_format=AnalysisResponse,
            use_web_search=True
        )
    except (ValueError, Exception) as e:
        factor_name = Path(path).stem
        print(f"Error analyzing factor {factor_name}: {e}")
        return f"# Factor Analysis Failed\n\nFactor: `{factor_name}`\n\nError: {e}\n", f"❌ Failed to analyze factor log: {e}"

    if response is None:
        factor_name = Path(path).stem
        print(f"Warning: No response for factor {factor_name} (max tool loops exhausted)")
        return f"# Factor Analysis Incomplete\n\nFactor: `{factor_name}`\n\nThe model exhausted tool call loops without producing a final response.\n", "⚠️ API Exhausted tool calls."

    return response.content, response.error_summary

