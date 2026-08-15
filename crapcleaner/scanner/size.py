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


def _compile_patterns(patterns: tuple[str, ...]):
    """Precompile suffix + fnmatch-regex per pattern for fast matching."""
    compiled = []
    for p in patterns or ():
        lower = p.lower()
        compiled.append((lower.lstrip("*."), re.compile(fnmatch.translate(lower))))
    return compiled


def _matches(entry_name: str, compiled) -> bool:
    lower = entry_name.lower()
    for suffix, regex in compiled:
        if lower.endswith(suffix) or regex.match(lower):
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

    def walk(directory: str) -> None:
        nonlocal total, count, skipped
        canonical = os.path.abspath(directory).lower()
        if canonical in seen_dirs:
            return
        seen_dirs.add(canonical)

        entries = _stat_entries(directory)
        for entry in entries:
            if stop_event is not None and stop_event.is_set():
                raise _Cancelled
            if visited[0] > max_files:
                return
            try:
                # Single lstat per entry: derive dir/file/link from st_mode
                st = entry.stat(follow_symlinks=False)
            except OSError:
                skipped += 1
                continue

            mode = st.st_mode
            if stat.S_ISLNK(mode):
                continue
            if stat.S_ISDIR(mode):
                if recurse:
                    walk(entry.path)
                continue
            if not stat.S_ISREG(mode):
                continue

            if patterns and not _matches(entry.name, matchers):
                continue
            from crapcleaner.safety.protected_paths import validate_cleanup_path

            is_safe, _ = validate_cleanup_path(entry.path)
            if not is_safe:
                skipped += 1
                continue
            total += st.st_size
            count += 1
            visited[0] += 1
            if count % 500 == 0 and progress_cb is not None:
                progress_cb(count, total, directory)

    try:
        walk(root)
    except _Cancelled:
        raise
    return total, count, skipped


class _Cancelled(Exception):
    pass


def should_scan_target(
    target_path: str, patterns: tuple[str, ...], subdirs: tuple[str, ...]
) -> bool:
    return True
