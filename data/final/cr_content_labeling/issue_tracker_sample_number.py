"""CR number: 4377, sample size: 353"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


_COMPATIBILITY_REPORT_MARKER = "# compatibility report"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_issue_tracker_dir() -> Path:
    return _repo_root() / "data" / "datasource" / "proton_issue_tracker"


def range_2021_through_2025_utc() -> tuple[datetime, datetime]:
    """Inclusive calendar range 2021-01-01 .. 2025-12-31 (end of day) in UTC."""
    start = datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2025, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)
    return start, end


def _parse_github_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    # e.g. "2018-08-21T22:40:50Z"
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _text_has_compatibility_report(text: str | None) -> bool:
    if not text:
        return False
    return _COMPATIBILITY_REPORT_MARKER in text.lower()


def count_compatibility_reports_in_range(
    tracker_dir: Path,
    range_start: datetime,
    range_end: datetime,
) -> int:
    """Each in-window submission counts once: opening post and each comment separately."""
    n = 0
    paths = sorted(tracker_dir.glob("proton_issues_*.json"))
    if not paths:
        return 0
    for path in paths:
        with path.open(encoding="utf-8") as f:
            blob = json.load(f)
        issues = blob.get("issues") or []
        if not isinstance(issues, list):
            continue
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            issue_created = _parse_github_ts(issue.get("created_at"))
            if (
                issue_created is not None
                and range_start <= issue_created <= range_end
                and _text_has_compatibility_report(issue.get("body"))
            ):
                n += 1

            for comment in issue.get("comments_data") or []:
                if not isinstance(comment, dict):
                    continue
                comment_created = _parse_github_ts(comment.get("created_at"))
                if (
                    comment_created is not None
                    and range_start <= comment_created <= range_end
                    and _text_has_compatibility_report(comment.get("body"))
                ):
                    n += 1
    return n


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Count Compatibility Report submissions in proton_issue_tracker: each issue "
            "created in 2021-01-01 .. 2025-12-31 (UTC) whose body matches, plus each "
            "comment created in that window whose body matches (case-insensitive "
            '"# Compatibility Report").'
        )
    )
    parser.add_argument(
        "--tracker-dir",
        type=Path,
        default=None,
        help=(
            "Directory with proton_issues_*.json dumps "
            "(default: repo data/datasource/proton_issue_tracker)"
        ),
    )
    args = parser.parse_args()
    tracker_dir = args.tracker_dir or default_issue_tracker_dir()
    if not tracker_dir.is_dir():
        raise SystemExit(f"issue tracker directory not found: {tracker_dir}")

    start, end = range_2021_through_2025_utc()
    total = count_compatibility_reports_in_range(tracker_dir, start, end)
    print(total)


if __name__ == "__main__":
    main()
