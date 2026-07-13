"""
Step 0: Freeze the configuration snapshot.

Serialize all key parameters of this analysis run to a JSON file so the
results stay traceable and reproducible.
"""

from src.config import (
    PROTONDB_REPORTS_PATH,
    GITHUB_CHUNKS_DIR,
    GITHUB_CHUNK_GLOB,
    STEP0_OUTPUT,
    TIME_WINDOW_START,
    TIME_WINDOW_END,
    APPID_RULE_PARENTHESES_PATTERN,
    APPID_RULE_STEAM_URL_PATTERN,
    APPID_RULE_STANDALONE_PATTERN,
    UNRESOLVED_APPID,
    CLASSIFIER_REPORT_HEADING,
    STATS_ROUND_DIGITS,
)
from src.utils.json_io import save_json
from src.utils.datetime_utils import now_utc_iso


def run() -> None:
    print("[Step 0] Freezing configuration snapshot...")

    config_snapshot = {
        "step": "step0_config",
        "generated_at": now_utc_iso(),
        "description": "Full configuration snapshot of the analysis run, for reproducibility",
        "time_window": {
            "start": TIME_WINDOW_START.isoformat(),
            "end": TIME_WINDOW_END.isoformat(),
        },
        "analysis_unit": "game_appid",
        "github_inclusion_criteria": {
            "description": "An issue is included in the study window if it meets either criterion (union of the two)",
            "criterion_1_created_at": "issue.created_at falls within [start, end]",
            "criterion_2_thread_median": (
                "the median created_at timestamp across all posts in the "
                "issue thread (body + all comments) falls within [start, end]"
            ),
            "inclusion_method_field": (
                "the inclusion_method field on each normalized record records which "
                "criterion actually matched: \"created_at\" or \"thread_median\""
            ),
        },
        "input_paths": {
            "protondb_reports": str(PROTONDB_REPORTS_PATH),
            "github_chunks_dir": str(GITHUB_CHUNKS_DIR),
            "github_chunk_glob": GITHUB_CHUNK_GLOB,
        },
        "appid_extraction_rules": {
            "priority_1_parentheses": APPID_RULE_PARENTHESES_PATTERN,
            "priority_2_steam_url": APPID_RULE_STEAM_URL_PATTERN,
            "priority_3_standalone": APPID_RULE_STANDALONE_PATTERN,
            "note_digit_range": "rules 1 and 2 accept 3-7 digits to cover early Steam appids; rule 3 requires 4-7 to reduce false positives",
            "unresolved_placeholder": UNRESOLVED_APPID,
        },
        "classifier_config": {
            "rule": "deterministic_heading_match",
            "required_heading": CLASSIFIER_REPORT_HEADING,
            "design_principle": "exact-match-only; no scoring, no heuristics",
            "classification_unit": "post-level (issue body or single comment body)",
        },
        "output_settings": {
            "stats_round_digits": STATS_ROUND_DIGITS,
            "json_indent": 2,
            "encoding": "utf-8",
        },
    }

    save_json(config_snapshot, STEP0_OUTPUT)
    print(f"  → Configuration saved to: {STEP0_OUTPUT}")


if __name__ == "__main__":
    run()
