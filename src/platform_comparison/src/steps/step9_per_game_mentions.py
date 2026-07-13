"""
Step 9: per-game (appid) cross-platform mutual-mention analysis.

Building on the overall Step 7 counts, this drills down to each matched game:
  A) ProtonDB side: how many of each game's CRs mention the GitHub Proton issue tracker
  B) GitHub side: how many of each game's **all posts** (CRs + discussion comments)
     within the time window mention ProtonDB
     ← Difference from Step 7: on the GitHub side the scope extends to discussion
       comments, not just CRs

Core metric: mentions / game (per-game mention counts, plus aggregate avg / distribution stats)

Output contains:
  - Per-matched-game details (`games` array, sorted by total mentions descending)
  - Summary statistics (`summary`: totals, means, distribution)
"""

import json
from pathlib import Path

from src.config import (
    PROTONDB_REPORTS_PATH,
    GITHUB_CHUNKS_DIR,
    GITHUB_CHUNK_GLOB,
    STEP1_OUTPUT,
    STEP3_THREADS_OUTPUT,
    STEP9_OUTPUT,
    PROTONDB_TS_START,
    PROTONDB_TS_END,
    UNRESOLVED_APPID,
    STATS_ROUND_DIGITS,
)
# Reuse step7's regex patterns and helpers so all three steps share the same search logic
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
from src.utils.datetime_utils import now_utc_iso
from src.utils.stats import compute_distribution_stats


# ── Part A: ProtonDB-side per-game scan ──────────────────────────────────────

def scan_protondb_per_game(matched_appids: set[str]) -> dict:
    """
    Scan all ProtonDB reports and, per game (appid), count CRs and how many of
    them mention GitHub.

    The search logic is identical to scan_protondb() (Step 7); the only
    difference is bucketing per game instead of aggregating. Only games in
    matched_appids and records within the time window are counted.

    Returns:
        {
            "summary": { n_games, total_crs, total_mention_*, avg_*_per_game,
                         distribution_* },
            "games":   [ { app_id, n_crs, n_mention_proton_issue_url,
                           n_mention_any_github }, ... ]  ← sorted by n_mention_any_github desc
        }
    """
    print("[Step 9-A] Loading ProtonDB reports...")
    raw_data: list = load_json(PROTONDB_REPORTS_PATH)
    print(f"  Total raw records: {len(raw_data):,}")

    # buckets[appid] = [n_crs, n_strict, n_any]
    buckets: dict[str, list[int]] = {a: [0, 0, 0] for a in matched_appids}

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

        b = buckets[app_id]
        b[0] += 1
        text = _pdb_notes_text(rec.get("responses") or {})
        if text:
            if _GH_ISSUE_URL.search(text):
                b[1] += 1
            if _GH_ANY.search(text):
                b[2] += 1

    games = sorted(
        [
            {
                "app_id": a,
                "n_crs": buckets[a][0],
                "n_mention_proton_issue_url": buckets[a][1],
                "n_mention_any_github": buckets[a][2],
            }
            for a in matched_appids
        ],
        key=lambda g: g["n_mention_any_github"],
        reverse=True,
    )

    n = len(games)
    total_crs    = sum(g["n_crs"]                    for g in games)
    total_strict = sum(g["n_mention_proton_issue_url"] for g in games)
    total_any    = sum(g["n_mention_any_github"]       for g in games)

    print(f"  Matched games: {n:,}  total CRs: {total_crs:,}")
    print(f"  Total Proton issue URL mentions: {total_strict:,}  "
          f"mean/game: {round(total_strict/n, 4) if n else 0}")
    print(f"  Total any-github.com mentions:   {total_any:,}  "
          f"mean/game: {round(total_any/n, 4) if n else 0}")

    return {
        "summary": {
            "n_games": n,
            "total_crs": total_crs,
            "total_mention_proton_issue_url": total_strict,
            "total_mention_any_github": total_any,
            "avg_mention_proton_issue_url_per_game": round(total_strict / n, 4) if n else 0,
            "avg_mention_any_github_per_game": round(total_any / n, 4) if n else 0,
            "pct_mention_proton_issue_url": _pct(total_strict, total_crs),
            "pct_mention_any_github": _pct(total_any, total_crs),
            "distribution_mention_proton_issue_url": compute_distribution_stats(
                [g["n_mention_proton_issue_url"] for g in games], STATS_ROUND_DIGITS
            ),
            "distribution_mention_any_github": compute_distribution_stats(
                [g["n_mention_any_github"] for g in games], STATS_ROUND_DIGITS
            ),
        },
        "games": games,
    }


# ── Part B: GitHub-side per-game scan (all posts, incl. discussion comments) ──

