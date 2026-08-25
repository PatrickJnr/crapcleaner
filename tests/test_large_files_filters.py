"""Tests for large file scanner filters, multi-root scanning, and format detection."""

from crapcleaner.analysis.large_files import (
    LargeFile,
    scan_large_files,
    scan_large_files_multi,
)


def test_large_file_human_size():
    lf = LargeFile(
        path="/test/file.mp4",
        size=1024 * 1024 * 50,
        last_modified=None,
        extension=".mp4",
        file_type="Video",
    )
    assert lf.human_size == "50.0 MB"
    assert lf.name == "file.mp4"
    assert lf.to_dict()["human_size"] == "50.0 MB"


def test_scan_large_files_filters(tmp_path):
    f_video = tmp_path / "movie.mp4"
    f_model = tmp_path / "weights.safetensors"
    f_data = tmp_path / "database.sqlite"

    f_video.write_bytes(b"v" * 10000)
    f_model.write_bytes(b"m" * 15000)
    f_data.write_bytes(b"d" * 8000)

    # All files above 5000 bytes
    all_large = scan_large_files(str(tmp_path), threshold_bytes=5000)
    assert len(all_large) == 3

    # Category filter
    videos_only = scan_large_files(str(tmp_path), threshold_bytes=5000, category_filter={"Video"})
    assert len(videos_only) == 1
    assert videos_only[0].extension == ".mp4"

    # Extension filter
    models_only = scan_large_files(
        str(tmp_path), threshold_bytes=5000, extension_filter={"safetensors"}
    )
    assert len(models_only) == 1
    assert models_only[0].extension == ".safetensors"


def test_scan_large_files_multi(tmp_path):
    root1 = tmp_path / "root1"
    root2 = tmp_path / "root2"
    root1.mkdir()
    root2.mkdir()

    (root1 / "big1.iso").write_bytes(b"1" * 20000)
    (root2 / "big2.vdi").write_bytes(b"2" * 30000)

    results = scan_large_files_multi(
        [str(root1), str(root2)], threshold_bytes=10000, max_results=10
    )
    assert len(results) == 2
    assert results[0].size == 30000  # Sorted by size descending
    assert results[1].size == 20000
