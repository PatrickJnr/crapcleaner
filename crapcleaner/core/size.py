"""Directory size computation with error tolerance, junction/loop prevention, and progress reporting."""

import fnmatch
import os
import re
import stat
from collections.abc import Callable

ProgressCallback = Callable[[int, int, str], None] | None


def _stat_entries(root: str) -> list[os.DirEntry]:
    try:
        return list(os.scandir(root))
    except OSError:
        return []


def is_reparse_point(st) -> bool:
    """Whether a stat result describes a link the traversal must not follow.

    `S_ISLNK`, `os.path.islink` and `is_dir(follow_symlinks=False)` all report a
    Windows junction as an ordinary directory, so the reparse tag is the only signal.

    Following one double-counts files through several paths, and a junction pointing
    outside the scan root would offer the user's own documents as reclaimable junk.
    """
    if stat.S_ISLNK(st.st_mode):
        return True
    return bool(getattr(st, "st_reparse_tag", 0))


_WILDCARDS = re.compile(r"[*?\[]")


def _compile_patterns(patterns: tuple[str, ...]) -> list[tuple[str, "re.Pattern[str] | None"]]:
    """Per pattern, a literal suffix when `*rest` has no further wildcard, else a regex.

    The suffix form has to agree with `fnmatch` exactly: the cleanup deletes by
    `fnmatch`, so anything the scan counts that `fnmatch` would refuse is space the
    scan promises and the cleanup never frees.
    """
    compiled: list[tuple[str, re.Pattern[str] | None]] = []
    for p in patterns or ():
        lower = p.lower()
        rest = lower[1:] if lower.startswith("*") else ""
        if rest and not _WILDCARDS.search(rest):
            compiled.append((rest, None))
        else:
            compiled.append(("", re.compile(fnmatch.translate(lower))))
    return compiled


def _matches(entry_name: str, compiled) -> bool:
    lower = entry_name.lower()
    for suffix, regex in compiled:
        if regex is None:
            if lower.endswith(suffix):
                return True
        elif regex.match(lower):
            return True
    return False


def compute_dir_size(
    root: str,
    patterns: tuple[str, ...] = (),
    recurse: bool = True,
    only_files: bool = False,
    max_files: int = 200000,
    stop_event=None,
    progress_cb: ProgressCallback = None,
    counter: list[int] | None = None,
) -> tuple[int, int, int]:
    """Compute (total_bytes, file_count, skipped_count) for a directory tree."""
    if not os.path.exists(root):
        return 0, 0, 0
    if os.path.isfile(root) or os.path.islink(root):
        return 0, 0, 0

    total = 0
    count = 0
    skipped = 0
    visited = counter if counter is not None else [0]
    seen_dirs: set[str] = set()
    matchers = _compile_patterns(patterns)

    from crapcleaner.core.protected_paths import (
        DirectoryGuard,
        invalidate_settings_exclusions,
    )

    # One config read per scanned target rather than one per file.
    invalidate_settings_exclusions()

    def walk(directory: str, guard) -> None:
        nonlocal total, count, skipped
        canonical = os.path.abspath(directory).lower()
        if canonical in seen_dirs:
            return
        seen_dirs.add(canonical)

        entries = _stat_entries(directory)
        for entry in entries:
            if stop_event is not None and stop_event.is_set():
                raise _Cancelled
            visited[0] += 1
            if visited[0] > max_files:
                return
            try:
                # Single lstat per entry: derive dir/file/link from st_mode
                st = entry.stat(follow_symlinks=False)
            except OSError:
                skipped += 1
                continue

            mode = st.st_mode
            if is_reparse_point(st):
                continue
            if stat.S_ISDIR(mode):
                if recurse:
                    # Derived lexically from the parent - no resolve() syscall.
                    walk(entry.path, guard.child(entry.name))
                    if visited[0] > max_files:
                        return
                continue
            if not stat.S_ISREG(mode):
                continue

            if patterns and not _matches(entry.name, matchers):
                continue

            if not guard.allows_file(entry.name):
                skipped += 1
                continue
            total += st.st_size
            count += 1
            if count % 500 == 0 and progress_cb is not None:
                progress_cb(count, total, directory)

    root_guard = DirectoryGuard(root)
    if not root_guard.directory_allowed:
        return 0, 0, 0

    try:
        walk(root, root_guard)
    except _Cancelled:
        raise
    return total, count, skipped


class _Cancelled(Exception):
    pass
