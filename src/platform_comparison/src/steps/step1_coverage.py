"""
Step 1: Platform coverage analysis.

Within a shared time window, compare which games (keyed by appid) ProtonDB and
GitHub each cover, and compute three sets: ProtonDB-only, in both, GitHub-only.
"""

from src.config import (
    PROTONDB_REPORTS_PATH,
    GITHUB_CHUNKS_DIR,
    GITHUB_CHUNK_GLOB,
    STEP1_OUTPUT,
    TIME_WINDOW_START,
    TIME_WINDOW_END,
    UNRESOLVED_APPID,
)
from src.loaders.protondb_loader import load_protondb_records
from src.loaders.github_loader import iter_github_issues, count_github_chunks
from src.parsers.appid_extractor import extract_appid
from src.utils.json_io import save_json
from src.utils.datetime_utils import now_utc_iso


def run() -> dict:
    print("[Step 1] Platform coverage analysis...")

    # ── ProtonDB ────────────────────────────────────────────────────────────
    print(f"  Loading ProtonDB data...")
    records, total_raw, filtered = load_protondb_records()
    protondb_appids: set[str] = {r["app_id"] for r in records}
    print(f"  ProtonDB: {total_raw} raw → {len(records)} in time window "
          f"(excluded {filtered}) → {len(protondb_appids)} games covered")

    # ── GitHub ──────────────────────────────────────────────────────────────
    n_chunks = count_github_chunks()
    print(f"  Scanning GitHub chunks ({n_chunks} files)...")
    github_appids: set[str] = set()
    github_total_issues = 0
    github_unresolved = 0

    for issue in iter_github_issues():
        github_total_issues += 1
        appid, _ = extract_appid(issue["title"], issue["body"])
        if appid == UNRESOLVED_APPID:
            github_unresolved += 1
        else:
            github_appids.add(appid)

    print(f"  GitHub: {github_total_issues} issues in time window "
          f"→ {len(github_appids)} appids resolved "
          f"({github_unresolved} unresolvable)")

    # ── Set operations ───────────────────────────────────────────────────────
    only_protondb = sorted(protondb_appids - github_appids)
    in_both = sorted(protondb_appids & github_appids)
    only_github = sorted(github_appids - protondb_appids)

    print(f"  ProtonDB only: {len(only_protondb)} games")
    print(f"  In both:       {len(in_both)} games")
    print(f"  GitHub only:   {len(only_github)} games")

    result = {
        "step": "step1_coverage",
        "generated_at": now_utc_iso(),
        "time_window": {
            "start": TIME_WINDOW_START.isoformat(),
            "end": TIME_WINDOW_END.isoformat(),
        },
        "protondb_input": str(PROTONDB_REPORTS_PATH),
        "github_chunks_dir": str(GITHUB_CHUNKS_DIR),
        "github_chunk_glob": GITHUB_CHUNK_GLOB,
        "summary": {
            "N_games_ProtonDB": len(protondb_appids),
            "N_games_GitHub": len(github_appids),
            "N_only_protondb": len(only_protondb),
            "N_both": len(in_both),
            "N_only_github": len(only_github),
            "N_github_unresolved_issues": github_unresolved,
            "N_github_total_issues_in_window": github_total_issues,
        },
        "only_in_protondb": only_protondb,
        "in_both": in_both,
        "only_in_github": only_github,
    }

    save_json(result, STEP1_OUTPUT)
    print(f"  → Results saved to: {STEP1_OUTPUT}")
    return result


if __name__ == "__main__":
    run()
