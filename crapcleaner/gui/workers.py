"""Background QThread workers so scans and cleanups never freeze the GUI."""

import threading

from PySide6.QtCore import QThread, Signal

from crapcleaner.cleaners.cleaner import clean_categories
from crapcleaner.scanner.scanner import ScanEngine


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
        from crapcleaner.large_files.scanner import scan_large_files

        try:
            files = scan_large_files(
                self._root,
                self._threshold,
                stop_event=self._stop,
                progress_cb=lambda n: self.progress.emit(n),
            )
            self.done.emit(files)
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))


class DuplicatesWorker(QThread):
    progress = Signal(int, int)
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, folders, min_size, parent=None):
        super().__init__(parent)
        self._folders = folders
        self._min_size = min_size
        self._stop = threading.Event()

    def request_stop(self):
        self._stop.set()

    def run(self):
        from crapcleaner.duplicates.finder import find_duplicates

        try:
            groups = find_duplicates(
                self._folders,
                self._min_size,
                stop_event=self._stop,
                progress_cb=lambda a, b: self.progress.emit(a, b),
            )
            self.done.emit(groups)
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
        from crapcleaner.ai.cleanup import get_ai_data

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
        from crapcleaner.docker.cleanup import docker_system_df, wsl_disk_report

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
        from crapcleaner.docker.cleanup import docker_system_df, wsl_disk_report

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
        from crapcleaner.cleaners.actions import run_action

        try:
            self.done.emit(run_action(self._action_name, dry_run=False))
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))
