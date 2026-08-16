"""Unit tests for the Recycle Bin / Trash inspector."""

from unittest.mock import patch

from crapcleaner.analysis.recycle_bin import empty_trash, get_recycle_bin_info


def test_get_recycle_bin_info_structure():
    info = get_recycle_bin_info()
    assert info is not None
    assert isinstance(info.available, bool)
    assert isinstance(info.total_size, int)
    assert isinstance(info.item_count, int)
    d = info.to_dict()
    assert "total_size" in d
    assert "item_count" in d
    assert "items" in d


def test_linux_trash_parsing(tmp_path):
    trash_dir = tmp_path / ".local" / "share" / "Trash"
    files_dir = trash_dir / "files"
    info_dir = trash_dir / "info"
    files_dir.mkdir(parents=True)
    info_dir.mkdir(parents=True)

    dummy_file = files_dir / "test.txt"
    dummy_file.write_text("hello trash")

    info_file = info_dir / "test.txt.trashinfo"
    info_file.write_text(
        "[Trash Info]\nPath=/home/user/test.txt\nDeletionDate=2026-08-15T12:00:00\n"
    )

    with patch("crapcleaner.analysis.recycle_bin.is_windows", return_value=False):
        with patch("crapcleaner.analysis.recycle_bin.is_linux", return_value=True):
            with patch(
                "crapcleaner.analysis.recycle_bin.get_user_profile", return_value=str(tmp_path)
            ):
                info = get_recycle_bin_info()
                assert info.available
                assert info.item_count == 1
                assert info.total_size > 0
                assert len(info.items) == 1
                assert info.items[0].original_path == "/home/user/test.txt"


def test_empty_trash_wrapper():
    with patch("crapcleaner.analysis.recycle_bin._empty_trash", return_value=True):
        assert empty_trash() is True
