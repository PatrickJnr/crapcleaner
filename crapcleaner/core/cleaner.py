"""Cleanup engine: deletes files per category, skips locked items, continues on errors."""

import os
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime

from crapcleaner.core.actions import run_action
from crapcleaner.core.protected_paths import validate_cleanup_path
from crapcleaner.models.category import CacheTarget, CleanupCategory
from crapcleaner.models.report import CleanupReport, CleanupResult
from crapcleaner.utils.files import (
    recycle_file,
    recycle_tree,
    remove_file,
    remove_tree,
    walk_safe,
)
from crapcleaner.utils.platform import is_admin

ProgressCallback = Callable[[str, int, int], None]
StopEvent = threading.Event | None


def normalize_excluded(paths) -> frozenset[str]:
    """Normalise user-deselected paths for comparison during a cleanup."""
    normalized = set()
    for path in paths or ():
        if not path:
            continue
        try:
            normalized.add(os.path.normcase(os.path.abspath(path)))
        except (OSError, ValueError):
            continue
    return frozenset(normalized)


def _is_excluded(path: str, excluded: frozenset[str]) -> bool:
    if not excluded:
        return False
    try:
        return os.path.normcase(os.path.abspath(path)) in excluded
    except (OSError, ValueError):
        return False


def _delete_target_files(
    target_path: str,
    patterns: tuple,
    recurse: bool,
    only_files: bool,
    dry_run: bool,
    stop_event: StopEvent,
    use_recycle_bin: bool = False,
    excluded: frozenset[str] = frozenset(),
) -> tuple:
    deleted = 0
    recovered = 0
    skipped = 0
    errors: list[str] = []
    permission_errors: list[str] = []
    skip_reasons: list[str] = []

    def outcome() -> tuple:
        return deleted, recovered, skipped, errors, permission_errors, skip_reasons

    def record_failure(path: str, exc: OSError) -> None:
        if isinstance(exc, PermissionError):
            permission_errors.append(f"{path}: {exc.strerror or exc}")
        else:
            errors.append(f"{path}: {exc}")

    is_safe, msg = validate_cleanup_path(target_path)
    if not is_safe:
        skip_reasons.append(msg)
        return outcome()

    if only_files and not os.path.isfile(target_path):
        # The target names a single file; a directory in its place is not the target.
        return outcome()

    def handle_file(path: str) -> None:
        nonlocal deleted, recovered, skipped
        if _is_excluded(path, excluded):
            skipped += 1
            return
        is_safe_file, reason = validate_cleanup_path(path)
        if not is_safe_file:
            skipped += 1
            skip_reasons.append(reason)
            return
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        if dry_run:
            deleted += 1
            recovered += size
            return
        try:
            removed = recycle_file(path) if use_recycle_bin else remove_file(path)
            if removed:
                deleted += 1
                recovered += size
            else:
                skipped += 1
                skip_reasons.append(f"{path}: in use or locked by another process")
        except OSError as exc:
            skipped += 1
            record_failure(path, exc)

    def handle_tree(path: str) -> None:
        nonlocal deleted, recovered, skipped
        is_safe_tree, reason = validate_cleanup_path(path)
        if not is_safe_tree:
            skipped += 1
            skip_reasons.append(reason)
            return
        if dry_run:
            for root, dirs, files in walk_safe(path):
                if stop_event is not None and stop_event.is_set():
                    raise _Stopped
                for name in files:
                    deleted += 1
                    try:
                        recovered += os.path.getsize(os.path.join(root, name))
                    except OSError:
                        pass
            return
        if use_recycle_bin and not patterns and not excluded:
            size = 0
            count = 0
            for root, dirs, files in walk_safe(path):
                if stop_event is not None and stop_event.is_set():
                    raise _Stopped
                for name in files:
                    count += 1
                    try:
                        size += os.path.getsize(os.path.join(root, name))
                    except OSError:
                        pass
            if recycle_tree(path):
                deleted += count
                recovered += size
            else:
                skipped += 1
                skip_reasons.append(f"{path}: could not be moved to the Recycle Bin")
            return
        total_size = 0
        total_files = 0
        for root, dirs, files in walk_safe(path, topdown=False):
            if stop_event is not None and stop_event.is_set():
                raise _Stopped
            for name in files:
                full = os.path.join(root, name)
                if patterns and not _name_matches(name, patterns):
                    continue
                if _is_excluded(full, excluded):
                    skipped += 1
                    continue
                is_safe_entry, entry_reason = validate_cleanup_path(full)
                if not is_safe_entry:
                    skipped += 1
                    skip_reasons.append(entry_reason)
                    continue
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = 0
                try:
                    if recycle_file(full) if use_recycle_bin else remove_file(full):
                        total_files += 1
                        total_size += size
                    else:
                        skipped += 1
                        skip_reasons.append(f"{full}: in use or locked by another process")
                except OSError as exc:
                    skipped += 1
                    record_failure(full, exc)
            for name in dirs:
                full = os.path.join(root, name)
                is_safe_dir, dir_reason = validate_cleanup_path(full)
                if not is_safe_dir:
                    skipped += 1
                    skip_reasons.append(dir_reason)
                    continue
                if patterns or excluded:
                    # Only files matching the pattern - or not deselected by the user -
                    # may go. Removing the tree here would take the rest with it, so the
                    # directory is only unlinked if processing left it empty.
                    try:
                        os.rmdir(full)
                    except OSError:
                        pass
                    continue
                if not (recycle_tree(full) if use_recycle_bin else remove_tree(full)):
                    skipped += 1
                    skip_reasons.append(f"{full}: directory could not be removed")
        deleted += total_files
        recovered += total_size

    try:
        if os.path.isfile(target_path):
            handle_file(target_path)
            return outcome()

        if not os.path.isdir(target_path):
            return outcome()

        if patterns:
            try:
                with os.scandir(target_path) as it:
                    for entry in it:
                        if stop_event is not None and stop_event.is_set():
                            raise _Stopped
                        if entry.is_dir(follow_symlinks=False) and recurse:
                            handle_tree(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            if _name_matches(entry.name, patterns):
                                handle_file(entry.path)
            except OSError as exc:
                record_failure(target_path, exc)
        elif recurse:
            handle_tree(target_path)
        else:
            try:
                with os.scandir(target_path) as it:
                    for entry in it:
                        if stop_event is not None and stop_event.is_set():
                            raise _Stopped
                        if entry.is_file(follow_symlinks=False):
                            handle_file(entry.path)
            except OSError as exc:
                record_failure(target_path, exc)
    except _Stopped:
        raise

    return outcome()


@dataclass(frozen=True)
class PathRemoval:
    """Outcome of removing one explicitly selected path."""

    path: str
    removed: bool
    reason: str = ""


def remove_selected_paths(paths: Iterable[str], use_recycle_bin: bool = True) -> list[PathRemoval]:
    """Remove paths a user picked individually, validating each one first.

    Views that let the user select files by hand - duplicates, large files - route
    through here rather than calling the filesystem helpers directly, so no deletion
    in the application can skip the protected-path layer. The per-path outcome lets
    the caller report exactly what was refused and why.
    """
    outcomes: list[PathRemoval] = []
    for path in paths:
        if not path:
            continue
        is_safe, reason = validate_cleanup_path(path)
        if not is_safe:
            outcomes.append(PathRemoval(path=path, removed=False, reason=reason))
            continue
        if not os.path.exists(path) and not os.path.islink(path):
            outcomes.append(PathRemoval(path=path, removed=False, reason="No longer on disk"))
            continue
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                ok = recycle_tree(path) if use_recycle_bin else remove_tree(path)
            else:
                ok = recycle_file(path) if use_recycle_bin else remove_file(path)
        except OSError as exc:
            outcomes.append(PathRemoval(path=path, removed=False, reason=str(exc)))
            continue
        outcomes.append(
            PathRemoval(
                path=path,
                removed=bool(ok),
                reason="" if ok else "In use or locked by another process",
            )
        )
    return outcomes


def _name_matches(name: str, patterns: tuple) -> bool:
    import fnmatch

    lowered = name.lower()
    return any(fnmatch.fnmatch(lowered, p.lower()) for p in patterns)


class _Stopped(Exception):
    pass


def clean_categories(
    categories: list[CleanupCategory],
    dry_run: bool = False,
    use_recycle_bin: bool = False,
    stop_event: StopEvent = None,
    progress_cb: ProgressCallback | None = None,
    excluded_paths=None,
) -> CleanupReport:
    """Clean the given categories.

    `excluded_paths` holds files the user deselected in the preview. They are
    counted as skipped and left exactly where they are - which is what makes the
    file-level preview more than a listing.
    """
    started = datetime.now()
    report = CleanupReport(started=started, dry_run=dry_run, use_recycle_bin=use_recycle_bin)
    admin = is_admin()
    excluded = normalize_excluded(excluded_paths)
    total = len(categories)

    for index, category in enumerate(categories):
        if stop_event is not None and stop_event.is_set():
            report.errors.append("Cleanup stopped by user.")
            break
        if progress_cb is not None:
            progress_cb(category.name, index, total)

        if category.safety_level.value == "DANGEROUS":
            report.results.append(
                CleanupResult(
                    category_id=category.id,
                    category_name=category.name,
                    files_deleted=0,
                    space_recovered=0,
                    skipped=0,
                    errors=["Category is DANGEROUS and is never deleted automatically."],
                    dry_run=dry_run,
                )
            )
            continue

        if category.requires_admin and not admin:
            report.results.append(
                CleanupResult(
                    category_id=category.id,
                    category_name=category.name,
                    files_deleted=0,
                    space_recovered=0,
                    skipped=0,
                    errors=["Requires administrator privileges."],
                    dry_run=dry_run,
                )
            )
            continue

        if category.action:
            action_res = run_action(
                category.action,
                dry_run=dry_run,
                is_admin=admin,
                category_name=category.name,
            )
            if action_res is not None:
                report.results.append(action_res)
            continue

        deleted = 0
        recovered = 0
        skipped = 0
        errors: list[str] = []
        permission_errors: list[str] = []
        skip_reasons: list[str] = []
        try:
            targets = list(category.targets)
            if category.finder is not None:
                targets.extend(CacheTarget(path=p) for p in category.finder(*category.finder_args))
            for target in targets:
                if stop_event is not None and stop_event.is_set():
                    raise _Stopped
                if not os.path.exists(target.path) and not os.path.islink(target.path):
                    continue
                d, r, s, e, pe, sr = _delete_target_files(
                    target.path,
                    target.patterns,
                    target.recurse,
                    target.only_files,
                    dry_run,
                    stop_event,
                    use_recycle_bin,
                    excluded,
                )
                deleted += d
                recovered += r
                skipped += s
                errors.extend(e)
                permission_errors.extend(pe)
                skip_reasons.extend(sr)
        except _Stopped:
            report.errors.append("Cleanup stopped by user.")
        except Exception as exc:
            errors.append(f"{category.name}: {exc}")

        report.results.append(
            CleanupResult(
                category_id=category.id,
                category_name=category.name,
                files_deleted=deleted,
                space_recovered=recovered,
                skipped=skipped,
                errors=errors,
                permission_errors=permission_errors,
                skip_reasons=skip_reasons,
                dry_run=dry_run,
            )
        )

    report.duration = (datetime.now() - started).total_seconds()
    return report
