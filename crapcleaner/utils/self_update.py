"""Download, verify, and install a new release, then start it again.

The constraint that matters: **the running application is only replaced once a new
one has been downloaded and verified.**

1. Find the asset for this platform on the release.
2. Download it beside the current executable, as a temporary file.
3. Verify its SHA-256 against the release's ``checksums.txt``, and that it looks
   like an executable for this platform.
4. Hand a script this process id, the verified file, and the path to replace. It
   waits for this process to exit, keeps the old binary as ``.bak``, moves the new
   one in, starts it, and removes the backup.
5. If either move fails it puts back what was there, starts it, and writes why to
   the application log, so a failed update never leaves the user with nothing.

Only frozen one-file builds can replace themselves this way; swapping one file
inside a one-folder build would leave the folder inconsistent, and a copy owned by
a package manager must be updated through that manager.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass

from crapcleaner import __version__
from crapcleaner.utils.logs import get_logger, log_path
from crapcleaner.utils.platform import is_windows

logger = get_logger("self_update")

GITHUB_REPO = "PatrickJnr/crapcleaner"
WINDOWS_ASSET = "CrapCleaner.exe"
LINUX_ASSET = "crapcleaner-linux-x86_64"
CHECKSUM_ASSET = "checksums.txt"

#: Read in chunks so a 60 MB download is not held in memory twice.
_CHUNK = 256 * 1024


class UpdateError(RuntimeError):
    """Anything that stopped an update, phrased for a person."""


@dataclass(frozen=True)
class DownloadedUpdate:
    """A verified release file, ready to be moved into place."""

    version: str
    path: str
    size: int
    sha256: str
    target: str


# --------------------------------------------------------------- eligibility
def install_kind() -> str:
    """How this copy was installed: 'onefile', 'onedir', or 'source'."""
    if not getattr(sys, "frozen", False):
        return "source"
    # PyInstaller's one-file build unpacks to a temporary directory recorded in
    # sys._MEIPASS; a one-folder build sits next to its own _internal directory.
    meipass = getattr(sys, "_MEIPASS", "")
    executable_dir = os.path.dirname(os.path.abspath(sys.executable))
    if meipass and os.path.normcase(meipass) != os.path.normcase(executable_dir):
        return "onefile"
    if os.path.isdir(os.path.join(executable_dir, "_internal")):
        return "onedir"
    return "onefile"


#: Path fragments that mean a package manager owns this copy, and the command that
#: manager expects. Replacing the file behind its back leaves its recorded version
#: and hash pointing at something that is no longer installed.
_MANAGER_FRAGMENTS: tuple[tuple[str, str], ...] = (
    ("winget/packages", "winget upgrade CrapCleaner"),
    ("scoop/apps", "scoop update crapcleaner"),
    ("chocolatey/lib", "choco upgrade crapcleaner"),
)
_MANAGER_PREFIXES: tuple[tuple[str, str], ...] = (
    ("/app/", "flatpak update"),
    ("/snap/", "snap refresh"),
)


def package_manager_command() -> str | None:
    """The upgrade command of the package manager that owns this copy, if any."""
    path = sys.executable.replace("\\", "/")
    lowered = path.lower()
    for fragment, command in _MANAGER_FRAGMENTS:
        if fragment in lowered:
            return command
    for prefix, command in _MANAGER_PREFIXES:
        if path.startswith(prefix):
            return command
    return None


def can_self_update() -> tuple[bool, str]:
    """Whether this copy can replace itself, and why not when it cannot."""
    managed = package_manager_command()
    if managed is not None:
        return False, f"This copy is installed by a package manager. Update it with: {managed}"
    kind = install_kind()
    if kind == "source":
        return False, (
            "This is a source checkout. Update it with 'git pull', or "
            "'pip install --upgrade crapcleaner'."
        )
    if kind == "onedir":
        return False, (
            "This is a folder installation. Download the new release and replace the "
            "folder, so the executable and its libraries stay in step."
        )
    return True, ""


def asset_name() -> str:
    return WINDOWS_ASSET if is_windows() else LINUX_ASSET


# ------------------------------------------------------------------ download
def _request(url: str):
    return urllib.request.Request(
        url,
        headers={"User-Agent": f"CrapCleaner/{__version__}", "Accept": "application/octet-stream"},
    )


def _fetch_text(url: str, timeout: float = 15.0) -> str:
    with urllib.request.urlopen(_request(url), timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def expected_digest(checksums: str, filename: str) -> str | None:
    """Pull one file's SHA-256 out of a `sha256sum` style listing."""
    for line in checksums.splitlines():
        parts = line.split()
        if len(parts) >= 2 and os.path.basename(parts[-1]) == filename:
            candidate = parts[0].strip().lower()
            if re.fullmatch(r"[0-9a-f]{64}", candidate):
                return candidate
    return None


def _looks_like_an_executable(path: str) -> bool:
    """A sanity check on the payload before anything is replaced with it."""
    try:
        with open(path, "rb") as fh:
            magic = fh.read(4)
    except OSError:
        return False
    if is_windows():
        return magic[:2] == b"MZ"
    return magic == b"\x7fELF"


