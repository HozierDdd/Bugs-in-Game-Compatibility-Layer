"""
Time-trend analysis: CR submission volume and game coverage
======================================

Research question:
  How do ProtonDB and the GitHub Issue Tracker differ in their CR submission
  volume / game coverage growth patterns over time?

Analysis metrics (aggregated by month):
  1. Monthly CR submissions  — for ProtonDB each record is one CR;
                               for GitHub the n_reports_in_thread field is used.
  2. Cumulative unique games — measures how each platform's "game coverage" evolves.

Key-event annotations (drawn as vertical dashed lines on the chart):
  - Proton 6.3 release (2021-09)
  - Steam Deck launch (2022-02)
  - Proton 7.0 release (2022-03)
  - Proton 8.0 release (2023-03)
  - Proton 9.0 release (2024-05)

Data sources (all produced by the Pipeline, no need to re-run):
  - ProtonDB : src/loaders/protondb_loader.py (reads data/protondb/reports_piiremoved.json)
  - GitHub   : data/processed/step3_github_threads.json

Usage:
    python3 scripts/analyze_time_trends.py

Output:
    data/processed/time_trends.json   -- raw monthly values (reusable downstream)
    data/processed/time_trends.png    -- visualization chart (requires matplotlib)
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

# Add the project root to sys.path so src/ can be reused
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.config import STEP3_THREADS_OUTPUT, UNRESOLVED_APPID
from src.loaders.protondb_loader import load_protondb_records
from src.utils.json_io import load_json, save_json
from src.utils.datetime_utils import from_unix_timestamp, from_iso8601

# ── Key events (label, YYYY-MM-DD) ──────────────────────────────────────────────
KEY_EVENTS: list[tuple[str, str]] = [
    ("Proton 6.3",      "2021-09-01"),
    ("Steam Deck\nLaunch", "2022-02-25"),
    ("Proton 7.0",      "2022-03-10"),
    ("Proton 8.0",      "2023-03-31"),
    ("Proton 9.0",      "2024-05-23"),
]

# ── Analysis time window (consistent with the Pipeline) ─────────────────────────────
DISPLAY_START = datetime(2021, 1, 1, tzinfo=timezone.utc)
DISPLAY_END   = datetime(2025, 12, 31, tzinfo=timezone.utc)


# ── Monthly aggregation helpers ──────────────────────────────────────────────────

def _month_key(dt: datetime) -> str:
    """datetime -> 'YYYY-MM' grouping key."""
    return dt.strftime("%Y-%m")


def _build_protondb_monthly(records: list[dict]) -> dict:
    """
    Aggregate ProtonDB CR submissions and first game appearances by month.

    Returns:
        {
          "cr_count":  {month: int},   # new CRs that month
          "new_games": {month: int},   # games appearing for the first time that month
        }
    """
    cr_by_month: dict[str, int] = defaultdict(int)
    first_seen: dict[str, str] = {}   # app_id -> month first seen

    for rec in records:
        dt = from_unix_timestamp(rec["timestamp"])
        month = _month_key(dt)
        cr_by_month[month] += 1

        app_id = rec["app_id"]
        if app_id not in first_seen:
            first_seen[app_id] = month

    new_games: dict[str, int] = defaultdict(int)
    for month in first_seen.values():
        new_games[month] += 1

    return {"cr_count": dict(cr_by_month), "new_games": dict(new_games)}


def _build_github_monthly(threads: list[dict]) -> dict:
    """
    Aggregate GitHub Tracker CR submissions and first game appearances by month.

    Notes:
      - CR count is taken from n_reports_in_thread (number of CR posts in that issue thread).
      - First game appearance uses the thread's created_at as a time proxy
        (individual comment-level timestamps are not kept separately in step3).
      - Threads whose resolved_appid is UNRESOLVED_APPID are excluded from game coverage.

    Returns:
        {
          "cr_count":  {month: int},
          "new_games": {month: int},
        }
    """
    cr_by_month: dict[str, int] = defaultdict(int)
    first_seen: dict[str, str] = {}

    for thread in threads:
        created_str = thread.get("created_at")
        if not created_str:
            continue
        try:
            dt = from_iso8601(created_str)
        except ValueError:
            continue

        month = _month_key(dt)
        cr_by_month[month] += thread.get("n_reports_in_thread", 0)

        app_id = thread.get("resolved_appid", UNRESOLVED_APPID)
        if app_id != UNRESOLVED_APPID and app_id not in first_seen:
            first_seen[app_id] = month

    new_games: dict[str, int] = defaultdict(int)
    for month in first_seen.values():
        new_games[month] += 1

    return {"cr_count": dict(cr_by_month), "new_games": dict(new_games)}


def _cumulative(new_games: dict[str, int], months: list[str]) -> list[int]:
    """Accumulate monthly new-game counts into a cumulative series (same length as months)."""
    cum, result = 0, []
    for m in months:
        cum += new_games.get(m, 0)
        result.append(cum)
    return result


def build_monthly_series(
    pdb_monthly: dict,
    gh_monthly: dict,
    start: datetime = DISPLAY_START,
    end: datetime   = DISPLAY_END,
) -> dict:
    """
    Align both platforms' monthly data onto the same timeline, bounded to [start, end].

    Returned structure:
        {
          "months":   ["YYYY-MM", ...],
          "protondb": {
            "cr_count_monthly":  [int, ...],
            "new_games_monthly": [int, ...],
            "cumulative_games":  [int, ...],
          },
          "github":   { same as above },
        }
    """
    all_months_set = set(pdb_monthly["cr_count"]) | set(gh_monthly["cr_count"])
    # Build a complete month sequence within [start, end] (keep placeholder 0 even for empty months)
    start_key = _month_key(start)
    end_key   = _month_key(end)
    months = sorted(m for m in all_months_set if start_key <= m <= end_key)

    pdb_cr  = [pdb_monthly["cr_count"].get(m, 0)  for m in months]
    gh_cr   = [gh_monthly["cr_count"].get(m, 0)   for m in months]
    pdb_new = [pdb_monthly["new_games"].get(m, 0) for m in months]
    gh_new  = [gh_monthly["new_games"].get(m, 0)  for m in months]

    return {
        "months": months,
        "protondb": {
            "cr_count_monthly":  pdb_cr,
            "new_games_monthly": pdb_new,
            "cumulative_games":  _cumulative(pdb_monthly["new_games"], months),
        },
        "github": {
            "cr_count_monthly":  gh_cr,
            "new_games_monthly": gh_new,
            "cumulative_games":  _cumulative(gh_monthly["new_games"], months),
        },
    }


# ── Visualization ────────────────────────────────────────────────────────────────────

def plot_time_trends(series: dict, output_path: Path) -> None:
    """
    Generate a 2-row, 1-column time-trend chart:
      Row 1: monthly CR submission volume comparison
      Row 2: cumulative game coverage comparison

    Annotate key events (Steam Deck launch, major Proton releases) on both subplots.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        import matplotlib.ticker as mticker
    except ImportError:
        print("[WARN] matplotlib not installed, skipping chart generation. Run: pip install matplotlib")
        return

    months = series["months"]
    xs = [datetime(int(m[:4]), int(m[5:7]), 1, tzinfo=timezone.utc) for m in months]
    pdb = series["protondb"]
    gh  = series["github"]

    # Key-event datetime objects
    events: list[tuple[str, datetime]] = [
        (label, datetime(*[int(x) for x in date_str.split("-")], tzinfo=timezone.utc))
        for label, date_str in KEY_EVENTS
    ]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    fig.suptitle(
        "ProtonDB x GitHub Proton Issue Tracker\n"
        "CR Submission Volume & Game Coverage Over Time (2021-2025, Monthly)",
        fontsize=12, fontweight="bold", y=0.99,
    )

    clr_pdb = "#1f77b4"   # blue  – ProtonDB
    clr_gh  = "#d62728"   # red   – GitHub Issue Tracker

    # ── Panel 1: Monthly CR submission volume ─────────────────────────────
    ax1.plot(xs, pdb["cr_count_monthly"], color=clr_pdb, linewidth=1.8,
             label="ProtonDB (monthly CR count)", alpha=0.9)
    ax1.plot(xs, gh["cr_count_monthly"],  color=clr_gh,  linewidth=1.8,
             label="GitHub Issue Tracker (monthly CR count)", alpha=0.9)
    ax1.set_ylabel("Monthly CR Submissions", fontsize=10)
    ax1.legend(loc="upper left", fontsize=9)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax1.grid(True, alpha=0.3, linestyle=":")
    ax1.set_title("(1) Monthly CR Submission Volume", fontsize=10, pad=4)

    # ── Panel 2: Cumulative unique games covered ──────────────────────────
    ax2.plot(xs, pdb["cumulative_games"], color=clr_pdb, linewidth=1.8,
             label="ProtonDB (cumulative unique games)", alpha=0.9)
    ax2.plot(xs, gh["cumulative_games"],  color=clr_gh,  linewidth=1.8,
             label="GitHub Issue Tracker (cumulative unique games)", alpha=0.9)
    ax2.set_ylabel("Cumulative Games Covered", fontsize=10)
    ax2.legend(loc="upper left", fontsize=9)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax2.grid(True, alpha=0.3, linestyle=":")
    ax2.set_title("(2) Cumulative Game Coverage", fontsize=10, pad=4)

    # ── Key events: vertical dashed lines + labels ────────────────────────
    cr_max = max(pdb["cr_count_monthly"] + gh["cr_count_monthly"])
    for label, evt_dt in events:
        for ax in (ax1, ax2):
            ax.axvline(x=evt_dt, color="gray", linestyle="--", linewidth=0.9, alpha=0.55)
        # Label only near the top of ax1
        ax1.text(
            evt_dt, cr_max * 0.96, label,
            fontsize=6.5, color="#555555", ha="center", va="top",
            rotation=90, alpha=0.9,
        )

    # ── X axis: one tick per quarter ─────────────────────────────────────
    ax2.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate(rotation=45, ha="right")

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] Chart saved -> {output_path}")


