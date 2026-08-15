"""Tests for old files scanner and age-based storage analysis."""

import os
import time

from crapcleaner.storage.old_files import find_old_files


def test_find_old_files_filtering(tmp_path):
    # Create test files
    f_old = tmp_path / "old_backup.zip"
    f_old.write_bytes(b"old archive data" * 100)

    f_new = tmp_path / "recent_log.txt"
    f_new.write_text("recent log data")

    now = time.time()
    # Modify mtime of old_backup.zip to 120 days ago
    old_mtime = now - (120 * 86400)
    os.utime(f_old, (old_mtime, old_mtime))

    # 1. Query files older than 90 days
    results_90d = find_old_files(str(tmp_path), min_age_days=90)
    assert len(results_90d) == 1
    assert results_90d[0].name == "old_backup.zip"
    assert results_90d[0].age_days >= 119
    assert results_90d[0].extension == "zip"

    # 2. Query files older than 150 days (should be empty)
    results_150d = find_old_files(str(tmp_path), min_age_days=150)
    assert len(results_150d) == 0

    # 3. Query with min size filter
    results_size_filtered = find_old_files(str(tmp_path), min_age_days=90, min_size_bytes=1000000)
    assert len(results_size_filtered) == 0


def test_find_old_files_nonexistent_path():
    res = find_old_files("/path/that/does/not/exist")
    assert res == []
