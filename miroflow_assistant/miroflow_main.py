
import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path if not present
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from miroflow_assistant.log_analysis import analyze_log_file

async def run_single_analysis(file_path, client):
    """Runs analysis for a single file."""
    try:
        await analyze_log_file(file_path, client)
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")

async def run_batch_analysis(folder_path, concurrency, client):
    """Runs batch analysis for a directory."""
    print(f"Scanning directory: {folder_path}")
    tasks = []
    sem = asyncio.Semaphore(concurrency)

    # Scan for json files in the current directory only
    for file in os.listdir(folder_path):
        if file.endswith(".json"):
            log_path = os.path.join(folder_path, file)
            
            # Check if analysis file exists
            base_name = os.path.splitext(log_path)[0]
            analysis_path = f"{base_name}_analysis.md"
            
            if os.path.exists(analysis_path):
                print(f"Skipping {file} (Analysis exists)")
                continue
            
            tasks.append(process_with_semaphore(sem, log_path, client))

    if not tasks:
        print("No new log files to process.")
        return

    print(f"Found {len(tasks)} files to analyze with concurrency {concurrency}...")
    await asyncio.gather(*tasks)

async def process_with_semaphore(sem, file_path, client):
    """Wrapper to respect concurrency limit."""
    async with sem:
        print(f"Starting analysis for: {file_path}")
        await run_single_analysis(file_path, client)
        print(f"Finished analysis for: {file_path}")

async def main():
    parser = argparse.ArgumentParser(description="Log Analysis Tool")
    parser.add_argument("path", help="Path to a json log file or a directory containing logs")
    parser.add_argument("--parallel", action="store_true", help="Enable parallel processing for directories")
    parser.add_argument("--concurrency", type=int, default=5, help="Max number of concurrent tasks")
    parser.add_argument("--model", type=str, default="openai/gpt-5.2", help="LLM model to use")
    
    args = parser.parse_args()
    target_path = args.path
    
    if not os.path.exists(target_path):
        print(f"Error: Path not found: {target_path}")
        return

    from llm_client import LLMClient
    async with LLMClient(model_name=args.model) as client:
        if os.path.isdir(target_path):
            if args.parallel:
                await run_batch_analysis(target_path, args.concurrency, client)
            else:
                print("Directory provided but --parallel flag not set. Please use --parallel to process directories.")
        else:
            # Single file
            await run_single_analysis(target_path, client)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
