#!/usr/bin/env python3
"""Cohen's Kappa for the fix STATUS (resolution_status) — the paper's k = 0.814.

Agreement between the two annotators on whether a CR has an observed fix,
over the full 66-CR re-reviewed subset:

  - annotator_A: ../second_annotator_66/   (66 CRs, independently re-reviewed subset)
  - annotator_B: ../../fix_labels/         (330 CRs, full labeled set)

resolution_status takes two values (with_observed_fix / no_observed_fix), so
the multi-class and binary formulations coincide.

Expected output (matches the paper):
  n=66  po=0.9091  kappa=0.8141
"""
import json, os
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
ANN_A_DIR = os.path.join(BASE, "..", "second_annotator_66")
ANN_B_DIR = os.path.join(BASE, "..", "..", "fix_labels")


def load_dir(d):
    # os.listdir (not glob) so the artifact also works under paths containing
    # glob metacharacters such as [brackets].
    items = {}
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        try:
            data = json.load(open(os.path.join(d, fn)))
        except Exception:
            continue
        if isinstance(data, list):
            for it in data:
                if "compatibility_report_id" in it:
                    items[it["compatibility_report_id"]] = it
    return items


def main():
    ann_a = load_dir(ANN_A_DIR)
    ann_b = load_dir(ANN_B_DIR)
    ids = sorted(set(ann_a) & set(ann_b))
    n = len(ids)
    print(f"CRs in both sets: {n}")

    pa = [ann_a[i].get("resolution_status") for i in ids]
    pb = [ann_b[i].get("resolution_status") for i in ids]
    print("annotator_A statuses:", dict(Counter(pa)))
    print("annotator_B statuses:", dict(Counter(pb)))

    cats = sorted(set(pa) | set(pb))
    po = sum(1 for x, y in zip(pa, pb) if x == y) / n
    pe = sum((pa.count(c) / n) * (pb.count(c) / n) for c in cats)
    kappa = (po - pe) / (1 - pe)
    print(f"\nresolution_status agreement: po={po:.4f}  pe={pe:.4f}  kappa={kappa:.4f}")
    print("(paper reports kappa = 0.814)")


if __name__ == "__main__":
    main()
