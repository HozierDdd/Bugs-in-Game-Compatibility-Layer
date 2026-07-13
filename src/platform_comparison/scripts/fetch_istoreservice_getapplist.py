#!/usr/bin/env python3
"""
Download the Steam store "games" catalog to a local JSON file.

API docs: https://partner.steamgames.com/doc/webapi/IStoreService#GetAppList

Two run modes:

  --mirror (no key needed)
      Download the games_appid.json mirror from jsnli/steamappidlist.
      This community repo syncs daily from the official IStoreService/GetAppList,
      with fields matching the official game entries (appid / name / last_modified / price_change_number).

  default mode (requires --key or the STEAM_WEB_API_KEY environment variable)
      Connect directly to the Valve API and page through all live data by last_appid.

Usage:
  # Official API (key required)
  STEAM_WEB_API_KEY=<key> python3 scripts/fetch_istoreservice_getapplist.py

  # Mirror, no key
  python3 scripts/fetch_istoreservice_getapplist.py --mirror

Requirements: Python 3.9+ standard library; curl must be available on the system.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

# This script lives in scripts/, so add the project root to sys.path to import src.*
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.json_io import save_json  # noqa: E402
from src.utils.steam_http import (  # noqa: E402
    ISTORESERVICE_DOCS_URL,
    ISTORESERVICE_GETAPPLIST_URL,
    JSNLI_GAMES_URL,
    curl_fetch,
)

_PAGE_MAX = 50_000


def _fetch_mirror() -> list[dict[str, Any]]:
    raw = curl_fetch(JSNLI_GAMES_URL, timeout_sec=600)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, list):
        raise RuntimeError(f"mirror JSON is not a list (got {type(data).__name__})")
    return data


def _fetch_official(
    key: str,
    *,
    max_results: int,
    include_dlc: bool,
    include_software: bool,
    include_videos: bool,
    include_hardware: bool,
) -> list[dict[str, Any]]:
    max_results = max(1, min(_PAGE_MAX, max_results))
    last_appid = 0
    apps: list[dict[str, Any]] = []

    while True:
        params = {
            "key": key,
            "max_results": max_results,
            "last_appid": last_appid,
            "include_games": 1,
            "include_dlc": int(include_dlc),
            "include_software": int(include_software),
            "include_videos": int(include_videos),
            "include_hardware": int(include_hardware),
        }
        raw = curl_fetch(
            f"{ISTORESERVICE_GETAPPLIST_URL}?{urlencode(params)}",
            timeout_sec=120,
        )
        text = raw.decode("utf-8", "replace").strip()
        if not text or text.startswith("<"):
            raise RuntimeError(f"unexpected API response: {text[:200]!r}")

        resp = json.loads(text).get("response", {})
        page: list[dict[str, Any]] = resp.get("apps") or []
        if not page:
            break

        apps.extend(page)
        last_appid = int(page[-1]["appid"])

        have_more = resp.get("have_more")
        if have_more is False or (have_more is None and len(page) < max_results):
            break

    return apps


def main() -> int:
    p = argparse.ArgumentParser(
        description="Download the Steam IStoreService/GetAppList game catalog and write it to JSON."
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/steam/istoreservice_getapplist_games.json"),
        help="Output JSON path (relative to the project root, or absolute)",
    )
    p.add_argument(
        "--key",
        default=os.environ.get("STEAM_WEB_API_KEY", ""),
        help="Steam Web API key (defaults to the STEAM_WEB_API_KEY environment variable)",
    )
    p.add_argument(
        "--mirror",
        action="store_true",
        help="Download a mirror snapshot from jsnli/steamappidlist, no key needed",
    )
    p.add_argument(
        "--max-results",
        type=int,
        default=_PAGE_MAX,
        help="Official API max_results per page (up to 50000)",
    )
    p.add_argument("--include-dlc", action="store_true", help="Official API: include DLC")
    p.add_argument("--include-software", action="store_true", help="Official API: include software")
    p.add_argument("--include-videos", action="store_true", help="Official API: include videos")
    p.add_argument("--include-hardware", action="store_true", help="Official API: include hardware")
    args = p.parse_args()

    root = Path(__file__).resolve().parents[1]
    out_path = args.output if args.output.is_absolute() else root / args.output

    if args.mirror:
        apps = _fetch_mirror()
        meta: dict[str, Any] = {
            "documentation": ISTORESERVICE_DOCS_URL,
            "api_endpoint": ISTORESERVICE_GETAPPLIST_URL,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "retrieval": "jsnli_github_raw_mirror",
            "mirror_url": JSNLI_GAMES_URL,
            "entry_count": len(apps),
            "note": (
                "Mirror snapshot for when no STEAM_WEB_API_KEY is available. "
                "Fields match the official GetAppList game entries; "
                "use --key to hit the official API directly for live data."
            ),
        }
    else:
        key = (args.key or "").strip()
        if not key:
            print(
                "Error: no Steam Web API key provided.\n"
                "  Set the environment variable and run:\n"
                "    STEAM_WEB_API_KEY=<key> python3 scripts/fetch_istoreservice_getapplist.py\n"
                "  Or use mirror mode (no key needed):\n"
                "    python3 scripts/fetch_istoreservice_getapplist.py --mirror",
                file=sys.stderr,
            )
            return 2

        apps = _fetch_official(
            key,
            max_results=args.max_results,
            include_dlc=args.include_dlc,
            include_software=args.include_software,
            include_videos=args.include_videos,
            include_hardware=args.include_hardware,
        )
        meta = {
            "documentation": ISTORESERVICE_DOCS_URL,
            "api_endpoint": ISTORESERVICE_GETAPPLIST_URL,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "retrieval": "official_api",
            "entry_count": len(apps),
            "filters": {
                "include_games": True,
                "include_dlc": args.include_dlc,
                "include_software": args.include_software,
                "include_videos": args.include_videos,
                "include_hardware": args.include_hardware,
                "max_results_per_page": max(1, min(_PAGE_MAX, args.max_results)),
            },
        }

    save_json({"meta": meta, "apps": apps}, out_path)
    print(f"[ok] wrote {out_path} ({meta['entry_count']} apps)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
