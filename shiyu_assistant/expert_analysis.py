import asyncio
import sys
import json
import re
from copy import deepcopy
from pathlib import Path

# Add project root to sys.path to allow imports from utils and other modules
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from typing import List, TYPE_CHECKING, Any

from utils.file_utils import read_jsonl, save_string_to_md, read_md_to_string
from schema import MarkdownResponse
from shiyu_assistant.factor_analysis import analyze_factor_log, build_factor_prompt_payload
from shiyu_assistant.compression_report import (
    render_expert_compression_report,
    render_factor_compression_report,
)
from shiyu_assistant.log_compression import (
    compress_log_messages,
    compress_markdown_reports,
    format_compressed_payload,
    calculate_key_field_hit_rate,
)

if TYPE_CHECKING:
    from LLM_CLIENT import LLMClient


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

DEFAULT_EXPERT_PROMPT_MAX_CHARS = 6400
DEFAULT_FACTOR_PROMPT_MAX_CHARS = 3600
RELAXED_EXPERT_PROMPT_MAX_CHARS = 9200
RELAXED_FACTOR_PROMPT_MAX_CHARS = 5600
DEFAULT_EXPERT_KEY_FIELD_HIT_RATE_THRESHOLD = 0.90
DEFAULT_FACTOR_KEY_FIELD_HIT_RATE_THRESHOLD = 0.88
MAX_MISSING_BACKFILL_PER_PAYLOAD = 8

AGGRESSIVE_EXPERT_SECTION_LIMITS: dict[str, dict[str, int]] = {
    "task_context": {"max_items": 3, "max_chars": 150},
    "tool_trace_compact": {"max_items": 6, "max_chars": 160},
    "key_findings": {"max_items": 11, "max_chars": 180},
    "key_field_backfill": {"max_items": 64, "max_chars": 600},
    "error_summary": {"max_items": 3, "max_chars": 150},
    "final_decision": {"max_items": 5, "max_chars": 180},
    "residual_context": {"max_items": 2, "max_chars": 140},
}

