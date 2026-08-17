"""Background QThread workers so scans and cleanups never freeze the GUI."""

import threading

from PySide6.QtCore import QThread, Signal

from crapcleaner.core.cleaner import clean_categories
from crapcleaner.core.scanner import ScanEngine

_MAX_GUI_LARGE_FILES = 5000
_MAX_GUI_DUPLICATE_GROUPS = 1000


def is_worker_running(worker: QThread | None) -> bool:
    """Safely check if a Qt QThread/worker is alive and running without raising Shiboken RuntimeError."""
    if worker is None:
        return False
    try:
        from shiboken6 import isValid

        if not isValid(worker):
            return False
    except ImportError:
        pass
    try:
        return bool(worker.isRunning())
    except (RuntimeError, AttributeError):
        return False


def stop_worker(worker: QThread | None, wait_ms: int = 2000) -> None:
    """Safely quit and wait for a worker thread if it is still valid and running."""
    if is_worker_running(worker) and worker is not None:
        try:
            worker.quit()
            worker.wait(wait_ms)
        except (RuntimeError, AttributeError):
            pass


class ScanWorker(QThread):
    progress = Signal(str, str, int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, engine: ScanEngine, max_files: int = 200000, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._max_files = max_files
        self._stop = threading.Event()

    def request_stop(self):
        self._engine.request_stop()

    def run(self):
        try:

            def cb(name, stage, state):
                self.progress.emit(name, stage, state)

            report = self._engine.run(progress_cb=cb, max_files=self._max_files)
            self.done.emit(report)
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class CleanWorker(QThread):
    progress = Signal(str, int, int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, categories, dry_run: bool, use_recycle_bin: bool = False, parent=None):
        super().__init__(parent)
        self._categories = categories
        self._dry_run = dry_run
        self._use_recycle_bin = use_recycle_bin
        self._stop = threading.Event()

    def request_stop(self):
        self._stop.set()

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
            )
            self.done.emit(report)
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class LargeFilesWorker(QThread):
    progress = Signal(int)
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, root, threshold, parent=None):
        super().__init__(parent)
        self._root = root
        self._threshold = threshold
        self._stop = threading.Event()

    def request_stop(self):
        self._stop.set()

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
            self.done.emit(files)
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class DuplicatesWorker(QThread):
    progress = Signal(int, int)
    done = Signal()
    failed = Signal(str)

    def __init__(self, folders, min_size, parent=None):
        super().__init__(parent)
        self._folders = folders
        self._min_size = min_size
        self._stop = threading.Event()
        self.result_groups = []

    def request_stop(self):
        self._stop.set()

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
            self.done.emit()
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class AiDataWorker(QThread):
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, min_size, parent=None):
        super().__init__(parent)
        self._min_size = min_size
        self._stop = threading.Event()

    def request_stop(self):
        self._stop.set()

    def run(self):
        from crapcleaner.categories.ai import get_ai_data

        try:
            self.done.emit(get_ai_data(min_size=self._min_size))
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class DockerWorker(QThread):
    done = Signal(object, list)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        from crapcleaner.categories.docker import docker_system_df, wsl_disk_report

        try:
            self.done.emit(docker_system_df(), wsl_disk_report())
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class DockerInfoWorker(QThread):
    done = Signal(object, list)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        from crapcleaner.categories.docker import docker_system_df, wsl_disk_report

        try:
            self.done.emit(docker_system_df(), wsl_disk_report())
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class DockerPruneWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, action_name: str, parent=None):
        super().__init__(parent)
        self._action_name = action_name

    def run(self):
        from crapcleaner.core.actions import run_action

        try:
            self.done.emit(run_action(self._action_name, dry_run=False))
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


# ---------------------------------------------------------------------------
# Non-blocking workers for slow system-info queries
# ---------------------------------------------------------------------------


