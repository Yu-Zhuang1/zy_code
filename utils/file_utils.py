import json
import os
from typing import List, Dict, Union

def read_jsonl(file_path: str) -> List[Dict]:
    """
    Reads a JSONL file and returns a list of dictionaries.
    
    Args:
        file_path (str): The path to the JSONL file.
        
    Returns:
        List[Dict]: A list of dictionaries parsed from the JSONL file.
    """
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data

def read_json(file_path: str) -> Dict:
    """
    Reads a JSON file and returns a dictionary.
    
    Args:
        file_path (str): The path to the JSON file.
        
    Returns:
        Dict: The dictionary parsed from the JSON file.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_string_to_md(content: str, file_path: str) -> None:
    """
    Writes a string to a Markdown file.
    
    Args:
        content (str): The string content to write.
        file_path (str): The output file path.
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def read_md_to_string(file_path: str) -> str:
    """
    Reads a Markdown file and returns its content as a string.
    
    Args:
        file_path (str): The path to the Markdown file.
        
    Returns:
        str: The content of the file.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()
