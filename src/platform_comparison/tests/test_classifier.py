"""
Unit tests for the compatibility report classifier.

Rule: a post containing "# Compatibility Report" (case-insensitive) -> is a report; otherwise not.
Deterministic rule, no scoring, no edge cases.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.compatibility_report_classifier import classify_post


# ── Test text ─────────────────────────────────────────────────────────────────

REPORT_FULL_TEMPLATE = """# Compatibility Report
- Name of the game with compatibility issues: Rising Storm
- Steam AppID of the game: 35450

## System Information
- GPU: GTX 1050 Ti
- Driver/LLVM version: NVIDIA 440.59
- Kernel version: 5.5 Manjaro
- Proton version: 5.0-3

## Symptoms
Game crashes immediately at launch with a black screen.

## Reproduction
1. Launch game via Steam with default settings
2. Game exits after ~2 seconds
"""

# Heading appears in the middle of the text (not the first line)
REPORT_HEADING_MID_TEXT = (
    "Some preamble.\n\n"
    "# Compatibility Report\n"
    "- Steam AppID: 220\n"
    "- GPU: RX 6700 XT\n"
)

# Contains system information fields but no heading -> not a report
NOT_REPORT_FIELDS_NO_HEADING = """## System Information
- GPU: RX 580
- Kernel version: 5.15.0-generic
- Proton version: 7.0-6

Game fails to start after the recent Proton update.
"""

DISCUSSION_SHORT = "same issue here, still not working"

DISCUSSION_THANKS = "Thanks for the fix! This worked for me."

DISCUSSION_SUGGESTION = (
    "Can you add support for MangoHud overlay? It would be really useful "
    "for performance monitoring. Many users have been requesting this feature."
)

# Pure quote (quoted content has no heading)
DISCUSSION_PURE_QUOTE = (
    "> GPU: RTX 3070\n"
    "> Proton version: 7.0\n\n"
    "Yeah I have the same GPU, no luck either."
)

# Different case -> still a report (case-insensitive)
REPORT_WRONG_CASE = "# compatibility report\n- AppID: 220\n- GPU: RTX 3080\n"

# All-uppercase variant -> still a report
REPORT_UPPER_CASE = "# COMPATIBILITY REPORT\n- AppID: 730\n- GPU: RX 6700 XT\n"


# ── Test functions ──────────────────────────────────────────────────────────────────

def test_full_template_is_report():
    """A full template post containing '# Compatibility Report' should be identified as a report."""
    result = classify_post(REPORT_FULL_TEMPLATE)
    assert result["is_compatibility_report"] is True


def test_heading_anywhere_in_text_is_report():
    """'# Compatibility Report' appearing anywhere in the text should trigger."""
    result = classify_post(REPORT_HEADING_MID_TEXT)
    assert result["is_compatibility_report"] is True


def test_fields_without_heading_not_report():
    """
    Has system information fields but no '# Compatibility Report' heading -> not a report.
    This is the most important behavior change from the old heuristic rule: structural fields no longer carry a score.
    """
    result = classify_post(NOT_REPORT_FIELDS_NO_HEADING)
    assert result["is_compatibility_report"] is False


def test_short_discussion_not_report():
    """A very short discussion reply is not a report."""
    result = classify_post(DISCUSSION_SHORT)
    assert result["is_compatibility_report"] is False


def test_thanks_not_report():
    """A thank-you post is not a report."""
    result = classify_post(DISCUSSION_THANKS)
    assert result["is_compatibility_report"] is False


def test_suggestion_not_report():
    """A feature suggestion post is not a report."""
    result = classify_post(DISCUSSION_SUGGESTION)
    assert result["is_compatibility_report"] is False


def test_pure_quote_not_report():
    """A pure-quote follow-up (with no heading) is not a report."""
    result = classify_post(DISCUSSION_PURE_QUOTE)
    assert result["is_compatibility_report"] is False


def test_wrong_case_is_report():
    """Lowercase heading variant -> still a report (rule is case-insensitive)."""
    result = classify_post(REPORT_WRONG_CASE)
    assert result["is_compatibility_report"] is True


def test_upper_case_is_report():
    """All-uppercase heading variant -> still a report (rule is case-insensitive)."""
    result = classify_post(REPORT_UPPER_CASE)
    assert result["is_compatibility_report"] is True


def test_empty_post():
    """Empty text is not a report."""
    for text in ["", "   ", None]:
        result = classify_post(text or "")
        assert result["is_compatibility_report"] is False


def test_return_schema():
    """The return value contains only the 'is_compatibility_report' field, without score or matched_rules."""
    result = classify_post(REPORT_FULL_TEMPLATE)
    assert set(result.keys()) == {"is_compatibility_report"}, (
        f"Unexpected keys in result: {set(result.keys())}"
    )


if __name__ == "__main__":
    test_full_template_is_report()
    print("  ✓ test_full_template_is_report")
    test_heading_anywhere_in_text_is_report()
    print("  ✓ test_heading_anywhere_in_text_is_report")
    test_fields_without_heading_not_report()
    print("  ✓ test_fields_without_heading_not_report")
    test_short_discussion_not_report()
    print("  ✓ test_short_discussion_not_report")
    test_thanks_not_report()
    print("  ✓ test_thanks_not_report")
    test_suggestion_not_report()
    print("  ✓ test_suggestion_not_report")
    test_pure_quote_not_report()
    print("  ✓ test_pure_quote_not_report")
    test_wrong_case_is_report()
    print("  ✓ test_wrong_case_is_report")
    test_upper_case_is_report()
    print("  ✓ test_upper_case_is_report")
    test_empty_post()
    print("  ✓ test_empty_post")
    test_return_schema()
    print("  ✓ test_return_schema")
    print("All classifier tests passed.")
