import os
import asyncio
import sys
import json
import re
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

DEFAULT_EXPERT_MAX_CHARS = 12600
DEFAULT_FACTOR_MAX_CHARS = 8600
RELAXED_EXPERT_MAX_CHARS = 16800
RELAXED_FACTOR_MAX_CHARS = 11200
DEFAULT_KEY_FIELD_HIT_RATE_THRESHOLD = 0.90


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
    compressed_log = compress_log_messages(log_rows, source_path=path)
    compressed_factor_reports = compress_markdown_reports(factor_analysis)

    strict_boxed = _extract_strict_final_boxed(log_rows)
    fallback_candidate = None if strict_boxed else _extract_fallback_final_candidate(log_rows)
    _inject_final_decision(compressed_log, strict_boxed, fallback_candidate)

    expert_max_chars = DEFAULT_EXPERT_MAX_CHARS
    factor_max_chars = DEFAULT_FACTOR_MAX_CHARS

    compressed_log_text = format_compressed_payload(
        compressed_log,
        max_chars=expert_max_chars,
        profile="expert",
    )
    compressed_factor_text = format_compressed_payload(
        compressed_factor_reports,
        max_chars=factor_max_chars,
        profile="factor",
    )

    # 若关键字段命中率偏低，放宽预算后重渲染一次，优先保证高保真。
    raw_log_text = json.dumps(log_rows, ensure_ascii=False)
    raw_factor_text = json.dumps(factor_analysis, ensure_ascii=False)
    expert_hit = calculate_key_field_hit_rate(raw_log_text, compressed_log_text)
    factor_hit = calculate_key_field_hit_rate(raw_factor_text, compressed_factor_text)
    if float(expert_hit.get("hit_rate", 0.0)) < key_field_hit_rate_threshold:
        expert_max_chars = RELAXED_EXPERT_MAX_CHARS
        factor_max_chars = RELAXED_FACTOR_MAX_CHARS
        compressed_log_text = format_compressed_payload(
            compressed_log,
            max_chars=expert_max_chars,
            profile="expert",
        )
        compressed_factor_text = format_compressed_payload(
            compressed_factor_reports,
            max_chars=factor_max_chars,
            profile="factor",
        )
        expert_hit = calculate_key_field_hit_rate(raw_log_text, compressed_log_text)
        factor_hit = calculate_key_field_hit_rate(raw_factor_text, compressed_factor_text)

    expert_metrics = compressed_log.get("compression_metrics", {})
    factor_metrics = compressed_factor_reports.get("compression_metrics", {})
    expert_raw_chars = int(expert_metrics.get("raw_chars", 0) or 0)
    expert_compressed_chars = int(expert_metrics.get("compressed_chars", 0) or 0)
    factor_raw_chars = int(factor_metrics.get("raw_chars", 0) or 0)
    factor_compressed_chars = int(factor_metrics.get("compressed_chars", 0) or 0)
    raw_prompt_chars = expert_raw_chars + factor_raw_chars
    compressed_prompt_chars = len(compressed_log_text) + len(compressed_factor_text)
    prompt_reduction_ratio = round(_safe_ratio(compressed_prompt_chars, raw_prompt_chars), 4)
    expert_reduction_ratio = round(_safe_ratio(expert_compressed_chars, expert_raw_chars), 4)
    factor_reduction_ratio = round(_safe_ratio(factor_compressed_chars, factor_raw_chars), 4)

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