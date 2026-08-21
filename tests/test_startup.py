"""Unit tests for the platform-neutral Startup Manager and both of its backends."""

import os
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from crapcleaner.system.backends import startup_linux
from crapcleaner.system.startup import (
    StartupItem,
    _estimate_startup_impact,
    _extract_executable_path,
    _extract_publisher,
    add_scopes,
    add_startup_item,
    get_startup_items,
    remove_startup_item,
    set_startup_item_enabled,
)
from crapcleaner.utils.platform import is_windows


def test_startup_item_to_dict():
    item = StartupItem(
        id="reg:HKCU_RUN:TestApp",
        name="TestApp",
        command="C:\\App\\app.exe --silent",
        location="Registry (Current User Run)",
        location_key="HKCU_RUN",
        scope="USER",
        enabled=True,
        impact="Low",
        publisher="Test Publisher",
        file_path="C:\\App\\app.exe",
        file_exists=True,
    )
    d = item.to_dict()
    assert d["id"] == "reg:HKCU_RUN:TestApp"
    assert d["name"] == "TestApp"
    assert d["command"] == "C:\\App\\app.exe --silent"
    assert d["enabled"] is True
    assert d["scope"] == "USER"
    assert d["impact"] == "Low"
    assert d["publisher"] == "Test Publisher"
    assert d["file_exists"] is True


def test_extract_executable_path():
    assert (
        _extract_executable_path('"C:\\Program Files\\App\\app.exe" --arg')
        == "C:\\Program Files\\App\\app.exe"
    )
    assert _extract_executable_path("C:\\Utils\\tool.exe /start") == "C:\\Utils\\tool.exe"
    assert _extract_executable_path("") == ""
    assert _extract_executable_path("notepad.exe") == "notepad.exe"


def test_estimate_startup_impact(tmp_path):
    assert _estimate_startup_impact("RandomApp", "C:\\nonexistent.exe", False) == "Not Measured"

    assert _estimate_startup_impact("Discord", "C:\\Users\\User\\Discord.exe", True) == "High"
    assert _estimate_startup_impact("Steam Client", "C:\\Steam\\steam.exe", True) == "High"
    assert _estimate_startup_impact("Spotify", "C:\\Spotify\\spotify.exe", True) == "High"

    assert _estimate_startup_impact("OneDrive", "C:\\OneDrive\\onedrive.exe", True) == "Medium"
    assert _estimate_startup_impact("Razer Synapse", "C:\\Razer\\razer.exe", True) == "Medium"

    f = tmp_path / "small.exe"
    f.write_bytes(b"x" * 1000)
    assert _estimate_startup_impact("SmallUtil", str(f), True) == "Low"


def test_extract_publisher():
    assert _extract_publisher("Microsoft Teams", "") == "Microsoft Corporation"
    assert _extract_publisher("Google Chrome", "") == "Google LLC"
    assert _extract_publisher("Discord", "") == "Discord Inc."
    assert _extract_publisher("Spotify", "") == "Spotify AB"
    assert _extract_publisher("Steam", "") == "Valve Corporation"
    assert _extract_publisher("Epic Games Launcher", "") == "Epic Games, Inc."
    assert _extract_publisher("Adobe Creative Cloud", "") == "Adobe Inc."
    assert _extract_publisher("NVIDIA Control Panel", "") == "NVIDIA Corporation"
    assert _extract_publisher("Unknown Tool", "C:\\Random\\tool.exe") == "Unknown Publisher"


def test_get_startup_items_returns_list():
    items = get_startup_items()
    assert isinstance(items, list)
    for item in items:
        assert isinstance(item, StartupItem)
        assert item.name
        assert item.location_key


def test_set_startup_item_enabled_invalid_id():
    ok, msg = set_startup_item_enabled("invalid_id", True)
    assert ok is False
    assert "Invalid" in msg


def test_remove_startup_item_invalid_id():
    ok, msg = remove_startup_item("invalid_id")
    assert ok is False
    assert "Invalid" in msg


def test_add_startup_item_empty_validation():
    ok, msg = add_startup_item("", "")
    assert ok is False
    assert "empty" in msg.lower()

    ok, msg = add_startup_item("TestApp", "")
    assert ok is False
    assert "empty" in msg.lower()


@contextmanager
def force_platform(name: str):
    """Pin the capability registry to one operating system."""
    with patch("crapcleaner.system.capabilities.is_windows", return_value=name == "windows"):
        with patch("crapcleaner.system.capabilities.is_linux", return_value=name == "linux"):
            yield


@pytest.fixture
def linux_autostart(monkeypatch, tmp_path):
    """A Linux platform with both autostart directories redirected into tmp_path.

    The system directory has to be redirected too. On a real Linux machine
    /etc/xdg/autostart exists and ships entries such as xdg-user-dirs-update, which
    would otherwise be listed alongside the fixture's own file and make any count
    assertion depend on what the host distribution happens to install.
    """
    config_home = tmp_path / ".config"
    autostart_dir = config_home / "autostart"
    autostart_dir.mkdir(parents=True)
    system_dir = tmp_path / "etc-xdg-autostart"
    system_dir.mkdir()

    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setattr(startup_linux, "SYSTEM_AUTOSTART_DIR", str(system_dir))
    with force_platform("linux"):
        yield autostart_dir


