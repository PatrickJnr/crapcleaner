"""Unit tests for the centralized protected paths safety layer.

Backslash paths are only path separators on Windows; on Linux "C:\\x\\.git" is a
single filename, so Windows-shaped literals are asserted only on Windows and the
POSIX equivalents carry the coverage elsewhere.
"""

from unittest.mock import patch

import pytest

from crapcleaner.core.protected_paths import (
    explain_protection,
    get_protected_rules_summary,
    get_protected_system_roots,
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


def test_protects_git_and_ssh():
    assert explain_protection("/home/user/code/project/.git/HEAD")
    assert explain_protection("/home/user/.ssh/known_hosts")
    assert explain_protection("/home/user/.ssh/id_ed25519")
    assert explain_protection("/home/user/.gnupg/secring.gpg")


@windows_only
def test_protects_git_and_ssh_windows():
    assert explain_protection("C:\\Projects\\repo\\.git")
    assert explain_protection("C:\\Users\\User\\.ssh\\id_rsa")


def test_protects_browser_credentials():
    assert explain_protection("/home/user/.mozilla/firefox/profile.default/key4.db")
    assert explain_protection("/home/user/.mozilla/firefox/profile.default/logins.json")
    assert explain_protection("/home/user/.config/google-chrome/Default/Login Data")
    assert explain_protection("/home/user/.config/google-chrome/Default/Cookies")


@windows_only
def test_protects_browser_credentials_windows():
    assert explain_protection(
        "C:\\Users\\User\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Login Data"
    )
    assert explain_protection(
        "C:\\Users\\User\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\Cookies"
    )


@windows_only
def test_protects_system_roots_windows():
    with patch("crapcleaner.core.protected_paths.get_windows_dir", return_value="C:\\Windows"):
        assert explain_protection("C:\\Windows")
        assert explain_protection("C:\\Windows\\System32")


@linux_only
def test_protects_system_roots_linux():
    for root in ("/etc", "/usr", "/boot", "/proc"):
        assert explain_protection(root) is not None, root


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
