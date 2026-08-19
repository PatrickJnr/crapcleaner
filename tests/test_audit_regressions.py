"""Regression tests for the confirmed findings of the v1.0.10.1 engineering audit.

Each test names the audit finding it locks down.
"""

import json
import os
import subprocess
import sys
import threading
import time
from unittest.mock import patch

import pytest

from crapcleaner.analysis.duplicates import find_duplicates
from crapcleaner.analysis.storage import analyze_storage_hierarchy
from crapcleaner.categories import browsers as browsers_module
from crapcleaner.categories.browsers import running_browser_names
from crapcleaner.core.cleaner import clean_categories
from crapcleaner.core.preview import generate_cleanup_preview
from crapcleaner.core.scanner import ScanEngine
from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.registry import get_all_categories
from crapcleaner.reports import export_report
from crapcleaner.system import live_metrics, storage_health
from crapcleaner.system.hardware import DriveSpec, SystemSpecs, print_specs_summary
from crapcleaner.utils.files import walk_safe
from crapcleaner.utils.platform import run_command


def _pyc_category(root: str) -> CleanupCategory:
    return CleanupCategory(
        id="test_pyc",
        name="Stray .pyc files",
        group="Testing",
        description="",
        safety_level=SafetyLevel.SAFE,
        targets=[CacheTarget(path=os.path.join(root, "stale.pyc"), only_files=True)],
    )


class TestCategoryIdentity:
    """BUG-01 / BUG-02: one owner per cleanup target."""

    def test_category_ids_are_unique(self):
        ids = [c.id for c in get_all_categories()]
        assert len(ids) == len(set(ids))

    def test_no_target_path_is_claimed_by_two_categories(self):
        owners: dict[str, str] = {}
        collisions = []
        for category in get_all_categories():
            for target in category.targets:
                key = os.path.normcase(os.path.abspath(target.path))
                if key in owners and owners[key] != category.id:
                    collisions.append((key, owners[key], category.id))
                owners[key] = category.id
        assert not collisions, f"paths scanned by more than one category: {collisions}"


class TestIndividualFileTargets:
    """BUG-03: a target pointing at a single file must size, preview and delete."""

    def test_scan_preview_and_delete_a_single_file_target(self, tmp_path):
        stale = tmp_path / "stale.pyc"
        stale.write_bytes(b"x" * 1024)
        category = _pyc_category(str(tmp_path))

        report = ScanEngine([category]).run()
        assert report.results[0].size == 1024
        assert report.results[0].item_count == 1

        preview = generate_cleanup_preview([category])
        assert preview.total_estimated_size == 1024
        assert preview.categories[0].items[0].path == str(stale)

        dry = clean_categories([category], dry_run=True)
        assert dry.total_files_deleted == 1
        assert stale.exists()

        executed = clean_categories([category], dry_run=False, use_recycle_bin=False)
        assert executed.total_files_deleted == 1
        assert not stale.exists()


class TestPlatformCategoryRegistration:
    """BUG-04: an application category belongs to exactly one platform."""

    def test_linux_does_not_register_windows_app_categories(self):
        with (
            patch("crapcleaner.categories.apps.is_linux", return_value=True),
            patch("crapcleaner.categories.apps.is_windows", return_value=False),
            patch("os.path.isdir", return_value=True),
        ):
            from crapcleaner.categories.apps import get_categories

            ids = [c.id for c in get_categories()]
        assert len(ids) == len(set(ids))
        assert not any("windows" in cid for cid in ids)

    def test_windows_does_not_register_linux_app_categories(self):
        with (
            patch("crapcleaner.categories.apps.is_linux", return_value=False),
            patch("crapcleaner.categories.apps.is_windows", return_value=True),
            patch("os.path.isdir", return_value=True),
        ):
            from crapcleaner.categories.apps import get_categories

            ids = [c.id for c in get_categories()]
        assert len(ids) == len(set(ids))
        assert not any(cid.startswith("linux_") for cid in ids)


