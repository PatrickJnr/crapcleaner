"""Command-line interface for CrapCleaner."""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any

from crapcleaner import __version__
from crapcleaner.analysis.duplicates import find_duplicates
from crapcleaner.analysis.file_types import analyze_file_types
from crapcleaner.analysis.installers import scan_installers
from crapcleaner.analysis.large_files import scan_large_files
from crapcleaner.analysis.recycle_bin import empty_trash, get_recycle_bin_info
from crapcleaner.analysis.storage import analyze_storage_hierarchy
from crapcleaner.config import load_settings
from crapcleaner.core.actions import run_action
from crapcleaner.core.cleaner import clean_categories
from crapcleaner.core.preview import generate_cleanup_preview
from crapcleaner.core.protected_paths import (
    get_protected_rules_summary,
)
from crapcleaner.core.scanner import ScanEngine
from crapcleaner.core.size import compute_dir_size
from crapcleaner.models.category import CleanupCategory, SafetyLevel
from crapcleaner.models.report import CleanupReport, ScanReport
from crapcleaner.registry import find_categories, get_all_categories
from crapcleaner.reports import export_report
from crapcleaner.system.storage_health import get_storage_health_report
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
        description="CrapCleaner - modern cleanup, disk-analysis, and duplicate finder utility.",
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
        "--cleanup-preview",
        action="store_true",
        help="Display a detailed pre-cleanup preview of all candidate files without modifying anything.",
    )
    parser.add_argument(
        "--recycle-bin",
        action="store_true",
        help="Inspect platform Recycle Bin / Trash size, item counts, and timestamps.",
    )
    parser.add_argument(
        "--empty-recycle-bin",
        action="store_true",
        help="Explicitly empty the Recycle Bin / Trash.",
    )
    parser.add_argument(
        "--disk-health",
        action="store_true",
        help="Inspect storage device health, SSD/HDD media type, and TRIM status.",
    )
    parser.add_argument(
        "--storage",
        nargs="?",
        const="",
        metavar="PATH",
        help="Hierarchical storage usage breakdown for a directory or drive (default: user profile).",
    )
    parser.add_argument(
        "--file-types",
        nargs="?",
        const="",
        metavar="PATH",
        help="Analyze storage distribution by functional file type (Images, Videos, Code, etc.).",
    )
    parser.add_argument(
        "--large-files",
        metavar="SIZE",
        help='Scan for files larger than SIZE (e.g. "1GB", "500MB").',
    )
    parser.add_argument(
        "--installers",
        action="store_true",
        help="Detect potentially removable installer and package archives in user folders.",
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
        "--cache-report",
        action="store_true",
        help="Audit developer, engine, and application caches.",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="View recent local cleanup history records.",
    )
    parser.add_argument(
        "--protected-paths",
        action="store_true",
        help="List all active protected filesystem paths and safety rules.",
    )
    parser.add_argument(
        "--export",
        choices=["json", "csv", "txt"],
        help="Export report format (used with --scan, --storage, --disk-health, etc.).",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Output file destination for --export.",
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
        help="Inspect PC hardware and OS specifications.",
    )
    parser.add_argument(
        "--root",
        metavar="PATH",
        help="Root path for file scans (default: user profile).",
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
        "--memory",
        action="store_true",
        help="Report RAM, swap/pagefile, and graphics memory usage.",
    )
    parser.add_argument(
        "--memory-clean",
        metavar="ACTION",
        help=(
            "Run a memory reclamation action "
            "(working_set, standby_list, fs_cache, vram_report). "
            "Use --memory-clean list to see what this system supports."
        ),
    )
    parser.add_argument(
        "--permanent-delete",
        action="store_true",
        help="Delete permanently instead of moving files to the Recycle Bin.",
    )
    parser.add_argument(
        "--startup",
        action="store_true",
        help=(
            "List configured startup applications, locations, and enabled status "
            "(registry Run keys on Windows, XDG autostart entries on Linux)."
        ),
    )
    parser.add_argument(
        "--services",
        action="store_true",
        help=(
            "List background services, status, and startup types "
            "(Windows services, or systemd units on Linux)."
        ),
    )
    parser.add_argument(
        "--system-updates",
        "--windows-updates",
        dest="system_updates",
        action="store_true",
        help=(
            "Check for pending operating-system updates and recent update history "
            "(Windows Update, or the distribution package manager on Linux)."
        ),
    )
    parser.add_argument(
        "--capabilities",
        action="store_true",
        help="Report which platform features are available on this operating system.",
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
                "what_it_contains": c.what_it_contains,
                "why_safe_to_delete": c.why_safe_to_delete,
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
            print(f"  error [{result.category_name}]: {error}", file=sys.stderr)
        for denied in result.permission_errors[:5]:
            print(f"  permission denied [{result.category_name}]: {denied}", file=sys.stderr)
        for reason in result.skip_reasons[:5]:
            print(f"  skipped [{result.category_name}]: {reason}", file=sys.stderr)
    print("-" * 74)
    print(
        f"Total: {report.total_files_deleted} files, {format_size(report.total_space_recovered)} "
        f"recovered, {report.total_skipped} skipped"
    )
    if report.permission_errors:
        print(f"Permission denied on {len(report.permission_errors)} item(s).")


def _confirm_execute(prompt: str = "This will modify or delete files. Continue? [y/N] ") -> bool:
    try:
        answer = input(prompt)
    except EOFError:
        return False
    return answer.strip().lower() in ("y", "yes")


def _print_memory_report(report, json_output: bool) -> None:
    if json_output:
        print(json.dumps(report.to_dict(), indent=2))
        return

    ram = report.ram
    print("=" * 80)
    print(" CrapCleaner Memory Report")
    print("=" * 80)
    print(f"Total RAM:      {format_size(ram.total_bytes)}")
    print(f"In Use:         {format_size(ram.used_bytes)} ({ram.percent_used}%)")
    print(f"Available:      {format_size(ram.available_bytes)}")
    if ram.cached_known:
        print(f"Cached/Standby: {format_size(ram.cached_bytes)}")
    else:
        print("Cached/Standby: not reported by this platform")
    if ram.commit_limit_bytes:
        print(
            f"Committed:      {format_size(ram.commit_bytes)} of "
            f"{format_size(ram.commit_limit_bytes)} commit limit"
        )
    print(f"Memory pressure: {ram.pressure}")
    print(f"Elevated:       {'yes' if is_admin() else 'no'}")
    if ram.swap_supported:
        print(
            f"Swap/Pagefile:  {format_size(ram.swap_used_bytes)} used of "
            f"{format_size(ram.swap_total_bytes)}"
        )
    else:
        print("Swap/Pagefile:  Not configured")
    print("-" * 80)
    if not report.gpus:
        print("Graphics:       No adapter with readable memory counters detected.")
    for gpu in report.gpus:
        vendor = f" [{gpu.vendor}]" if gpu.vendor else ""
        print(f"GPU: {gpu.name}{vendor}")
        if gpu.live_usage_available:
            print(
                f"  VRAM: {format_size(gpu.used_bytes)} used of "
                f"{format_size(gpu.total_bytes)} ({gpu.percent_used}%) via {gpu.source}"
            )
        elif gpu.total_bytes:
            print(f"  VRAM: {format_size(gpu.total_bytes)} installed, live usage unavailable")
        else:
            print("  VRAM: capacity not reported")
    for consumer in report.vram_consumers:
        print(
            f"  Holding VRAM: {consumer.name} (PID {consumer.pid}) {format_size(consumer.used_bytes)}"
        )
    print("=" * 80)


def _run_memory(args, settings: dict) -> int:
    from crapcleaner.system.memory_actions import available_actions
    from crapcleaner.system.memory_actions import run_action as run_memory_action
    from crapcleaner.system.memory_report import get_memory_report

    action_id = args.memory_clean
    if not action_id:
        _print_memory_report(get_memory_report(), args.json)
        return 0

    if action_id == "list":
        actions = available_actions()
        if args.json:
            print(json.dumps([a.to_dict() for a in actions], indent=2))
        else:
            for action in actions:
                admin = " [requires administrator]" if action.requires_admin else ""
                print(f"{action.id}: {action.name}{admin}")
                print(f"    {action.effect}")
        return 0

    dry_run = not args.execute
    result = run_memory_action(action_id, dry_run=dry_run)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.message)
        if result.success and result.measurable and not result.dry_run:
            print(
                f"Available memory: {format_size(result.before.available_bytes)} -> "
                f"{format_size(result.after.available_bytes)} "
                f"(reclaimed {format_size(result.reclaimed_bytes)})"
            )
        if dry_run and result.success:
            print("Nothing was changed. Re-run with --execute to perform this action.")
    return 0 if result.success else 1


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
            args.cleanup_preview,
            args.recycle_bin,
            args.empty_recycle_bin,
            args.disk_health,
            args.storage is not None,
            args.file_types is not None,
            args.large_files,
            args.installers,
            args.duplicates,
            args.cache_report,
            args.history,
            args.protected_paths,
            args.prune_docker,
            args.health_check,
            args.benchmark,
            args.specs,
            args.memory,
            args.memory_clean,
            args.startup,
            args.services,
            args.system_updates,
            args.capabilities,
        )
    ):
        from crapcleaner.gui.app import run_gui

        return run_gui()

    if args.memory or args.memory_clean:
        return _run_memory(args, settings)

    if args.protected_paths:
        rules = get_protected_rules_summary()
        if args.json:
            print(json.dumps(rules, indent=2))
        else:
            print("=" * 80)
            print(" CrapCleaner Protected Filesystem Rules & Safety Layer")
            print("=" * 80)
            for r in rules:
                print(f"[{r['rule_type']}] {r['target']}")
                print(f"  Reason: {r['reason']}")
            print("=" * 80)
        return 0

    if args.recycle_bin:
        info = get_recycle_bin_info()
        if args.json:
            print(json.dumps(info.to_dict(), indent=2))
        else:
            print("=" * 60)
            print(" Recycle Bin / Trash Storage Inspection")
            print("=" * 60)
            print(f"Recoverable Space: {format_size(info.total_size)}")
            print(f"Total Items:       {info.item_count:,}")
            if info.oldest_item:
                print(f"Oldest Item:       {format_datetime(info.oldest_item)}")
            if info.newest_item:
                print(f"Newest Item:       {format_datetime(info.newest_item)}")
            if info.items:
                print("\nSample Deleted Items:")
                for item in info.items[:15]:
                    print(f"  • {item.name:<30} ({format_size(item.size)})")
            print("=" * 60)
        return 0

    if args.empty_recycle_bin:
        if not args.yes and not _confirm_execute(
            "Are you sure you want to empty the Recycle Bin/Trash? [y/N] "
        ):
            print("Cancelled.")
            return 1
        ok = empty_trash()
        print("Recycle Bin emptied successfully." if ok else "Failed to empty Recycle Bin.")
        return 0 if ok else 1

    if args.disk_health:
        health_disks = get_storage_health_report()
        if args.export:
            export_report(
                health_disks,
                report_type="disk_health",
                export_format=args.export,
                output_path=args.output,
            )
            if not args.output:
                print(
                    export_report(
                        health_disks, report_type="disk_health", export_format=args.export
                    )
                )
            return 0
        if args.json:
            print(json.dumps([d.to_dict() for d in health_disks], indent=2))
        else:
            print("=" * 80)
            print(" Storage Device Health & Diagnostics")
            print("=" * 80)
            for d in health_disks:
                trim_str = (
                    "Enabled" if d.trim_enabled else ("Supported" if d.trim_supported else "N/A")
                )
                cap_str = format_size(d.capacity) if d.capacity else "N/A"
                free_str = f" (Free: {format_size(d.free_space)})" if d.free_space else ""
                print(f"Drive: {d.device_id} - {d.model}")
                print(f"  Type: {d.media_type} ({d.bus_type}) | Filesystem: {d.filesystem}")
                print(f"  Capacity: {cap_str}{free_str} | Status: {d.health_status}")
                print(f"  TRIM Status: {trim_str}")
                print("-" * 80)
        return 0

    if args.storage is not None:
        target_path = (
            args.storage
            or args.root
            or settings.get("large_file_default_root")
            or get_user_profile()
        )
        node = analyze_storage_hierarchy(target_path, max_depth=3)
        if node is None:
            print(f"error: unable to inspect storage path {target_path!r}", file=sys.stderr)
            return 1
        if args.export:
            export_report(
                node, report_type="storage", export_format=args.export, output_path=args.output
            )
            if not args.output:
                print(export_report(node, report_type="storage", export_format=args.export))
            return 0
        if args.json:
            print(json.dumps(node.to_dict(), indent=2))
        else:
            print("=" * 70)
            print(
                f" Storage Breakdown: {node.path} ({format_size(node.size)}, {node.file_count:,} files)"
            )
            print("=" * 70)
            for child in node.children:
                print(
                    f"  [DIR] {child.name:<30} {format_size(child.size):>10} ({child.percentage_of_parent:>5.1f}%)"
                )
            print("=" * 70)
        return 0

    if args.file_types is not None:
        target_path = args.file_types or args.root or get_user_profile()
        types_summary = analyze_file_types(target_path)
        if args.json:
            print(json.dumps([t.to_dict() for t in types_summary], indent=2))
        else:
            print(f"File Type Storage Analysis on {target_path}")
            print(f"{'Category':<28} {'Size':>10} {'Files':>8} {'Share':>7}")
            print("-" * 60)
            for s in types_summary:
                print(
                    f"{s.category:<28} {format_size(s.total_size):>10} {s.file_count:>8,} {s.percentage:>6.1f}%"
                )
            print("-" * 60)
        return 0

    if args.installers:
        installs = scan_installers(search_roots=[args.root] if args.root else None)
        if args.json:
            print(json.dumps([item.to_dict() for item in installs], indent=2))
        else:
            print(f"Found {len(installs)} potentially removable installer(s):")
            print(f"{'Size':>10}  {'Modified':<16} Path")
            print("-" * 80)
            for item in installs[:100]:
                print(
                    f"{format_size(item.size):>10}  {format_datetime(item.modified_at)}  {item.path}"
                )
        return 0

    if args.cleanup_preview:
        categories = [
            c
            for c in get_all_categories()
            if c.selected_by_default and c.safety_level in (SafetyLevel.SAFE, SafetyLevel.LOW_RISK)
        ]
        preview = generate_cleanup_preview(categories)
        if args.export:
            export_report(
                preview, report_type="scan", export_format=args.export, output_path=args.output
            )
            if not args.output:
                print(export_report(preview, report_type="scan", export_format=args.export))
            return 0
        if args.json:
            print(json.dumps(preview.to_dict(), indent=2))
        else:
            print("=" * 80)
            print(" CrapCleaner Pre-Cleanup Preview")
            print(
                f" Total Reclaimable: {format_size(preview.total_estimated_size)} ({preview.total_item_count} items)"
            )
            print("=" * 80)
            for c in preview.categories:
                if c.estimated_size == 0 and c.item_count == 0:
                    continue
                admin_str = " [Admin required]" if c.requires_admin else ""
                rev_str = " (Recycle Bin)" if c.reversible else " (Permanent)"
                print(
                    f"\n[Category] {c.category_name} - {format_size(c.estimated_size)} ({c.item_count} items){admin_str}{rev_str}"
                )
                for item in c.items[:10]:
                    print(f"    • {item.path} ({format_size(item.size)})")
            print("\n" + "=" * 80)
        return 0

    if args.cache_report:
        categories = [
            c
            for c in get_all_categories()
            if c.group in ("Developer tools", "Python", "Node.js", ".NET", "Browsers", "Gaming")
        ]
        engine = ScanEngine(categories)
        report = engine.run()
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print("Cache & Developer Tool Audit Report")
            _print_scan(report, json_output=False)
        return 0

    if args.history:
        from crapcleaner.history import load as load_hist

        records = load_hist()
        if args.export:
            export_report(
                records, report_type="history", export_format=args.export, output_path=args.output
            )
            if not args.output:
                print(export_report(records, report_type="history", export_format=args.export))
            return 0
        if args.json:
            print(json.dumps([h.to_dict() for h in records], indent=2))
        else:
            print("Recent Cleanup History:")
            print(f"{'Date':<19} {'Kind':<10} {'Files':>8} {'Recovered':>12}")
            print("-" * 55)
            for r in records[-50:]:
                print(
                    f"{format_datetime(r.started):<19} {r.kind:<10} {r.files_removed:>8} {format_size(r.space_recovered):>12}"
                )
        return 0

    if args.specs:
        from crapcleaner.system.hardware import get_system_specs, print_specs_summary

        specs = get_system_specs()
        print_specs_summary(specs, json_output=args.json)
        return 0

    if args.health_check:
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
        quick_categories = [
            c
            for c in categories
            if c.finder is None and not c.requires_admin and c.selected_by_default
        ][:5]
        engine = ScanEngine(quick_categories)
        report = engine.run(max_files=200)

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

        if args.json:
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
            extra = []
            label = str(stat_item.get("label", ""))
            filesystem = str(stat_item.get("filesystem", ""))
            if label:
                extra.append(label)
            if filesystem:
                extra.append(filesystem)
            suffix = f" [{' · '.join(extra)}]" if extra else ""
            print(
                f"  - Drive {drive_name}{suffix}: {used_sz} used / {total_sz} ({pct_used}% full) · Free: {free_sz}"
            )
        print("-" * 60)
        print(f"Total Storage:     {format_size(total_capacity)} (Free: {format_size(total_free)})")
        print(
            f"Reclaimable Junk:  {format_size(report.total_size)} across {result['categories_with_junk']} active categories"
        )
        print("=" * 60)
        return 0

    if args.benchmark:
        target = os.environ.get("TEMP", os.path.join(get_local_appdata(), "Temp"))
        if not args.json:
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

        if args.json:
            print(json.dumps(res, indent=2))
            return 0

        print("-" * 50)
        print(f"Files Visited:   {count:,}")
        print(f"Total Scanned:   {format_size(total)}")
        print(f"Elapsed Time:    {duration:.3f} s")
        print(f"Traversal Speed: {files_per_sec:,} files/sec ({mb_per_sec:.2f} MB/s)")
        print("-" * 50)
        return 0

    if args.list_categories:
        _print_categories(get_all_categories(), json_output=args.json)
        return 0

    if args.scan:
        from crapcleaner.core.cache import ScanCache

        categories = get_all_categories()
        cache = ScanCache(ttl=float(settings.get("scan_cache_ttl", 300)))
        engine = ScanEngine(categories, cache=cache)
        report = engine.run(max_files=settings.get("max_scan_files", 200000))
        cache.save()
        if args.export:
            export_report(
                report, report_type="scan", export_format=args.export, output_path=args.output
            )
            if not args.output:
                print(export_report(report, report_type="scan", export_format=args.export))
            return 0
        _print_scan(report, json_output=args.json)
        return 0

    if args.large_files:
        threshold = parse_size(args.large_files)
        root = args.root or settings.get("large_file_default_root") or get_user_profile()
        files = scan_large_files(root, threshold)
        if args.json:
            print(json.dumps([f.to_dict() for f in files], indent=2))
        else:
            print(f"{'Size':>10}  {'Modified':<16} {'Type':<16} Path")
            print("-" * 90)
            for item in files[:200]:
                print(
                    f"{format_size(item.size):>10}  {item.last_modified:%Y-%m-%d %H:%M}  "
                    f"{item.file_type:<16} {item.path}"
                )
            print(f"Found {len(files)} files.")
        return 0

    if args.duplicates:
        min_size = parse_size(args.min_dup_size)
        groups = find_duplicates(args.duplicates, min_size)
        if args.json:
            print(json.dumps([g.to_dict() for g in groups], indent=2))
        else:
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
            from crapcleaner.history import append
            from crapcleaner.models.history import HistoryEntry

            append(HistoryEntry.from_report(cleanup_report))
        return 0

    if args.capabilities:
        return _run_capabilities(args)

    if args.startup:
        return _run_startup(args)

    if args.services:
        return _run_services(args)

    if args.system_updates:
        return _run_system_updates(args)

    parser.print_help()
    return 0


