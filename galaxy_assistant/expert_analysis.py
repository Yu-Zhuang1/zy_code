import os
import asyncio
import sys
from pathlib import Path

# Add project root to sys.path to allow imports from utils and other modules
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from typing import List, Optional, TYPE_CHECKING

from utils.file_utils import read_jsonl, save_string_to_md
from schema import MarkdownResponse
from galaxy_assistant.factor_analysis import analyze_factor_log

if TYPE_CHECKING:
    from LLM_CLIENT import LLMClient


def galaxy_task_analysis_prompt(path: str, factor_analysis: List[str], answer: str = None, use_alternative_prompt: bool = False) -> list[dict]:
    """
    Build the prompt messages for expert agent log analysis.
    
    Args:
        path: Path to the expert agent log file (jsonl).
        factor_analysis: List of factor analysis reports (markdown strings).
        answer: Optional final answer for comparison.
        use_alternative_prompt: Whether to use alternative prompt templates.
        
    Returns:
        List of message dicts for the LLM.
    """
    log = read_jsonl(path)
    
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
        以下是你需要分析的主智能体的日志：
        {log}
        以下是其他分析师对于主智能体调用的各个子智能体的分析报告：
        {factor_analysis}
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
        以下是你需要分析的专家智能体的日志：
        {log}
        以下是其他分析师对于该专家所调用的子智能体的分析报告：
        {factor_analysis}
        """
        if answer:
            user_prompt += f"\n以下是最终的答案：\n{answer}"
        user_prompt += "\n现在，请你给出你的分析报告，需要为纯md格式："
    
    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt}
    ]


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
    messages = galaxy_task_analysis_prompt(expert_log_path, factor_reports, answer, use_alternative_prompt)
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
    
    # Create analysis folder if it doesn't exist
    analysis_folder.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Find all jsonl files in the factors folder
    factor_files = list(factors_folder.glob("*.jsonl"))
    
    if not factor_files:
        print(f"No .jsonl files found in {factors_folder}")
        return
    
    print(f"Found {len(factor_files)} factor log files for task{folder_path}. Starting analysis...")
    
    # Step 2: Analyze all factor logs concurrently with a limit
    # Limit to 'concurrency_limit' concurrent requests to avoid overwhelming the API
    sem = asyncio.Semaphore(concurrency_limit)

    async def analyze_with_limit(file_path: str) -> str:
        async with sem:
            return await analyze_factor_log(client, file_path, use_alternative_prompt)

    factor_tasks = [analyze_with_limit(str(f)) for f in factor_files]
    factor_reports = await asyncio.gather(*factor_tasks)
    
    # Step 3: Save factor analysis reports
    factor_report_paths = []
    for i, (factor_file, report) in enumerate(zip(factor_files, factor_reports)):
        report_name = f"factor_{factor_file.stem}_analysis.md"
        report_path = analysis_folder / report_name
        save_string_to_md(report, str(report_path))
        factor_report_paths.append(report_path)
        print(f"Saved factor report: {report_path}")
    
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
    
    # Step 6: Save expert analysis report
    expert_report_path = analysis_folder / "expert_analysis.md"
    save_string_to_md(expert_report, str(expert_report_path))
    print(f"Saved expert report: {expert_report_path}")
    
    print(f"\nAll analysis reports saved to: {analysis_folder}")


if __name__ == "__main__":
    from llm_client import LLMClient
    
    async def main():
        async with LLMClient("openai/gpt-5.2") as client:
            await run_full_analysis(client, r"data\galaxy_futurex_0204\galaxy_futurex_0204\685e48ac6e8dbd006cdc6f71", answer=None, concurrency_limit=5)

    asyncio.run(main())