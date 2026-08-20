"""Tests for Linux compatibility, categories, and platform fallbacks."""

import os
from unittest.mock import patch

import pytest

from crapcleaner.categories.apps import get_categories as get_apps_categories
from crapcleaner.categories.browsers import get_categories as get_browser_categories
from crapcleaner.system.hardware import (
    _get_cpu_specs,
    _get_memory_specs,
    _get_motherboard_specs,
    _get_os_specs,
    _read_key_value_file,
    _read_text,
)
from crapcleaner.utils.platform import get_drive_info, is_linux, is_windows, list_drives


def test_platform_helpers():
    assert isinstance(is_windows(), bool)
    assert isinstance(is_linux(), bool)


@patch("crapcleaner.utils.platform.sys.platform", "linux")
def test_list_drives_linux():
    roots = list_drives()
    assert "/" in roots


@patch("crapcleaner.utils.platform.is_windows", return_value=False)
def test_get_drive_info_linux(mock_win, tmp_path):
    info = get_drive_info(str(tmp_path))
    assert "total" in info
    assert "free" in info
    assert "used" in info
    assert info["total"] > 0


@patch("crapcleaner.categories.apps.is_linux", return_value=True)
@patch("crapcleaner.categories.apps.is_windows", return_value=False)
def test_linux_app_categories(mock_win, mock_linux):
    cats = get_apps_categories()
    ids = {c.id for c in cats}
    assert "apt_cache" in ids
    assert "dnf_cache" in ids
    assert "pacman_cache" in ids
    assert "flatpak_cache" in ids
    assert "snap_cache" in ids
    assert "discord_cache" in ids
    assert "slack_cache" in ids
    assert "spotify_cache" in ids


@patch("crapcleaner.categories.apps.is_linux", return_value=True)
@patch("crapcleaner.categories.apps.is_windows", return_value=False)
def test_linux_app_caches_cover_every_install_method(mock_win, mock_linux):
    """A Flatpak or Snap install keeps its cache somewhere else entirely (issue #7)."""
    by_id = {c.id: c for c in get_apps_categories()}

    for cid, flatpak_id, snap_name in (
        ("discord_cache", "com.discordapp.Discord", "discord"),
        ("slack_cache", "com.slack.Slack", "slack"),
        ("spotify_cache", "com.spotify.Client", "spotify"),
    ):
        paths = [t.path.replace("\\", "/") for t in by_id[cid].targets]
        assert any(f".var/app/{flatpak_id}/" in p for p in paths), f"{cid}: no Flatpak path"
        assert any(f"snap/{snap_name}/current/" in p for p in paths), f"{cid}: no Snap path"
        assert any(".var/app" not in p and "/snap/" not in p for p in paths), (
            f"{cid}: no native path"
        )


@patch("crapcleaner.categories.browsers.is_linux", return_value=True)
@patch("crapcleaner.categories.browsers.is_windows", return_value=False)
def test_linux_browser_categories(mock_win, mock_linux):
    cats = get_browser_categories()
    assert isinstance(cats, list)


def test_read_key_value_file(tmp_path):
    f = tmp_path / "os-release"
    f.write_text('NAME="Ubuntu"\nVERSION="24.04 LTS"\nPRETTY_NAME="Ubuntu 24.04 LTS"\n')
    data = _read_key_value_file(str(f), sep="=")
    assert data.get("NAME") == '"Ubuntu"'
    assert data.get("PRETTY_NAME") == '"Ubuntu 24.04 LTS"'


def test_read_text_fallback():
    assert _read_text("/nonexistent/file/path/that/does/not/exist") == ""


@patch("crapcleaner.system.hardware.os.name", "posix")
@patch("crapcleaner.system.hardware.is_linux", return_value=True)
def test_linux_os_specs(mock_linux):
    spec = _get_os_specs()
    assert spec.architecture != ""
    assert spec.computer_name != ""


