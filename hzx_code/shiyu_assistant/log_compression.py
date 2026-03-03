import json
import re
from collections import Counter
from copy import deepcopy
from typing import Any

TRUNCATION_PLACEHOLDER = "...[truncated]..."

SECTION_BUDGET = {
    "task_context": 3200,
    "tool_trace_compact": 4400,
    "key_findings": 4200,
    "error_summary": 1800,
    "final_decision": 2200,
    "residual_context": 2200,
}

REPORT_SECTION_BUDGET = {
    "report_compact": 5000,
    "aggregate_findings": 2600,
    "aggregate_errors": 1400,
}

RENDER_PROFILE_MAX_CHARS = {
    "factor": 9000,
    "expert": 13000,
    "balanced": 12000,
}

RENDER_PROFILE_MIN_ITEMS = {
    "factor": {
        "residual_context": 2,
        "tool_trace_compact": 5,
        "task_context": 5,
        "error_summary": 2,
        "key_findings": 6,
        "final_decision": 1,
    },
    "expert": {
        "residual_context": 4,
        "tool_trace_compact": 8,
        "task_context": 6,
        "error_summary": 3,
        "key_findings": 9,
        "final_decision": 2,
    },
    "balanced": {
        "residual_context": 3,
        "tool_trace_compact": 7,
        "task_context": 6,
        "error_summary": 2,
        "key_findings": 8,
        "final_decision": 2,
    },
}

RENDER_DEGRADE_ORDER = (
    "residual_context",
    "tool_trace_compact",
    "task_context",
    "error_summary",
    "key_findings",
    "final_decision",
)

BOXED_RE = re.compile(r"\\boxed\s*\{[^}]+\}")
URL_RE = re.compile(r"https?://[^\s)\]>\"'\\]+")
DATE_RE = re.compile(
    r"\b(?:20\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])|"
    r"(?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])[-/.]20\d{2})\b"
)
NUMBER_RE = re.compile(r"(?<!\w)(?:[-+]?\d+(?:\.\d+)?%?|[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?)(?!\w)")
TOOL_CALL_BLOCK_RE = re.compile(r"<use_mcp_tool>.*?</use_mcp_tool>", re.IGNORECASE | re.DOTALL)
TOOL_SERVER_RE = re.compile(r"<server_name>(.*?)</server_name>", re.IGNORECASE | re.DOTALL)
TOOL_NAME_RE = re.compile(r"<tool_name>(.*?)</tool_name>", re.IGNORECASE | re.DOTALL)
TOOL_ARGS_RE = re.compile(r"<arguments>\s*(.*?)\s*</arguments>", re.IGNORECASE | re.DOTALL)

MAX_KEY_URL_FIELDS = 36
MAX_KEY_DATE_FIELDS = 24

TASK_KEYWORDS = (
    "task",
    "question",
    "constraint",
    "must",
    "should",
    "format",
    "final answer",
    "resolution source",
    "market will resolve",
    "选项",
    "任务",
    "约束",
)
FINDING_KEYWORDS = (
    "final",
    "conclusion",
    "answer",
    "evidence",
    "source",
    "confidence",
    "probability",
    "odds",
    "forecast",
    "predict",
    "result",
    "winner",
    "结论",
    "证据",
    "来源",
    "概率",
    "预测",
)
ERROR_KEYWORDS = (
    "error",
    "failed",
    "exception",
    "timeout",
    "429",
    "403",
    "400",
    "traceback",
    "invalid",
    "denied",
)

FINAL_ANSWER_INSTRUCTION_MARKERS = (
    "must end with this exact format",
    "do not use any other format",
    "we are now ending this session",
    "you must not initiate any further tool use",
    "summarize all working history",
    "output the final answer in the format",
    "the original question is repeated here for reference",
)

FORMAT_NOISE_MARKERS = FINAL_ANSWER_INSTRUCTION_MARKERS + (
    "conversation history will be deleted",
    "this is your final opportunity",
    "focus on factual, specific, and well-organized information",
)


