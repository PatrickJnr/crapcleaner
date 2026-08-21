"""Background QThread workers so scans and cleanups never freeze the GUI."""

import threading

from PySide6.QtCore import QThread, Signal

from crapcleaner.core.cleaner import clean_categories, remove_selected_paths
from crapcleaner.core.scanner import ScanEngine

_MAX_GUI_LARGE_FILES = 5000
_MAX_GUI_DUPLICATE_GROUPS = 1000


def is_worker_running(worker: QThread | None) -> bool:
    """Whether a worker is alive and running, tolerating a deleted Qt object."""
    if worker is None:
        return False
    try:
        from shiboken6 import isValid

        if not isValid(worker):
            return False
    except (ImportError, TypeError):
        pass
    try:
        return bool(worker.isRunning())
    except (RuntimeError, AttributeError):
        return False


def stop_worker(worker: QThread | None, wait_ms: int = 150) -> None:
    """Ask a worker to stop, then wait briefly, tolerating one already gone.

    None of these workers runs an event loop, so quit() never reached them and the
    wait was the entire cost. A stopped worker discards its result, so the wait only
    has to cover a body that is about to return anyway.
    """
    if is_worker_running(worker) and worker is not None:
        try:
            request_stop = getattr(worker, "request_stop", None)
            if request_stop is not None:
                request_stop()
            else:
                worker.quit()
            worker.wait(wait_ms)
        except (RuntimeError, AttributeError):
            pass


