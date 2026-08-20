"""Bytes a file occupies on disk, as opposed to the length of its contents.

The storage analyzer sums `st_size`, which is what the file claims to contain. The
free space the operating system reports is about something else: a 3 KB file in a
4 KB cluster costs 4 KB, an NTFS-compressed file costs less than its length, and a
sparse virtual disk can claim 80 GB while occupying 12 GB. On a drive full of small
files those differences add up, and the treemap total then disagrees with the drive.

Logical size stays the default because it is free - every listing already carries
it. Allocated size costs one call per file on Windows, so it is opt-in there; on
Linux `st_blocks` comes back with the stat that was already performed, so it is
free either way.
"""

import ctypes
import os
import sys
import threading

_IS_WINDOWS = sys.platform.startswith("win")

#: volume root -> cluster size in bytes.
_cluster_sizes: dict[str, int] = {}
_cluster_lock = threading.Lock()

SIZE_LOGICAL = "logical"
SIZE_ALLOCATED = "allocated"


def cluster_size(path: str) -> int:
    """Allocation unit for the volume `path` sits on, or 0 if it cannot be read."""
    if not _IS_WINDOWS:
        return 0
    try:
        drive = os.path.splitdrive(os.path.abspath(path))[0]
    except (OSError, ValueError):
        return 0
    if not drive:
        return 0
    root = drive + "\\"

    with _cluster_lock:
        cached = _cluster_sizes.get(root)
    if cached is not None:
        return cached

    sectors_per_cluster = ctypes.c_ulong(0)
    bytes_per_sector = ctypes.c_ulong(0)
    free_clusters = ctypes.c_ulong(0)
    total_clusters = ctypes.c_ulong(0)
    try:
        ok = ctypes.windll.kernel32.GetDiskFreeSpaceW(
            ctypes.c_wchar_p(root),
            ctypes.byref(sectors_per_cluster),
            ctypes.byref(bytes_per_sector),
            ctypes.byref(free_clusters),
            ctypes.byref(total_clusters),
        )
    except (AttributeError, OSError):
        ok = 0
    size = int(sectors_per_cluster.value * bytes_per_sector.value) if ok else 0

    with _cluster_lock:
        _cluster_sizes[root] = size
    return size


def _round_up(size: int, unit: int) -> int:
    if unit <= 0 or size <= 0:
        return size
    remainder = size % unit
    return size if remainder == 0 else size + (unit - remainder)


def allocated_size(path: str, st) -> int:
    """Bytes `path` occupies on disk.

    Falls back to the logical size whenever the real figure cannot be read, so a
    total is never made smaller by a failed query.
    """
    blocks = getattr(st, "st_blocks", None)
    if blocks is not None:
        # POSIX: 512-byte units, already present in the stat result.
        return int(blocks) * 512

    if not _IS_WINDOWS:
        return int(st.st_size)

    high = ctypes.c_ulong(0)
    try:
        low = ctypes.windll.kernel32.GetCompressedFileSizeW(
            ctypes.c_wchar_p(path), ctypes.byref(high)
        )
    except (AttributeError, OSError):
        return _round_up(int(st.st_size), cluster_size(path))

    # 0xFFFFFFFF is the error return; the call also legitimately returns it for a
    # file of that size, which GetLastError would disambiguate. Treating it as a
    # failure costs nothing but the rounding fallback.
    if low == 0xFFFFFFFF:
        return _round_up(int(st.st_size), cluster_size(path))

    on_disk = (int(high.value) << 32) + int(low)
    if on_disk <= 0:
        return _round_up(int(st.st_size), cluster_size(path))
    # Compressed and sparse files report less than their length; everything else
    # still occupies whole clusters.
    return _round_up(on_disk, cluster_size(path))


def size_for(path: str, st, mode: str) -> int:
    """Logical or allocated size, by mode name."""
    if mode == SIZE_ALLOCATED:
        return allocated_size(path, st)
    return int(st.st_size)
