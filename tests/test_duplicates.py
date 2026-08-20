"""Tests for duplicate finder."""

import threading

from crapcleaner.analysis.duplicates import DuplicateGroup, find_duplicates


def _write(tmp_path, rel, data):
    full = tmp_path / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(data)
    return str(full)


class TestDuplicateGroup:
    def test_counts(self):
        group = DuplicateGroup(size=100, files=["a", "b", "c"])
        assert group.duplicate_count == 2
        assert group.reclaimable == 200

    def test_single_file_no_dupe(self):
        group = DuplicateGroup(size=100, files=["a"])
        assert group.duplicate_count == 0
        assert group.reclaimable == 0


class TestFindDuplicates:
    def test_finds_same_content(self, tmp_path):
        f1 = _write(tmp_path, "a/f1.bin", b"same content")
        f2 = _write(tmp_path, "b/f2.bin", b"same content")
        groups = find_duplicates([str(tmp_path)], min_size_bytes=1)
        assert len(groups) == 1
        assert set(groups[0].files) == {f1, f2}

    def test_different_content_not_grouped(self, tmp_path):
        _write(tmp_path, "a/f1.bin", b"content A")
        _write(tmp_path, "b/f2.bin", b"content B")
        assert find_duplicates([str(tmp_path)], min_size_bytes=1) == []

    def test_min_size_filter(self, tmp_path):
        _write(tmp_path, "a/small.txt", b"x")
        _write(tmp_path, "b/small.txt", b"x")
        assert find_duplicates([str(tmp_path)], min_size_bytes=1024) == []

    def test_three_copies(self, tmp_path):
        _write(tmp_path, "a/f.bin", b"data")
        _write(tmp_path, "b/f.bin", b"data")
        _write(tmp_path, "c/f.bin", b"data")
        groups = find_duplicates([str(tmp_path)], min_size_bytes=1)
        assert groups[0].duplicate_count == 2

    def test_same_size_different_prefix(self, tmp_path):
        # 16 KB files: same size, different 8 KB prefix
        _write(tmp_path, "a/f1.bin", b"A" * 16384)
        _write(tmp_path, "b/f2.bin", b"B" * 16384)
        assert find_duplicates([str(tmp_path)], min_size_bytes=1) == []

    def test_same_prefix_different_body(self, tmp_path):
        # 16 KB files: same 8 KB prefix, different remainder
        prefix = b"P" * 8192
        _write(tmp_path, "a/f1.bin", prefix + b"X" * 8192)
        _write(tmp_path, "b/f2.bin", prefix + b"Y" * 8192)
        assert find_duplicates([str(tmp_path)], min_size_bytes=1) == []

    def test_same_prefix_same_body(self, tmp_path):
        prefix = b"P" * 8192
        body = b"B" * 8192
        f1 = _write(tmp_path, "a/f1.bin", prefix + body)
        f2 = _write(tmp_path, "b/f2.bin", prefix + body)
        groups = find_duplicates([str(tmp_path)], min_size_bytes=1)
        assert len(groups) == 1
        assert set(groups[0].files) == {f1, f2}

    def test_max_groups_limit(self, tmp_path):
        for i in range(3):
            payload = bytes([65 + i]) * 4096
            _write(tmp_path, f"g{i}/a.bin", payload)
            _write(tmp_path, f"g{i}/b.bin", payload)
        groups = find_duplicates([str(tmp_path)], min_size_bytes=1, max_groups=2)
        assert len(groups) == 2


class TestCancelledHashPass:
    """A cancelled full-hash pass returned [], discarding groups already confirmed."""

    def test_groups_confirmed_before_the_stop_are_returned(self, tmp_path):
        small = b"s" * 100
        large = b"l" * 20000
        _write(tmp_path, "small_a.bin", small)
        _write(tmp_path, "small_b.bin", small)
        _write(tmp_path, "large_a.bin", large)
        _write(tmp_path, "large_b.bin", large)
        stop_event = threading.Event()

        groups = find_duplicates(
            [str(tmp_path)],
            min_size_bytes=1,
            stop_event=stop_event,
            # Fires once the prefix-sized group is confirmed, before any full hashing.
            progress_cb=lambda *_: stop_event.set(),
            max_workers=1,
        )

        assert [g.size for g in groups] == [100]


class TestGroupOrdering:
    def test_the_capped_result_holds_the_largest_groups_first(self, tmp_path):
        for index, size in enumerate((300, 100, 200)):
            payload = bytes([index]) * size
            _write(tmp_path, f"g{index}_a.bin", payload)
            _write(tmp_path, f"g{index}_b.bin", payload)

        groups = find_duplicates([str(tmp_path)], min_size_bytes=1, max_groups=2)

        assert [g.size for g in groups] == [300, 200]
