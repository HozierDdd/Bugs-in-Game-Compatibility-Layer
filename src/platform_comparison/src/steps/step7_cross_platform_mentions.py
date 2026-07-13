"""
Step 7: cross-platform information-flow analysis — mutual mentions in post bodies.

Research questions:
  A) ProtonDB side: among the ProtonDB CRs for matched games, how many
     explicitly mention a link to the GitHub Proton issue tracker in the body
     (notes.extra / notes.verdict)?
  B) GitHub side: among the GitHub CRs identified within the time window
     (issue bodies and comments), how many explicitly mention ProtonDB (URL or name)?

Search patterns (all case-insensitive):
  A → B: github.com/ValveSoftware/Proton/issues/<number>
          (loose comparison: any github.com link)
  B → A: protondb.com (URL) / protondb (name included)

Scope:
  - ProtonDB side: step1 in_both appid set + records within the time window
  - GitHub side: three tiers — all issues / resolved-appid games / matched games
"""

import json
import re
from pathlib import Path

from src.config import (
    PROTONDB_REPORTS_PATH,
    GITHUB_CHUNKS_DIR,
    GITHUB_CHUNK_GLOB,
    STEP1_OUTPUT,
    STEP3_THREADS_OUTPUT,
    STEP7_OUTPUT,
    PROTONDB_TS_START,
    PROTONDB_TS_END,
    UNRESOLVED_APPID,
)
from src.parsers.compatibility_report_classifier import classify_post
from src.loaders.github_loader import count_github_chunks
from src.utils.json_io import load_json, save_json
from src.utils.datetime_utils import now_utc_iso

# ── Mention patterns (case-insensitive) ──────────────────────────────────────
# Part A: ProtonDB body → GitHub Proton issue tracker
_GH_ISSUE_URL = re.compile(
    r"github\.com/ValveSoftware/Proton/issues/\d+", re.IGNORECASE
)
_GH_ANY = re.compile(r"github\.com", re.IGNORECASE)

# Part B: GitHub CR body → ProtonDB (URL first, name as fallback)
_PDB_URL = re.compile(r"protondb\.com", re.IGNORECASE)
_PDB_ANY = re.compile(r"protondb", re.IGNORECASE)


def _pdb_notes_text(responses: dict) -> str:
    """Extract the free-text body of a ProtonDB report (notes.extra + notes.verdict)."""
    notes = responses.get("notes") or {}
    if not isinstance(notes, dict):
        return ""
    parts = [notes.get("extra") or "", notes.get("verdict") or ""]
    return " ".join(p for p in parts if isinstance(p, str))


def _pct(n: int, d: int) -> float:
    return round(n / d * 100, 2) if d else 0


# ── Part A: ProtonDB-side scan ───────────────────────────────────────────────

def scan_protondb(matched_appids: set[str]) -> dict:
    """
    Scan all ProtonDB reports and, among the CRs that belong to matched games
    and fall within the time window, compute the share that mention the GitHub
    Proton issue tracker.
    """
    print("[Step 7-A] Loading ProtonDB reports...")
    raw_data: list = load_json(PROTONDB_REPORTS_PATH)
    print(f"  Total raw records: {len(raw_data):,}")

    total = mention_strict = mention_github = 0

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

        total += 1
        text = _pdb_notes_text(rec.get("responses") or {})
        if not text:
            continue
        if _GH_ISSUE_URL.search(text):
            mention_strict += 1
        if _GH_ANY.search(text):
            mention_github += 1

    print(f"  Total CRs for matched games: {total:,}")
    print(f"  Mentioning Proton issue tracker URL: {mention_strict:,} ({_pct(mention_strict, total)}%)")
    print(f"  Mentioning any github.com:           {mention_github:,} ({_pct(mention_github, total)}%)")

    return {
        "total_cr": total,
        "mention_proton_issue_url": {
            "count": mention_strict,
            "pct": _pct(mention_strict, total),
            "pattern": "github.com/ValveSoftware/Proton/issues/<number> (case-insensitive)",
        },
        "mention_any_github": {
            "count": mention_github,
            "pct": _pct(mention_github, total),
            "pattern": "github.com (case-insensitive, any link)",
        },
    }


