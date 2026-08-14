"""Command-line interface for CrapCleaner."""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any

from crapcleaner import __version__
from crapcleaner.cleaners.actions import run_action
from crapcleaner.cleaners.cleaner import clean_categories
from crapcleaner.config.settings import load_settings
from crapcleaner.duplicates.finder import DuplicateGroup, find_duplicates
from crapcleaner.large_files.scanner import LargeFile, scan_large_files
from crapcleaner.models.category import CleanupCategory, SafetyLevel
from crapcleaner.models.report import CleanupReport, ScanReport
from crapcleaner.registry import find_categories, get_all_categories
from crapcleaner.scanner.scanner import ScanEngine
from crapcleaner.scanner.size import compute_dir_size
from crapcleaner.utils.format import format_datetime, format_size, parse_size
from crapcleaner.utils.platform import (
    get_drive_info,
    get_local_appdata,
    get_user_profile,
    is_admin,
    list_drives,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crapcleaner",
        description="CrapCleaner - modern Windows cleanup, disk-analysis, and duplicate finder utility.",
    )
    parser.add_argument("--version", action="version", version=f"CrapCleaner {__version__}")
    parser.add_argument("--gui", action="store_true", help="Launch the graphical interface.")
    parser.add_argument("--scan", action="store_true", help="Scan for reclaimable space.")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List all available cleanup categories and exit.",
    )
    parser.add_argument(
        "--clean-safe",
        action="store_true",
        help="Clean all categories that are safe by default (SAFE + LOW_RISK).",
    )
    parser.add_argument(
        "--clean-category",
        action="append",
        nargs="+",
        metavar="NAME",
        help="Clean a category matching NAME (repeatable, substring match).",
    )
    parser.add_argument(
        "--large-files",
        metavar="SIZE",
        help='Scan for files larger than SIZE (e.g. "1GB", "500MB").',
    )
    parser.add_argument(
        "--duplicates",
        metavar="FOLDER",
        action="append",
        help="Scan one or more folders for duplicate files (e.g. --duplicates C:\\Downloads).",
    )
    parser.add_argument(
        "--min-dup-size",
        metavar="SIZE",
        default="1MB",
        help="Minimum file size for duplicate scanning (default: 1MB).",
    )
    parser.add_argument(
        "--prune-docker",
        action="store_true",
        help="Run docker system prune -af to reclaim container and build cache space.",
    )
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Perform a comprehensive system storage and cleanup health check.",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Run disk traversal and hashing throughput benchmarks.",
    )
    parser.add_argument(
        "--specs",
        action="store_true",
        help="Inspect PC hardware and OS specifications (Speccy-style).",
    )
    parser.add_argument(
        "--root",
        metavar="PATH",
        help="Root path for --large-files scans (default: user profile).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without deleting anything.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the cleanup (overrides the dry-run default).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt for real cleanups.",
    )
    parser.add_argument(
        "--permanent-delete",
        action="store_true",
        help="Delete permanently instead of moving files to the Recycle Bin.",
    )
    return parser


def _select_clean_categories(names: list[str]) -> list[CleanupCategory]:
    selected: list[CleanupCategory] = []
    for name in names:
        for category in find_categories(name):
            if category not in selected:
                selected.append(category)
    if not selected:
        print(f"error: no category matches {', '.join(names)!r}", file=sys.stderr)
        return []
    return selected


def _print_categories(categories: list[CleanupCategory], json_output: bool = False) -> None:
    if json_output:
        data = [
            {
                "id": c.id,
                "name": c.name,
                "group": c.group,
                "safety_level": c.safety_level.value,
                "requires_admin": c.requires_admin,
                "selected_by_default": c.selected_by_default,
                "description": c.description,
            }
            for c in categories
        ]
        print(json.dumps(data, indent=2))
        return

    print(f"{'Category ID':<28} {'Name':<36} {'Group':<16} {'Safety':<10} {'Admin':<6}")
    print("-" * 102)
    for c in categories:
        admin_flag = "YES" if c.requires_admin else "NO"
        print(
            f"{c.id[:28]:<28} {c.name[:36]:<36} {c.group[:16]:<16} "
            f"{c.safety_level.label[:10]:<10} {admin_flag:<6}"
        )
    print("-" * 102)
    print(f"Total categories: {len(categories)}")


def _print_scan(report: ScanReport, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps(report.to_dict(), indent=2, default=str))
        return
    print(
        f"Scan started {format_datetime(report.started)}"
        + (", cancelled" if report.cancelled else f", took {report.duration:.1f}s")
    )
    print(f"{'Category':<42} {'Group':<16} {'Safety':<9} {'Files':>8} {'Size':>10}")
    print("-" * 90)
    for result in sorted(report.results, key=lambda r: -r.size):
        if result.size == 0 and result.item_count == 0:
            continue
        print(
            f"{result.name[:42]:<42} {result.group[:16]:<16} "
            f"{result.safety_level[:9]:<9} {result.item_count:>8} {format_size(result.size):>10}"
        )
    print("-" * 90)
    print(f"Total reclaimable: {format_size(report.total_size)} ({report.total_files} files)")
    for result in report.results:
        for error in result.errors[:5]:
            print(f"  warn [{result.name}]: {error}", file=sys.stderr)


