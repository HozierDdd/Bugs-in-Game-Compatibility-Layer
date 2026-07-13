"""
JSON read/write utilities.
Consistently uses indent=2, UTF-8 encoding, and ensure_ascii=False.
"""

import json
from pathlib import Path
from typing import Any


def load_json(path: Path | str) -> Any:
    """Load JSON from a file, handling encoding automatically."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Any, path: Path | str, *, indent: int = 2) -> None:
    """Serialize an object to a JSON file, ensuring UTF-8 and indented formatting."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


