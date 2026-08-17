"""DirectoryGuard must agree with validate_cleanup_path for every file it judges.

The guard is a scan-time optimisation that resolves a directory once instead of
resolving every file inside it. It is only safe if it reaches the same verdict as the
authoritative check, so these tests compare the two directly rather than asserting the
guard's behaviour in isolation.
"""

import os

import pytest

from crapcleaner.core.protected_paths import (
    DirectoryGuard,
    refresh_protection_cache,
    validate_cleanup_path,
)
from crapcleaner.utils.platform import get_local_appdata, get_user_profile, is_windows


@pytest.fixture(autouse=True)
def _clean_cache():
    refresh_protection_cache()
    yield
    refresh_protection_cache()


def _agree(directory: str, name: str) -> None:
    """The guard and the authoritative check must reach the same verdict."""
    guard = DirectoryGuard(directory)
    guard_verdict = guard.allows_file(name)
    strict_verdict, message = validate_cleanup_path(os.path.join(directory, name))
    assert guard_verdict == strict_verdict, (
        f"{directory!r} / {name!r}: guard={guard_verdict} strict={strict_verdict} ({message})"
    )


# ---------------------------------------------------------------------------
# Equivalence
# ---------------------------------------------------------------------------


def test_ordinary_cache_file_is_allowed_by_both(tmp_path):
    cache_dir = tmp_path / "SomeApp" / "Cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "blob.tmp").write_bytes(b"x")
    _agree(str(cache_dir), "blob.tmp")


@pytest.mark.parametrize(
    "name",
    ["id_rsa", "known_hosts", "logins.json", "key4.db", "NTUSER.DAT", "cookies"],
)
def test_protected_filenames_blocked_by_both(tmp_path, name):
    folder = tmp_path / "data"
    folder.mkdir()
    (folder / name).write_bytes(b"x")
    _agree(str(folder), name)


@pytest.mark.parametrize("protected_dir", [".git", ".ssh", ".gnupg", ".aws", ".kube"])
def test_protected_directory_components_blocked_by_both(tmp_path, protected_dir):
    folder = tmp_path / "project" / protected_dir / "objects"
    folder.mkdir(parents=True)
    (folder / "somefile.tmp").write_bytes(b"x")
    _agree(str(folder), "somefile.tmp")

    guard = DirectoryGuard(str(folder))
    assert guard.directory_allowed is False
    assert guard.reason


def test_browser_credential_file_blocked_by_both(tmp_path):
    profile = tmp_path / "Google" / "Chrome" / "User Data" / "Default"
    profile.mkdir(parents=True)
    (profile / "Login Data").write_bytes(b"x")
    _agree(str(profile), "Login Data")


def test_a_file_named_like_a_protected_directory_is_blocked(tmp_path):
    """`.git` as a *file* must be refused too, matching the strict check."""
    folder = tmp_path / "weird"
    folder.mkdir()
    (folder / ".git").write_bytes(b"gitdir: ../real")
    _agree(str(folder), ".git")


def test_user_exclusions_are_honoured(tmp_path):
    excluded = tmp_path / "keep-me"
    excluded.mkdir()
    (excluded / "file.tmp").write_bytes(b"x")

    rules = [str(excluded)]
    guard = DirectoryGuard(str(excluded), exclusions=rules)
    assert guard.directory_allowed is False

    allowed, message = validate_cleanup_path(str(excluded / "file.tmp"), exclusions=rules)
    assert allowed is False
    assert "exclusion" in message.lower()


# ---------------------------------------------------------------------------
# The regression this design nearly introduced
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not is_windows(), reason="Windows protected roots")
def test_files_directly_inside_a_protected_root_are_still_scannable():
    """A protected root must not block its own contents.

    The exact-root rule exists to stop the root itself being deleted. Real cleanup
    categories scan directly inside %LOCALAPPDATA%, so treating the root match as a
    directory-level failure would silently return zero results for them.
    """
    local = get_local_appdata()
    assert local, "LOCALAPPDATA should be set on Windows"

    guard = DirectoryGuard(local)
    assert guard.directory_allowed is True
    assert guard.allows_file("some_cache_file.tmp") is True
    _agree(local, "some_cache_file.tmp")


def test_the_root_itself_is_still_protected():
    root = get_user_profile()
    allowed, message = validate_cleanup_path(root)
    assert allowed is False
    assert "protected" in message.lower()


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------


def test_exclusion_changes_are_picked_up_after_a_refresh(tmp_path, monkeypatch):
    folder = tmp_path / "cache"
    folder.mkdir()

    settings = {"excluded_paths": []}
    monkeypatch.setattr("crapcleaner.config.load_settings", lambda: dict(settings))

    refresh_protection_cache()
    assert DirectoryGuard(str(folder)).directory_allowed is True

    settings["excluded_paths"] = [str(folder)]
    refresh_protection_cache()
    assert DirectoryGuard(str(folder)).directory_allowed is False


def test_settings_are_not_read_once_per_file(tmp_path, monkeypatch):
    """The default path must not touch config.json for every candidate file."""
    calls = {"n": 0}

    def counting_load():
        calls["n"] += 1
        return {"excluded_paths": []}

    monkeypatch.setattr("crapcleaner.config.load_settings", counting_load)
    refresh_protection_cache()

    folder = tmp_path / "many"
    folder.mkdir()
    guard = DirectoryGuard(str(folder))
    for i in range(200):
        guard.allows_file(f"file{i}.tmp")

    assert calls["n"] <= 1
