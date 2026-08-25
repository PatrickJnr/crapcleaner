"""Tests for StorageNode and StorageIndex analysis enhancements."""

from crapcleaner.analysis.storage import StorageIndex, StorageNode, analyze_storage_hierarchy


def test_storage_node_properties():
    child = StorageNode(name="child", path="/data/child", size=1024 * 1024)
    parent = StorageNode(
        name="parent",
        path="/data",
        size=5 * 1024 * 1024,
        file_count=10,
        dir_count=1,
        children=[child],
    )

    assert parent.human_size == "5.0 MB"
    assert parent.largest_child is child
    assert not parent.is_leaf
    assert child.is_leaf
    assert child.largest_child is None

    d = parent.to_dict()
    assert d["human_size"] == "5.0 MB"
    assert len(d["children"]) == 1


def test_storage_index_query_methods(tmp_path):
    # Setup directories with varying file sizes
    d_big = tmp_path / "big_dir"
    d_big.mkdir()
    (d_big / "file1.bin").write_bytes(b"x" * 10000)

    d_mid = tmp_path / "mid_dir"
    d_mid.mkdir()
    (d_mid / "file2.bin").write_bytes(b"x" * 5000)

    d_nested = tmp_path / "nested" / "deep"
    d_nested.mkdir(parents=True)
    (d_nested / "file3.bin").write_bytes(b"x" * 2000)

    index = StorageIndex()
    root_node = analyze_storage_hierarchy(str(tmp_path), max_depth=4, index_out=index)
    assert root_node is not None

    # Test get_top_directories
    top_dirs = index.get_top_directories(n=3, exclude_root=str(tmp_path))
    assert len(top_dirs) >= 2
    assert top_dirs[0].size >= top_dirs[1].size

    # Test get_largest_leaf_directories
    leaves = index.get_largest_leaf_directories(n=5)
    assert len(leaves) > 0

    # Test summary
    summary = index.summary(str(tmp_path))
    assert summary["total_directories"] >= 4
    assert summary["total_size"] == 17000
    assert summary["total_files"] == 3

    # Test find_directories
    matches = index.find_directories("mid_dir")
    assert len(matches) == 1
    assert matches[0].name == "mid_dir"
