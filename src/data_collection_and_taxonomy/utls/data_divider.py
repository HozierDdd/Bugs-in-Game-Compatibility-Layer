#!/usr/bin/env python3
"""
JSON File Divider

This script divides large JSON files containing GitHub issues into smaller chunks.
Each output file contains at most a specified number of issues.
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Optional
try:
    from utls.utls import find_root_directory
except ModuleNotFoundError:
    import importlib.util, pathlib
    _spec = importlib.util.spec_from_file_location(
        "utls", pathlib.Path(__file__).parent / "utls.py"
    )
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    find_root_directory = _mod.find_root_directory



def divide_json_file(
    input_file: str,
    output_dir: str = "data/issue_origin",
    issues_per_file: int = 10,
    output_prefix: Optional[str] = None
) -> List[str]:
    """
    Divide a large JSON file containing issues into smaller files.
    
    Args:
        input_file: Path to the input JSON file
        output_dir: Directory to save divided files (default: data/issue_origin)
        issues_per_file: Maximum number of issues per output file (default: 10)
        output_prefix: Prefix for output filenames (default: based on input filename)
    
    Returns:
        List of paths to created output files
    """
    # Convert to Path objects
    input_path = Path(input_file)
    output_path = Path(output_dir)
    
    # Validate input file exists
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")
    
    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Load the original JSON file
    print(f"Loading JSON file: {input_file}...")
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Extract metadata and issues (support both list and dict formats)
    if isinstance(data, list):
        metadata = {}
        issues = data
    else:
        metadata = data.get("metadata", {})
        issues = data.get("issues", [])
    
    total_issues = len(issues)
    print(f"Total issues found: {total_issues}")
    
    if total_issues == 0:
        print("No issues to divide.")
        return []
    
    # Calculate number of files needed
    num_files = math.ceil(total_issues / issues_per_file)
    print(f"Will create {num_files} files with up to {issues_per_file} issues each.")
    
    # Generate output prefix if not provided
    if output_prefix is None:
        # Use input filename without extension as prefix
        output_prefix = input_path.stem
    
    # Divide issues into chunks and save
    output_files = []
    for i in range(num_files):
        start_idx = i * issues_per_file
        end_idx = min(start_idx + issues_per_file, total_issues)
        chunk_issues = issues[start_idx:end_idx]
        
        # Create output filename
        file_num = i + 1
        output_filename = f"{output_prefix}_part{file_num:03d}.json"
        output_file_path = output_path / output_filename
        
        # Create output data structure
        output_data = chunk_issues
        
        # Save chunk to file
        print(f"Writing part {file_num}/{num_files} ({len(chunk_issues)} issues) to {output_filename}...")
        with open(output_file_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        output_files.append(str(output_file_path))
        file_size_mb = output_file_path.stat().st_size / 1024 / 1024
        print(f"  ✓ Saved {file_size_mb:.2f} MB")
    
    print(f"\n✓ Successfully divided file into {num_files} parts!")
    print(f"Output directory: {output_path}")
    
    return output_files


def main():
    root_dir = find_root_directory()

    input_file = f"{root_dir}/data/protondb/reports_piiremoved.json"
    output_dir = f"{root_dir}/data/protondb/report_chunks"
    issues_per_file = 10
    output_prefix = None

    output_files = divide_json_file(
        input_file=input_file,
        output_dir=output_dir,
        issues_per_file=issues_per_file,
        output_prefix=output_prefix
    )
    print(f"\nCreated {len(output_files)} files successfully!")


if __name__ == "__main__":
    main()