class SpecsWorker(QThread):
    """Fetches system hardware specs + storage health off the main thread."""

    done = Signal(object, list)  # (HardwareSpecs, list[DiskHealthInfo])
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            from crapcleaner.system.hardware import get_system_specs
            from crapcleaner.system.storage_health import get_storage_health_report

            specs = get_system_specs()
            try:
                health = get_storage_health_report()
            except Exception:
                health = []
            self.done.emit(specs, health)
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class HealthWorker(QThread):
    """Fetches storage health diagnostics off the main thread."""

    done = Signal(list)  # list[DiskHealthInfo]
    failed = Signal(str)

    def __init__(self, force_refresh: bool = False, parent=None):
        super().__init__(parent)
        self._force_refresh = force_refresh

    def run(self):
        try:
            from crapcleaner.system.storage_health import get_storage_health_report

            self.done.emit(get_storage_health_report(force_refresh=self._force_refresh))
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class StorageAnalysisWorker(QThread):
    """Runs the 4 storage analysis passes off the main thread.

    Signals fire as each section completes so the UI can update progressively.
    """

    tree_done = Signal(object)  # StorageNode root
    types_done = Signal(list)  # list[FileTypeSummary]
    old_done = Signal(list)  # list[OldFileInfo]
    vms_done = Signal(list)  # list[VmStorageInfo]
    progress = Signal(str, int, str)  # stage, files seen, current directory
    finished_all = Signal()
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, path: str, depth: int = 3, parent=None):
        super().__init__(parent)
        self._path = path
        self._depth = depth
        self._stop_event = threading.Event()

    def request_stop(self) -> None:
        """Ask the analysis to stop. Each pass checks this between entries."""
        self._stop_event.set()

    @property
    def stop_requested(self) -> bool:
        return self._stop_event.is_set()

    def _emit_progress(self, stage: str):
        # Throttled by the analyzers themselves, which report every 1000-1500 files.
        return lambda seen, where: self.progress.emit(stage, seen, where)

    def run(self):
        try:
            from crapcleaner.analysis.file_types import analyze_file_types
            from crapcleaner.analysis.old_files import find_old_files
            from crapcleaner.analysis.storage import analyze_storage_hierarchy
            from crapcleaner.analysis.virtual_machines import detect_virtual_machine_storage

            root_node = analyze_storage_hierarchy(
                self._path,
                max_depth=self._depth,
                stop_event=self._stop_event,
                progress_cb=self._emit_progress("Measuring directories"),
            )
            if self._stop_event.is_set():
                self.cancelled.emit()
                return
            self.tree_done.emit(root_node)

            file_types = analyze_file_types(
                self._path,
                stop_event=self._stop_event,
                progress_cb=self._emit_progress("Classifying file types"),
            )
            if self._stop_event.is_set():
                self.cancelled.emit()
                return
            self.types_done.emit(file_types)

            old_files = find_old_files(
                self._path,
                min_age_days=90,
                max_results=200,
                stop_event=self._stop_event,
            )
            if self._stop_event.is_set():
                self.cancelled.emit()
                return
            self.old_done.emit(old_files)

            vms = detect_virtual_machine_storage()
            if self._stop_event.is_set():
                self.cancelled.emit()
                return
            self.vms_done.emit(vms)

            self.finished_all.emit()
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class MemoryReportWorker(QThread):
    """Reads RAM, swap, and VRAM statistics off the main thread."""

    done = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            from crapcleaner.system.memory_report import get_memory_report

            self.done.emit(get_memory_report())
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class MemoryActionWorker(QThread):
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

            self.done.emit(run_action(self._action_id, dry_run=self._dry_run))
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class StartupWorker(QThread):
    """Loads Windows startup applications off the main thread."""

    done = Signal(list)
    failed = Signal(str)

    def run(self):
        try:
            from crapcleaner.system.startup import get_startup_items

            self.done.emit(get_startup_items(force_refresh=True))
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class StartupActionWorker(QThread):
    """Executes a startup modification action (toggle enable/disable, remove, add) asynchronously."""

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

            self.done.emit(ok, msg)
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class SystemUpdateWorker(QThread):
    """Checks for pending system updates and recent update history off the main thread."""

    done = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            from crapcleaner.system.system_updates import check_system_updates

            self.done.emit(check_system_updates(include_history=True))
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class SystemUpdateInstallWorker(QThread):
    """Installs pending system updates off the main thread."""

    done = Signal(bool, str)
    failed = Signal(str)

    def run(self):
        try:
            from crapcleaner.system.system_updates import install_system_updates

            ok, msg = install_system_updates()
            self.done.emit(ok, msg)
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


# Historic names, kept for existing imports.
WindowsUpdateWorker = SystemUpdateWorker
WindowsUpdateInstallWorker = SystemUpdateInstallWorker


class ServicesWorker(QThread):
    """Retrieves every service or systemd unit and its runtime state off the main thread."""

    done = Signal(list)
    failed = Signal(str)

    def run(self):
        try:
            from crapcleaner.system.services import get_services_report

            self.done.emit(get_services_report(force_refresh=True))
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class ServiceActionWorker(QThread):
    """Executes start, stop, restart, or startup type configuration for a service asynchronously."""

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

            self.done.emit(ok, msg)
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class PackageManagerWorker(QThread):
    """Scans all detected package managers for available updates off the main thread."""

    done = Signal(list)  # list[ManagerResult]
    failed = Signal(str)

    def __init__(self, force_refresh: bool = False, parent=None):
        super().__init__(parent)
        self._force_refresh = force_refresh

    def run(self):
        try:
            from crapcleaner.system.package_managers import get_all_updates

            self.done.emit(get_all_updates(force_refresh=self._force_refresh))
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class PackageUpdateWorker(QThread):
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
            self.done.emit(ok, msg)
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))

