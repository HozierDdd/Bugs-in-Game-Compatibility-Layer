"""
Step 2: ProtonDB observation-volume analysis.

Aggregate report counts and verdict distributions per game, and compute the
overall distribution statistics.
"""

from src.config import (
    PROTONDB_REPORTS_PATH,
    STEP2_OUTPUT,
    TIME_WINDOW_START,
    TIME_WINDOW_END,
)
from src.loaders.protondb_loader import load_protondb_records
from src.transforms.protondb_transform import (
    aggregate_by_game,
    compute_protondb_distribution,
)
from src.utils.json_io import save_json
from src.utils.datetime_utils import now_utc_iso


def run() -> dict:
    print("[Step 2] ProtonDB observation-volume analysis...")

    # Load and filter
    records, total_raw, filtered = load_protondb_records()
    print(f"  Raw records: {total_raw} → in time window: {len(records)}")

    # Aggregate by game
    game_stats = aggregate_by_game(records)
    print(f"  Games covered: {len(game_stats)}")

    # Distribution statistics
    distribution = compute_protondb_distribution(game_stats)
    print(f"  Report-count distribution — median: {distribution['median']}, "
          f"P90: {distribution['p90']}, max: {distribution['max']}")

    # Sort the game list by report count, descending (for readability)
    games_list = sorted(
        game_stats.values(),
        key=lambda g: g["n_reports_protondb"],
        reverse=True,
    )

    result = {
        "step": "step2_protondb",
        "generated_at": now_utc_iso(),
        "time_window": {
            "start": TIME_WINDOW_START.isoformat(),
            "end": TIME_WINDOW_END.isoformat(),
        },
        "input_path": str(PROTONDB_REPORTS_PATH),
        "summary": {
            "total_raw_records": total_raw,
            "records_in_window": len(records),
            "n_games": len(game_stats),
            "distribution_n_reports_protondb": distribution,
        },
        "games": games_list,
    }

    save_json(result, STEP2_OUTPUT)
    print(f"  → Results saved to: {STEP2_OUTPUT}")
    return result


if __name__ == "__main__":
    run()
