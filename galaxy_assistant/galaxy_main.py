import sys
import asyncio
import argparse
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from llm_client import LLMClient
from galaxy_assistant.expert_analysis import run_full_analysis
from galaxy_assistant.answer_process import process_gold_answers


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Galaxy Assistant - Log Analysis Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "-b", "--batch",
        action="store_true",
        help="Enable batch analysis mode (analyze all subfolders)"
    )
    parser.add_argument(
        "-a", "--answers",
        type=str,
        default=None,
        help="Path to answers JSON file (optional)"
    )
    parser.add_argument(
        "-f", "--folder",
        type=str,
        required=True,
        help="Log folder path (required)"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default = "openai/gpt-5.2",
        help="Model name (e.g., openai/gpt-4o)"
    )
    parser.add_argument(
        "-fc", "--factor-concurrency",
        type=int,
        default=10,
        help="Concurrency for factor analysis within a single task (default: 10)"
    )
    parser.add_argument(
        "-tc", "--task-concurrency",
        type=int,
        default=5,
        help="Concurrency for analyzing multiple tasks in batch mode (default: 5)"
    )
    
    return parser.parse_args()


async def run_batch_analysis(
    client: LLMClient,
    folder_path: str,
    answers: dict,
    factor_concurrency: int,
    task_concurrency: int
):
    """
    Run analysis on all subfolders in the given folder path.
    
    Args:
        client: The LLMClient instance.
        folder_path: Path to the folder containing task subfolders.
        answers: Dictionary mapping task id to ground_truth.
        factor_concurrency: Concurrency limit for factor analysis.
        task_concurrency: Concurrency limit for batch task analysis.
    """
    folder = Path(folder_path)
    subfolders = [f for f in folder.iterdir() if f.is_dir()]
    
    if not subfolders:
        print(f"No subfolders found in {folder_path}")
        return
    
    print(f"Found {len(subfolders)} task folders. Starting batch analysis...")
    
    # Create semaphore to limit concurrent task analysis
    sem = asyncio.Semaphore(task_concurrency)
    
    async def analyze_task(task_folder: Path):
        async with sem:
            task_id = task_folder.name
            answer = answers.get(task_id) if answers else None
            print(f"Starting analysis for task: {task_id}")
            await run_full_analysis(
                client,
                str(task_folder),
                answer=answer,
                concurrency_limit=factor_concurrency
            )
            print(f"Completed analysis for task: {task_id}")
    
    tasks = [analyze_task(f) for f in subfolders]
    await asyncio.gather(*tasks)
    
    print(f"\nBatch analysis complete. Analyzed {len(subfolders)} tasks.")


async def main():
    args = parse_args()
    
    # Load answers if provided
    answers = {}
    if args.answers:
        print(f"Loading answers from: {args.answers}")
        answer_list = process_gold_answers(args.answers)
        answers = {item['id']: item['ground_truth'] for item in answer_list}
        print(f"Loaded {len(answers)} answers.")
    
    # Create LLM client
    async with LLMClient(args.model) as client:
        if args.batch:
            # Batch mode: analyze all subfolders
            await run_batch_analysis(
                client,
                args.folder,
                answers,
                args.factor_concurrency,
                args.task_concurrency
            )
        else:
            # Single mode: analyze the specified folder
            folder = Path(args.folder)
            task_id = folder.name
            answer = answers.get(task_id) if answers else None
            print(f"Starting single task analysis: {args.folder}")
            await run_full_analysis(
                client,
                args.folder,
                answer=answer,
                concurrency_limit=args.factor_concurrency
            )
            print("Single task analysis complete.")


if __name__ == "__main__":
    asyncio.run(main())
