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


def test_folder_holding_only_empty_folders_is_reported(tmp_path):
    (tmp_path / "a" / "b" / "c").mkdir(parents=True)

    paths = [r.path for r in find_empty_folders(str(tmp_path), min_depth=1)]

    assert str(tmp_path / "a") in paths
    assert str(tmp_path / "a" / "b") in paths
    assert str(tmp_path / "a" / "b" / "c") in paths


def test_folder_holding_a_file_below_it_is_not_reported(tmp_path):
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    (deep / "keep.txt").write_text("content", encoding="utf-8")

    paths = [r.path for r in find_empty_folders(str(tmp_path), min_depth=1)]

    assert str(tmp_path / "a") not in paths
    assert str(deep) not in paths