def _safe_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _truncate_middle(text: str, max_chars: int) -> str:
    text = text.strip()
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= len(TRUNCATION_PLACEHOLDER) + 2:
        return text[:max_chars]
    head_len = (max_chars - len(TRUNCATION_PLACEHOLDER)) // 2
    tail_len = max_chars - len(TRUNCATION_PLACEHOLDER) - head_len
    return f"{text[:head_len]}{TRUNCATION_PLACEHOLDER}{text[-tail_len:]}"


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = _normalize_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item.strip())
    return result


def _extract_lines_by_keywords(
    text: str,
    keywords: tuple[str, ...],
    max_lines: int = 6,
    max_line_chars: int = 260,
) -> list[str]:
    lowered_keywords = tuple(k.lower() for k in keywords)
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if any(k in low for k in lowered_keywords):
            lines.append(_truncate_middle(line, max_line_chars))
        if len(lines) >= max_lines:
            break
    return _dedupe_keep_order(lines)


def _extract_dates_and_numbers(text: str, max_items: int = 8) -> list[str]:
    dates = DATE_RE.findall(text)
    numbers = NUMBER_RE.findall(text)
    merged: list[str] = []
    for value in dates + numbers:
        token = value.strip()
        if not token:
            continue
        merged.append(token)
        if len(merged) >= max_items:
            break
    return _dedupe_keep_order(merged)


def _normalize_url(url: str) -> str:
    normalized = url.strip().replace("\\/", "/")
    for marker in ("\\n", "\\t", "\n", "\t", "|", "##", "**"):
        if marker in normalized:
            normalized = normalized.split(marker, 1)[0]
    normalized = normalized.strip("`'\"<>[](){}")
    normalized = normalized.rstrip(".,;:!?)\\")
    normalized = normalized.strip()
    if not normalized.lower().startswith(("http://", "https://")):
        return ""
    return normalized


def _extract_urls(text: str, max_items: int = 24) -> list[str]:
    urls: list[str] = []
    for matched in URL_RE.findall(text):
        normalized = _normalize_url(matched)
        if not normalized:
            continue
        urls.append(normalized)
        if len(urls) >= max_items:
            break
    return _dedupe_keep_order(urls)


def _split_message_fragments(text: str) -> list[dict[str, str]]:
    if not isinstance(text, str):
        return []
    fragments: list[dict[str, str]] = []
    cursor = 0
    for match in TOOL_CALL_BLOCK_RE.finditer(text):
        leading = text[cursor:match.start()].strip()
        if leading:
            fragments.append({"kind": "text", "content": leading})
        tool_block = match.group(0).strip()
        if tool_block:
            fragments.append({"kind": "tool_call", "content": tool_block})
        cursor = match.end()

    trailing = text[cursor:].strip()
    if trailing:
        fragments.append({"kind": "text", "content": trailing})
    if not fragments and text.strip():
        fragments.append({"kind": "text", "content": text.strip()})
    return fragments


def _looks_like_format_instruction(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in FORMAT_NOISE_MARKERS)


def _looks_like_final_answer(role: str, text: str) -> bool:
    if role != "assistant":
        return False
    normalized = text.strip()
    if not normalized:
        return False
    if _looks_like_format_instruction(normalized):
        return False
    boxed_matches = list(BOXED_RE.finditer(normalized))
    if not boxed_matches:
        return False
    if boxed_matches[0].start() <= 160:
        return True
    lowered = normalized.lower()
    return "final answer" in lowered or "final report" in lowered or "prediction" in lowered


def _looks_like_error(text: str) -> bool:
    low = text.lower()
    return any(token in low for token in ERROR_KEYWORDS)


def _looks_like_task_context(role: str, idx: int, text: str) -> bool:
    if role in {"system", "user"} and idx <= 3:
        return True
    low = text.lower()
    return any(token in low for token in TASK_KEYWORDS)


def _compact_tool_calls(tool_calls: Any) -> list[str]:
    if not isinstance(tool_calls, list):
        return []
    compact: list[str] = []
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        function_obj = call.get("function", {})
        if isinstance(function_obj, dict):
            name = _safe_text(function_obj.get("name", "unknown_tool")).strip() or "unknown_tool"
            arguments = _truncate_middle(_safe_text(function_obj.get("arguments", "")), 260)
        else:
            name = _safe_text(call.get("name", "unknown_tool")).strip() or "unknown_tool"
            arguments = _truncate_middle(_safe_text(call.get("arguments", "")), 260)
        compact.append(f"tool={name}; args={arguments}")
    return _dedupe_keep_order(compact)


