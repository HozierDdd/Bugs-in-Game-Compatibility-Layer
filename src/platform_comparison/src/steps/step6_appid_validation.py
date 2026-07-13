"""
Step 6: two-phase GitHub AppID validation.

Reads the step3 output (game list with resolved AppIDs) and, for every AppID:
  Phase 1 — compare against the current Steam catalog snapshot
             (jsnli/steamappidlist, updated daily)
  Phase 2 — for Phase 1 misses, call the Steam appdetails API to catch
             Legacy and delisted games

Validation status
─────────────────
  verified   — Phase 1 or Phase 2 confirmed the AppID really exists in Steam's database
  unverified — neither phase matched; cannot auto-confirm, needs manual review

Note: unverified does not mean the AppID is invalid. Fully delisted games,
    SDK/tool builds, demos, and mis-extracted entries produced by rule 3 may all
    fail to match in either phase.
"""

from src.config import (
    STEP3_OUTPUT,
    STEP6_OUTPUT,
    STEAM_APPLIST_CACHE_PATH,
    STEAM_APPLIST_CACHE_TTL_DAYS,
    APPDETAILS_REQUEST_DELAY,
)
from src.utils.appid_validator import build_steam_appid_map, verify_via_appdetails
from src.utils.json_io import load_json, save_json
from src.utils.datetime_utils import now_utc_iso


def run() -> dict:
    print("[Step 6] Two-phase GitHub AppID validation...")

    games = load_json(STEP3_OUTPUT)["games"]
    total = len(games)
    print(f"  Step 3 input games: {total}")

    # ── Phase 1: whitelist lookup against the current Steam catalog ───────────
    appid_map = build_steam_appid_map(
        STEAM_APPLIST_CACHE_PATH, ttl_days=STEAM_APPLIST_CACHE_TTL_DAYS
    )
    phase1_hits: set[str] = set()
    phase1_miss: list[str] = []

    for g in games:
        aid = str(g["app_id"])
        if aid in appid_map:
            phase1_hits.add(aid)
        else:
            phase1_miss.append(aid)

    print(f"  Phase 1 hits: {len(phase1_hits)} / {total} ({len(phase1_hits) / total * 100:.1f}%)")
    print(f"  Phase 1 misses: {len(phase1_miss)}, moving to Phase 2...")

    # ── Phase 2: appdetails API re-confirmation (all misses, no pre-filter) ───
    est_sec = len(phase1_miss) * APPDETAILS_REQUEST_DELAY
    print(f"  Calling Steam appdetails API ({len(phase1_miss)} items, ~{est_sec:.0f}s)...")
    phase2 = verify_via_appdetails(phase1_miss, request_delay=APPDETAILS_REQUEST_DELAY)

    # ── Classification: verified / unverified ────────────────────────────────
    records: list[dict] = []
    n_verified = 0

    for g in games:
        aid = str(g["app_id"])
        is_verified = aid in phase1_hits or phase2.get(aid, False)
        n_verified += is_verified
        records.append({
            "app_id": aid,
            "game_title_github": g.get("game_title_github", ""),
            "validation_status": "verified" if is_verified else "unverified",
        })

    n_unverified = total - n_verified
    print(f"\n  Validation summary:")
    print(f"    ✅ verified:   {n_verified} ({n_verified / total * 100:.1f}%)")
    print(f"    ❓ unverified: {n_unverified} ({n_unverified / total * 100:.1f}%)")

    result = {
        "step": "step6_appid_validation",
        "generated_at": now_utc_iso(),
        "summary": {
            "total_games": total,
            "counts": {"verified": n_verified, "unverified": n_unverified},
        },
        "games": records,
    }
    save_json(result, STEP6_OUTPUT)
    print(f"\n  → Results saved to: {STEP6_OUTPUT}")
    return result


if __name__ == "__main__":
    run()
