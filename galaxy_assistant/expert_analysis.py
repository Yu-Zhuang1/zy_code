import os
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

from typing import List, Optional, TYPE_CHECKING, Any

from utils.file_utils import read_jsonl, save_string_to_md, read_md_to_string
from schema import MarkdownResponse
from galaxy_assistant.factor_analysis import analyze_factor_log
from shiyu_assistant.log_compression import (
    compress_log_messages,
    compress_markdown_reports,
    format_compressed_payload,
    calculate_key_field_hit_rate,
)

if TYPE_CHECKING:
    from LLM_CLIENT import LLMClient


THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
BOXED_RE = re.compile(r"\\boxed\s*\{[^}]+\}")
BOXED_TRAILING_RE = re.compile(r"^[\s\.,;:!?\)\]\}\"'`_-]*$")
FORMAT_NOISE_MARKERS = (
    "must end with this exact format",
    "do not use any other format",
    "we are now ending this session",
    "you must not initiate any further tool use",
    "summarize all working history",
    "output the final answer in the format",
    "the original question is repeated here for reference",
    "required json schema",
    "return only a valid json object",
)

DEFAULT_EXPERT_MAX_CHARS = 7600
DEFAULT_FACTOR_MAX_CHARS = 3800
RELAXED_EXPERT_MAX_CHARS = 9800
RELAXED_FACTOR_MAX_CHARS = 5600
DEFAULT_KEY_FIELD_HIT_RATE_THRESHOLD = 0.82
DEFAULT_FACTOR_KEY_FIELD_HIT_RATE_THRESHOLD = 0.24
MAX_MISSING_BACKFILL_PER_PAYLOAD = 8

DATE_TOKEN_RE = re.compile(
    r"\b20\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])\b"
)
URL_TOKEN_RE = re.compile(r"https?://[^\s)\]>\"'\\]+")

AGGRESSIVE_LOG_SECTION_LIMITS: dict[str, dict[str, int]] = {
    "task_context": {"max_items": 3, "max_chars": 150},
    "tool_trace_compact": {"max_items": 6, "max_chars": 150},
    "key_findings": {"max_items": 12, "max_chars": 180},
    "error_summary": {"max_items": 3, "max_chars": 150},
    "final_decision": {"max_items": 5, "max_chars": 180},
    "residual_context": {"max_items": 2, "max_chars": 140},
}

AGGRESSIVE_FACTOR_SECTION_LIMITS: dict[str, dict[str, int]] = {
    "report_compact": {"max_items": 7, "max_chars": 170},
    "aggregate_findings": {"max_items": 9, "max_chars": 170},
    "aggregate_errors": {"max_items": 3, "max_chars": 150},
}


def _truncate_middle(text: str, max_chars: int) -> str:
    marker = "...[truncated]..."
    if not isinstance(text, str):
        return ""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    head_len = (max_chars - len(marker)) // 2
    tail_len = max_chars - len(marker) - head_len
    return f"{text[:head_len]}{marker}{text[-tail_len:]}"


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - numerator / denominator))


def _format_expert_prompt_stats(payload: dict[str, Any], expert_log_path: str) -> str:
    stats = payload.get("prompt_compression_stats", {})
    strict_boxed = payload.get("strict_boxed")
    strict_boxed_found = bool(strict_boxed)
    strict_boxed_value = strict_boxed.get("boxed") if strict_boxed_found else "none"
    task_id = Path(expert_log_path).parent.name
    return (
        "[ExpertPromptStats] "
        f"task={task_id} "
        f"raw={stats.get('raw_prompt_chars', 'n/a')} "
        f"compressed={stats.get('compressed_prompt_chars', 'n/a')} "
        f"reduction={stats.get('prompt_reduction_ratio', 'n/a')} "
        f"expert_ratio={stats.get('expert_reduction_ratio', 'n/a')} "
        f"factor_ratio={stats.get('factor_reduction_ratio', 'n/a')} "
        f"strict_boxed_hit={strict_boxed_found} "
        f"strict_boxed={strict_boxed_value}"
    )


def _strip_think_blocks(content: str) -> str:
    if not isinstance(content, str):
        return ""
    return THINK_BLOCK_RE.sub("", content).strip()