@patch("crapcleaner.system.hardware.os.name", "posix")
@patch("crapcleaner.system.hardware.is_linux", return_value=True)
def test_linux_cpu_specs(mock_linux):
    spec = _get_cpu_specs()
    assert spec.cores_logical >= 1
    assert spec.cores_physical >= 1


@patch("crapcleaner.system.hardware.os.name", "posix")
@patch("crapcleaner.system.hardware.is_linux", return_value=True)
def test_linux_memory_specs(mock_linux):
    spec = _get_memory_specs()
    assert isinstance(spec.total_bytes, int)


@patch("crapcleaner.system.hardware.os.name", "posix")
@patch("crapcleaner.system.hardware.is_linux", return_value=True)
def test_linux_motherboard_specs(mock_linux):
    spec = _get_motherboard_specs()
    assert isinstance(spec.manufacturer, str)


def test_get_mount_metadata():
    from crapcleaner.utils.platform import get_mount_metadata

    data = get_mount_metadata()
    assert isinstance(data, dict)


def test_dedupe_linux_mounts(tmp_path):
    from crapcleaner.utils.platform import _dedupe_linux_mounts

    mounts = [str(tmp_path)]
    res = _dedupe_linux_mounts(mounts)
    assert len(res) == 1


def test_dedupe_linux_mounts_drops_duplicate_aliases(tmp_path):
    from crapcleaner.utils.platform import _dedupe_linux_mounts

    alias = tmp_path / "alias"
    try:
        os.symlink(tmp_path, alias, target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("symlink creation is not permitted in this environment")
    mounts = [str(tmp_path), str(alias)]
    res = _dedupe_linux_mounts(mounts)
    assert res == [str(tmp_path)]


def test_visible_linux_mount_filters_proc_and_run():
    from crapcleaner.utils.platform import _is_visible_linux_mount

    assert _is_visible_linux_mount("/", "ext4") is True
    assert _is_visible_linux_mount("/proc", "proc") is False
    assert _is_visible_linux_mount("/proc/sysrq-trigger", "proc") is False
    assert _is_visible_linux_mount("/run/user/1000", "tmpfs") is False


def test_visible_linux_mount_is_strict_about_user_storage_paths():
    from crapcleaner.utils.platform import _is_visible_linux_mount

    assert _is_visible_linux_mount("/home", "ext4") is True
    assert _is_visible_linux_mount("/mnt/data", "ext4") is True
    assert _is_visible_linux_mount("/media/will/Drive", "ext4") is True
    assert _is_visible_linux_mount("/tmp", "ext4") is False
    assert _is_visible_linux_mount("/var", "ext4") is False
    assert _is_visible_linux_mount("/usr", "ext4") is False


@patch("crapcleaner.utils.platform.is_windows", return_value=False)
def test_linux_drive_display_helpers(_mock_win):
    from crapcleaner.utils.platform import linux_drive_display_kind, linux_drive_display_name

    assert linux_drive_display_name("/") == "System Root (/)"
    assert linux_drive_display_name("/home") == "Home"
    assert linux_drive_display_name("/mnt/data") == "Mounted Volume (data)"
    assert linux_drive_display_name("/media/will/FastSSD") == "External Drive (FastSSD)"
    assert linux_drive_display_kind("/") == "SYSTEM"
    assert linux_drive_display_kind("/home") == "HOME"
    assert linux_drive_display_kind("/mnt/data") == "MOUNTED"
    assert linux_drive_display_kind("/media/will/FastSSD") == "EXTERNAL"


def test_linux_trash_helpers(tmp_path):
    from crapcleaner.utils.files import _empty_linux_trash, _trash_put

    f = tmp_path / "sample.txt"
    f.write_text("hello")
    assert _trash_put(str(f)) is True
    assert not f.exists()

    with patch("crapcleaner.utils.files.get_user_profile", return_value=str(tmp_path)):
        trash_dir = tmp_path / ".local" / "share" / "Trash" / "files"
        trash_dir.mkdir(parents=True, exist_ok=True)
        (trash_dir / "old.txt").write_text("trash")
        assert _empty_linux_trash() is True
        assert not (trash_dir / "old.txt").exists()