def _unsupported(capability_key: str, as_json: bool) -> int:
    """Report a capability the running platform does not provide, and exit non-zero."""
    from crapcleaner.system.capabilities import get_capability

    capability = get_capability(capability_key)
    if as_json:
        print(json.dumps({"supported": False, "reason": capability.unsupported_reason}, indent=2))
    else:
        print(capability.unsupported_reason)
    return 1


def _run_capabilities(args) -> int:
    """Report what this operating system can and cannot do."""
    import platform as _platform

    from crapcleaner.system.capabilities import capability_summary

    summary = capability_summary()
    if args.json:
        print(json.dumps({"platform": sys.platform, "capabilities": summary}, indent=2))
        return 0

    print("=" * 80)
    print("CrapCleaner Platform Capabilities")
    print("=" * 80)
    print(f"Operating System: {_platform.system()} {_platform.release()} ({sys.platform})")
    print("-" * 80)
    print(f"{'Feature':<20} {'Available':<12} Detail")
    print("-" * 80)
    for key, info in summary.items():
        state = "yes" if info["supported"] else "no"
        detail = info["title"] if info["supported"] else info["reason"]
        print(f"{key:<20} {state:<12} {detail}")
    print("=" * 80)
    return 0


def _run_startup(args) -> int:
    from crapcleaner.system.capabilities import STARTUP, get_capability
    from crapcleaner.system.startup import get_startup_items, is_available

    if not is_available():
        return _unsupported(STARTUP, args.json)

    items = get_startup_items(force_refresh=True)
    if args.json:
        print(json.dumps([i.to_dict() for i in items], indent=2))
        return 0

    print("=" * 80)
    print(f"CrapCleaner {get_capability(STARTUP).title}")
    print("=" * 80)
    print(f"{'State':<10} {'Application':<25} {'Location':<25} {'Impact':<10} Command")
    print("-" * 80)
    for item in items:
        state_str = "ENABLED" if item.enabled else "DISABLED"
        print(
            f"{state_str:<10} {item.name[:24]:<25} {item.location[:24]:<25} {item.impact:<10} {item.command}"
        )
    print("-" * 80)
    enabled_cnt = sum(1 for i in items if i.enabled)
    print(
        f"Total: {len(items)} startup items ({enabled_cnt} enabled, {len(items) - enabled_cnt} disabled)."
    )
    return 0


