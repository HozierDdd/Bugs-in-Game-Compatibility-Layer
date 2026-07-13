"""
Compute the Micro Cohen's Kappa between two annotators (annotator_1 and
annotator_2) over the "tags" field in parts 27-33 (the RQ2 reliability batches).

Micro Cohen's Kappa: every (item, tag) combination is expanded into a single
unified sequence of binary decisions ("did this annotator apply this tag to
this item"), and one global confusion matrix is built to yield a single Kappa
value. It reflects the overall agreement across all binary decisions in the
multi-label annotation task, without being biased by the number of tags or by
rare tags.
"""

import json
import os
from sklearn.metrics import cohen_kappa_score

BASE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "compatibility_report_selection",
    "labeled_cr_symptom_data"
)
ANN1_DIR = os.path.join(BASE_DIR, "collaborative_annotation/refined_tags")
ANN2_DIR = os.path.join(BASE_DIR, "labeled_symptom_annotator_2/enhanced/refined_tags")
PARTS = range(27, 34)


def load_parts(ann_dir: str) -> dict[int, dict]:
    """Load every item in parts 27-33 of the given annotator directory, keyed by id."""
    items = {}
    for part in PARTS:
        path = os.path.join(ann_dir, f"part_{part}.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            items[item["id"]] = item
    return items


def compute_kappa() -> float:
    ann1_items = load_parts(ANN1_DIR)
    ann2_items = load_parts(ANN2_DIR)

    # Keep only items that both annotators labeled.
    common_ids = sorted(set(ann1_items) & set(ann2_items))
    if not common_ids:
        raise ValueError("No common items between the two annotators (no id intersection).")

    # Collect the union of all tags either annotator used across the common items.
    all_tags: set[str] = set()
    for id_ in common_ids:
        all_tags.update(ann1_items[id_].get("tags") or [])
        all_tags.update(ann2_items[id_].get("tags") or [])
    all_tags = sorted(all_tags)

    # -- Debug info: per-tag counts (not part of the final Kappa computation) -------
    print(f"Common items: {len(common_ids)}")
    print(f"Unique tags: {len(all_tags)}")
    print()
    print(f"{'[debug] tag':<35} {'Ann1 count':>13}  {'Ann2 count':>13}  {'identical':>12}")
    print("-" * 80)
    for tag in all_tags:
        vec1 = [1 if tag in (ann1_items[id_].get("tags") or []) else 0 for id_ in common_ids]
        vec2 = [1 if tag in (ann2_items[id_].get("tags") or []) else 0 for id_ in common_ids]
        perfect = "yes (skip)" if vec1 == vec2 else "no"
        print(f"{tag:<35} {sum(vec1):>13}  {sum(vec2):>13}  {perfect:>12}")
    print()

    # -- Micro Cohen's Kappa core computation ---------------------------------------
    # Expand all (item, tag) combinations into two equal-length global binary vectors:
    #   flat_ann1[i] = 1 means annotator_1 made a positive decision for the i-th
    #   (item, tag) pair. The agreement of the whole multi-label task is determined
    #   by this single global confusion matrix.
    flat_ann1: list[int] = []
    flat_ann2: list[int] = []

    for tag in all_tags:
        for id_ in common_ids:
            flat_ann1.append(1 if tag in (ann1_items[id_].get("tags") or []) else 0)
            flat_ann2.append(1 if tag in (ann2_items[id_].get("tags") or []) else 0)

    total_decisions = len(flat_ann1)  # = len(all_tags) x len(common_ids)

    # When the global vectors are perfectly identical (edge case), Cohen's Kappa is
    # still 0/0, so we handle it explicitly.
    if flat_ann1 == flat_ann2:
        raise ValueError(
            "The two annotators agree on every (item, tag) decision; Micro Kappa denominator is zero."
        )

    micro_kappa = cohen_kappa_score(flat_ann1, flat_ann2)

    print(f"Total global binary decisions (items x tags): {len(common_ids)} x {len(all_tags)} = {total_decisions}")
    print()
    print(f"{'=' * 62}")
    print(f"Final Micro Cohen's Kappa (global binary-decision agreement): {micro_kappa:.4f}")
    print(f"{'=' * 62}")
    return micro_kappa


if __name__ == "__main__":
    compute_kappa()
