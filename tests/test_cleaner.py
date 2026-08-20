"""Tests for the cleanup engine."""

import json
import os
from datetime import datetime

import crapcleaner.core.cleaner as cleaner_mod
from crapcleaner.core.cleaner import clean_categories
from crapcleaner.core.manifest import MAX_MANIFESTS, read_manifest, write_manifest
from crapcleaner.core.size import compute_dir_size
from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.models.report import CleanupReport, RemovedPath
from crapcleaner.utils.files import remove_tree


def _make_tree(tmp_path, spec):
    for rel, data in spec.items():
        full = tmp_path / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(data, encoding="utf-8")


def _category(target_path, safety=SafetyLevel.SAFE, cid="test_cat", patterns=()):
    return CleanupCategory(
        id=cid,
        name="Test category",
        description="desc",
        safety_level=safety,
        targets=[CacheTarget(path=target_path, patterns=patterns)],
    )


class TestCleanCategories:
    def test_deletes_files(self, tmp_path):
        _make_tree(tmp_path, {"a.txt": "x" * 100, "b.log": "y" * 50})
        report = clean_categories([_category(str(tmp_path))], dry_run=False)
        assert report.total_files_deleted == 2
        assert report.total_space_recovered == 150
        assert not os.path.exists(tmp_path / "a.txt")

    def test_dry_run_deletes_nothing(self, tmp_path):
        _make_tree(tmp_path, {"a.txt": "x" * 100})
        report = clean_categories([_category(str(tmp_path))], dry_run=True)
        assert report.total_files_deleted == 1
        assert report.dry_run is True
        assert os.path.exists(tmp_path / "a.txt")

    def test_patterns_only(self, tmp_path):
        _make_tree(tmp_path, {"a.log": "x" * 100, "b.txt": "y" * 50})
        report = clean_categories([_category(str(tmp_path), patterns=("*.log",))], dry_run=False)
        assert report.total_files_deleted == 1
        assert report.total_space_recovered == 100
        assert os.path.exists(tmp_path / "b.txt")

    def test_missing_target_is_ok(self, tmp_path):
        report = clean_categories([_category(str(tmp_path / "nope"))], dry_run=False)
        assert report.total_files_deleted == 0
        assert report.errors == []

    def test_dangerous_never_deleted(self, tmp_path):
        _make_tree(tmp_path, {"a.txt": "x"})
        cat = _category(str(tmp_path), safety=SafetyLevel.DANGEROUS, cid="danger")
        report = clean_categories([cat], dry_run=False)
        assert report.total_files_deleted == 0
        assert os.path.exists(tmp_path / "a.txt")
        assert any("DANGEROUS" in e for r in report.results for e in r.errors)

    def test_missing_targets_in_report(self, tmp_path):
        _make_tree(tmp_path, {"a.txt": "x" * 10})
        report = clean_categories([_category(str(tmp_path))], dry_run=False)
        r = report.results[0]
        assert r.category_id == "test_cat"
        assert r.files_deleted == 1
        assert r.space_recovered == 10

    def test_multiple_categories(self, tmp_path):
        _make_tree(tmp_path, {"a.txt": "x" * 10})
        cat2 = _category(str(tmp_path / "nope"), cid="missing")
        report = clean_categories(
            [_category(str(tmp_path), cid="c1"), cat2],
            dry_run=False,
        )
        assert len(report.results) == 2
        assert report.results[0].files_deleted == 1
        assert report.results[1].files_deleted == 0


class TestRecycleBin:
    def test_whole_tree_recycled_in_one_call(self, tmp_path, monkeypatch):
        _make_tree(tmp_path, {"a.txt": "x" * 100, "sub/b.txt": "y" * 50})
        calls = []
        monkeypatch.setattr(cleaner_mod, "recycle_tree", lambda p: calls.append(p) or True)
        report = clean_categories([_category(str(tmp_path))], dry_run=False, use_recycle_bin=True)
        assert report.use_recycle_bin is True
        assert report.total_files_deleted == 2
        assert report.total_space_recovered == 150
        assert calls == [str(tmp_path)]

    def test_single_file_recycled(self, tmp_path, monkeypatch):
        _make_tree(tmp_path, {"a.txt": "x" * 10})
        target = tmp_path / "a.txt"
        calls = []
        monkeypatch.setattr(cleaner_mod, "recycle_file", lambda p: calls.append(p) or True)
        cat = CleanupCategory(
            id="t",
            name="T",
            description="d",
            safety_level=SafetyLevel.SAFE,
            targets=[CacheTarget(path=str(target), only_files=True)],
        )
        report = clean_categories([cat], dry_run=False, use_recycle_bin=True)
        assert report.total_files_deleted == 1
        assert calls == [str(target)]

    def test_permanent_mode_never_recycles(self, tmp_path, monkeypatch):
        _make_tree(tmp_path, {"a.txt": "x" * 10})

        def boom(path):
            raise AssertionError("recycle used in permanent mode")

        monkeypatch.setattr(cleaner_mod, "recycle_file", boom)
        monkeypatch.setattr(cleaner_mod, "recycle_tree", boom)
        report = clean_categories([_category(str(tmp_path))], dry_run=False, use_recycle_bin=False)
        assert report.use_recycle_bin is False
        assert report.total_files_deleted == 1
        assert not os.path.exists(tmp_path / "a.txt")

    def test_dry_run_recycle_reports_nothing_deleted(self, tmp_path, monkeypatch):
        _make_tree(tmp_path, {"a.txt": "x" * 10})
        monkeypatch.setattr(
            cleaner_mod,
            "recycle_tree",
            lambda p: (_ for _ in ()).throw(AssertionError()),
        )
        report = clean_categories([_category(str(tmp_path))], dry_run=True, use_recycle_bin=True)
        assert report.dry_run is True
        assert report.total_files_deleted == 1
        assert os.path.exists(tmp_path / "a.txt")