def _print_cleanup(report: CleanupReport, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps(report.to_dict(), indent=2, default=str))
        return
    mode = "DRY RUN (nothing deleted)" if report.dry_run else "EXECUTED"
    print(f"Cleanup {mode} - started {format_datetime(report.started)} ({report.duration:.1f}s)")
    if not report.dry_run:
        print(
            "Deletion mode: "
            + ("Recycle Bin (recoverable)" if report.use_recycle_bin else "permanent")
        )
    print(f"{'Category':<42} {'Deleted':>8} {'Skipped':>8} {'Recovered':>10}")
    print("-" * 74)
    for result in report.results:
        print(
            f"{result.category_name[:42]:<42} {result.files_deleted:>8} "
            f"{result.skipped:>8} {format_size(result.space_recovered):>10}"
        )
        for error in result.errors[:5]:
            print(f"  warn [{result.category_name}]: {error}", file=sys.stderr)
    print("-" * 74)
    print(
        f"Total: {report.total_files_deleted} files, {format_size(report.total_space_recovered)} "
        f"recovered, {report.total_skipped} skipped"
    )


def _print_large_files(files: list[LargeFile], json_output: bool = False) -> None:
    if json_output:
        print(json.dumps([f.to_dict() for f in files], indent=2))
        return
    print(f"{'Size':>10}  {'Modified':<16} {'Type':<16} Path")
    print("-" * 90)
    for item in files[:200]:
        print(
            f"{format_size(item.size):>10}  {item.last_modified:%Y-%m-%d %H:%M}  "
            f"{item.file_type:<16} {item.path}"
        )
    print(f"Found {len(files)} files.")


def _print_duplicates(groups: list[DuplicateGroup], json_output: bool = False) -> None:
    if json_output:
        print(json.dumps([g.to_dict() for g in groups], indent=2))
        return
    total_reclaimable = sum(g.reclaimable for g in groups)
    print(f"{'Size':>10} {'Copies':>8} {'Wasted Space':>14} File Path")
    print("-" * 90)
    for g in groups[:100]:
        print(
            f"{format_size(g.size):>10} {len(g.files):>8} {format_size(g.reclaimable):>14} "
            f"{g.files[0]}"
        )
        for copy_path in g.files[1:]:
            print(f"{'':>34} -> {copy_path}")
    print("-" * 90)
    print(
        f"Found {len(groups)} duplicate group(s) with {format_size(total_reclaimable)} reclaimable space."
    )


def _run_health_check(json_output: bool = False) -> int:
    drives = list_drives()
    drive_stats: list[dict[str, Any]] = []
    total_capacity: int = 0
    total_free: int = 0
    for drive_letter in drives:
        try:
            info = get_drive_info(drive_letter)
            total_cap = int(info["total"])
            free_space = int(info["free"])
            used_space = int(info["used"])
            total_capacity += total_cap
            total_free += free_space
            pct = int(used_space / total_cap * 100) if total_cap else 0
            drive_stats.append(
                {
                    "drive": drive_letter,
                    "total": total_cap,
                    "used": used_space,
                    "free": free_space,
                    "used_pct": pct,
                }
            )
        except OSError:
            pass

    admin = is_admin()
    categories = get_all_categories()
    quick_categories = [c for c in categories if c.finder is None]
    engine = ScanEngine(quick_categories)
    report = engine.run(max_files=2000)

    result = {
        "timestamp": datetime.now().isoformat(),
        "admin": admin,
        "drives": drive_stats,
        "total_capacity": total_capacity,
        "total_free": total_free,
        "total_reclaimable": report.total_size,
        "categories_checked": len(categories),
        "categories_with_junk": len([r for r in report.results if r.size > 0]),
    }

    if json_output:
        print(json.dumps(result, indent=2))
        return 0

    print("=" * 60)
    print(" CrapCleaner System Health & Storage Report")
    print("=" * 60)
    print(
        f"Privileges:        {'Administrator (Full system access)' if admin else 'Standard User'}"
    )
    print(f"Monitored Drives:  {len(drive_stats)} volume(s)")
    for stat_item in drive_stats:
        used_sz = format_size(float(stat_item["used"]))
        total_sz = format_size(float(stat_item["total"]))
        free_sz = format_size(float(stat_item["free"]))
        pct_used = stat_item["used_pct"]
        drive_name = stat_item["drive"]
        print(
            f"  - Drive {drive_name}: {used_sz} used / {total_sz} ({pct_used}% full) · Free: {free_sz}"
        )
    print("-" * 60)
    print(f"Total Storage:     {format_size(total_capacity)} (Free: {format_size(total_free)})")
    print(
        f"Reclaimable Junk:  {format_size(report.total_size)} across {result['categories_with_junk']} active categories"
    )
    print("=" * 60)
    return 0


