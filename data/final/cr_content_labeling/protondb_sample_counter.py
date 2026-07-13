"""sample number: 285304, sample size: 384"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_chunk_dir() -> Path:
    return _repo_root() / "data" / "datasource" / "protondb" / "chunks-2026-01"


def range_2021_through_2025_utc() -> tuple[int, int]:
    """Inclusive calendar range 2021-01-01 .. 2025-12-31 in UTC, as Unix seconds."""
    start = int(datetime(2021, 1, 1, tzinfo=timezone.utc).timestamp())
    end_inclusive = int(
        datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp()
    )
    return start, end_inclusive


def count_reports_in_range(
    chunk_dir: Path,
    start_ts: int,
    end_ts_inclusive: int,
) -> int:
    """Count JSON array entries whose ``timestamp`` lies in [start_ts, end_ts_inclusive]."""
    n = 0
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
                n += 1
    return n


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Count ProtonDB reports in chunks for 2021-01-01 .. 2025-12-31 (UTC)."
    )
    parser.add_argument(
        "--chunk-dir",
        type=Path,
        default=None,
        help="Directory containing cr_data_chunk_*.json (default: repo data/datasource/protondb/chunks-2026-01)",
    )
    args = parser.parse_args()
    chunk_dir = args.chunk_dir or default_chunk_dir()
    if not chunk_dir.is_dir():
        raise SystemExit(f"chunk directory not found: {chunk_dir}")

    start, end_inc = range_2021_through_2025_utc()
    total = count_reports_in_range(chunk_dir, start, end_inc)
    print(total)


if __name__ == "__main__":
    main()
