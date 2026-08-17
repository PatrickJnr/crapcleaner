"""Storage analysis: correctness under parallelism, cancellation, and progress."""

import os
import threading

import pytest

from crapcleaner.analysis.file_types import analyze_file_types
from crapcleaner.analysis.storage import analyze_storage_hierarchy


@pytest.fixture
def tree(tmp_path):
    """A deterministic tree: 6 tops x 4 subs x 10 files of 100 bytes."""
    for a in range(6):
        for b in range(4):
            d = tmp_path / f"top{a}" / f"sub{b}"
            d.mkdir(parents=True)
            for f in range(10):
                (d / f"f{f}.bin").write_bytes(b"x" * 100)
    return str(tmp_path)


# ---------------------------------------------------------------------------
# Parallel analysis must not change the answer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("workers", [1, 2, 4, 8])
def test_worker_count_does_not_change_the_result(tree, workers):
    node = analyze_storage_hierarchy(tree, max_depth=3, max_workers=workers)
    assert node.file_count == 240
    assert node.size == 24000
    assert node.dir_count == 30  # 6 tops + 24 subs


def test_repeated_parallel_runs_are_stable(tree):
    results = {
        (n.file_count, n.size)
        for n in (analyze_storage_hierarchy(tree, max_depth=3, max_workers=8) for _ in range(4))
    }
    assert len(results) == 1


def test_children_are_ordered_by_size_not_completion(tmp_path):
    """Parallel workers finish out of order; the tree must still be size-sorted."""
    for name, count in (("small", 1), ("huge", 40), ("medium", 10)):
        d = tmp_path / name
        d.mkdir()
        for i in range(count):
            (d / f"f{i}.bin").write_bytes(b"x" * 1000)

    node = analyze_storage_hierarchy(str(tmp_path), max_depth=2, max_workers=8)
    assert [c.name for c in node.children] == ["huge", "medium", "small"]
    assert node.children[0].percentage_of_parent > node.children[-1].percentage_of_parent


def test_max_depth_limits_the_tree_but_not_the_measurement(tree):
    """Sizes always cover the whole subtree; depth only trims what is returned."""
    shallow = analyze_storage_hierarchy(tree, max_depth=1, max_workers=4)
    deep = analyze_storage_hierarchy(tree, max_depth=3, max_workers=4)

    assert shallow.size == deep.size
    assert shallow.file_count == deep.file_count
    assert shallow.children and not shallow.children[0].children
    assert deep.children[0].children


def test_missing_root_returns_none(tmp_path):
    assert analyze_storage_hierarchy(str(tmp_path / "nope")) is None


# ---------------------------------------------------------------------------
# Cancellation and progress
# ---------------------------------------------------------------------------


def test_hierarchy_cancellation_returns_promptly(tree):
    stop = threading.Event()
    stop.set()
    node = analyze_storage_hierarchy(tree, max_depth=3, stop_event=stop, max_workers=4)
    assert node is not None
    assert node.file_count == 0


def test_hierarchy_reports_progress(tree):
    seen = []
    analyze_storage_hierarchy(
        tree, max_depth=3, max_workers=1, progress_cb=lambda n, where: seen.append((n, where))
    )
    assert seen, "no progress was reported"
    # Counts only ever move forward.
    assert [n for n, _ in seen] == sorted(n for n, _ in seen)


def test_file_types_cancellation(tree):
    stop = threading.Event()
    stop.set()
    assert analyze_file_types(tree, stop_event=stop) == []


# ---------------------------------------------------------------------------
# File-type analysis
# ---------------------------------------------------------------------------


def test_file_types_uses_listing_sizes_without_restatting(tmp_path, monkeypatch):
    """Sizes come from the directory listing; a stat per file is what made this slow."""
    (tmp_path / "a.png").write_bytes(b"x" * 500)
    (tmp_path / "b.mp4").write_bytes(b"x" * 900)
    (tmp_path / "c.unknownext").write_bytes(b"x" * 100)

    calls = {"n": 0}
    real_stat = os.stat

    def counting_stat(*args, **kwargs):
        calls["n"] += 1
        return real_stat(*args, **kwargs)

    monkeypatch.setattr("crapcleaner.analysis.file_types.os.stat", counting_stat, raising=False)
    summaries = analyze_file_types(str(tmp_path))

    by_cat = {s.category: s for s in summaries}
    assert by_cat["Images"].total_size == 500
    assert by_cat["Videos"].total_size == 900
    assert by_cat["Other"].total_size == 100
    assert calls["n"] == 0, "analyze_file_types should not stat files by path"


def test_file_types_percentages_total_one_hundred(tmp_path):
    (tmp_path / "a.png").write_bytes(b"x" * 400)
    (tmp_path / "b.mp4").write_bytes(b"x" * 600)
    summaries = analyze_file_types(str(tmp_path))
    assert sum(s.percentage for s in summaries) == pytest.approx(100.0)


def test_file_types_records_extensions(tmp_path):
    (tmp_path / "a.png").write_bytes(b"x")
    (tmp_path / "b.jpg").write_bytes(b"x")
    images = next(s for s in analyze_file_types(str(tmp_path)) if s.category == "Images")
    assert images.extensions == [".jpg", ".png"]
    assert images.file_count == 2


def test_file_types_on_missing_root(tmp_path):
    assert analyze_file_types(str(tmp_path / "nope")) == []
