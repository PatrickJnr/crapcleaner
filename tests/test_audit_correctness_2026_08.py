"""Regression tests for the 2026-08-19 audit: correctness findings.

Finding IDs refer to audit.md.
"""

import json
import os
import time

import pytest

from crapcleaner.analysis.duplicates import find_duplicates
from crapcleaner.analysis.large_files import scan_large_files
from crapcleaner.analysis.old_files import find_old_files
from crapcleaner.core.cache import MAX_CACHE_ENTRIES, ScanCache
from crapcleaner.core.preview import generate_cleanup_preview
from crapcleaner.core.scanner import scan_category
from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel


def _write(path: str, data: str = "x") -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(data)
    return path


def _category(root: str, **target_kwargs) -> CleanupCategory:
    return CleanupCategory(
        id="probe",
        name="Probe",
        group="Testing",
        description="",
        safety_level=SafetyLevel.SAFE,
        targets=[CacheTarget(path=root, **target_kwargs)],
    )


class TestPreviewTotalsCoverEverything:
    """BUG-01: the walk stopped at the item cap, so the totals stopped with it."""

    def test_totals_exceed_the_item_cap(self, tmp_path):
        root = tmp_path / "cache"
        for i in range(25):
            _write(str(root / f"f{i}.bin"), "0123456789")

        preview = generate_cleanup_preview([_category(str(root))], max_items_per_category=5)
        category = preview.categories[0]

        assert category.item_count == 25, "count stopped at the display cap"
        assert category.estimated_size == 250, "size stopped at the display cap"
        assert len(category.items) == 5
        assert category.items_truncated is True

    def test_totals_match_the_scan_for_the_same_target(self, tmp_path):
        root = tmp_path / "cache"
        for i in range(30):
            _write(str(root / "deep" / f"f{i}.bin"), "abcd")

        scanned = scan_category(_category(str(root)))
        preview = generate_cleanup_preview([_category(str(root))], max_items_per_category=4)

        assert preview.categories[0].estimated_size == scanned.size
        assert preview.categories[0].item_count == scanned.item_count

    def test_small_category_is_not_marked_truncated(self, tmp_path):
        root = tmp_path / "cache"
        _write(str(root / "one.bin"), "abc")

        preview = generate_cleanup_preview([_category(str(root))], max_items_per_category=50)

        assert preview.categories[0].items_truncated is False


class TestLargeFileSkipListMatchesNames:
    """BUG-02: the skip list was matched as a substring of the whole path."""

    def test_folder_whose_name_contains_windows_is_scanned(self, tmp_path):
        target = _write(
            str(tmp_path / "Games" / "MyGame" / "WindowsNoEditor" / "data.pak"), "P" * 512
        )

        found = [item.path for item in scan_large_files(str(tmp_path), threshold_bytes=1)]

        assert target in found

    def test_programdata_substring_does_not_hide_a_folder(self, tmp_path):
        target = _write(str(tmp_path / "MyProgramDataBackup" / "big.bin"), "B" * 512)

        found = [item.path for item in scan_large_files(str(tmp_path), threshold_bytes=1)]

        assert target in found

    def test_node_modules_is_still_skipped_by_name(self, tmp_path):
        _write(str(tmp_path / "proj" / "node_modules" / "lib.js"), "J" * 512)
        keep = _write(str(tmp_path / "proj" / "app.js"), "J" * 512)

        found = [item.path for item in scan_large_files(str(tmp_path), threshold_bytes=1)]

        assert found == [keep]

    @pytest.mark.skipif(os.name != "nt", reason="anchored to the real Windows directory")
    def test_the_real_windows_directory_is_skipped(self):
        from crapcleaner.analysis.large_files import _should_skip_dir
        from crapcleaner.utils.platform import get_windows_dir

        assert _should_skip_dir(get_windows_dir()) is True
        assert _should_skip_dir(os.path.join(get_windows_dir(), "System32")) is True


class TestOldFilesReturnsTheOldest:
    """BUG-03: the walk stopped at max_results, returning the first files found."""

    def test_the_oldest_files_win_regardless_of_walk_order(self, tmp_path):
        now = time.time()
        # Newer files in a directory the walk reaches first, older ones deeper.
        for i in range(5):
            path = _write(str(tmp_path / "a_first" / f"new{i}.bin"), "x")
            os.utime(path, (now - 100 * 86400, now - 100 * 86400))
        oldest = []
        for i in range(3):
            path = _write(str(tmp_path / "z_last" / f"old{i}.bin"), "x")
            os.utime(path, (now - 900 * 86400, now - 900 * 86400))
            oldest.append(path)

        results = find_old_files(str(tmp_path), min_age_days=30, max_results=3)

        assert {item.path for item in results} == set(oldest)

    def test_results_are_ordered_oldest_first(self, tmp_path):
        now = time.time()
        for age in (700, 200, 400):
            path = _write(str(tmp_path / f"f{age}.bin"), "x")
            os.utime(path, (now - age * 86400, now - age * 86400))

        results = find_old_files(str(tmp_path), min_age_days=30, max_results=10)

        assert [r.age_days for r in results] == sorted([r.age_days for r in results], reverse=True)

    def test_recent_files_are_excluded(self, tmp_path):
        _write(str(tmp_path / "fresh.bin"), "x")

        assert find_old_files(str(tmp_path), min_age_days=30) == []


