"""CrapCleaner main window and GUI entry point."""

import os
import sys

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from crapcleaner import __version__
from crapcleaner.config.settings import load_settings, update_settings
from crapcleaner.gui.dialogs import ConfirmCleanupDialog, ReportDialog
from crapcleaner.gui.sidebar import Sidebar
from crapcleaner.gui.theme import apply_theme, make_window_icon
from crapcleaner.gui.views import (
    AboutView,
    AiDataView,
    CleanupView,
    DashboardView,
    DockerView,
    DuplicatesView,
    HelpSafetyView,
    HistoryView,
    LargeFilesView,
    MemoryView,
    SettingsView,
    SpecsView,
    StorageBreakdownView,
)
from crapcleaner.gui.workers import (
    AiDataWorker,
    CleanWorker,
    DockerPruneWorker,
    DockerWorker,
    DuplicatesWorker,
    HealthWorker,
    LargeFilesWorker,
    ScanWorker,
    SpecsWorker,
    StorageAnalysisWorker,
)
from crapcleaner.history.store import append as history_append
from crapcleaner.models.history import HistoryEntry
from crapcleaner.registry import get_all_categories
from crapcleaner.scanner.cache import ScanCache
from crapcleaner.utils.format import format_datetime, format_size


class MainWindow(QMainWindow):
    _PAGE_KEYS = [
        "dashboard",
        "cleanup",
        "storage",
        "large",
        "duplicates",
        "ai",
        "docker",
        "specs",
        "memory",
        "history",
        "settings",
        "help",
        "about",
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"CrapCleaner [CCleaner] v{__version__}")
        self.setWindowIcon(make_window_icon())
        self.resize(1200, 780)
        self.setMinimumSize(1000, 660)
        self._settings = load_settings()
        disabled = set(self._settings.get("disabled_categories", []))
        self._categories = [c for c in get_all_categories() if c.id not in disabled]
        self._workers = []
        self._scan_cache = None
        self._restore_geometry()
        self._last_highlighted: str = ""

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = Sidebar(__version__)
        self.sidebar.navigation_requested.connect(self.navigate)
        root_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.dashboard = DashboardView(self)
        self.cleanup_view = CleanupView(self)
        self.storage_view = StorageBreakdownView(self)
        self.large_files_view = LargeFilesView(self)
        self.duplicates_view = DuplicatesView(self)
        self.ai_view = AiDataView(self)
        self.docker_view = DockerView(self)
        self.specs_view = SpecsView(self)
        self.memory_view = MemoryView(self)
        self.history_view = HistoryView(self)
        self.settings_view = SettingsView(self)
        self.help_view = HelpSafetyView(self)
        self.about_view = AboutView(self)
        for page in (
            self.dashboard,
            self.cleanup_view,
            self.storage_view,
            self.large_files_view,
            self.duplicates_view,
            self.ai_view,
            self.docker_view,
            self.specs_view,
            self.memory_view,
            self.history_view,
            self.settings_view,
            self.help_view,
            self.about_view,
        ):
            self.stack.addWidget(page)
        root_layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        self._setup_shortcuts()
        self.dashboard.refresh()
        self.cleanup_view.populate(self._categories)
        self.history_view.refresh()
        theme = self._settings.get("theme", "dark")
        self._apply_theme_to_views(theme)
        self.sidebar.set_active("dashboard")
        self.statusBar().showMessage("Ready", 3000)

    def _setup_shortcuts(self):
        # Ctrl+1..9,0 for tab switching
        for i, key in enumerate(self._PAGE_KEYS):
            key_num = (i + 1) % 10
            sc = QShortcut(QKeySequence(f"Ctrl+{key_num}"), self)
            sc.activated.connect(lambda k=key: self.navigate(k))

        # Ctrl+R to start scan
        scan_sc = QShortcut(QKeySequence("Ctrl+R"), self)
        scan_sc.activated.connect(self.start_scan)

        # F5 to refresh active view
        refresh_sc = QShortcut(QKeySequence("F5"), self)
        refresh_sc.activated.connect(self._refresh_active_view)

        # Escape to cancel scan
        esc_sc = QShortcut(QKeySequence("Escape"), self)
        esc_sc.activated.connect(self.cancel_active_scan)

    def _refresh_active_view(self):
        idx = self.stack.currentIndex()
        if 0 <= idx < len(self._PAGE_KEYS):
            key = self._PAGE_KEYS[idx]
            if key == "dashboard":
                self.dashboard.refresh()
            elif key == "history":
                self.history_view.refresh()
            elif key == "docker":
                self.refresh_docker()
            elif key == "specs":
                self.specs_view.refresh_specs()
            elif key == "storage":
                self.storage_view.refresh_health()
            elif key == "memory":
                self.memory_view.refresh()

    def navigate(self, key: str):
        if key not in self._PAGE_KEYS:
            return
        self.stack.setCurrentIndex(self._PAGE_KEYS.index(key))
        self.sidebar.set_active(key)
        if key == "dashboard":
            self.dashboard.refresh()
        elif key == "history":
            self.history_view.refresh()
        elif key == "specs":
            if self.specs_view._specs is None:
                self.specs_view.refresh_specs()
        elif key == "storage":
            self.storage_view.refresh_health()
        elif key == "memory":
            self.memory_view.refresh()

    def review_and_clean(self):
        self.navigate("cleanup")
        self.cleanup_view.review_recommended()

    def _apply_theme_to_views(self, theme: str):
        self.sidebar.apply_theme(theme)
        for view in (
            self.dashboard,
            self.cleanup_view,
            self.storage_view,
            self.large_files_view,
            self.duplicates_view,
            self.ai_view,
            self.docker_view,
            self.specs_view,
            self.memory_view,
            self.history_view,
            self.settings_view,
            self.help_view,
            self.about_view,
        ):
            apply = getattr(view, "apply_theme", None)
            if apply is not None:
                apply(theme)

    def _restore_geometry(self):
        hex_ = self._settings.get("window_geometry", "")
        if not hex_:
            return
        from PySide6.QtCore import QByteArray

        try:
            self.restoreGeometry(QByteArray.fromHex(hex_.encode("ascii")))
        except Exception:
            pass

    def switch_theme(self, theme: str):
        """Cross-fade the whole window into the given theme."""
        from crapcleaner.gui.theme import fade_theme_change

        def swap():
            app_inst = QApplication.instance()
            if isinstance(app_inst, QApplication):
                apply_theme(app_inst, theme)
            self._apply_theme_to_views(theme)

        duration = 0 if self._settings.get("reduce_motion", False) else 180
        fade_theme_change(self, swap, duration_ms=duration)

    def apply_settings(self):
        self._settings = load_settings()
        theme = self._settings.get("theme", "dark")
        self.switch_theme(theme)
        disabled = set(self._settings.get("disabled_categories", []))
        self._categories = [c for c in get_all_categories() if c.id not in disabled]
        self.cleanup_view.populate(self._categories)
        self.dashboard.refresh()
        self.history_view.refresh()

    def _register_worker(self, worker):
        self._workers.append(worker)
        worker.finished.connect(
            lambda: self._workers.remove(worker) if worker in self._workers else None
        )

    def cancel_active_scan(self):
        for worker in list(self._workers):
            if hasattr(worker, "request_stop"):
                worker.request_stop()
        self.dashboard.set_scanning(False)
        self.cleanup_view.set_scanning(False)
        self.statusBar().showMessage("Scan cancelled by user.", 4000)

    def start_scan(self):
        from crapcleaner.scanner.scanner import ScanEngine

        ttl = float(self._settings.get("scan_cache_ttl", 300))
        self._scan_cache = ScanCache(ttl=ttl)
        engine = ScanEngine(self._categories, cache=self._scan_cache)
        worker = ScanWorker(engine, max_files=self._settings.get("max_scan_files", 200000))
        worker.progress.connect(self._on_scan_progress)
        worker.done.connect(self._on_scan_done)
        worker.failed.connect(lambda msg: self._on_scan_failed(msg))
        self._register_worker(worker)
        self.dashboard.set_scanning(True)
        self.cleanup_view.set_scanning(True)
        self.statusBar().showMessage("Scanning junk categories...", 4000)
        worker.start()

    def _scan_pct(self, stage, state) -> int:
        try:
            cur, total = stage.split("/")
            done = int(cur) if state else int(cur) - 1
            total = int(total)
        except (AttributeError, ValueError):
            return -1
        if total <= 0:
            return -1
        return int(max(0, min(100, done / total * 100)))

    def _on_scan_progress(self, name, stage, state):
        self.cleanup_view.status_label.setText(f"Scanning: {name} ({stage})")
        # Only repaint the tree highlight when the category actually changes —
        # avoids a UI-thread backlog when 8 worker threads emit rapidly.
        if name != self._last_highlighted:
            self._last_highlighted = name
            self.cleanup_view.highlight_category(name)
        self.dashboard.set_scan_progress(name, self._scan_pct(stage, state))

    def _on_scan_done(self, report):
        self.dashboard.set_scanning(False)
        self.cleanup_view.set_scanning(False)
        self.cleanup_view.clear_status()
        self.cleanup_view.clear_highlight()
        self.dashboard.set_scan(report)
        self.cleanup_view.update_sizes()
        if self._scan_cache is not None:
            self._scan_cache.save()
        hits, _ = self._scan_cache.stats if self._scan_cache is not None else (0, 0)
        history_append(
            HistoryEntry(
                kind="scan",
                started=report.started,
                duration=report.duration,
                total_identified=report.total_size,
            )
        )
        self.history_view.refresh()

        if report.total_size > 0:
            self.sidebar.set_badge("cleanup", format_size(report.total_size))
        else:
            self.sidebar.set_badge("cleanup", "")

        if report.cancelled:
            self.statusBar().showMessage("Scan cancelled.", 5000)
        else:
            cached_note = f" ({hits} cached)" if hits else ""
            self.statusBar().showMessage(
                f"Scan complete — {format_size(report.total_size)} identified as reclaimable.{cached_note}",
                8000,
            )

    def _on_scan_failed(self, message: str):
        self.dashboard.set_scanning(False)
        self.cleanup_view.set_scanning(False)
        self.cleanup_view.clear_status()
        QMessageBox.critical(self, "Scan Failed", message)

    def clean_selected(self):
        categories = self.cleanup_view.selected_categories()
        if not categories:
            QMessageBox.information(self, "Cleanup", "Select at least one category to clean.")
            return
        use_recycle_bin = self._settings.get("use_recycle_bin", True)
        if self._settings.get("confirm_cleanup", True):
            dialog = ConfirmCleanupDialog(
                categories,
                dry_run_default=self._settings.get("dry_run_default", True),
                use_recycle_bin_default=use_recycle_bin,
                parent=self,
            )
            if dialog.exec() != ConfirmCleanupDialog.DialogCode.Accepted:
                return
            dry_run = dialog.is_dry_run()
            use_recycle_bin = dialog.use_recycle_bin()
        else:
            dry_run = self._settings.get("dry_run_default", True)

        worker = CleanWorker(categories, dry_run=dry_run, use_recycle_bin=use_recycle_bin)
        worker.progress.connect(self._on_clean_progress)
        worker.done.connect(lambda report: self._on_clean_done(report, categories))
        worker.failed.connect(lambda msg: QMessageBox.critical(self, "Cleanup Failed", msg))
        self._register_worker(worker)
        self.cleanup_view.set_cleaning(True, len(categories))
        worker.start()

    def _on_clean_progress(self, name, index, total):
        self.cleanup_view.set_clean_progress(name, index)

    def _on_clean_done(self, report, categories):
        self.cleanup_view.clear_status()
        self.cleanup_view.set_cleaning(False)
        summary = []
        for result in report.results:
            line = f"{result.category_name}: {result.files_deleted} files, {format_size(result.space_recovered)}"
            if result.skipped:
                line += f", {result.skipped} skipped"
            for error in result.errors[:3]:
                line += f"\n    warn: {error}"
            summary.append(line)
        text = "\n\n".join(summary)
        mode_note = ""
        if not report.dry_run:
            mode_note = (
                "\n\nFiles were moved to the Recycle Bin (remember to empty it to free space)."
                if report.use_recycle_bin
                else "\n\nFiles were permanently deleted."
            )
        text += (
            f"\n\nTOTAL: {report.total_files_deleted} files, "
            f"{format_size(report.total_space_recovered)} recovered, "
            f"{report.total_skipped} skipped"
            + ("\n\nDRY RUN - no files were actually deleted." if report.dry_run else mode_note)
        )
        if report.dry_run:
            self.statusBar().showMessage("Dry run complete (preview only, nothing deleted).", 6000)
        else:
            if self._scan_cache is not None:
                self._scan_cache.clear()
            self.dashboard.set_cleanup(
                f"{format_datetime(report.started)} - {format_size(report.total_space_recovered)} recovered"
            )
            self.sidebar.set_badge("cleanup", "")
            self.statusBar().showMessage("Cleanup completed successfully.", 6000)
            self.cleanup_view.populate(self._categories)
            self.cleanup_view.update_sizes()
            self.dashboard.refresh()
        history_append(HistoryEntry.from_report(report))
        self.history_view.refresh()
        ReportDialog(
            "Cleanup Report Summary",
            text,
            parent=self,
        ).exec()

        if not report.dry_run and self._settings.get("auto_rescan_after_cleanup", True):
            self.start_scan()

    def scan_large_files(self, root, threshold):
        worker = LargeFilesWorker(root, threshold)
        worker.progress.connect(self.large_files_view.show_progress)
        worker.done.connect(self.large_files_view.show_files)
        worker.failed.connect(lambda msg: QMessageBox.critical(self, "Scan Failed", msg))
        self._register_worker(worker)
        worker.start()

    def scan_duplicates(self, folders, min_size):
        worker = DuplicatesWorker(folders, min_size)
        worker.done.connect(lambda: self.duplicates_view.show_groups(worker.result_groups))
        worker.failed.connect(lambda msg: QMessageBox.critical(self, "Scan Failed", msg))
        self._register_worker(worker)
        worker.start()

    def scan_ai_data(self, min_size):
        worker = AiDataWorker(min_size)
        worker.done.connect(self.ai_view.show_items)
        worker.failed.connect(lambda msg: QMessageBox.critical(self, "Scan Failed", msg))
        self._register_worker(worker)
        worker.start()

    def refresh_docker(self):
        worker = DockerWorker()
        worker.done.connect(self._on_docker_info)
        worker.failed.connect(lambda msg: QMessageBox.critical(self, "Docker", msg))
        self._register_worker(worker)
        worker.start()

    def _on_docker_info(self, info, wsl_rows):
        self.docker_view.show_docker_info(info)
        self.docker_view.show_wsl_report(wsl_rows)

    def run_docker_prune(self, action_name):
        if self._settings.get("show_command_preview", True):
            cmd = (
                "docker system prune -f"
                if action_name == "prune_all"
                else f"docker {action_name.replace('_', ' ')} -f"
            )
            ans = QMessageBox.question(
                self,
                "Command Preview",
                f"The following external command will be executed:\n\n    {cmd}\n\nDo you want to proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

        worker = DockerPruneWorker(action_name)
        worker.done.connect(
            lambda result: ReportDialog(
                "Docker Prune Report",
                f"Prune finished.\n\nSkipped: {result.skipped}\nErrors: {len(result.errors)}\n"
                + ("\n".join(result.errors[:5]) if result.errors else ""),
                parent=self,
            ).exec()
        )
        worker.failed.connect(lambda msg: QMessageBox.critical(self, "Docker Prune", msg))
        self._register_worker(worker)
        worker.start()

    def closeEvent(self, event):
        for worker in self._workers:
            if hasattr(worker, "request_stop"):
                worker.request_stop()
            worker.wait(1000)
        try:
            geometry = bytes(self.saveGeometry().toHex().data()).decode("ascii")
            if geometry:
                update_settings(window_geometry=geometry)
        except Exception:
            pass
        super().closeEvent(event)


def _prepare_linux_qt_environment() -> None:
    if not sys.platform.startswith("linux"):
        return
    if os.environ.get("QT_QPA_PLATFORM"):
        return
    if os.environ.get("WAYLAND_DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "wayland"
        return
    if os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        return
    os.environ["QT_QPA_PLATFORM"] = "offscreen"


def run_gui() -> int:
    _prepare_linux_qt_environment()

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("CrapCleaner")
    app.setOrganizationName("CrapCleaner")
    app.setStyle("Fusion")
    settings = load_settings()
    apply_theme(app, settings.get("theme", "dark"))
    window = MainWindow()
    window.show()
    return app.exec()


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("--gui",):
        return run_gui()
    from crapcleaner.cli import run as cli_run

    return cli_run(argv)
