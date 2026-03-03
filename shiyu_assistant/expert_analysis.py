import os
import asyncio
import sys
from pathlib import Path

# Add project root to sys.path to allow imports from utils and other modules
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from typing import List, Optional, TYPE_CHECKING

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
)

if TYPE_CHECKING:
    from LLM_CLIENT import LLMClient


def build_expert_prompt_payload(
    path: str,
    factor_reports: List[str],
    answer: str = None,
    use_alternative_prompt: bool = False,
) -> dict:
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
    log = read_jsonl(path)
    compressed_log = compress_log_messages(log, source_path=path)
    compressed_log_text = format_compressed_payload(
        compressed_log,
        max_chars=12600,
        profile="expert",
    )
    compressed_factor_reports = compress_markdown_reports(factor_reports)
    compressed_factor_text = format_compressed_payload(
        compressed_factor_reports,
        max_chars=8600,
        profile="factor",
    )

    expert_metrics = compressed_log.get("compression_metrics", {})
    factor_metrics = compressed_factor_reports.get("compression_metrics", {})
    compression_header = (
        f"expert_raw={expert_metrics.get('raw_chars', 'n/a')}, "
        f"expert_compressed={expert_metrics.get('compressed_chars', 'n/a')}, "
        f"expert_ratio={expert_metrics.get('reduction_ratio', 0.0)}, "
        f"factor_raw={factor_metrics.get('raw_chars', 'n/a')}, "
        f"factor_compressed={factor_metrics.get('compressed_chars', 'n/a')}, "
        f"factor_ratio={factor_metrics.get('reduction_ratio', 0.0)}"
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
        "compression_header": compression_header,
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