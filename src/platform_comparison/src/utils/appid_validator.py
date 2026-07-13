"""
Two-phase Steam AppID validation utility.

Phase 1 — Compare against the local cache of jsnli/steamappidlist (Steam's current
          catalog, covering games/DLC/software); a hit means valid_current_*.

Phase 2 — For anything Phase 1 missed, call the Steam appdetails API one by one;
          success=true means valid_legacy (a Legacy version, or a delisted game
          the API can still resolve).

Caching strategy:
    The Steam AppID list (~220k entries) is written to a local JSON file and
    auto-refreshed after ttl_days days.
    A cold start downloads in about 3-5s; later calls read the local file and respond in milliseconds.
"""

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Data sources ──────────────────────────────────────────────────────────────

_APPLIST_BASE = "https://raw.githubusercontent.com/jsnli/steamappidlist/master/data"
_CAT_LABELS = {"games": "game", "dlc": "dlc", "software": "software"}
_APPDETAILS_URL = "https://store.steampowered.com/api/appdetails?appids={appid}"


def _fetch_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "ProtonDB-Analyzer/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── Phase 1: local cache lookup ───────────────────────────────────────────────

def build_steam_appid_map(cache_path: Path, *, ttl_days: int = 7) -> dict[str, str]:
    """
    Return a {appid_str: category} dict (category ∈ {"game", "dlc", "software"}).

    On the first call (or when the cache is older than ttl_days), downloads the
    latest snapshot from GitHub and writes it to the cache;
    afterwards it reads the local file directly.
    """
    if _cache_is_fresh(cache_path, ttl_days):
        return json.loads(cache_path.read_text(encoding="utf-8"))["categories"]

    print("  [AppID Validator] Downloading the Steam AppID list from GitHub...", flush=True)
    categories: dict[str, str] = {}
    for cat, label in _CAT_LABELS.items():
        entries = _fetch_json(f"{_APPLIST_BASE}/{cat}_appid.json")
        for entry in entries:
            categories[str(entry["appid"])] = label
        print(f"    {cat}: {len(entries)} entries", flush=True)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {"generated_at": datetime.now(timezone.utc).isoformat(), "categories": categories},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return categories


def _cache_is_fresh(path: Path, ttl_days: int) -> bool:
    if not path.exists():
        return False
    age_seconds = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
    return age_seconds < ttl_days * 86400


# ── Phase 2: appdetails API confirmation ──────────────────────────────────────

def verify_via_appdetails(appids: list[str], *, request_delay: float = 1.5) -> dict[str, bool]:
    """
    Call the Steam appdetails API for each AppID in the list, returning {appid: is_confirmed}.

    is_confirmed=True means the AppID exists in Steam's database
    (possibly a Legacy version, or a delisted entry not yet purged from the records).
    Network errors are treated as False (unable to confirm).

    request_delay defaults to 1.5s, in line with Steam's rate limit of roughly 200 calls / 5 min.
    """
    results: dict[str, bool] = {}
    for i, appid in enumerate(appids):
        if i > 0:
            time.sleep(request_delay)
        try:
            data = _fetch_json(_APPDETAILS_URL.format(appid=appid))
            results[appid] = bool(data.get(appid, {}).get("success", False))
        except Exception:
            results[appid] = False
    return results
