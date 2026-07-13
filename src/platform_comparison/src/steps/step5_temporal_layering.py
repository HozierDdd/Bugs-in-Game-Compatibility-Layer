"""
Step 5: Temporal Layering analysis.

Research goal: for games that appear on both platforms, measure the first
appearance time on ProtonDB and on GitHub, and the ordering between the two
(lead time).

This step only captures first-appearance ordering; it says nothing about
platform quality, activity level, or causal influence.
"""

import json
from pathlib import Path
from statistics import median

from src.config import (
    GITHUB_CHUNKS_DIR,
    GITHUB_CHUNK_GLOB,
    PROTONDB_REPORTS_PATH,
    PROTONDB_TS_START,
    PROTONDB_TS_END,
    STEP4_OUTPUT,
    STEP5_GAMES_OUTPUT,
    STEP5_SUMMARY_OUTPUT,
    STEP5_TOP_PDB_OUTPUT,
    STEP5_TOP_GH_OUTPUT,
    STEP5_SAME_DAY_OUTPUT,
    STATS_ROUND_DIGITS,
    TIME_WINDOW_START,
    TIME_WINDOW_END,
)
from src.utils.datetime_utils import (
    from_iso8601, from_unix_timestamp, now_utc_iso, thread_median_in_window,
)
from src.utils.json_io import load_json, save_json
from src.utils.stats import percentile

# ── Constants ─────────────────────────────────────────────────────────────────
_OUTLIER_TOP_N = 20   # max rows for outlier / spot-check samples
_SAME_DAY_SAMPLE = 20 # max rows for same-day sampling


# ── Internal helpers ──────────────────────────────────────────────────────────

def _classify_sign(lead_days: float,
                   pdb_date_str: str,
                   gh_date_str: str) -> str:
    """
    Decide the ordering class from each platform's first-appearance UTC date.

    Rules:
    - Same UTC date                       → "same_day"
    - lead_days > 0 (GitHub later)        → "protondb_first"
    - lead_days < 0 (ProtonDB later)      → "github_first"

    The date-string arguments are already ISO 8601 UTC, e.g.
    "2021-03-15T10:22:00+00:00".
    """
    pdb_date = from_iso8601(pdb_date_str).date()
    gh_date  = from_iso8601(gh_date_str).date()
    if pdb_date == gh_date:
        return "same_day"
    return "protondb_first" if lead_days > 0 else "github_first"


# ── Data scan: ProtonDB ────────────────────────────────────────────────────────

def _scan_protondb_earliest(
    matched_appids: set[str],
) -> dict[str, dict]:
    """
    Scan raw ProtonDB records and, for each matched appid, find the earliest
    report within the time window.

    Returns:
        {appid: {"first_report_time": ISO str, "n_reports": int}}
    """
    raw_data = load_json(PROTONDB_REPORTS_PATH)

    # appid -> (earliest_ts, count)
    earliest: dict[str, float] = {}
    counts: dict[str, int]     = {}

    for raw in raw_data:
        ts = raw.get("timestamp")
        if ts is None or not (PROTONDB_TS_START <= ts <= PROTONDB_TS_END):
            continue
        try:
            app_id = str(raw["app"]["steam"]["appId"])
        except (KeyError, TypeError):
            continue
        if app_id not in matched_appids:
            continue
        # Update the earliest timestamp
        if app_id not in earliest or ts < earliest[app_id]:
            earliest[app_id] = ts
        counts[app_id] = counts.get(app_id, 0) + 1

    result: dict[str, dict] = {}
    for appid, ts in earliest.items():
        dt = from_unix_timestamp(ts)
        result[appid] = {
            # Normalize output to an ISO 8601 UTC string
            "first_report_time": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_reports": counts[appid],
        }
    return result


# ── Data scan: GitHub ──────────────────────────────────────────────────────────