def test_linux_autostart_workflow(linux_autostart):
    autostart_dir = linux_autostart
    desktop_file = autostart_dir / "my_app.desktop"
    desktop_file.write_text(
        "[Desktop Entry]\nType=Application\nName=My Test App\n"
        "Exec=/usr/bin/myapp --tray\nHidden=false\nX-GNOME-Autostart-enabled=true\n"
    )

    items = get_startup_items()
    assert len(items) == 1
    assert items[0].name == "My Test App"
    assert items[0].enabled is True
    assert items[0].scope == "USER"

    ok, _msg = set_startup_item_enabled(items[0].id, False)
    assert ok is True
    content = desktop_file.read_text()
    assert "Hidden=true" in content
    assert "X-GNOME-Autostart-enabled=false" in content
    assert get_startup_items()[0].enabled is False

    ok, _msg = set_startup_item_enabled(items[0].id, True)
    assert ok is True
    assert get_startup_items()[0].enabled is True

    ok, _msg = add_startup_item("Second App", "/usr/bin/secondapp")
    assert ok is True
    assert (autostart_dir / "second_app.desktop").exists()

    ok, _msg = remove_startup_item("linux:USER_STARTUP:second_app.desktop")
    assert ok is True
    assert not (autostart_dir / "second_app.desktop").exists()


def test_linux_system_entry_is_hidden_not_deleted(linux_autostart, tmp_path):
    """/etc is root-owned, so disabling a packaged entry writes a user override."""
    # The fixture already created and redirected the system directory.
    system_dir = tmp_path / "etc-xdg-autostart"
    packaged = system_dir / "org.gnome.Tracker.desktop"
    packaged.write_text("[Desktop Entry]\nType=Application\nName=Tracker\nExec=tracker-miner\n")

    items = get_startup_items()
    assert len(items) == 1
    assert items[0].scope == "SYSTEM"
    assert items[0].publisher == "Gnome"

    ok, msg = remove_startup_item(items[0].id)
    assert ok is True
    assert "hidden" in msg.lower()
    # The packaged file survives; a user override now suppresses it.
    assert packaged.exists()
    override = linux_autostart / "org.gnome.Tracker.desktop"
    assert override.exists()
    assert "Hidden=true" in override.read_text()
    assert get_startup_items()[0].enabled is False


def test_linux_user_entry_shadows_system_entry(linux_autostart, tmp_path):
    system_dir = tmp_path / "etc-xdg-autostart"
    (system_dir / "shared.desktop").write_text(
        "[Desktop Entry]\nName=Packaged Version\nExec=/usr/bin/shared\n"
    )
    (linux_autostart / "shared.desktop").write_text(
        "[Desktop Entry]\nName=User Version\nExec=/usr/bin/shared\n"
    )

    items = get_startup_items()
    assert len(items) == 1
    assert items[0].name == "User Version"


def test_linux_rejects_system_scope_add(linux_autostart):
    ok, msg = add_startup_item("Daemon", "/usr/bin/daemon", scope="SYSTEM")
    assert ok is False
    assert "user" in msg.lower()


def test_ids_from_another_platform_are_rejected():
    with force_platform("linux"):
        ok, msg = set_startup_item_enabled("reg:HKCU_RUN:SomeWindowsApp", False)
        assert ok is False
        assert "operating system" in msg.lower()

    with force_platform("windows"):
        ok, msg = remove_startup_item("linux:USER_STARTUP:app.desktop")
        assert ok is False
        assert "operating system" in msg.lower()


def test_unsupported_platform_refuses_gracefully():
    with force_platform("other"):
        assert get_startup_items() == []
        assert add_scopes() == ()
        ok, msg = add_startup_item("App", "/bin/app")
        assert ok is False
        assert "not available" in msg.lower()


def test_extract_executable_path_walks_an_unquoted_path_with_spaces(tmp_path):
    """Windows accepts unquoted Run values, so splitting on the first space is wrong."""
    target = tmp_path / "Program Files" / "App" / "app.exe"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")

    assert _extract_executable_path(f"{target} --minimized") == str(target)
    assert _extract_executable_path(str(target)) == str(target)


@pytest.mark.skipif(
    not is_windows(), reason="%VAR% is Windows syntax; POSIX expandvars leaves it as written"
)
def test_extract_executable_path_expands_environment_variables(tmp_path, monkeypatch):
    target = tmp_path / "Common Files" / "svc.exe"
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    monkeypatch.setenv("CC_TEST_ROOT", str(tmp_path))

    unexpanded = os.path.join("%CC_TEST_ROOT%", "Common Files", "svc.exe")
    assert _extract_executable_path(f"{unexpanded} /background") == str(target)
