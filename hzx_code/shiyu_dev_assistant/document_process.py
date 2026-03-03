"""
文档处理模块 - 用于处理和组织JSONL文件
"""

import os
import shutil
from pathlib import Path
from typing import Optional


def process_folder(folder_a: str) -> dict:
    """
    扫描文件夹A，处理其下所有直接子文件夹中的JSONL文件。
    
    对于每个子文件夹Bi:
    1. 找到第一个文件名中不包含'_call'的jsonl文件，将其重命名为'expert_'前缀
    2. 创建'factors'子文件夹
    3. 将所有文件名中包含'_call'的jsonl文件移动到'factors'文件夹
    
    Args:
        folder_a: 要扫描的根文件夹路径
        
    Returns:
        dict: 处理结果统计，包含处理的文件夹数、重命名的文件数、移动的文件数
    """
    folder_a_path = Path(folder_a)
    
    if not folder_a_path.exists():
        raise FileNotFoundError(f"文件夹不存在: {folder_a}")
    
    if not folder_a_path.is_dir():
        raise NotADirectoryError(f"路径不是文件夹: {folder_a}")
    
    result = {
        "processed_folders": 0,
        "renamed_files": 0,
        "moved_files": 0,
        "details": []
    }
    
    # 遍历A下的所有直接子文件夹
    for item in folder_a_path.iterdir():
        if not item.is_dir():
            continue
            
        folder_bi = item
        folder_detail = {
            "folder": str(folder_bi),
            "renamed_file": None,
            "moved_files": []
        }
        
        # 获取Bi文件夹下所有的jsonl文件
        jsonl_files = list(folder_bi.glob("*.jsonl"))
        
        # 找到第一个文件名中不包含'_call'的jsonl文件并重命名
        renamed = False
        for jsonl_file in jsonl_files:
            if "_call" not in jsonl_file.stem:
                new_name = f"expert_{jsonl_file.name}"
                new_path = jsonl_file.parent / new_name
                
                # 避免重复重命名已经有export_前缀的文件
                if not jsonl_file.name.startswith("expert_"):
                    jsonl_file.rename(new_path)
                    folder_detail["renamed_file"] = {
                        "original": str(jsonl_file),
                        "new": str(new_path)
                    }
                    result["renamed_files"] += 1
                    renamed = True
                break  # 只处理第一个符合条件的文件
        
        # 创建factors文件夹
        factors_folder = folder_bi / "factors"
        factors_folder.mkdir(exist_ok=True)
        
        # 重新获取jsonl文件列表（因为可能有文件已被重命名）
        jsonl_files = list(folder_bi.glob("*.jsonl"))
        
        # 将所有包含'_call'的jsonl文件移动到factors文件夹
        for jsonl_file in jsonl_files:
            if "_call" in jsonl_file.stem:
                dest_path = factors_folder / jsonl_file.name
                shutil.move(str(jsonl_file), str(dest_path))
                folder_detail["moved_files"].append({
                    "original": str(jsonl_file),
                    "destination": str(dest_path)
                })
                result["moved_files"] += 1
        
        result["processed_folders"] += 1
        result["details"].append(folder_detail)
    
    return result


def main():
    """主函数，用于测试"""
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python document_process.py <文件夹路径>")
        sys.exit(1)
    
    folder_path = sys.argv[1]
    
    try:
        result = process_folder(folder_path)
        print(f"处理完成!")
        print(f"处理的文件夹数: {result['processed_folders']}")
        print(f"重命名的文件数: {result['renamed_files']}")
        print(f"移动的文件数: {result['moved_files']}")
        
        if result['details']:
            print("\n详细信息:")
            for detail in result['details']:
                print(f"\n文件夹: {detail['folder']}")
                if detail['renamed_file']:
                    print(f"  重命名: {detail['renamed_file']['original']} -> {detail['renamed_file']['new']}")
                if detail['moved_files']:
                    print(f"  移动的文件:")
                    for moved in detail['moved_files']:
                        print(f"    {moved['original']} -> {moved['destination']}")
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
