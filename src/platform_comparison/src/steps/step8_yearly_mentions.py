"""
Step 8: yearly-trend analysis of cross-platform information flow (2021–2025).

Building on the Step 7 counting logic, this breaks the five-year change in
mutual references down by year:
  A) ProtonDB CR → GitHub Proton issue tracker: bucketed by the CR's Unix-timestamp year
  B) GitHub CR → ProtonDB: bucketed by each post's own created_at year
     - issue-body CRs use issue.created_at
     - comment CRs use comment.created_at

The scope matches Step 7 (matched games + time window); this only adds a yearly
breakdown on top of the Step 7 aggregation, with no recomputation beyond the
one full load of the ProtonDB reports file.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from src.config import (
    PROTONDB_REPORTS_PATH,
    GITHUB_CHUNKS_DIR,
    GITHUB_CHUNK_GLOB,
    STEP1_OUTPUT,
    STEP3_THREADS_OUTPUT,
    STEP8_OUTPUT,
    PROTONDB_TS_START,
    PROTONDB_TS_END,
    UNRESOLVED_APPID,
)
# Reuse step7's regex patterns and helpers so the search logic stays identical
from src.steps.step7_cross_platform_mentions import (
    _pdb_notes_text,
    _pct,
    _GH_ISSUE_URL,
    _GH_ANY,
    _PDB_URL,
    _PDB_ANY,
)
from src.parsers.compatibility_report_classifier import classify_post
from src.utils.json_io import load_json, save_json
from src.utils.datetime_utils import now_utc_iso, from_iso8601

YEARS: list[int] = list(range(2021, 2026))
_YEAR_SET: set[int] = set(YEARS)


def _ts_to_year(ts: float) -> int | None:
    """Unix timestamp → year; returns None if outside the study range."""
    y = datetime.fromtimestamp(ts, tz=timezone.utc).year
    return y if y in _YEAR_SET else None


def _iso_to_year(s: str) -> int | None:
    """ISO 8601 string → year; returns None on parse failure or outside the study range."""
    if not s:
        return None
    try:
        y = from_iso8601(s).year
    except ValueError:
        return None
    return y if y in _YEAR_SET else None


def _empty_pdb_buckets() -> dict[str, list[int]]:
    """Three counters per year: [total_cr, mention_strict, mention_any]."""
    return {str(y): [0, 0, 0] for y in YEARS}


def _empty_gh_buckets() -> list[dict[str, list[int]]]:
    """Three scopes × three counters per year: [total_cr, url_hit, any_hit]."""
    return [{str(y): [0, 0, 0] for y in YEARS} for _ in range(3)]


# ── Part A: ProtonDB-side yearly scan ─────────────────────────────────────────

def scan_protondb_by_year(matched_appids: set[str]) -> dict[str, dict]:
    """
    Single pass over all ProtonDB reports, counting GitHub mentions by the CR's
    submission year. The search logic is identical to scan_protondb() (Step 7),
    only adding yearly bucketing.
    """
    print("[Step 8-A] Loading ProtonDB reports...")
    raw_data: list = load_json(PROTONDB_REPORTS_PATH)
    print(f"  Total raw records: {len(raw_data):,}")

    buckets = _empty_pdb_buckets()

    for rec in raw_data:
        ts = rec.get("timestamp")
        if ts is None or not (PROTONDB_TS_START <= ts <= PROTONDB_TS_END):
            continue
        try:
            app_id = str(rec["app"]["steam"]["appId"])
        except (KeyError, TypeError):
            continue
        if app_id not in matched_appids:
            continue

        year = _ts_to_year(ts)
        if year is None:
            continue

        b = buckets[str(year)]
        b[0] += 1
        text = _pdb_notes_text(rec.get("responses") or {})
        if text:
            if _GH_ISSUE_URL.search(text):
                b[1] += 1
            if _GH_ANY.search(text):
                b[2] += 1

    result: dict[str, dict] = {}
    for y in YEARS:
        cr, strict, any_ = buckets[str(y)]
        result[str(y)] = {
            "total_cr": cr,
            "mention_proton_issue_url": {
                "count": strict,
                "pct": _pct(strict, cr),
                "pattern": "github.com/ValveSoftware/Proton/issues/<number> (case-insensitive)",
            },
            "mention_any_github": {
                "count": any_,
                "pct": _pct(any_, cr),
                "pattern": "github.com (case-insensitive, any link)",
            },
        }
        print(f"  {y}: CR {cr:,}  Proton issue URL {strict:,} ({_pct(strict, cr)}%)  "
              f"any github.com {any_:,} ({_pct(any_, cr)}%)")

    return result


# ── Part B: GitHub CR-side yearly scan ───────────────────────────────────────

def scan_github_crs_by_year(matched_appids: set[str]) -> dict[str, dict]:
    """
    Single pass over all GitHub chunks, counting ProtonDB mentions by each CR
    post's created_at year. Issue-body CRs use issue.created_at; comment CRs use
    comment.created_at. The search logic is identical to scan_github_crs()
    (Step 7), only adding yearly bucketing.
    """
    print("  Loading step3_github_threads.json for the issue→appid mapping...")
    threads: list[dict] = load_json(STEP3_THREADS_OUTPUT).get("threads", [])

    all_numbers: set[int] = set()
    appid_map: dict[int, str] = {}
    for t in threads:
        num = t.get("issue_number")
        if num is None:
            continue
        all_numbers.add(num)
        appid = t.get("resolved_appid")
        if appid and appid != UNRESOLVED_APPID:
            appid_map[num] = appid

    print(f"  Total issues in the time window: {len(all_numbers):,}, of which resolved appids: {len(appid_map):,}")

    # counters[scope_idx][year_str] = [total_cr, url_hit, any_hit]
    counters = _empty_gh_buckets()

    chunk_files = sorted(Path(GITHUB_CHUNKS_DIR).glob(GITHUB_CHUNK_GLOB))
    for chunk_path in chunk_files:
        with open(chunk_path, encoding="utf-8") as f:
            chunk = json.load(f)

        for issue in (chunk.get("issues") or []):
            number = issue.get("number")
            if number not in all_numbers:
                continue

            appid = appid_map.get(number)
            is_resolved = appid is not None
            is_matched = is_resolved and appid in matched_appids

            # (body, created_at) pairs: issue body + each comment
            posts = [(issue.get("body") or "", issue.get("created_at") or "")]
            posts += [
                (c.get("body") or "", c.get("created_at") or "")
                for c in (issue.get("comments_data") or [])
            ]

            for body, created_at in posts:
                if not classify_post(body)["is_compatibility_report"]:
                    continue
                year = _iso_to_year(created_at)
                if year is None:
                    continue

                y = str(year)
                url_hit = bool(_PDB_URL.search(body))
                any_hit = bool(_PDB_ANY.search(body))

                counters[0][y][0] += 1
                if url_hit: counters[0][y][1] += 1
                if any_hit: counters[0][y][2] += 1
                if is_resolved:
                    counters[1][y][0] += 1
                    if url_hit: counters[1][y][1] += 1
                    if any_hit: counters[1][y][2] += 1
                if is_matched:
                    counters[2][y][0] += 1
                    if url_hit: counters[2][y][1] += 1
                    if any_hit: counters[2][y][2] += 1

    scope_keys = ["all_issues_in_window", "resolved_appid_games", "matched_games_only"]

    def _scope(cr: int, url: int, any_: int) -> dict:
        return {
            "total_cr": cr,
            "mention_protondb_url": {
                "count": url, "pct": _pct(url, cr),
                "pattern": "protondb.com (case-insensitive)",
            },
            "mention_protondb_any": {
                "count": any_, "pct": _pct(any_, cr),
                "pattern": "protondb (case-insensitive, name and URL)",
            },
        }

    result: dict[str, dict] = {}
    for y in YEARS:
        y_str = str(y)
        result[y_str] = {
            scope_keys[i]: _scope(*counters[i][y_str])
            for i in range(3)
        }
        cr_all, url_all, any_all = counters[0][y_str]
        print(f"  {y}: CR (all) {cr_all:,}  protondb.com {url_all:,} ({_pct(url_all, cr_all)}%)  "
              f"protondb name {any_all:,} ({_pct(any_all, cr_all)}%)")

    return result


# ── Main entry point ──────────────────────────────────────────────────────────

def run() -> dict:
    print("[Step 8] Yearly-trend analysis of cross-platform information flow (2021–2025)")
    print("=" * 60)

    step1 = load_json(STEP1_OUTPUT)
    matched_appids: set[str] = set(step1["in_both"])
    print(f"  Matched games (in_both): {len(matched_appids):,}")
    print()

    print("── Part A: ProtonDB CRs mentioning the GitHub Proton issue tracker, by year ──")
    result_a = scan_protondb_by_year(matched_appids)
    print()

    print("── Part B: GitHub CRs mentioning ProtonDB, by year ──")
    result_b = scan_github_crs_by_year(matched_appids)
    print()

    result = {
        "step": "step8_yearly_mentions",
        "generated_at": now_utc_iso(),
        "years": YEARS,
        "n_matched_games": len(matched_appids),
        "note": (
            "The year is based on each CR post's own timestamp: the ProtonDB side uses the Unix timestamp, "
            "the GitHub side uses the created_at of the issue body or comment."
        ),
        "part_a_protondb_mentions_github_by_year": result_a,
        "part_b_github_cr_mentions_protondb_by_year": result_b,
    }

    save_json(result, STEP8_OUTPUT)
    print(f"[Step 8] Results saved to: {STEP8_OUTPUT}")
    return result


if __name__ == "__main__":
    run()
