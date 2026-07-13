"""
Statistics utilities.
Uses only the standard library; percentiles are implemented by hand.
"""

import math
from typing import Sequence


def percentile(data: Sequence[float | int], p: float) -> float:
    """
    Compute a percentile (linear interpolation, matching numpy percentile's default method).
    p ranges over [0, 100].
    """
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return float(sorted_data[0])
    # Map the percentile to an index.
    rank = p / 100 * (n - 1)
    lower = int(math.floor(rank))
    upper = int(math.ceil(rank))
    if lower == upper:
        return float(sorted_data[lower])
    # Linear interpolation.
    fraction = rank - lower
    return float(sorted_data[lower] * (1 - fraction) + sorted_data[upper] * fraction)


def compute_distribution_stats(values: list[int | float], round_digits: int = 1) -> dict:
    """
    Compute distribution stats for a set of values: median, IQR, 90th percentile, max.
    All returned fields are rounded to round_digits decimal places.
    """
    if not values:
        return {
            "count": 0,
            "median": None,
            "iqr": None,
            "p90": None,
            "max": None,
        }
    q1 = percentile(values, 25)
    q3 = percentile(values, 75)
    return {
        "count": len(values),
        "median": round(percentile(values, 50), round_digits),
        "iqr": round(q3 - q1, round_digits),
        "p90": round(percentile(values, 90), round_digits),
        "max": round(max(values), round_digits),
    }