class TestScanAndCleanupAgreeOnPatterns:
    """BUG-03: the scan's suffix fast path matched extensionless names fnmatch refuses."""

    #: Real names that end in the pattern's letters without the dot.
    DECOYS = ("catalog", "backlog", "changelog", "dialog", "notepf", "xpf")

    def _tree(self, tmp_path):
        _make_tree(
            tmp_path,
            {name: "decoy" for name in self.DECOYS} | {"app.log": "x" * 50, "boot.pf": "y" * 30},
        )

    def test_scan_counts_only_what_fnmatch_would_delete(self, tmp_path):
        self._tree(tmp_path)

        total, count, _skipped = compute_dir_size(str(tmp_path), patterns=("*.log", "*.pf"))

        assert count == 2
        assert total == 80

    def test_scan_size_matches_the_cleanup_it_promises(self, tmp_path):
        self._tree(tmp_path)
        category = _category(str(tmp_path), patterns=("*.log", "*.pf"))

        total, _count, _skipped = compute_dir_size(str(tmp_path), patterns=("*.log", "*.pf"))
        report = clean_categories([category], dry_run=True)

        assert report.total_space_recovered == total

    def test_a_wildcard_in_the_middle_still_matches(self, tmp_path):
        _make_tree(tmp_path, {"cache_v2.tmp": "x", "cache_v2.keep": "y"})

        _total, count, _skipped = compute_dir_size(str(tmp_path), patterns=("cache*.tmp",))

        assert count == 1


class TestCleanupManifest:
    """FEAT-06: history stored counts only, so nothing could say what was removed."""

    def _run(self, tmp_path, config_home, monkeypatch, **kwargs):
        monkeypatch.setattr(cleaner_mod, "config_dir", lambda: str(config_home))
        return clean_categories([_category(str(tmp_path))], **kwargs)

    def test_a_run_records_every_path_it_removed(self, tmp_path, monkeypatch):
        config_home = tmp_path / "config"
        junk = tmp_path / "junk"
        _make_tree(junk, {"a.tmp": "aaa", "nested/b.tmp": "bb"})

        report = self._run(junk, config_home, monkeypatch)

        stored = read_manifest(report.manifest_path)
        assert {item["path"] for item in stored["items"]} == {
            str(junk / "a.tmp"),
            str(junk / "nested" / "b.tmp"),
        }
        assert sum(item["size"] for item in stored["items"]) == 5
        assert all(item["recycled"] is False for item in stored["items"])

    def test_a_dry_run_writes_nothing(self, tmp_path, monkeypatch):
        config_home = tmp_path / "config"
        junk = tmp_path / "junk"
        _make_tree(junk, {"a.tmp": "aaa"})

        report = self._run(junk, config_home, monkeypatch, dry_run=True)

        assert report.manifest_path == ""
        assert not (config_home / "cleanup_manifests").exists()

    def test_a_recycled_tree_is_one_entry_carrying_its_file_count(self, tmp_path, monkeypatch):
        config_home = tmp_path / "config"
        junk = tmp_path / "junk"
        _make_tree(junk, {"a.tmp": "aaa", "nested/b.tmp": "bb"})
        monkeypatch.setattr(cleaner_mod, "recycle_tree", lambda path: remove_tree(path))

        report = self._run(junk, config_home, monkeypatch, use_recycle_bin=True)

        stored = read_manifest(report.manifest_path)
        assert stored["items"] == [
            {"path": str(junk), "size": 5, "recycled": True, "file_count": 2}
        ]

    def test_paths_stay_out_of_the_serialised_report(self, tmp_path, monkeypatch):
        config_home = tmp_path / "config"
        junk = tmp_path / "junk"
        _make_tree(junk, {"secret_name.tmp": "aaa"})

        report = self._run(junk, config_home, monkeypatch)

        assert "secret_name" not in json.dumps(report.to_dict())

    def test_only_the_newest_runs_are_kept(self, tmp_path, monkeypatch):
        config_home = tmp_path / "config"
        directory = str(config_home / "cleanup_manifests")
        for minute in range(MAX_MANIFESTS + 5):
            report = CleanupReport(started=datetime(2026, 1, 1, 0, minute))
            report.removed.append(RemovedPath(f"c:/junk/{minute}.tmp", 1, False))
            write_manifest(report, str(config_home))

        kept = sorted(os.listdir(directory))
        assert len(kept) == MAX_MANIFESTS
        assert kept[0].startswith("20260101-000500")

    def test_an_unreadable_manifest_reads_as_empty(self, tmp_path):
        broken = tmp_path / "broken.json"
        broken.write_text("{not json", encoding="utf-8")

        assert read_manifest(str(broken)) == {}
        assert read_manifest(str(tmp_path / "missing.json")) == {}
