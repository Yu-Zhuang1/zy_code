import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.file_utils import save_json
from miroflow_assistant.log_compression_rules import (
    BOXED_ANSWER_RE,
    CONFLICT_KEYWORDS,
    DATE_RE,
    DECISIVE_KEYWORDS,
    ERROR_SIGNATURE_PATTERNS,
    EVIDENCE_LIMITS,
    MESSAGE_CHAR_BUDGET,
    NUMBER_RE,
    PROMPT_SECTION_CHAR_BUDGET,
    RESIDUAL_CONTEXT_LIMITS,
    SEARCH_QUERY_RE,
    SEARCH_RESULT_TOP_K,
    SEARCH_SNIPPET_MAX_CHARS,
    TASK_CONSTRAINT_KEYWORDS,
    THINK_BLOCK_RE,
    WEBPAGE_NOISE_CONTAINS,
    WEBPAGE_NOISE_PREFIXES,
    extract_domain,
)


TRUNCATION_PLACEHOLDER = "...[truncated]..."
MAX_ERROR_BUCKETS = 12
TOOL_CALL_BLOCK_RE = re.compile(r"<use_mcp_tool>.*?</use_mcp_tool>", re.IGNORECASE | re.DOTALL)
FINAL_ANSWER_INSTRUCTION_MARKERS = (
    "must end with this exact format",
    "wrap your final answer in",
    "your final answer should be",
    "do not use any other format",
    "follow the format instruction",
)


def _truncate_middle(content: str, max_chars: int) -> str:
    if not isinstance(content, str):
        return ""
    if max_chars <= 0:
        return ""
    if len(content) <= max_chars:
        return content

    head = int(max_chars * 0.7)
    tail = max_chars - head - len(TRUNCATION_PLACEHOLDER)
    if tail < 0:
        return content[:max_chars]
    return content[:head] + TRUNCATION_PLACEHOLDER + content[-tail:]


def _normalize_space(content: str) -> str:
    if not isinstance(content, str):
        return ""
    return re.sub(r"\s+", " ", content).strip()


def _strip_think_blocks(content: str) -> str:
    if not isinstance(content, str):
        return ""
    cleaned = THINK_BLOCK_RE.sub("", content).strip()
    return cleaned


def _try_json_loads(content: str) -> Any:
    if not isinstance(content, str):
        return None
    try:
        return json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return None


def _looks_like_search_payload(content: str) -> bool:
    if not isinstance(content, str):
        return False
    stripped = content.strip()
    return stripped.startswith("{") and '"searchParameters"' in stripped


def _looks_like_webpage_markdown(content: str) -> bool:
    if not isinstance(content, str):
        return False

    lowered = content.lower()
    if "[skip to main content]" in lowered:
        return True
    if "main navigation menu" in lowered:
        return True
    if "close ad" in lowered:
        return True

    first_lines = [line.strip().lower() for line in content.splitlines()[:30] if line.strip()]
    if not first_lines:
        return False

    noisy_prefix_hits = 0
    for line in first_lines:
        if any(line.startswith(prefix) for prefix in WEBPAGE_NOISE_PREFIXES):
            noisy_prefix_hits += 1
    return noisy_prefix_hits >= 2


def _compact_tool_call_xml(content: str) -> str:
    if not isinstance(content, str):
        return ""

    server_match = re.search(r"<server_name>(.*?)</server_name>", content, re.DOTALL)
    tool_match = re.search(r"<tool_name>(.*?)</tool_name>", content, re.DOTALL)
    args_match = re.search(r"<arguments>\s*(.*?)\s*</arguments>", content, re.DOTALL)

    server_name = _normalize_space(server_match.group(1)) if server_match else ""
    tool_name = _normalize_space(tool_match.group(1)) if tool_match else ""
    arguments = _normalize_space(args_match.group(1)) if args_match else ""

    if server_name or tool_name:
        compact = {
            "type": "tool_call",
            "server_name": server_name,
            "tool_name": tool_name,
            "arguments": _truncate_middle(arguments, 220),
        }
        return json.dumps(compact, ensure_ascii=False)

    return _truncate_middle(content, MESSAGE_CHAR_BUDGET["tool_call"])