class _Worker(QThread):
    """Base for every worker here: cooperatively stoppable, and silent once stopped."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop = threading.Event()

    def request_stop(self) -> None:
        self._stop.set()

    @property
    def stop_requested(self) -> bool:
        return self._stop.is_set()

    def _emit(self, signal, *args) -> None:
        """Drop a result the caller stopped caring about instead of delivering it late."""
        if not self._stop.is_set():
            signal.emit(*args)


class ScanWorker(_Worker):
    progress = Signal(str, str, int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, engine: ScanEngine, max_files: int = 200000, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._max_files = max_files

    def request_stop(self) -> None:
        super().request_stop()
        self._engine.request_stop()

    def run(self):
        try:

            def cb(name, stage, state):
                self.progress.emit(name, stage, state)

            report = self._engine.run(progress_cb=cb, max_files=self._max_files)
            self.done.emit(report)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class CleanWorker(_Worker):
    progress = Signal(str, int, int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        categories,
        dry_run: bool,
        use_recycle_bin: bool = False,
        parent=None,
        excluded_paths=None,
    ):
        super().__init__(parent)
        self._categories = categories
        self._dry_run = dry_run
        self._use_recycle_bin = use_recycle_bin
        self._excluded_paths = set(excluded_paths or ())

    def run(self):
        try:

            def cb(name, index, total):
                self.progress.emit(name, index, total)

            report = clean_categories(
                self._categories,
                dry_run=self._dry_run,
                use_recycle_bin=self._use_recycle_bin,
                stop_event=self._stop,
                progress_cb=cb,
                excluded_paths=self._excluded_paths,
            )
            self.done.emit(report)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class DeleteWorker(_Worker):
    """Removes hand-picked paths off the GUI thread, reporting each one as it goes."""

    progress = Signal(int, int, str)  # completed count, total, path just handled
    done = Signal(list)  # list[PathRemoval], one per path attempted
    failed = Signal(str)

    def __init__(self, paths: list[str], use_recycle_bin: bool, parent=None):
        super().__init__(parent)
        self._paths = [p for p in paths if p]
        self._use_recycle_bin = use_recycle_bin

    def run(self):
        total = len(self._paths)
        outcomes = []
        try:
            for index, path in enumerate(self._paths, 1):
                if self._stop.is_set():
                    break
                outcomes.extend(
                    remove_selected_paths([path], use_recycle_bin=self._use_recycle_bin)
                )
                self.progress.emit(index, total, path)
            # Emitted even when stopped: a partial list still records real deletions.
            self.done.emit(outcomes)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class LargeFilesWorker(_Worker):
    progress = Signal(int)
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, root, threshold, parent=None):
        super().__init__(parent)
        self._root = root
        self._threshold = threshold

    def run(self):
        from crapcleaner.analysis.large_files import scan_large_files

        try:
            files = scan_large_files(
                self._root,
                self._threshold,
                stop_event=self._stop,
                progress_cb=lambda n: self.progress.emit(n),
                max_results=_MAX_GUI_LARGE_FILES,
            )
            self._emit(self.done, files)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class DuplicatesWorker(_Worker):
    progress = Signal(int, int)
    done = Signal()
    failed = Signal(str)

    def __init__(self, folders, min_size, parent=None):
        super().__init__(parent)
        self._folders = folders
        self._min_size = min_size
        self.result_groups = []

    def run(self):
        from crapcleaner.analysis.duplicates import find_duplicates

        try:
            self.result_groups = find_duplicates(
                self._folders,
                self._min_size,
                stop_event=self._stop,
                progress_cb=lambda a, b: self.progress.emit(a, b),
                max_groups=_MAX_GUI_DUPLICATE_GROUPS,
            )
            self._emit(self.done)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class AiDataWorker(_Worker):
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, min_size, parent=None):
        super().__init__(parent)
        self._min_size = min_size

    def run(self):
        from crapcleaner.categories.ai import get_ai_data

        try:
            self._emit(self.done, get_ai_data(min_size=self._min_size))
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class DockerWorker(_Worker):
    done = Signal(object, list)
    failed = Signal(str)

    def run(self):
        from crapcleaner.categories.docker import docker_system_df, wsl_disk_report

        try:
            self._emit(self.done, docker_system_df(), wsl_disk_report())
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class DockerPruneWorker(_Worker):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, action_name: str, parent=None):
        super().__init__(parent)
        self._action_name = action_name

    def run(self):
        from crapcleaner.core.actions import run_action

        try:
            self._emit(self.done, run_action(self._action_name, dry_run=False))
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class SpecsWorker(_Worker):
    """Fetches system hardware specs + storage health off the main thread."""

    done = Signal(object, list)  # (HardwareSpecs, list[DiskHealthInfo])
    failed = Signal(str)

    def run(self):
        try:
            from crapcleaner.system.hardware import get_system_specs
            from crapcleaner.system.storage_health import get_storage_health_report

            specs = get_system_specs()
            try:
                health = get_storage_health_report()
            except Exception:
                health = []
            self._emit(self.done, specs, health)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class HealthWorker(_Worker):
    """Fetches storage health diagnostics off the main thread."""

    done = Signal(list)  # list[DiskHealthInfo]
    failed = Signal(str)

    def __init__(self, force_refresh: bool = False, parent=None):
        super().__init__(parent)
        self._force_refresh = force_refresh

    def run(self):
        try:
            from crapcleaner.system.storage_health import get_storage_health_report

            self._emit(self.done, get_storage_health_report(force_refresh=self._force_refresh))
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class StorageAnalysisWorker(_Worker):
    """Runs the 4 storage analysis passes off the main thread.

    Signals fire as each section completes so the UI can update progressively.
    """

    tree_done = Signal(object)  # StorageNode root
    tree_partial = Signal(object)  # StorageNode root, as measured so far
    index_done = Signal(object)  # StorageIndex: every directory this scan measured
    changes_done = Signal(object)  # SnapshotComparison | None, against the last scan
    types_done = Signal(list)  # list[FileTypeSummary]
    old_done = Signal(list)  # list[OldFileInfo]
    vms_done = Signal(list)  # list[VmStorageInfo]
    progress = Signal(str, int, str)  # stage, files seen, current directory
    finished_all = Signal()
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, path: str, depth: int = 3, parent=None, size_mode: str = "logical"):
        super().__init__(parent)
        self._path = path
        self._depth = depth
        self._size_mode = size_mode

    def _emit_progress(self, stage: str):
        # Throttled by the analyzers themselves, which report every 1000-1500 files.
        return lambda seen, where: self.progress.emit(stage, seen, where)

    def run(self):
        try:
            from crapcleaner.analysis.file_types import FileTypeCollector
            from crapcleaner.analysis.old_files import OldFileCollector
            from crapcleaner.analysis.storage import StorageIndex, analyze_storage_hierarchy
            from crapcleaner.analysis.virtual_machines import detect_virtual_machine_storage

            # One traversal, three consumers: separate passes paid the metadata cost
            # three times and ran strictly in sequence.
            file_types = FileTypeCollector()
            old_files = OldFileCollector(min_age_days=90, max_results=200)

            def observe(entry, st) -> None:
                file_types.observe(entry.name, st.st_size)
                old_files.observe(entry.path, entry.name, st)

            index = StorageIndex()
            root_node = analyze_storage_hierarchy(
                self._path,
                max_depth=self._depth,
                stop_event=self._stop,
                progress_cb=self._emit_progress("Measuring directories"),
                partial_cb=self.tree_partial.emit,
                file_observer=observe,
                index_out=index,
                size_mode=self._size_mode,
            )
            if self._stop.is_set():
                self.cancelled.emit()
                return
            self.tree_done.emit(root_node)
            self.index_done.emit(index)

            # Compare before overwriting, so the view can answer "what grew".
            from crapcleaner.analysis.snapshots import compare, save_snapshot, sizes_from_index

            sizes = sizes_from_index(index)
            try:
                self.changes_done.emit(compare(self._path, sizes, size_mode=self._size_mode))
                save_snapshot(self._path, sizes, size_mode=self._size_mode)
            except Exception:  # pragma: no cover - a snapshot must never fail a scan
                self.changes_done.emit(None)

            self.types_done.emit(file_types.summaries())
            self.old_done.emit(old_files.results())

            vms = detect_virtual_machine_storage()
            if self._stop.is_set():
                self.cancelled.emit()
                return
            self.vms_done.emit(vms)

            self.finished_all.emit()
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class StorageExpandWorker(_Worker):
    """Measures one subtree on demand, so the first view does not pay for the whole disk."""

    done = Signal(str, object)  # requested path, StorageNode
    failed = Signal(str)

    def __init__(self, path: str, depth: int = 2, parent=None):
        super().__init__(parent)
        self._path = path
        self._depth = depth

    def run(self):
        try:
            from crapcleaner.analysis.storage import analyze_storage_hierarchy

            node = analyze_storage_hierarchy(
                self._path,
                max_depth=self._depth,
                stop_event=self._stop,
            )
            if not self._stop.is_set():
                self.done.emit(self._path, node)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class PreviewWorker(_Worker):
    """Builds the pre-cleanup manifest off the GUI thread.

    Enumerating candidate files walks every target, which is exactly the work that
    must not happen on the UI thread while a modal dialog is opening.
    """

    done = Signal(object)  # CleanupPreview
    progress = Signal(str, int, int)  # category name, index, total
    failed = Signal(str)

    def __init__(self, categories, max_items: int = 500, parent=None):
        super().__init__(parent)
        self._categories = categories
        self._max_items = max_items

    def run(self):
        try:
            from crapcleaner.core.preview import generate_cleanup_preview

            preview = generate_cleanup_preview(
                self._categories,
                max_items_per_category=self._max_items,
                stop_event=self._stop,
                progress_cb=lambda name, index, total: self.progress.emit(name, index, total),
                resolve_finders=True,
            )
            self._emit(self.done, preview)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class ContributorsWorker(_Worker):
    """Fetches the contributor list and their avatars off the GUI thread.

    Done inline in the About page's constructor, this was a 3 s call plus a
    blocking download per contributor, freezing the window on a slow network.
    """

    #: list of (ContributorInfo, avatar file path or "")
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, force_refresh: bool = False, parent=None):
        super().__init__(parent)
        self._force_refresh = force_refresh

    def run(self):
        try:
            from concurrent.futures import ThreadPoolExecutor

            from crapcleaner.utils.contributors import fetch_avatar_file, fetch_contributors

            contributors = fetch_contributors(
                timeout_seconds=3.0, force_refresh=self._force_refresh
            )
            if not contributors:
                self._emit(self.done, [])
                return

            # Independent downloads; serialising them was most of the wait.
            with ThreadPoolExecutor(max_workers=min(6, len(contributors))) as pool:
                avatars = list(
                    pool.map(
                        lambda c: fetch_avatar_file(c.avatar_url, c.login, timeout_seconds=3.0),
                        contributors,
                    )
                )
            self._emit(self.done, [(c, avatar or "") for c, avatar in zip(contributors, avatars)])
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class UpdateCheckWorker(_Worker):
    """Asks GitHub for the latest release without blocking the window."""

    done = Signal(object)  # UpdateInfo | None
    failed = Signal(str)

    def run(self):
        try:
            from crapcleaner.utils.updater import check_for_updates

            self._emit(self.done, check_for_updates(timeout_seconds=5.0))
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class UpdateDownloadWorker(_Worker):
    """Downloads and verifies a release without blocking the window."""

    progress = Signal(int, int)  # bytes received, total (0 when unknown)
    done = Signal(object)  # DownloadedUpdate
    failed = Signal(str)

    def __init__(self, version: str, parent=None):
        super().__init__(parent)
        self._version = version

    def run(self):
        try:
            from crapcleaner.utils.self_update import download_update

            update = download_update(
                self._version, progress_cb=lambda got, total: self.progress.emit(got, total)
            )
            self._emit(self.done, update)
        except Exception as exc:
            self._emit(self.failed, str(exc))


class ScheduledScanWorker(_Worker):
    """Runs the unattended scan on demand, without blocking the window."""

    done = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            from crapcleaner.core.scheduler import run_scheduled_scan

            self._emit(self.done, run_scheduled_scan())
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class MemoryReportWorker(_Worker):
    """Reads RAM, swap, and VRAM statistics off the main thread."""

    done = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            from crapcleaner.system.memory_report import get_memory_report

            self._emit(self.done, get_memory_report())
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class MemoryActionWorker(_Worker):
    """Runs a single memory reclamation action off the main thread."""

    done = Signal(object)
    failed = Signal(str)

    def __init__(self, action_id: str, dry_run: bool = False, parent=None):
        super().__init__(parent)
        self._action_id = action_id
        self._dry_run = dry_run

    def run(self):
        try:
            from crapcleaner.system.memory_actions import run_action

            self._emit(self.done, run_action(self._action_id, dry_run=self._dry_run))
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class StartupWorker(_Worker):
    """Loads Windows startup applications off the main thread."""

    done = Signal(list)
    failed = Signal(str)

    def run(self):
        try:
            from crapcleaner.system.startup import get_startup_items

            self._emit(self.done, get_startup_items(force_refresh=True))
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class StartupActionWorker(_Worker):
    """Enables, disables, removes, or adds a startup entry off the main thread."""

    done = Signal(bool, str)
    failed = Signal(str)

    def __init__(
        self,
        action: str,
        item_id: str = "",
        enabled: bool = True,
        name: str = "",
        command: str = "",
        scope: str = "USER",
        parent=None,
    ):
        super().__init__(parent)
        self._action = action
        self._item_id = item_id
        self._enabled = enabled
        self._name = name
        self._command = command
        self._scope = scope

    def run(self):
        try:
            from crapcleaner.system.startup import (
                add_startup_item,
                remove_startup_item,
                set_startup_item_enabled,
            )

            if self._action == "toggle":
                ok, msg = set_startup_item_enabled(self._item_id, self._enabled)
            elif self._action == "remove":
                ok, msg = remove_startup_item(self._item_id)
            elif self._action == "add":
                ok, msg = add_startup_item(self._name, self._command, scope=self._scope)
            else:
                ok, msg = False, f"Unknown startup action: {self._action}"

            self._emit(self.done, ok, msg)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class SystemUpdateWorker(_Worker):
    """Checks for pending system updates and recent update history off the main thread."""

    done = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            from crapcleaner.system.system_updates import check_system_updates

            self._emit(self.done, check_system_updates(include_history=True))
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class SystemUpdateInstallWorker(_Worker):
    """Installs pending system updates off the main thread."""

    done = Signal(bool, str)
    failed = Signal(str)

    def run(self):
        try:
            from crapcleaner.system.system_updates import install_system_updates

            ok, msg = install_system_updates()
            self._emit(self.done, ok, msg)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


# Historic names, kept for existing imports.
WindowsUpdateWorker = SystemUpdateWorker
WindowsUpdateInstallWorker = SystemUpdateInstallWorker


class ServicesWorker(_Worker):
    """Retrieves every service or systemd unit and its runtime state off the main thread."""

    done = Signal(list)
    failed = Signal(str)

    def run(self):
        try:
            from crapcleaner.system.services import get_services_report

            self._emit(self.done, get_services_report(force_refresh=True))
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class ServiceActionWorker(_Worker):
    """Starts, stops, restarts, or reconfigures one service off the main thread."""

    done = Signal(bool, str)
    failed = Signal(str)

    def __init__(
        self,
        action: str,
        service_name: str,
        startup_type: str = "",
        force: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._action = action
        self._service_name = service_name
        self._startup_type = startup_type
        self._force = force

    def run(self):
        try:
            from crapcleaner.system.services import (
                restart_service,
                set_service_startup_type,
                start_service,
                stop_service,
            )

            if self._action == "start":
                ok, msg = start_service(self._service_name)
            elif self._action == "stop":
                ok, msg = stop_service(self._service_name, force=self._force)
            elif self._action == "restart":
                ok, msg = restart_service(self._service_name)
            elif self._action == "startup_type":
                ok, msg = set_service_startup_type(self._service_name, self._startup_type)
            else:
                ok, msg = False, f"Unknown service action: {self._action}"

            self._emit(self.done, ok, msg)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class PackageManagerWorker(_Worker):
    """Scans all detected package managers for available updates off the main thread."""

    done = Signal(list)  # list[ManagerResult]
    failed = Signal(str)

    def __init__(self, force_refresh: bool = False, parent=None):
        super().__init__(parent)
        self._force_refresh = force_refresh

    def run(self):
        try:
            from crapcleaner.system.package_managers import get_all_updates

            self._emit(self.done, get_all_updates(force_refresh=self._force_refresh))
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class PackageUpdateWorker(_Worker):
    """Installs one package (or all packages for a manager) off the main thread."""

    done = Signal(bool, str)
    failed = Signal(str)

    def __init__(self, manager: str, pkg_id: str = "", update_all: bool = False, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._pkg_id = pkg_id
        self._update_all = update_all

    def run(self):
        try:
            from crapcleaner.system.package_managers import install_all_updates, install_update

            if self._update_all:
                ok, msg = install_all_updates(self._manager)
            else:
                ok, msg = install_update(self._manager, self._pkg_id)
            self._emit(self.done, ok, msg)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class DiagnosticsWorker(_Worker):
    """Writes the diagnostics bundle off the GUI thread.

    It reads the tail of the log and probes every drive, which is seconds of blocking
    work in a click handler.
    """

    done = Signal(str)  # path written
    failed = Signal(str)

    def __init__(self, destination: str, parent=None):
        super().__init__(parent)
        self._destination = destination

    def run(self):
        try:
            from crapcleaner.system.diagnostics import write_diagnostics_bundle

            self._emit(self.done, write_diagnostics_bundle(self._destination))
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class DrivesWorker(_Worker):
    """Loads the physical-disk inventory off the main thread."""

    done = Signal(list, str, str)  # (list[PhysicalDiskInfo], schedule_state, schedule_detail)
    failed = Signal(str)

    def __init__(self, force_refresh: bool = False, parent=None):
        super().__init__(parent)
        self._force_refresh = force_refresh

    def run(self):
        try:
            from crapcleaner.system.drive_actions import scheduled_optimization_status
            from crapcleaner.system.drives import get_drives_report

            drives = get_drives_report(force_refresh=self._force_refresh)
            try:
                state, detail = scheduled_optimization_status()
            except Exception:
                state, detail = "Unknown", ""
            self._emit(self.done, drives, state, detail)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class DriveAnalyzeWorker(_Worker):
    """Measures fragmentation on one volume off the main thread."""

    done = Signal(str, bool, str, object)  # (letter, ok, message, percent|None)
    failed = Signal(str)

    def __init__(self, letter: str, parent=None):
        super().__init__(parent)
        self._letter = letter

    def run(self):
        try:
            from crapcleaner.system.drive_actions import analyze_volume

            ok, message, percent = analyze_volume(self._letter)
            self._emit(self.done, self._letter, ok, message, percent)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class DriveOptimizeWorker(_Worker):
    """Runs Windows' volume optimisation, which can take hours on a large HDD."""

    done = Signal(str, bool, str)  # (letter, ok, message)
    failed = Signal(str)

    def __init__(self, letter: str, parent=None):
        super().__init__(parent)
        self._letter = letter

    def run(self):
        try:
            from crapcleaner.system.drive_actions import optimize_volume

            ok, message = optimize_volume(self._letter)
            self._emit(self.done, self._letter, ok, message)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class DriveBulkWorker(_Worker):
    """Runs one drive action across several volumes, one at a time.

    Sequential rather than parallel: these are disk-bound operations, and running them
    together would only make each one slower. Stopping is honoured between volumes,
    since Windows offers no way to abort an optimisation already under way.
    """

    progress = Signal(str, bool, str, object)  # (letter, ok, message, percent|None)
    started_volume = Signal(str, int, int)  # (letter, index, total)
    done = Signal(int, int)  # (succeeded, attempted)
    failed = Signal(str)

    def __init__(self, letters: list[str], action: str, parent=None):
        super().__init__(parent)
        self._letters = list(letters)
        self._action = action

    def run(self):
        try:
            from crapcleaner.system.drive_actions import analyze_volume, optimize_volume

            succeeded = 0
            attempted = 0
            total = len(self._letters)

            for index, letter in enumerate(self._letters, start=1):
                if self.stop_requested:
                    break
                self._emit(self.started_volume, letter, index, total)

                if self._action == "analyze":
                    ok, message, percent = analyze_volume(letter)
                else:
                    ok, message = optimize_volume(letter)
                    percent = None

                attempted += 1
                succeeded += 1 if ok else 0
                self._emit(self.progress, letter, ok, message, percent)

            self._emit(self.done, succeeded, attempted)
        except Exception as exc:  # pragma: no cover - defensive
            self._emit(self.failed, str(exc))


class NavCountsWorker(_Worker):
    """Counts for the sidebar badges, gathered off the GUI thread at launch.

    Only probes that are cheap or already cached belong here. An update check is
    neither, so the update badges are filled in by their own views instead.
    """

    done = Signal(dict)

    def run(self):
        counts: dict[str, str] = {}
        try:
            from crapcleaner.system.startup import get_startup_items

            enabled = sum(1 for item in get_startup_items() if item.enabled)
            if enabled:
                counts["startup"] = str(enabled)
        except Exception:
            pass

        if self.stop_requested:
            return

        try:
            from crapcleaner.system.drives import get_drives_report

            disks = [d for d in get_drives_report() if not d.is_unmapped]
            if disks:
                counts["drives"] = str(len(disks))
        except Exception:
            pass

        if self.stop_requested:
            return

        try:
            from crapcleaner.system.services import get_services_report

            running = sum(1 for svc in get_services_report() if svc.status == "Running")
            if running:
                counts["services"] = str(running)
        except Exception:
            pass

        self._emit(self.done, counts)
