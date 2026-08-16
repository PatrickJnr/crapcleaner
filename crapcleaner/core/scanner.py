"""Scan engine: walks all categories and computes reclaimable space."""

import os
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from crapcleaner.core.cache import ScanCache
from crapcleaner.core.size import _Cancelled, compute_dir_size
from crapcleaner.models.category import CleanupCategory
from crapcleaner.models.report import ScanCategoryResult, ScanReport

ProgressCallback = Callable[[str, str, int], None]
StopEvent = threading.Event | None

_MAX_WORKERS = 8


def scan_category(
    category: CleanupCategory,
    stop_event: StopEvent = None,
    max_files: int = 200000,
    cache: ScanCache | None = None,
) -> ScanCategoryResult:
    total = 0
    count = 0
    skipped = 0
    errors: list[str] = []
    counter = [0]

    if not category.has_targets:
        return ScanCategoryResult(
            category_id=category.id,
            name=category.name,
            size=0,
            item_count=0,
            skipped=0,
            safety_level=category.safety_level.value,
            group=category.group,
            description=category.description,
            reclaimable=category.reclaimable,
            errors=[],
        )

    for target in category.targets:
        if stop_event is not None and stop_event.is_set():
            raise _Cancelled
        if not target.exists:
            continue
        if target.only_files and os.path.isfile(target.path):
            try:
                total += os.path.getsize(target.path)
                count += 1
            except OSError:
                skipped += 1
            continue
        if cache is not None:
            cached = cache.get_dir(
                target.path,
                target.patterns,
                target.recurse,
                target.only_files,
                max_files,
            )
            if cached is not None:
                total += cached[0]
                count += cached[1]
                skipped += cached[2]
                continue
        try:
            t, c, s = compute_dir_size(
                target.path,
                patterns=target.patterns,
                recurse=target.recurse,
                only_files=target.only_files,
                max_files=max_files,
                stop_event=stop_event,
                counter=counter,
            )
            total += t
            count += c
            skipped += s
            if cache is not None:
                cache.put_dir(
                    target.path,
                    target.patterns,
                    target.recurse,
                    target.only_files,
                    max_files,
                    t,
                    c,
                    s,
                )
        except _Cancelled:
            raise
        except OSError as exc:
            errors.append(f"{target.path}: {exc}")

    if category.finder is not None:
        if cache is not None:
            found_paths = cache.get_finder(category.finder, category.finder_args)
        else:
            found_paths = None
        if found_paths is None:
            found_paths = category.finder(*category.finder_args)
            if cache is not None:
                cache.put_finder(category.finder, category.finder_args, found_paths)
        for found in found_paths:
            if stop_event is not None and stop_event.is_set():
                raise _Cancelled
            if cache is not None:
                cached = cache.get_dir(found, (), True, False, max_files)
                if cached is not None:
                    total += cached[0]
                    count += cached[1]
                    skipped += cached[2]
                    continue
            try:
                t, c, s = compute_dir_size(
                    found,
                    max_files=max_files,
                    stop_event=stop_event,
                    counter=counter,
                )
                total += t
                count += c
                skipped += s
                if cache is not None:
                    cache.put_dir(found, (), True, False, max_files, t, c, s)
            except _Cancelled:
                raise
            except OSError as exc:
                errors.append(f"{found}: {exc}")

    category.size = total
    category.item_count = count
    category.skipped = skipped
    category.errors = errors

    return ScanCategoryResult(
        category_id=category.id,
        name=category.name,
        size=total,
        item_count=count,
        skipped=skipped,
        safety_level=category.safety_level.value,
        group=category.group,
        description=category.description,
        reclaimable=category.reclaimable,
        errors=errors,
    )


class ScanEngine:
    def __init__(
        self,
        categories: list[CleanupCategory] | None = None,
        cache: ScanCache | None = None,
    ):
        self.categories = categories or []
        self._cache = cache
        self._stop_event = threading.Event()

    def request_stop(self) -> None:
        self._stop_event.set()

    @property
    def stop_requested(self) -> bool:
        return self._stop_event.is_set()

    def run(
        self,
        progress_cb: ProgressCallback | None = None,
        max_files: int = 200000,
    ) -> ScanReport:
        started = datetime.now()
        report = ScanReport(started=started)
        total_categories = len(self.categories)

        if total_categories == 0:
            report.duration = 0.0
            return report

        def scan_one(index: int, category: CleanupCategory):
            if self._stop_event.is_set():
                return None
            try:
                return scan_category(
                    category, self._stop_event, max_files=max_files, cache=self._cache
                )
            except _Cancelled:
                return None
            except Exception as exc:  # pragma: no cover - defensive
                return exc

        def error_result(category: CleanupCategory, exc: str) -> ScanCategoryResult:
            return ScanCategoryResult(
                category_id=category.id,
                name=category.name,
                size=0,
                item_count=0,
                skipped=0,
                safety_level=category.safety_level.value,
                group=category.group,
                description=category.description,
                reclaimable=category.reclaimable,
                errors=[exc],
            )

        workers = min(_MAX_WORKERS, total_categories)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = []
            for index, category in enumerate(self.categories):
                if self._stop_event.is_set():
                    break
                if progress_cb is not None:
                    progress_cb(category.name, f"{index + 1}/{total_categories}", 0)
                futures.append(pool.submit(scan_one, index, category))

            # Collect in submission order so results/progress stay deterministic.
            for index, future in enumerate(futures):
                outcome = future.result()
                category = self.categories[index]
                if progress_cb is not None:
                    progress_cb(category.name, f"{index + 1}/{total_categories}", 1)
                if outcome is None:
                    continue
                if isinstance(outcome, Exception):
                    report.errors.append(f"{category.name}: {outcome}")
                    report.results.append(error_result(category, str(outcome)))
                else:
                    report.results.append(outcome)

        if self._stop_event.is_set():
            report.cancelled = True

        report.duration = (datetime.now() - started).total_seconds()
        return report