def _scan_github_earliest(
    matched_appids: set[str],
) -> dict[str, dict]:
    """
    Scan all GitHub issue chunks and, for each matched appid, find the earliest
    created issue within the time window (ties broken by the smallest issue
    number, for determinism).

    AppID extraction reuses exactly the same three-tier rules as step3 (via
    appid_extractor).

    Returns:
        {appid: {"first_issue_time": ISO str,
                 "first_issue_number": int,
                 "first_issue_title": str,
                 "n_issues": int}}
    """
    # Deferred import to avoid a circular dependency
    from src.parsers.appid_extractor import extract_appid
    from src.config import UNRESOLVED_APPID

    chunks_dir = Path(GITHUB_CHUNKS_DIR)
    chunk_files = sorted(chunks_dir.glob(GITHUB_CHUNK_GLOB))

    if not chunk_files:
        raise FileNotFoundError(
            f"No chunk files matching '{GITHUB_CHUNK_GLOB}' found under {chunks_dir}"
        )

    # appid -> (earliest_dt, issue_number, title)
    earliest_dt:  dict[str, object] = {}   # datetime
    earliest_num: dict[str, int]    = {}
    earliest_ttl: dict[str, str]    = {}
    counts: dict[str, int]          = {}

    for chunk_path in chunk_files:
        with open(chunk_path, encoding="utf-8") as f:
            chunk = json.load(f)

        for raw_issue in chunk.get("issues") or []:
            created_str = raw_issue.get("created_at")
            if not created_str:
                continue
            try:
                dt = from_iso8601(created_str)
            except ValueError:
                continue

            title = raw_issue.get("title") or ""
            body  = raw_issue.get("body")  or ""
            number = raw_issue.get("number")
            if number is None:
                continue

            # Time-window filter: created_at in window, or thread median in window
            if not (TIME_WINDOW_START <= dt <= TIME_WINDOW_END):
                if not thread_median_in_window(raw_issue, TIME_WINDOW_START, TIME_WINDOW_END):
                    continue

            appid, _rule = extract_appid(title, body)
            if appid == UNRESOLVED_APPID or appid not in matched_appids:
                continue

            counts[appid] = counts.get(appid, 0) + 1

            # Key on the earliest dt; ties broken by smallest issue number (deterministic)
            if appid not in earliest_dt:
                earliest_dt[appid]  = dt
                earliest_num[appid] = number
                earliest_ttl[appid] = title
            elif dt < earliest_dt[appid] or (
                dt == earliest_dt[appid] and number < earliest_num[appid]
            ):
                earliest_dt[appid]  = dt
                earliest_num[appid] = number
                earliest_ttl[appid] = title

    result: dict[str, dict] = {}
    for appid, dt in earliest_dt.items():
        result[appid] = {
            "first_issue_time": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "first_issue_number": earliest_num[appid],
            "first_issue_title": earliest_ttl[appid],
            "n_issues": counts[appid],
        }
    return result


# ── Core computation ───────────────────────────────────────────────────────────

def _build_game_rows(
    matched_games: list[dict],
    pdb_data: dict[str, dict],
    gh_data: dict[str, dict],
) -> list[dict]:
    """
    Build a temporal-layering row for each matched game.
    If a platform still lacks a timestamp after scanning (should not happen in
    theory), skip that game and print a warning.
    """
    rows = []
    skipped = 0

    for game in matched_games:
        appid = game["game_appid"]
        pdb   = pdb_data.get(appid)
        gh    = gh_data.get(appid)

        if pdb is None or gh is None:
            # A handful of appids may be inconsistent between the raw data and master_summary
            skipped += 1
            continue

        pdb_time_str = pdb["first_report_time"]
        gh_time_str  = gh["first_issue_time"]

        # lead_time_days = GitHub first-appearance - ProtonDB first-appearance (days, float)
        pdb_dt = from_iso8601(pdb_time_str)
        gh_dt  = from_iso8601(gh_time_str)
        delta  = gh_dt - pdb_dt
        lead_days = delta.total_seconds() / 86400.0

        sign = _classify_sign(lead_days, pdb_time_str, gh_time_str)

        rows.append({
            "game_appid":               appid,
            "game_title_protondb":      game.get("game_title_protondb") or "",
            "first_report_time_protondb": pdb_time_str,
            "first_issue_time_github":  gh_time_str,
            "lead_time_days":           lead_days,
            "lead_time_sign":           sign,
            "n_reports_protondb_in_window": pdb["n_reports"],
            "n_issues_github_in_window": gh["n_issues"],
            "first_issue_number":       gh["first_issue_number"],
            "first_issue_title":        gh["first_issue_title"],
        })

    if skipped:
        print(f"  [Warning] {skipped} appids missing timestamp data, skipped")

    return rows


