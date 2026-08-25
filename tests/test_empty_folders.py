"""Tests for empty folder analyzer and safety exclusions."""

from crapcleaner.analysis.empty_folders import find_empty_folders


def test_find_empty_folders_detection(tmp_path):
    # Empty directory
    d_empty = tmp_path / "empty_dir"
    d_empty.mkdir()

    # Nested empty directory
    d_nested = tmp_path / "nested_parent" / "nested_empty"
    d_nested.mkdir(parents=True)

    # Non-empty directory
    d_full = tmp_path / "full_dir"
    d_full.mkdir()
    (d_full / "file.txt").write_text("content", encoding="utf-8")

    results = find_empty_folders(str(tmp_path), min_depth=1)
    paths = [r.path for r in results]

    assert str(d_empty) in paths
    assert str(d_nested) in paths
    assert str(d_full) not in paths


def test_find_empty_folders_respects_protected_roots(tmp_path):
    # Protected .git directory (should be skipped)
    git_dir = tmp_path / ".git" / "empty_hook"
    git_dir.mkdir(parents=True)

    results = find_empty_folders(str(tmp_path), min_depth=1)
    paths = [r.path for r in results]

    assert not any(".git" in p for p in paths)