def scan_github_posts_per_game(matched_appids: set[str]) -> dict:
    """
    Scan all GitHub chunks and, per game (appid), count how many of **all posts**
    (issue body + comments, whether or not they are CRs) within the time window
    mention ProtonDB.

    Difference from scan_github_crs() (Step 7):
      - Step 7 only scans posts classified as CRs (classify_post True)
      - This function scans **every post** under a matched game's issues (CRs + discussion comments)

    The search patterns are identical to Step 7 (_PDB_URL / _PDB_ANY).

    Returns:
        {
            "summary": { n_games, total_posts, total_posts_cr,
                         total_posts_discussion, total_mention_*,
                         avg_*_per_game, distribution_* },
            "games":   [ { app_id, n_posts_total, n_posts_cr, n_posts_discussion,
                           n_mention_protondb_url, n_mention_protondb_any },
                         ... ]  ← sorted by n_mention_protondb_any desc
        }
    """
    print("  Loading step3_github_threads.json for the issue→appid mapping...")
    threads: list[dict] = load_json(STEP3_THREADS_OUTPUT).get("threads", [])

    # Keep only matched-game issue mappings (excludes unresolved and non-matched games)
    appid_map: dict[int, str] = {}
    for t in threads:
        num = t.get("issue_number")
        if num is None:
            continue
        appid = t.get("resolved_appid")
        if appid and appid != UNRESOLVED_APPID and appid in matched_appids:
            appid_map[num] = appid

    print(f"  Matched-game issues: {len(appid_map):,}")

    # buckets[appid] = [n_posts_total, n_posts_cr, n_mention_url, n_mention_any]
    buckets: dict[str, list[int]] = {a: [0, 0, 0, 0] for a in matched_appids}

    chunk_files = sorted(Path(GITHUB_CHUNKS_DIR).glob(GITHUB_CHUNK_GLOB))
    for chunk_path in chunk_files:
        with open(chunk_path, encoding="utf-8") as f:
            chunk = json.load(f)

        for issue in (chunk.get("issues") or []):
            number = issue.get("number")
            if number not in appid_map:
                continue

            b = buckets[appid_map[number]]

            # issue body + all comments (whether or not they are CRs)
            posts = [issue.get("body") or ""]
            posts += [c.get("body") or "" for c in (issue.get("comments_data") or [])]

            for body in posts:
                b[0] += 1  # total posts
                if classify_post(body)["is_compatibility_report"]:
                    b[1] += 1  # CR posts
                if _PDB_URL.search(body):
                    b[2] += 1
                if _PDB_ANY.search(body):
                    b[3] += 1

    games = sorted(
        [
            {
                "app_id": a,
                "n_posts_total": buckets[a][0],
                "n_posts_cr": buckets[a][1],
                "n_posts_discussion": buckets[a][0] - buckets[a][1],
                "n_mention_protondb_url": buckets[a][2],
                "n_mention_protondb_any": buckets[a][3],
            }
            for a in matched_appids
        ],
        key=lambda g: g["n_mention_protondb_any"],
        reverse=True,
    )

    n = len(games)
    total_posts  = sum(g["n_posts_total"]        for g in games)
    total_cr     = sum(g["n_posts_cr"]           for g in games)
    total_disc   = sum(g["n_posts_discussion"]   for g in games)
    total_url    = sum(g["n_mention_protondb_url"] for g in games)
    total_any    = sum(g["n_mention_protondb_any"] for g in games)

    print(f"  Matched games: {n:,}  total posts: {total_posts:,}  "
          f"(CR {total_cr:,} + discussion {total_disc:,})")
    print(f"  Total protondb.com URL mentions: {total_url:,}  "
          f"mean/game: {round(total_url/n, 4) if n else 0}")
    print(f"  Total protondb (name included) mentions: {total_any:,}  "
          f"mean/game: {round(total_any/n, 4) if n else 0}")

    return {
        "summary": {
            "n_games": n,
            "total_posts": total_posts,
            "total_posts_cr": total_cr,
            "total_posts_discussion": total_disc,
            "total_mention_protondb_url": total_url,
            "total_mention_protondb_any": total_any,
            "avg_mention_protondb_url_per_game": round(total_url / n, 4) if n else 0,
            "avg_mention_protondb_any_per_game": round(total_any / n, 4) if n else 0,
            "pct_mention_protondb_url": _pct(total_url, total_posts),
            "pct_mention_protondb_any": _pct(total_any, total_posts),
            "distribution_mention_protondb_url": compute_distribution_stats(
                [g["n_mention_protondb_url"] for g in games], STATS_ROUND_DIGITS
            ),
            "distribution_mention_protondb_any": compute_distribution_stats(
                [g["n_mention_protondb_any"] for g in games], STATS_ROUND_DIGITS
            ),
        },
        "games": games,
    }


# ── Main entry point ──────────────────────────────────────────────────────────

def run() -> dict:
    print("[Step 9] Per-game cross-platform mutual-mention analysis")
    print("=" * 60)

    step1 = load_json(STEP1_OUTPUT)
    matched_appids: set[str] = set(step1["in_both"])
    print(f"  Matched games (in_both): {len(matched_appids):,}")
    print()

    print("── Part A: ProtonDB CRs per game mentioning the GitHub Proton issue tracker ──")
    result_a = scan_protondb_per_game(matched_appids)
    print()

    print("── Part B: all GitHub posts (CRs + discussion) per game mentioning ProtonDB ──")
    result_b = scan_github_posts_per_game(matched_appids)
    print()

    result = {
        "step": "step9_per_game_mentions",
        "generated_at": now_utc_iso(),
        "n_matched_games": len(matched_appids),
        "note": (
            "Part A counts ProtonDB CR bodies only; "
            "Part B counts all GitHub posts (issue body + all comments, including discussion comments), "
            "not limited to CRs, scoped to matched games' issues within the time window."
        ),
        "part_a_protondb_per_game": result_a,
        "part_b_github_per_game": result_b,
    }

    save_json(result, STEP9_OUTPUT)
    print(f"[Step 9] Results saved to: {STEP9_OUTPUT}")
    return result


if __name__ == "__main__":
    run()