def download_update(
    version: str,
    progress_cb=None,
    timeout: float = 30.0,
    base_url: str | None = None,
) -> DownloadedUpdate:
    """Download and verify the release asset for this platform.

    Raises :class:`UpdateError` with something a person can act on. Nothing on disk
    is touched apart from a temporary file until :func:`apply_update` runs.
    """
    allowed, reason = can_self_update()
    if not allowed:
        raise UpdateError(reason)

    tag = version if version.startswith("v") else f"v{version}"
    root = base_url or f"https://github.com/{GITHUB_REPO}/releases/download/{tag}"
    name = asset_name()

    try:
        checksums = _fetch_text(f"{root}/{CHECKSUM_ASSET}", timeout=timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        raise UpdateError(f"Could not read the release checksums: {exc}") from exc

    digest = expected_digest(checksums, name)
    if digest is None:
        raise UpdateError(
            f"The release does not publish a checksum for {name}, so the download "
            "cannot be verified. Update manually from the releases page."
        )

    target = os.path.abspath(sys.executable)
    directory = os.path.dirname(target)
    try:
        handle, temp_path = tempfile.mkstemp(prefix=".crapcleaner-update-", dir=directory)
        os.close(handle)
    except OSError as exc:
        raise UpdateError(f"Cannot write next to the application: {exc}") from exc

    hasher = hashlib.sha256()
    written = 0
    try:
        with urllib.request.urlopen(_request(f"{root}/{name}"), timeout=timeout) as response:
            total = int(response.headers.get("Content-Length") or 0)
            with open(temp_path, "wb") as out:
                while True:
                    chunk = response.read(_CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
                    hasher.update(chunk)
                    written += len(chunk)
                    if progress_cb is not None:
                        progress_cb(written, total)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        _discard(temp_path)
        raise UpdateError(f"Download failed: {exc}") from exc

    actual = hasher.hexdigest()
    if actual != digest:
        _discard(temp_path)
        raise UpdateError(
            "The downloaded file does not match the published checksum, so it will not "
            "be installed."
        )
    if not _looks_like_an_executable(temp_path):
        _discard(temp_path)
        raise UpdateError("The downloaded file is not an executable for this platform.")

    if not is_windows():
        try:
            os.chmod(temp_path, os.stat(temp_path).st_mode | stat.S_IXUSR | stat.S_IXGRP)
        except OSError:
            pass

    logger.info("Downloaded update %s (%d bytes) to %s", tag, written, temp_path)
    return DownloadedUpdate(
        version=version, path=temp_path, size=written, sha256=actual, target=target
    )


def _discard(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


# ------------------------------------------------------------------- install
_WINDOWS_SCRIPT = """@echo off
rem Written by CrapCleaner to replace itself. Safe to delete.
setlocal
set "TARGET={target}"
set "NEW={new}"
set "BACKUP={target}.bak"
set "LOG={log}"
rem Absolute paths: a GNU find or tasklist earlier in PATH - Git for Windows ships one -
rem reads the pid as a filename, fails, and the wait below would end immediately.
set "FIND=%SystemRoot%\\System32\\find.exe"
set "TASKLIST=%SystemRoot%\\System32\\tasklist.exe"
set "PROBE=%TEMP%\\crapcleaner-wait-{pid}.txt"

set /a WAITED=0
:wait
rem Through a file rather than a pipe. cmd builds a pipe by starting two more copies of
rem itself, which it cannot do without a console, and this script is deliberately
rem started without one: piping here killed it on its first command.
"%TASKLIST%" /FI "PID eq {pid}" /NH >"%PROBE%" 2>nul
"%FIND%" "{pid}" "%PROBE%" >nul 2>&1
if errorlevel 1 goto swap
set /a WAITED+=1
if %WAITED% GEQ 60 goto swap
ping -n 2 127.0.0.1 >nul
goto wait

:swap
del /F /Q "%PROBE%" >nul 2>&1
rem A one-file build keeps a second process alive briefly after the application exits,
rem so the executable can still be locked here. Retry rather than abandoning the update
rem on the first refusal.
set /a TRIES=0
:retry
if exist "%BACKUP%" del /F /Q "%BACKUP%" >nul 2>&1
move /Y "%TARGET%" "%BACKUP%" >nul 2>&1
if not errorlevel 1 goto moved
set /a TRIES+=1
if %TRIES% GEQ 30 goto abandoned
ping -n 2 127.0.0.1 >nul
goto retry

:moved
move /Y "%NEW%" "%TARGET%" >nul 2>&1
if errorlevel 1 goto restore
start "" "%TARGET%" {relaunch_args}
ping -n 3 127.0.0.1 >nul
del /F /Q "%BACKUP%" >nul 2>&1
goto done

:restore
move /Y "%BACKUP%" "%TARGET%" >nul 2>&1
>>"%LOG%" echo Update abandoned: the new build could not be moved into place. The installed version was restored.
start "" "%TARGET%"
goto done

:abandoned
>>"%LOG%" echo Update abandoned: "%TARGET%" was still in use after 60 seconds. The installed version was left in place.
start "" "%TARGET%"
del /F /Q "%NEW%" >nul 2>&1

:done
rem Close the script before deleting it, or cmd reports that it cannot be found.
(goto) 2>nul & del /F /Q "%~f0"
"""

_POSIX_SCRIPT = """#!/bin/sh
# Written by CrapCleaner to replace itself. Safe to delete.
TARGET='{target}'
NEW='{new}'
BACKUP='{target}.bak'
LOG='{log}'

waited=0
while [ $waited -lt 120 ] && kill -0 {pid} 2>/dev/null; do
    sleep 0.5
    waited=$((waited + 1))
done

rm -f "$BACKUP"
# A one-file build keeps a second process alive briefly, and a running binary can still
# refuse to be replaced, so retry rather than abandoning on the first failure.
tries=0
while [ $tries -lt 30 ] && ! mv "$TARGET" "$BACKUP" 2>/dev/null; do
    sleep 1
    tries=$((tries + 1))
done
if [ ! -f "$BACKUP" ]; then
    echo "Update abandoned: $TARGET was still in use. The installed version was left in place." >>"$LOG"
    "$TARGET" &
    rm -f "$NEW"
    rm -f "$0"
    exit 1
fi
if ! mv "$NEW" "$TARGET"; then
    mv "$BACKUP" "$TARGET"
    echo "Update abandoned: the new build could not be moved into place. The installed version was restored." >>"$LOG"
    "$TARGET" &
    rm -f "$0"
    exit 1
fi

chmod +x "$TARGET"
"$TARGET" {relaunch_args} &
sleep 1
rm -f "$BACKUP"
rm -f "$0"
"""


def write_installer_script(update: DownloadedUpdate, relaunch_args: str = "") -> str:
    """Write the script that performs the swap after this process exits."""
    suffix = ".cmd" if is_windows() else ".sh"
    template = _WINDOWS_SCRIPT if is_windows() else _POSIX_SCRIPT
    body = template.format(
        target=update.target,
        new=update.path,
        pid=os.getpid(),
        relaunch_args=relaunch_args,
        log=log_path(),
    )
    handle, path = tempfile.mkstemp(prefix="crapcleaner-install-", suffix=suffix)
    with os.fdopen(handle, "w", encoding="utf-8", newline="") as fh:
        fh.write(body)
    if not is_windows():
        os.chmod(path, 0o755)
    return path


def _verify_replaceable(target: str) -> None:
    """Rename the target aside and back, so a doomed swap fails while the app is alive.

    The installer script only runs after this process exits; a first move that fails
    there leaves the user with no application and nobody to tell.
    """
    probe = f"{target}.swap-check"
    try:
        os.replace(target, probe)
    except OSError as exc:
        raise UpdateError(
            f"{target} cannot be replaced ({exc}), so the update was not started and "
            "the application is untouched. Close any other copy, or exclude the folder "
            "from antivirus, and try again."
        ) from exc
    try:
        os.replace(probe, target)
    except OSError as exc:
        raise UpdateError(
            f"The application could not be renamed back and is now {probe}. "
            f"Rename it to {os.path.basename(target)} before starting it again."
        ) from exc


def _child_environment() -> dict[str, str]:
    """The environment minus the one-file bootstrap this process was started with.

    A frozen one-file build runs with `_PYI_*` set, describing the archive it unpacked
    and its place in the parent/child pair. Anything it starts inherits them, and they
    travel through the installer script into the new build, whose own bootloader then
    believes it is the child of a one-file parent and checks that its parent process is
    the same executable. It is not - the parent is a shell that has since exited - so it
    refuses to start with "Security validation failure: parent process has different
    executable", after the swap has already succeeded.

    PyInstaller also moves the library path aside and keeps the original beside it.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI")}
    env.pop("_MEIPASS2", None)  # the name used by builds before PyInstaller 6.

    for name in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        original = env.pop(f"{name}_ORIG", None)
        if original is not None:
            env[name] = original
    return env


def apply_update(update: DownloadedUpdate, relaunch_args: str = "") -> str:
    """Start the installer and hand control to it. The caller must then exit.

    Returns the script path. The application must quit promptly: the script waits
    on this process id, and until it exits nothing has been replaced.
    """
    if not os.path.isfile(update.path):
        raise UpdateError("The downloaded update is no longer available.")
    _verify_replaceable(update.target)

    script = write_installer_script(update, relaunch_args=relaunch_args)
    try:
        if is_windows():
            # CREATE_NO_WINDOW only. Adding DETACHED_PROCESS leaves the script with no
            # console at all, and cmd cannot build a pipe or run a FOR /F without one -
            # it died on the first command of the wait loop and nothing was ever
            # swapped. A hidden console is invisible in the same way and still works.
            subprocess.Popen(
                ["cmd.exe", "/c", script],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                close_fds=True,
                env=_child_environment(),
            )
        else:
            subprocess.Popen(
                ["/bin/sh", script],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                env=_child_environment(),
            )
    except OSError as exc:
        _discard(script)
        raise UpdateError(f"Could not start the installer: {exc}") from exc

    logger.info("Update installer started: %s", script)
    return script
