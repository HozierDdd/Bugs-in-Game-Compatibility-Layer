"""
Unit tests for datetime_utils.
Tests the time-window filtering logic and Unix timestamp conversion.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.datetime_utils import from_unix_timestamp, in_window


def test_in_window_inside():
    """A timestamp inside the window should return True."""
    start = datetime(2021, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    ts_in = 1640000000  # 2021-12-20
    assert in_window(from_unix_timestamp(ts_in), start, end) is True


def test_in_window_before():
    """A timestamp before the window should return False."""
    start = datetime(2021, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    ts_before = 1577836800  # 2020-01-01
    assert in_window(from_unix_timestamp(ts_before), start, end) is False


def test_in_window_after():
    """A timestamp after the window should return False."""
    start = datetime(2021, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    ts_after = 1767225600  # 2026-01-01
    assert in_window(from_unix_timestamp(ts_after), start, end) is False


def test_in_window_boundary():
    """The boundary value (window start point) should return True."""
    start = datetime(2021, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    ts_boundary = int(start.timestamp())
    assert in_window(from_unix_timestamp(ts_boundary), start, end) is True


if __name__ == "__main__":
    test_in_window_inside()
    print("  ✓ test_in_window_inside")
    test_in_window_before()
    print("  ✓ test_in_window_before")
    test_in_window_after()
    print("  ✓ test_in_window_after")
    test_in_window_boundary()
    print("  ✓ test_in_window_boundary")
    print("All datetime_utils tests passed.")
