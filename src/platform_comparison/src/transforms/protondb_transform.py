"""
ProtonDB data aggregation layer.

Aggregates normalized ProtonDB records by game_appid,
computing each game's report count and verdict distribution.
"""

from collections import defaultdict
from src.utils.stats import compute_distribution_stats
from src.config import STATS_ROUND_DIGITS


def aggregate_by_game(records: list[dict]) -> dict[str, dict]:
    """
    Aggregate ProtonDB records by app_id.

    Args:
        records: list of normalized ProtonDB records

    Returns:
        game_appid -> {
            "app_id": str,
            "game_title": str,              # last-seen title (more recent)
            "n_reports_protondb": int,
            "verdict_counts": dict,         # verdict -> count
        }
    """
    # Group by appid
    groups: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        groups[rec["app_id"]].append(rec)

    result: dict[str, dict] = {}
    for app_id, recs in groups.items():
        # Take the title from the last record (usually more recent)
        title = ""
        for r in reversed(recs):
            if r["title"]:
                title = r["title"]
                break

        # Tally the verdict distribution
        verdict_counts: dict[str, int] = defaultdict(int)
        for r in recs:
            v = r["verdict"] or "unknown"
            verdict_counts[v] += 1

        result[app_id] = {
            "app_id": app_id,
            "game_title": title,
            "n_reports_protondb": len(recs),
            "verdict_counts": dict(verdict_counts),
        }

    return result


def compute_protondb_distribution(game_stats: dict[str, dict]) -> dict:
    """
    Compute distribution statistics of per-game report counts for ProtonDB.

    Args:
        game_stats: the return value of aggregate_by_game

    Returns:
        distribution statistics dict (count, median, iqr, p90, max)
    """
    counts = [v["n_reports_protondb"] for v in game_stats.values()]
    return compute_distribution_stats(counts, STATS_ROUND_DIGITS)
