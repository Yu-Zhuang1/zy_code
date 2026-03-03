import os
import sys
import asyncio
from pathlib import Path
import re
import json

# Add project root to sys.path if not present
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from schema import MarkdownResponse
from miroflow_assistant.log_process import process_log_data
from utils.file_utils import save_string_to_md
from typing import Any, TYPE_CHECKING
if TYPE_CHECKING:
    from llm_client import LLMClient


def _truncate_middle(content: str, max_chars: int) -> str:
    if not isinstance(content, str):
        return ""
    if max_chars <= 0:
        return ""
    if len(content) <= max_chars:
        return content
    marker = "...[truncated]..."
    head = int(max_chars * 0.65)
    tail = max_chars - head - len(marker)
    if tail < 0:
        return content[:max_chars]
    return content[:head] + marker + content[-tail:]


def _format_prompt_bundle(log: dict) -> str:
    bundle = log.get("prompt_bundle") if isinstance(log, dict) else None
    if not isinstance(bundle, dict):
        return _truncate_middle(
            json.dumps(log, ensure_ascii=False, indent=2),
            12000,
        )

    sections = []
    task_context = bundle.get("task_context", {})
    decisive_evidence = bundle.get("decisive_evidence", [])
    conflict_evidence = bundle.get("conflict_evidence", [])
    error_summary = bundle.get("error_summary", {})
    residual_context = bundle.get("residual_context", {})
    compression_metrics = bundle.get("compression_metrics", {})

    sections.append("### 1) task_context")
    sections.append(json.dumps(task_context, ensure_ascii=False, indent=2))

    sections.append("### 2) decisive_evidence")
    sections.append(json.dumps(decisive_evidence, ensure_ascii=False, indent=2))

    sections.append("### 3) conflict_evidence")
    sections.append(json.dumps(conflict_evidence, ensure_ascii=False, indent=2))

    sections.append("### 4) error_summary")
    sections.append(json.dumps(error_summary, ensure_ascii=False, indent=2))

    sections.append("### 5) residual_context")
    sections.append(json.dumps(residual_context, ensure_ascii=False, indent=2))

    sections.append("### 6) compression_metrics")
    sections.append(json.dumps(compression_metrics, ensure_ascii=False, indent=2))

    payload = "\n\n".join(sections)
    return _truncate_middle(payload, 20000)


def _render_compression_report(log_data: dict, file_path: str) -> str:
    baseline = log_data.get("baseline_metrics", {})
    metrics = log_data.get("compression_metrics", {})
    prompt_bundle = log_data.get("prompt_bundle", {})
    decisive_evidence = prompt_bundle.get("decisive_evidence", []) if isinstance(prompt_bundle, dict) else []
    conflict_evidence = prompt_bundle.get("conflict_evidence", []) if isinstance(prompt_bundle, dict) else []

    lines: list[str] = []
    lines.append("# Compression Report")
    lines.append("")
    lines.append(f"- file: `{file_path}`")
    lines.append(f"- task_id: `{log_data.get('task_id')}`")
    lines.append(f"- status: `{log_data.get('status')}`")
    lines.append("")
    lines.append("## Metrics")
    lines.append(
        f"- raw_content_chars: `{metrics.get('raw_content_chars', 0)}`"
    )
    lines.append(
        f"- compressed_content_chars: `{metrics.get('compressed_content_chars', 0)}`"
    )
    lines.append(
        f"- message_char_reduction_ratio: `{metrics.get('message_char_reduction_ratio', 0)}`"
    )
    lines.append(f"- raw_prompt_chars: `{metrics.get('raw_prompt_chars', 0)}`")
    lines.append(
        f"- compressed_prompt_chars: `{metrics.get('compressed_prompt_chars', 0)}`"
    )
    lines.append(
        f"- prompt_reduction_ratio: `{metrics.get('prompt_reduction_ratio', 0)}`"
    )
    lines.append(
        f"- raw_message_count: `{metrics.get('raw_message_count', 0)}`"
    )
    lines.append(
        f"- compressed_message_count: `{metrics.get('compressed_message_count', 0)}`"
    )
    lines.append("")
    lines.append("## Baseline Summary")
    lines.append(
        f"- think_messages: `{baseline.get('think_messages', 0)}`"
    )
    lines.append(
        f"- search_payload_messages: `{baseline.get('search_payload_messages', 0)}`"
    )
    lines.append(
        f"- scrape_server_not_found_messages: `{baseline.get('scrape_server_not_found_messages', 0)}`"
    )
    lines.append(
        f"- google_tool_result_error_messages: `{baseline.get('google_tool_result_error_messages', 0)}`"
    )
    lines.append("")
    lines.append("## Decisive Evidence (Top 5)")
    for item in decisive_evidence[:5]:
        excerpt = item.get("excerpt", "") if isinstance(item, dict) else str(item)
        lines.append(f"- {_truncate_middle(str(excerpt), 260)}")
    if not decisive_evidence:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Conflict Evidence (Top 5)")
    for item in conflict_evidence[:5]:
        excerpt = item.get("excerpt", "") if isinstance(item, dict) else str(item)
        lines.append(f"- {_truncate_middle(str(excerpt), 260)}")
    if not conflict_evidence:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)


