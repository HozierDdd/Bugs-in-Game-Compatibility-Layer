"""
Date/time utilities.
Uniformly handles both ProtonDB Unix timestamps and GitHub ISO 8601 strings.
"""

from datetime import datetime, timezone


def from_unix_timestamp(ts: int | float) -> datetime:
    """
    Convert a Unix second-level timestamp to a UTC-aware datetime.
    ProtonDB's timestamp field is an integer number of seconds.
    """
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def from_iso8601(s: str) -> datetime:
    """
    Convert a GitHub ISO 8601 string (e.g. '2021-03-15T10:22:00Z') to a UTC-aware datetime.
    Python 3.11+ supports fromisoformat directly; this stays compatible with 3.9+.
    """
    # GitHub always uses the Z suffix; replace with +00:00 for older Python compatibility.
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def in_window(dt: datetime, start: datetime, end: datetime) -> bool:
    """Return whether datetime falls within the closed interval [start, end]."""
    return start <= dt <= end


def thread_median_in_window(
    raw_issue: dict,
    start: datetime,
    end: datetime,
) -> bool:
    """
    Determine whether the median timestamp of all posts in an issue thread lies in [start, end].

    Post set = the issue body (created_at) + each comment in comments_data (created_at).
    The median uses standard linear interpolation: an odd count takes the middle value,
    an even count takes the mean of the two middle values.

    Typically called only when issue.created_at is outside the window, to avoid needless work.
    Returns False if created_at cannot be parsed.
    """
    created_str = raw_issue.get("created_at")
    if not created_str:
        return False
    try:
        ts0 = from_iso8601(created_str).timestamp()
    except ValueError:
        return False

    all_ts = [ts0]
    for comment in (raw_issue.get("comments_data") or []):
        c_str = comment.get("created_at")
        if c_str:
            try:
                all_ts.append(from_iso8601(c_str).timestamp())
            except ValueError:
                pass

    all_ts.sort()
    n = len(all_ts)
    median_ts = all_ts[n // 2] if n % 2 == 1 else (all_ts[n // 2 - 1] + all_ts[n // 2]) / 2

    return in_window(datetime.fromtimestamp(median_ts, tz=timezone.utc), start, end)


def now_utc_iso() -> str:
    """Return the current UTC time as an ISO 8601 string, used for output file generation timestamps."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