def _run_benchmark(json_output: bool = False) -> int:
    target = os.environ.get("TEMP", os.path.join(get_local_appdata(), "Temp"))
    if not json_output:
        print(f"Benchmarking scanner traversal on {target}...")
    t0 = time.perf_counter()
    total, count, skipped = compute_dir_size(target, max_files=2000)
    t1 = time.perf_counter()
    duration = max(t1 - t0, 0.001)

    files_per_sec = int(count / duration)
    mb_per_sec = (total / (1024 * 1024)) / duration

    res = {
        "target": target,
        "files_scanned": count,
        "bytes_scanned": total,
        "duration_seconds": round(duration, 4),
        "files_per_second": files_per_sec,
        "throughput_mb_s": round(mb_per_sec, 2),
    }

    if json_output:
        print(json.dumps(res, indent=2))
        return 0

    print("-" * 50)
    print(f"Files Visited:   {count:,}")
    print(f"Total Scanned:   {format_size(total)}")
    print(f"Elapsed Time:    {duration:.3f} s")
    print(f"Traversal Speed: {files_per_sec:,} files/sec ({mb_per_sec:.2f} MB/s)")
    print("-" * 50)
    return 0


def _confirm_execute() -> bool:
    try:
        answer = input("This will modify or delete files. Continue? [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = load_settings()

    if args.gui or not any(
        (
            args.scan,
            args.list_categories,
            args.clean_safe,
            args.clean_category,
            args.large_files,
            args.duplicates,
            args.prune_docker,
            args.health_check,
            args.benchmark,
            args.specs,
        )
    ):
        from crapcleaner.gui.app import run_gui

        return run_gui()

    if args.specs:
        from crapcleaner.specs.hardware import get_system_specs, print_specs_summary

        specs = get_system_specs()
        print_specs_summary(specs, json_output=args.json)
        return 0

    if args.health_check:
        return _run_health_check(json_output=args.json)

    if args.benchmark:
        return _run_benchmark(json_output=args.json)

    if args.list_categories:
        _print_categories(get_all_categories(), json_output=args.json)
        return 0

    if args.scan:
        from crapcleaner.scanner.cache import ScanCache

        categories = get_all_categories()
        cache = ScanCache(ttl=float(settings.get("scan_cache_ttl", 300)))
        engine = ScanEngine(categories, cache=cache)
        report = engine.run(max_files=settings.get("max_scan_files", 200000))
        cache.save()
        _print_scan(report, json_output=args.json)
        return 0

    if args.large_files:
        threshold = parse_size(args.large_files)
        root = args.root or settings.get("large_file_default_root") or get_user_profile()
        files = scan_large_files(root, threshold)
        _print_large_files(files, json_output=args.json)
        return 0

    if args.duplicates:
        min_size = parse_size(args.min_dup_size)
        groups = find_duplicates(args.duplicates, min_size)
        _print_duplicates(groups, json_output=args.json)
        return 0

    if args.prune_docker:
        dry_run = args.dry_run or (not args.execute and settings.get("dry_run_default", True))
        if not dry_run and not args.yes and not _confirm_execute():
            print("Cancelled.")
            return 1
        result = run_action("docker_system_prune", dry_run=dry_run, is_admin=is_admin())
        if result and result.errors:
            print(f"error: {result.errors[0]}", file=sys.stderr)
            return 1
        print(
            "Docker prune completed successfully."
            if not dry_run
            else "Docker prune dry-run simulated."
        )
        return 0

    if args.clean_safe or args.clean_category:
        if args.clean_category:
            categories = _select_clean_categories(
                [n for group in args.clean_category for n in group]
            )
        else:
            categories = [
                c
                for c in get_all_categories()
                if c.selected_by_default
                and c.safety_level in (SafetyLevel.SAFE, SafetyLevel.LOW_RISK)
            ]
        if not categories:
            print("error: no categories selected for cleanup", file=sys.stderr)
            return 1

        dry_run = args.dry_run or (not args.execute and settings.get("dry_run_default", True))
        if not dry_run and not args.yes and not _confirm_execute():
            print("Cancelled.")
            return 1

        use_recycle_bin = not args.permanent_delete and settings.get("use_recycle_bin", True)
        cleanup_report = clean_categories(
            categories,
            dry_run=dry_run,
            use_recycle_bin=use_recycle_bin,
        )
        _print_cleanup(cleanup_report, json_output=args.json)
        if not dry_run:
            from crapcleaner.history.store import append
            from crapcleaner.models.history import HistoryEntry

            append(HistoryEntry.from_report(cleanup_report))
        return 0

    parser.print_help()
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
