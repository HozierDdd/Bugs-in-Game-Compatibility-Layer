"""
Step 4: Master summary table.

Merge the per-game ProtonDB metrics and per-game GitHub metrics into a single
wide table, one row per game_appid. Fields for a missing platform are set to null.
"""

from src.config import (
    STEP2_OUTPUT,
    STEP3_OUTPUT,
    STEP4_OUTPUT,
    TIME_WINDOW_START,
    TIME_WINDOW_END,
)
from src.utils.json_io import load_json, save_json
from src.utils.datetime_utils import now_utc_iso


def run() -> dict:
    print("[Step 4] Building master summary table...")

    # ── Load outputs from prior steps ────────────────────────────────────────
    step2 = load_json(STEP2_OUTPUT)
    step3 = load_json(STEP3_OUTPUT)

    # Build an appid -> game data lookup dict
    protondb_map: dict[str, dict] = {
        g["app_id"]: g for g in step2["games"]
    }
    github_map: dict[str, dict] = {
        g["app_id"]: g for g in step3["games"]
    }

    all_appids = sorted(set(protondb_map) | set(github_map))
    print(f"  ProtonDB games: {len(protondb_map)}")
    print(f"  GitHub games:   {len(github_map)}")
    print(f"  Unique appids after merge: {len(all_appids)}")

    rows = []
    for appid in all_appids:
        pdb = protondb_map.get(appid)
        ghb = github_map.get(appid)

        row = {
            "game_appid": appid,
            # ProtonDB fields
            "game_title_protondb": pdb["game_title"] if pdb else None,
            "n_reports_protondb": pdb["n_reports_protondb"] if pdb else None,
            "verdict_counts": pdb["verdict_counts"] if pdb else None,
            # GitHub fields
            "n_issues_github": ghb["n_issues_github"] if ghb else None,
            "n_reports_github": ghb["n_reports_github"] if ghb else None,
            "n_comments_github": ghb["n_comments_github"] if ghb else None,
            # Presence flags
            "present_in_protondb": pdb is not None,
            "present_in_github": ghb is not None,
        }
        rows.append(row)

    # Sort by ProtonDB report count, descending (missing treated as 0)
    rows.sort(key=lambda r: r["n_reports_protondb"] or 0, reverse=True)

    # Tally coverage
    both_count = sum(1 for r in rows if r["present_in_protondb"] and r["present_in_github"])
    only_pdb = sum(1 for r in rows if r["present_in_protondb"] and not r["present_in_github"])
    only_gh = sum(1 for r in rows if not r["present_in_protondb"] and r["present_in_github"])
    print(f"  In both platforms: {both_count} | ProtonDB only: {only_pdb} | GitHub only: {only_gh}")

    result = {
        "step": "step4_master_summary",
        "generated_at": now_utc_iso(),
        "time_window": {
            "start": TIME_WINDOW_START.isoformat(),
            "end": TIME_WINDOW_END.isoformat(),
        },
        "inputs": {
            "step2_protondb": str(STEP2_OUTPUT),
            "step3_github":   str(STEP3_OUTPUT),
        },
        "summary": {
            "total_unique_appids": len(all_appids),
            "n_in_both": both_count,
            "n_only_protondb": only_pdb,
            "n_only_github": only_gh,
        },
        "games": rows,
    }

    save_json(result, STEP4_OUTPUT)
    print(f"  → Master summary table saved to: {STEP4_OUTPUT}")
    return result


if __name__ == "__main__":
    run()
