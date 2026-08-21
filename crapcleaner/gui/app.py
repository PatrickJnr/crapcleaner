"""CrapCleaner main window and GUI entry point."""

import os
import sys
import time

from PySide6.QtCore import QThread
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
from crapcleaner.categories.browsers import running_browser_names
from crapcleaner.config import load_settings, take_recovery_notice, update_settings
from crapcleaner.core.cache import ScanCache
from crapcleaner.gui.dialogs import ConfirmCleanupDialog, HelpSafetyDialog, ReportDialog
from crapcleaner.gui.sidebar import Sidebar
from crapcleaner.gui.theme import apply_theme, make_window_icon, theme_label
from crapcleaner.gui.theme_watcher import ThemeWatcher
from crapcleaner.gui.views import (
    AboutView,
    AiDataView,
    AppUpdatesView,
    CleanupView,
    DashboardView,
    DockerView,
    DrivesView,
    DuplicatesView,
    HistoryView,
    LargeFilesView,
    MemoryView,
    ServicesView,
    SettingsView,
    SpecsView,
    StartupView,
    StorageBreakdownView,
    SystemUpdatesView,
)
from crapcleaner.gui.workers import (
    AiDataWorker,
    CleanWorker,
    DockerPruneWorker,
    DockerWorker,
    DuplicatesWorker,
    LargeFilesWorker,
    ScanWorker,
)
from crapcleaner.history import append as history_append
from crapcleaner.models.history import HistoryEntry
from crapcleaner.registry import get_all_categories
from crapcleaner.system.capabilities import (
    APP_UPDATES,
    SERVICES,
    STARTUP,
    SYSTEM_UPDATES,
    is_supported,
)
from crapcleaner.utils.format import format_datetime, format_size