AGGRESSIVE_FACTOR_REPORT_SECTION_LIMITS: dict[str, dict[str, int]] = {
    "report_compact": {"max_items": 6, "max_chars": 170},
    "aggregate_findings": {"max_items": 8, "max_chars": 170},
    "key_field_backfill": {"max_items": 64, "max_chars": 600},
    "aggregate_errors": {"max_items": 3, "max_chars": 150},
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
    if section in {"key_findings", "aggregate_findings"} and any(
        token in lowered for token in ("evidence", "signal", "confidence", "source")
    ):
        score += 8
    if section in {"error_summary", "aggregate_errors"} and any(
        token in lowered for token in ("error", "failed", "timeout", "429", "403")
    ):
        score += 6
    if "assistant@" in lowered or "tool@" in lowered or "report_" in lowered:
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
            lowered = _normalize_key(line)
            if lowered.startswith("- recover_url:"):
                line = _truncate_middle(line, 1000)
            elif lowered.startswith("- recover_"):
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


def _apply_section_pruning(
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
                max_line_chars=int(limits.get("max_chars", 180)),
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
    max_items: int = MAX_MISSING_BACKFILL_PER_PAYLOAD,
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


def _hit_rate(hit: dict[str, Any]) -> float:
    try:
        return float(hit.get("hit_rate", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _format_expert_prompt_stats(payload: dict[str, Any], expert_log_path: str) -> str:
    stats = payload.get("prompt_compression_stats", {})
    task_id = Path(expert_log_path).parent.name
    return (
        "[ExpertPromptStats] "
        f"task={task_id} "
        f"raw={stats.get('raw_prompt_chars', 'n/a')} "
        f"compressed={stats.get('compressed_prompt_chars', 'n/a')} "
        f"reduction={stats.get('prompt_reduction_ratio', 'n/a')} "
        f"expert_hit={stats.get('expert_key_field_hit_rate', 'n/a')} "
        f"factor_hit={stats.get('factor_key_field_hit_rate', 'n/a')} "
        f"log_backfill={stats.get('log_backfill_count', 0)} "
        f"factor_backfill={stats.get('factor_backfill_count', 0)}"
    )


def build_expert_prompt_payload(
    path: str,
    factor_reports: List[str],
    answer: str = None,
    use_alternative_prompt: bool = False,
    key_field_hit_rate_threshold: float = DEFAULT_EXPERT_KEY_FIELD_HIT_RATE_THRESHOLD,
) -> dict[str, Any]:
    """
    Build prompt messages and compression artifacts for expert log analysis.
    
    Args:
        path: Path to the expert agent log file (jsonl).
        factor_reports: List of factor analysis reports (markdown strings).
        answer: Optional final answer for comparison.
        use_alternative_prompt: Whether to use alternative prompt templates.
        
    Returns:
        Dict containing prompt messages and compressed payload artifacts.
    """
    log_rows = read_jsonl(path)
    raw_log_text = json.dumps(log_rows, ensure_ascii=False)
    raw_factor_text = json.dumps(factor_reports, ensure_ascii=False)

    compressed_log_raw = compress_log_messages(log_rows, source_path=path)
    compressed_factor_reports_raw = compress_markdown_reports(factor_reports)
    compressed_log = _apply_section_pruning(compressed_log_raw, AGGRESSIVE_EXPERT_SECTION_LIMITS)
    compressed_factor_reports = _apply_section_pruning(
        compressed_factor_reports_raw,
        AGGRESSIVE_FACTOR_REPORT_SECTION_LIMITS,
    )

    expert_max_chars = DEFAULT_EXPERT_PROMPT_MAX_CHARS
    factor_max_chars = DEFAULT_FACTOR_PROMPT_MAX_CHARS
    factor_hit_rate_threshold = min(
        DEFAULT_FACTOR_KEY_FIELD_HIT_RATE_THRESHOLD,
        key_field_hit_rate_threshold,
    )
    log_backfill_count = 0
    factor_backfill_count = 0

    compressed_log_text = _render_compact_payload(
        compressed_log,
        max_chars=expert_max_chars,
        profile="expert",
    )
    compressed_factor_text = _render_compact_payload(
        compressed_factor_reports,
        max_chars=factor_max_chars,
        profile="factor",
    )
    expert_hit = calculate_key_field_hit_rate(raw_log_text, compressed_log_text)
    factor_hit = calculate_key_field_hit_rate(raw_factor_text, compressed_factor_text)

    log_backfill_count += _inject_missing_key_fields(
        compressed_log,
        expert_hit.get("missing_examples", []),
        section_name="key_field_backfill",
        max_items=MAX_MISSING_BACKFILL_PER_PAYLOAD,
    )
    factor_backfill_count += _inject_missing_key_fields(
        compressed_factor_reports,
        factor_hit.get("missing_examples", []),
        section_name="key_field_backfill",
        max_items=MAX_MISSING_BACKFILL_PER_PAYLOAD,
    )
    if log_backfill_count or factor_backfill_count:
        compressed_log = _apply_section_pruning(compressed_log, AGGRESSIVE_EXPERT_SECTION_LIMITS)
        compressed_factor_reports = _apply_section_pruning(
            compressed_factor_reports,
            AGGRESSIVE_FACTOR_REPORT_SECTION_LIMITS,
        )
        compressed_log_text = _render_compact_payload(
            compressed_log,
            max_chars=expert_max_chars,
            profile="expert",
        )
        compressed_factor_text = _render_compact_payload(
            compressed_factor_reports,
            max_chars=factor_max_chars,
            profile="factor",
        )
        expert_hit = calculate_key_field_hit_rate(raw_log_text, compressed_log_text)
        factor_hit = calculate_key_field_hit_rate(raw_factor_text, compressed_factor_text)

    needs_relax = (
        _hit_rate(expert_hit) < key_field_hit_rate_threshold
        or _hit_rate(factor_hit) < factor_hit_rate_threshold
    )
    if needs_relax:
        expert_max_chars = RELAXED_EXPERT_PROMPT_MAX_CHARS
        factor_max_chars = RELAXED_FACTOR_PROMPT_MAX_CHARS
        log_backfill_count += _inject_raw_key_fields(
            compressed_log,
            raw_log_text,
            section_name="key_field_backfill",
            max_urls=36,
            max_dates=24,
            max_boxed=16,
        )
        factor_backfill_count += _inject_raw_key_fields(
            compressed_factor_reports,
            raw_factor_text,
            section_name="key_field_backfill",
            max_urls=20,
            max_dates=18,
            max_boxed=12,
        )
        compressed_log = _apply_section_pruning(compressed_log, AGGRESSIVE_EXPERT_SECTION_LIMITS)
        compressed_factor_reports = _apply_section_pruning(
            compressed_factor_reports,
            AGGRESSIVE_FACTOR_REPORT_SECTION_LIMITS,
        )
        compressed_log_text = _render_compact_payload(
            compressed_log,
            max_chars=expert_max_chars,
            profile="expert",
        )
        compressed_factor_text = _render_compact_payload(
            compressed_factor_reports,
            max_chars=factor_max_chars,
            profile="factor",
        )
        expert_hit = calculate_key_field_hit_rate(raw_log_text, compressed_log_text)
        factor_hit = calculate_key_field_hit_rate(raw_factor_text, compressed_factor_text)

        extra_log_backfill = _inject_missing_key_fields(
            compressed_log,
            expert_hit.get("missing_examples", []),
            section_name="key_field_backfill",
            max_items=MAX_MISSING_BACKFILL_PER_PAYLOAD,
        )
        extra_factor_backfill = _inject_missing_key_fields(
            compressed_factor_reports,
            factor_hit.get("missing_examples", []),
            section_name="key_field_backfill",
            max_items=MAX_MISSING_BACKFILL_PER_PAYLOAD,
        )
        log_backfill_count += extra_log_backfill
        factor_backfill_count += extra_factor_backfill
        if extra_log_backfill or extra_factor_backfill:
            compressed_log = _apply_section_pruning(compressed_log, AGGRESSIVE_EXPERT_SECTION_LIMITS)
            compressed_factor_reports = _apply_section_pruning(
                compressed_factor_reports,
                AGGRESSIVE_FACTOR_REPORT_SECTION_LIMITS,
            )
            compressed_log_text = _render_compact_payload(
                compressed_log,
                max_chars=expert_max_chars,
                profile="expert",
            )
            compressed_factor_text = _render_compact_payload(
                compressed_factor_reports,
                max_chars=factor_max_chars,
                profile="factor",
            )
            expert_hit = calculate_key_field_hit_rate(raw_log_text, compressed_log_text)
            factor_hit = calculate_key_field_hit_rate(raw_factor_text, compressed_factor_text)

    expert_metrics = compressed_log_raw.get("compression_metrics", {})
    factor_metrics = compressed_factor_reports_raw.get("compression_metrics", {})
    expert_raw_chars = int(expert_metrics.get("raw_chars", len(raw_log_text)) or 0)
    factor_raw_chars = int(factor_metrics.get("raw_chars", len(raw_factor_text)) or 0)
    expert_prompt_chars = len(compressed_log_text)
    factor_prompt_chars = len(compressed_factor_text)
    raw_prompt_chars = expert_raw_chars + factor_raw_chars
    compressed_prompt_chars = expert_prompt_chars + factor_prompt_chars
    prompt_reduction_ratio = round(_safe_ratio(compressed_prompt_chars, raw_prompt_chars), 4)
    expert_reduction_ratio = round(_safe_ratio(expert_prompt_chars, expert_raw_chars), 4)
    factor_reduction_ratio = round(_safe_ratio(factor_prompt_chars, factor_raw_chars), 4)

    compression_header = (
        f"expert_raw={expert_metrics.get('raw_chars', 'n/a')}, "
        f"expert_compressed={expert_metrics.get('compressed_chars', 'n/a')}, "
        f"expert_ratio={expert_metrics.get('reduction_ratio', 0.0)}, "
        f"factor_raw={factor_metrics.get('raw_chars', 'n/a')}, "
        f"factor_compressed={factor_metrics.get('compressed_chars', 'n/a')}, "
        f"factor_ratio={factor_metrics.get('reduction_ratio', 0.0)}, "
        f"expert_key_field_hit_rate={expert_hit.get('hit_rate', 'n/a')}, "
        f"factor_key_field_hit_rate={factor_hit.get('hit_rate', 'n/a')}"
    )
    
    if use_alternative_prompt:
        # shiyu_dev提示词
        sys_prompt = """
        你是一个日志分析专家。你现在正在对一个执行预测任务的多智能体系统的部分日志执行分析工作。
        这个多智能体系统由一个主智能体负责统筹调度和任务分解，调用子智能体对子任务进行分析。
        你将被提供主智能体的执行日志，以及其他分析师对主智能体调用的各个子智能体日志的分析报告。
        你的任务是分析主智能体的日志。
        请你分析主智能体的执行流程，对任务的分解是否合理，是否合理的调用了子智能体，是否正确的理解和使用了子智能体传回的结果，作出最终决策的逻辑是否合理，依据了哪些关键线索和证据。
        你应该将你的分析结果输出为纯markdown格式的字符串，不要包含多余的字符，可以直接存储进.md文件。
        """
        if answer:
            sys_prompt += "\n你还需要参考最终的答案，思考主智能体的最终预测是否正确。如果不正确，请你分析可能导致预测失败的原因"
        
        user_prompt = f"""
        以下是你需要分析的主智能体日志（结构化压缩版）：
        {compression_header}
        {compressed_log_text}
        以下是其他分析师对于主智能体调用的各个子智能体分析报告（结构化压缩版）：
        {compressed_factor_text}
        """
        if answer:
            user_prompt += f"\n以下是最终的答案：\n{answer}"
        user_prompt += "\n现在，请你给出你的分析报告，需要为纯md格式："
    else:
        # galaxy框架提示词
        sys_prompt = """
        你是一个日志分析专家。你现在正在对一个执行预测任务的多智能体系统的部分日志执行分析工作。
        这个多智能体由一个专家智能体调用多个子智能体进行分析，最后子智能体的结果交由专家智能体进行聚合。
        你将被提供专家智能体的执行日志，以及其他分析师对各个子智能体的分析报告。
        你的任务是分析专家智能体的执行日志。
        你需要分析子智能体给出了哪些关键数值、指标或结果，需要分析专家智能体做出决策的逻辑是否正确以及依据了什么关键证据、是否充分。
        """
        if answer:
            sys_prompt += "\n你还需要参考最终的答案，思考专家智能体的决策是否正确。如果不正确，请你分析可能导致预测失败的原因"
        
        sys_prompt += "\n你应该将你的分析结果输出为纯markdown格式的字符串，不要包含多余的字符，可以直接存储进.md文件。"
        user_prompt = f"""
        以下是你需要分析的专家智能体日志（结构化压缩版）：
        {compression_header}
        {compressed_log_text}
        以下是其他分析师对于该专家所调用子智能体的分析报告（结构化压缩版）：
        {compressed_factor_text}
        """
        if answer:
            user_prompt += f"\n以下是最终的答案：\n{answer}"
        user_prompt += "\n现在，请你给出你的分析报告，需要为纯md格式："
    
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt}
    ]

    return {
        "messages": messages,
        "compressed_log": compressed_log,
        "compressed_log_text": compressed_log_text,
        "compressed_factor_reports": compressed_factor_reports,
        "compressed_factor_text": compressed_factor_text,
        "expert_key_field_hit_rate": expert_hit,
        "factor_key_field_hit_rate": factor_hit,
        "compression_header": compression_header,
        "prompt_compression_stats": {
            "raw_prompt_chars": raw_prompt_chars,
            "compressed_prompt_chars": compressed_prompt_chars,
            "prompt_reduction_ratio": prompt_reduction_ratio,
            "expert_reduction_ratio": expert_reduction_ratio,
            "factor_reduction_ratio": factor_reduction_ratio,
            "expert_prompt_chars": expert_prompt_chars,
            "factor_prompt_chars": factor_prompt_chars,
            "expert_budget_chars": expert_max_chars,
            "factor_budget_chars": factor_max_chars,
            "expert_key_field_hit_rate": expert_hit.get("hit_rate", "n/a"),
            "factor_key_field_hit_rate": factor_hit.get("hit_rate", "n/a"),
            "log_backfill_count": log_backfill_count,
            "factor_backfill_count": factor_backfill_count,
        },
    }


def shiyu_task_analysis_prompt(
    path: str,
    factor_reports: List[str],
    answer: str = None,
    use_alternative_prompt: bool = False,
) -> list[dict]:
    payload = build_expert_prompt_payload(path, factor_reports, answer, use_alternative_prompt)
    return payload["messages"]


def _factor_analysis_report_path(analysis_folder: Path, factor_file: Path) -> Path:
    return analysis_folder / f"factor_{factor_file.stem}_analysis.md"


async def analyze_expert_log(client: 'LLMClient', factor_reports: List[str], expert_log_path: str, answer: str = None, use_alternative_prompt: bool = False) -> str:
    """
    Analyze expert agent log using LLM with structured output.
    
    Args:
        client: The async LLMClient instance.
        factor_reports: List of factor analysis reports.
        expert_log_path: Path to the expert agent log file.
        answer: Optional final answer for comparison.
        use_alternative_prompt: Whether to use alternative prompt templates.
        
    Returns:
        str: The expert analysis report in Markdown format.
    """
    payload = build_expert_prompt_payload(expert_log_path, factor_reports, answer, use_alternative_prompt)
    print(_format_expert_prompt_stats(payload, expert_log_path))
    messages = payload["messages"]
    response = await client.chat_structured(messages, response_format=MarkdownResponse)
    return response.content


async def run_full_analysis(client: 'LLMClient', folder_path: str, answer: str = None, concurrency_limit: int = 10, use_alternative_prompt: bool = False) -> None:
    """
    Run the full analysis pipeline: analyze all factor logs, then analyze expert log,
    and save all reports to the 'analysis' subfolder.
    
    Args:
        client: The async LLMClient instance.
        folder_path: Path to the task folder (e.g., 'data/galaxy_futurex_0204/.../685e48ac...').
        answer: Optional final answer for comparison.
        concurrency_limit: Maximum number of concurrent factor analysis tasks. Defaults to 10.
        use_alternative_prompt: Whether to use alternative prompt templates.
    """
    folder = Path(folder_path)
    factors_folder = folder / "factors"
    analysis_folder = folder / "analysis"
    expert_report_path = analysis_folder / "expert_analysis.md"
    if expert_report_path.is_file():
        print(f"Skip completed task (expert report exists): {expert_report_path}")
        return

    # Create analysis folder if it doesn't exist
    analysis_folder.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Find all jsonl files in the factors folder
    factor_files = list(factors_folder.glob("*.jsonl"))
    
    if not factor_files:
        print(f"No .jsonl files found in {factors_folder}")
        return
    
    print(f"Found {len(factor_files)} factor log files for task{folder_path}. Starting analysis...")
    
    # Step 2: Reuse existing factor reports; only generate missing ones.
    factor_reports_map = {}
    missing_factor_files = []

    for factor_file in factor_files:
        report_path = _factor_analysis_report_path(analysis_folder, factor_file)
        if report_path.is_file():
            factor_reports_map[factor_file] = read_md_to_string(str(report_path))
            print(f"Reuse existing factor report: {report_path}")
        else:
            missing_factor_files.append(factor_file)

    if missing_factor_files:
        print(f"Need to generate {len(missing_factor_files)} missing factor reports.")
        # Limit to 'concurrency_limit' concurrent requests to avoid overwhelming the API
        sem = asyncio.Semaphore(concurrency_limit)

        async def analyze_with_limit(file_path: Path) -> tuple[Path, str]:
            async with sem:
                report = await analyze_factor_log(client, str(file_path), use_alternative_prompt)
                return file_path, report

        factor_tasks = [analyze_with_limit(f) for f in missing_factor_files]
        generated_results = await asyncio.gather(*factor_tasks)

        # Step 3: Save generated factor reports
        for factor_file, report in generated_results:
            report_path = _factor_analysis_report_path(analysis_folder, factor_file)
            save_string_to_md(report, str(report_path))
            factor_reports_map[factor_file] = report
            print(f"Saved factor report: {report_path}")

            factor_payload = build_factor_prompt_payload(str(factor_file), use_alternative_prompt)
            factor_compression_report_path = analysis_folder / f"factor_{factor_file.stem}_compression_report.md"
            factor_compression_report_content = render_factor_compression_report(
                str(factor_file),
                factor_payload["compressed_log"],
                factor_payload["compressed_log_text"],
            )
            save_string_to_md(factor_compression_report_content, str(factor_compression_report_path))
            print(f"Saved factor compression report: {factor_compression_report_path}")
    else:
        print("All factor reports already exist, skip factor regeneration.")

    factor_reports = [factor_reports_map[factor_file] for factor_file in factor_files]
    
    # Step 4: Find expert log (expecting a single file starting with 'expert' and ending with '.jsonl')
    expert_log_candidates = list(folder.glob("expert*.jsonl"))
    if not expert_log_candidates:
        print(f"No expert log (expert*.jsonl) found in {folder}. Skipping expert analysis.")
        return
    
    if len(expert_log_candidates) > 1:
        print(f"Warning: Multiple expert logs found in {folder}. Using the first one: {expert_log_candidates[0].name}")

    expert_log_path = str(expert_log_candidates[0])
    print(f"Analyzing expert log: {expert_log_path}")
    
    # Step 5: Analyze expert log using the factor reports
    expert_report = await analyze_expert_log(client, list(factor_reports), expert_log_path, answer, use_alternative_prompt)
    
    # Step 6: Save expert analysis report (completion marker)
    save_string_to_md(expert_report, str(expert_report_path))
    print(f"Saved expert report: {expert_report_path}")

    expert_payload = build_expert_prompt_payload(
        path=expert_log_path,
        factor_reports=list(factor_reports),
        answer=answer,
        use_alternative_prompt=use_alternative_prompt,
    )
    expert_compression_report_path = analysis_folder / "expert_compression_report.md"
    expert_compression_report_content = render_expert_compression_report(
        expert_log_path=expert_log_path,
        compressed_expert_log=expert_payload["compressed_log"],
        compressed_expert_text=expert_payload["compressed_log_text"],
        compressed_factor_reports=expert_payload["compressed_factor_reports"],
        compressed_factor_text=expert_payload["compressed_factor_text"],
        factor_report_count=len(factor_reports),
    )
    save_string_to_md(expert_compression_report_content, str(expert_compression_report_path))
    print(f"Saved expert compression report: {expert_compression_report_path}")
    
    print(f"\nAll analysis reports saved to: {analysis_folder}")


if __name__ == "__main__":
    from llm_client import LLMClient
    
    async def main():
        async with LLMClient("openai/gpt-5.2") as client:
            await run_full_analysis(client, r"data\galaxy_futurex_0204\galaxy_futurex_0204\685e48ac6e8dbd006cdc6f71", answer=None, concurrency_limit=5)

    asyncio.run(main())