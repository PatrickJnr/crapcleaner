"""Tests for duplicate finder performance optimizations and filter capabilities."""

from crapcleaner.analysis.duplicates import (
    DuplicateGroup,
    _hash_sample,
    find_duplicates,
    summarize_duplicates,
)


def test_hash_sample(tmp_path):
    file_path = tmp_path / "large_sample.bin"
    # Create 100 KB file
    file_path.write_bytes(b"A" * 8192 + b"B" * 80000 + b"C" * 8192)
    h = _hash_sample(str(file_path), file_size=100 * 1024)
    assert h is not None
    assert len(h) == 64


def test_find_duplicates_extension_filters(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()

    f1 = tmp_path / "a" / "photo.png"
    f2 = tmp_path / "b" / "photo.png"
    f1.write_bytes(b"image_content_12345")
    f2.write_bytes(b"image_content_12345")

    d1 = tmp_path / "a" / "doc.pdf"
    d2 = tmp_path / "b" / "doc.pdf"
    d1.write_bytes(b"pdf_content_12345")
    d2.write_bytes(b"pdf_content_12345")

    # Filter to only .png
    png_groups = find_duplicates([str(tmp_path)], min_size_bytes=1, include_extensions={"png"})
    assert len(png_groups) == 1
    assert all(f.endswith(".png") for f in png_groups[0].files)

    # Exclude .png
    pdf_groups = find_duplicates([str(tmp_path)], min_size_bytes=1, exclude_extensions={"png"})
    assert len(pdf_groups) == 1
    assert all(f.endswith(".pdf") for f in pdf_groups[0].files)


def test_find_duplicates_max_size_filter(tmp_path):
    f1 = tmp_path / "huge1.bin"
    f2 = tmp_path / "huge2.bin"
    f1.write_bytes(b"x" * 20000)
    f2.write_bytes(b"x" * 20000)

    s1 = tmp_path / "small1.bin"
    s2 = tmp_path / "small2.bin"
    s1.write_bytes(b"y" * 100)
    s2.write_bytes(b"y" * 100)

    groups = find_duplicates([str(tmp_path)], min_size_bytes=1, max_size_bytes=1000)
    assert len(groups) == 1
    assert groups[0].size == 100


def test_summarize_duplicates():
    g1 = DuplicateGroup(size=1000, files=["a", "b", "c"])
    g2 = DuplicateGroup(size=500, files=["d", "e"])
    summary = summarize_duplicates([g1, g2])

    assert summary["total_groups"] == 2
    assert summary["total_duplicate_files"] == 3  # (3-1) + (2-1)
    assert summary["total_files"] == 5
    assert summary["reclaimable_bytes"] == (2 * 1000) + (1 * 500)
    assert summary["largest_group_reclaimable"] == 2000