def _compact_search_payload(content: str) -> str:
    payload = _try_json_loads(content)
    if not isinstance(payload, dict):
        query_match = SEARCH_QUERY_RE.search(content)
        query = query_match.group(1) if query_match else ""
        fallback = {
            "type": "search_result",
            "query": query,
            "raw_excerpt": _truncate_middle(content, MESSAGE_CHAR_BUDGET["fallback"]),
        }
        return json.dumps(fallback, ensure_ascii=False)

    params = payload.get("searchParameters", {})
    query = params.get("q", "") if isinstance(params, dict) else ""
    organic = payload.get("organic", [])
    compact_results = []
    if isinstance(organic, list):
        for item in organic[:SEARCH_RESULT_TOP_K]:
            if not isinstance(item, dict):
                continue
            title = _truncate_middle(str(item.get("title", "")), 100)
            link = str(item.get("link", ""))
            snippet = _truncate_middle(str(item.get("snippet", "")), SEARCH_SNIPPET_MAX_CHARS)
            date = str(item.get("date", ""))
            compact_results.append(
                {
                    "domain": extract_domain(link),
                    "title": title,
                    "snippet": snippet,
                    "date": date,
                }
            )

    compact = {"type": "search_result", "query": query, "top_results": compact_results}
    search_info = payload.get("searchInformation")
    if isinstance(search_info, dict) and search_info.get("didYouMean"):
        compact["did_you_mean"] = str(search_info.get("didYouMean"))

    return json.dumps(compact, ensure_ascii=False)


def _clean_web_markdown(content: str) -> str:
    if not isinstance(content, str):
        return ""

    cleaned_lines: list[str] = []
    seen = set()
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lower = line.lower()
        if any(lower.startswith(prefix) for prefix in WEBPAGE_NOISE_PREFIXES):
            continue
        if any(token in lower for token in WEBPAGE_NOISE_CONTAINS):
            continue
        if lower in {"menu", "sports", "tickets"}:
            continue
        if len(line) <= 1:
            continue
        if line in seen:
            continue

        seen.add(line)
        cleaned_lines.append(line)
        if len(cleaned_lines) >= 80:
            break

    if not cleaned_lines:
        return _truncate_middle(content, MESSAGE_CHAR_BUDGET["webpage_markdown"])

    cleaned = "\n".join(cleaned_lines)
    return _truncate_middle(cleaned, MESSAGE_CHAR_BUDGET["webpage_markdown"])


def _is_tool_error(content: str) -> bool:
    if not isinstance(content, str):
        return False
    lowered = content.lower()
    return (
        ("tool call to" in lowered and "failed" in lowered)
        or lowered.startswith("tool result error - tool:")
        or "failed to connect to sandbox" in lowered
        or "status 403" in lowered
        or "failed to retrieve page" in lowered
    )


def _canonicalize_error(content: str) -> tuple[str, str]:
    normalized = _normalize_space(content)
    for name, pattern in ERROR_SIGNATURE_PATTERNS:
        match = pattern.search(content)
        if not match:
            continue
        detail = match.group(1).strip() if match.groups() else ""
        detail_suffix = f":{detail}" if detail else ""
        key = f"{name}{detail_suffix}"
        summary = f"{name}{detail_suffix}"
        return key, summary
    return f"generic:{normalized[:80]}", normalized[:220]


def _extract_excerpt(content: str, keywords: tuple[str, ...], max_chars: int) -> str:
    if not isinstance(content, str):
        return ""
    lowered = content.lower()
    idx = -1
    for keyword in keywords:
        k_idx = lowered.find(keyword.lower())
        if k_idx != -1:
            idx = k_idx
            break

    if idx == -1:
        return _truncate_middle(content, max_chars)

    half = max_chars // 2
    start = max(0, idx - half)
    end = min(len(content), idx + half)
    return _truncate_middle(content[start:end], max_chars)


def _split_message_fragments(content: str) -> list[dict[str, str]]:
    if not isinstance(content, str):
        return []

    fragments: list[dict[str, str]] = []
    cursor = 0

    for match in TOOL_CALL_BLOCK_RE.finditer(content):
        text_part = content[cursor : match.start()].strip()
        if text_part:
            fragments.append({"kind": "text", "content": text_part})

        tool_part = match.group(0).strip()
        if tool_part:
            fragments.append({"kind": "tool_call", "content": tool_part})
        cursor = match.end()

    tail = content[cursor:].strip()
    if tail:
        fragments.append({"kind": "text", "content": tail})

    if not fragments and content.strip():
        fragments.append({"kind": "text", "content": content.strip()})

    return fragments