# ── Part B: GitHub CR-side scan ──────────────────────────────────────────────

def scan_github_crs(matched_appids: set[str]) -> dict:
    """
    Scan all GitHub chunks and, for every CR post (identified by classify_post),
    compute the share that mention ProtonDB. Reported over three scopes:
    all / resolved appid / matched games.

    The issue_number → appid mapping comes from step3_github_threads.json
    (avoids re-running AppID resolution).
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

    print(f"  Total issues in the time window: {len(all_numbers):,}")
    print(f"  Of which resolved appids: {len(appid_map):,}")

    # Counters: [all, resolved, matched] × [cr, url_hit, any_hit]
    counters = [[0, 0, 0] for _ in range(3)]  # 0=all, 1=resolved, 2=matched

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

            posts = [issue.get("body") or ""] + [
                c.get("body") or "" for c in (issue.get("comments_data") or [])
            ]
            for body in posts:
                if not classify_post(body)["is_compatibility_report"]:
                    continue
                url_hit = bool(_PDB_URL.search(body))
                any_hit = bool(_PDB_ANY.search(body))

                counters[0][0] += 1
                if url_hit: counters[0][1] += 1
                if any_hit: counters[0][2] += 1
                if is_resolved:
                    counters[1][0] += 1
                    if url_hit: counters[1][1] += 1
                    if any_hit: counters[1][2] += 1
                if is_matched:
                    counters[2][0] += 1
                    if url_hit: counters[2][1] += 1
                    if any_hit: counters[2][2] += 1

    labels = ["all step3", "resolved-appid games", f"matched {len(matched_appids)} games"]
    for label, (cr, url, any_) in zip(labels, counters):
        print(f"  [{label}] Total GitHub CRs: {cr:,}")
        print(f"    Mentioning protondb.com URL: {url:,} ({_pct(url, cr)}%)")
        print(f"    Mentioning ProtonDB (name included): {any_:,} ({_pct(any_, cr)}%)")

    def _scope(cr, url, any_):
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

    return {
        "scope_note": (
            "all_issues_in_window includes issue CRs with unresolved appids (aligned with the full step3); "
            "resolved_appid_games and matched_games_only are subsets of it."
        ),
        "all_issues_in_window":  _scope(*counters[0]),
        "resolved_appid_games":  _scope(*counters[1]),
        "matched_games_only":    _scope(*counters[2]),
    }


# ── Main entry point ──────────────────────────────────────────────────────────

def run() -> dict:
    print("[Step 7] Cross-platform information flow: mutual mentions in post bodies")
    print("=" * 60)

    step1 = load_json(STEP1_OUTPUT)
    matched_appids: set[str] = set(step1["in_both"])
    print(f"  Matched games (in_both): {len(matched_appids):,}")
    print(f"  GitHub chunk files: {count_github_chunks():,}")
    print()

    print("── Part A: ProtonDB CRs mentioning the GitHub Proton issue tracker ──")
    result_a = scan_protondb(matched_appids)
    print()

    print("── Part B: GitHub CRs mentioning ProtonDB ──")
    result_b = scan_github_crs(matched_appids)
    print()

    result = {
        "step": "step7_cross_platform_mentions",
        "generated_at": now_utc_iso(),
        "n_matched_games": len(matched_appids),
        "part_a_protondb_mentions_github": result_a,
        "part_b_github_cr_mentions_protondb": result_b,
    }

    save_json(result, STEP7_OUTPUT)
    print(f"[Step 7] Results saved to: {STEP7_OUTPUT}")
    return result


if __name__ == "__main__":
    run()
