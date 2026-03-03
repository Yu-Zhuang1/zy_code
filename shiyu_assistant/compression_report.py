from typing import Any


TRUNCATION_MARKER = "...[truncated]..."


def _truncate_middle(text: str, max_chars: int) -> str:
    if not isinstance(text, str):
        return ""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= len(TRUNCATION_MARKER) + 2:
        return text[:max_chars]
    head_len = (max_chars - len(TRUNCATION_MARKER)) // 2
    tail_len = max_chars - len(TRUNCATION_MARKER) - head_len
    return f"{text[:head_len]}{TRUNCATION_MARKER}{text[-tail_len:]}"


def _metric(payload: dict[str, Any], key: str) -> Any:
    metrics = payload.get("compression_metrics")
    if not isinstance(metrics, dict):
        return "n/a"
    return metrics.get(key, "n/a")


def _section_count(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, list):
        return len(value)
    return 0


def _preview_lines(items: Any, limit: int = 5, max_chars: int = 220) -> list[str]:
    if not isinstance(items, list):
        return []

    results: list[str] = []
    for item in items:
        line = str(item).strip()
        if not line:
            continue
        if line.startswith("- "):
            line = line[2:]
        results.append(_truncate_middle(line, max_chars))
        if len(results) >= limit:
            break
    return results


def render_factor_compression_report(
    file_path: str,
    compressed_log: dict[str, Any],
    compressed_log_text: str,
) -> str:
    lines: list[str] = []
    lines.append("# Compression Report")
    lines.append("")
    lines.append("- type: `factor`")
    lines.append(f"- source_file: `{file_path}`")
    lines.append("")
    lines.append("## Metrics")
    lines.append(f"- raw_chars: `{_metric(compressed_log, 'raw_chars')}`")
    lines.append(f"- compressed_chars: `{_metric(compressed_log, 'compressed_chars')}`")
    lines.append(f"- reduction_ratio: `{_metric(compressed_log, 'reduction_ratio')}`")
    lines.append("")
    lines.append("## Section Counts")
    lines.append(f"- task_context: `{_section_count(compressed_log, 'task_context')}`")
    lines.append(f"- tool_trace_compact: `{_section_count(compressed_log, 'tool_trace_compact')}`")
    lines.append(f"- key_findings: `{_section_count(compressed_log, 'key_findings')}`")
    lines.append(f"- error_summary: `{_section_count(compressed_log, 'error_summary')}`")
    lines.append(f"- final_decision: `{_section_count(compressed_log, 'final_decision')}`")
    lines.append(f"- residual_context: `{_section_count(compressed_log, 'residual_context')}`")
    lines.append("")

    lines.append("## Final Decision Preview")
    final_preview = _preview_lines(compressed_log.get("final_decision"), limit=5, max_chars=240)
    if not final_preview:
        lines.append("- (none)")
    else:
        for item in final_preview:
            lines.append(f"- {item}")
    lines.append("")

    lines.append("## Key Findings Preview")
    findings_preview = _preview_lines(compressed_log.get("key_findings"), limit=5, max_chars=240)
    if not findings_preview:
        lines.append("- (none)")
    else:
        for item in findings_preview:
            lines.append(f"- {item}")
    lines.append("")

    lines.append("## Prompt Payload Preview")
    lines.append("```json")
    lines.append(_truncate_middle(compressed_log_text, 1800))
    lines.append("```")
    return "\n".join(lines)


def render_expert_compression_report(
    expert_log_path: str,
    compressed_expert_log: dict[str, Any],
    compressed_expert_text: str,
    compressed_factor_reports: dict[str, Any],
    compressed_factor_text: str,
    factor_report_count: int,
) -> str:
    lines: list[str] = []
    lines.append("# Compression Report")
    lines.append("")
    lines.append("- type: `expert`")
    lines.append(f"- source_file: `{expert_log_path}`")
    lines.append(f"- factor_report_count: `{factor_report_count}`")
    lines.append("")
    lines.append("## Expert Log Metrics")
    lines.append(f"- raw_chars: `{_metric(compressed_expert_log, 'raw_chars')}`")
    lines.append(f"- compressed_chars: `{_metric(compressed_expert_log, 'compressed_chars')}`")
    lines.append(f"- reduction_ratio: `{_metric(compressed_expert_log, 'reduction_ratio')}`")
    lines.append("")
    lines.append("## Factor Reports Metrics")
    lines.append(f"- raw_chars: `{_metric(compressed_factor_reports, 'raw_chars')}`")
    lines.append(f"- compressed_chars: `{_metric(compressed_factor_reports, 'compressed_chars')}`")
    lines.append(f"- reduction_ratio: `{_metric(compressed_factor_reports, 'reduction_ratio')}`")
    lines.append("")
    lines.append("## Expert Section Counts")
    lines.append(f"- task_context: `{_section_count(compressed_expert_log, 'task_context')}`")
    lines.append(f"- tool_trace_compact: `{_section_count(compressed_expert_log, 'tool_trace_compact')}`")
    lines.append(f"- key_findings: `{_section_count(compressed_expert_log, 'key_findings')}`")
    lines.append(f"- error_summary: `{_section_count(compressed_expert_log, 'error_summary')}`")
    lines.append(f"- final_decision: `{_section_count(compressed_expert_log, 'final_decision')}`")
    lines.append(f"- residual_context: `{_section_count(compressed_expert_log, 'residual_context')}`")
    lines.append("")

    lines.append("## Aggregate Findings Preview")
    findings_preview = _preview_lines(compressed_factor_reports.get("aggregate_findings"), limit=5, max_chars=240)
    if not findings_preview:
        lines.append("- (none)")
    else:
        for item in findings_preview:
            lines.append(f"- {item}")
    lines.append("")

    lines.append("## Expert Final Decision Preview")
    final_preview = _preview_lines(compressed_expert_log.get("final_decision"), limit=5, max_chars=240)
    if not final_preview:
        lines.append("- (none)")
    else:
        for item in final_preview:
            lines.append(f"- {item}")
    lines.append("")

    lines.append("## Prompt Payload Preview (Expert)")
    lines.append("```json")
    lines.append(_truncate_middle(compressed_expert_text, 1400))
    lines.append("```")
    lines.append("")

    lines.append("## Prompt Payload Preview (Factor Reports)")
    lines.append("```json")
    lines.append(_truncate_middle(compressed_factor_text, 1400))
    lines.append("```")
    return "\n".join(lines)