def _is_format_noise(content: str) -> bool:
    lowered = content.lower()
    return any(marker in lowered for marker in FORMAT_NOISE_MARKERS)


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen = set()
    results: list[str] = []
    for item in items:
        normalized = item.strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        results.append(normalized)
    return results


def _normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


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
    rendered = format_compressed_payload(
        payload,
        max_chars=max_chars,
        profile=profile,
    )
    return _minify_json_text(rendered)


def _is_priority_line(line: str) -> bool:
    lowered = line.lower()
    if any(
        marker in lowered
        for marker in (
            "strict_final_boxed",
            "strict_final_source",
            "fallback_final_candidate",
            "recover_boxed",
            "recover_url",
            "recover_date",
            "boxed:",
            "\\boxed",
            "url:",
            "key_numbers_dates",
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
        score += 25
    if section in {"key_findings", "aggregate_findings"}:
        if any(token in lowered for token in ("evidence", "signal", "confidence", "source")):
            score += 10
    if section in {"error_summary", "aggregate_errors"} and any(
        token in lowered for token in ("error", "failed", "timeout", "429", "403")
    ):
        score += 8
    if "assistant@" in lowered or "tool@" in lowered or "report_" in lowered:
        score += 3
    if len(line) <= 120:
        score += 2
    return score


def _prune_section_items(
    items: list[Any],
    section: str,
    max_items: int,
    max_line_chars: int,
) -> list[str]:
    prepared: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, item in enumerate(items):
        line = str(item).strip()
        if not line or _is_format_noise(line):
            continue
        if _normalize_key(line).startswith("- recover_"):
            # Keep recovered key fields intact to preserve exact URL/date/boxed matching.
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
        for key in ("total_messages", "strict_boxed_detection"):
            if key in meta:
                compact_meta[key] = meta[key]
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
    if not value:
        return None
    return field_type, value


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


def _hit_rate(hit: dict[str, Any]) -> float:
    try:
        return float(hit.get("hit_rate", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _extract_strict_final_boxed(log_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    只在 assistant 消息中提取“最终结论形态”的 boxed：
    - 忽略 think 块与格式说明噪音
    - 仅接受消息尾部 boxed（尾部仅允许空白或轻量标点）
    - 多候选时取最后一个（最接近真正最终输出）
    """
    candidates: list[dict[str, Any]] = []

    for idx, row in enumerate(log_rows):
        role = str(row.get("role", "")).strip().lower()
        if role != "assistant":
            continue

        content = _strip_think_blocks(str(row.get("content", "")))
        if not content or _is_format_noise(content):
            continue

        matches = list(BOXED_RE.finditer(content))
        if not matches:
            continue

        last_match = matches[-1]
        trailing = content[last_match.end() :]
        if not BOXED_TRAILING_RE.match(trailing):
            continue

        candidates.append(
            {
                "index": idx,
                "boxed": last_match.group(0).strip(),
                "message_excerpt": _truncate_middle(content, 260),
            }
        )

    if not candidates:
        return None
    return candidates[-1]


def _extract_fallback_final_candidate(log_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    当 strict boxed 未命中时，回退到最后一条高置信 assistant 结论片段。
    """
    for idx in range(len(log_rows) - 1, -1, -1):
        row = log_rows[idx]
        role = str(row.get("role", "")).strip().lower()
        if role != "assistant":
            continue

        content = _strip_think_blocks(str(row.get("content", "")))
        if not content or _is_format_noise(content):
            continue

        return {
            "index": idx,
            "content": _truncate_middle(content, 280),
        }
    return None


def _inject_final_decision(
    compressed_log: dict[str, Any],
    strict_boxed: dict[str, Any] | None,
    fallback_candidate: dict[str, Any] | None,
) -> None:
    existing = compressed_log.get("final_decision", [])
    existing_lines = [str(item).strip() for item in existing] if isinstance(existing, list) else []
    existing_lines = [line for line in existing_lines if line and not _is_format_noise(line)]
    # 清理可能来自推理链/模板说明的 boxed 提及，避免误导模型。
    existing_lines = [line for line in existing_lines if "\\boxed" not in line.lower()]

    final_lines: list[str] = []
    if strict_boxed:
        final_lines.append(f"- strict_final_boxed: {strict_boxed['boxed']}")
        final_lines.append(f"- strict_final_source: assistant@{strict_boxed['index']}")
    else:
        final_lines.append("- strict_final_boxed: not_found")
        if fallback_candidate:
            final_lines.append(
                "- fallback_final_candidate: "
                f"assistant@{fallback_candidate['index']} -> {fallback_candidate['content']}"
            )
        else:
            final_lines.append("- fallback_final_candidate: unavailable")

    compressed_log["final_decision"] = _dedupe_keep_order(final_lines + existing_lines)[:12]

    meta = compressed_log.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    meta["strict_boxed_detection"] = {
        "found": bool(strict_boxed),
        "boxed": strict_boxed.get("boxed") if strict_boxed else None,
        "source_index": strict_boxed.get("index") if strict_boxed else None,
        "fallback_used": strict_boxed is None,
        "fallback_source_index": fallback_candidate.get("index") if fallback_candidate else None,
    }
    compressed_log["meta"] = meta


def build_expert_prompt_payload(
    path: str,
    factor_analysis: List[str],
    answer: str = None,
    use_alternative_prompt: bool = False,
    key_field_hit_rate_threshold: float = DEFAULT_KEY_FIELD_HIT_RATE_THRESHOLD,
) -> dict[str, Any]:
    """
    Build compressed prompt messages and payload metadata for expert analysis.
    
    Args:
        path: Path to the expert agent log file (jsonl).
        factor_analysis: List of factor analysis reports (markdown strings).
        answer: Optional final answer for comparison.
        use_alternative_prompt: Whether to use alternative prompt templates.
        key_field_hit_rate_threshold: Minimum key-field hit rate before relaxing budgets.
        
    Returns:
        Dict containing prompt messages and compression artifacts.
    """
    log_rows = read_jsonl(path)
    raw_log_text = json.dumps(log_rows, ensure_ascii=False)
    raw_factor_text = json.dumps(factor_analysis, ensure_ascii=False)
    compressed_log_raw = compress_log_messages(log_rows, source_path=path)
    compressed_factor_reports_raw = compress_markdown_reports(factor_analysis)

    strict_boxed = _extract_strict_final_boxed(log_rows)
    fallback_candidate = None if strict_boxed else _extract_fallback_final_candidate(log_rows)
    _inject_final_decision(compressed_log_raw, strict_boxed, fallback_candidate)

    compressed_log = _apply_section_pruning(compressed_log_raw, AGGRESSIVE_LOG_SECTION_LIMITS)
    compressed_factor_reports = _apply_section_pruning(
        compressed_factor_reports_raw,
        AGGRESSIVE_FACTOR_SECTION_LIMITS,
    )

    expert_max_chars = DEFAULT_EXPERT_MAX_CHARS
    factor_max_chars = DEFAULT_FACTOR_MAX_CHARS
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
        section_name="aggregate_findings",
        max_items=MAX_MISSING_BACKFILL_PER_PAYLOAD,
    )

    if log_backfill_count or factor_backfill_count:
        compressed_log = _apply_section_pruning(compressed_log, AGGRESSIVE_LOG_SECTION_LIMITS)
        compressed_factor_reports = _apply_section_pruning(
            compressed_factor_reports,
            AGGRESSIVE_FACTOR_SECTION_LIMITS,
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
        expert_max_chars = RELAXED_EXPERT_MAX_CHARS
        factor_max_chars = RELAXED_FACTOR_MAX_CHARS
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
            section_name="aggregate_findings",
            max_items=MAX_MISSING_BACKFILL_PER_PAYLOAD,
        )
        log_backfill_count += extra_log_backfill
        factor_backfill_count += extra_factor_backfill
        if extra_log_backfill or extra_factor_backfill:
            compressed_log = _apply_section_pruning(compressed_log, AGGRESSIVE_LOG_SECTION_LIMITS)
            compressed_factor_reports = _apply_section_pruning(
                compressed_factor_reports,
                AGGRESSIVE_FACTOR_SECTION_LIMITS,
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
        f"factor_key_field_hit_rate={factor_hit.get('hit_rate', 'n/a')}, "
        f"strict_boxed_found={bool(strict_boxed)}, "
        f"strict_boxed={strict_boxed.get('boxed') if strict_boxed else 'none'}"
    )
    
    if use_alternative_prompt:
        # shiyu_dev提示词
        sys_prompt = """
        你是一个日志分析专家。你现在正在对一个执行预测任务的多智能体系统的部分日志执行分析工作。
        这个多智能体系统由一个主智能体负责统筹调度和任务分解，调用子智能体对子任务进行分析。
        你将被提供主智能体的执行日志，以及其他分析师对主智能体调用的各个子智能体日志的分析报告。
        你的任务是分析主智能体的日志。
        请将你的分析过程明确分为以下两个阶段：
        1. 流程梳理：分析主智能体的整体执行流程，任务分解是否合理，是否合理地调用了子智能体，以及是否正确地理解和使用了子智能体传回的结果。梳理它作出最终决策的逻辑是否合理，依据了哪些关键线索和证据。
        2. 错误检查：详细检查整个流程中是否出现任何错误、执行瑕疵或不合理的任务下发。
        你应该将你的分析结果输出为纯markdown格式的字符串，不要包含多余的字符，可以直接存储进.md文件。
        【极其重要】：你具备联网搜索能力（search_web工具），并且我设定了允许你连续多次调用它！当日志中出现多个你不确定的：时间/休市日要求、API接口字段、特定报错码、业务公式或事件细节时，你**必须**针对每一个疑点分别发起多次 search_web 调用，直到所有关键事实都被互联网数据交叉验证过为止。不要靠猜测下结论，充分利用你的搜索权限！
        """
        if answer:
            sys_prompt += "\n在错误检查阶段，你还需要参考最终的答案，思考主智能体的最终预测是否正确。如果不正确，请你分析可能导致预测失败的原因。"
        
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

        请将你的分析过程明确分为以下两个阶段：
        1. 流程梳理：分析各个子智能体给出了哪些关键数值、指标或结果，梳理专家智能体统筹这些信息并做出决策的逻辑是否合理，以及依据了什么关键证据、是否充分。
        2. 错误检查：详细检查专家智能体或子智能体在执行过程中是否发生了错误，评估可能存在的薄弱环节。

        【极其重要】：你具备联网搜索能力（search_web工具），并且我设定了允许你连续多次调用它！当日志中出现多个你不确定的：时间/休市日要求、API接口字段、特定报错码、业务公式或事件细节时，你**必须**针对每一个疑点分别发起多次 search_web 调用，直到所有关键事实都被互联网数据交叉验证过为止。由于搜索次数有限，请务必按照重要性顺序，优先搜索最核心、最可能导致严重误判的疑点。不要靠猜测下结论，充分利用你的搜索权限！
        """
        if answer:
            sys_prompt += "\n在错误检查阶段，你还需要参考最终的答案，思考专家智能体的决策是否正确。如果不正确，请你分析可能导致预测失败的原因。"
        
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
        {"role": "user", "content": user_prompt},
    ]
    return {
        "messages": messages,
        "compressed_log": compressed_log,
        "compressed_log_text": compressed_log_text,
        "compressed_factor_reports": compressed_factor_reports,
        "compressed_factor_text": compressed_factor_text,
        "strict_boxed": strict_boxed,
        "fallback_candidate": fallback_candidate,
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
            "log_backfill_count": log_backfill_count,
            "factor_backfill_count": factor_backfill_count,
        },
    }


def galaxy_task_analysis_prompt(path: str, factor_analysis: List[str], answer: str = None, use_alternative_prompt: bool = False) -> list[dict]:
    payload = build_expert_prompt_payload(path, factor_analysis, answer, use_alternative_prompt)
    return payload["messages"]


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
    
    # If expert report already exists, this task has been fully completed.
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
        report_name = f"factor_{factor_file.stem}_analysis.md"
        report_path = analysis_folder / report_name
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
            report_name = f"factor_{factor_file.stem}_analysis.md"
            report_path = analysis_folder / report_name
            save_string_to_md(report, str(report_path))
            factor_reports_map[factor_file] = report
            print(f"Saved factor report: {report_path}")
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
    
    print(f"\nAll analysis reports saved to: {analysis_folder}")


if __name__ == "__main__":
    from llm_client import LLMClient
    
    async def main():
        async with LLMClient("openai/gpt-5.2") as client:
            await run_full_analysis(client, r"data\galaxy_futurex_0204\galaxy_futurex_0204\685e48ac6e8dbd006cdc6f71", answer=None, concurrency_limit=5)

    asyncio.run(main())