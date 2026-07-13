"""
Steam HTTP utility layer.

Provides two kinds of capability:
1. curl_fetch — fetches HTTPS via a curl subprocess, working around the
   SSL: CERTIFICATE_VERIFY_FAILED problem that some macOS Python installs hit
   due to missing root certificates (which affects urllib).
2. Steam Store API wrappers — fetch_appdetails_release fetches a single AppID's
   release date with built-in 429/503 exponential-backoff retries;
   parse_steam_release_date parses the returned date string.

This module is used only by the standalone scripts under scripts/; the pipeline
steps (step0-7) continue to reach the Steam API via the urllib path in
appid_validator.py.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import date
from typing import Any

# ── Public URL / documentation constants ──────────────────────────────────────

JSNLI_GAMES_URL = (
    "https://raw.githubusercontent.com/jsnli/steamappidlist/master/data/games_appid.json"
)
ISTORESERVICE_GETAPPLIST_URL = (
    "https://api.steampowered.com/IStoreService/GetAppList/v1/"
)
ISTORESERVICE_DOCS_URL = (
    "https://partner.steamgames.com/doc/webapi/IStoreService#GetAppList"
)

_STORE_APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"

# The Steam store endpoint triggers 429 more readily for non-browser UAs; use a common desktop browser UA to reduce throttling.
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_TOOL_UA = "ProtonDB-Analyzer/1.0"

# ── curl wrapper ──────────────────────────────────────────────────────────────

def curl_fetch(
    url: str,
    *,
    timeout_sec: int = 120,
    user_agent: str = _TOOL_UA,
) -> bytes:
    """Fetch a URL via curl and return the raw response bytes.

    Args:
        url:         Target URL.
        timeout_sec: curl -m timeout in seconds.
        user_agent:  User-Agent header; GitHub and the Steam store endpoint
                     suit different values, passed in by the caller as needed
                     (defaults to the tool UA).

    Raises:
        RuntimeError: curl process exited with a non-zero code.
    """
    proc = subprocess.run(
        ["curl", "-sS", "--compressed", "-m", str(timeout_sec), "-A", user_agent, url],
        check=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace")[:800])
    return proc.stdout


# ── Steam release-date parsing ────────────────────────────────────────────────

_RE_EU = re.compile(r"^(\d{1,2}) ([A-Za-z]{3}), (\d{4})$")
_RE_US = re.compile(r"^([A-Za-z]{3}) (\d{1,2}), (\d{4})$")
_RE_YEAR = re.compile(r"^(\d{4})$")
_RE_QUARTER = re.compile(r"^Q([1-4]) (\d{4})$", re.IGNORECASE)
_MONTH = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,  "May": 5,  "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
_SKIP = frozenset({"coming soon", "to be announced", "tbd", "tba"})


def parse_steam_release_date(s: str) -> date | None:
    """Parse the common formats of Steam appdetails release_date.date, returning a date or None.

    Supports:
    - European: ``9 Dec, 2020``
    - US:       ``Mar 28, 2023``
    - Year only: ``2024`` → Jan 1 of that year (conservative choice)
    - Quarter:   ``Q4 2024`` → first day of the quarter (Oct 1)
    """
    s = (s or "").strip()
    if not s or s.lower() in _SKIP:
        return None

    m = _RE_EU.match(s)
    if m:
        month = _MONTH.get(m.group(2))
        return date(int(m.group(3)), month, int(m.group(1))) if month else None

    m = _RE_US.match(s)
    if m:
        month = _MONTH.get(m.group(1))
        return date(int(m.group(3)), month, int(m.group(2))) if month else None

    m = _RE_YEAR.match(s)
    if m:
        return date(int(m.group(1)), 1, 1)

    m = _RE_QUARTER.match(s)
    if m:
        q_start = {1: 1, 2: 4, 3: 7, 4: 10}[int(m.group(1))]
        return date(int(m.group(2)), q_start, 1)

    return None


# ── appdetails release-date fetching ──────────────────────────────────────────

def fetch_appdetails_release(
    appid: int,
    *,
    retries: int = 10,
) -> tuple[int, bool, bool, str | None]:
    """Fetch a single AppID's release_date info, with built-in throttle backoff and retries.

    Returns:
        (http_code, store_success, coming_soon, date_display)

        - ``http_code``:     HTTP status code; 0 when curl fails or parsing errors.
        - ``store_success``: Steam side ``success=true`` and a release_date field is present.
        - ``coming_soon``:   ``release_date.coming_soon``; conservatively True when unknown.
        - ``date_display``:  Steam's raw date string, e.g. ``"19 Jul, 2024"``;
                             None when the AppID doesn't exist or has no date field.

    Note:
        The Steam store endpoint only supports single-AppID queries (multiple IDs return HTTP 400).
        On 429, retries automatically with exponential backoff (30 → 60 → 120 … up to 300s);
        on 403 / 503, waits a fixed 30s before each retry; any other non-200 status returns directly.
    """
    url = f"{_STORE_APPDETAILS_URL}?appids={appid}&filters=release_date&l=english&cc=us"
    backoff = 30.0

    for _ in range(retries):
        proc = subprocess.run(
            ["curl", "-sS", "--compressed", "-m", "45", "-w", "%{http_code}",
             "-A", _BROWSER_UA, url],
            check=False,
            capture_output=True,
        )
        if proc.returncode != 0:
            return 0, False, True, None

        text = proc.stdout.decode("utf-8", "replace")
        if len(text) < 3:
            return 0, False, True, None

        try:
            http_code = int(text[-3:])
        except ValueError:
            return 0, False, True, None

        body = text[:-3].strip()

        if http_code == 429:
            time.sleep(backoff)
            backoff = min(300.0, backoff * 2)
            continue

        if http_code in (403, 503):
            time.sleep(30.0)
            continue

        if http_code != 200 or not body or body == "null":
            return http_code, False, True, None

        data: Any = json.loads(body)
        entry = data.get(str(appid))
        if not entry or not entry.get("success"):
            return http_code, False, True, None

        rd = (entry.get("data") or {}).get("release_date") or {}
        coming = bool(rd.get("coming_soon", False))
        disp = rd.get("date")
        return http_code, True, coming, disp if isinstance(disp, str) else None

    return 429, False, True, None  # retries exhausted
