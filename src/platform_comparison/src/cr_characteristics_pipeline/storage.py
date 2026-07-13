"""Small JSON/JSONL helpers for the CR characteristics pipeline."""

import json
from pathlib import Path
from typing import Any, Iterable, Iterator


def read_jsonl(path: Path | str) -> Iterator[dict]:
    path = Path(path)
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(records: Iterable[dict], path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False))
            f.write("\n")


def append_jsonl(record: dict, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False))
        f.write("\n")


def load_jsonl_by_record_id(path: Path | str) -> dict[str, dict]:
    return {
        str(item["record_id"]): item
        for item in read_jsonl(path)
        if item.get("record_id") is not None
    }


def load_jsonl_record_ids(path: Path | str) -> set[str]:
    return set(load_jsonl_by_record_id(path))


def save_failed_record(record: dict[str, Any], path: Path | str) -> None:
    append_jsonl(record, path)

