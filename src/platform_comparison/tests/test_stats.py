"""
Unit tests for the stats utilities.
Tests the hand-implemented percentile calculation and distribution stats functions.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.stats import percentile, compute_distribution_stats


def test_percentile_median():
    """Median (p50) calculation."""
    data = [1, 2, 3, 4, 5]
    assert percentile(data, 50) == 3.0

    data_even = [1, 2, 3, 4]
    assert percentile(data_even, 50) == 2.5


def test_percentile_extremes():
    """Minimum (p0) and maximum (p100)."""
    data = [10, 20, 30, 40, 50]
    assert percentile(data, 0) == 10.0
    assert percentile(data, 100) == 50.0


def test_percentile_single_element():
    """Any percentile of a single-element list equals that element."""
    assert percentile([42], 25) == 42.0
    assert percentile([42], 75) == 42.0
    assert percentile([42], 50) == 42.0


def test_percentile_p90():
    """90th percentile."""
    data = list(range(1, 11))  # [1, 2, ..., 10]
    p90 = percentile(data, 90)
    # numpy default linear interpolation: rank = 0.9 * 9 = 8.1 -> 9 + 0.1*(10-9) = 9.1
    assert abs(p90 - 9.1) < 1e-9, f"got {p90}"


def test_percentile_empty():
    """An empty list returns 0.0."""
    assert percentile([], 50) == 0.0


def test_compute_distribution_stats_basic():
    """Basic distribution statistics."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    stats = compute_distribution_stats(data)
    assert stats["count"] == 10
    assert stats["median"] == 5.5
    assert stats["max"] == 10.0
    # IQR = Q3 - Q1
    assert stats["iqr"] is not None
    assert stats["p90"] is not None


def test_compute_distribution_stats_empty():
    """An empty list returns None values."""
    stats = compute_distribution_stats([])
    assert stats["count"] == 0
    assert stats["median"] is None
    assert stats["iqr"] is None
    assert stats["p90"] is None
    assert stats["max"] is None


if __name__ == "__main__":
    test_percentile_median()
    print("  ✓ test_percentile_median")
    test_percentile_extremes()
    print("  ✓ test_percentile_extremes")
    test_percentile_single_element()
    print("  ✓ test_percentile_single_element")
    test_percentile_p90()
    print("  ✓ test_percentile_p90")
    test_percentile_empty()
    print("  ✓ test_percentile_empty")
    test_compute_distribution_stats_basic()
    print("  ✓ test_compute_distribution_stats_basic")
    test_compute_distribution_stats_empty()
    print("  ✓ test_compute_distribution_stats_empty")
    print("All stats utility tests passed.")
