"""The self-updater must not fight a package manager, nor leave nothing behind."""

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

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

    # The outcome of the first move must be tested before the second one runs; where
    # it is handled - inline or at a label - is the script's business.
    assert "errorlevel" in guard or "$BACKUP" in guard, guard
    assert relaunch in script
    assert log in script
    assert log_path() in script


class TestTheInstallerScriptDoesNotDependOnPath:
    """A GNU find earlier in PATH made the wait loop exit immediately, so the script
    raced the running application instead of waiting for it to close."""

    def _script(self, tmp_path, monkeypatch, windows=True):
        monkeypatch.setattr(module, "is_windows", lambda: windows)
        path = module.write_installer_script(_update(tmp_path))
        body = Path(path).read_text(encoding="utf-8")
        os.remove(path)
        return body

    def test_the_wait_loop_calls_find_and_tasklist_by_absolute_path(self, tmp_path, monkeypatch):
        body = self._script(tmp_path, monkeypatch)

        assert r"System32\find.exe" in body
        assert r"System32\tasklist.exe" in body
        for line in body.splitlines():
            if "| find " in line or line.strip().startswith("tasklist "):
                raise AssertionError(f"resolves through PATH: {line.strip()}")

    def test_the_swap_is_retried_rather_than_abandoned_on_the_first_refusal(
        self, tmp_path, monkeypatch
    ):
        body = self._script(tmp_path, monkeypatch)

        assert ":retry" in body, "a one-file build can still hold the exe briefly"
        assert "TRIES" in body
        assert "goto retry" in body

    def test_the_script_closes_itself_before_deleting_itself(self, tmp_path, monkeypatch):
        body = self._script(tmp_path, monkeypatch)

        assert '(goto) 2>nul & del /F /Q "%~f0"' in body, "cmd otherwise prints a not-found error"

    def test_the_posix_script_retries_the_move_too(self, tmp_path, monkeypatch):
        body = self._script(tmp_path, monkeypatch, windows=False)

        assert "tries" in body
        assert "kill -0" in body, "the wait must not shell out to a command PATH can shadow"


class TestTheInstallerScriptRunsWithoutAConsole:
    """The script is started hidden, and cmd cannot build a pipe without a console.

    tasklist | find killed it on its first command: nothing was ever swapped, no branch
    that writes to the log was reached, and the downloaded file was left beside the
    application. The absolute paths added earlier were correct and made no difference,
    because the pipe itself was the problem.
    """

    def _script(self, tmp_path, monkeypatch):
        monkeypatch.setattr(module, "is_windows", lambda: True)
        path = module.write_installer_script(_update(tmp_path))
        body = Path(path).read_text(encoding="utf-8")
        os.remove(path)
        return body

    def test_the_wait_loop_uses_no_pipe(self, tmp_path, monkeypatch):
        body = self._script(tmp_path, monkeypatch)

        for line in body.splitlines():
            if line.lstrip().startswith("rem"):
                continue
            assert "|" not in line, f"a pipe needs a console the script does not have: {line}"

    def test_the_wait_loop_still_decides_on_the_pid(self, tmp_path, monkeypatch):
        """Removing the pipe must not remove the waiting."""
        body = self._script(tmp_path, monkeypatch)

        assert "tasklist.exe" in body
        assert "find.exe" in body
        assert ":wait" in body and "goto wait" in body

    def test_the_probe_file_is_cleaned_up(self, tmp_path, monkeypatch):
        body = self._script(tmp_path, monkeypatch)

        assert "PROBE" in body
        assert 'del /F /Q "%PROBE%"' in body


#: subprocess defines these on Windows only, which is also the only platform where
#: they mean anything: off Windows the code asks for no flags at all.
_CREATE_NO_WINDOW = 0x08000000
_DETACHED_PROCESS = 0x00000008


@pytest.mark.skipif(
    not hasattr(subprocess, "CREATE_NO_WINDOW"),
    reason="console creation flags exist only on Windows",
)
def test_the_installer_is_started_with_a_console_it_simply_does_not_show(tmp_path, monkeypatch):
    """DETACHED_PROCESS gives the script no console at all, which is what broke it."""
    seen = {}

    def fake_popen(args, **kwargs):
        seen.update(kwargs)
        seen["args"] = args
        return SimpleNamespace(pid=1234)

    monkeypatch.setattr(module, "is_windows", lambda: True)
    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(module, "_verify_replaceable", lambda target: None)

    module.apply_update(_update(tmp_path))

    flags = seen["creationflags"]
    assert flags & _CREATE_NO_WINDOW, "the console must exist but stay hidden"
    assert not flags & _DETACHED_PROCESS, "no console means no pipe, and no FOR /F either"