def _compute_summary(rows: list[dict]) -> dict:
    """Compute summary stats: sign distribution + continuous lead_time distribution."""
    total = len(rows)
    if total == 0:
        return {}

    n_pdb  = sum(1 for r in rows if r["lead_time_sign"] == "protondb_first")
    n_same = sum(1 for r in rows if r["lead_time_sign"] == "same_day")
    n_gh   = sum(1 for r in rows if r["lead_time_sign"] == "github_first")

    leads = [r["lead_time_days"] for r in rows]
    r = STATS_ROUND_DIGITS

    return {
        # Sign distribution
        "n_matched_games":     total,
        "n_protondb_first":    n_pdb,
        "n_same_day":          n_same,
        "n_github_first":      n_gh,
        "pct_protondb_first":  round(n_pdb  / total * 100, r),
        "pct_same_day":        round(n_same / total * 100, r),
        "pct_github_first":    round(n_gh   / total * 100, r),
        # Continuous distribution
        "median_lead_time_days": round(median(leads), r),
        "iqr_lead_time_days":    round(
            percentile(leads, 75) - percentile(leads, 25), r
        ),
        "p10_lead_time_days":  round(percentile(leads, 10), r),
        "p90_lead_time_days":  round(percentile(leads, 90), r),
        "min_lead_time_days":  round(min(leads), r),
        "max_lead_time_days":  round(max(leads), r),
    }


# ── Outlier / spot-check output fields ─────────────────────────────────────────

_SPOT_FIELDS = (
    "game_appid",
    "game_title_protondb",
    "lead_time_days",
    "first_report_time_protondb",
    "first_issue_time_github",
    "first_issue_number",
    "first_issue_title",
)


def _extract_spot(row: dict) -> dict:
    """Pull the fields needed for spot-checking from a full row."""
    return {k: row[k] for k in _SPOT_FIELDS}


# ── Main entry point ──────────────────────────────────────────────────────────

