"""Tests for user exclusions management and enforcement."""

import os
import tempfile

from crapcleaner.core.protected_paths import (
    is_path_excluded,
    validate_cleanup_path,
)
from crapcleaner.core.size import compute_dir_size


def test_is_path_excluded():
    with tempfile.TemporaryDirectory() as tmpdir:
        subfolder = os.path.join(tmpdir, "my_custom_safe_data")
        os.makedirs(subfolder, exist_ok=True)
        file_path = os.path.join(subfolder, "important.dat")
        with open(file_path, "w") as f:
            f.write("important data")

        # Not excluded initially
        is_excl, _ = is_path_excluded(file_path, exclusions=[])
        assert not is_excl

        # Excluded when added
        is_excl, reason = is_path_excluded(file_path, exclusions=[subfolder])
        assert is_excl
        assert subfolder in reason


def test_validate_cleanup_path_with_exclusions():
    with tempfile.TemporaryDirectory() as tmpdir:
        excluded_dir = os.path.join(tmpdir, "excluded_builds")
        os.makedirs(excluded_dir, exist_ok=True)
        file_in_excl = os.path.join(excluded_dir, "app.cache")
        with open(file_in_excl, "w") as f:
            f.write("cache")

        is_safe, msg = validate_cleanup_path(file_in_excl, exclusions=[excluded_dir])
        assert not is_safe
        assert "Excluded path skipped" in msg


def test_compute_dir_size_skips_excluded():
    with tempfile.TemporaryDirectory() as tmpdir:
        nested_dir = os.path.join(tmpdir, "keep_this_dir")
        os.makedirs(nested_dir, exist_ok=True)
        file1 = os.path.join(nested_dir, "test.tmp")
        with open(file1, "wb") as f:
            f.write(b"x" * 1024)

        # Normal scan
        total, count, skipped = compute_dir_size(tmpdir)
        assert count == 1
        assert total == 1024

        # With mock exclusion in settings
        from unittest.mock import patch

        with patch(
            "crapcleaner.config.load_settings",
            return_value={"excluded_paths": [nested_dir]},
        ):
            total_excl, count_excl, skipped_excl = compute_dir_size(tmpdir)
            assert count_excl == 0
            assert total_excl == 0
            assert skipped_excl == 1
