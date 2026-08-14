"""Tests for the cleanup engine."""

import os

import crapcleaner.cleaners.cleaner as cleaner_mod
from crapcleaner.cleaners.cleaner import clean_categories
from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel


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