def _looks_like_final_answer(role: str, content: str) -> bool:
    if role != "assistant":
        return False
    if not isinstance(content, str):
        return False

    normalized = content.strip()
    if not normalized:
        return False

    lowered = normalized.lower()
    if any(marker in lowered for marker in FINAL_ANSWER_INSTRUCTION_MARKERS):
        return False

    matches = list(BOXED_ANSWER_RE.finditer(normalized))
    if not matches:
        return False

    last_match = matches[-1]
    trailing = normalized[last_match.end() :].strip()
    return trailing == ""


def _classify_message(role: str, content: str, raw_content: str) -> str:
    if _looks_like_final_answer(role, content):
        return "final_answer"
    if _is_tool_error(content):
        return "tool_error"
    if _looks_like_search_payload(content):
        return "tool_result_search_json"
    if _looks_like_webpage_markdown(content):
        return "tool_result_webpage_markdown"
    if "<use_mcp_tool>" in content:
        return "tool_call_xml"
    if role == "assistant" and "<think>" in (raw_content or ""):
        return "assistant_think"
    if role == "user" and any(key in content.lower() for key in TASK_CONSTRAINT_KEYWORDS):
        return "task_or_instruction"
    return "residual"


def _message_budget(scope: str, role: str, msg_type: str) -> int:
    if msg_type == "tool_call_xml":
        return MESSAGE_CHAR_BUDGET["tool_call"]
    if msg_type == "tool_result_webpage_markdown":
        return MESSAGE_CHAR_BUDGET["webpage_markdown"]
    if scope == "main":
        return MESSAGE_CHAR_BUDGET["main_user"] if role == "user" else MESSAGE_CHAR_BUDGET["main_assistant"]
    return MESSAGE_CHAR_BUDGET["sub_user"] if role == "user" else MESSAGE_CHAR_BUDGET["sub_assistant"]


def _iter_all_messages(data: dict) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    main_msgs = data.get("main_agent_message_history", {}).get("message_history", [])
    for idx, msg in enumerate(main_msgs):
        rows.append(("main", "main", str(idx), str(msg.get("content", ""))))

    sub_sessions = data.get("sub_agent_message_history_sessions", {})
    for session_name, session_data in sub_sessions.items():
        sub_msgs = session_data.get("message_history", [])
        for idx, msg in enumerate(sub_msgs):
            rows.append(("sub", str(session_name), str(idx), str(msg.get("content", ""))))
    return rows


def get_message_content_length(data: dict) -> int:
    total_len = 0
    for _, _, _, content in _iter_all_messages(data):
        if isinstance(content, str):
            total_len += len(content)
    return total_len


def _collect_anchor_samples(data: dict) -> dict[str, list[str]]:
    decisive: list[str] = []
    conflict: list[str] = []
    constraints: list[str] = []
    seen = set()

    task_description = str(data.get("input", {}).get("task_description", ""))
    if task_description:
        for line in task_description.splitlines():
            normalized = line.strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if any(token in lowered for token in TASK_CONSTRAINT_KEYWORDS) and normalized not in seen:
                constraints.append(_truncate_middle(normalized, 220))
                seen.add(normalized)
            if len(constraints) >= 6:
                break

    for _, session_name, msg_idx, content in _iter_all_messages(data):
        lowered = content.lower()
        ref = f"{session_name}:{msg_idx}"
        if any(token in lowered for token in DECISIVE_KEYWORDS):
            excerpt = _extract_excerpt(content, DECISIVE_KEYWORDS, 220)
            key = f"d:{excerpt}"
            if key not in seen:
                decisive.append(f"[{ref}] {excerpt}")
                seen.add(key)
        if any(token in lowered for token in CONFLICT_KEYWORDS):
            excerpt = _extract_excerpt(content, CONFLICT_KEYWORDS, 220)
            key = f"c:{excerpt}"
            if key not in seen:
                conflict.append(f"[{ref}] {excerpt}")
                seen.add(key)

        if len(decisive) >= 6 and len(conflict) >= 6:
            break

    return {
        "task_constraints": constraints[:6],
        "decisive_signals": decisive[:6],
        "conflict_signals": conflict[:6],
    }


