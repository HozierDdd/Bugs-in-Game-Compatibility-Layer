import os
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import math


def find_root_directory(
        start_path: Optional[str] = None,
        marker_files: Optional[List[str]] = None
) -> Path:
    """
    Find the project root directory by looking for marker files or directories.

    Args:
        start_path: Starting directory to search from (default: current file's directory)
        marker_files: List of marker files/directories to look for (default: ['.git', 'README.md', 'LICENSE'])

    Returns:
        Path to the root directory

    Raises:
        FileNotFoundError: If root directory cannot be found
    """
    if marker_files is None:
        marker_files = ['.git', 'README.md', 'LICENSE', 'requirements.txt']

    # Start from current file's directory or specified path
    if start_path is None:
        # Get the directory where this script is located
        current_file = Path(__file__).resolve()
        current_dir = current_file.parent
    else:
        current_dir = Path(start_path).resolve()

    # Traverse up the directory tree
    path = current_dir
    while path != path.parent:  # Stop at filesystem root
        # Check if any marker file/directory exists
        for marker in marker_files:
            marker_path = path / marker
            if marker_path.exists():
                return path
        path = path.parent

    # If no marker found, return the starting directory as fallback
    return current_dir


def chunk_loader(
        chunks_path: Optional[str] = None,
        combine_issues: bool = True,
        sort_by_part: bool = True
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Load all data from the chunks folder.

    Args:
        chunks_path: Path to the chunks folder (default: data/issue_origin/chunks from project root)
        combine_issues: If True, combine all issues into a single list with metadata.
                       If False, return list of chunk dictionaries with their metadata.
        sort_by_part: If True, sort chunks by part number before processing

    Returns:
        If combine_issues=True: Dictionary with keys:
            - 'metadata': Combined metadata from all chunks
            - 'issues': List of all issues from all chunks
        If combine_issues=False: List of chunk dictionaries, each with 'metadata' and 'issues'

    Raises:
        FileNotFoundError: If chunks folder doesn't exist
        ValueError: If no JSON files found in chunks folder
    """
    # Determine chunks path
    root_dir = find_root_directory()
    if chunks_path is None:
        chunks_path = root_dir / "data" / "issue_origin" / "chunks"
    else:
        chunks_path = f"{root_dir}/{chunks_path}"
        chunks_path = Path(chunks_path)

    # Validate chunks path exists
    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunks folder not found: {chunks_path}")

    if not chunks_path.is_dir():
        raise ValueError(f"Path is not a directory: {chunks_path}")

    # Find all JSON files in chunks folder
    json_files = list(chunks_path.glob("*.json"))

    if not json_files:
        raise ValueError(f"No JSON files found in chunks folder: {chunks_path}")

    # Sort files by part number if requested
    if sort_by_part:
        def extract_part_number(f: Path) -> int:
            """Extract part number from filename for proper numeric sorting."""
            match = re.search(r'part(\d+)\.json', f.name)
            return int(match.group(1)) if match else 0
        
        json_files = sorted(json_files, key=extract_part_number)
    else:
        # Fallback to name-based sorting
        json_files = sorted(json_files, key=lambda f: f.name)

    # Load all chunks and track failures
    chunks = []
    failed_files = []
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                chunk_data = json.load(f)
                chunks.append(chunk_data)
        except json.JSONDecodeError as e:
            failed_files.append({
                'file': str(json_file.name),
                'error': f"JSON decode error: {str(e)}",
                'error_type': 'JSONDecodeError'
            })
            print(f"Warning: Failed to parse {json_file.name}: {e}")
            continue
        except Exception as e:
            failed_files.append({
                'file': str(json_file.name),
                'error': str(e),
                'error_type': type(e).__name__
            })
            print(f"Warning: Failed to load {json_file.name}: {e}")
            continue

    if not chunks:
        raise ValueError(f"Failed to load any valid JSON chunks. {len(failed_files)} files failed to load.")

    # Warn if some files failed
    if failed_files:
        print(f"\nWarning: {len(failed_files)} file(s) failed to load out of {len(json_files)} total files.")
        print(f"Failed files: {[f['file'] for f in failed_files]}")

    # Return based on combine_issues flag
    if combine_issues:
        # Combine all issues into a single list
        all_issues = []
        combined_metadata = {
            'total_chunks_loaded': len(chunks),
            'total_files_found': len(json_files),
            'total_files_failed': len(failed_files),
            'failed_files': failed_files,
            'total_issues_loaded': 0,
            'chunks_info': []
        }

        # Preserve first chunk's metadata as base
        if chunks:
            try:
                first_metadata = chunks[0].get('metadata', {})
                combined_metadata.update({
                    'repository': first_metadata.get('repository'),
                    'collection_date': first_metadata.get('collection_date'),
                    'api_url': first_metadata.get('api_url'),
                    'total_issues': first_metadata.get('total_issues'),
                    'total_parts': first_metadata.get('total_parts')
                })
            except Exception as e:
                print(f"INFO: first chunk has no metadata.")

        # Combine issues and track chunk info
        for chunk in chunks:
            try:
                chunk_metadata = chunk.get('metadata', {})
                combined_metadata['chunks_info'].append({
                    'part_number': chunk_metadata.get('part_number'),
                    'issues_in_part': chunk_metadata.get('issues_in_part'),
                    'issue_range': chunk_metadata.get('issue_range')
                })
                combined_metadata['total_issues_loaded'] = len(all_issues)
                issues = chunk.get('issues', [])
                all_issues.extend(issues)
            except Exception as e:
                print(f"Warning: Seems don't need to combine issues, change the value to false: {e}")
                return chunks
        return {
            'metadata': combined_metadata,
            'issues': all_issues
        }



    else:
        # Return list of chunks as-is
        return chunks


def chunk_saver(
        data: List[Dict[str, Any]],
        save_location: Union[str, Path],
        chunk_size: int = 100,
        filename_prefix: str = "chunk",
        start_index: int = 1
) -> List[Path]:
    root_dir = find_root_directory()
    if not data:
        raise ValueError("Data list cannot be empty")
    
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")

    # Convert save_location to Path and ensure it exists
    save_path = root_dir / save_location
    if not save_path.exists():
        save_path.mkdir(parents=True, exist_ok=True)
    
    if not save_path.is_dir():
        raise ValueError(f"save_location must be a directory: {save_path}")

    saved_files = []
    total_chunks = (len(data) + chunk_size - 1) // chunk_size  # Ceiling division

    # Split data into chunks and save each chunk
    for chunk_idx in range(total_chunks):
        start = chunk_idx * chunk_size
        end = min(start + chunk_size, len(data))
        chunk_data = data[start:end]

        # Generate filename with zero-padded index
        file_index = start_index + chunk_idx
        filename = f"{filename_prefix}_{file_index:04d}.json"
        file_path = save_path / filename

        # Write JSON file
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(chunk_data, f, ensure_ascii=False, indent=2)
            saved_files.append(file_path)
        except Exception as e:
            raise OSError(f"Failed to write file {file_path}: {e}")

    return saved_files

def chunk_divider(
        data: Dict[str, Any],
        issues_per_file: int = 50
):
    issues = data.get("issues", [])

    total_issues = len(issues)
    print(f"Total issues found: {total_issues}")

    if total_issues == 0:
        print("No issues to divide.")
        return []

    # Calculate number of files needed
    num_files = math.ceil(total_issues / issues_per_file)
    print(f"Will create {num_files} files with up to {issues_per_file} issues each.")


    # Divide issues into chunks and save
    output_files = []
    for i in range(num_files):
        start_idx = i * issues_per_file
        end_idx = min(start_idx + issues_per_file, total_issues)
        chunk_issues = issues[start_idx:end_idx]

        # Create output filename
        file_num = i + 1
        output_filename = f"part{file_num:03d}.json"
        output_file_path = "data/issue_filtered/" + output_filename

        # Create output data structure
        output_data = chunk_issues

        print(f"Writing part {file_num}/{num_files} ({len(chunk_issues)} issues) to {output_filename}...")
        with open(output_file_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        output_files.append(str(output_file_path))

    print(f"\n✓ Successfully divided file into {num_files} parts!")


if __name__ == "__main__":
    # root_dir = find_root_directory()
    # print(f"Project root directory: {root_dir}")

    # Example usage of chunk_loader
    try:
        data = chunk_loader()
        metadata = data['metadata']
        print(f"\nLoaded {metadata['total_issues_loaded']} issues from {metadata['total_chunks_loaded']}/{metadata['total_files_found']} chunks")
        if metadata['total_files_failed'] > 0:
            print(f"⚠️  Warning: {metadata['total_files_failed']} file(s) failed to load:")
            for failed in metadata['failed_files']:
                print(f"   - {failed['file']}: {failed['error_type']}")
    except Exception as e:
        print(f"Error loading chunks: {e}")

    # root_dir = find_root_directory()
    # chunks_path = root_dir / "data" / "issue_filtered" / "issue_close_completed"
    # loader = chunk_loader(chunks_path, True, True)
    #
