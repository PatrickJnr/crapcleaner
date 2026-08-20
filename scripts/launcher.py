"""PyInstaller entry point for the frozen CrapCleaner executable.

This used to call `run_gui()` unconditionally and ignore `sys.argv`, so every
command-line feature the README documents - `--scan`, `--json`, `--cleanup-preview`,
`--capabilities` - opened the GUI instead when run from the shipped binary. Argument
handling now goes through `crapcleaner.app.main`, the same dispatcher used by the
console script and by `python -m crapcleaner`.

Windows builds are windowed, so the frozen process starts with no Python-level
standard streams even when the shell that launched it handed it pipes. Two things
have to happen before output can be seen, in this order:

1. Adopt any standard handles the parent passed. Handle inheritance does not depend
   on the subsystem, so `crapcleaner.exe --scan > out.txt` and `... | findstr` both
   arrive with valid handles that simply have no Python file objects attached.
2. Failing that, attach to the console the process was launched from and open its
   streams directly, which covers being run interactively from cmd or PowerShell.

A binary started from Explorer has neither, and has no arguments either, so the GUI
path never pays for any of this.
"""

import os
import sys
from pathlib import Path

# Ensure repository root is on sys.path when running from source or build hooks
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from crapcleaner.app import main  # noqa: E402

_ATTACH_PARENT_PROCESS = -1
#: (stream name, GetStdHandle id, open mode)
_STD_STREAMS = (
    ("stdin", -10, "r"),
    ("stdout", -11, "w"),
    ("stderr", -12, "w"),
)


def _stream_is_usable(stream) -> bool:
    """Whether a stream is backed by a real file descriptor.

    A windowed PyInstaller build substitutes a writer that swallows everything, so
    "is not None" is not the question - print() succeeds and the text goes nowhere.
    """
    if stream is None:
        return False
    try:
        return stream.fileno() >= 0
    except (OSError, ValueError, AttributeError):
        return False


def _adopt_inherited_handles() -> bool:
    """Attach Python file objects to standard handles the parent already gave us."""
    import ctypes
    import msvcrt

    kernel32 = ctypes.windll.kernel32
    kernel32.GetStdHandle.restype = ctypes.c_void_p
    invalid = ctypes.c_void_p(-1).value

    adopted = False
    for name, which, mode in _STD_STREAMS:
        if _stream_is_usable(getattr(sys, name, None)):
            continue
        handle = kernel32.GetStdHandle(which)
        if not handle or handle == invalid:
            continue
        try:
            flags = os.O_RDONLY if mode == "r" else 0
            descriptor = msvcrt.open_osfhandle(handle, flags)
            stream = os.fdopen(descriptor, mode, encoding="utf-8", errors="replace", buffering=1)
        except OSError:
            continue
        setattr(sys, name, stream)
        adopted = True
    return adopted


def _attach_parent_console() -> None:
    """Attach to the console this process was launched from and open its streams."""
    import ctypes

    try:
        if not ctypes.windll.kernel32.AttachConsole(_ATTACH_PARENT_PROCESS):
            return
    except (OSError, AttributeError):
        return

    for name, device, mode in (
        ("stdout", "CONOUT$", "w"),
        ("stderr", "CONOUT$", "w"),
        ("stdin", "CONIN$", "r"),
    ):
        try:
            setattr(
                sys,
                name,
                open(device, mode, encoding="utf-8", errors="replace", buffering=1),
            )
        except OSError:
            continue


def _prepare_console_output() -> None:
    """Make stdout usable for a frozen, windowed build invoked with arguments.

    Order matters. If the runtime already wired the standard streams to whatever the
    shell handed over - a pipe, a redirected file - they are left alone: attaching to
    a console and reopening CONOUT$ on top would send the output to the terminal and
    away from the pipe the caller is reading.
    """
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return
    try:
        if _stream_is_usable(getattr(sys, "stdout", None)):
            return
        if not _adopt_inherited_handles():
            _attach_parent_console()
    except Exception:  # pragma: no cover - output setup must never break the command
        pass


if __name__ == "__main__":
    if len(sys.argv) > 1:
        _prepare_console_output()
    sys.exit(main())