def run() -> dict:
    """Step 5 entry point: temporal layering analysis."""
    print("[Step 5] Temporal Layering analysis...")

    # ── 1. Get the matched-game set from master_summary ─────────────────────
    print("  Loading master summary (master_summary.json)...")
    master = load_json(STEP4_OUTPUT)
    matched_games = [
        g for g in master["games"]
        if g.get("present_in_protondb") and g.get("present_in_github")
    ]
    matched_appids = {g["game_appid"] for g in matched_games}
    print(f"  Matched games (present on both platforms): {len(matched_appids)}")

    # ── 2. Scan ProtonDB first-appearance times ─────────────────────────────
    print("  Scanning ProtonDB first-report times...")
    pdb_data = _scan_protondb_earliest(matched_appids)
    print(f"    appids with a valid timestamp: {len(pdb_data)}")

    # ── 3. Scan GitHub first-appearance times ────────────────────────────────
    print("  Scanning GitHub first-issue times...")
    gh_data = _scan_github_earliest(matched_appids)
    print(f"    appids with a valid timestamp: {len(gh_data)}")

    # ── 4. Build per-game temporal rows ──────────────────────────────────────
    print("  Computing lead_time_days and sign classification...")
    rows = _build_game_rows(matched_games, pdb_data, gh_data)
    print(f"  Valid game rows: {len(rows)}")

    # ── 5. Summary statistics ────────────────────────────────────────────────
    summary_stats = _compute_summary(rows)
    print(
        f"  ProtonDB first: {summary_stats.get('n_protondb_first')} | "
        f"same day: {summary_stats.get('n_same_day')} | "
        f"GitHub first: {summary_stats.get('n_github_first')}"
    )
    print(
        f"  lead_time median: {summary_stats.get('median_lead_time_days')} days | "
        f"IQR: {summary_stats.get('iqr_lead_time_days')} days"
    )

    # ── Shared metadata ──────────────────────────────────────────────────────
    generated_at = now_utc_iso()
    time_window_meta = {
        "start": TIME_WINDOW_START.isoformat(),
        "end":   TIME_WINDOW_END.isoformat(),
    }
    definitions = {
        "first_report_time_protondb": (
            "Earliest ProtonDB-report Unix timestamp for the game within the time window, "
            "converted to a UTC ISO 8601 string"
        ),
        "first_issue_time_github": (
            "Earliest GitHub issue created_at (UTC) for the game within the time window, "
            "as an ISO 8601 string; ties broken by the smallest issue number"
        ),
        "lead_time_days": (
            "first_issue_time_github - first_report_time_protondb, in days (float); "
            "> 0 means ProtonDB appeared first, < 0 means GitHub appeared first"
        ),
        "lead_time_sign": (
            "'protondb_first': the two UTC calendar dates differ and ProtonDB is first; "
            "'same_day': the two UTC calendar dates are the same; "
            "'github_first': the two UTC calendar dates differ and GitHub is first"
        ),
    }

    # ── 6. Output the per-game temporal table ────────────────────────────────
    # Sorted by lead_time_days descending (the more ProtonDB leads, the higher)
    rows_sorted = sorted(rows, key=lambda r: r["lead_time_days"], reverse=True)

    games_output = {
        "step":        "step5_temporal_layering_games",
        "generated_at": generated_at,
        "time_window": time_window_meta,
        "input_paths": {
            "master_summary": str(STEP4_OUTPUT),
            "protondb_reports": str(PROTONDB_REPORTS_PATH),
            "github_chunks_dir": str(GITHUB_CHUNKS_DIR),
        },
        "definitions": definitions,
        "n_games": len(rows_sorted),
        "games": rows_sorted,
    }
    save_json(games_output, STEP5_GAMES_OUTPUT)
    print(f"  → Per-game temporal table saved to: {STEP5_GAMES_OUTPUT}")

    # ── 7. Output summary statistics ────────────────────────────────────────
    summary_output = {
        "step":        "step5_temporal_layering_summary",
        "generated_at": generated_at,
        "time_window": time_window_meta,
        "input_paths": {
            "master_summary": str(STEP4_OUTPUT),
            "protondb_reports": str(PROTONDB_REPORTS_PATH),
            "github_chunks_dir": str(GITHUB_CHUNKS_DIR),
        },
        "definitions": definitions,
        "summary": summary_stats,
    }
    save_json(summary_output, STEP5_SUMMARY_OUTPUT)
    print(f"  → Summary statistics saved to: {STEP5_SUMMARY_OUTPUT}")

    # ── 8. Outlier / spot-check output ──────────────────────────────────────
    spot_meta = {
        "generated_at": generated_at,
        "time_window":  time_window_meta,
    }

    # 8a. Top N where ProtonDB leads most (largest lead_time_days)
    top_pdb = [_extract_spot(r) for r in rows_sorted[:_OUTLIER_TOP_N]]
    save_json({**spot_meta,
               "description": f"Top {_OUTLIER_TOP_N} games by largest lead_time_days (ProtonDB leads most)",
               "n": len(top_pdb),
               "games": top_pdb},
              STEP5_TOP_PDB_OUTPUT)
    print(f"  → ProtonDB-leads-most sample saved to: {STEP5_TOP_PDB_OUTPUT}")

    # 8b. Top N where GitHub leads most (smallest, i.e. most negative, lead_time_days)
    top_gh = [_extract_spot(r) for r in rows_sorted[-_OUTLIER_TOP_N:]][::-1]
    save_json({**spot_meta,
               "description": f"Top {_OUTLIER_TOP_N} games by smallest lead_time_days (GitHub leads most)",
               "n": len(top_gh),
               "games": top_gh},
              STEP5_TOP_GH_OUTPUT)
    print(f"  → GitHub-leads-most sample saved to: {STEP5_TOP_GH_OUTPUT}")

    # 8c. Same-day sample (drawn in game_appid lexical order, deterministic)
    same_day_rows = [
        r for r in sorted(rows, key=lambda x: x["game_appid"])
        if r["lead_time_sign"] == "same_day"
    ][:_SAME_DAY_SAMPLE]
    save_json({**spot_meta,
               "description": f"Games with lead_time_sign='same_day' (up to {_SAME_DAY_SAMPLE}, sorted by appid)",
               "n": len(same_day_rows),
               "games": [_extract_spot(r) for r in same_day_rows]},
              STEP5_SAME_DAY_OUTPUT)
    print(f"  → Same-day sample saved to: {STEP5_SAME_DAY_OUTPUT}")

    return summary_output


if __name__ == "__main__":
    run()
