"""Unit tests for storage hierarchy and file type analysis."""

import os

import pytest

from crapcleaner.storage.analyzer import analyze_storage_hierarchy
from crapcleaner.storage.file_types import analyze_file_types
from crapcleaner.storage.virtual_machines import detect_virtual_machine_storage


def test_analyze_storage_hierarchy(tmp_path):
    sub1 = tmp_path / "folder_a"
    sub2 = tmp_path / "folder_b"
    sub1.mkdir()
    sub2.mkdir()

    (sub1 / "file1.bin").write_bytes(b"a" * 1024)
    (sub2 / "file2.bin").write_bytes(b"b" * 2048)

    node = analyze_storage_hierarchy(str(tmp_path), max_depth=2)
    assert node is not None
    assert node.size >= 3072
    assert node.file_count == 2
    assert node.dir_count == 2
    assert len(node.children) == 2

    # Check child sort order (largest first)
    assert node.children[0].name == "folder_b"
    assert node.children[0].size == 2048
    assert node.children[0].percentage_of_parent > 60.0


def test_analyze_file_types(tmp_path):
    (tmp_path / "photo.png").write_bytes(b"x" * 500)
    (tmp_path / "video.mp4").write_bytes(b"y" * 1500)
    (tmp_path / "code.py").write_bytes(b"z" * 300)

    summaries = analyze_file_types(str(tmp_path))
    assert len(summaries) >= 3

    cat_map = {s.category: s for s in summaries}
    assert "Videos" in cat_map
    assert cat_map["Videos"].total_size == 1500
    assert "Images" in cat_map
    assert cat_map["Images"].total_size == 500
    assert "Developer files" in cat_map
    assert cat_map["Developer files"].total_size == 300


def test_detect_virtual_machine_storage(tmp_path):
    vbox_dir = tmp_path / "VirtualBox VMs" / "Ubuntu"
    vbox_dir.mkdir(parents=True)
    vdi_file = vbox_dir / "disk.vdi"
    vdi_file.write_bytes(b"\x00" * 1024)

    from unittest.mock import patch

    with patch("crapcleaner.storage.virtual_machines.get_user_profile", return_value=str(tmp_path)):
        with patch(
            "crapcleaner.storage.virtual_machines.get_local_appdata", return_value=str(tmp_path)
        ):
            items = detect_virtual_machine_storage()
            assert any(i.platform == "VirtualBox" for i in items)
            for item in items:
                d = item.to_dict()
                assert "platform" in d
                assert "guidance" in d


def test_analyzer_results_are_stable_and_bounded(tmp_path):
    from crapcleaner.storage.analyzer import analyze_storage_hierarchy

    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "deep").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "one.bin").write_bytes(b"x" * 2048)
    (tmp_path / "a" / "deep" / "two.bin").write_bytes(b"x" * 1024)
    (tmp_path / "b" / "three.bin").write_bytes(b"x" * 512)

    node = analyze_storage_hierarchy(str(tmp_path), max_depth=3)
    assert node.size == 2048 + 1024 + 512
    assert node.file_count == 3
    assert node.dir_count == 3
    assert [c.name for c in node.children] == ["a", "b"]
    assert node.children[0].percentage_of_parent > node.children[1].percentage_of_parent

    again = analyze_storage_hierarchy(str(tmp_path), max_depth=3)
    assert (again.size, again.file_count, again.dir_count) == (
        node.size,
        node.file_count,
        node.dir_count,
    )


def test_analyzer_cancels_promptly(tmp_path):
    import threading

    from crapcleaner.storage.analyzer import analyze_storage_hierarchy

    for i in range(30):
        d = tmp_path / f"dir{i}"
        d.mkdir()
        (d / "f.bin").write_bytes(b"y" * 64)

    stop = threading.Event()
    stop.set()
    node = analyze_storage_hierarchy(str(tmp_path), max_depth=3, stop_event=stop)
    assert node.size == 0
    assert node.children == []


def test_symlinked_directory_is_not_counted_twice(tmp_path):

    from crapcleaner.storage.analyzer import analyze_storage_hierarchy

    real = tmp_path / "real"
    real.mkdir()
    (real / "data.bin").write_bytes(b"z" * 4096)
    try:
        os.symlink(str(real), str(tmp_path / "link"), target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("symlink creation is not permitted in this environment")

    node = analyze_storage_hierarchy(str(tmp_path), max_depth=3)
    assert node.size == 4096
    assert node.file_count == 1
