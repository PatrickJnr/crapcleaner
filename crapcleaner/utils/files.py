"""Safe file operations: permission-aware deletion, Windows long-path normalization, and Recycle Bin access."""

import ctypes
import os
import shutil
import stat
from collections.abc import Iterable
from ctypes import wintypes


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


def normalize_long_path(path: str) -> str:
    """Ensure path handles Windows 260-character MAX_PATH limit safely."""
    if os.name != "nt" or not path:
        return path
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
    """Permanently remove a directory tree, handling readonly files gracefully."""
    norm = normalize_long_path(path)
    try:
        _clear_readonly(norm)
        for root, dirs, files in os.walk(norm, topdown=False):
            for name in files:
                _clear_readonly(os.path.join(root, name))
            for name in dirs:
                _clear_readonly(os.path.join(root, name))
        shutil.rmtree(norm, onerror=_on_rmtree_error)
        return True
    except OSError:
        return False


def recycle_file(path: str) -> bool:
    """Move a single file to the Recycle Bin. Permanent delete on non-Windows."""
    if os.name != "nt":
        return remove_file(path)
    return _shfile_op_delete([path])


def recycle_tree(path: str) -> bool:
    """Move a whole directory tree to the Recycle Bin. Permanent delete on non-Windows."""
    if os.name != "nt":
        return remove_tree(path)
    return _shfile_op_delete([path])


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
        if not _shfile_op_delete([p]):
            failed.append(p)
    return not failed, failed


def empty_recycle_bin() -> bool:
    """Empty the Windows Recycle Bin on all drives."""
    if os.name != "nt":
        return False
    try:
        result = ctypes.windll.shell32.SHEmptyRecycleBinW(
            None, None, _SHERB_NOCONFIRMATION | _SHERB_NOPROGRESSUI | _SHERB_NOSOUND
        )
        return result == 0
    except OSError:
        return False


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
