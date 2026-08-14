"""Tests for Linux compatibility, categories, and platform fallbacks."""

from unittest.mock import patch

from crapcleaner.apps.cleanup import get_categories as get_apps_categories
from crapcleaner.browsers.cleanup import get_categories as get_browser_categories
from crapcleaner.specs.hardware import (
    _get_cpu_specs,
    _get_memory_specs,
    _get_motherboard_specs,
    _get_os_specs,
    _read_key_value_file,
    _read_text,
)
from crapcleaner.utils.platform import get_drive_info, is_linux, is_windows, list_drives


def test_platform_helpers():
    # Verify platform checks return boolean
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


@patch("crapcleaner.apps.cleanup.is_linux", return_value=True)
@patch("crapcleaner.apps.cleanup.is_windows", return_value=False)
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


@patch("crapcleaner.browsers.cleanup.is_linux", return_value=True)
@patch("crapcleaner.browsers.cleanup.is_windows", return_value=False)
def test_linux_browser_categories(mock_win, mock_linux):
    # Mocking user profile with browser directories
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


@patch("crapcleaner.specs.hardware.os.name", "posix")
@patch("crapcleaner.specs.hardware.is_linux", return_value=True)
def test_linux_os_specs(mock_linux):
    spec = _get_os_specs()
    assert spec.architecture != ""
    assert spec.computer_name != ""


@patch("crapcleaner.specs.hardware.os.name", "posix")
@patch("crapcleaner.specs.hardware.is_linux", return_value=True)
def test_linux_cpu_specs(mock_linux):
    spec = _get_cpu_specs()
    assert spec.cores_logical >= 1
    assert spec.cores_physical >= 1


@patch("crapcleaner.specs.hardware.os.name", "posix")
@patch("crapcleaner.specs.hardware.is_linux", return_value=True)
def test_linux_memory_specs(mock_linux):
    spec = _get_memory_specs()
    assert isinstance(spec.total_bytes, int)


@patch("crapcleaner.specs.hardware.os.name", "posix")
@patch("crapcleaner.specs.hardware.is_linux", return_value=True)
def test_linux_motherboard_specs(mock_linux):
    spec = _get_motherboard_specs()
    assert isinstance(spec.manufacturer, str)
