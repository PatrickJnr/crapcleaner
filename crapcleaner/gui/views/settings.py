"""Settings view, including theme and scan configuration."""

import os
import shutil

from PySide6.QtCore import (
    QSize,
    Qt,
    QTime,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.config import config_path, load_settings, save_settings
from crapcleaner.constants import DEFAULT_CONFIG
from crapcleaner.gui.custom_theme_builder import CustomThemeBuilderWidget
from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.theme import THEMES
from crapcleaner.gui.theme import color as theme_color
from crapcleaner.gui.theme_picker import ThemeGalleryWidget
from crapcleaner.gui.views.common import page_header
from crapcleaner.models.category import SafetyLevel
from crapcleaner.registry import get_all_categories
from crapcleaner.utils.format import format_datetime, format_size


class SettingsView(QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._categories = get_all_categories()
        self._theme = "dark"
        self._section_buttons: dict[str, QPushButton] = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)
        self.settings = load_settings()

        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        header_text = page_header(
            "Preferences & Configuration",
            "Customize interface themes, safety protections, scan engine speed, and cleanup rules.",
        )
        header_row.addWidget(header_text, 1)

        actions_box = QHBoxLayout()
        actions_box.setSpacing(8)

        self.reset_top_btn = QPushButton("Reset Defaults")
        self.reset_top_btn.setIcon(material_icon("refresh", "#888888"))
        self.reset_top_btn.setFixedHeight(34)
        self.reset_top_btn.clicked.connect(self._reset_defaults)
        actions_box.addWidget(self.reset_top_btn)

        self.save_button = QPushButton("Save Preferences")
        self.save_button.setProperty("primary", "true")
        self.save_button.setIcon(material_icon("check", "#ffffff"))
        self.save_button.setFixedHeight(34)
        self.save_button.setFixedWidth(160)
        self.save_button.clicked.connect(self._save)
        actions_box.addWidget(self.save_button)

        header_row.addLayout(actions_box)
        root.addLayout(header_row)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(6)

        self._sections = [
            ("themes", "Theme Gallery", "palette"),
            ("custom_studio", "Custom Theme Studio", "auto_awesome"),
            ("safety", "Safety & Protection", "security"),
            ("exclusions", "Exclusions & Roots", "folder"),
            ("performance", "Scan Performance", "speed"),
            ("rules", "Category Rules", "checklist"),
            ("backup", "Backup & Sync", "backup"),
        ]

        for idx, (key, label, icon_name) in enumerate(self._sections):
            btn = QPushButton(label.replace("&", "&&"))
            btn.setProperty("chip", "true")
            btn.setProperty("active", "true" if idx == 0 else "false")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(material_icon(icon_name, "#3b82f6" if idx == 0 else "#888888"))
            btn.setIconSize(QSize(16, 16))
            btn.clicked.connect(lambda _, k=key, i=idx: self._set_active_tab(k, i))
            self._section_buttons[key] = btn
            nav_row.addWidget(btn)

        nav_row.addStretch(1)
        root.addLayout(nav_row)

        self.tab_stack = QStackedWidget()

        page_themes_scroll = QScrollArea()
        page_themes_scroll.setWidgetResizable(True)
        page_themes_scroll.setFrameShape(QFrame.Shape.NoFrame)
        page_themes_container = QWidget()
        lay_themes = QVBoxLayout(page_themes_container)
        lay_themes.setContentsMargins(0, 4, 8, 4)
        lay_themes.setSpacing(14)

        current_theme = self.settings.get("theme", "dark")
        self.theme_gallery = ThemeGalleryWidget(current_theme, page_themes_container)
        self.theme_combo = self.theme_gallery.theme_combo
        self.theme_gallery.theme_changed.connect(self._on_theme_changed)
        self.theme_gallery.open_studio_requested.connect(
            lambda: self._set_active_tab("custom_studio", 1)
        )
        lay_themes.addWidget(self.theme_gallery)

        motion_card = QFrame()
        motion_card.setProperty("card", "true")
        motion_lay = QVBoxLayout(motion_card)
        motion_lay.setContentsMargins(14, 10, 14, 10)
        motion_lay.setSpacing(4)
        motion_title = QLabel("Motion & Visual Transitions")
        motion_title.setTextFormat(Qt.TextFormat.PlainText)
        motion_title.setProperty("strong", "true")
        motion_lay.addWidget(motion_title)
        self.reduce_motion_check = QCheckBox("Reduce motion (skip the theme cross-fade)")
        self.reduce_motion_check.setChecked(bool(self.settings.get("reduce_motion", False)))
        self.reduce_motion_check.toggled.connect(self._save_reduce_motion)
        motion_lay.addWidget(self.reduce_motion_check)

        self.high_contrast_check = QCheckBox(
            "High contrast (raise text in every theme to WCAG AAA)"
        )
        self.high_contrast_check.setToolTip(
            "Applies to whichever theme is active, not just the High Contrast palette."
        )
        self.high_contrast_check.setChecked(bool(self.settings.get("high_contrast", False)))
        self.high_contrast_check.toggled.connect(self._save_high_contrast)
        motion_lay.addWidget(self.high_contrast_check)
        lay_themes.addWidget(motion_card)

        page_themes_scroll.setWidget(page_themes_container)
        self.tab_stack.addWidget(page_themes_scroll)

        page_studio_scroll = QScrollArea()
        page_studio_scroll.setWidgetResizable(True)
        page_studio_scroll.setFrameShape(QFrame.Shape.NoFrame)
        page_studio_container = QWidget()
        lay_studio = QVBoxLayout(page_studio_container)
        lay_studio.setContentsMargins(0, 4, 8, 4)
        lay_studio.setSpacing(14)

        self.custom_builder = CustomThemeBuilderWidget(page_studio_container)
        self.custom_builder.theme_applied.connect(self._on_custom_theme_applied)
        self.custom_builder.theme_saved.connect(self._on_custom_theme_saved)
        # No trailing stretch here: it left the bottom half of the page empty.
        lay_studio.addWidget(self.custom_builder, 1)

        page_studio_scroll.setWidget(page_studio_container)
        self.tab_stack.addWidget(page_studio_scroll)

        page_safety = QWidget()
        lay_safety = QVBoxLayout(page_safety)
        lay_safety.setContentsMargins(0, 4, 0, 0)
        lay_safety.setSpacing(12)

        safety_card = QFrame()
        safety_card.setProperty("card", "true")
        sc_lay = QVBoxLayout(safety_card)
        sc_lay.setContentsMargins(16, 16, 16, 16)
        sc_lay.setSpacing(12)

        sc_title = QLabel("System Safety Defaults")
        sc_title.setProperty("strong", "true")
        sc_lay.addWidget(sc_title)

        self.dry_run_check = QCheckBox(
            "Default cleanups to Dry-Run mode (Simulate and preview first)"
        )
        self.dry_run_check.setChecked(self.settings.get("dry_run_default", True))
        self.confirm_check = QCheckBox("Always require confirmation dialog before cleaning")
        self.confirm_check.setChecked(self.settings.get("confirm_cleanup", True))
        self.recycle_check = QCheckBox(
            "Move deleted files to the Recycle Bin (recommended safe default)"
        )
        self.recycle_check.setChecked(bool(self.settings.get("use_recycle_bin", True)))
        self.auto_rescan_check = QCheckBox(
            "Automatically rescan system after cleanup (verify actual recovered space)"
        )
        self.auto_rescan_check.setChecked(
            bool(self.settings.get("auto_rescan_after_cleanup", True))
        )
        self.cmd_preview_check = QCheckBox(
            "Show command preview before running external operations (Docker / WSL)"
        )
        self.cmd_preview_check.setChecked(bool(self.settings.get("show_command_preview", True)))
        self.offline_check = QCheckBox(
            "Offline mode (never contact the network: no update checks, no contributor list)"
        )
        self.offline_check.setChecked(bool(self.settings.get("offline_mode", False)))

        sc_lay.addWidget(self.dry_run_check)
        sc_lay.addWidget(self.confirm_check)
        sc_lay.addWidget(self.recycle_check)
        sc_lay.addWidget(self.auto_rescan_check)
        sc_lay.addWidget(self.cmd_preview_check)
        sc_lay.addWidget(self.offline_check)
        lay_safety.addWidget(safety_card)

        guide_card = QFrame()
        guide_card.setProperty("card", "true")
        g_lay = QVBoxLayout(guide_card)
        g_lay.setContentsMargins(16, 16, 16, 16)
        g_lay.setSpacing(10)
        guide_title = QLabel("Safety Level Architecture")
        guide_title.setProperty("strong", "true")
        g_lay.addWidget(guide_title)

        levels_grid = QGridLayout()
        levels_grid.setSpacing(10)

        badge_safe = QLabel("SAFE")
        badge_safe.setProperty("badge", "true")
        badge_safe.setProperty("level", "safe")
        desc_safe = QLabel(
            "Standard temporary cache files, crash dumps, and browser histories. Zero risk."
        )
        desc_safe.setProperty("subtle", "true")

        badge_low = QLabel("LOW RISK")
        badge_low.setProperty("badge", "true")
        badge_low.setProperty("level", "warn")
        desc_low = QLabel("Package manager caches (pip, npm, cargo), old downloads, thumbnails.")
        desc_low.setProperty("subtle", "true")

        badge_review = QLabel("REVIEW")
        badge_review.setProperty("badge", "true")
        badge_review.setProperty("level", "review")
        desc_review = QLabel(
            "AI model checkpoints, Docker image caches, virtualenvs. Review recommended."
        )
        desc_review.setProperty("subtle", "true")

        badge_danger = QLabel("DANGEROUS")
        badge_danger.setProperty("badge", "true")
        badge_danger.setProperty("level", "danger")
        desc_danger = QLabel(
            "System component stores, recovery images, registry caches. Use with caution."
        )
        desc_danger.setProperty("subtle", "true")

        levels_grid.addWidget(badge_safe, 0, 0)
        levels_grid.addWidget(desc_safe, 0, 1)
        levels_grid.addWidget(badge_low, 1, 0)
        levels_grid.addWidget(desc_low, 1, 1)
        levels_grid.addWidget(badge_review, 2, 0)
        levels_grid.addWidget(desc_review, 2, 1)
        levels_grid.addWidget(badge_danger, 3, 0)
        levels_grid.addWidget(desc_danger, 3, 1)

        g_lay.addLayout(levels_grid)
        lay_safety.addWidget(guide_card)
        lay_safety.addStretch(1)

        self.tab_stack.addWidget(page_safety)

        page_excl = QWidget()
        lay_excl = QHBoxLayout(page_excl)
        lay_excl.setContentsMargins(0, 4, 0, 0)
        lay_excl.setSpacing(12)

        card_excl = QFrame()
        card_excl.setProperty("card", "true")
        ce_lay = QVBoxLayout(card_excl)
        ce_lay.setContentsMargins(14, 14, 14, 14)
        ce_lay.setSpacing(8)

        ce_title = QLabel("Cleanup Exclusions")
        ce_title.setProperty("strong", "true")
        ce_sub = QLabel("Permanently skip these folders during all scans and cleanups.")
        ce_sub.setProperty("subtle", "true")
        ce_sub.setWordWrap(True)
        ce_lay.addWidget(ce_title)
        ce_lay.addWidget(ce_sub)

        self.exclusions_list = QListWidget()
        self.exclusions_list.setAccessibleName("Folders excluded from every scan")
        for excl_path in self.settings.get("excluded_paths", []):
            self.exclusions_list.addItem(excl_path)
        ce_lay.addWidget(self.exclusions_list, 1)

        row_excl_btns = QHBoxLayout()
        add_excl_btn = QPushButton("Add Folder...")
        add_excl_btn.setIcon(material_icon("add", "#888888"))
        add_excl_btn.clicked.connect(self._add_exclusion)
        rem_excl_btn = QPushButton("Remove Selected")
        rem_excl_btn.setIcon(material_icon("delete", "#888888"))
        rem_excl_btn.clicked.connect(self._remove_exclusion)
        row_excl_btns.addWidget(add_excl_btn)
        row_excl_btns.addWidget(rem_excl_btn)
        row_excl_btns.addStretch(1)
        ce_lay.addLayout(row_excl_btns)
        lay_excl.addWidget(card_excl, 1)

        card_roots = QFrame()
        card_roots.setProperty("card", "true")
        cr_lay = QVBoxLayout(card_roots)
        cr_lay.setContentsMargins(14, 14, 14, 14)
        cr_lay.setSpacing(8)

        cr_title = QLabel("Developer Scan Roots")
        cr_title.setProperty("strong", "true")
        self.all_drives_check = QCheckBox(
            "Automatically search all local drives for developer caches"
        )
        self.all_drives_check.setChecked(bool(self.settings.get("scan_all_drives", True)))
        cr_lay.addWidget(cr_title)
        cr_lay.addWidget(self.all_drives_check)

        self.roots_list = QListWidget()
        self.roots_list.setAccessibleName("Extra folders to scan")
        for root_path in self.settings.get("scan_roots", []):
            self.roots_list.addItem(root_path)
        cr_lay.addWidget(self.roots_list, 1)

        row_roots_btns = QHBoxLayout()
        add_root_btn = QPushButton("Add Root Folder...")
        add_root_btn.setIcon(material_icon("add", "#888888"))
        add_root_btn.clicked.connect(self._add_root)
        rem_root_btn = QPushButton("Remove Selected")
        rem_root_btn.setIcon(material_icon("delete", "#888888"))
        rem_root_btn.clicked.connect(self._remove_root)
        row_roots_btns.addWidget(add_root_btn)
        row_roots_btns.addWidget(rem_root_btn)
        row_roots_btns.addStretch(1)
        cr_lay.addLayout(row_roots_btns)
        lay_excl.addWidget(card_roots, 1)

        self.tab_stack.addWidget(page_excl)

        page_perf = QWidget()
        lay_perf = QVBoxLayout(page_perf)
        lay_perf.setContentsMargins(0, 4, 0, 0)
        lay_perf.setSpacing(12)

        perf_card = QFrame()
        perf_card.setProperty("card", "true")
        pc_lay = QVBoxLayout(perf_card)
        pc_lay.setContentsMargins(16, 16, 16, 16)
        pc_lay.setSpacing(14)

        pc_title = QLabel("Scanning Engine Performance")
        pc_title.setProperty("strong", "true")
        pc_lay.addWidget(pc_title)

        row_files = QHBoxLayout()
        row_files.addWidget(QLabel("Max Files Scanned per Run:"))
        self.max_files_spin = QSpinBox()
        self.max_files_spin.setAccessibleName("Maximum files scanned")
        self.max_files_spin.setRange(5000, 2000000)
        self.max_files_spin.setSingleStep(10000)
        self.max_files_spin.setSuffix(" files")
        self.max_files_spin.setValue(int(self.settings.get("max_scan_files", 200000)))
        row_files.addWidget(self.max_files_spin)

        p_fast = QPushButton("Quick (50k)")
        p_fast.clicked.connect(lambda: self.max_files_spin.setValue(50000))
        p_std = QPushButton("Standard (200k)")
        p_std.clicked.connect(lambda: self.max_files_spin.setValue(200000))
        p_deep = QPushButton("Deep (1M)")
        p_deep.clicked.connect(lambda: self.max_files_spin.setValue(1000000))
        row_files.addWidget(p_fast)
        row_files.addWidget(p_std)
        row_files.addWidget(p_deep)
        row_files.addStretch(1)
        pc_lay.addLayout(row_files)

        row_ttl = QHBoxLayout()
        row_ttl.addWidget(QLabel("Scan Cache TTL (Seconds):"))
        self.cache_ttl_spin = QSpinBox()
        self.cache_ttl_spin.setAccessibleName("Scan cache lifetime")
        self.cache_ttl_spin.setRange(0, 3600)
        self.cache_ttl_spin.setSuffix(" s")
        self.cache_ttl_spin.setValue(int(self.settings.get("scan_cache_ttl", 300)))
        row_ttl.addWidget(self.cache_ttl_spin)
        row_ttl.addStretch(1)
        pc_lay.addLayout(row_ttl)

        ttl_sub = QLabel(
            "Higher TTL avoids re-scanning unmodified directories within the specified time window."
        )
        ttl_sub.setProperty("subtle", "true")
        pc_lay.addWidget(ttl_sub)

        lay_perf.addWidget(perf_card)

        # The schedule belongs to the operating system - Task Scheduler or a systemd
        # timer - so this reports what is registered rather than storing a setting.
        sched_card = QFrame()
        sched_card.setProperty("card", "true")
        sc_lay = QVBoxLayout(sched_card)
        sc_lay.setContentsMargins(16, 16, 16, 16)
        sc_lay.setSpacing(12)

        sc_title = QLabel("Scheduled Scan")
        sc_title.setProperty("strong", "true")
        sc_lay.addWidget(sc_title)

        sc_sub = QLabel(
            "Run a scan on a schedule and be told when there is something worth cleaning. "
            "A scheduled run only ever scans - it never deletes anything."
        )
        sc_sub.setWordWrap(True)
        sc_sub.setProperty("subtle", "true")
        sc_lay.addWidget(sc_sub)

        self.schedule_status_label = QLabel("Checking…")
        self.schedule_status_label.setWordWrap(True)
        sc_lay.addWidget(self.schedule_status_label)

        sched_row = QHBoxLayout()
        sched_row.setSpacing(10)

        sched_row.addWidget(QLabel("Run:"))
        self.schedule_frequency = QComboBox()
        self.schedule_frequency.addItem("Every day", "daily")
        self.schedule_frequency.addItem("Every week", "weekly")
        self.schedule_frequency.setAccessibleName("How often the scheduled scan runs")
        sched_row.addWidget(self.schedule_frequency)

        sched_row.addWidget(QLabel("at"))
        self.schedule_time = QTimeEdit()
        self.schedule_time.setDisplayFormat("HH:mm")
        self.schedule_time.setAccessibleName("Time of day the scheduled scan runs")
        sched_row.addWidget(self.schedule_time)

        sched_row.addWidget(QLabel("Tell me above:"))
        self.schedule_threshold = QSpinBox()
        self.schedule_threshold.setRange(0, 1024 * 1024)
        self.schedule_threshold.setSingleStep(512)
        self.schedule_threshold.setSuffix(" MB")
        self.schedule_threshold.setAccessibleName("Notify when at least this much is reclaimable")
        sched_row.addWidget(self.schedule_threshold)
        sched_row.addStretch(1)
        sc_lay.addLayout(sched_row)

        sched_actions = QHBoxLayout()
        sched_actions.setSpacing(8)
        self.schedule_enable_btn = QPushButton("Enable Schedule")
        self.schedule_enable_btn.setProperty("primary", "true")
        self.schedule_enable_btn.clicked.connect(self._enable_schedule)
        self.schedule_disable_btn = QPushButton("Remove Schedule")
        self.schedule_disable_btn.clicked.connect(self._disable_schedule)
        self.schedule_run_btn = QPushButton("Run One Now")
        self.schedule_run_btn.setToolTip("Run the unattended scan once, right now")
        self.schedule_run_btn.clicked.connect(self._run_scheduled_scan_now)
        sched_actions.addWidget(self.schedule_enable_btn)
        sched_actions.addWidget(self.schedule_disable_btn)
        sched_actions.addWidget(self.schedule_run_btn)
        sched_actions.addStretch(1)
        sc_lay.addLayout(sched_actions)

        self.schedule_last_label = QLabel("")
        self.schedule_last_label.setWordWrap(True)
        self.schedule_last_label.setProperty("subtle", "true")
        sc_lay.addWidget(self.schedule_last_label)

        lay_perf.addWidget(sched_card)
        lay_perf.addStretch(1)
        self.tab_stack.addWidget(page_perf)
        self._refresh_schedule_state()

        page_rules = QWidget()
        lay_rules = QVBoxLayout(page_rules)
        lay_rules.setContentsMargins(0, 4, 0, 0)
        lay_rules.setSpacing(10)

        rules_card = QFrame()
        rules_card.setProperty("card", "true")
        rc_lay = QVBoxLayout(rules_card)
        rc_lay.setContentsMargins(14, 14, 14, 14)
        rc_lay.setSpacing(10)

        r_header = QHBoxLayout()
        r_title = QLabel("Active Category Rules (Disabled rules are skipped)")
        r_title.setProperty("strong", "true")
        r_header.addWidget(r_title, 1)

        btn_all = QPushButton("Enable All")
        btn_all.clicked.connect(self._enable_all_categories)
        btn_safe = QPushButton("Safe Only")
        btn_safe.clicked.connect(self._enable_safe_only_categories)
        btn_none = QPushButton("Disable All")
        btn_none.clicked.connect(self._disable_all_categories)
        r_header.addWidget(btn_all)
        r_header.addWidget(btn_safe)
        r_header.addWidget(btn_none)
        rc_lay.addLayout(r_header)

        self.cat_list = QListWidget()
        self.cat_list.setAccessibleName("Cleanup categories to offer")
        self._rebuild_cat_list()
        rc_lay.addWidget(self.cat_list, 1)
        lay_rules.addWidget(rules_card)

        self.tab_stack.addWidget(page_rules)

        page_backup = QWidget()
        lay_backup = QVBoxLayout(page_backup)
        lay_backup.setContentsMargins(0, 4, 0, 0)
        lay_backup.setSpacing(12)

        backup_card = QFrame()
        backup_card.setProperty("card", "true")
        bc_lay = QVBoxLayout(backup_card)
        bc_lay.setContentsMargins(16, 16, 16, 16)
        bc_lay.setSpacing(12)

        bc_title = QLabel("Configuration Backup & Migration")
        bc_title.setProperty("strong", "true")
        bc_sub = QLabel(
            "Export your settings to JSON to create backups or transfer rules between machines."
        )
        bc_sub.setProperty("subtle", "true")
        bc_lay.addWidget(bc_title)
        bc_lay.addWidget(bc_sub)

        bc_btns = QHBoxLayout()
        export_btn = QPushButton("Export Settings...")
        export_btn.setIcon(material_icon("download", "#888888"))
        export_btn.clicked.connect(self._export)
        import_btn = QPushButton("Import Settings...")
        import_btn.setIcon(material_icon("upload", "#888888"))
        import_btn.clicked.connect(self._import)
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setIcon(material_icon("refresh", "#888888"))
        reset_btn.clicked.connect(self._reset_defaults)

        bc_btns.addWidget(export_btn)
        bc_btns.addWidget(import_btn)
        bc_btns.addWidget(reset_btn)
        bc_btns.addStretch(1)
        bc_lay.addLayout(bc_btns)

        cfg_loc = QLabel(f"Active Config Path: {config_path()}")
        cfg_loc.setProperty("subtle", "true")
        cfg_loc.setStyleSheet("font-size: 11px; font-family: monospace;")
        bc_lay.addWidget(cfg_loc)

        lay_backup.addWidget(backup_card)
        lay_backup.addStretch(1)
        self.tab_stack.addWidget(page_backup)

        root.addWidget(self.tab_stack, 1)

    def _refresh_schedule_state(self):
        """Ask the operating system what is registered, and show that."""
        from datetime import datetime

        from crapcleaner.core.scheduler import last_result, status

        state = status()
        config = state.config

        self.schedule_frequency.setCurrentIndex(1 if config.frequency == "weekly" else 0)
        hours, _, minutes = config.at.partition(":")
        self.schedule_time.setTime(QTime(int(hours or 18), int(minutes or 0)))
        self.schedule_threshold.setValue(int(config.threshold_mb))

        for widget in (
            self.schedule_frequency,
            self.schedule_time,
            self.schedule_threshold,
            self.schedule_enable_btn,
            self.schedule_run_btn,
        ):
            widget.setEnabled(state.supported)
        self.schedule_disable_btn.setEnabled(state.supported and state.registered)

        if not state.supported:
            self.schedule_status_label.setText(state.detail)
        elif state.registered:
            self.schedule_status_label.setText(
                f"Scheduled: {config.frequency} at {config.at}. Registered as {state.detail}."
            )
        else:
            self.schedule_status_label.setText("No scheduled scan. Nothing runs in the background.")

        previous = last_result()
        if previous:
            when = datetime.fromtimestamp(previous.get("finished_at", 0))
            self.schedule_last_label.setText(
                f"Last scheduled scan: {format_datetime(when)} - "
                f"{format_size(previous.get('total_reclaimable', 0))} reclaimable."
            )
        else:
            self.schedule_last_label.setText("No scheduled scan has run yet.")

    def _enable_schedule(self):
        from crapcleaner.core.scheduler import ScheduleConfig, enable

        wanted = ScheduleConfig(
            enabled=True,
            at=self.schedule_time.time().toString("HH:mm"),
            frequency=self.schedule_frequency.currentData() or "daily",
            threshold_mb=int(self.schedule_threshold.value()),
        )
        try:
            ok, message = enable(wanted)
        except ValueError as exc:
            QMessageBox.warning(self, "Scheduled Scan", str(exc))
            return
        if ok:
            QMessageBox.information(self, "Scheduled Scan", message)
        else:
            QMessageBox.warning(self, "Scheduled Scan", message)
        self._refresh_schedule_state()

    def _disable_schedule(self):
        from crapcleaner.core.scheduler import disable

        ok, message = disable()
        if not ok:
            QMessageBox.warning(self, "Scheduled Scan", message)
        self._refresh_schedule_state()

    def _run_scheduled_scan_now(self):
        """Run the unattended scan once, off the interface thread."""
        from crapcleaner.gui.workers import ScheduledScanWorker, is_worker_running

        if is_worker_running(getattr(self, "_schedule_worker", None)):
            return
        self.schedule_run_btn.setEnabled(False)
        self.schedule_status_label.setText("Running a scan…")

        worker = ScheduledScanWorker(parent=self)
        self._schedule_worker = worker
        worker.done.connect(lambda _result: self._refresh_schedule_state())
        worker.failed.connect(lambda message: QMessageBox.warning(self, "Scheduled Scan", message))
        worker.finished.connect(lambda: self.schedule_run_btn.setEnabled(True))
        worker.finished.connect(lambda: setattr(self, "_schedule_worker", None))
        worker.start()

    def _set_active_tab(self, key: str, index: int):
        self.tab_stack.setCurrentIndex(index)
        theme = getattr(self, "_theme", "dark")
        accent_col = theme_color(theme, "accent")
        muted_col = theme_color(theme, "muted")
        for k, btn in self._section_buttons.items():
            is_active = k == key
            btn.setProperty("active", "true" if is_active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        for idx, (k, _, icon_name) in enumerate(self._sections):
            if k in self._section_buttons:
                btn = self._section_buttons[k]
                icon_col = accent_col if idx == index else muted_col
                btn.setIcon(material_icon(icon_name, icon_col))

    def _enable_all_categories(self):
        for i in range(self.cat_list.count()):
            self.cat_list.item(i).setCheckState(Qt.CheckState.Checked)

    def _disable_all_categories(self):
        for i in range(self.cat_list.count()):
            self.cat_list.item(i).setCheckState(Qt.CheckState.Unchecked)

    def _enable_safe_only_categories(self):
        cat_map = {c.id: c for c in self._categories}
        for i in range(self.cat_list.count()):
            cat_id = self.cat_list.item(i).data(Qt.ItemDataRole.UserRole)
            cat = cat_map.get(cat_id)
            if cat and cat.safety_level == SafetyLevel.SAFE:
                self.cat_list.item(i).setCheckState(Qt.CheckState.Checked)
            else:
                self.cat_list.item(i).setCheckState(Qt.CheckState.Unchecked)

    def _rebuild_cat_list(self):
        self.cat_list.clear()
        disabled_raw = self.settings.get("disabled_categories", [])
        disabled = set(disabled_raw) if isinstance(disabled_raw, (list, set, tuple)) else set()
        for category in self._categories:
            item = QListWidgetItem(
                f"{category.name} ({category.safety_level.label})"
                + (" [requires admin]" if category.requires_admin else "")
            )
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Unchecked if category.id in disabled else Qt.CheckState.Checked
            )
            item.setToolTip(category.description)
            item.setData(Qt.ItemDataRole.UserRole, category.id)
            self.cat_list.addItem(item)

    def _add_root(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose development root folder")
        if folder and not self.roots_list.findItems(folder, Qt.MatchFlag.MatchExactly):
            self.roots_list.addItem(folder)

    def _remove_root(self):
        for item in self.roots_list.selectedItems():
            self.roots_list.takeItem(self.roots_list.row(item))

    def _add_exclusion(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Choose folder to permanently exclude from cleanup"
        )
        if folder and not self.exclusions_list.findItems(folder, Qt.MatchFlag.MatchExactly):
            self.exclusions_list.addItem(folder)

    def _save_high_contrast(self, enabled: bool):
        from crapcleaner.gui.theme import set_high_contrast

        self.settings["high_contrast"] = enabled
        save_settings({"high_contrast": enabled})
        # The palette layer holds the flag in memory, so it has to be told directly.
        set_high_contrast(enabled)
        self._main.apply_settings()

    def _save_reduce_motion(self, enabled: bool):
        self.settings["reduce_motion"] = enabled
        save_settings({"reduce_motion": enabled})
        main_settings = getattr(self._main, "_settings", None)
        if isinstance(main_settings, dict):
            main_settings["reduce_motion"] = enabled

    def _select_theme(self, theme: str):
        if theme in THEMES:
            if hasattr(self, "theme_gallery"):
                self.theme_gallery.select_theme(theme, emit_signal=False)
            else:
                self.theme_combo.setCurrentIndex(THEMES.index(theme))

    def _on_custom_theme_saved(self, theme_id: str):
        """A Studio theme was saved: show it in the gallery and switch to it."""
        from crapcleaner.gui.theme import theme_label

        self.refresh_theme_gallery()
        self.theme_gallery.select_theme(theme_id)
        window = self.window()
        status = getattr(window, "statusBar", None)
        if callable(status):
            status().showMessage(f"Saved the theme {theme_label(theme_id)!r}.", 6000)

    def refresh_theme_gallery(self):
        """Rebuild the gallery from the current registry."""
        gallery = getattr(self, "theme_gallery", None)
        if gallery is not None and hasattr(gallery, "refresh_themes"):
            gallery.refresh_themes()

    def _on_custom_theme_applied(self, custom_cfg: dict):
        """Apply and persist custom theme configuration."""
        from crapcleaner.gui.theme import invalidate_custom_theme_cache

        invalidate_custom_theme_cache()
        already_custom = self.settings.get("theme") == "custom"
        self.settings["theme"] = "custom"
        self.settings["custom_theme"] = custom_cfg
        save_settings({"theme": "custom", "custom_theme": custom_cfg})
        # The gallery only needs telling the first time.
        if not already_custom and hasattr(self, "theme_gallery"):
            self.theme_gallery.select_theme("custom", emit_signal=False)
        switch = getattr(self._main, "switch_theme", None)
        if switch is not None:
            try:
                switch("custom", animate=False)
            except TypeError:
                switch("custom")

    def _on_theme_changed(self, theme: str):
        """Apply theme selected from the visual theme gallery."""
        self.settings["theme"] = theme
        save_settings({"theme": theme})
        switch = getattr(self._main, "switch_theme", None)
        if switch is not None:
            switch(theme)

    def _preview_theme(self, _label: str):
        """Apply the selected theme immediately and remember it across launches."""
        theme = self.theme_combo.currentData()
        if not theme:
            return
        self.settings["theme"] = theme
        save_settings({"theme": theme})
        if hasattr(self, "theme_gallery"):
            self.theme_gallery.select_theme(theme, emit_signal=False)
        switch = getattr(self._main, "switch_theme", None)
        if switch is not None:
            switch(theme)

    def apply_theme(self, theme: str):
        self._theme = theme
        if hasattr(self, "theme_gallery"):
            self.theme_gallery.select_theme(theme, emit_signal=False)

        accent_col = theme_color(theme, "accent")
        muted_col = theme_color(theme, "muted")

        self.save_button.setIcon(material_icon("check", "#ffffff"))
        self.reset_top_btn.setIcon(material_icon("refresh", muted_col))

        curr_idx = self.tab_stack.currentIndex()
        for idx, (key, _, icon_name) in enumerate(self._sections):
            if key in self._section_buttons:
                btn = self._section_buttons[key]
                icon_col = accent_col if idx == curr_idx else muted_col
                btn.setIcon(material_icon(icon_name, icon_col))

    def _remove_exclusion(self):
        for item in self.exclusions_list.selectedItems():
            self.exclusions_list.takeItem(self.exclusions_list.row(item))

    def _save(self):
        roots = [self.roots_list.item(i).text() for i in range(self.roots_list.count())]
        exclusions = [
            self.exclusions_list.item(i).text() for i in range(self.exclusions_list.count())
        ]
        disabled = [
            self.cat_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.cat_list.count())
            if self.cat_list.item(i).checkState() == Qt.CheckState.Unchecked
        ]
        settings = {
            "theme": self.theme_combo.currentData(),
            "reduce_motion": self.reduce_motion_check.isChecked(),
            "high_contrast": self.high_contrast_check.isChecked(),
            "offline_mode": self.offline_check.isChecked(),
            "dry_run_default": self.dry_run_check.isChecked(),
            "confirm_cleanup": self.confirm_check.isChecked(),
            "use_recycle_bin": self.recycle_check.isChecked(),
            "auto_rescan_after_cleanup": self.auto_rescan_check.isChecked(),
            "show_command_preview": self.cmd_preview_check.isChecked(),
            "scan_roots": roots,
            "excluded_paths": exclusions,
            "scan_all_drives": self.all_drives_check.isChecked(),
            "scan_cache_ttl": self.cache_ttl_spin.value(),
            "max_scan_files": self.max_files_spin.value(),
            "disabled_categories": disabled,
        }
        save_settings(settings)
        self.settings = settings
        self._main.apply_settings()
        QMessageBox.information(self, "Settings", "Preferences saved successfully.")

    def _reset_defaults(self):
        ans = QMessageBox.question(self, "Reset Settings", "Reset all settings to default values?")
        if ans == QMessageBox.StandardButton.Yes:
            save_settings(dict(DEFAULT_CONFIG))
            self.settings = load_settings()
            self._select_theme(self.settings.get("theme", "dark"))
            self.dry_run_check.setChecked(self.settings.get("dry_run_default", True))
            self.confirm_check.setChecked(self.settings.get("confirm_cleanup", True))
            self.recycle_check.setChecked(bool(self.settings.get("use_recycle_bin", True)))
            self.auto_rescan_check.setChecked(
                bool(self.settings.get("auto_rescan_after_cleanup", True))
            )
            self.cmd_preview_check.setChecked(bool(self.settings.get("show_command_preview", True)))
            self.reduce_motion_check.setChecked(bool(self.settings.get("reduce_motion", False)))
            self.high_contrast_check.setChecked(bool(self.settings.get("high_contrast", False)))
            self.offline_check.setChecked(bool(self.settings.get("offline_mode", False)))
            self.max_files_spin.setValue(int(self.settings.get("max_scan_files", 200000)))
            self.all_drives_check.setChecked(bool(self.settings.get("scan_all_drives", True)))
            self.cache_ttl_spin.setValue(int(self.settings.get("scan_cache_ttl", 300)))
            self.roots_list.clear()
            self.exclusions_list.clear()
            self._rebuild_cat_list()
            self._main.apply_settings()

    def _export(self):
        default = os.path.join(os.path.expanduser("~"), "crapcleaner-settings.json")
        dest, _ = QFileDialog.getSaveFileName(self, "Export Settings", default, "JSON (*.json)")
        if not dest:
            return
        try:
            shutil.copyfile(config_path(), dest)
            QMessageBox.information(self, "Export Settings", f"Settings exported to:\n{dest}")
        except OSError as exc:
            QMessageBox.warning(self, "Export Error", str(exc))

    def _import(self):
        src, _ = QFileDialog.getOpenFileName(
            self, "Import Settings", os.path.expanduser("~"), "JSON (*.json)"
        )
        if not src:
            return
        try:
            shutil.copyfile(src, config_path())
            self.settings = load_settings()
            self._select_theme(self.settings.get("theme", "dark"))
            self.dry_run_check.setChecked(self.settings.get("dry_run_default", True))
            self.confirm_check.setChecked(self.settings.get("confirm_cleanup", True))
            self.recycle_check.setChecked(bool(self.settings.get("use_recycle_bin", True)))
            self.auto_rescan_check.setChecked(
                bool(self.settings.get("auto_rescan_after_cleanup", True))
            )
            self.cmd_preview_check.setChecked(bool(self.settings.get("show_command_preview", True)))
            self.reduce_motion_check.setChecked(bool(self.settings.get("reduce_motion", False)))
            self.high_contrast_check.setChecked(bool(self.settings.get("high_contrast", False)))
            self.offline_check.setChecked(bool(self.settings.get("offline_mode", False)))
            self.max_files_spin.setValue(int(self.settings.get("max_scan_files", 200000)))
            self.all_drives_check.setChecked(bool(self.settings.get("scan_all_drives", True)))
            self.cache_ttl_spin.setValue(int(self.settings.get("scan_cache_ttl", 300)))
            self.roots_list.clear()
            for root_path in self.settings.get("scan_roots", []):
                self.roots_list.addItem(root_path)
            self.exclusions_list.clear()
            for excl_path in self.settings.get("excluded_paths", []):
                self.exclusions_list.addItem(excl_path)
            self._rebuild_cat_list()
            self._main.apply_settings()
            QMessageBox.information(self, "Import Settings", "Settings imported successfully.")
        except OSError as exc:
            QMessageBox.warning(self, "Import Error", str(exc))
