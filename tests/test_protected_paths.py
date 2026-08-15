"""Unit tests for the centralized protected paths safety layer.

Backslash paths are only path separators on Windows; on Linux "C:\\x\\.git" is a
single filename, so Windows-shaped literals are asserted only on Windows and the
POSIX equivalents carry the coverage elsewhere.
"""

from unittest.mock import patch

import pytest

from crapcleaner.safety.protected_paths import (
    get_protected_rules_summary,
    get_protected_system_roots,
    is_path_protected,
    validate_cleanup_path,
)
from crapcleaner.utils.platform import is_windows

windows_only = pytest.mark.skipif(not is_windows(), reason="Windows path semantics")
linux_only = pytest.mark.skipif(is_windows(), reason="POSIX path semantics")


def test_protected_system_roots():
    roots = get_protected_system_roots()
    assert len(roots) > 0
    paths = [p for p, _ in roots]
    assert all(isinstance(p, str) for p in paths)


def test_is_path_protected_git_and_ssh():
    assert is_path_protected("/home/user/code/project/.git/HEAD")
    assert is_path_protected("/home/user/.ssh/known_hosts")
    assert is_path_protected("/home/user/.ssh/id_ed25519")
    assert is_path_protected("/home/user/.gnupg/secring.gpg")


@windows_only
def test_is_path_protected_git_and_ssh_windows():
    assert is_path_protected("C:\\Projects\\repo\\.git")
    assert is_path_protected("C:\\Users\\User\\.ssh\\id_rsa")


def test_is_path_protected_browser_credentials():
    assert is_path_protected("/home/user/.mozilla/firefox/profile.default/key4.db")
    assert is_path_protected("/home/user/.mozilla/firefox/profile.default/logins.json")
    assert is_path_protected("/home/user/.config/google-chrome/Default/Login Data")
    assert is_path_protected("/home/user/.config/google-chrome/Default/Cookies")


@windows_only
def test_is_path_protected_browser_credentials_windows():
    assert is_path_protected(
        "C:\\Users\\User\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Login Data"
    )
    assert is_path_protected(
        "C:\\Users\\User\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\Cookies"
    )


@windows_only
def test_is_path_protected_system_roots_windows():
    with patch("crapcleaner.safety.protected_paths.get_windows_dir", return_value="C:\\Windows"):
        assert is_path_protected("C:\\Windows")
        assert is_path_protected("C:\\Windows\\System32")


@linux_only
def test_is_path_protected_system_roots_linux():
    for root in ("/etc", "/usr", "/boot", "/proc"):
        assert is_path_protected(root), root


def test_ordinary_cache_path_is_not_protected(tmp_path):
    junk = tmp_path / "cache" / "junk123.tmp"
    junk.parent.mkdir(parents=True)
    junk.write_text("x", encoding="utf-8")
    is_safe, msg = validate_cleanup_path(str(junk))
    assert is_safe
    assert "allowed" in msg.lower()


def test_validate_cleanup_path_blocks_credentials():
    is_safe, reason = validate_cleanup_path("/home/user/.ssh/id_ed25519")
    assert not is_safe
    assert "Protected path blocked" in reason


@windows_only
def test_validate_cleanup_path_blocks_credentials_windows():
    is_safe, reason = validate_cleanup_path("C:\\Users\\User\\.ssh\\id_ed25519")
    assert not is_safe
    assert "Protected path blocked" in reason


def test_get_protected_rules_summary():
    summary = get_protected_rules_summary()
    assert len(summary) >= 3
    rule_types = {r["rule_type"] for r in summary}
    assert "Protected Root" in rule_types
    assert "Protected Directory Pattern" in rule_types
    assert "Protected File Pattern" in rule_types