def _run_services(args) -> int:
    from crapcleaner.system.capabilities import SERVICES, get_capability
    from crapcleaner.system.services import get_services_report, is_available

    if not is_available():
        return _unsupported(SERVICES, args.json)

    capability = get_capability(SERVICES)
    services = get_services_report(force_refresh=True)
    if args.json:
        print(json.dumps([s.to_dict() for s in services], indent=2))
        return 0

    noun = capability.terms.get("unit_noun_plural", "services")
    print("=" * 80)
    print(f"CrapCleaner {capability.title}")
    print("=" * 80)
    print(f"{'Status':<10} {'Startup':<16} {'Name':<22} Display Name")
    print("-" * 80)
    for s in services:
        print(f"{s.status:<10} {s.startup_type[:15]:<16} {s.name[:21]:<22} {s.display_name}")
    print("-" * 80)
    running_cnt = sum(1 for s in services if s.status == "Running")
    print(
        f"Total: {len(services)} {noun} ({running_cnt} running, {len(services) - running_cnt} stopped/other)."
    )
    return 0


def _run_system_updates(args) -> int:
    from crapcleaner.system.capabilities import SYSTEM_UPDATES, get_capability
    from crapcleaner.system.system_updates import check_system_updates, is_available

    if not is_available():
        return _unsupported(SYSTEM_UPDATES, args.json)

    capability = get_capability(SYSTEM_UPDATES)
    report = check_system_updates(include_history=True)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    history_label = capability.terms.get("history_label", "Recent Update History")
    print("=" * 80)
    print(f"CrapCleaner {capability.title} Report")
    print("=" * 80)
    print(f"Update Backend: {report.backend or capability.title}")
    print(f"Backend Status: {report.service_status}")
    print(f"Last Checked:   {report.last_checked}")
    if report.reboot_required:
        print("Reboot:         Required to finish applying installed updates.")
    if report.error:
        print(f"Note/Warning:   {report.error}")
    print("-" * 80)
    print("Available Updates:")
    if report.available_updates:
        for u in report.available_updates:
            kb_str = f" ({', '.join(u.kb_numbers)})" if u.kb_numbers else ""
            size_str = f" - {format_size(u.size_bytes)}" if u.size_bytes else ""
            print(f"  - [{u.severity}] {u.title}{kb_str}{size_str}")
    else:
        print("  No pending updates found. System is up to date.")
    print("-" * 80)
    print(f"{history_label} ({len(report.installed_history)} items):")
    for h in report.installed_history[:10]:
        print(f"  - {h.id} ({h.title}): Installed on {h.installed_on or '--'}")
    print("=" * 80)
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
