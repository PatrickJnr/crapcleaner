"""Regression tests for the confirmed findings of the 2026-08-20 audit.

Each test names the finding it locks down.
"""

import os
from unittest.mock import patch

from crapcleaner.categories.browsers import _build_browser_categories
from crapcleaner.core.cleaner import _delete_target_files, clean_categories


def _write(path: str, text: str = "payload") -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


# SAFE-01 - a protected file was refused by name and then deleted with its parent


def test_protected_file_is_not_deleted_with_its_parent_directory(tmp_path):
    target = tmp_path / "AppCache"
    profile = target / "profile"
    junk = _write(str(profile / "blob.dat"))
    cookies = _write(str(profile / "cookies"))
    key = _write(str(profile / "id_rsa"))

    deleted, _recovered, skipped, _errors, _perms, reasons = _delete_target_files(
        str(target),
        patterns=(),
        recurse=True,
        only_files=False,
        dry_run=False,
        stop_event=None,
        use_recycle_bin=False,
    )

    assert not os.path.exists(junk), "the unprotected file should still be cleaned"
    assert os.path.exists(cookies), "a refused credential must survive its parent directory"
    assert os.path.exists(key), "a refused credential must survive its parent directory"
    assert os.path.isdir(profile), "a directory holding refused files must not be removed"
    assert deleted == 1
    assert skipped == 2
    assert len(reasons) == 2


# SAFE-02 - the Recycle Bin fast path moved the whole tree without validating it


def test_recycle_fast_path_refuses_a_tree_holding_a_protected_file(tmp_path):
    target = tmp_path / "AppCache"
    junk = _write(str(target / "blob.dat"))
    cookies = _write(str(target / "cookies"))

    recycled_trees: list[str] = []
    recycled_files: list[str] = []

    def fake_recycle_tree(path: str) -> bool:
        recycled_trees.append(path)
        return True

    def fake_recycle_file(path: str) -> bool:
        recycled_files.append(path)
        os.remove(path)
        return True

    with (
        patch("crapcleaner.core.cleaner.recycle_tree", fake_recycle_tree),
        patch("crapcleaner.core.cleaner.recycle_file", fake_recycle_file),
    ):
        deleted, _recovered, skipped, _errors, _perms, reasons = _delete_target_files(
            str(target),
            patterns=(),
            recurse=True,
            only_files=False,
            dry_run=False,
            stop_event=None,
            use_recycle_bin=True,
        )

    assert recycled_trees == [], "a tree holding a protected file must not be recycled whole"
    assert recycled_files == [junk], "only the unprotected file should be recycled"
    assert os.path.exists(cookies)
    assert deleted == 1
    assert skipped == 1
    assert any("cookies" in reason for reason in reasons)


def test_recycle_fast_path_still_moves_a_clean_tree_in_one_call(tmp_path):
    target = tmp_path / "AppCache"
    _write(str(target / "blob.dat"))
    _write(str(target / "nested" / "other.dat"))

    recycled_trees: list[str] = []

    def fake_recycle_tree(path: str) -> bool:
        recycled_trees.append(path)
        return True

    with patch("crapcleaner.core.cleaner.recycle_tree", fake_recycle_tree):
        deleted, _recovered, skipped, _errors, _perms, _reasons = _delete_target_files(
            str(target),
            patterns=(),
            recurse=True,
            only_files=False,
            dry_run=False,
            stop_event=None,
            use_recycle_bin=True,
        )

    assert recycled_trees == [str(target)], "a clean tree should still go in a single move"
    assert deleted == 2
    assert skipped == 0


# CAT-01 - os.path.join(profile, *sub) unpacked the string one character at a time


