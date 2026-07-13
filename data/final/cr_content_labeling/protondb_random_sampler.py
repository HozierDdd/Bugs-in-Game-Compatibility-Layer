"""Randomly sample 384 ProtonDB compatibility reports from 2021-01-01 to 2025-12-31 (UTC)."""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SAMPLE_SIZE = 384


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_chunk_dir() -> Path:
    return _repo_root() / "data" / "datasource" / "protondb" / "chunks-2026-01"


def default_sample_output_path() -> Path:
    return Path(__file__).resolve().parent / "sample_data" / "protondb_sample.json"


def range_2021_through_2025_utc() -> tuple[int, int]:
    """Inclusive calendar range 2021-01-01 .. 2025-12-31 in UTC, as Unix seconds."""
    start = int(datetime(2021, 1, 1, tzinfo=timezone.utc).timestamp())
    end_inclusive = int(
        datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp()
    )
    return start, end_inclusive


def collect_reports_in_range(
    chunk_dir: Path,
    start_ts: int,
    end_ts_inclusive: int,
) -> list[dict]:
    """Collect all CR entries whose ``timestamp`` lies in [start_ts, end_ts_inclusive]."""
    pool: list[dict] = []
    for path in sorted(chunk_dir.glob("cr_data_chunk_*.json")):
        with path.open("rb") as f:
            batch = json.load(f)
        if not isinstance(batch, list):
            continue
        for item in batch:
            ts = item.get("timestamp")
            if ts is None:
                continue
            if start_ts <= ts <= end_ts_inclusive:
                pool.append(item)
    return pool


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Randomly sample ProtonDB compatibility reports "
            "(2021-01-01 .. 2025-12-31 UTC) from chunk files."
        )
    )
    parser.add_argument(
        "--chunk-dir",
        type=Path,
        default=None,
        help=(
            "Directory containing cr_data_chunk_*.json "
            "(default: repo data/datasource/protondb/chunks-2026-01)"
        ),
    )
    parser.add_argument(
        "-n",
        "--sample-size",
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        help=f"Number of reports to draw (default: {DEFAULT_SAMPLE_SIZE})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for reproducible sampling",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=default_sample_output_path(),
        help=(
            "Path for the sampled JSON array "
            "(default: sample_data/protondb_sample.json next to this script)"
        ),
    )
    args = parser.parse_args()
    chunk_dir = args.chunk_dir or default_chunk_dir()
    if not chunk_dir.is_dir():
        raise SystemExit(f"chunk directory not found: {chunk_dir}")

    start, end_inc = range_2021_through_2025_utc()
    pool = collect_reports_in_range(chunk_dir, start, end_inc)
    k = args.sample_size
    if len(pool) < k:
        raise SystemExit(
            f"not enough reports: need {k}, have {len(pool)} in the date range"
        )

    rng = random.Random(args.seed)
    sample = rng.sample(pool, k)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Sampled {k} reports from {len(pool)} candidates -> {args.output}")


if __name__ == "__main__":
    main()
