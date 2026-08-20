"""The self-updater must not fight a package manager, nor leave nothing behind."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import crapcleaner.utils.self_update as module
from crapcleaner.utils.logs import log_path
from crapcleaner.utils.self_update import (
    DownloadedUpdate,
    UpdateError,
    apply_update,
    can_self_update,
    package_manager_command,
)


@pytest.mark.parametrize(
    ("executable", "command"),
    [
        (
            r"C:\Users\a\AppData\Local\Microsoft\WinGet\Packages\CrapCleaner\CrapCleaner.exe",
            "winget upgrade CrapCleaner",
        ),
        (r"C:\Users\a\scoop\apps\crapcleaner\current\CrapCleaner.exe", "scoop update crapcleaner"),
        (
            r"C:\ProgramData\chocolatey\lib\crapcleaner\tools\CrapCleaner.exe",
            "choco upgrade crapcleaner",
        ),
        ("/app/bin/crapcleaner", "flatpak update"),
        ("/snap/crapcleaner/current/bin/crapcleaner", "snap refresh"),
    ],
)
def test_a_managed_copy_refuses_and_names_the_manager(monkeypatch, executable, command):
    monkeypatch.setattr(sys, "executable", executable)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert package_manager_command() == command
    allowed, reason = can_self_update()
    assert allowed is False
    assert command in reason


def test_manager_paths_are_matched_whatever_their_case(monkeypatch):
    monkeypatch.setattr(sys, "executable", r"C:\Users\a\SCOOP\Apps\crapcleaner\CrapCleaner.exe")
    assert package_manager_command() == "scoop update crapcleaner"


def test_a_standalone_copy_is_not_treated_as_managed(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "CrapCleaner.exe"))
    assert package_manager_command() is None


def _update(tmp_path) -> DownloadedUpdate:
    target = tmp_path / "crapcleaner"
    target.write_bytes(b"installed")
    new = tmp_path / "downloaded"
    new.write_bytes(b"new build")
    return DownloadedUpdate(
        version="9.9.9", path=str(new), size=9, sha256="0" * 64, target=str(target)
    )


def test_an_unreplaceable_target_stops_the_update_while_the_app_is_still_running(
    tmp_path, monkeypatch
):
    update = _update(tmp_path)

    def refuse(*args, **kwargs):
        raise PermissionError("held by another process")

    started: list = []
    monkeypatch.setattr(os, "replace", refuse)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: started.append(a))

    with pytest.raises(UpdateError) as raised:
        apply_update(update)

    assert "untouched" in str(raised.value)
    assert started == []
    assert Path(update.target).read_bytes() == b"installed"


def test_a_replaceable_target_leaves_the_application_where_it_was(tmp_path, monkeypatch):
    update = _update(tmp_path)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: None)

    script = apply_update(update)

    assert Path(update.target).read_bytes() == b"installed"
    assert not Path(f"{update.target}.swap-check").exists()
    os.remove(script)


@pytest.mark.parametrize(
    ("windows", "first", "second", "relaunch", "log"),
    [
        (False, 'mv "$TARGET" "$BACKUP"', 'mv "$NEW" "$TARGET"', '"$TARGET" &', '"$LOG"'),
        (
            True,
            'move /Y "%TARGET%" "%BACKUP%"',
            'move /Y "%NEW%" "%TARGET%"',
            'start "" "%TARGET%"',
            '"%LOG%"',
        ),
    ],
)
def test_a_failed_first_move_restores_and_reports(
    tmp_path, monkeypatch, windows, first, second, relaunch, log
):
    monkeypatch.setattr(module, "is_windows", lambda: windows)
    path = module.write_installer_script(_update(tmp_path))
    script = Path(path).read_text(encoding="utf-8")
    os.remove(path)

    guard = script.split(first, 1)[1].split(second, 1)[0]

    assert "exit" in guard
    assert relaunch in guard
    assert log in guard
    assert log_path() in script
