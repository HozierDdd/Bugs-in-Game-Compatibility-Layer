"""
GitHub compatibility report classifier.

────────────────────────────────────────────────────────────────────────────
Decision rule: deterministic single-heading detection (case-insensitive)
────────────────────────────────────────────────────────────────────────────

A post is a compatibility report if and only if its text contains (case-insensitively):

    # Compatibility Report

A deterministic rule is used instead of a scoring heuristic because:
  1. The Proton issue tracker's official template requires every compatibility report to start with this line
  2. It removes the subjectivity of threshold/weight tuning, giving fully reproducible results across runs
  3. Precision is extremely high — ordinary discussion posts almost never contain this exact heading
  4. It eases manual verification: any misclassification can be located directly in the raw data

Case-insensitive: tolerates casing variants entered by users (e.g. "# compatibility report"),
avoiding missed reports that differ only in letter case.

Classification unit: POST level (an issue body OR a single comment body), not thread level.
Reason: a single thread may contain multiple compatibility reports from different users.
────────────────────────────────────────────────────────────────────────────
"""

from src.config import CLASSIFIER_REPORT_HEADING

_HEADING_LOWER = CLASSIFIER_REPORT_HEADING.lower()


def classify_post(post_text: str) -> dict:
    """
    Determine whether a post body is a compatibility report.

    Args:
        post_text: raw text of an issue body or comment body

    Returns:
        {"is_compatibility_report": bool}
    """
    if not post_text:
        return {"is_compatibility_report": False}

    is_report = _HEADING_LOWER in post_text.lower()
    return {"is_compatibility_report": is_report}


# ── Lightweight self-test ────────────────────────────────────────────────────

_TEST_CASES = [
    # (name, text, expected_is_report)

    # Contains the official template heading → report
    (
        "full_template",
        """# Compatibility Report
- Name of the game: Rising Storm
- Steam AppID of the game: 35450

## System Information
- GPU: GTX 1050 Ti
- Proton version: 5.0-3

## Symptoms
Game crashes at launch.
""",
        True,
    ),
    # Heading appears anywhere in the body → report
    (
        "heading_mid_text",
        "Some intro text.\n\n# Compatibility Report\n- Steam AppID: 220\n",
        True,
    ),
    # No heading, even with system-info fields present → not a report
    (
        "fields_without_heading",
        "GPU: RTX 3070\nProton version: 7.0-4\nStill getting the same crash.",
        False,
    ),
    # Short discussion → not a report
    (
        "short_discussion",
        "same issue here, still not working",
        False,
    ),
    # Thanks/acknowledgement post → not a report
    (
        "thanks_post",
        "Thanks for the fix! This worked perfectly for me.",
        False,
    ),
    # Feature suggestion → not a report
    (
        "suggestion",
        "Can you add MangoHud support? Many users have been requesting this feature.",
        False,
    ),
    # Pure quote → not a report (the heading is not inside the quote)
    (
        "pure_quote",
        "> GPU: RTX 3070\n> Proton version: 7.0\n\nYeah same here.",
        False,
    ),
    # Empty text → not a report
    (
        "empty",
        "",
        False,
    ),
    # Different case → still a report (heading is case-insensitive)
    (
        "wrong_case",
        "# compatibility report\n- AppID: 220",
        True,
    ),
    # Mixed-case variant → still a report
    (
        "mixed_case",
        "# COMPATIBILITY REPORT\n- AppID: 730",
        True,
    ),
]


def _run_tests() -> None:
    """Assert against the built-in test cases to verify classifier behavior."""
    fail_count = 0
    for name, text, expected in _TEST_CASES:
        result = classify_post(text)
        got = result["is_compatibility_report"]
        if got != expected:
            print(f"  FAIL [{name}]: expected={expected}, got={got}")
            fail_count += 1
        else:
            print(f"  OK   [{name}]: is_report={got}")
    if fail_count == 0:
        print("compatibility_report_classifier: all tests passed.")
    else:
        print(f"compatibility_report_classifier: {fail_count} test(s) FAILED.")


if __name__ == "__main__":
    _run_tests()
