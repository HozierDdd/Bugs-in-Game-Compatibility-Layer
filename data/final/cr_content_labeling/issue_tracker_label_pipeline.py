"""Pipeline: load N issue-tracker samples, label each via llm_labeler(issue_tracker), save results."""

from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path


def _load_labeler():
    """Dynamically import ``llm_labeler(issue_tracker).py`` (parentheses in filename)."""
    spec_path = Path(__file__).resolve().parent / "llm_labeler(issue_tracker).py"
    spec = importlib.util.spec_from_file_location("llm_labeler_issue_tracker", str(spec_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def default_sample_path() -> Path:
    return Path(__file__).resolve().parent / "sample_data" / "issue_tracker_sample.json"


def default_output_path() -> Path:
    return Path(__file__).resolve().parent / "result" / "overall_result" /"issue_tracker_label_result(llm).json"


def load_samples(path: Path, n: int) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data[:n]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Label N issue-tracker compatibility reports using the LLM labeler.",
    )
    parser.add_argument(
        "-n",
        type=int,
        default=353,
        help="Number of samples to label (default: 50)",
    )
    parser.add_argument(
        "--sample-path",
        type=Path,
        default=default_sample_path(),
        help="Path to issue_tracker_sample.json",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=default_output_path(),
        help="Path for the result JSON file",
    )
    args = parser.parse_args()

    # ---- import labeler and initialise client ----
    labeler = _load_labeler()
    api_key, model, temperature = labeler.load_environment()
    client = labeler.create_client(api_key)

    # ---- load samples ----
    samples = load_samples(args.sample_path, args.n)
    print(f"Loaded {len(samples)} samples from {args.sample_path}")

    # ---- label each sample ----
    results: list[dict] = []
    for idx, sample in enumerate(samples):
        url = sample.get("url", "")
        body = sample.get("body", "")
        tag = f"[{idx + 1}/{len(samples)}]"

        if not body:
            print(f"{tag} SKIP (empty body): {url}")
            continue

        print(f"{tag} Labeling: {url}")
        try:
            analysis = labeler.label_single(client, model, temperature, body)
        except Exception as e:
            print(f"{tag} ERROR: {e}")
            analysis = None

        results.append({
            "index": idx,
            "url": url,
            "analysis": analysis,
        })

        time.sleep(0.5)

    # ---- write output ----
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\nDone. {len(results)} results written to {args.output}")


if __name__ == "__main__":
    main()
