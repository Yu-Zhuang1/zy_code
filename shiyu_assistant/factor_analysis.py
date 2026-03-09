import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.file_utils import read_jsonl
from schema import MarkdownResponse
from shiyu_assistant.log_compression import compress_log_messages, format_compressed_payload
# Assuming LLMClient is available from the root context or imported appropriately
# If running as a module, might need relative imports or python path setup.
# Using string forward reference for type hint to avoid circular imports if strictly needed,
# but here specific import is likely fine if run from root.
from typing import Any, TYPE_CHECKING
if TYPE_CHECKING:
    from llm_client import LLMClient


def build_factor_prompt_payload(path: str, use_alternative_prompt: bool = False) -> dict[str, Any]:
    """
    Build prompt messages and compression artifacts for factor log analysis.
    
    Args:
        path: Path to the factor log file (jsonl).
        use_alternative_prompt: Whether to use alternative prompt templates.
        
    Returns:
        Dict containing prompt messages and compressed payload artifacts.
    """
    log = read_jsonl(path)
    compressed_log = compress_log_messages(log, source_path=path)
    compressed_log_text = format_compressed_payload(
        compressed_log,
        max_chars=8800,
        profile="factor",
    )
    metrics = compressed_log.get("compression_metrics", {})
    ratio = metrics.get("reduction_ratio", 0.0)
    compression_header = (
        f"raw_chars={metrics.get('raw_chars', 'n/a')}, "
        f"compressed_chars={metrics.get('compressed_chars', 'n/a')}, "
        f"reduction_ratio={ratio}"
    )
    
    if use_alternative_prompt:
        # shiyu_dev框架提示词
        sys_prompt = """
        你是一个日志分析专家。你现在正在对一个执行预测任务的多智能体系统的部分日志执行分析工作。
        这个多智能体系统由一个主智能体负责统筹调度和任务分解，调用子智能体对子任务进行分析。
        你的任务是分析其中的一个子智能体的日志。

        请将你的分析过程明确分为以下两个阶段：
        1. 流程梳理：分析子智能体的整个工作流程，它找到了哪些关键指标和数值，以及它做出决策的依据是什么。检查流程是否合理。
        2. 错误检查：详细检查子智能体的工具调用质量和效果，明确指出是否发生了任何错误、遗漏或不合理的行为。

        你应该将你的分析结果输出为纯markdown格式的字符串，不要包含多余的字符，可以直接存储进.md文件。

        【极其重要】：你具备联网搜索能力（search_web工具），并且我设定了允许你连续多次调用它！当日志中出现多个你不确定的：时间/休市日要求、API接口字段、特定报错码、业务公式或事件细节时，你**必须**针对每一个疑点分别发起多次 search_web 调用，直到所有关键事实都被互联网数据交叉验证过为止。由于搜索次数有限，请务必按照重要性顺序，优先搜索最核心、最可能导致严重误判的疑点。不要靠猜测下结论，充分利用你的搜索权限！
        如果你没有经过联网搜索和交叉验证，请说明。
        """
        
        user_prompt = f"""
        子智能体日志（结构化压缩版）：
        {compression_header}
        {compressed_log_text}
        请给出分析报告（纯md格式）：
        """
    else:
        # galaxy框架提示词
        sys_prompt = """
        你是一个日志分析专家。你现在正在对一个执行预测任务的多智能体系统的部分日志执行分析工作。
        这个多智能体系统由一个专家智能体调用多个子智能体进行分析，最后子智能体的结果交由专家智能体进行聚合。
        你的任务是分析其中的一个子智能体的日志。

        请将你的分析过程明确分为以下两个阶段：
        1. 流程梳理：分析子智能体的整个工作流程，它找到了哪些关键指标和数值，以及它做出决策的依据是什么。检查流程是否合理。
        2. 错误检查：详细检查子智能体的工具调用质量和效果，明确指出是否发生了任何错误、遗漏或不合理的行为。

        你应该将你的分析结果输出为纯markdown格式的字符串，不要包含多余的字符，可以直接存储进.md文件。

        【极其重要】：你具备联网搜索能力（search_web工具），并且我设定了允许你连续多次调用它！当日志中出现多个你不确定的：时间/休市日要求、API接口字段、特定报错码、业务公式或事件细节时，你**必须**针对每一个疑点分别发起多次 search_web 调用，直到所有关键事实都被互联网数据交叉验证过为止。由于搜索次数有限，请务必按照重要性顺序，优先搜索最核心、最可能导致严重误判的疑点。不要靠猜测下结论，充分利用你的搜索权限！
        如果你没有经过联网搜索和交叉验证，请说明。
        """
        
        user_prompt = f"""
        以下是你需要分析的子智能体日志（结构化压缩版）：
        {compression_header}
        {compressed_log_text}
        现在，请你给出你的分析报告，需要为纯md格式：
        """
    
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt}
    ]

    return {
        "messages": messages,
        "compressed_log": compressed_log,
        "compressed_log_text": compressed_log_text,
        "compression_header": compression_header,
    }


def factor_analysis_prompt(path: str, use_alternative_prompt: bool = False) -> list[dict]:
    payload = build_factor_prompt_payload(path, use_alternative_prompt)
    return payload["messages"]

async def analyze_factor_log(client: 'LLMClient', path: str, use_alternative_prompt: bool = False) -> str:
    """
    Asynchronously analyze a factor log using the LLM client.
    
    Args:
        client: The LLMClient instance (async).
        path: Path to the log file (jsonl).
        use_alternative_prompt: Whether to use alternative prompt templates.
        
    Returns:
        str: The analysis result in Markdown format.
    """
    loop = asyncio.get_running_loop()
    payload = await loop.run_in_executor(None, lambda: build_factor_prompt_payload(path, use_alternative_prompt))
    messages = payload["messages"]
    
    # Using chat_structured to enforce MarkdownResponse schema
    response = await client.chat_structured(messages, response_format=MarkdownResponse, use_web_search=True)
    
    return response.content

