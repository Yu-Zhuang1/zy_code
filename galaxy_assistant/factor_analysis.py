import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.file_utils import read_jsonl
from schema import MarkdownResponse
# Assuming LLMClient is available from the root context or imported appropriately
# If running as a module, might need relative imports or python path setup.
# Using string forward reference for type hint to avoid circular imports if strictly needed,
# but here specific import is likely fine if run from root.
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from llm_client import LLMClient

def factor_analysis_prompt(path: str, use_alternative_prompt: bool = False) -> list[dict]:
    """
    Build the prompt messages for factor log analysis.
    
    Args:
        path: Path to the factor log file (jsonl).
        use_alternative_prompt: Whether to use alternative prompt templates.
        
    Returns:
        List of message dicts for the LLM.
    """
    log = read_jsonl(path)
    
    if use_alternative_prompt:
        # shiyu_dev框架提示词
        sys_prompt = """
        你是一个日志分析专家。你现在正在对一个执行预测任务的多智能体系统的部分日志执行分析工作。
        这个多智能体系统由一个主智能体负责统筹调度和任务分解，调用子智能体对子任务进行分析。
        你的任务是分析其中的一个子智能体的日志。
        你需要分析子智能体找到了哪些关键指标和数值，分析子智能体做出决策的依据是什么。
        你还需要分析子智能体的工具调用质量和效果，是否发生了错误。
        你还需要分析子智能体的整个工作流程，检查是否合理。
        你应该将你的分析结果输出为纯markdown格式的字符串，不要包含多余的字符，可以直接存储进.md文件。
        """
        
        user_prompt = f"""
        子智能体日志：
        {log}
        请给出分析报告（纯md格式）：
        """
    else:
        # galaxy框架提示词
        sys_prompt = """
        你是一个日志分析专家。你现在正在对一个执行预测任务的多智能体系统的部分日志执行分析工作。
        这个多智能体系统由一个专家智能体调用多个子智能体进行分析，最后子智能体的结果交由专家智能体进行聚合。
        你的任务是分析其中的一个子智能体的日志。
        你需要分析子智能体找到了哪些关键指标和数值，分析子智能体做出决策的依据是什么。
        你还需要分析子智能体的工具调用质量和效果，是否发生了错误。
        你还需要分析子智能体的整个工作流程，检查是否合理。
        你应该将你的分析结果输出为纯markdown格式的字符串，不要包含多余的字符，可以直接存储进.md文件。
        """
        
        user_prompt = f"""
        以下是你需要分析的子智能体的日志：
        {log}
        现在，请你给出你的分析报告，需要为纯md格式：
        """
    
    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt}
    ]

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
    messages = await loop.run_in_executor(None, lambda: factor_analysis_prompt(path, use_alternative_prompt))
    
    # Using chat_structured to enforce MarkdownResponse schema
    response = await client.chat_structured(messages, response_format=MarkdownResponse)
    
    return response.content