def collect_log_baseline_metrics_from_data(data: dict) -> dict[str, Any]:
    total_messages = 0
    total_chars = 0
    think_messages = 0
    search_payload_messages = 0
    scrape_server_not_found = 0
    google_tool_result_error = 0
    webpage_noise_messages = 0
    tool_call_messages = 0

    for _, _, _, content in _iter_all_messages(data):
        if not isinstance(content, str):
            continue
        total_messages += 1
        total_chars += len(content)

        lowered = content.lower()
        if "<think>" in lowered:
            think_messages += 1
        if _looks_like_search_payload(content):
            search_payload_messages += 1
        if "tool call to scrape_website on tool-scrape_website failed" in lowered:
            scrape_server_not_found += 1
        if lowered.startswith("tool result error - tool: google_search"):
            google_tool_result_error += 1
        if _looks_like_webpage_markdown(content):
            webpage_noise_messages += 1
        if "<use_mcp_tool>" in lowered:
            tool_call_messages += 1

    step_logs = data.get("step_logs", [])
    step_level_counter: Counter[str] = Counter()
    if isinstance(step_logs, list):
        for item in step_logs:
            if isinstance(item, dict):
                step_level_counter[str(item.get("info_level", "info"))] += 1

    return {
        "status": data.get("status"),
        "task_id": data.get("task_id"),
        "sub_agent_counter": data.get("sub_agent_counter"),
        "total_messages": total_messages,
        "total_content_chars": total_chars,
        "think_messages": think_messages,
        "search_payload_messages": search_payload_messages,
        "scrape_server_not_found_messages": scrape_server_not_found,
        "google_tool_result_error_messages": google_tool_result_error,
        "webpage_noise_messages": webpage_noise_messages,
        "tool_call_messages": tool_call_messages,
        "step_log_counts": {
            "info": step_level_counter.get("info", 0),
            "warning": step_level_counter.get("warning", 0),
            "error": step_level_counter.get("error", 0),
        },
        "key_anchors": _collect_anchor_samples(data),
    }


