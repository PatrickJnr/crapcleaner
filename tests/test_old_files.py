"""Tests for old files scanner and age-based storage analysis."""

import os
import time

from crapcleaner.analysis.old_files import find_old_files


def test_find_old_files_filtering(tmp_path):
    f_old = tmp_path / "old_backup.zip"
    f_old.write_bytes(b"old archive data" * 100)

    f_new = tmp_path / "recent_log.txt"
    f_new.write_text("recent log data")

    now = time.time()
    old_mtime = now - (120 * 86400)
    os.utime(f_old, (old_mtime, old_mtime))

    results_90d = find_old_files(str(tmp_path), min_age_days=90)
    assert len(results_90d) == 1
    assert results_90d[0].name == "old_backup.zip"
    assert results_90d[0].age_days >= 119
    assert results_90d[0].extension == "zip"

    results_150d = find_old_files(str(tmp_path), min_age_days=150)
    assert len(results_150d) == 0

    results_size_filtered = find_old_files(str(tmp_path), min_age_days=90, min_size_bytes=1000000)
    assert len(results_size_filtered) == 0


def test_find_old_files_nonexistent_path():
    res = find_old_files("/path/that/does/not/exist")
    assert res == []
