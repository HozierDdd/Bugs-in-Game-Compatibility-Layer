"""
Post-volume analysis: GitHub Issue Tracker vs ProtonDB
================================================

Research question:
  From 2021-01-01 to 2025-12-31, compare the two platforms' total monthly
  post volume and their trends.

Metric definitions:
  - GitHub Proton Issue Tracker: all posts published within the time window
      = issue bodies created in the window + comments published in the window
    Note: even if an issue was created before the window, its later comments
    that fall inside the window are still counted.
  - ProtonDB: all compatibility reports submitted within the window (each record is one report).

Difference from analyze_time_trends.py:
  - analyze_time_trends.py counts "CR count", grouped by thread creation time;
  - this script counts "post count", grouped by each post's (issue body / comment)
    actual publish time, and is not limited to compatibility reports -- it includes
    all discussion posts.

Prerequisites: none (reads raw chunk files directly, no need to run the Pipeline)

Usage:
    python3 scripts/analyze_post_volume.py

Output:
    data/processed/post_volume.json   -- raw monthly values (reusable downstream)
    data/processed/post_volume.png    -- visualization chart (requires matplotlib)
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.config import (
    GITHUB_CHUNKS_DIR,
    GITHUB_CHUNK_GLOB,
    TIME_WINDOW_START,
    TIME_WINDOW_END,
)
from src.loaders.protondb_loader import load_protondb_records
from src.utils.datetime_utils import from_iso8601, from_unix_timestamp, in_window, now_utc_iso
from src.utils.json_io import save_json

# ── Key events (kept consistent with analyze_time_trends.py) ────────────────────────────
KEY_EVENTS: list[tuple[str, str]] = [
    ("Proton 6.3",         "2021-09-01"),
    ("Steam Deck\nLaunch", "2022-02-25"),
    ("Proton 7.0",         "2022-03-10"),
    ("Proton 8.0",         "2023-03-31"),
    ("Proton 9.0",         "2024-05-23"),
]


def _month_key(dt: datetime) -> str:
    """datetime -> 'YYYY-MM' grouping key."""
    return dt.strftime("%Y-%m")


def _scan_github_posts(
    chunks_dir: Path,
    chunk_glob: str,
    start: datetime,
    end: datetime,
) -> dict:
    """
    Walk all raw GitHub issue chunks and count posts per month within the time window.

    Post unit: issue body (created_at as its post time) + each comment (created_at as its post time).
    Even if an issue was created before the window, its in-window comments are still tallied
    into the corresponding month.

    Returns:
        {
          "post_count":                  {month: int},
          "total":                       int,
          "issues_scanned":              int,
          "issues_with_window_activity": int,
        }
    """
    post_by_month: dict[str, int] = defaultdict(int)
    issues_scanned = 0
    issues_with_activity = 0

    for chunk_path in sorted(Path(chunks_dir).glob(chunk_glob)):
        with open(chunk_path, encoding="utf-8") as f:
            chunk = json.load(f)

        for raw_issue in (chunk.get("issues") or []):
            issues_scanned += 1
            had_activity = False

            # Issue body post time
            created_str = raw_issue.get("created_at")
            if created_str:
                try:
                    dt = from_iso8601(created_str)
                    if in_window(dt, start, end):
                        post_by_month[_month_key(dt)] += 1
                        had_activity = True
                except ValueError:
                    pass

            # Post time of each comment
            for comment in (raw_issue.get("comments_data") or []):
                c_str = comment.get("created_at")
                if c_str:
                    try:
                        dt = from_iso8601(c_str)
                        if in_window(dt, start, end):
                            post_by_month[_month_key(dt)] += 1
                            had_activity = True
                    except ValueError:
                        pass

            if had_activity:
                issues_with_activity += 1

    return {
        "post_count": dict(post_by_month),
        "total": sum(post_by_month.values()),
        "issues_scanned": issues_scanned,
        "issues_with_window_activity": issues_with_activity,
    }


def _count_protondb_monthly(records: list[dict]) -> dict:
    """
    Count ProtonDB CR submissions per month (records already filtered to the time window).

    Returns:
        {"cr_count": {month: int}, "total": int}
    """
    cr_by_month: dict[str, int] = defaultdict(int)
    for rec in records:
        cr_by_month[_month_key(from_unix_timestamp(rec["timestamp"]))] += 1
    return {"cr_count": dict(cr_by_month), "total": sum(cr_by_month.values())}


def build_monthly_series(
    pdb_monthly: dict,
    gh_stats: dict,
    start: datetime = TIME_WINDOW_START,
    end: datetime = TIME_WINDOW_END,
) -> dict:
    """
    Align both platforms' monthly data onto the same timeline, bounded to [start, end].

    Returned structure:
        {
          "window":      {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
          "generated_at": str,
          "summary":     {"github": {...}, "protondb": {...}},
          "months":      ["YYYY-MM", ...],
          "protondb":    {"cr_count_monthly": [...], "cumulative_posts": [...]},
          "github_issue_tracker": {"post_count_monthly": [...], "cumulative_posts": [...]},
        }
    """
    all_months = set(pdb_monthly["cr_count"]) | set(gh_stats["post_count"])
    start_key, end_key = _month_key(start), _month_key(end)
    months = sorted(m for m in all_months if start_key <= m <= end_key)

    pdb_cr   = [pdb_monthly["cr_count"].get(m, 0) for m in months]
    gh_posts = [gh_stats["post_count"].get(m, 0)  for m in months]

    pdb_cum, gh_cum = [], []
    pdb_c = gh_c = 0
    for p, g in zip(pdb_cr, gh_posts):
        pdb_c += p
        gh_c  += g
        pdb_cum.append(pdb_c)
        gh_cum.append(gh_c)

    return {
        "window": {
            "start": start.strftime("%Y-%m-%d"),
            "end":   end.strftime("%Y-%m-%d"),
        },
        "generated_at": now_utc_iso(),
        "summary": {
            "github": {
                "total_posts":                 gh_stats["total"],
                "issues_scanned":              gh_stats["issues_scanned"],
                "issues_with_window_activity": gh_stats["issues_with_window_activity"],
            },
            "protondb": {
                "total_crs": pdb_monthly["total"],
            },
        },
        "months": months,
        "protondb": {
            "cr_count_monthly": pdb_cr,
            "cumulative_posts":  pdb_cum,
        },
        "github_issue_tracker": {
            "post_count_monthly": gh_posts,
            "cumulative_posts":   gh_cum,
        },
    }


# ── Visualization ────────────────────────────────────────────────────────────────────

def plot_post_volume(series: dict, output_path: Path) -> None:
    """
    Generate a 2-row, 1-column post-volume trend chart:
      Row 1: monthly post volume comparison (ProtonDB CR count vs GitHub post count)
      Row 2: cumulative post volume comparison

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
    xs  = [datetime(int(m[:4]), int(m[5:7]), 1, tzinfo=timezone.utc) for m in months]
    pdb = series["protondb"]
    gh  = series["github_issue_tracker"]

    events: list[tuple[str, datetime]] = [
        (label, datetime(*[int(x) for x in date_str.split("-")], tzinfo=timezone.utc))
        for label, date_str in KEY_EVENTS
    ]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    fig.suptitle(
        "ProtonDB x GitHub Proton Issue Tracker\n"
        "Post Volume Over Time (2021-2025, Monthly)",
        fontsize=12, fontweight="bold", y=0.99,
    )

    clr_pdb = "#1f77b4"
    clr_gh  = "#d62728"

    # ── Panel 1: Monthly post volume ──────────────────────────────────────────
    ax1.plot(xs, pdb["cr_count_monthly"],   color=clr_pdb, linewidth=1.8,
             label="ProtonDB (monthly CR count)", alpha=0.9)
    ax1.plot(xs, gh["post_count_monthly"],  color=clr_gh,  linewidth=1.8,
             label="GitHub Issue Tracker (monthly posts: issues + comments)", alpha=0.9)
    ax1.set_ylabel("Monthly Posts", fontsize=10)
    ax1.legend(loc="upper left", fontsize=9)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax1.grid(True, alpha=0.3, linestyle=":")
    ax1.set_title("(1) Monthly Post Volume", fontsize=10, pad=4)

    # ── Panel 2: Cumulative post volume ───────────────────────────────────────
    ax2.plot(xs, pdb["cumulative_posts"], color=clr_pdb, linewidth=1.8,
             label="ProtonDB (cumulative CRs)", alpha=0.9)
    ax2.plot(xs, gh["cumulative_posts"],  color=clr_gh,  linewidth=1.8,
             label="GitHub Issue Tracker (cumulative posts)", alpha=0.9)
    ax2.set_ylabel("Cumulative Posts", fontsize=10)
    ax2.legend(loc="upper left", fontsize=9)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax2.grid(True, alpha=0.3, linestyle=":")
    ax2.set_title("(2) Cumulative Post Volume", fontsize=10, pad=4)

    # ── Key events: vertical dashed lines + labels ────────────────────────────
    cr_max = max(pdb["cr_count_monthly"] + gh["post_count_monthly"])
    for label, evt_dt in events:
        for ax in (ax1, ax2):
            ax.axvline(x=evt_dt, color="gray", linestyle="--", linewidth=0.9, alpha=0.55)
        ax1.text(
            evt_dt, cr_max * 0.96, label,
            fontsize=6.5, color="#555555", ha="center", va="top",
            rotation=90, alpha=0.9,
        )

    # ── X axis: one tick per quarter ─────────────────────────────────────────
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
    print("=== Post-volume analysis: GitHub Issue Tracker vs ProtonDB ===\n")

    # 1. Load ProtonDB reports (reuse existing loader, time-window filter applied automatically)
    print("[1/4] Loading ProtonDB reports...")
    pdb_records, total_raw, _ = load_protondb_records()
    print(f"      {total_raw:,} raw records, {len(pdb_records):,} kept in window")

    # 2. Scan raw GitHub chunks (don't filter issues, check every post's timestamp)
    print("[2/4] Scanning GitHub issue chunks (including follow-up discussion on issues created before the window)...")
    gh_stats = _scan_github_posts(
        GITHUB_CHUNKS_DIR, GITHUB_CHUNK_GLOB,
        TIME_WINDOW_START, TIME_WINDOW_END,
    )
    print(f"      Scanned {gh_stats['issues_scanned']:,} issues, "
          f"{gh_stats['issues_with_window_activity']:,} with in-window activity")
    print(f"      Total in-window posts: {gh_stats['total']:,} (issue bodies + comments)")

    # 3. Aggregate by month and align the timeline
    print("[3/4] Aggregating by month...")
    pdb_monthly = _count_protondb_monthly(pdb_records)
    series = build_monthly_series(pdb_monthly, gh_stats)

    months = series["months"]
    print(f"      Time span: {months[0]} ~ {months[-1]} ({len(months)} months)")
    print(f"      ProtonDB   : {series['summary']['protondb']['total_crs']:,} CRs")
    print(f"      GitHub     : {series['summary']['github']['total_posts']:,} posts")

    # 4. Save JSON data and PNG chart
    out_json = ROOT_DIR / "data" / "processed" / "post_volume.json"
    save_json(series, out_json)
    print(f"\n[OK] Monthly data saved -> {out_json}")

    print("[4/4] Generating chart...")
    out_png = ROOT_DIR / "data" / "processed" / "post_volume.png"
    plot_post_volume(series, out_png)

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
