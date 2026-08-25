"""Tests for running process and active application lock warnings."""

from unittest.mock import patch

from crapcleaner.system.process_guard import (
    APP_DEFINITIONS,
    get_running_process_snapshot,
    running_processes_for_categories,
)


def test_app_definitions_structure():
    assert len(APP_DEFINITIONS) >= 20
    for key, (win_proc, linux_proc, display_name, prefixes) in APP_DEFINITIONS.items():
        assert key
        assert win_proc.endswith(".exe")
        assert linux_proc
        assert display_name
        assert len(prefixes) >= 1


def test_running_processes_for_browsers():
    snapshot = "chrome.exe\nfirefox.exe\n"
    running = running_processes_for_categories(
        ["chrome_cache", "firefox_cache"], process_snapshot=snapshot
    )
    assert "Google Chrome" in running
    assert "Mozilla Firefox" in running


def test_running_processes_for_developer_tools():
    snapshot = "code.exe\nclaude.exe\ncursor.exe\n"
    running = running_processes_for_categories(
        ["vscode_caches", "claude_desktop_caches", "cursor_caches"],
        process_snapshot=snapshot,
    )
    assert "VS Code" in running
    assert "Claude Desktop" in running
    assert "Cursor" in running


def test_running_processes_for_apps_and_launchers():
    snapshot = "discord.exe\nspotify.exe\nsteam.exe\n"
    running = running_processes_for_categories(
        ["discord_cache", "spotify_cache", "steam_caches"],
        process_snapshot=snapshot,
    )
    assert "Discord" in running
    assert "Spotify" in running
    assert "Steam" in running


def test_unrelated_categories_return_no_running_warning():
    snapshot = "chrome.exe\ncode.exe\n"
    running = running_processes_for_categories(
        ["windows_temp", "system_logs", "dotnet_caches"],
        process_snapshot=snapshot,
    )
    assert running == []


def test_empty_snapshot_returns_empty():
    assert running_processes_for_categories(["chrome_cache"], process_snapshot="") == []


def test_get_running_process_snapshot_invokes_platform_command():
    with patch(
        "crapcleaner.system.process_guard.run_command",
        return_value={"returncode": 0, "stdout": "TestProcess\n"},
    ):
        snap = get_running_process_snapshot()
        assert "testprocess" in snap