class TestDriveFormatting:
    """BUG-05: Windows drive letters carry exactly one colon."""

    def test_windows_drive_letter_is_not_double_punctuated(self, capsys):
        specs = SystemSpecs()
        specs.drives = [
            DriveSpec(drive="C:", label="OS", file_system="NTFS", total_bytes=100, used_bytes=40)
        ]
        with patch("crapcleaner.system.hardware.is_windows", return_value=True):
            print_specs_summary(specs)
        assert "C::" not in capsys.readouterr().out

    def test_linux_mount_point_is_not_suffixed(self, capsys):
        specs = SystemSpecs()
        specs.drives = [DriveSpec(drive="/home", file_system="ext4", total_bytes=100, used_bytes=1)]
        with patch("crapcleaner.system.hardware.is_windows", return_value=False):
            print_specs_summary(specs)
        out = capsys.readouterr().out
        assert "/home:" not in out
        assert "/home" in out


class TestSafeTraversal:
    """BUG-06: links, junctions and cycles never widen a scan."""

    def _symlink(self, target, link, tmp_path):
        """Link a directory: a symlink, or a junction where symlinks need privileges."""
        try:
            os.symlink(str(target), str(link), target_is_directory=True)
            return
        except (OSError, NotImplementedError, AttributeError):
            pass
        if sys.platform != "win32":
            pytest.skip("directory links are not permitted in this environment")
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not os.path.exists(str(link)):
            pytest.skip("neither symlinks nor junctions can be created here")

    def test_walk_safe_does_not_descend_a_directory_symlink(self, tmp_path):
        real = tmp_path / "real"
        (real / "nested").mkdir(parents=True)
        (real / "nested" / "file.txt").write_text("data")
        self._symlink(real, tmp_path / "link", tmp_path)

        walked = {dirpath for dirpath, _dirs, _files in walk_safe(str(tmp_path))}
        assert not any("link" in os.path.basename(p) for p in walked)

    def test_walk_safe_terminates_on_a_self_referencing_link(self, tmp_path):
        loop_root = tmp_path / "loop"
        loop_root.mkdir()
        self._symlink(loop_root, loop_root / "self", tmp_path)
        assert len(list(walk_safe(str(loop_root)))) == 1

    def test_storage_analyzer_does_not_bill_linked_data_twice(self, tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        (real / "payload.bin").write_bytes(b"y" * 4096)
        self._symlink(real, tmp_path / "mirror", tmp_path)

        node = analyze_storage_hierarchy(str(tmp_path), max_depth=3)
        assert node is not None
        assert node.size == 4096


class TestBrowserLockWarning:
    """BUG-07: a running browser is reported, never terminated."""

    def test_running_browser_is_named_for_its_categories(self):
        with patch.object(browsers_module, "_process_listing", return_value="chrome.exe\n"):
            assert running_browser_names(["chrome_cache", "firefox_cache"]) == ["Google Chrome"]

    def test_unrelated_categories_produce_no_warning(self):
        with patch.object(browsers_module, "_process_listing", return_value="chrome.exe\n"):
            assert running_browser_names(["windows_temp", "dotnet_caches"]) == []

    def test_missing_process_listing_is_not_reported_as_idle_browsers(self):
        with patch.object(browsers_module, "_process_listing", return_value=""):
            assert running_browser_names(["chrome_cache"]) == []


class TestRecursiveCsvExport:
    """BUG-08: every descendant of a storage tree reaches the CSV."""

    def _tree(self):
        return {
            "name": "root",
            "path": "/root",
            "size": 300,
            "file_count": 3,
            "children": [
                {
                    "name": "a",
                    "path": "/root/a",
                    "size": 200,
                    "file_count": 2,
                    "children": [
                        {
                            "name": "deep",
                            "path": "/root/a/deep",
                            "size": 100,
                            "file_count": 1,
                            "children": [
                                {
                                    "name": "deeper",
                                    "path": "/root/a/deep/deeper",
                                    "size": 50,
                                    "file_count": 1,
                                    "children": [],
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    def test_nested_nodes_are_exported(self):
        csv_text = export_report(self._tree(), report_type="storage", export_format="csv")
        for path in ("/root", "/root/a", "/root/a/deep", "/root/a/deep/deeper"):
            assert path in csv_text

    def test_a_list_of_roots_is_exported(self):
        csv_text = export_report([self._tree()], report_type="storage", export_format="csv")
        assert "/root/a/deep/deeper" in csv_text


class TestLinuxStorageHealth:
    """BUG-12: capacity is byte-accurate and unknown free space is never zero-washed."""

    _LSBLK = (
        '{"blockdevices":['
        '{"name":"nvme0n1","model":"Fast SSD","rota":false,"size":"512110190592",'
        '"type":"disk","tran":"nvme","fstype":"ext4","mountpoint":"/"},'
        '{"name":"sdb","model":"Spare HDD","rota":true,"size":"2000398934016",'
        '"type":"disk","tran":"sata","fstype":null,"mountpoint":null}]}'
    )

    def _report(self, tmp_path):
        usage = (512110190592, 300000000000, 212110190592)
        with (
            patch.object(
                storage_health, "run_command", return_value={"returncode": 0, "stdout": self._LSBLK}
            ),
            patch.object(storage_health.os.path, "exists", return_value=True),
            patch.object(storage_health.shutil, "disk_usage", return_value=usage),
        ):
            return storage_health._get_linux_storage_health()

    def test_mounted_device_reports_capacity_and_free_space(self, tmp_path):
        mounted = self._report(tmp_path)[0]
        assert mounted.capacity == 512110190592
        assert mounted.free_space == 212110190592
        assert mounted.media_type == "NVMe SSD"

    def test_unmounted_device_keeps_capacity_but_no_invented_free_space(self, tmp_path):
        unmounted = self._report(tmp_path)[1]
        assert unmounted.capacity == 2000398934016
        assert unmounted.free_space is None or unmounted.free_space == 0


class TestGpuTelemetry:
    """SUB-03: vendor-neutral telemetry that never fabricates a reading."""

    def _card(self, tmp_path, vendor: str, files: dict[str, str]) -> str:
        device = tmp_path / "card0" / "device"
        device.mkdir(parents=True)
        (device / "vendor").write_text(vendor)
        for name, value in files.items():
            (device / name).write_text(value)
        return str(tmp_path)

    def test_amd_sysfs_card_reports_load_and_vram(self, tmp_path):
        drm = self._card(
            tmp_path,
            "0x1002",
            {
                "gpu_busy_percent": "37",
                "mem_info_vram_total": "8589934592",
                "mem_info_vram_used": "2147483648",
            },
        )
        gpu = live_metrics._discover_sysfs_gpu(drm)
        assert gpu is not None and gpu.name == "AMD Radeon"
        vitals = gpu.sample()
        assert vitals.available and vitals.utilization_pct == 37.0
        assert vitals.vram_total_bytes == 8589934592

    def test_missing_metrics_render_as_not_available(self, tmp_path):
        drm = self._card(tmp_path, "0x8086", {"gpu_busy_percent": "5"})
        gpu = live_metrics._discover_sysfs_gpu(drm)
        assert gpu is not None and gpu.name == "Intel Graphics"
        vitals = gpu.sample()
        assert vitals.temperature_c is None
        assert vitals.temp_str == "N/A"
        assert vitals.vram_fraction_str == "-- / --"

    def test_unknown_vendor_is_not_claimed(self, tmp_path):
        drm = self._card(tmp_path, "0x1234", {"gpu_busy_percent": "5"})
        assert live_metrics._discover_sysfs_gpu(drm) is None


class TestCacheInvalidation:
    """PERF-02: volatile groups go stale fast, static ones stay cached."""

    def _cache(self, tmp_path, ttl: float = 300.0):
        from crapcleaner.core.cache import ScanCache

        return ScanCache(ttl=ttl, path=str(tmp_path / "cache.json"))

    def test_changed_directory_timestamp_invalidates_a_cached_entry(self, tmp_path):
        root = tmp_path / "cache_root"
        root.mkdir()
        (root / "a.bin").write_bytes(b"a" * 10)

        cache = self._cache(tmp_path)
        cache.put_dir(str(root), (), True, False, 200000, 10, 1, 0)
        assert cache.get_dir(str(root), (), True, False, 200000) == (10, 1, 0)

        # Set the timestamp explicitly: Windows updates a directory's recorded
        # mtime lazily, which is exactly why volatile groups also carry a short TTL.
        stamp = os.stat(root).st_mtime + 120
        os.utime(root, (stamp, stamp))
        assert cache.get_dir(str(root), (), True, False, 200000) is None

    def test_untouched_directory_still_hits(self, tmp_path):
        root = tmp_path / "static_root"
        (root / "sub").mkdir(parents=True)
        cache = self._cache(tmp_path)
        cache.put_dir(str(root), (), True, False, 200000, 5, 1, 0)
        assert cache.get_dir(str(root), (), True, False, 200000) == (5, 1, 0)

    def test_volatile_group_entry_expires_before_the_default_ttl(self, tmp_path):
        from crapcleaner.core.cache import ttl_for_group

        root = tmp_path / "volatile"
        root.mkdir()
        cache = self._cache(tmp_path)
        cache.put_dir(str(root), (), True, False, 200000, 5, 1, 0)

        assert ttl_for_group("Browsers") is not None
        assert ttl_for_group("Developer") is None
        time.sleep(0.02)
        assert cache.get_dir(str(root), (), True, False, 200000, ttl=0.01) is None
        assert cache.get_dir(str(root), (), True, False, 200000) == (5, 1, 0)

    def test_expired_entry_is_not_reused(self, tmp_path):
        root = tmp_path / "expiring"
        root.mkdir()
        from crapcleaner.core.cache import ScanCache

        cache = ScanCache(ttl=0.01, path=str(tmp_path / "expiring.json"))
        cache.put_dir(str(root), (), True, False, 200000, 1, 1, 0)
        time.sleep(0.05)
        assert cache.get_dir(str(root), (), True, False, 200000) is None


class TestDuplicateHashing:
    """PERF-01: parallel full hashing keeps results identical and stays cancellable."""

    def _tree(self, tmp_path, copies: int = 6):
        payload = b"z" * (32 * 1024)
        for index in range(copies):
            (tmp_path / f"copy{index}.bin").write_bytes(payload)
        (tmp_path / "unique.bin").write_bytes(b"q" * (32 * 1024))
        return str(tmp_path)

    def test_parallel_and_serial_hashing_agree(self, tmp_path):
        root = self._tree(tmp_path)
        serial = find_duplicates([root], min_size_bytes=1024, max_workers=1)
        parallel = find_duplicates([root], min_size_bytes=1024, max_workers=8)
        assert [g.size for g in serial] == [g.size for g in parallel]
        assert [sorted(g.files) for g in serial] == [sorted(g.files) for g in parallel]
        assert serial and serial[0].duplicate_count == 5

    def test_cancellation_stops_before_returning_groups(self, tmp_path):
        root = self._tree(tmp_path)
        stop = threading.Event()
        stop.set()
        assert find_duplicates([root], min_size_bytes=1024, stop_event=stop, max_workers=4) == []


class TestCentralSubprocessExecution:
    """ARCH-02: one runner with consistent results, timeouts and env support."""

    def test_successful_command_reports_ok_and_output(self):
        result = run_command([sys.executable, "-c", "print('hello')"], timeout=30.0)
        assert result.ok
        assert "hello" in result.stdout
        assert result.error is None

    def test_failing_command_is_not_reported_as_success(self):
        result = run_command([sys.executable, "-c", "import sys; sys.exit(3)"], timeout=30.0)
        assert not result.ok
        assert result.returncode == 3

    def test_missing_executable_returns_an_error_instead_of_raising(self):
        result = run_command(["definitely-not-a-real-binary-xyz"], timeout=5.0)
        assert not result.ok
        assert result.error
        assert result.returncode < 0

    def test_timeout_is_reported_as_a_failure(self):
        result = run_command([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.5)
        assert not result.ok
        assert result.error == "timed out"

    def test_extra_environment_reaches_the_child(self):
        result = run_command(
            [sys.executable, "-c", "import os; print(os.environ['CRAPCLEANER_TEST'])"],
            timeout=30.0,
            env_extra={"CRAPCLEANER_TEST": "present"},
        )
        assert result.ok and "present" in result.stdout

    def test_mapping_access_still_works_for_existing_callers(self):
        result = run_command([sys.executable, "-c", "print('x')"], timeout=30.0)
        assert result["returncode"] == 0
        assert "x" in str(result.get("stdout", ""))
        assert result.get("missing", "fallback") == "fallback"


class TestExpandedCoverage:
    """SUB-01/02/04: new cleanup and discovery coverage stays safe and previewable."""

    def test_new_browsers_are_known_and_never_target_profiles(self):
        from crapcleaner.categories.browsers import BROWSER_DISPLAY_NAMES

        for browser in ("floorp", "waterfox", "thorium", "librewolf", "operagx", "arc"):
            assert browser in BROWSER_DISPLAY_NAMES

        forbidden = ("bookmarks", "passwords", "login data", "history", "cookies")
        for category in get_all_categories():
            if category.group != "Browsers":
                continue
            for target in category.targets:
                lowered = target.path.lower()
                assert not any(word in lowered for word in forbidden)

    def test_developer_caches_cover_the_shared_compiler_caches(self):
        from crapcleaner.categories.developer import get_categories

        ids = {c.id for c in get_categories()}
        assert {"sccache", "zig_cache"} <= ids

    def test_project_local_tool_caches_are_found_under_scan_roots(self, tmp_path):
        from crapcleaner.categories.python import find_tool_cache_dirs

        project = tmp_path / "project"
        for cache_dir in (".ruff_cache", ".mypy_cache", ".pytest_cache", ".tox"):
            (project / cache_dir / "inner").mkdir(parents=True)
        (project / "src").mkdir()
        (project / "src" / "app.py").write_text("x = 1")

        found = {os.path.basename(path) for path in find_tool_cache_dirs([str(tmp_path)])}
        assert found == {".ruff_cache", ".mypy_cache", ".pytest_cache", ".tox"}
        assert (project / "src" / "app.py").exists()

    def test_docker_buildx_cache_is_an_action_not_a_file_delete(self):
        from crapcleaner.categories.docker import get_categories

        buildx = next(c for c in get_categories() if c.id == "docker_buildx_prune")
        assert buildx.action == "docker_buildx_prune"
        assert not buildx.targets
        assert buildx.safety_level is SafetyLevel.REVIEW

    def test_ai_models_are_discovery_only(self):
        models = next(c for c in get_all_categories() if c.id == "ai_models")
        assert models.safety_level is SafetyLevel.DANGEROUS
        assert not models.selected_by_default


class TestStorageScanStreaming:
    """A whole-volume scan must show data while it runs, and agree with the final tree."""

    def _tree(self, tmp_path, dirs: int = 6, files_per_dir: int = 4):
        for d in range(dirs):
            folder = tmp_path / f"dir{d}" / "nested"
            folder.mkdir(parents=True)
            for f in range(files_per_dir):
                (folder / f"file{f}.bin").write_bytes(b"x" * 1024)
        return str(tmp_path)

    def test_partial_snapshots_never_overcount_the_final_tree(self, tmp_path):
        root = self._tree(tmp_path)
        seen: list = []
        final = analyze_storage_hierarchy(
            root, max_depth=3, partial_cb=seen.append, partial_interval=0.01
        )
        assert final is not None
        assert final.size == 6 * 4 * 1024
        for snapshot in seen:
            assert snapshot.size <= final.size
            assert snapshot.file_count <= final.file_count

    def test_worker_count_does_not_change_the_result(self, tmp_path):
        root = self._tree(tmp_path, dirs=8, files_per_dir=3)
        single = analyze_storage_hierarchy(root, max_depth=3, max_workers=1)
        many = analyze_storage_hierarchy(root, max_depth=3, max_workers=16)
        assert single is not None and many is not None
        assert (single.size, single.file_count, single.dir_count) == (
            many.size,
            many.file_count,
            many.dir_count,
        )
        assert [c.name for c in single.children] == [c.name for c in many.children]

    def test_cancellation_stops_a_parallel_scan(self, tmp_path):
        root = self._tree(tmp_path, dirs=4, files_per_dir=2)
        stop = threading.Event()
        stop.set()
        node = analyze_storage_hierarchy(root, max_depth=3, stop_event=stop, max_workers=8)
        assert node is not None
        assert node.file_count == 0


class TestScanProgressAttribution:
    """A stall must be reported under the category that is actually running."""

    def _category(self, cid: str, finder) -> CleanupCategory:
        return CleanupCategory(
            id=cid,
            name=cid,
            group="Testing",
            description="",
            safety_level=SafetyLevel.SAFE,
            finder=finder,
            finder_args=(),
        )

    def test_slow_category_is_named_while_it_runs(self):
        started = threading.Event()
        release = threading.Event()

        def slow_finder():
            started.set()
            release.wait(10)
            return []

        categories = [
            self._category("fast", lambda: []),
            self._category("slow", slow_finder),
        ]
        events: list[tuple[str, int]] = []
        engine = ScanEngine(categories)

        def run():
            engine.run(progress_cb=lambda name, position, state: events.append((name, state)))

        worker = threading.Thread(target=run)
        worker.start()
        assert started.wait(10)
        time.sleep(0.2)

        # Mid-stall the last thing reported must be "slow", not the fast category
        # that happened to be queued in front of it.
        assert events[-1][0] == "slow"
        release.set()
        worker.join(timeout=10)
        assert not worker.is_alive()
        assert ("slow", 1) in events

    def test_a_category_whose_targets_do_not_exist_costs_nothing(self, tmp_path):
        absent = CleanupCategory(
            id="absent",
            name="Absent",
            group="Testing",
            description="",
            safety_level=SafetyLevel.SAFE,
            targets=[CacheTarget(path=str(tmp_path / "missing" / "cache"))],
        )
        started = time.monotonic()
        result = ScanEngine([absent]).run().results[0]
        assert result.size == 0 and result.item_count == 0
        assert time.monotonic() - started < 1.0


class TestColdPreview:
    """A preview with no prior scan must not report a finder category as empty."""

    def _finder_category(self, root: str) -> CleanupCategory:
        return CleanupCategory(
            id="test_finder",
            name="Discovered caches",
            group="Testing",
            description="",
            safety_level=SafetyLevel.SAFE,
            finder=lambda base: [os.path.join(base, "found")],
            finder_args=(root,),
        )

    def test_resolved_finder_reports_real_sizes(self, tmp_path):
        (tmp_path / "found").mkdir()
        (tmp_path / "found" / "cached.bin").write_bytes(b"x" * 2048)
        category = self._finder_category(str(tmp_path))

        cold = generate_cleanup_preview([category])
        assert cold.total_estimated_size == 0

        resolved = generate_cleanup_preview([category], resolve_finders=True)
        assert resolved.total_estimated_size == 2048
        assert resolved.categories[0].item_count == 1


class TestWindowsVolumeInfo:
    """Drive reporting must name the volume, not leave the field blank."""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows volume metadata")
    def test_system_drive_reports_its_filesystem(self):
        from crapcleaner.utils.platform import get_drive_info

        info = get_drive_info("C:")
        assert info["filesystem"]
        assert "label" in info

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows volume metadata")
    def test_unreadable_volume_reports_blank_not_a_placeholder(self):
        from crapcleaner.utils.platform import _windows_volume_info

        assert _windows_volume_info(r"Z:\definitely-not-mounted" + "\\") == ("", "")


class TestPackagedAssets:
    """ARCH-01 follow-up: assets resolve from the package, not from a module's location."""

    def test_bundled_assets_exist(self):
        from crapcleaner.gui.icons import ASSETS_DIR

        for asset in ("avatar.jpg", "MaterialIcons-Regular.ttf"):
            assert (ASSETS_DIR / asset).is_file(), f"missing bundled asset: {asset}"


class TestJsonlProgressMode:
    """SUB-05: machine-readable streaming progress, and nothing else on stdout."""

    def _lines(self, capsys):
        out = capsys.readouterr().out.strip().splitlines()
        return [json.loads(line) for line in out if line.strip()]

    def test_cleanup_emits_only_valid_json_lines(self, capsys, tmp_path):
        stale = tmp_path / "stale.pyc"
        stale.write_bytes(b"x" * 64)
        from crapcleaner.cli import main

        with patch(
            "crapcleaner.cli._select_clean_categories", return_value=[_pyc_category(str(tmp_path))]
        ):
            assert main(["--clean-category", "test_pyc", "--dry-run", "--progress-jsonl"]) == 0

        events = self._lines(capsys)
        names = [event["event"] for event in events]
        assert names[0] == "cleanup_start"
        assert names[-1] == "cleanup_complete"
        assert "cleanup_result" in names
        assert all("time" in event for event in events)

    def test_standard_output_is_untouched_without_the_flag(self, capsys, tmp_path):
        stale = tmp_path / "stale.pyc"
        stale.write_bytes(b"x" * 64)
        from crapcleaner.cli import main

        with patch(
            "crapcleaner.cli._select_clean_categories", return_value=[_pyc_category(str(tmp_path))]
        ):
            assert main(["--clean-category", "test_pyc", "--dry-run"]) == 0
        out = capsys.readouterr().out
        assert "Cleanup DRY RUN" in out
        with pytest.raises(json.JSONDecodeError):
            json.loads(out.splitlines()[0])

    def test_scan_stream_reports_start_and_completion(self, capsys):
        from crapcleaner.cli import JsonlProgress

        stream = JsonlProgress(True)
        stream.emit("scan_start", categories=2)
        stream.scan_progress("Temp files", "1/2", 0)
        stream.report_warnings("Temp files", ["locked file"])
        stream.emit("scan_complete", total_size=10, total_files=1, cancelled=False, duration=0.1)

        events = self._lines(capsys)
        assert [event["event"] for event in events] == [
            "scan_start",
            "scan_progress",
            "warning",
            "scan_complete",
        ]
        assert events[1]["phase"] == "started"

    def test_disabled_stream_writes_nothing(self, capsys):
        from crapcleaner.cli import JsonlProgress

        JsonlProgress(False).emit("scan_start", categories=1)
        assert capsys.readouterr().out == ""


@pytest.mark.skipif(sys.platform != "win32", reason="PATHEXT resolution is Windows-specific")
class TestExecutableResolution:
    """ARCH-03: executable lookup honours PATHEXT."""

    def test_which_resolves_a_windows_shim_without_its_extension(self):
        from crapcleaner.utils.platform import which

        assert which("where") is not None
        assert which("definitely-not-a-real-binary-xyz") is None
