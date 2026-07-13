"""
Global analysis configuration.
All business parameters live here; step scripts must not hardcode thresholds or paths.
"""

from pathlib import Path
from datetime import datetime, timezone

# ── Project root ────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent

# ── Data paths ──────────────────────────────────────────────────────────────
DATA_DIR = ROOT_DIR / "data"

PROTONDB_REPORTS_PATH = DATA_DIR / "protondb" / "reports_piiremoved.json"

# GitHub chunks directory (filename pattern: proton_issues_*_part*.json)
GITHUB_CHUNKS_DIR = DATA_DIR / "issue_tracker" / "issue_origin" / "chunks"
GITHUB_CHUNK_GLOB = "proton_issues_*_part*.json"

PROCESSED_DIR = DATA_DIR / "processed"

# ── Output file paths ────────────────────────────────────────────────────────
STEP0_OUTPUT = PROCESSED_DIR / "step0_config.json"
STEP1_OUTPUT = PROCESSED_DIR / "step1_coverage.json"
STEP2_OUTPUT = PROCESSED_DIR / "step2_protondb.json"
STEP3_OUTPUT = PROCESSED_DIR / "step3_github.json"
STEP3_THREADS_OUTPUT = PROCESSED_DIR / "step3_github_threads.json"
STEP4_OUTPUT = PROCESSED_DIR / "master_summary.json"

# Step 5 temporal layering
STEP5_GAMES_OUTPUT     = PROCESSED_DIR / "step5_temporal_layering_games.json"
STEP5_SUMMARY_OUTPUT   = PROCESSED_DIR / "step5_temporal_layering_summary.json"
STEP5_TOP_PDB_OUTPUT   = PROCESSED_DIR / "step5_temporal_layering_top_protondb_first.json"
STEP5_TOP_GH_OUTPUT    = PROCESSED_DIR / "step5_temporal_layering_top_github_first.json"
STEP5_SAME_DAY_OUTPUT  = PROCESSED_DIR / "step5_temporal_layering_same_day_samples.json"

# Step 6 AppID two-stage validation
STEP6_OUTPUT = PROCESSED_DIR / "step6_appid_validation.json"

# Step 7 cross-platform information flow analysis
STEP7_OUTPUT = PROCESSED_DIR / "step7_cross_platform_mentions.json"

# Step 8 cross-platform information flow yearly trend (2021–2025)
STEP8_OUTPUT = PROCESSED_DIR / "step8_yearly_mentions.json"

# Step 9 per-game mutual mention analysis
STEP9_OUTPUT = PROCESSED_DIR / "step9_per_game_mentions.json"


# ── Time window (always UTC-aware datetime) ──────────────────────────────────
TIME_WINDOW_START = datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
TIME_WINDOW_END = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

# ProtonDB timestamps are Unix integer seconds; precompute to speed up filtering
PROTONDB_TS_START: float = TIME_WINDOW_START.timestamp()
PROTONDB_TS_END: float = TIME_WINDOW_END.timestamp()

# ── AppID extraction rules (in priority order) ───────────────────────────────

# Rule 1: 3-7 digit number in trailing parentheses of the title  e.g. "Half-Life 2 (220)"
# Using 3-7 rather than 4-7: Steam has 3-digit appids (e.g. 220=HL2, 730=CS:GO),
# and the parenthetical context (trailing position) guarantees precision
# without needing an extra digit-count constraint.
APPID_RULE_PARENTHESES_PATTERN = r"\((\d{3,7})\)\s*$"

# Rule 2: Steam store link in the body  e.g. "store.steampowered.com/app/220"
# Also relaxed to 3 digits: the URL-path context is extremely precise and won't misfire.
APPID_RULE_STEAM_URL_PATTERN = r"store\.steampowered\.com/app/(\d{3,7})"

# Rule 3: standalone 4-7 digit integer in the title (conservative fallback, lower precision)
# Keep the 4-digit lower bound to avoid matching issue numbers, years, and other short digits;
# exclude a # prefix (issue reference #12345) and dot/hyphen affixes (version-number fragments).
# A "9" in "Proton 9.0" is only 1 digit and won't match;
# the digits in "3.16-4" are each ≤ 2 digits and likewise won't match.
APPID_RULE_STANDALONE_PATTERN = r"(?<!#)(?<![.\-])\b(\d{4,7})\b(?![.\-])"

# Placeholder used when resolution fails
UNRESOLVED_APPID = "unresolved_appid"

# ── Compatibility report classifier (deterministic rule) ────────────────────
# Criterion: a post must contain this exact heading line to count as a compatibility report.
# A deterministic single rule is used instead of a scoring heuristic to:
#   - remove the subjectivity of threshold tuning
#   - guarantee fully reproducible results across runs
#   - in the Proton issue tracker, formal reports all use this official template heading
CLASSIFIER_REPORT_HEADING = "# Compatibility Report"

# ── AppID validation (Step 6) ────────────────────────────────────────────────
# Steam AppID list cache (~220k entries, 17MB) to avoid repeated downloads
STEAM_APPLIST_CACHE_PATH = DATA_DIR / "cache" / "steam_applist.json"
# Cache lifetime (days); refreshed automatically on the next run once exceeded
STEAM_APPLIST_CACHE_TTL_DAYS = 7
# Steam appdetails API request interval (seconds); Steam's official rate limit is ~200 calls/5min
APPDETAILS_REQUEST_DELAY = 1.5

# ── Statistics output precision ──────────────────────────────────────────────
STATS_ROUND_DIGITS = 1
