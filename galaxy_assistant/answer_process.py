import json
import os
from typing import List, Dict, Any

def process_gold_answers(file_path: str) -> List[Dict[str, Any]]:
    """
    Read a JSON file containing a list of dictionaries and extract 'id' and 'ground_truth'.
    
    Args:
        file_path (str): The path to the JSON file.
        
    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each containing 'id' and 'ground_truth'.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = []
    for item in data:
        if 'id' in item and 'ground_truth' in item:
            results.append({
                "id": item['id'],
                "ground_truth": item['ground_truth']
            })
    return results

if __name__ == "__main__":
    # Example usage (commented out as specific file path might not match)
    file_path = r"data\2026-02-04__gold.json"
    if os.path.exists(file_path):
        answers = process_gold_answers(file_path)
        print(f"Extracted {len(answers)} answers.")
        if answers:
            print(f"First answer: {answers[0]}")
    #pass
