"""Background QThread workers so scans and cleanups never freeze the GUI."""

import threading

from PySide6.QtCore import QThread, Signal

from crapcleaner.core.cleaner import clean_categories
from crapcleaner.core.scanner import ScanEngine

_MAX_GUI_LARGE_FILES = 5000
_MAX_GUI_DUPLICATE_GROUPS = 1000


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
    finished_all = Signal()
    failed = Signal(str)

    def __init__(self, path: str, depth: int = 3, parent=None):
        super().__init__(parent)
        self._path = path
        self._depth = depth

    def run(self):
        try:
            from crapcleaner.analysis.file_types import analyze_file_types
            from crapcleaner.analysis.old_files import find_old_files
            from crapcleaner.analysis.storage import analyze_storage_hierarchy
            from crapcleaner.analysis.virtual_machines import detect_virtual_machine_storage

            root_node = analyze_storage_hierarchy(self._path, max_depth=self._depth)
            self.tree_done.emit(root_node)

            file_types = analyze_file_types(self._path)
            self.types_done.emit(file_types)

            old_files = find_old_files(self._path, min_age_days=90, max_results=200)
            self.old_done.emit(old_files)

            vms = detect_virtual_machine_storage()
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
