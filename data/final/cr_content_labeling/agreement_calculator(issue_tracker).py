"""Compute human-vs-LLM agreement on the ten CR content items for the ProtonGT.

Compares the full manual labels (result/human_labeled/) against the LLM labels
(result/llm_labeled/) over all 353 sampled ProtonGT CRs, pooling the ten
items into binary (record x item) judgments.

Expected output:
Samples: 353
Label pairs: 3530
Cohen's Kappa: 0.8237
Raw Agreement: 0.9258
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


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


def default_human_path() -> Path:
    return (
        Path(__file__).resolve().parent
        / "result" / "human_labeled" / "issue_tracker_label(manual_labeled).json"
    )


def default_llm_path() -> Path:
    return (
        Path(__file__).resolve().parent
        / "result" / "llm_labeled" / "issue_tracker_label_result(llm).json"
    )


def load_labels(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _cohens_kappa(y1: list[bool], y2: list[bool]) -> float:
    """Compute Cohen's Kappa for two lists of binary labels."""
    n = len(y1)
    if n == 0:
        return float("nan")

    a = sum(1 for a1, a2 in zip(y1, y2) if a1 and a2)
    d = sum(1 for a1, a2 in zip(y1, y2) if not a1 and not a2)
    b = sum(1 for a1, a2 in zip(y1, y2) if a1 and not a2)
    c = sum(1 for a1, a2 in zip(y1, y2) if not a1 and a2)

    po = (a + d) / n
    pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)

    if pe == 1.0:
        return 1.0
    return (po - pe) / (1.0 - pe)


def compute_agreement(human_data: list[dict], llm_data: list[dict]) -> dict:
    """Return overall Cohen's Kappa and raw agreement, pooled across all dimensions."""
    human_map = {item["index"]: item["analysis"] for item in human_data if item.get("analysis")}
    llm_map = {item["index"]: item["analysis"] for item in llm_data if item.get("analysis")}
    common_indices = sorted(set(human_map) & set(llm_map))

    if not common_indices:
        raise ValueError("No overlapping samples with valid analyses found.")

    all_human: list[bool] = []
    all_llm: list[bool] = []

    for idx in common_indices:
        h = human_map[idx]
        l = llm_map[idx]
        for dim in DIMENSIONS:
            all_human.append(bool(h.get(dim, False)))
            all_llm.append(bool(l.get(dim, False)))

    kappa = _cohens_kappa(all_human, all_llm)
    raw = sum(1 for a, b in zip(all_human, all_llm) if a == b) / len(all_human)

    return {
        "num_samples": len(common_indices),
        "num_dimensions": len(DIMENSIONS),
        "total_label_pairs": len(all_human),
        "cohens_kappa": round(kappa, 4),
        "raw_agreement": round(raw, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute overall Cohen's Kappa between human and LLM label results.",
    )
    parser.add_argument(
        "--human", type=Path, default=default_human_path(),
        help="Path to human label result JSON",
    )
    parser.add_argument(
        "--llm", type=Path, default=default_llm_path(),
        help="Path to LLM label result JSON",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Optional path to save agreement report as JSON",
    )
    args = parser.parse_args()

    human_data = load_labels(args.human)
    llm_data = load_labels(args.llm)
    report = compute_agreement(human_data, llm_data)

    print(f"Samples: {report['num_samples']}")
    print(f"Label pairs: {report['total_label_pairs']}")
    print(f"Cohen's Kappa: {report['cohens_kappa']}")
    print(f"Raw Agreement: {report['raw_agreement']}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"Report saved to {args.output}")


if __name__ == "__main__":
    main()
