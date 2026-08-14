"""Tests for scan engine and directory size computation."""

from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.scanner.scanner import ScanEngine, scan_category
from crapcleaner.scanner.size import compute_dir_size


def _make_tree(tmp_path, spec):
    """spec: dict of relative path -> content bytes."""
    for rel, data in spec.items():
        full = tmp_path / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            full.write_bytes(data)
        else:
            full.write_text(data, encoding="utf-8")


class TestComputeDirSize:
    def test_sums_all_files(self, tmp_path):
        _make_tree(
            tmp_path,
            {
                "a.txt": "x" * 100,
                "sub/b.txt": "y" * 200,
                "sub/deep/c.bin": b"z" * 300,
            },
        )
        total, count, skipped = compute_dir_size(str(tmp_path))
        assert total == 600
        assert count == 3
        assert skipped == 0

    def test_patterns_filter(self, tmp_path):
        _make_tree(
            tmp_path,
            {
                "keep.log": "l" * 50,
                "other.txt": "t" * 100,
            },
        )
        total, count, _ = compute_dir_size(str(tmp_path), patterns=("*.log",))
        assert total == 50
        assert count == 1

    def test_no_recurse(self, tmp_path):
        _make_tree(
            tmp_path,
            {
                "a.txt": "x" * 10,
                "sub/b.txt": "y" * 20,
            },
        )
        total, count, _ = compute_dir_size(str(tmp_path), recurse=False)
        assert total == 10
        assert count == 1

    def test_missing_root(self):
        total, count, skipped = compute_dir_size("Z:\\does\\not\\exist")
        assert (total, count, skipped) == (0, 0, 0)

    def test_file_root_returns_zero(self, tmp_path):
        f = tmp_path / "single.txt"
        f.write_text("hello", encoding="utf-8")
        assert compute_dir_size(str(f)) == (0, 0, 0)


def _category(target_path, safety=SafetyLevel.SAFE, cid="test_cat"):
    return CleanupCategory(
        id=cid,
        name="Test category",
        description="desc",
        safety_level=safety,
        targets=[CacheTarget(path=target_path)],
    )


class TestScanCategory:
    def test_reports_size(self, tmp_path):
        _make_tree(tmp_path, {"f1.txt": "a" * 500, "f2.txt": "b" * 500})
        cat = _category(str(tmp_path))
        result = scan_category(cat)
        assert result.size == 1000
        assert result.item_count == 2
        assert result.errors == []

    def test_missing_target_zero(self, tmp_path):
        cat = _category(str(tmp_path / "nope"))
        result = scan_category(cat)
        assert result.size == 0
        assert result.item_count == 0

    def test_only_files_scan_single_file(self, tmp_path):
        f = tmp_path / "single.log"
        f.write_text("x" * 400, encoding="utf-8")
        cat = CleanupCategory(
            id="only_files_cat",
            name="Only-files cat",
            description="d",
            safety_level=SafetyLevel.SAFE,
            targets=[CacheTarget(path=str(f), only_files=True)],
        )
        result = scan_category(cat)
        assert result.size == 400
        assert result.item_count == 1

    def test_only_files_ignores_directory_target(self, tmp_path):
        _make_tree(tmp_path, {"a.txt": "x" * 100, "sub/b.txt": "y" * 200})
        cat = CleanupCategory(
            id="only_files_dir",
            name="Only-files on a dir",
            description="d",
            safety_level=SafetyLevel.SAFE,
            targets=[CacheTarget(path=str(tmp_path), only_files=True)],
        )
        result = scan_category(cat)
        assert result.size == 300
        assert result.item_count == 2

    def test_no_targets_short_circuits(self):
        cat = CleanupCategory(id="x", name="X", description="d", safety_level=SafetyLevel.SAFE)
        result = scan_category(cat)
        assert result.size == 0
        assert result.item_count == 0

    def test_finder_paths_included(self, tmp_path):
        _make_tree(tmp_path, {"cache/a.txt": "a" * 10})
        cat = CleanupCategory(
            id="finder_cat",
            name="Finder cat",
            description="d",
            safety_level=SafetyLevel.SAFE,
            finder=lambda: [str(tmp_path / "cache")],
            finder_args=(),
        )
        result = scan_category(cat)
        assert result.size == 10


class TestScanEngine:
    def test_runs_all_categories(self, tmp_path):
        _make_tree(tmp_path, {"f.txt": "x" * 100})
        cats = [
            _category(str(tmp_path), cid="c1"),
            _category(str(tmp_path / "empty"), cid="c2"),
        ]
        report = ScanEngine(cats).run()
        assert report.total_size == 100
        assert report.total_files == 1
        assert report.result_by_id("c1") is not None
        assert report.result_by_id("c2") is not None

    def test_cancel_stops(self, tmp_path):
        _make_tree(tmp_path, {"f.txt": "x" * 100})
        engine = ScanEngine([_category(str(tmp_path), cid="c1")])
        engine.request_stop()
        report = engine.run()
        assert report.cancelled is True

    def test_report_dict(self, tmp_path):
        _make_tree(tmp_path, {"f.txt": "x" * 100})
        report = ScanEngine([_category(str(tmp_path), cid="c1")]).run()
        d = report.to_dict()
        assert d["total_size"] == 100
        assert len(d["categories"]) == 1