class TestScanTruncationIsVisible:
    """BUG-04: the file budget capped totals with no signal to anyone."""

    def test_hitting_the_budget_sets_the_flag_and_explains_itself(self, tmp_path):
        root = tmp_path / "many"
        for i in range(20):
            _write(str(root / f"f{i}.bin"), "x")

        result = scan_category(_category(str(root)), max_files=5)

        assert result.truncated is True
        assert any("budget" in error for error in result.errors)

    def test_a_complete_scan_is_not_flagged(self, tmp_path):
        root = tmp_path / "few"
        _write(str(root / "a.bin"), "x")

        result = scan_category(_category(str(root)), max_files=1000)

        assert result.truncated is False
        assert result.errors == []

    def test_a_truncated_result_is_never_cached(self, tmp_path):
        root = tmp_path / "many"
        for i in range(20):
            _write(str(root / f"f{i}.bin"), "x")
        cache = ScanCache(ttl=300.0, path=str(tmp_path / "cache.json"))

        scan_category(_category(str(root)), max_files=5, cache=cache)

        assert cache.get_dir(str(root), (), True, False, 5) is None


class TestScanCacheIsPruned:
    """BUG-05: entries accumulated forever and were re-parsed on every start."""

    def test_expired_entries_are_dropped_on_save(self, tmp_path):
        path = str(tmp_path / "cache.json")
        cache = ScanCache(ttl=1.0, path=path)
        target = tmp_path / "dir"
        target.mkdir()
        cache.put_dir(str(target), (), True, False, 100, 1, 1, 0)
        # Age the entry well past the keep window (ttl * 4, floor of one hour).
        for entry in cache._entries.values():
            entry["cached_at"] = time.time() - 7200

        cache.save()

        assert not os.path.exists(path) or json.loads(open(path).read())["entries"] == {}

    def test_entry_count_is_capped(self, tmp_path):
        path = str(tmp_path / "cache.json")
        cache = ScanCache(ttl=300.0, path=path)
        now = time.time()
        cache._entries = {
            f"key-{i}": {
                "total": 1,
                "count": 1,
                "skipped": 0,
                "probe": [],
                "cached_at": now - i * 0.001,
            }
            for i in range(MAX_CACHE_ENTRIES + 250)
        }

        cache.save()

        with open(path, encoding="utf-8") as fh:
            assert len(json.load(fh)["entries"]) == MAX_CACHE_ENTRIES

    def test_fresh_entries_survive(self, tmp_path):
        path = str(tmp_path / "cache.json")
        cache = ScanCache(ttl=300.0, path=path)
        target = tmp_path / "dir"
        target.mkdir()
        cache.put_dir(str(target), (), True, False, 100, 5, 2, 0)

        cache.save()

        assert ScanCache(ttl=300.0, path=path).get_dir(str(target), (), True, False, 100) == (
            5,
            2,
            0,
        )


class TestHardlinksAreNotReclaimableSpace:
    """BUG-06: a second name for one file was reported as a duplicate copy."""

    @pytest.fixture
    def linked(self, tmp_path):
        payload = "content-" * 200
        first = _write(str(tmp_path / "a.bin"), payload)
        second = str(tmp_path / "b.bin")
        try:
            os.link(first, second)
        except (OSError, NotImplementedError, AttributeError) as exc:
            pytest.skip(f"hardlinks unavailable here: {exc}")
        return first, second

    def test_hardlinked_names_are_not_offered_as_duplicates(self, linked, tmp_path):
        groups = find_duplicates([str(tmp_path)], min_size_bytes=1)

        assert groups == []

    def test_a_real_copy_alongside_a_hardlink_reports_one_reclaimable_copy(self, linked, tmp_path):
        first, _second = linked
        with open(first, encoding="utf-8") as fh:
            payload = fh.read()
        _write(str(tmp_path / "copy" / "c.bin"), payload)

        groups = find_duplicates([str(tmp_path)], min_size_bytes=1)

        assert len(groups) == 1
        assert groups[0].duplicate_count == 1
        assert groups[0].reclaimable == groups[0].size
        assert len(groups[0].hardlinks) == 1


class TestHistoryIsBounded:
    """BUG-08: the log grew without limit and was read whole on every refresh."""

    def test_the_file_is_trimmed_to_the_cap(self, tmp_path, monkeypatch):
        from datetime import datetime

        from crapcleaner import history as history_module
        from crapcleaner.models.history import HistoryEntry

        monkeypatch.setattr(history_module, "config_dir", lambda: str(tmp_path))
        monkeypatch.setattr(history_module, "MAX_ENTRIES", 10)
        for _ in range(25):
            history_module.append(HistoryEntry(kind="scan", started=datetime.now()))

        with open(history_module.history_path(), encoding="utf-8") as fh:
            assert sum(1 for _ in fh) == 10

    def test_load_returns_the_newest_entries(self, tmp_path, monkeypatch):
        from datetime import datetime

        from crapcleaner import history as history_module
        from crapcleaner.models.history import HistoryEntry

        monkeypatch.setattr(history_module, "config_dir", lambda: str(tmp_path))
        for i in range(12):
            history_module.append(
                HistoryEntry(kind="scan", started=datetime.now(), total_identified=i)
            )

        entries = history_module.load(limit=3)

        assert [e.total_identified for e in entries] == [9, 10, 11]
