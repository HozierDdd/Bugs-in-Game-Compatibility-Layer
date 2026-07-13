"""Randomly sample Compatibility Report submissions from proton_issue_tracker dumps."""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

_COMPATIBILITY_REPORT_MARKER = "# compatibility report"
DEFAULT_SAMPLE_SIZE = 353


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_issue_tracker_dir() -> Path:
    return _repo_root() / "data" / "datasource" / "proton_issue_tracker"

def default_sample_output_path() -> Path:
    return Path(__file__).resolve().parent / "issue_tracker_sample.json"


def range_2021_through_2025_utc() -> tuple[datetime, datetime]:
    """Inclusive calendar range 2021-01-01 .. 2025-12-31 (end of day) in UTC."""
    start = datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2025, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)
    return start, end


def _parse_github_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _text_has_compatibility_report(text: str | None) -> bool:
    if not text:
        return False
    return _COMPATIBILITY_REPORT_MARKER in text.lower()


def collect_compatibility_report_submissions(
    tracker_dir: Path,
    range_start: datetime,
    range_end: datetime,
) -> list[dict]:
    """Same rules as issue_tracker_sample_number: in-window issue body + in-window comments."""
    out: list[dict] = []
    paths = sorted(tracker_dir.glob("proton_issues_*.json"))
    for path in paths:
        with path.open(encoding="utf-8") as f:
            blob = json.load(f)
        issues = blob.get("issues") or []
        if not isinstance(issues, list):
            continue
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            issue_num = issue.get("number")
            issue_created = _parse_github_ts(issue.get("created_at"))
            if (
                issue_created is not None
                and range_start <= issue_created <= range_end
                and _text_has_compatibility_report(issue.get("body"))
            ):
                out.append(
                    {
                        "body": issue.get("body"),
                        "url": issue.get("html_url")
                    }
                )

            for comment in issue.get("comments_data") or []:
                if not isinstance(comment, dict):
                    continue
                comment_created = _parse_github_ts(comment.get("created_at"))
                if (
                    comment_created is not None
                    and range_start <= comment_created <= range_end
                    and _text_has_compatibility_report(comment.get("body"))
                ):
                    out.append(
                        {
                            "body": comment.get("body"),
                            "url": comment.get("html_url")
                        }
                    )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Randomly sample Compatibility Report submissions (2021-2025 UTC, "
            'same rules as issue_tracker_sample_number: issue open or comment with '
            '"# Compatibility Report", each in-window post counts once).'
        )
    )
    parser.add_argument(
        "--tracker-dir",
        type=Path,
        default=None,
        help=(
            "Directory with proton_issues_*.json "
            "(default: repo data/datasource/proton_issue_tracker)"
        ),
    )
    parser.add_argument(
        "-n",
        "--sample-size",
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        help=f"Number of submissions to draw (default: {DEFAULT_SAMPLE_SIZE})",
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
            "(default: compatibility_report_sample.json next to this script)"
        ),
    )
    args = parser.parse_args()
    tracker_dir = args.tracker_dir or default_issue_tracker_dir()
    if not tracker_dir.is_dir():
        raise SystemExit(f"issue tracker directory not found: {tracker_dir}")

    start, end = range_2021_through_2025_utc()
    pool = collect_compatibility_report_submissions(tracker_dir, start, end)
    k = args.sample_size
    if len(pool) < k:
        raise SystemExit(
            f"not enough submissions: need {k}, have {len(pool)} in the date range"
        )

    rng = random.Random(args.seed)
    sample = rng.sample(pool, k)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()