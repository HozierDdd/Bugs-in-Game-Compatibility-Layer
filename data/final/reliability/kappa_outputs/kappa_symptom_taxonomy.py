#!/usr/bin/env python3
"""Cohen's Kappa for the RQ2 symptom taxonomy — the paper's k = 0.77.

Agreement on the 7 held-out batches (parts 27-33, 70 CRs) between:

  - annotator_A's independent labels under the consolidated 25-tag taxonomy
    (../../symptom_labels/last_7_chunk_result(annotator_A)/initial_tags/round_2/)
  - the collaborative refined labels
    (../../symptom_labels/collaborative_annotation/refined_tags/ parts 27-33)

Method (matches the paper): each tag in the union label universe is treated as
a present/absent judgment per CR; Cohen's kappa is computed over all
(CR x tag) binary cells.

Expected output: kappa = 0.7712 (n = 70 CRs; paper reports 0.77).

For reference, annotator_A's post-adjudication refined_tags vs the
collaborative refined labels yields kappa = 0.92; the paper deliberately
reports only the pre-adjudication 0.77 (the 0.92 re-code was considered
contaminated by the adjudication discussion).
"""
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))
SYM = os.path.join(BASE, "..", "..", "symptom_labels")
ANN_A_DIR = os.path.join(SYM, "last_7_chunk_result(annotator_A)", "initial_tags", "round_2")
COLLAB_DIR = os.path.join(SYM, "collaborative_annotation", "refined_tags")
HELD_OUT_PARTS = range(27, 34)  # parts 27-33


def load_dir(d, parts=None):
    # os.listdir (not glob) so the artifact also works under paths containing
    # glob metacharacters such as [brackets].
    recs = {}
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        if parts is not None:
            try:
                n = int(fn.split("_")[-1].split(".")[0])
            except ValueError:
                continue
            if n not in parts:
                continue
        for r in json.load(open(os.path.join(d, fn))):
            recs[r["id"]] = set(r.get("tags") or [])
    return recs


def main():
    a = load_dir(ANN_A_DIR)
    b = load_dir(COLLAB_DIR, parts=HELD_OUT_PARTS)
    ids = sorted(set(a) & set(b))
    universe = sorted(set().union(*a.values()) | set().union(*b.values()))
    print(f"CRs: {len(ids)} | label universe: {len(universe)} tags")

    ya, yb = [], []
    for i in ids:
        for t in universe:
            ya.append(1 if t in a[i] else 0)
            yb.append(1 if t in b[i] else 0)
    n = len(ya)
    po = sum(1 for x, y in zip(ya, yb) if x == y) / n
    p1a, p1b = sum(ya) / n, sum(yb) / n
    pe = p1a * p1b + (1 - p1a) * (1 - p1b)
    kappa = (po - pe) / (1 - pe)
    print(f"binary cells: n={n}  po={po:.4f}  pe={pe:.4f}  kappa={kappa:.4f}")
    print("(paper reports kappa = 0.77)")


if __name__ == "__main__":
    main()