def analysis_prompt(log:dict, answer:str = None):
    sys_prompt = '''
    你是一个智能体日志分析师，负责分析智能体的运行日志，并输出分析结果。
    你将得到一个智能体系统的日志。
    请你分析智能体运行情况，包括：
    智能体最终决策的逻辑是什么，依据了什么关键证据，指标，这些关键证据的来源是哪里？
    智能体整体执行流程的质量如何？
    如果用户提供了任务的正确答案，确认智能体预测是否正确。如果不正确，分析原因。
    智能体是否发生了以下的问题或错误：
    1.幻觉问题：纯文本幻觉 (模型生成了与现实世界知识冲突的、虚构的文本陈述) 或工具相关幻觉(智能体虚构了工具的输出，或者声称自己拥有某些实际不存在的工具能力);
    2.信息处理问题：检索质量差(检索到的信息由于内容过载或不相关，导致冗余)或工具输出误解(模型错误地理解了工具返回的数据);
    3.决策制定问题：问题识别错误（在步骤级别上误解了任务）或工具选择错误；
    4.输出生成问题：输出格式错误或者指令不合规（模型未能遵循约束条件）；
    5.工具调用问题：各种API问题，环境配置问题等导致的工具调用失败；
    6.上下文处理失败：上下文过长导致模型遗忘了之前的指令或状态;
    7.资源滥用：由于规划不当，导致重复且无意义地调用工具（例如反复读取同一个文件而没有进展）;
    8.任务管理问题：目标偏离 (智能体在执行过程中“跑题”了，被环境中的干扰信息带偏，忘记了最初的目标)或任务编排错误(在多智能体系统中，子任务的分配、协调或进度监控出现问题).

    你应该将你的分析结果输出为纯markdown格式的字符串，不要包含多余的字符，可以直接存储进.md文件。
    '''
    log_payload = _format_prompt_bundle(log)
    user_prompt = f"""
    以下是你需要分析的智能体系统日志：
    {log_payload}
    """
    if answer:
        user_prompt += f"""
    该任务的正确答案是：
    {answer}
    """
    user_prompt += "现在，请你给出你的分析报告，需要为纯md格式："
    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt}
    ]

async def analyze_log_file(file_path, client, answer=None, answers_map=None):
    """
    Analyzes a log file using an LLM and saves the report as a Markdown file.
    
    Args:
        file_path (str): Path to the JSON log file.
        client: An instance of the LLMClient.
    """
    # Process the log data
    print(f"Loading log from {file_path}")
    log_data = process_log_data(file_path)
    compression_metrics = log_data.get("compression_metrics", {})
    
    if answers_map:
        task_id = log_data.get('task_id')
        if task_id:
            # Extract digits from the beginning or until non-digit
            match = re.match(r'^[^0-9]*(\d+)', str(task_id))
            # The user requirement was: "take the part from the beginning to the end or before the first non-digit character"
            # Actually interpretation: "task_id字段中从开头到结尾或者第一个非数字字符之前的部分"
            # This usually means taking the prefix digits.
            # Example: "123_abc" -> "123"
            # Example: "123" -> "123"
            
            # Let's implement strictly: "from start ... to first non-digit"
            extracted_id = ""
            for char in str(task_id):
                if char.isdigit():
                    extracted_id += char
                else:
                    break
            
            if extracted_id and extracted_id in answers_map:
                answer = answers_map[extracted_id]
                # print(f"Matched answer for task_id {task_id} (extracted: {extracted_id})")
    
    
    # Generate the prompt
    loop = asyncio.get_running_loop()
    messages = await loop.run_in_executor(None, analysis_prompt, log_data, answer)
    
    # Get analysis from LLM
    response = await client.chat_structured(messages, response_format=MarkdownResponse)
    analysis_content = response.content
    
    # Determine output file path
    base_name = os.path.splitext(file_path)[0]
    output_path = f"{base_name}_analysis.md"
    compression_report_path = f"{base_name}_compression_report.md"
    
    # Save the analysis report
    save_string_to_md(analysis_content, output_path)
    print(f"Analysis saved to: {output_path}")
    compression_report_content = _render_compression_report(log_data, file_path)
    save_string_to_md(compression_report_content, compression_report_path)
    print(f"Compression report saved to: {compression_report_path}")
    return {
        "task_id": log_data.get("task_id"),
        "output_path": output_path,
        "compression_report_path": compression_report_path,
        "compression_metrics": compression_metrics if isinstance(compression_metrics, dict) else {},
    }

if __name__ == "__main__":
    from llm_client import LLMClient
    
    async def main():
        log_path = "test/long_text_C3FBBFA9-1F78-40CE-A535-E3B662A5DC24.json"
        
        # Check if the file exists before running
        if not os.path.exists(log_path):
            print(f"Test file not found: {log_path}")
            return

        async with LLMClient("openai/gpt-5.2") as client:
            await analyze_log_file(log_path, client)

    asyncio.run(main())