class MainWindow(QMainWindow):
    # Pages that exist on every platform, in navigation order.
    _CORE_PAGES = (
        "dashboard",
        "cleanup",
        "storage",
        "large",
        "duplicates",
        "ai",
        "docker",
        "specs",
        "drives",
        "memory",
    )
    # Pages whose availability the capability registry decides, in navigation order.
    _CAPABILITY_PAGES = (STARTUP, SERVICES, APP_UPDATES, SYSTEM_UPDATES)

    @staticmethod
    def _build_page_keys() -> list[str]:
        """Pages this operating system can actually show, asked of the registry."""
        keys = list(MainWindow._CORE_PAGES)
        keys += [key for key in MainWindow._CAPABILITY_PAGES if is_supported(key)]
        keys += ["history", "settings", "about"]
        return keys

    def __init__(self):
        super().__init__()
        self._PAGE_KEYS = self._build_page_keys()
        self.setWindowTitle(f"CrapCleaner v{__version__}")
        self.setWindowIcon(make_window_icon())
        self._set_default_geometry()
        self._settings = load_settings()
        disabled = set(self._settings.get("disabled_categories", []))
        self._categories = [c for c in get_all_categories() if c.id not in disabled]
        self._workers = []
        self._scan_cache = None
        self._restore_geometry()
        self._last_highlighted: str = ""
        #: nav key -> badge text, from whichever source knew the number last.
        self._nav_counts: dict[str, str] = {}
        self._counts_worker = None

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = Sidebar(__version__, page_keys=self._PAGE_KEYS)
        self.sidebar.navigation_requested.connect(self.navigate)
        self.sidebar.help_requested.connect(self.show_help_dialog)
        root_layout.addWidget(self.sidebar)

        # Pages are built on first use: assembling all sixteen up front cost about two
        # seconds before the window could be shown, and most are never opened. Each
        # slot holds an empty placeholder until the real view is needed.
        self.stack = QStackedWidget()
        self._views: dict[str, QWidget] = {}
        self._placeholders: dict[str, QWidget] = {}
        for key in self._PAGE_KEYS:
            placeholder = QWidget()
            self._placeholders[key] = placeholder
            self.stack.addWidget(placeholder)

        root_layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        self._theme = self._settings.get("theme", "dark")

        self._theme_watcher = ThemeWatcher(self)
        self._theme_watcher.themes_changed.connect(self._on_themes_changed)

        self._setup_shortcuts()
        # The dashboard is the landing page, so it is the one view worth building now.
        self.dashboard.refresh()
        self._apply_theme_to_views(self._theme)
        self.sidebar.apply_theme(self._theme)
        self.stack.setCurrentIndex(self._PAGE_KEYS.index("dashboard"))
        self.sidebar.set_active("dashboard")
        # If load_settings() had to move a damaged file aside, say so rather than let
        # the user silently lose their exclusions.
        notice = take_recovery_notice()
        if notice:
            self.statusBar().showMessage(notice, 20000)
        else:
            self.statusBar().showMessage("Ready", 3000)

    #: attribute name -> (page key, factory). Attribute access builds the view, so
    #: every existing `self.cleanup_view` style call site keeps working unchanged.
    _VIEW_SPECS = {
        "dashboard": ("dashboard", DashboardView),
        "cleanup_view": ("cleanup", CleanupView),
        "storage_view": ("storage", StorageBreakdownView),
        "large_files_view": ("large", LargeFilesView),
        "duplicates_view": ("duplicates", DuplicatesView),
        "ai_view": ("ai", AiDataView),
        "docker_view": ("docker", DockerView),
        "specs_view": ("specs", SpecsView),
        "drives_view": ("drives", DrivesView),
        "memory_view": ("memory", MemoryView),
        "startup_view": (STARTUP, StartupView),
        "services_view": (SERVICES, ServicesView),
        "app_updates_view": (APP_UPDATES, AppUpdatesView),
        "updates_view": (SYSTEM_UPDATES, SystemUpdatesView),
        "history_view": ("history", HistoryView),
        "settings_view": ("settings", SettingsView),
        "about_view": ("about", AboutView),
    }

    def __getattr__(self, name: str):
        """Build a page the first time something asks for it.

        Only called for attributes that do not already exist, so a built view is a
        plain instance attribute afterwards and costs nothing to reach.
        """
        specs = type(self).__dict__.get("_VIEW_SPECS") or MainWindow._VIEW_SPECS
        if name not in specs:
            raise AttributeError(name)
        # During __init__ the bookkeeping dicts may not exist yet.
        if "_views" not in self.__dict__:
            raise AttributeError(name)

        key, factory = specs[name]
        if key not in self._PAGE_KEYS:
            # A capability this platform does not provide: no page, no widget.
            setattr(self, name, None)
            return None

        view = self._build_view(key, factory)
        setattr(self, name, view)
        return view

    def _build_view(self, key: str, factory) -> QWidget:
        existing = self._views.get(key)
        if existing is not None:
            return existing

        view = factory(self)
        self._views[key] = view

        # Keep the slot at its original index so page order, shortcuts and navigation
        # indices all stay valid.
        index = self._PAGE_KEYS.index(key)
        placeholder = self._placeholders.pop(key, None)
        self.stack.insertWidget(index, view)
        if placeholder is not None:
            self.stack.removeWidget(placeholder)
            placeholder.deleteLater()

        apply = getattr(view, "apply_theme", None)
        if apply is not None:
            apply(getattr(self, "_theme", "dark"))

        # First-load work, deferred out of start-up along with the view itself.
        if key == "cleanup":
            view.populate(self._categories)
            view.set_scan_delta(self._settings.get("last_scan_snapshot", {}), None)
        elif key == "history":
            view.refresh()
        return view

    def _built_views(self) -> list[QWidget]:
        return [v for v in self._views.values() if v is not None]

    def _ensure_page(self, key: str) -> QWidget | None:
        """Make sure the page for `key` exists before it is shown."""
        for attr, (page_key, _factory) in self._VIEW_SPECS.items():
            if page_key == key:
                return getattr(self, attr)
        return None

    def _setup_shortcuts(self):
        # Only the first ten pages get Ctrl+N: wrapping round would bind Ctrl+1 twice,
        # which Qt treats as ambiguous and refuses to fire at all.
        for i, key in enumerate(self._PAGE_KEYS[:10]):
            key_num = (i + 1) % 10
            sc = QShortcut(QKeySequence(f"Ctrl+{key_num}"), self)
            sc.activated.connect(lambda k=key: self.navigate(k))

        help_sc = QShortcut(QKeySequence("F1"), self)
        help_sc.activated.connect(self.show_help_dialog)

        scan_sc = QShortcut(QKeySequence("Ctrl+R"), self)
        scan_sc.activated.connect(self.start_scan)

        refresh_sc = QShortcut(QKeySequence("F5"), self)
        refresh_sc.activated.connect(self._refresh_active_view)

        esc_sc = QShortcut(QKeySequence("Escape"), self)
        esc_sc.activated.connect(self.cancel_active_scan)

    def show_help_dialog(self):
        """Open the Help, Safety Philosophy, and FAQ modal dialog."""
        dlg = HelpSafetyDialog(self)
        theme = self._settings.get("theme", "dark")
        dlg.apply_theme(theme)
        dlg.exec()

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
            elif key == "startup":
                self.startup_view.refresh()
            elif key == "services":
                self.services_view.refresh()
            elif key == "app_updates":
                self.app_updates_view.refresh()
            elif key == "updates" and self.updates_view is not None:
                self.updates_view.refresh()

    def navigate(self, key: str):
        if key not in self._PAGE_KEYS:
            return
        self._ensure_page(key)
        self.stack.setCurrentIndex(self._PAGE_KEYS.index(key))
        self.sidebar.set_active(key)
        self.refresh_nav_badges()
        if key == "dashboard":
            self.dashboard.refresh()
        elif key == "history":
            self.history_view.refresh()
        elif key == "specs":
            if self.specs_view._specs is None:
                self.specs_view.refresh_specs()
        elif key == "drives":
            if not self.drives_view._drives:
                self.drives_view.refresh_drives()
        elif key == "memory":
            self.memory_view.refresh()
        elif key == "startup":
            if not self.startup_view._items:
                self.startup_view.refresh()
        elif key == "services":
            if not self.services_view._services:
                self.services_view.refresh()
        elif key == "app_updates":
            if not self.app_updates_view._all_updates:
                self.app_updates_view.refresh()
        elif key == "updates" and self.updates_view is not None:
            if not self.updates_view._report:
                self.updates_view.refresh()

    # --- sidebar badges -------------------------------------------------------

    #: page key -> the attribute holding its loaded data, and how to count it. A page
    #: that was never opened holds nothing and contributes nothing, so this is read from
    #: `self._views` rather than through the attributes, which would build the page.
    _BADGE_SOURCES = {
        "startup": ("_items", lambda items: sum(1 for i in items if i.enabled)),
        "services": ("_services", lambda svcs: sum(1 for s in svcs if s.status == "Running")),
        "drives": ("_drives", lambda disks: sum(1 for d in disks if not d.is_unmapped)),
        "app_updates": ("_all_updates", len),
        "updates": ("_report", lambda report: len(report.available_updates)),
    }

    #: Badges that mean "something is waiting for you" rather than "here is a number".
    _ATTENTION_BADGES = ("updates", "app_updates", "cleanup")

    def showEvent(self, event):
        """Count once the window is actually on screen.

        Not in __init__: the probes are real I/O, and a window that is constructed but
        never shown - every test that builds one - has no sidebar for them to fill.
        """
        super().showEvent(event)
        self._start_nav_counts()

    def _start_nav_counts(self):
        """Fill the badges once at launch from probes that are cheap or already cached."""
        if self._counts_worker is not None:
            return
        from crapcleaner.gui.workers import NavCountsWorker

        worker = NavCountsWorker(parent=self)
        self._counts_worker = worker
        worker.done.connect(self._on_nav_counts)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_nav_counts(self, counts: dict):
        for key, text in counts.items():
            # A page the user has since opened knows better than a launch-time probe.
            self._nav_counts.setdefault(key, text)
        self.refresh_nav_badges()

    def refresh_nav_badges(self):
        """Push the current counts onto the sidebar, preferring live view data."""
        counts = dict(self._nav_counts)

        for key, (field, summarise) in self._BADGE_SOURCES.items():
            view = self._views.get(key)
            if view is None:
                continue
            data = getattr(view, field, None)
            if data is None:
                continue
            # An opened page is authoritative, including when it found nothing: a stale
            # "3 updates" after installing all three is worse than no badge.
            try:
                total = summarise(data)
            except Exception:
                continue
            counts[key] = str(total) if total else ""

        for key in self.sidebar._buttons:
            text = counts.get(key, "")
            level = "accent" if text and key in self._ATTENTION_BADGES else ""
            self.sidebar.set_badge(key, text, level)

    def review_and_clean(self):
        self.navigate("cleanup")
        self.cleanup_view.review_recommended()

    def _on_themes_changed(self):
        """A theme file changed on disk: restyle now, and refresh the gallery.

        Reapplies `self._theme`, not `self._settings["theme"]` - the latter is the
        start-up snapshot, so reading it here swapped the window to whatever was
        stored when it opened instead of the theme being edited.
        """
        from crapcleaner.gui.theme import THEMES

        theme = getattr(self, "_theme", None) or self._settings.get("theme", "dark")
        if theme not in THEMES and theme != "custom":
            # The active theme's file was deleted while it was in use.
            self.statusBar().showMessage(
                f"The theme {theme!r} is no longer available; using Dark.", 6000
            )
            theme = "dark"
            update_settings(theme=theme)
            self._settings["theme"] = theme

        application = QApplication.instance()
        if isinstance(application, QApplication):
            apply_theme(application, theme, window=self)
        self._apply_theme_to_views(theme)

        settings_view = self._views.get("settings")
        if settings_view is not None and hasattr(settings_view, "refresh_theme_gallery"):
            settings_view.refresh_theme_gallery()
            gallery = getattr(settings_view, "theme_gallery", None)
            if gallery is not None and theme in THEMES:
                gallery.select_theme(theme, emit_signal=False)

        self.statusBar().showMessage(f"Themes reloaded - {theme_label(theme)} reapplied.", 4000)

    def _apply_theme_to_views(self, theme: str):
        # `_settings` is a snapshot; keep its theme in step with what is applied.
        self._settings["theme"] = theme
        self._theme = theme
        self.sidebar.apply_theme(theme)
        # Built pages only. One built later picks the theme up in _build_view, so
        # nothing is forced into existence just to be recoloured.
        for view in self._built_views():
            apply = getattr(view, "apply_theme", None)
            if apply is not None:
                apply(theme)

    #: What the dashboard was laid out for: every row fits, nothing is clipped.
    DEFAULT_SIZE = (1460, 1160)
    #: The largest floor that still fits a 1280x720 laptop. DEFAULT_SIZE cannot be the
    #: minimum: it exceeds a 1080p screen once the taskbar is taken off.
    MINIMUM_SIZE = (1200, 660)

    def _set_default_geometry(self):
        """Open at the designed size, shrunk to fit the screen, and centred."""
        self.setMinimumSize(*self.MINIMUM_SIZE)

        width, height = self.DEFAULT_SIZE
        minimum_width, minimum_height = self.MINIMUM_SIZE
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(width, available.width())
            height = min(height, available.height())
        self.resize(max(width, minimum_width), max(height, minimum_height))

        if screen is not None:
            frame = self.frameGeometry()
            frame.moveCenter(screen.availableGeometry().center())
            self.move(frame.topLeft())

    def _restore_geometry(self):
        hex_ = self._settings.get("window_geometry", "")
        if not hex_:
            return
        from PySide6.QtCore import QByteArray

        try:
            self.restoreGeometry(QByteArray.fromHex(hex_.encode("ascii")))
        except Exception:
            pass

    def switch_theme(self, theme: str, animate: bool = True):
        """Cross-fade the whole window into the given theme.

        `animate` is off while a theme is being edited in the Studio: a
        cross-fade marks a change of theme, and every slider notch is not one.
        """
        from crapcleaner.gui.theme import fade_theme_change

        def swap():
            app_inst = QApplication.instance()
            if isinstance(app_inst, QApplication):
                apply_theme(app_inst, theme, window=self)
            self._apply_theme_to_views(theme)

        if not animate or self._settings.get("reduce_motion", False):
            fade_theme_change(self, swap, duration_ms=0)
            return
        fade_theme_change(self, swap, duration_ms=180)

    def apply_settings(self):
        self._settings = load_settings()
        theme = self._settings.get("theme", "dark")
        self.switch_theme(theme)
        disabled = set(self._settings.get("disabled_categories", []))
        self._categories = [c for c in get_all_categories() if c.id not in disabled]
        self.cleanup_view.populate(self._categories)
        self.cleanup_view.set_scan_delta(self._settings.get("last_scan_snapshot", {}), None)
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
        from crapcleaner.core.scanner import ScanEngine

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
        # Repaint the tree highlight only on a real change: 8 worker threads emitting
        # rapidly otherwise backs up the UI thread.
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
        previous_snapshot = self._settings.get("last_scan_snapshot", {})
        current_snapshot = {
            "total_identified": report.total_size,
            "categories": {c.id: int(c.size) for c in self._categories},
            "started": report.started.isoformat(timespec="seconds"),
        }
        self.cleanup_view.set_scan_delta(previous_snapshot, current_snapshot)
        self._settings = update_settings(last_scan_snapshot=current_snapshot)
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

        self._nav_counts["cleanup"] = (
            format_size(report.total_size) if report.total_size > 0 else ""
        )
        self.refresh_nav_badges()

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
        locked_by = running_browser_names([c.id for c in categories])
        if locked_by:
            self.statusBar().showMessage(
                f"{', '.join(locked_by)} running - locked cache files will be skipped.", 8000
            )
        excluded_paths: set[str] = set()
        if self._settings.get("confirm_cleanup", True):
            dialog = ConfirmCleanupDialog(
                categories,
                dry_run_default=self._settings.get("dry_run_default", True),
                use_recycle_bin_default=use_recycle_bin,
                parent=self,
                locked_by=locked_by,
            )
            if dialog.exec() != ConfirmCleanupDialog.DialogCode.Accepted:
                return
            dry_run = dialog.is_dry_run()
            use_recycle_bin = dialog.use_recycle_bin()
            excluded_paths = dialog.excluded_paths()
        else:
            dry_run = self._settings.get("dry_run_default", True)
            excluded_paths = set()

        worker = CleanWorker(
            categories,
            dry_run=dry_run,
            use_recycle_bin=use_recycle_bin,
            excluded_paths=excluded_paths,
        )
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
            self.statusBar().showMessage(
                f"Cleanup finished - {report.total_skipped} item(s) skipped (locked or protected)."
                if report.total_skipped
                else "Cleanup completed successfully.",
                6000,
            )
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
        # Stop everything first, then wait once against a shared deadline: stopping and
        # waiting per worker cost up to a second each with the window frozen. Iterated
        # as a copy because each worker's finished handler mutates the list.
        watcher = getattr(self, "_theme_watcher", None)
        if watcher is not None:
            watcher.stop()

        workers = list(self._workers)
        try:
            workers += [t for t in self.findChildren(QThread) if t not in workers]
        except Exception:
            pass
        for worker in workers:
            if hasattr(worker, "request_stop"):
                worker.request_stop()

        deadline = time.monotonic() + 2.0
        for worker in workers:
            remaining = max(0.0, deadline - time.monotonic())
            if remaining <= 0:
                break
            worker.wait(int(remaining * 1000))
        try:
            geometry = bytes(self.saveGeometry().toHex().data()).decode("ascii")
            if geometry:
                update_settings(window_geometry=geometry)
        except Exception:
            pass
        super().closeEvent(event)


class NoDisplayError(RuntimeError):
    """Raised when the GUI is asked for on a system with nowhere to draw it."""


def _prepare_linux_qt_environment() -> None:
    """Pick a Qt platform plugin, or say plainly that there is no display.

    Falling back to `offscreen` made the GUI over SSH render to nowhere, which is
    indistinguishable from a hang. Callers that genuinely want offscreen (tests, CI)
    set QT_QPA_PLATFORM themselves and are honoured.
    """
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
    raise NoDisplayError(
        "No display was found (neither WAYLAND_DISPLAY nor DISPLAY is set).\n"
        "Use the command line instead - run 'crapcleaner --help' - or set "
        "QT_QPA_PLATFORM=offscreen to render with no display."
    )


def run_gui() -> int:
    try:
        _prepare_linux_qt_environment()
    except NoDisplayError as exc:
        print(str(exc), file=sys.stderr)
        return 2

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
