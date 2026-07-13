"""
Unit tests for the AppID extractor.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.appid_extractor import extract_appid
from src.config import UNRESOLVED_APPID


def test_parentheses_rule_standard():
    """Rule 1: parentheses at the end of the title, standard 4-7 digit appid."""
    appid, rule = extract_appid("Disgaea PC (405900)", "")
    assert appid == "405900", f"got {appid}"
    assert rule == "parentheses"

    appid, rule = extract_appid("Some DLC (1234567)", "")
    assert appid == "1234567"
    assert rule == "parentheses"


def test_parentheses_rule_three_digit():
    """Rule 1: support 3-digit appid (early Steam games)."""
    # Half-Life 2 appid = 220
    appid, rule = extract_appid("Half-Life 2 (220)", "")
    assert appid == "220", f"got {appid}"
    assert rule == "parentheses"

    # The Elder Scrolls V: Skyrim Special Edition
    appid, rule = extract_appid("The Elder Scrolls V: Skyrim Special Edition (489830)", "")
    assert appid == "489830"
    assert rule == "parentheses"


def test_steam_url_rule():
    """Rule 2: Steam store URL in the body (supports 3-7 digit appid)."""
    body = "Game page: https://store.steampowered.com/app/220/Half-Life_2"
    appid, rule = extract_appid("No id in title here", body)
    assert appid == "220", f"got {appid}"
    assert rule == "steam_url"

    body2 = "https://store.steampowered.com/app/489830"
    appid, rule = extract_appid("No id in title", body2)
    assert appid == "489830"
    assert rule == "steam_url"

    # Rule 1 takes priority over rule 2
    appid, rule = extract_appid("Game (12345)", "https://store.steampowered.com/app/22222")
    assert rule == "parentheses"


def test_standalone_rule():
    """Rule 3: standalone 4-7 digit integer in the title (conservative fallback)."""
    appid, rule = extract_appid("12345 - Game crashes at launch", "")
    assert appid == "12345", f"got {appid}"
    assert rule == "standalone"


def test_standalone_false_positive_prevention():
    """Rule 3 must not mistakenly match version numbers or issue numbers."""
    # "Proton 9.0": 9 is only 1 digit, no other 4-7 digit number -> unresolved
    appid, rule = extract_appid("Proton 9.0 regression", "")
    assert appid == UNRESOLVED_APPID, f"should be unresolved, got {appid}"

    # "#12345" reference prefix -> excluded by negative lookbehind -> unresolved
    appid, rule = extract_appid("Related to #12345", "")
    assert appid == UNRESOLVED_APPID, f"#-prefixed number should be unresolved, got {appid}"

    # No digits at all
    appid, rule = extract_appid("Discussion about Proton features", "")
    assert appid == UNRESOLVED_APPID

    # Fewer than 4 digits (3 digits do not match in standalone)
    appid, rule = extract_appid("Issue 999 discussion", "")
    assert appid == UNRESOLVED_APPID


def test_unresolved():
    """Return UNRESOLVED when none of the three rules match."""
    appid, rule = extract_appid("Discussion about Proton features", "")
    assert appid == UNRESOLVED_APPID
    assert rule == "unresolved"

    appid, rule = extract_appid("", "")
    assert appid == UNRESOLVED_APPID


def test_priority_order():
    """Ensure rule priority: parentheses > steam_url > standalone."""
    # Title has parentheses + body has steam url: rule 1 wins
    appid, rule = extract_appid(
        "Game (11111)",
        "https://store.steampowered.com/app/22222"
    )
    assert appid == "11111"
    assert rule == "parentheses"

    # Title has no parentheses, body has steam url, title has standalone number: rule 2 wins
    appid, rule = extract_appid(
        "Game crash 33333",
        "https://store.steampowered.com/app/22222"
    )
    assert appid == "22222"
    assert rule == "steam_url"


if __name__ == "__main__":
    test_parentheses_rule_standard()
    print("  ✓ test_parentheses_rule_standard")
    test_parentheses_rule_three_digit()
    print("  ✓ test_parentheses_rule_three_digit")
    test_steam_url_rule()
    print("  ✓ test_steam_url_rule")
    test_standalone_rule()
    print("  ✓ test_standalone_rule")
    test_standalone_false_positive_prevention()
    print("  ✓ test_standalone_false_positive_prevention")
    test_unresolved()
    print("  ✓ test_unresolved")
    test_priority_order()
    print("  ✓ test_priority_order")
    print("All appid_extractor tests passed.")