def test_chromium_cache_targets_resolve_to_real_directories(tmp_path):
    root = tmp_path / "Chrome" / "User Data"
    for sub in ("Cache", "Code Cache", "GPUCache", "Service Worker"):
        (root / "Default" / sub).mkdir(parents=True)
    _write(str(root / "Default" / "Cache" / "data_0"))

    categories = _build_browser_categories("chrome", "Chrome", str(root))

    assert categories, "a profile directory should produce categories"
    for category in categories:
        for target in category.targets:
            assert os.path.isdir(target.path), f"{category.id} points at {target.path}"
            parts = target.path.split(os.sep)
            assert not any(len(part) == 1 for part in parts[1:]), (
                f"{category.id} built a character-split path: {target.path}"
            )

    cache = next(c for c in categories if c.id == "chrome_cache")
    assert [t.path for t in cache.targets] == [str(root / "Default" / "Cache")]


# BUG-01 - a cancelled cleanup reported zero after deleting hundreds of files


class _StopAfter:
    """A stop event that fires once the walk has processed `after` directories."""

    def __init__(self, after: int) -> None:
        self.after = after
        self.calls = 0

    def is_set(self) -> bool:
        self.calls += 1
        return self.calls > self.after


def test_cancelled_cleanup_reports_what_it_already_deleted(tmp_path):
    from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel

    target = tmp_path / "Cache"
    for folder in ("a", "b", "c", "d", "e"):
        for index in range(3):
            _write(str(target / folder / f"file{index}.dat"))
    before = sum(len(files) for _root, _dirs, files in os.walk(target))

    category = CleanupCategory(
        id="test_cache",
        name="Test cache",
        description="Fixture",
        safety_level=SafetyLevel.SAFE,
        targets=[CacheTarget(path=str(target))],
    )

    report = clean_categories([category], stop_event=_StopAfter(4))

    remaining = sum(len(files) for _root, _dirs, files in os.walk(target))
    gone = before - remaining
    assert gone > 0, "the fixture must delete something before the stop fires"
    assert remaining > 0, "the stop must actually interrupt the walk"
    assert report.results[0].files_deleted == gone
    assert report.results[0].space_recovered > 0
    assert "Cleanup stopped by user." in report.errors


# SEC-01 - an avatar URL from a writable cache file reached urlopen unchecked


def test_avatar_urls_are_restricted_to_github_over_https():
    from crapcleaner.utils.contributors import _is_github_avatar_url

    assert _is_github_avatar_url("https://avatars.githubusercontent.com/u/1?v=4")
    assert _is_github_avatar_url("https://github.com/a.png")
    assert not _is_github_avatar_url("file:///etc/shadow")
    assert not _is_github_avatar_url("http://avatars.githubusercontent.com/u/1")
    assert not _is_github_avatar_url("https://evil.test/payload.png")


def test_fetch_avatar_file_refuses_a_local_file_url():
    from crapcleaner.utils import contributors

    def explode(*_args, **_kwargs):
        raise AssertionError("a refused URL must never be opened")

    with patch.object(contributors.urllib.request, "urlopen", explode):
        assert contributors.fetch_avatar_file("file:///etc/shadow", "someone") is None


# SEC-02 - a read-only update check ran `sudo apt update`


def test_listing_apt_updates_does_not_run_a_privileged_refresh():
    from crapcleaner.system import package_managers

    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(list(command))
        return 0, "", ""

    with patch.object(package_managers, "_run", fake_run):
        package_managers._get_apt_updates()

    assert calls, "the check should still list upgradable packages"
    for command in calls:
        assert "sudo" not in command, f"a read-only check ran with sudo: {command}"
        assert "update" not in command, f"a read-only check refreshed the lists: {command}"


# SEC-03 - package ids scraped from output were appended to a root command


def test_safe_package_ids_rejects_option_shaped_names():
    from crapcleaner.utils.platform import safe_package_ids

    assert safe_package_ids(["firefox", "lib32-mesa", "python3.12"]) == [
        "firefox",
        "lib32-mesa",
        "python3.12",
    ]
    assert safe_package_ids(["-o", "--force", "", "-"]) == []


def test_install_update_refuses_an_option_shaped_package_id():
    from crapcleaner.system import package_managers

    def explode(*_args, **_kwargs):
        raise AssertionError("an unsafe id must never reach a package manager")

    with patch.object(package_managers, "_run", explode):
        ok, message = package_managers.install_update("apt", "--reinstall")

    assert ok is False
    assert "Refusing" in message
