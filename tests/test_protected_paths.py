"""Unit tests for the centralized protected paths safety layer."""

from unittest.mock import patch

from crapcleaner.safety.protected_paths import (
    get_protected_rules_summary,
    get_protected_system_roots,
    is_path_protected,
    validate_cleanup_path,
)


def test_protected_system_roots():
    roots = get_protected_system_roots()
    assert len(roots) > 0
    paths = [p for p, _ in roots]
    assert all(isinstance(p, str) for p in paths)


def test_is_path_protected_git_and_ssh():
    assert is_path_protected("C:\\Projects\\repo\\.git")
    assert is_path_protected("/home/user/code/project/.git/HEAD")
    assert is_path_protected("C:\\Users\\User\\.ssh\\id_rsa")
    assert is_path_protected("/home/user/.ssh/known_hosts")


def test_is_path_protected_browser_credentials():
    assert is_path_protected(
        "C:\\Users\\User\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Login Data"
    )
    assert is_path_protected(
        "C:\\Users\\User\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\Cookies"
    )
    assert is_path_protected("/home/user/.mozilla/firefox/profile.default/key4.db")
    assert is_path_protected("/home/user/.mozilla/firefox/profile.default/logins.json")


def test_is_path_protected_system_roots():
    with patch("crapcleaner.safety.protected_paths.is_windows", return_value=True):
        with patch(
            "crapcleaner.safety.protected_paths.get_windows_dir", return_value="C:\\Windows"
        ):
            assert is_path_protected("C:\\Windows")
            assert is_path_protected("C:\\Windows\\System32")


def test_validate_cleanup_path():
    is_safe, msg = validate_cleanup_path("C:\\Users\\User\\AppData\\Local\\Temp\\junk123.tmp")
    assert is_safe
    assert "allowed" in msg.lower()

    is_safe_blocked, reason = validate_cleanup_path("C:\\Users\\User\\.ssh\\id_ed25519")
    assert not is_safe_blocked
    assert "Protected path blocked" in reason


def test_get_protected_rules_summary():
    summary = get_protected_rules_summary()
    assert len(summary) >= 3
    rule_types = {r["rule_type"] for r in summary}
    assert "Protected Root" in rule_types
    assert "Protected Directory Pattern" in rule_types
    assert "Protected File Pattern" in rule_types
