#!/usr/bin/env python3
"""Verify the RQ1 ten-item content-coding numbers against the released labels.

1) Human-vs-LLM agreement, pooled over both platforms (all sampled CRs,
   ten binary items each):
     raw agreement (po) = 0.9142   <- the paper's reported 0.914 (raw agreement)
     Cohen's kappa      = 0.8266
   Per platform: ProtonDB kappa 0.8021 (po 0.9036), ProtonGT kappa 0.8237
   (po 0.9258) — see the two agreement_calculator scripts.

2) Per-item prevalence (the paper's Fig. 3), computed from the manual labels:
   ProtonDB  (n=384): matches the figure exactly on all ten items.
   ProtonGT: 353 CRs were labeled in total; the paper's figure uses a RANDOM
   345-record subset of them, drawn to match the designed sample size for the
   3,316-CR population (95% confidence, 5% margin of error). The released
   labels cover all 353 records, so values computed here differ from the
   figure by at most ~0.8 pp.

Run: python3 verify_content_coding.py   (no arguments, stdlib only)
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent

DIMENSIONS = [
    "observed_behavior",
    "expected_behavior",
    "proton_version",
    "steps_to_reproduce",
    "test_cases_or_example",
    "component",
    "program_output",
    "user_environment",
    "media",
    "product_game_title",
]

ITEM_LABELS = {
    "product_game_title": "game title",
    "user_environment": "user environment",
    "observed_behavior": "observed behavior",
    "proton_version": "Proton version",
    "test_cases_or_example": "test cases or example",
    "component": "component",
    "steps_to_reproduce": "steps to reproduce",
    "expected_behavior": "expected behavior",
    "program_output": "program output",
    "media": "media information",
}

# Values shown in the paper's Fig. 3 (ProtonDB n=384 / ProtonGT n=345).
PAPER_FIG3 = {
    "protondb": {"game title": 100.0, "user environment": 100.0, "observed behavior": 100.0,
                 "Proton version": 31.2, "test cases or example": 40.6, "component": 16.4,
                 "steps to reproduce": 18.2, "expected behavior": 9.4, "program output": 4.9,
                 "media information": 0.5},
    "issue_tracker": {"game title": 98.8, "user environment": 99.1, "observed behavior": 99.7,
                      "Proton version": 96.5, "test cases or example": 49.6, "component": 28.1,
                      "steps to reproduce": 91.3, "expected behavior": 11.9, "program output": 80.0,
                      "media information": 21.4},
}

FILES = {
    "protondb": ("result/human_labeled/protondb_label(manual_labeled).json",
                 "result/llm_labeled/protondb_label_result(llm).json"),
    "issue_tracker": ("result/human_labeled/issue_tracker_label(manual_labeled).json",
                      "result/llm_labeled/issue_tracker_label_result(llm).json"),
}


def load(rel: str) -> dict[int, dict]:
    data = json.load(open(BASE / rel, encoding="utf-8"))
    return {r["index"]: r["analysis"] for r in data if r.get("analysis")}


def kappa(pairs: list[tuple[bool, bool]]) -> tuple[float, float]:
    n = len(pairs)
    a = sum(1 for x, y in pairs if x and y)
    d = sum(1 for x, y in pairs if not x and not y)
    b = sum(1 for x, y in pairs if x and not y)
    c = sum(1 for x, y in pairs if not x and y)
    po = (a + d) / n
    pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
    k = 1.0 if pe == 1.0 else (po - pe) / (1.0 - pe)
    return k, po


def main() -> None:
    print("=" * 72)
    print("1) Human-vs-LLM agreement (ten items, binary judgments)")
    print("=" * 72)
    pooled: list[tuple[bool, bool]] = []
    for plat, (hf, lf) in FILES.items():
        h, l = load(hf), load(lf)
        common = sorted(set(h) & set(l))
        pairs = [(bool(h[i].get(dim)), bool(l[i].get(dim))) for i in common for dim in DIMENSIONS]
        k, po = kappa(pairs)
        pooled += pairs
        print(f"  {plat:<14} records={len(common):>3}  pairs={len(pairs):>4}  "
              f"kappa={k:.4f}  raw agreement={po:.4f}")
    k, po = kappa(pooled)
    print(f"  {'POOLED':<14} records={len(pooled)//10:>3}  pairs={len(pooled):>4}  "
          f"kappa={k:.4f}  raw agreement={po:.4f}")
    print(f"  -> the paper's reported 0.914 corresponds to the pooled RAW AGREEMENT ({po:.4f}).")

    print()
    print("=" * 72)
    print("2) Fig. 3 per-item prevalence from the manual labels")
    print("=" * 72)
    for plat, (hf, _) in FILES.items():
        h = load(hf)
        n = len(h)
        note = "" if plat == "protondb" else "  (paper figure uses a random 345-record subset; see module docstring)"
        print(f"--- {plat} (n={n}){note}")
        print(f"    {'item':<24} {'computed':>9} {'paper':>7}")
        for dim in DIMENSIONS:
            lab = ITEM_LABELS[dim]
            pct = sum(1 for a in h.values() if a.get(dim)) / n * 100
            paper = PAPER_FIG3[plat][lab]
            flag = "" if abs(round(pct, 1) - paper) < 0.06 else "   <- differs (figure: random n=345 subset)"
            print(f"    {lab:<24} {pct:>8.1f}% {paper:>6.1f}%{flag}")


if __name__ == "__main__":
    main()