# ── Main flow ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== Time-trend analysis: CR submission volume and game coverage ===\n")

    # 1. Load ProtonDB reports (reuse existing loader, time-window filter applied automatically)
    print("[1/4] Loading ProtonDB reports...")
    pdb_records, total_raw, filtered = load_protondb_records()
    print(f"      {total_raw:,} raw records, {len(pdb_records):,} kept in window")

    # 2. Load GitHub threads (step3 already resolved game AppIDs and counted CRs)
    print("[2/4] Loading GitHub threads (from step3_github_threads.json)...")
    threads_data = load_json(STEP3_THREADS_OUTPUT)
    threads = threads_data.get("threads", [])
    print(f"      {len(threads):,} threads total")

    # 3. Aggregate by month and align the timeline
    print("[3/4] Aggregating by month...")
    pdb_monthly = _build_protondb_monthly(pdb_records)
    gh_monthly  = _build_github_monthly(threads)
    series = build_monthly_series(pdb_monthly, gh_monthly)

    months = series["months"]
    pdb_total_cr  = sum(series["protondb"]["cr_count_monthly"])
    gh_total_cr   = sum(series["github"]["cr_count_monthly"])
    pdb_cum_games = series["protondb"]["cumulative_games"][-1]
    gh_cum_games  = series["github"]["cumulative_games"][-1]

    print(f"      Time span: {months[0]} ~ {months[-1]} ({len(months)} months)")
    print(f"      ProtonDB: {pdb_total_cr:,} CRs in window, "
          f"covering {pdb_cum_games:,} games")
    print(f"      GitHub  : {gh_total_cr:,} CRs in window, "
          f"covering {gh_cum_games:,} games")

    # 4. Save JSON data and PNG chart
    out_json = ROOT_DIR / "data" / "processed" / "time_trends.json"
    save_json(series, out_json)
    print(f"\n[OK] Monthly data saved -> {out_json}")

    print("[4/4] Generating chart...")
    out_png = ROOT_DIR / "data" / "processed" / "time_trends.png"
    plot_time_trends(series, out_png)

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
