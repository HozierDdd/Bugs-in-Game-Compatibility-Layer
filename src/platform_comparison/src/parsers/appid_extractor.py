"""
Steam AppID extraction module.

Parses a Steam AppID from a GitHub issue's title and body,
applying rules in the following priority order:

    Priority 1 — trailing parentheses in the title  e.g. "Half-Life 2 (220)"
                 Highest precision; the vast majority of reports submitted via
                 the official template follow this convention.
                 Supports 3-7 digit numbers: Steam has 3-digit appids (e.g. 220, 440),
                 and the trailing-parenthesis position gives enough context that no
                 extra digit-count constraint is needed.

    Priority 2 — Steam store link in the body  e.g. store.steampowered.com/app/220
                 High precision; the URL-path context is unambiguous, also supports 3-7 digits.

    Priority 3 — standalone 4-7 digit integer in the title (conservative fallback)
                 Keeps the 4-digit lower bound to avoid matching issue numbers, years, etc.;
                 excludes a # prefix and dot/hyphen affixes to filter out version-number fragments.
                 Lower precision; used only when the first two rules both fail.

If none of the three rules match, returns the UNRESOLVED_APPID placeholder.
"""

import re
from src.config import (
    APPID_RULE_PARENTHESES_PATTERN,
    APPID_RULE_STEAM_URL_PATTERN,
    APPID_RULE_STANDALONE_PATTERN,
    UNRESOLVED_APPID,
)

# Precompile the regexes to avoid recompiling on every call
_RE_PARENTHESES = re.compile(APPID_RULE_PARENTHESES_PATTERN)
_RE_STEAM_URL = re.compile(APPID_RULE_STEAM_URL_PATTERN)
_RE_STANDALONE = re.compile(APPID_RULE_STANDALONE_PATTERN)


def extract_appid(title: str, body: str | None) -> tuple[str, str]:
    """
    Extract a Steam AppID from an issue title and body.

    Returns:
        (appid, rule_used)
        appid    — the extracted AppID string, or UNRESOLVED_APPID
        rule_used — the name of the rule that matched, for logging and debugging
    """
    title = title or ""
    body = body or ""

    # Rule 1: trailing parentheses in the title
    m = _RE_PARENTHESES.search(title)
    if m:
        return m.group(1), "parentheses"

    # Rule 2: Steam store URL in the body
    m = _RE_STEAM_URL.search(body)
    if m:
        return m.group(1), "steam_url"

    # Rule 3: standalone number in the title (fallback)
    m = _RE_STANDALONE.search(title)
    if m:
        return m.group(1), "standalone"

    return UNRESOLVED_APPID, "unresolved"


# ── Lightweight self-test ────────────────────────────────────────────────────

def _run_tests() -> None:
    """Assert key scenarios; can serve as a quick smoke test at runtime."""
    cases = [
        # (title, body, expected_appid, expected_rule)

        # Rule 1: trailing parentheses in the title (3-7 digits)
        ("Disgaea PC (405900)", "", "405900", "parentheses"),
        ("Some Game (1234567)", "", "1234567", "parentheses"),
        # 3-digit appids (Half-Life 2, Counter-Strike, and other early games)
        ("Half-Life 2 (220)", "", "220", "parentheses"),
        ("The Elder Scrolls V: Skyrim Special Edition (489830)", "", "489830", "parentheses"),
        # Rule 1 takes priority over Rule 3
        ("Game Fix 9999 (12345)", "", "12345", "parentheses"),

        # Rule 2: Steam store URL in the body (3-7 digits)
        ("Bug report", "https://store.steampowered.com/app/220/Half-Life_2", "220", "steam_url"),
        ("No id in title here", "https://store.steampowered.com/app/489830", "489830", "steam_url"),

        # Rule 3: standalone number in the title (4-7 digits, conservative fallback)
        ("12345 - Game crashes at launch", "", "12345", "standalone"),

        # Cases that must NOT be mis-matched by Rule 3
        # "9" in "Proton 9.0" is only 1 digit, no match; no other 4-7 digit number present
        ("Proton 9.0 regression", "", UNRESOLVED_APPID, "unresolved"),
        # issue-number reference "#12345" must be excluded
        ("Related to #12345", "", UNRESOLVED_APPID, "unresolved"),
        # no digits at all
        ("Discussion thread", "", UNRESOLVED_APPID, "unresolved"),
    ]
    fail_count = 0
    for title, body, exp_id, exp_rule in cases:
        got_id, got_rule = extract_appid(title, body)
        if got_id != exp_id or got_rule != exp_rule:
            print(f"  FAIL: title={title!r} body={body[:40]!r}"
                  f"\n        got=({got_id!r}, {got_rule!r})"
                  f"\n        expected=({exp_id!r}, {exp_rule!r})")
            fail_count += 1
    if fail_count == 0:
        print("appid_extractor: all tests passed.")
    else:
        print(f"appid_extractor: {fail_count} test(s) FAILED.")


if __name__ == "__main__":
    _run_tests()
