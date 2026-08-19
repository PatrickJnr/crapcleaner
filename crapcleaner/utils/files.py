"""Safe file operations: permission-aware deletion, Windows long-path normalization, and Recycle Bin access."""

import ctypes
import os
import shutil
import stat
import subprocess
from collections.abc import Iterable
from ctypes import wintypes
from datetime import datetime
from urllib.parse import quote

from crapcleaner.utils.platform import get_user_profile, is_linux, run_command, which


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", wintypes.USHORT),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


_FO_DELETE = 3
_FOF_ALLOWUNDO = 0x40
_FOF_NOCONFIRMATION = 0x10
_FOF_SILENT = 0x4
_FOF_NOERRORUI = 0x400

_SHERB_NOCONFIRMATION = 0x00000001
_SHERB_NOPROGRESSUI = 0x00000002
_SHERB_NOSOUND = 0x00000004


#: FILE_ATTRIBUTE_REPARSE_POINT. Windows directory junctions carry this flag but are
#: reported as ordinary directories by S_ISLNK, os.path.islink, and
#: DirEntry.is_dir(follow_symlinks=False), so it is the only reliable signal.
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def is_link_like(entry_or_stat) -> bool:
    """Whether an entry is a symlink, junction, or other reparse point.

    Accepts an `os.DirEntry` or a stat result. Traversal must never descend through
    one: a junction loop recurses until the file budget is spent, and a junction
    pointing outside the tree being walked would let a scan report - or a cleanup
    delete - files that are nowhere near the intended target.
    """
    try:
        is_entry = hasattr(entry_or_stat, "is_symlink")
        if is_entry:
            if entry_or_stat.is_symlink():
                return True
            st = entry_or_stat.stat(follow_symlinks=False)
        else:
            st = entry_or_stat
            if stat.S_ISLNK(st.st_mode):
                return True
    except OSError:
        return False

    if getattr(st, "st_reparse_tag", 0):
        return True
    return bool(getattr(st, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT)


def walk_safe(top: str, topdown: bool = True):
    """`os.walk` that never follows symlinks or Windows junctions.

    `os.walk` follows junctions even with `followlinks=False`, because that flag only
    covers symlinks. Reparse points are yielded among the file names rather than
    descended into, so a caller deleting a tree removes the link itself and leaves its
    target alone.
    """
    try:
        entries = list(os.scandir(top))
    except OSError:
        return

    dirs: list[str] = []
    files: list[str] = []
    for entry in entries:
        try:
            if is_link_like(entry):
                files.append(entry.name)
            elif entry.is_dir(follow_symlinks=False):
                dirs.append(entry.name)
            else:
                files.append(entry.name)
        except OSError:
            continue

    if topdown:
        yield top, dirs, files
    for name in dirs:
        yield from walk_safe(os.path.join(top, name), topdown)
    if not topdown:
        yield top, dirs, files


def walk_safe_entries(top: str):
    """Like :func:`walk_safe`, but yields `(dirpath, file_entries)` with the entries.

    A directory listing already carries each file's size, so a caller that needs sizes
    can read them from the `os.DirEntry` instead of issuing a fresh `os.stat` per file.
    That one avoidable syscall per file is the difference between a file-type breakdown
    taking a hundred seconds and taking ten.

    Symlinks and junctions are yielded as entries rather than descended into, exactly
    as in :func:`walk_safe`.
    """
    try:
        entries = list(os.scandir(top))
    except OSError:
        return

    dirs: list[os.DirEntry] = []
    files: list[os.DirEntry] = []
    for entry in entries:
        try:
            if is_link_like(entry):
                files.append(entry)
            elif entry.is_dir(follow_symlinks=False):
                dirs.append(entry)
            else:
                files.append(entry)
        except OSError:
            continue

    yield top, files
    for entry in dirs:
        yield from walk_safe_entries(entry.path)


def file_manager_name() -> str:
    """What to call the platform's file manager in menu labels."""
    return "File Explorer" if os.name == "nt" else "File Manager"


def reveal_in_file_manager(path: str, select: bool = True) -> bool:
    """Show `path` in the platform's file manager.

    Arguments are always passed as a list, never as a command string. Interpolating a
    path into one lets a name containing a quote change the command being run.
    """
    if not path:
        return False
    target = os.path.abspath(path)
    if not os.path.exists(target):
        return False

    try:
        if os.name == "nt":
            if select and not os.path.isdir(target):
                # explorer wants this exact single-argument form for /select.
                subprocess.Popen(["explorer", f"/select,{target}"])
            else:
                subprocess.Popen(["explorer", target])
            return True

        folder = target if os.path.isdir(target) else os.path.dirname(target)
        # The freedesktop interface highlights the file itself; xdg-open can only open
        # the containing folder, so it is the fallback rather than the first choice.
        if select and not os.path.isdir(target) and which("dbus-send"):
            result = run_command(
                [
                    "dbus-send",
                    "--session",
                    "--dest=org.freedesktop.FileManager1",
                    "--type=method_call",
                    "/org/freedesktop/FileManager1",
                    "org.freedesktop.FileManager1.ShowItems",
                    f"array:string:file://{target}",
                    "string:",
                ],
                timeout=5.0,
            )
            if result.ok:
                return True

        if which("xdg-open"):
            subprocess.Popen(["xdg-open", folder])
            return True
        return False
    except (OSError, subprocess.SubprocessError):
        return False


def normalize_long_path(path: str) -> str:
    """Ensure path handles Windows 260-character MAX_PATH limit safely."""
    if not path:
        return path
    if os.name != "nt":
        return os.path.abspath(path)
    if path.startswith("\\\\?\\") or path.startswith("\\\\.\\"):
        return path
    abs_path = os.path.abspath(path)
    if len(abs_path) >= 240:
        if abs_path.startswith("\\\\"):
            return "\\\\?\\UNC\\" + abs_path[2:]
        return "\\\\?\\" + abs_path
    return abs_path


def _clear_readonly(path: str) -> None:
    """Clear readonly, hidden, or system flags preventing deletion."""
    try:
        norm = normalize_long_path(path)
        if hasattr(os.stat_result, "st_file_attributes"):
            attr = getattr(os.stat(norm), "st_file_attributes", None)
            if attr is not None and attr & getattr(stat, "FILE_ATTRIBUTE_READONLY", 1):
                os.chmod(norm, stat.S_IWRITE | stat.S_IREAD)
        elif os.path.isdir(norm):
            os.chmod(norm, 0o777)
        else:
            os.chmod(norm, 0o666)
    except OSError:
        pass


def remove_file(path: str) -> bool:
    """Permanently delete a single file, clearing readonly attributes if locked."""
    norm = normalize_long_path(path)
    try:
        _clear_readonly(norm)
        os.remove(norm)
        return True
    except OSError:
        try:
            _clear_readonly(norm)
            os.chmod(norm, 0o777)
            os.remove(norm)
            return True
        except OSError:
            return False


def _on_rmtree_error(func, path, _exc_info):
    """Error handler callback for shutil.rmtree to clear readonly bits and retry."""
    try:
        _clear_readonly(path)
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        func(path)
    except OSError:
        pass


def remove_tree(path: str) -> bool:
    """Permanently remove a directory tree, handling readonly files gracefully.

    Links inside the tree are detached rather than followed. `shutil.rmtree` only
    learned to recognise junctions in Python 3.12 (`os.DirEntry.is_junction`), and this
    project supports 3.10 and 3.11, where it would descend into one and delete the
    files it points at. Detaching them first makes the behaviour identical on every
    supported version. The attribute pass uses the same safe walk so it cannot clear
    the read-only flag on files outside the tree either.
    """
    norm = normalize_long_path(path)
    try:
        _clear_readonly(norm)
        junctions: list[str] = []
        for root, dirs, files in walk_safe(norm, topdown=False):
            for name in files:
                full = os.path.join(root, name)
                _clear_readonly(full)
                # walk_safe reports links among the file names; a directory link has to
                # be removed with rmdir, which unlinks it without touching its target.
                if os.path.isdir(full):
                    junctions.append(full)
            for name in dirs:
                _clear_readonly(os.path.join(root, name))

        for junction in junctions:
            try:
                os.rmdir(junction)
            except OSError:
                pass

        shutil.rmtree(norm, onerror=_on_rmtree_error)
        return True
    except OSError:
        return False


def recycle_file(path: str) -> bool:
    """Move a single file to the platform trash/recycle bin."""
    if os.name == "nt":
        return _shfile_op_delete([path])
    if is_linux():
        return _trash_put(path)
    return remove_file(path)


def recycle_tree(path: str) -> bool:
    """Move a whole directory tree to the platform trash/recycle bin."""
    if os.name == "nt":
        return _shfile_op_delete([path])
    if is_linux():
        return _trash_put(path)
    return remove_tree(path)


def _shfile_op_delete(paths: Iterable[str]) -> bool:
    """Invoke Windows Shell IFileOperation / SHFileOperation to send to Recycle Bin."""
    valid_paths = [os.path.abspath(p) for p in paths if os.path.exists(p)]
    if not valid_paths:
        return True
    joined = "\0".join(valid_paths) + "\0\0"
    op = _SHFILEOPSTRUCTW(
        hwnd=None,
        wFunc=_FO_DELETE,
        pFrom=joined,
        pTo=None,
        fFlags=_FOF_ALLOWUNDO | _FOF_NOCONFIRMATION | _FOF_SILENT | _FOF_NOERRORUI,
        fAnyOperationsAborted=False,
        hNameMappings=None,
        lpszProgressTitle=None,
    )
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return result == 0


def move_to_recycle_bin(paths: list[str]) -> tuple[bool, list[str]]:
    """Move a list of paths to the Recycle Bin and return (success, failed_list)."""
    failed = []
    for p in paths:
        if not os.path.exists(p):
            continue
        ok = _shfile_op_delete([p]) if os.name == "nt" else (_trash_put(p) if is_linux() else False)
        if not ok:
            failed.append(p)
    return not failed, failed


def empty_recycle_bin() -> bool:
    """Empty the platform recycle bin/trash."""
    if os.name == "nt":
        try:
            result = ctypes.windll.shell32.SHEmptyRecycleBinW(
                None, None, _SHERB_NOCONFIRMATION | _SHERB_NOPROGRESSUI | _SHERB_NOSOUND
            )
            return result == 0
        except OSError:
            return False
    if is_linux():
        return _empty_linux_trash()
    return False


def _trash_put(path: str) -> bool:
    trash_put = which("gio")
    if trash_put and run_command([trash_put, "trash", path], timeout=20.0).ok:
        return True
    trash_cli = which("trash-put")
    if trash_cli and run_command([trash_cli, path], timeout=20.0).ok:
        return True
    return _freedesktop_trash_put(path)


def _freedesktop_trash_put(path: str) -> bool:
    src = os.path.abspath(path)
    if not os.path.exists(src):
        return True

    user = get_user_profile()
    trash_root = os.path.join(user, ".local", "share", "Trash")
    files_dir = os.path.join(trash_root, "files")
    info_dir = os.path.join(trash_root, "info")
    try:
        os.makedirs(files_dir, exist_ok=True)
        os.makedirs(info_dir, exist_ok=True)
    except OSError:
        return False

    base_name = os.path.basename(src.rstrip(os.sep)) or "item"
    candidate = base_name
    stem, ext = os.path.splitext(base_name)
    counter = 1
    while os.path.exists(os.path.join(files_dir, candidate)) or os.path.exists(
        os.path.join(info_dir, f"{candidate}.trashinfo")
    ):
        candidate = f"{stem}.{counter}{ext}" if stem else f"{base_name}.{counter}"
        counter += 1

    dest = os.path.join(files_dir, candidate)
    info_path = os.path.join(info_dir, f"{candidate}.trashinfo")
    deleted_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    info_text = f"[Trash Info]\nPath={quote(src)}\nDeletionDate={deleted_at}\n"

    try:
        with open(info_path, "w", encoding="utf-8") as fh:
            fh.write(info_text)
        shutil.move(src, dest)
        return True
    except OSError:
        try:
            if os.path.exists(info_path):
                os.remove(info_path)
        except OSError:
            pass
        return False


def _empty_linux_trash() -> bool:
    user = get_user_profile()
    candidates = [
        os.path.join(user, ".local", "share", "Trash", "files"),
        os.path.join(user, ".local", "share", "Trash", "info"),
    ]
    ok = True
    for path in candidates:
        if not os.path.isdir(path):
            continue
        for entry in os.listdir(path):
            full = os.path.join(path, entry)
            if os.path.isdir(full) and not os.path.islink(full):
                ok = remove_tree(full) and ok
            else:
                ok = remove_file(full) and ok
    return ok


def path_is_locked(path: str) -> bool:
    """Check if a file is currently opened with exclusive lock by another process."""
    norm = normalize_long_path(path)
    if not os.path.exists(norm):
        return False
    try:
        handle = os.open(norm, os.O_RDWR)
        os.close(handle)
        return False
    except OSError:
        return True