class TestTheInstallerDoesNotInheritTheOneFileBootstrap:
    """A frozen one-file build runs with `_PYI_*` describing the archive it unpacked.

    Anything it starts inherits them, and they travelled through the installer script
    into the new build, whose own bootloader then believed it was the child of a
    one-file parent and checked that its parent process was the same executable. It was
    not - the parent was a shell that had since exited - so the new build refused to
    start with "Security validation failure: parent process has different executable",
    after the swap had already succeeded.
    """

    def test_the_bootstrap_variables_are_dropped(self, monkeypatch):
        monkeypatch.setenv("_PYI_PARENT_PROCESS_LEVEL", "1")
        monkeypatch.setenv("_PYI_ARCHIVE_FILE", r"C:\apps\CrapCleaner.exe")
        monkeypatch.setenv("_PYI_APPLICATION_HOME_DIR", r"C:\Temp\_MEI123")
        monkeypatch.setenv("_MEIPASS2", r"C:\Temp\_MEI123")

        env = module._child_environment()

        assert not [name for name in env if name.startswith("_PYI")]
        assert "_MEIPASS2" not in env

    def test_everything_else_survives(self, monkeypatch):
        """Stripping too much would start the new build without its own environment."""
        monkeypatch.setenv("_PYI_ARCHIVE_FILE", "x")
        monkeypatch.setenv("CRAPCLEANER_TEST_MARKER", "kept")

        env = module._child_environment()

        assert env.get("CRAPCLEANER_TEST_MARKER") == "kept"
        assert "PATH" in env

    def test_the_library_path_is_put_back_as_it_was(self, monkeypatch):
        """PyInstaller moves it aside on Linux and keeps the original beside it."""
        monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEI999")
        monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/lib/mine")

        env = module._child_environment()

        assert env["LD_LIBRARY_PATH"] == "/usr/lib/mine"
        assert "LD_LIBRARY_PATH_ORIG" not in env

    def test_the_installer_is_started_with_the_cleaned_environment(self, tmp_path, monkeypatch):
        seen = {}

        def fake_popen(args, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(pid=1234)

        monkeypatch.setenv("_PYI_PARENT_PROCESS_LEVEL", "1")
        monkeypatch.setattr(module, "is_windows", lambda: True)
        monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(module, "_verify_replaceable", lambda target: None)

        module.apply_update(_update(tmp_path))

        assert "env" in seen, "without an explicit environment the child inherits this one"
        assert not [name for name in seen["env"] if name.startswith("_PYI")]


class _Downloaded:
    """The smallest stand-in for urlopen's response that download_update needs."""

    def __init__(self, payload: bytes):
        self._payload = payload
        self._sent = False
        self.headers = {"Content-Length": str(len(payload))}

    def read(self, size: int) -> bytes:
        if self._sent:
            return b""
        self._sent = True
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestAnAppImageReplacesTheFileTheUserDownloaded:
    """Inside an AppImage sys.executable points into a read-only squashfs mount.

    Writing next to it is impossible, and replacing it would not be what the user
    means: the file they have is the .AppImage. The runtime exports APPIMAGE with its
    path, and that is the thing to replace.
    """

    def test_the_target_is_the_appimage_not_the_mount(self, monkeypatch):
        monkeypatch.setenv("APPIMAGE", "/home/someone/Apps/CrapCleaner-x86_64.AppImage")
        monkeypatch.setattr(module.sys, "executable", "/tmp/.mount_CrapC12/usr/bin/crapcleaner")

        assert module.install_target() == "/home/someone/Apps/CrapCleaner-x86_64.AppImage"
        assert module.install_kind() == "appimage"

    def test_without_the_variable_nothing_changes(self, monkeypatch):
        monkeypatch.delenv("APPIMAGE", raising=False)

        assert module.appimage_path() == ""
        assert module.install_target() == os.path.abspath(module.sys.executable)

    def test_an_appimage_may_replace_itself(self, monkeypatch):
        monkeypatch.setenv("APPIMAGE", "/home/someone/Apps/CrapCleaner-x86_64.AppImage")

        allowed, reason = module.can_self_update()

        assert allowed is True, reason

    def test_it_downloads_an_appimage_rather_than_the_bare_binary(self, monkeypatch):
        """Swapping in the plain binary would strip the desktop entry and icon."""
        monkeypatch.setattr(module, "is_windows", lambda: False)
        monkeypatch.setenv("APPIMAGE", "/home/someone/Apps/CrapCleaner-x86_64.AppImage")

        assert module.asset_name() == module.APPIMAGE_ASSET

        monkeypatch.delenv("APPIMAGE", raising=False)
        assert module.asset_name() == module.LINUX_ASSET

    def test_windows_is_unaffected_by_a_stray_variable(self, monkeypatch):
        monkeypatch.setattr(module, "is_windows", lambda: True)
        monkeypatch.setenv("APPIMAGE", "/nonsense")

        assert module.asset_name() == module.WINDOWS_ASSET

    def test_the_download_lands_beside_the_appimage(self, tmp_path, monkeypatch):
        """The mount is read-only, so a temporary file there cannot even be created."""
        appimage = tmp_path / "CrapCleaner-x86_64.AppImage"
        appimage.write_bytes(b"\x7fELF old")
        monkeypatch.setenv("APPIMAGE", str(appimage))
        monkeypatch.setattr(module, "is_windows", lambda: False)
        monkeypatch.setattr(module.sys, "executable", "/tmp/.mount_CrapC12/usr/bin/crapcleaner")

        payload = b"\x7fELF new"
        digest = hashlib.sha256(payload).hexdigest()
        monkeypatch.setattr(
            module, "_fetch_text", lambda url, timeout=15.0: f"{digest}  {module.APPIMAGE_ASSET}"
        )
        monkeypatch.setattr(module.urllib.request, "urlopen", lambda *a, **k: _Downloaded(payload))

        update = module.download_update("1.4.0")

        assert update.target == str(appimage)
        assert os.path.dirname(update.path) == str(tmp_path)
        assert update.sha256 == digest
