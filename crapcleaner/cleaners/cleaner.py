"""Cleanup engine: deletes files per category, skips locked items, continues on errors."""

import os
import threading
from collections.abc import Callable
from datetime import datetime

from crapcleaner.cleaners.actions import run_action
from crapcleaner.models.category import CacheTarget, CleanupCategory
from crapcleaner.models.report import CleanupReport, CleanupResult
from crapcleaner.utils.files import (
    recycle_file,
    recycle_tree,
    remove_file,
    remove_tree,
)
from crapcleaner.utils.platform import is_admin

ProgressCallback = Callable[[str, int, int], None]
StopEvent = threading.Event | None


def _delete_target_files(
    target_path: str,
    patterns: tuple,
    recurse: bool,
    only_files: bool,
    dry_run: bool,
    stop_event: StopEvent,
    use_recycle_bin: bool = False,
) -> tuple:
    deleted = 0
    recovered = 0
    skipped = 0
    errors: list[str] = []

    def handle_file(path: str) -> None:
        nonlocal deleted, recovered, skipped
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
        except OSError as exc:
            skipped += 1
            errors.append(f"{path}: {exc}")

    def handle_tree(path: str) -> None:
        nonlocal deleted, recovered, skipped
        if dry_run:
            for root, dirs, files in os.walk(path):
                if stop_event is not None and stop_event.is_set():
                    raise _Stopped
                for name in files:
                    deleted += 1
                    try:
                        recovered += os.path.getsize(os.path.join(root, name))
                    except OSError:
                        pass
            return
        if use_recycle_bin and not patterns:
            size = 0
            count = 0
            for root, dirs, files in os.walk(path):
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
            return
        total_size = 0
        total_files = 0
        for root, dirs, files in os.walk(path, topdown=False):
            if stop_event is not None and stop_event.is_set():
                raise _Stopped
            for name in files:
                full = os.path.join(root, name)
                if patterns and not _name_matches(name, patterns):
                    continue
                try:
                    total_size += os.path.getsize(full)
                except OSError:
                    pass
                try:
                    if recycle_file(full) if use_recycle_bin else remove_file(full):
                        total_files += 1
                    else:
                        skipped += 1
                except OSError as exc:
                    skipped += 1
                    errors.append(f"{full}: {exc}")
            for name in dirs:
                full = os.path.join(root, name)
                if recycle_tree(full) if use_recycle_bin else remove_tree(full):
                    pass
                else:
                    skipped += 1
        deleted += total_files
        recovered += total_size
        if os.path.isdir(path) and not os.path.exists(path):
            pass

    try:
        if only_files and os.path.isfile(target_path):
            handle_file(target_path)
            return deleted, recovered, skipped, errors

        if not os.path.isdir(target_path):
            return deleted, recovered, skipped, errors

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
                errors.append(f"{target_path}: {exc}")
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
                errors.append(f"{target_path}: {exc}")
    except _Stopped:
        raise

    return deleted, recovered, skipped, errors


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
) -> CleanupReport:
    started = datetime.now()
    report = CleanupReport(started=started, dry_run=dry_run, use_recycle_bin=use_recycle_bin)
    admin = is_admin()
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
        try:
            targets = list(category.targets)
            if category.finder is not None:
                targets.extend(CacheTarget(path=p) for p in category.finder(*category.finder_args))
            for target in targets:
                if stop_event is not None and stop_event.is_set():
                    raise _Stopped
                if not os.path.exists(target.path) and not os.path.islink(target.path):
                    continue
                d, r, s, e = _delete_target_files(
                    target.path,
                    target.patterns,
                    target.recurse,
                    target.only_files,
                    dry_run,
                    stop_event,
                    use_recycle_bin,
                )
                deleted += d
                recovered += r
                skipped += s
                errors.extend(e)
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
                dry_run=dry_run,
            )
        )

    report.duration = (datetime.now() - started).total_seconds()
    return report