def _compact_tool_call_xml(content: str) -> str:
    server_match = TOOL_SERVER_RE.search(content)
    tool_match = TOOL_NAME_RE.search(content)
    args_match = TOOL_ARGS_RE.search(content)
    server_name = _truncate_middle(_safe_text(server_match.group(1) if server_match else ""), 80)
    tool_name = _truncate_middle(_safe_text(tool_match.group(1) if tool_match else ""), 80)
    arguments = _truncate_middle(_safe_text(args_match.group(1) if args_match else ""), 240)
    if server_name or tool_name:
        return f"tool_call: server={server_name}; tool={tool_name}; args={arguments}"
    return _truncate_middle(content, 260)


def _canonical_error_signature(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"https?://\S+", "<url>", lowered)
    lowered = re.sub(r"\b\d+\b", "<num>", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return _truncate_middle(lowered, 160)


def _message_position_score(idx: int, total: int) -> float:
    if total <= 1:
        return 0.0
    return idx / (total - 1)


def _append_scored_item(bucket: list[dict[str, Any]], text: str, score: float, idx: int) -> None:
    normalized = text.strip()
    if not normalized:
        return
    bucket.append({"text": normalized, "score": score, "idx": idx})


def _pack_scored_items(
    items: list[dict[str, Any]],
    max_chars: int,
    max_items: int,
    min_items: int = 0,
) -> list[str]:
    deduped: dict[str, dict[str, Any]] = {}
    for item in items:
        text = _safe_text(item.get("text", "")).strip()
        key = _normalize_key(text)
        if not key:
            continue
        current = {
            "text": text,
            "score": float(item.get("score", 0.0)),
            "idx": int(item.get("idx", 0)),
        }
        previous = deduped.get(key)
        if previous is None:
            deduped[key] = current
            continue
        if current["score"] > previous["score"]:
            deduped[key] = current
            continue
        if current["score"] == previous["score"] and current["idx"] > previous["idx"]:
            deduped[key] = current

    ranked = sorted(deduped.values(), key=lambda row: (row["score"], row["idx"]), reverse=True)
    packed: list[str] = []
    used_chars = 0
    for row in ranked:
        if len(packed) >= max_items:
            break
        line = f"- {row['text']}"
        cost = len(line) + 1
        if used_chars + cost <= max_chars:
            packed.append(line)
            used_chars += cost
            continue
        remaining = max_chars - used_chars
        if remaining > 80:
            packed.append(f"- {_truncate_middle(row['text'], remaining - 2)}")
        break

    if min_items > 0 and len(packed) < min_items:
        for row in ranked:
            fallback = f"- {_truncate_middle(row['text'], 180)}"
            if fallback in packed:
                continue
            packed.append(fallback)
            if len(packed) >= min_items or len(packed) >= max_items:
                break
    return packed


def _select_prioritized_urls(url_rows: list[dict[str, Any]], max_items: int) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for row in url_rows:
        url = _safe_text(row.get("url", "")).strip()
        if not url:
            continue
        key = _normalize_key(url)
        priority = int(row.get("priority", 0))
        idx = int(row.get("idx", 0))
        previous = selected.get(key)
        current = {"url": url, "priority": priority, "idx": idx}
        if previous is None:
            selected[key] = current
            continue
        if current["priority"] > previous["priority"]:
            selected[key] = current
            continue
        if current["priority"] == previous["priority"] and current["idx"] > previous["idx"]:
            selected[key] = current

    ranked = sorted(selected.values(), key=lambda row: (row["priority"], row["idx"]), reverse=True)
    return ranked[:max_items]


def _select_prioritized_boxed(boxed_rows: list[dict[str, Any]], max_items: int) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for row in boxed_rows:
        boxed = _safe_text(row.get("boxed", "")).strip()
        if not boxed:
            continue
        key = _normalize_key(boxed)
        priority = int(row.get("priority", 0))
        idx = int(row.get("idx", 0))
        previous = selected.get(key)
        current = {"boxed": boxed, "priority": priority, "idx": idx}
        if previous is None:
            selected[key] = current
            continue
        if current["priority"] > previous["priority"]:
            selected[key] = current
            continue
        if current["priority"] == previous["priority"] and current["idx"] > previous["idx"]:
            selected[key] = current

    ranked = sorted(selected.values(), key=lambda row: (row["priority"], row["idx"]), reverse=True)
    return ranked[:max_items]


def compress_log_messages(messages: list[dict[str, Any]], source_path: str | None = None) -> dict[str, Any]:
    task_candidates: list[dict[str, Any]] = []
    tool_candidates: list[dict[str, Any]] = []
    finding_candidates: list[dict[str, Any]] = []
    final_candidates: list[dict[str, Any]] = []
    residual_candidates: list[dict[str, Any]] = []
    prioritized_urls: list[dict[str, Any]] = []
    prioritized_boxed: list[dict[str, Any]] = []
    error_counter: Counter[str] = Counter()
    error_example: dict[str, str] = {}

    total_messages = max(len(messages), 1)
    for idx, message in enumerate(messages):
        if not isinstance(message, dict):
            continue

        role = _safe_text(message.get("role", "unknown")).strip() or "unknown"
        content = _safe_text(message.get("content", ""))
        tool_calls = message.get("tool_calls")
        if not content and not tool_calls:
            continue

        message_pos_score = _message_position_score(idx, total_messages)
        for tool_line in _compact_tool_calls(tool_calls):
            _append_scored_item(
                tool_candidates,
                f"assistant@{idx}: {tool_line}",
                score=1.3 + message_pos_score,
                idx=idx,
            )

        fragments = _split_message_fragments(content)
        if not fragments:
            continue

        for fragment in fragments:
            fragment_kind = _safe_text(fragment.get("kind", "text"))
            fragment_text = _safe_text(fragment.get("content", "")).strip()
            if not fragment_text:
                continue

            if fragment_kind == "tool_call":
                compact_tool = _compact_tool_call_xml(fragment_text)
                _append_scored_item(
                    tool_candidates,
                    f"{role}@{idx}: {compact_tool}",
                    score=1.6 + message_pos_score,
                    idx=idx,
                )
                continue

            is_format_noise = _looks_like_format_instruction(fragment_text)
            is_final_answer = _looks_like_final_answer(role, fragment_text)
            urls = _extract_urls(fragment_text, max_items=12)
            url_priority = 3 if is_final_answer else (2 if role == "tool" else 1)
            for url in urls:
                prioritized_urls.append({"url": url, "priority": url_priority, "idx": idx})

            if role == "assistant" and not is_format_noise:
                for boxed in BOXED_RE.findall(fragment_text):
                    boxed_priority = 3 if is_final_answer else 2
                    prioritized_boxed.append({"boxed": boxed, "priority": boxed_priority, "idx": idx})

            if _looks_like_task_context(role, idx, fragment_text):
                task_lines = _extract_lines_by_keywords(
                    fragment_text,
                    TASK_KEYWORDS,
                    max_lines=4,
                    max_line_chars=220,
                )
                if task_lines:
                    for line in task_lines:
                        noise_penalty = -0.5 if is_format_noise else 0.0
                        _append_scored_item(
                            task_candidates,
                            f"{role}@{idx}: {line}",
                            score=0.9 + message_pos_score + noise_penalty,
                            idx=idx,
                        )
                elif not is_format_noise:
                    _append_scored_item(
                        task_candidates,
                        f"{role}@{idx}: {_truncate_middle(fragment_text, 260)}",
                        score=0.7 + message_pos_score,
                        idx=idx,
                    )

            if role == "tool" or "<use_mcp_tool>" in fragment_text.lower() or "tool call" in fragment_text.lower():
                tool_lines = _extract_lines_by_keywords(
                    fragment_text,
                    FINDING_KEYWORDS + ERROR_KEYWORDS,
                    max_lines=4,
                    max_line_chars=220,
                )
                if tool_lines:
                    for line in tool_lines:
                        _append_scored_item(
                            tool_candidates,
                            f"{role}@{idx}: {line}",
                            score=1.2 + message_pos_score,
                            idx=idx,
                        )
                else:
                    _append_scored_item(
                        tool_candidates,
                        f"{role}@{idx}: {_truncate_middle(fragment_text, 220)}",
                        score=1.0 + message_pos_score,
                        idx=idx,
                    )

            if not is_format_noise:
                finding_lines = _extract_lines_by_keywords(
                    fragment_text,
                    FINDING_KEYWORDS,
                    max_lines=3,
                    max_line_chars=220,
                )
                for line in finding_lines:
                    _append_scored_item(
                        finding_candidates,
                        f"{role}@{idx}: {line}",
                        score=1.2 + message_pos_score,
                        idx=idx,
                    )

                if role in {"assistant", "tool"}:
                    date_num = _extract_dates_and_numbers(fragment_text, max_items=6)
                    if date_num:
                        _append_scored_item(
                            finding_candidates,
                            f"{role}@{idx}: key_numbers_dates={', '.join(date_num)}",
                            score=0.8 + message_pos_score,
                            idx=idx,
                        )

            if is_final_answer:
                _append_scored_item(
                    final_candidates,
                    f"{role}@{idx}: {_truncate_middle(fragment_text, 320)}",
                    score=2.5 + message_pos_score,
                    idx=idx,
                )
            elif role == "assistant" and not is_format_noise and "final" in fragment_text.lower():
                _append_scored_item(
                    final_candidates,
                    f"{role}@{idx}: {_truncate_middle(fragment_text, 260)}",
                    score=1.3 + message_pos_score,
                    idx=idx,
                )

            if _looks_like_error(fragment_text):
                signature = _canonical_error_signature(fragment_text)
                error_counter[signature] += 1
                error_example.setdefault(signature, _truncate_middle(fragment_text, 200))

            if role in {"assistant", "user"}:
                residual_penalty = -0.4 if is_format_noise else 0.0
                _append_scored_item(
                    residual_candidates,
                    f"{role}@{idx}: {_truncate_middle(fragment_text, 200)}",
                    score=0.5 + message_pos_score + residual_penalty,
                    idx=idx,
                )

    for boxed_row in _select_prioritized_boxed(prioritized_boxed, max_items=12):
        boxed_text = boxed_row["boxed"]
        boxed_idx = boxed_row["idx"]
        boxed_score = 2.0 + 0.2 * boxed_row["priority"] + _message_position_score(boxed_idx, total_messages)
        _append_scored_item(
            finding_candidates,
            f"boxed: {boxed_text}",
            score=boxed_score,
            idx=boxed_idx,
        )
        _append_scored_item(
            final_candidates,
            f"boxed: {boxed_text}",
            score=boxed_score + 0.4,
            idx=boxed_idx,
        )

    for url_row in _select_prioritized_urls(prioritized_urls, max_items=40):
        url_text = url_row["url"]
        url_idx = url_row["idx"]
        url_score = 1.1 + 0.25 * url_row["priority"] + _message_position_score(url_idx, total_messages)
        _append_scored_item(
            finding_candidates,
            f"url: {url_text}",
            score=url_score,
            idx=url_idx,
        )

    if not final_candidates:
        for idx in range(len(messages) - 1, -1, -1):
            msg = messages[idx]
            if not isinstance(msg, dict):
                continue
            role = _safe_text(msg.get("role", "unknown")).strip() or "unknown"
            text = _safe_text(msg.get("content", "")).strip()
            if role not in {"assistant", "user"} or not text:
                continue
            if _looks_like_format_instruction(text):
                continue
            _append_scored_item(
                final_candidates,
                f"{role}@{idx}: {_truncate_middle(text, 260)}",
                score=1.1 + _message_position_score(idx, total_messages),
                idx=idx,
            )
            if len(final_candidates) >= 3:
                break

    error_candidates: list[dict[str, Any]] = []
    for signature, count in error_counter.most_common(12):
        sample = error_example.get(signature, "")
        _append_scored_item(
            error_candidates,
            f"type={signature}; count={count}; sample={sample}",
            score=float(count),
            idx=0,
        )

    payload = {
        "meta": {
            "source_path": source_path,
            "total_messages": len(messages),
        },
        "task_context": _pack_scored_items(
            task_candidates,
            SECTION_BUDGET["task_context"],
            max_items=16,
            min_items=3,
        ),
        "tool_trace_compact": _pack_scored_items(
            tool_candidates,
            SECTION_BUDGET["tool_trace_compact"],
            max_items=28,
            min_items=4,
        ),
        "key_findings": _pack_scored_items(
            finding_candidates,
            SECTION_BUDGET["key_findings"],
            max_items=30,
            min_items=6,
        ),
        "error_summary": _pack_scored_items(
            error_candidates,
            SECTION_BUDGET["error_summary"],
            max_items=12,
            min_items=1,
        ),
        "final_decision": _pack_scored_items(
            final_candidates,
            SECTION_BUDGET["final_decision"],
            max_items=12,
            min_items=2,
        ),
        "residual_context": _pack_scored_items(
            residual_candidates,
            SECTION_BUDGET["residual_context"],
            max_items=14,
            min_items=3,
        ),
    }

    raw_chars = len(json.dumps(messages, ensure_ascii=False))
    compressed_chars = len(json.dumps(payload, ensure_ascii=False))
    reduction_ratio = 0.0
    if raw_chars > 0:
        reduction_ratio = 1.0 - compressed_chars / raw_chars
    payload["compression_metrics"] = {
        "raw_chars": raw_chars,
        "compressed_chars": compressed_chars,
        "reduction_ratio": round(max(0.0, reduction_ratio), 4),
    }
    return payload


def compress_markdown_reports(reports: list[str]) -> dict[str, Any]:
    compact_candidates: list[dict[str, Any]] = []
    finding_candidates: list[dict[str, Any]] = []
    error_candidates: list[dict[str, Any]] = []
    raw_text = ""

    for idx, report in enumerate(reports):
        text = _safe_text(report).strip()
        if not text:
            continue
        raw_text += text
        label = f"report_{idx + 1}"
        pos_score = _message_position_score(idx, max(len(reports), 1))

        _append_scored_item(
            compact_candidates,
            f"{label}: {_truncate_middle(text, 280)}",
            score=1.0 + pos_score,
            idx=idx,
        )

        for line in _extract_lines_by_keywords(text, FINDING_KEYWORDS, max_lines=6, max_line_chars=220):
            _append_scored_item(
                finding_candidates,
                f"{label}: {line}",
                score=1.1 + pos_score,
                idx=idx,
            )

        for line in _extract_lines_by_keywords(text, ERROR_KEYWORDS, max_lines=4, max_line_chars=220):
            _append_scored_item(
                error_candidates,
                f"{label}: {line}",
                score=1.2 + pos_score,
                idx=idx,
            )

        boxed_hits = BOXED_RE.findall(text)
        if boxed_hits:
            _append_scored_item(
                compact_candidates,
                f"{label}_boxed: {' | '.join(boxed_hits[:3])}",
                score=1.4 + pos_score,
                idx=idx,
            )

        urls = _extract_urls(text, max_items=8)
        if urls:
            _append_scored_item(
                compact_candidates,
                f"{label}_urls: {' | '.join(urls[:4])}",
                score=1.3 + pos_score,
                idx=idx,
            )

    payload = {
        "report_compact": _pack_scored_items(
            compact_candidates,
            REPORT_SECTION_BUDGET["report_compact"],
            max_items=30,
            min_items=4,
        ),
        "aggregate_findings": _pack_scored_items(
            finding_candidates,
            REPORT_SECTION_BUDGET["aggregate_findings"],
            max_items=18,
            min_items=4,
        ),
        "aggregate_errors": _pack_scored_items(
            error_candidates,
            REPORT_SECTION_BUDGET["aggregate_errors"],
            max_items=12,
            min_items=1,
        ),
    }
    raw_chars = len(raw_text)
    compressed_chars = len(json.dumps(payload, ensure_ascii=False))
    reduction_ratio = 0.0
    if raw_chars > 0:
        reduction_ratio = 1.0 - compressed_chars / raw_chars
    payload["compression_metrics"] = {
        "raw_chars": raw_chars,
        "compressed_chars": compressed_chars,
        "reduction_ratio": round(max(0.0, reduction_ratio), 4),
    }
    return payload


def _shrink_section_once(payload: dict[str, Any], section: str, min_items: int) -> bool:
    items = payload.get(section)
    if not isinstance(items, list):
        return False
    if len(items) <= min_items:
        return False
    payload[section] = items[:-1]
    return True


def _shorten_longest_item_once(
    payload: dict[str, Any],
    section: str,
    min_chars: int,
) -> bool:
    items = payload.get(section)
    if not isinstance(items, list) or not items:
        return False
    longest_idx = max(range(len(items)), key=lambda i: len(_safe_text(items[i])))
    current = _safe_text(items[longest_idx])
    if len(current) <= min_chars:
        return False
    items[longest_idx] = _truncate_middle(current, max(min_chars, int(len(current) * 0.7)))
    payload[section] = items
    return True


def _render_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _resolve_render_profile(profile: str) -> str:
    if profile in RENDER_PROFILE_MAX_CHARS:
        return profile
    return "balanced"


def _apply_layered_degradation(
    payload: dict[str, Any],
    max_chars: int,
    profile: str,
) -> dict[str, Any]:
    profile_key = _resolve_render_profile(profile)
    min_items = RENDER_PROFILE_MIN_ITEMS[profile_key]
    working = deepcopy(payload)

    if len(_render_payload(working)) <= max_chars:
        return working

    for _ in range(600):
        if len(_render_payload(working)) <= max_chars:
            break
        progressed = False
        for section in RENDER_DEGRADE_ORDER:
            if _shrink_section_once(working, section, min_items=min_items[section]):
                progressed = True
                break
        if progressed:
            continue
        for section in RENDER_DEGRADE_ORDER:
            if _shorten_longest_item_once(working, section, min_chars=120):
                progressed = True
                break
        if not progressed:
            break
    return working


def format_compressed_payload(
    payload: dict[str, Any],
    max_chars: int | None = None,
    profile: str = "balanced",
) -> str:
    profile_key = _resolve_render_profile(profile)
    target_chars = max_chars if isinstance(max_chars, int) and max_chars > 0 else RENDER_PROFILE_MAX_CHARS[profile_key]
    degraded = _apply_layered_degradation(payload, max_chars=target_chars, profile=profile_key)
    return _render_payload(degraded)


def calculate_key_field_hit_rate(raw_text: str, compressed_text: str) -> dict[str, Any]:
    raw_boxed = _dedupe_keep_order(BOXED_RE.findall(raw_text))
    raw_urls = _extract_urls(raw_text, max_items=MAX_KEY_URL_FIELDS)
    raw_dates = _dedupe_keep_order(DATE_RE.findall(raw_text))[:MAX_KEY_DATE_FIELDS]

    compressed_boxed = set(_dedupe_keep_order(BOXED_RE.findall(compressed_text)))
    compressed_urls = set(_extract_urls(compressed_text, max_items=MAX_KEY_URL_FIELDS * 2))
    compressed_dates = set(_dedupe_keep_order(DATE_RE.findall(compressed_text)))

    raw_fields: list[tuple[str, str]] = []
    raw_fields.extend(("boxed", value) for value in raw_boxed)
    raw_fields.extend(("url", value) for value in raw_urls)
    raw_fields.extend(("date", value) for value in raw_dates)
    if not raw_fields:
        return {
            "matched": 0,
            "total": 0,
            "hit_rate": 1.0,
            "missing_examples": [],
        }

    matched = 0
    missing_examples: list[str] = []
    for field_type, value in raw_fields:
        exists = False
        if field_type == "boxed":
            exists = value in compressed_boxed
        elif field_type == "url":
            exists = value in compressed_urls
        elif field_type == "date":
            exists = value in compressed_dates
        else:
            exists = value in compressed_text
        if exists:
            matched += 1
        elif len(missing_examples) < 8:
            missing_examples.append(f"{field_type}:{value}")

    hit_rate = matched / len(raw_fields)
    return {
        "matched": matched,
        "total": len(raw_fields),
        "hit_rate": round(hit_rate, 4),
        "missing_examples": missing_examples,
    }
