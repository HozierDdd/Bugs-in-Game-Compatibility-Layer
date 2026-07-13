"""Map symptom tags onto the observed-fix labeled data.

Data sources (artifact layout):
- observed_fix:  ../../labeled_dataset/fix_labels/cr_discussion_annotated_chunk_*.json
- symptom_tags:  ../../labeled_dataset/symptom_labels/collaborative_annotation/refined_tags/part_*.json

Output:
- ../../labeled_dataset/symptom_fix_joined/  — 33 chunks; each observed-fix CR
  gains a `symptom_tags` field (taken from the same CR's `tags` in refined_tags).

Running this script regenerates the joined dataset from its two inputs, which
also serves as a consistency check of the released data.
"""

import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATASET_ROOT = SCRIPT_DIR.parent.parent / "labeled_dataset"
OBSERVED_FIX_DIR = DATASET_ROOT / "fix_labels"
REFINED_TAGS_DIR = DATASET_ROOT / "symptom_labels" / "collaborative_annotation" / "refined_tags"
OUTPUT_DIR = DATASET_ROOT / "symptom_fix_joined"


def _chunk_index(path: Path) -> int:
    """Extract the numeric index from a file name for sorting (chunk_0 / part_1 ...)."""
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else -1


def _build_symptom_lookup() -> dict:
    """Read all refined_tags and build CR -> symptom tags lookup tables.

    Prefer the compatibility_report id as the key; also index by issue_number
    as a fallback key.
    """
    by_id = {}
    by_issue = {}
    for part_path in REFINED_TAGS_DIR.glob("part_*.json"):
        with part_path.open(encoding="utf-8") as f:
            records = json.load(f)
        for record in records:
            tags = record.get("tags", [])
            cr_id = record.get("id")
            issue_number = record.get("issue_number")
            if cr_id is not None:
                by_id[cr_id] = tags
            if issue_number is not None:
                by_issue[issue_number] = tags
    return {"by_id": by_id, "by_issue": by_issue}


def map_symptom_tags_to_fix() -> dict:
    """Map symptom tags onto the observed-fix CRs, producing 33 new chunks.

    Returns a statistics dict with matched/unmatched counts etc.
    """
    lookup = _build_symptom_lookup()
    by_id = lookup["by_id"]
    by_issue = lookup["by_issue"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    chunk_paths = sorted(
        OBSERVED_FIX_DIR.glob("cr_discussion_annotated_chunk_*.json"),
        key=_chunk_index,
    )

    stats = {
        "total_crs": 0,
        "matched": 0,
        "unmatched": 0,
        "chunks_written": 0,
        "unmatched_details": [],
    }

    for chunk_path in chunk_paths:
        with chunk_path.open(encoding="utf-8") as f:
            crs = json.load(f)

        for cr in crs:
            stats["total_crs"] += 1
            cr_id = cr.get("compatibility_report_id")
            issue_number = cr.get("issue_number")

            tags = None
            if cr_id is not None and cr_id in by_id:
                tags = by_id[cr_id]
            elif issue_number is not None and issue_number in by_issue:
                tags = by_issue[issue_number]

            if tags is not None:
                cr["symptom_tags"] = tags
                stats["matched"] += 1
            else:
                cr["symptom_tags"] = []
                stats["unmatched"] += 1
                stats["unmatched_details"].append(
                    {
                        "chunk": chunk_path.name,
                        "issue_number": issue_number,
                        "compatibility_report_id": cr_id,
                    }
                )

        output_path = OUTPUT_DIR / chunk_path.name
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(crs, f, ensure_ascii=False, indent=2)
        stats["chunks_written"] += 1

    return stats


if __name__ == "__main__":
    result = map_symptom_tags_to_fix()
    print(f"total CRs:       {result['total_crs']}")
    print(f"matched:         {result['matched']}")
    print(f"unmatched:       {result['unmatched']}")
    print(f"chunks written:  {result['chunks_written']}")
    print(f"output dir:      {OUTPUT_DIR}")
    if result["unmatched_details"]:
        print("\nunmatched CRs:")
        for item in result["unmatched_details"]:
            print(
                f"  - {item['chunk']}: issue_number={item['issue_number']}, "
                f"compatibility_report_id={item['compatibility_report_id']}"
            )