def collect_log_baseline_metrics(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return collect_log_baseline_metrics_from_data(data)


def _record_evidence(
    evidence_store: dict[str, Any],
    content: str,
    source: str,
    role: str,
    msg_type: str,
) -> None:
    if not content:
        return

    lowered = content.lower()
    if any(token in lowered for token in DECISIVE_KEYWORDS):
        excerpt = _extract_excerpt(content, DECISIVE_KEYWORDS, EVIDENCE_LIMITS["excerpt_max_chars"])
        key = f"d::{excerpt}"
        if key not in evidence_store["seen"]:
            evidence_store["decisive"].append(
                {"source": source, "role": role, "type": msg_type, "excerpt": excerpt}
            )
            evidence_store["seen"].add(key)

    if any(token in lowered for token in CONFLICT_KEYWORDS):
        excerpt = _extract_excerpt(content, CONFLICT_KEYWORDS, EVIDENCE_LIMITS["excerpt_max_chars"])
        key = f"c::{excerpt}"
        if key not in evidence_store["seen"]:
            evidence_store["conflict"].append(
                {"source": source, "role": role, "type": msg_type, "excerpt": excerpt}
            )
            evidence_store["seen"].add(key)

    if msg_type == "final_answer":
        excerpt = _extract_excerpt(content, ("\\boxed{", "final answer"), EVIDENCE_LIMITS["excerpt_max_chars"])
        key = f"d::final::{excerpt}"
        if key not in evidence_store["seen"]:
            evidence_store["decisive"].append(
                {"source": source, "role": role, "type": "final_answer", "excerpt": excerpt}
            )
            evidence_store["seen"].add(key)


def _compress_message_history(
    raw_messages: list[dict],
    scope: str,
    session_name: str,
    error_store: dict[str, dict[str, Any]],
    evidence_store: dict[str, Any],
) -> list[dict]:
    cleaned_messages: list[dict] = []

    for idx, msg in enumerate(raw_messages):
        role = str(msg.get("role", ""))
        raw_content = msg.get("content", "")
        if not isinstance(raw_content, str):
            continue

        stripped = _strip_think_blocks(raw_content)
        fragments = _split_message_fragments(stripped)
        if not fragments:
            continue

        for fragment_idx, fragment in enumerate(fragments):
            fragment_kind = str(fragment.get("kind", "text"))
            fragment_content = str(fragment.get("content", "")).strip()
            if not fragment_content:
                continue

            msg_type = "tool_call_xml"
            if fragment_kind != "tool_call":
                msg_type = _classify_message(role, fragment_content, raw_content)

            source_ref = f"{scope}:{session_name}:{idx}:{fragment_idx}"

            if msg_type == "tool_result_search_json":
                compressed = _compact_search_payload(fragment_content)
            elif msg_type == "tool_result_webpage_markdown":
                compressed = _clean_web_markdown(fragment_content)
            elif msg_type == "tool_call_xml":
                compressed = _compact_tool_call_xml(fragment_content)
            elif msg_type == "tool_error":
                err_key, err_summary = _canonicalize_error(fragment_content)
                bucket = error_store.setdefault(
                    err_key,
                    {
                        "error_type": err_key,
                        "count": 0,
                        "first_source": source_ref,
                        "last_source": source_ref,
                        "example": _truncate_middle(fragment_content, 220),
                    },
                )
                bucket["count"] += 1
                bucket["last_source"] = source_ref
                if bucket["count"] > 1:
                    continue
                compressed = f"tool_error::{err_summary}"
            else:
                budget = _message_budget(scope, role, msg_type)
                compressed = _truncate_middle(fragment_content, budget)

            if not compressed:
                continue

            _record_evidence(evidence_store, compressed, source_ref, role, msg_type)
            cleaned_messages.append({"role": role, "content": compressed})

    return cleaned_messages


def _summarize_step_logs(step_logs: list[dict]) -> dict[str, Any]:
    level_counter: Counter[str] = Counter()
    milestones: list[dict[str, str]] = []
    error_buckets: dict[str, dict[str, Any]] = {}

    for idx, row in enumerate(step_logs):
        if not isinstance(row, dict):
            continue
        level = str(row.get("info_level", "info"))
        message = str(row.get("message", ""))
        step_name = str(row.get("step_name", ""))
        timestamp = str(row.get("timestamp", ""))
        level_counter[level] += 1

        marker_text = f"{step_name} {message}".lower()
        if (
            "task start" in marker_text
            or "start task" in marker_text
            or "final answer" in marker_text
            or "task completed" in marker_text
        ):
            milestones.append(
                {
                    "step_name": step_name,
                    "message": _truncate_middle(message, 220),
                    "timestamp": timestamp,
                }
            )

        if level in {"warning", "error"} and message:
            key, summary = _canonicalize_error(message)
            bucket = error_buckets.setdefault(
                key,
                {
                    "error_type": key,
                    "count": 0,
                    "first_step_index": idx,
                    "last_step_index": idx,
                    "example": _truncate_middle(summary, 220),
                },
            )
            bucket["count"] += 1
            bucket["last_step_index"] = idx

    return {
        "counts": {
            "info": level_counter.get("info", 0),
            "warning": level_counter.get("warning", 0),
            "error": level_counter.get("error", 0),
        },
        "milestones": milestones[:12],
        "error_buckets": sorted(error_buckets.values(), key=lambda x: x["count"], reverse=True)[
            :MAX_ERROR_BUCKETS
        ],
    }


def _build_residual_context(
    cleaned_main_history: dict[str, Any], cleaned_sub_sessions: dict[str, Any]
) -> dict[str, Any]:
    main_messages = cleaned_main_history.get("message_history", [])
    main_recent = main_messages[-RESIDUAL_CONTEXT_LIMITS["main_recent_messages"] :]
    main_recent = [
        {
            "role": msg.get("role", ""),
            "content": _truncate_middle(
                str(msg.get("content", "")),
                RESIDUAL_CONTEXT_LIMITS["message_max_chars"],
            ),
        }
        for msg in main_recent
    ]

    sub_recent: dict[str, list[dict[str, str]]] = {}
    for session_name, session_data in cleaned_sub_sessions.items():
        session_msgs = session_data.get("message_history", [])
        recent_msgs = session_msgs[-RESIDUAL_CONTEXT_LIMITS["sub_recent_messages"] :]
        sub_recent[session_name] = [
            {
                "role": msg.get("role", ""),
                "content": _truncate_middle(
                    str(msg.get("content", "")),
                    RESIDUAL_CONTEXT_LIMITS["message_max_chars"],
                ),
            }
            for msg in recent_msgs
        ]

    return {"main_recent_messages": main_recent, "sub_recent_messages": sub_recent}


def _trim_evidence_items(
    items: list[dict[str, Any]],
    max_items: int,
    budget_chars: int,
) -> list[dict[str, Any]]:
    trimmed: list[dict[str, Any]] = []
    used = 0
    for item in items:
        if len(trimmed) >= max_items:
            break
        excerpt = _truncate_middle(str(item.get("excerpt", "")), EVIDENCE_LIMITS["excerpt_max_chars"])
        candidate = {
            "source": str(item.get("source", "")),
            "role": str(item.get("role", "")),
            "type": str(item.get("type", "")),
            "excerpt": excerpt,
        }
        candidate_len = len(json.dumps(candidate, ensure_ascii=False))
        if used + candidate_len > budget_chars:
            break
        trimmed.append(candidate)
        used += candidate_len
    return trimmed


def _apply_prompt_bundle_budget(prompt_bundle: dict[str, Any]) -> dict[str, Any]:
    task_context = prompt_bundle.get("task_context", {})
    if isinstance(task_context, dict):
        task_description = str(task_context.get("task_description", ""))
        task_context["task_description"] = _truncate_middle(
            task_description, PROMPT_SECTION_CHAR_BUDGET["task_context"]
        )
        prompt_bundle["task_context"] = task_context

    prompt_bundle["decisive_evidence"] = _trim_evidence_items(
        list(prompt_bundle.get("decisive_evidence", [])),
        EVIDENCE_LIMITS["decisive_max_items"],
        PROMPT_SECTION_CHAR_BUDGET["decisive_evidence"],
    )
    prompt_bundle["conflict_evidence"] = _trim_evidence_items(
        list(prompt_bundle.get("conflict_evidence", [])),
        EVIDENCE_LIMITS["conflict_max_items"],
        PROMPT_SECTION_CHAR_BUDGET["conflict_evidence"],
    )

    error_summary = prompt_bundle.get("error_summary", {})
    if isinstance(error_summary, dict):
        buckets = error_summary.get("message_error_buckets", [])
        if isinstance(buckets, list):
            serialized = 0
            trimmed_buckets = []
            for bucket in buckets:
                if len(trimmed_buckets) >= MAX_ERROR_BUCKETS:
                    break
                candidate = {
                    "error_type": str(bucket.get("error_type", "")),
                    "count": int(bucket.get("count", 0)),
                    "first_source": str(bucket.get("first_source", "")),
                    "last_source": str(bucket.get("last_source", "")),
                    "example": _truncate_middle(str(bucket.get("example", "")), 180),
                }
                candidate_len = len(json.dumps(candidate, ensure_ascii=False))
                if serialized + candidate_len > PROMPT_SECTION_CHAR_BUDGET["error_summary"]:
                    break
                trimmed_buckets.append(candidate)
                serialized += candidate_len
            error_summary["message_error_buckets"] = trimmed_buckets
        prompt_bundle["error_summary"] = error_summary

    residual_context = prompt_bundle.get("residual_context", {})
    residual_text = json.dumps(residual_context, ensure_ascii=False)
    if len(residual_text) > PROMPT_SECTION_CHAR_BUDGET["residual_context"]:
        residual_context = {
            "main_recent_messages": residual_context.get("main_recent_messages", [])[-8:],
            "sub_recent_messages": {
                session_name: msgs[-3:]
                for session_name, msgs in residual_context.get("sub_recent_messages", {}).items()
            },
        }
        prompt_bundle["residual_context"] = residual_context

    return prompt_bundle


def process_log_data(file_path: str) -> dict[str, Any]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON file: {file_path}")

    baseline_metrics = collect_log_baseline_metrics_from_data(data)

    cleaned_data: dict[str, Any] = {
        "status": data.get("status"),
        "start_time": data.get("start_time"),
        "task_id": data.get("task_id"),
        "final_boxed_answer": data.get("final_boxed_answer"),
        "error": data.get("error"),
    }

    input_data = data.get("input", {})
    cleaned_data["task_description"] = input_data.get("task_description")

    evidence_store: dict[str, Any] = {"decisive": [], "conflict": [], "seen": set()}
    message_error_store: dict[str, dict[str, Any]] = {}

    main_history = data.get("main_agent_message_history", {})
    cleaned_main_history: dict[str, Any] = {}
    main_system_prompt = main_history.get("system_prompt")
    if isinstance(main_system_prompt, str):
        cleaned_main_history["system_prompt"] = _truncate_middle(main_system_prompt, 1400)

    raw_main_messages = main_history.get("message_history", [])
    if isinstance(raw_main_messages, list):
        cleaned_main_history["message_history"] = _compress_message_history(
            raw_main_messages,
            scope="main",
            session_name="main",
            error_store=message_error_store,
            evidence_store=evidence_store,
        )
    else:
        cleaned_main_history["message_history"] = []

    cleaned_data["main_agent_message_history"] = cleaned_main_history

    sub_sessions = data.get("sub_agent_message_history_sessions", {})
    cleaned_sub_sessions: dict[str, Any] = {}
    if isinstance(sub_sessions, dict):
        for session_name, session_data in sub_sessions.items():
            raw_sub_messages = (
                session_data.get("message_history", [])
                if isinstance(session_data, dict)
                else []
            )
            cleaned_sub_sessions[session_name] = {
                "message_history": _compress_message_history(
                    raw_sub_messages if isinstance(raw_sub_messages, list) else [],
                    scope="sub",
                    session_name=str(session_name),
                    error_store=message_error_store,
                    evidence_store=evidence_store,
                )
            }
    cleaned_data["sub_agent_message_history_sessions"] = cleaned_sub_sessions

    step_summary = _summarize_step_logs(data.get("step_logs", []))
    cleaned_data["step_summary"] = step_summary

    compressed_chars = get_message_content_length(cleaned_data)
    raw_chars = int(baseline_metrics.get("total_content_chars", 0))
    ratio = 0.0
    if raw_chars > 0:
        ratio = max(0.0, min(1.0, 1.0 - compressed_chars / raw_chars))

    message_error_buckets = sorted(
        message_error_store.values(),
        key=lambda item: int(item.get("count", 0)),
        reverse=True,
    )

    prompt_bundle = {
        "task_context": {
            "task_id": cleaned_data.get("task_id"),
            "status": cleaned_data.get("status"),
            "task_description": str(cleaned_data.get("task_description") or ""),
            "final_boxed_answer": cleaned_data.get("final_boxed_answer"),
        },
        "decisive_evidence": evidence_store["decisive"],
        "conflict_evidence": evidence_store["conflict"],
        "error_summary": {
            "message_error_buckets": message_error_buckets,
            "step_log_counts": step_summary.get("counts", {}),
            "step_milestones": step_summary.get("milestones", []),
            "step_error_buckets": step_summary.get("error_buckets", []),
        },
        "residual_context": _build_residual_context(cleaned_main_history, cleaned_sub_sessions),
        "compression_metrics": {
            "raw_content_chars": raw_chars,
            "compressed_content_chars": compressed_chars,
            "message_char_reduction_ratio": round(ratio, 4),
            "raw_message_count": baseline_metrics.get("total_messages"),
            "compressed_message_count": len(cleaned_main_history.get("message_history", []))
            + sum(
                len(session.get("message_history", []))
                for session in cleaned_sub_sessions.values()
            ),
        },
    }
    cleaned_data["prompt_bundle"] = _apply_prompt_bundle_budget(prompt_bundle)
    raw_prompt_chars = len(json.dumps(data, ensure_ascii=False))
    compressed_prompt_chars = len(json.dumps(cleaned_data["prompt_bundle"], ensure_ascii=False))
    prompt_reduction_ratio = 0.0
    if raw_prompt_chars > 0:
        prompt_reduction_ratio = 1.0 - compressed_prompt_chars / raw_prompt_chars
    cleaned_data["prompt_bundle"]["compression_metrics"].update(
        {
            "raw_prompt_chars": raw_prompt_chars,
            "compressed_prompt_chars": compressed_prompt_chars,
            "prompt_reduction_ratio": round(max(0.0, prompt_reduction_ratio), 4),
        }
    )

    cleaned_data["baseline_metrics"] = baseline_metrics
    cleaned_data["compression_metrics"] = cleaned_data["prompt_bundle"]["compression_metrics"]
    return cleaned_data


if __name__ == "__main__":
    processed_log = process_log_data("test/long_text_C3FBBFA9-1F78-40CE-A535-E3B662A5DC24.json")
    save_json(processed_log, "processed_log3.json")