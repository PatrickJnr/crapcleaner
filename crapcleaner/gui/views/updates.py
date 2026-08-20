"""System update and application update views."""

from typing import Any

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QFont,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.views.common import CrapTable, _c, badge, page_header, section_label, stat_card
from crapcleaner.system.capabilities import (
    SYSTEM_UPDATES,
    get_capability,
)
from crapcleaner.utils.format import (
    format_size,
)
from crapcleaner.utils.platform import (
    elevate,
    is_admin,
    is_windows,
)


class SystemUpdatesView(QWidget):
    """View and manage pending operating-system updates and update history.

    Backed by Windows Update on Windows and the distribution package manager on
    Linux; all platform vocabulary comes from the capability registry.
    """

    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._theme = "dark"
        self._report = None
        self._worker = None
        self._install_worker = None
        self._capability = get_capability(SYSTEM_UPDATES)
        self._terms = self._capability.terms
        self._update_noun = self._terms.get("update_noun", "update")
        self._history_noun = self._terms.get("history_noun", "update")
        self._os_name = self._terms.get("os_name", "system")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)
        root.addWidget(page_header(self._capability.title, self._capability.subtitle))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(14)

        # 1. Hero Card
        self.hero_card = QFrame()
        self.hero_card.setProperty("card", "true")
        hero_lay = QVBoxLayout(self.hero_card)
        hero_lay.setContentsMargins(18, 16, 18, 16)
        hero_lay.setSpacing(10)

        hero_top = QHBoxLayout()
        self.hero_badge = badge("UP TO DATE", "safe")
        self.service_badge = badge("CHECKING BACKEND", "muted")
        self.elevated_badge = badge(
            "ELEVATED (ADMIN)" if is_admin() else "STANDARD USER",
            "safe" if is_admin() else "muted",
        )
        hero_top.addWidget(self.hero_badge)
        hero_top.addWidget(self.service_badge)
        hero_top.addWidget(self.elevated_badge)
        hero_top.addStretch(1)

        if not is_admin() and is_windows():
            self.elevate_btn = QPushButton("Relaunch as Admin")
            self.elevate_btn.setProperty("secondary", "true")
            self.elevate_btn.setIcon(material_icon("security", _c(self._theme, "accent")))
            self.elevate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.elevate_btn.clicked.connect(self._relaunch_admin)
            hero_top.addWidget(self.elevate_btn)

        self.settings_btn = QPushButton(self._terms.get("settings_label", "Open Update Settings"))
        self.settings_btn.setIcon(material_icon("settings", _c(self._theme, "text")))
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self._open_settings)

        self.install_btn = QPushButton("Install Updates")
        self.install_btn.setProperty("primary", "true")
        self.install_btn.setIcon(material_icon("system_update", "#ffffff"))
        self.install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_btn.clicked.connect(self._install_updates)
        self.install_btn.setEnabled(False)

        self.check_btn = QPushButton("Check for Updates")
        self.check_btn.setIcon(material_icon("refresh", _c(self._theme, "text")))
        self.check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_btn.clicked.connect(self.refresh)

        hero_top.addWidget(self.settings_btn)
        hero_top.addWidget(self.install_btn)
        hero_top.addWidget(self.check_btn)
        hero_lay.addLayout(hero_top)

        self.hero_title = QLabel(f"{self._capability.title} Manager")
        self.hero_title.setStyleSheet(
            f"font-size: 20px; font-weight: 800; color: {_c(self._theme, 'text')};"
        )
        hero_lay.addWidget(self.hero_title)

        self.status_label = QLabel(
            f"Click 'Check for Updates' to query {self._os_name} for pending {self._update_noun}s."
        )
        self.status_label.setProperty("subtle", "true")
        self.status_label.setStyleSheet(f"font-size: 11px; color: {_c(self._theme, 'muted')};")
        hero_lay.addWidget(self.status_label)

        # Result banner
        self.result_banner = QFrame()
        self.result_banner.setProperty("card", "true")
        self.result_banner.setVisible(False)
        rb_lay = QHBoxLayout(self.result_banner)
        rb_lay.setContentsMargins(12, 8, 12, 8)
        rb_lay.setSpacing(10)
        self.result_icon = QLabel()
        self.result_icon.setPixmap(material_icon("check", _c(self._theme, "safe")).pixmap(18, 18))
        self.result_label = QLabel("")
        self.result_label.setStyleSheet(f"font-weight: 600; color: {_c(self._theme, 'text')};")
        self.result_label.setWordWrap(True)
        self.banner_settings_btn = QPushButton("Open Settings")
        self.banner_settings_btn.setIcon(material_icon("settings", _c(self._theme, "text")))
        self.banner_settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.banner_settings_btn.clicked.connect(self._open_settings)
        rb_lay.addWidget(self.result_icon)
        rb_lay.addWidget(self.result_label, 1)
        rb_lay.addWidget(self.banner_settings_btn)
        hero_lay.addWidget(self.result_banner)

        layout.addWidget(self.hero_card)

        # 2. Metric Cards Row
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(12)
        c1, self.avail_card_val, self.avail_card_sub = stat_card(
            "AVAILABLE UPDATES", "0", "Ready to install", self._theme
        )
        c2, self.size_card_val, self.size_card_sub = stat_card(
            "DOWNLOAD SIZE", "0 B", "Cumulative package size", self._theme
        )
        c3, self.crit_card_val, self.crit_card_sub = stat_card(
            "CRITICAL / SECURITY", "0", "High severity fixes", self._theme
        )
        c4, self.hist_card_val, self.hist_card_sub = stat_card(
            "INSTALLED HOTFIXES", "0", "Recent history", self._theme
        )
        for c in (c1, c2, c3, c4):
            metrics_row.addWidget(c)
        layout.addLayout(metrics_row)

        # 3. Available Updates Section
        layout.addWidget(section_label(f"Available {self._capability.title}"))
        self.avail_table = CrapTable(0, 5)
        # Windows identifies updates by KB article; package managers use the package
        # version, so the second column is labelled per platform.
        self.avail_table.setHorizontalHeaderLabels(
            [
                "Title",
                "KB Article" if self._capability.platform == "windows" else "Version",
                "Severity",
                "Size",
                "Category",
            ]
        )
        self.avail_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.avail_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.avail_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.avail_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.avail_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self.avail_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.avail_table.setMinimumHeight(180)
        layout.addWidget(self.avail_table)

        # 4. Installed Update History Section
        layout.addWidget(
            section_label(self._terms.get("history_label", "Installed Update History"))
        )

        # Filter bar for history
        hist_filter_card = QFrame()
        hist_filter_card.setProperty("card", "true")
        hf_lay = QHBoxLayout(hist_filter_card)
        hf_lay.setContentsMargins(14, 8, 14, 8)
        hf_lay.setSpacing(10)
        h_icon = QLabel()
        h_icon.setPixmap(material_icon("search", _c(self._theme, "muted")).pixmap(16, 16))
        hf_lay.addWidget(h_icon)
        self.hist_search = QLineEdit()
        self.hist_search.setPlaceholderText(
            f"Filter installed {self._history_noun}s by identifier or description..."
        )
        self.hist_search.textChanged.connect(self._filter_history)
        hf_lay.addWidget(self.hist_search)
        layout.addWidget(hist_filter_card)

        self.hist_table = CrapTable(0, 4)
        self.hist_table.setHorizontalHeaderLabels(
            [
                "HotFix ID" if self._capability.platform == "windows" else "Transaction",
                "Description",
                "Installed Date",
                "Installed By" if self._capability.platform == "windows" else "Source",
            ]
        )
        self.hist_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.hist_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.hist_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.hist_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.hist_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.hist_table.setMinimumHeight(220)
        layout.addWidget(self.hist_table)

        scroll.setWidget(container)
        root.addWidget(scroll)

    def refresh(self):
        self.status_label.setText(
            f"Checking for {self._update_noun}s and recent {self._history_noun} history..."
        )
        self.check_btn.setEnabled(False)
        self.hero_badge.setText("CHECKING...")
        self.hero_badge.setProperty("level", "warning")
        self.result_banner.setVisible(False)
        from crapcleaner.gui.workers import WindowsUpdateWorker, stop_worker

        stop_worker(getattr(self, "_worker", None))

        worker = WindowsUpdateWorker(parent=self)
        self._worker = worker
        worker.done.connect(self._on_updates_loaded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(
            lambda: (
                setattr(self, "_worker", None) if getattr(self, "_worker", None) is worker else None
            )
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_updates_loaded(self, report: Any):
        self._report = report
        self.check_btn.setEnabled(True)

        # Backend badge - the Windows Update service, or the detected package manager.
        svc_status = report.service_status.upper()
        healthy = any(token in svc_status for token in ("RUNNING", "ACTIVE", "AVAILABLE"))
        self.service_badge.setText(svc_status)
        self.service_badge.setProperty("level", "safe" if healthy else "warning")

        # Counts & metrics
        avail = report.available_updates
        hist = report.installed_history
        total_size = sum(u.size_bytes for u in avail)
        crit_count = sum(1 for u in avail if u.severity in ("Critical", "Important"))

        if avail:
            self.hero_badge.setText(f"{len(avail)} UPDATES AVAILABLE")
            self.hero_badge.setProperty("level", "accent")
            self.install_btn.setEnabled(True)
            # Package managers do not report a download size up front.
            size_note = f" ({format_size(total_size)} total)" if total_size else ""
            self.status_label.setText(
                f"{len(avail)} {self._update_noun}(s) ready to install{size_note}."
            )
        else:
            self.hero_badge.setText("UP TO DATE")
            self.hero_badge.setProperty("level", "safe")
            self.install_btn.setEnabled(False)
            self.status_label.setText(f"System is up to date (checked {report.last_checked}).")

        if getattr(report, "reboot_required", False):
            self.status_label.setText(
                self.status_label.text() + " A reboot is pending to finish earlier updates."
            )

        self.avail_card_val.setText(str(len(avail)))
        self.size_card_val.setText(format_size(total_size))
        self.crit_card_val.setText(str(crit_count))
        self.hist_card_val.setText(str(len(hist)))

        self._populate_available(avail)
        self._populate_history(hist)

        if report.error:
            self.result_label.setText(f"{self._capability.title} Note: {report.error}")
            self.result_icon.setPixmap(
                material_icon("warning", _c(self._theme, "warning")).pixmap(18, 18)
            )
            self.result_banner.setVisible(True)
        else:
            self.result_banner.setVisible(False)

    def _on_failed(self, msg: str):
        # explain_windows_error passes non-Windows messages through untouched, so it is
        # safe to run on every platform.
        from crapcleaner.utils.windows_errors import explain_windows_error

        self.check_btn.setEnabled(True)
        explained = explain_windows_error(msg)
        self.status_label.setText(f"Failed to check updates: {explained}")
        self.result_label.setText(f"Update Check Note: {explained}")
        self.result_icon.setPixmap(
            material_icon("warning", _c(self._theme, "danger")).pixmap(18, 18)
        )
        self.result_banner.setVisible(True)

    def _populate_available(self, items: list[Any]):
        self.avail_table.setRowCount(0)
        self.avail_table.setRowCount(len(items))

        for row, item in enumerate(items):
            # Title
            t_item = QTableWidgetItem(item.title)
            t_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            if item.description:
                t_item.setToolTip(item.description)
            self.avail_table.setItem(row, 0, t_item)

            # KB
            kb_str = ", ".join(item.kb_numbers) if item.kb_numbers else "--"
            kb_item = QTableWidgetItem(kb_str)
            self.avail_table.setItem(row, 1, kb_item)

            # Severity
            sev_item = QTableWidgetItem(item.severity)
            if item.severity in ("Critical", "Important"):
                sev_item.setForeground(QColor(_c(self._theme, "danger")))
            elif item.severity == "Moderate":
                sev_item.setForeground(QColor(_c(self._theme, "warning")))
            self.avail_table.setItem(row, 2, sev_item)

            # Size
            size_str = format_size(item.size_bytes) if item.size_bytes > 0 else "Dynamic"
            s_item = QTableWidgetItem(size_str)
            self.avail_table.setItem(row, 3, s_item)

            # Category
            cat_str = ", ".join(item.categories) if item.categories else "General"
            cat_item = QTableWidgetItem(cat_str)
            cat_item.setForeground(QColor(_c(self._theme, "muted")))
            self.avail_table.setItem(row, 4, cat_item)

    def _populate_history(self, items: list[Any]):
        self.hist_table.setRowCount(0)
        self.hist_table.setRowCount(len(items))

        for row, item in enumerate(items):
            kb_item = QTableWidgetItem(item.id)
            kb_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.hist_table.setItem(row, 0, kb_item)

            desc_item = QTableWidgetItem(item.categories[0] if item.categories else item.title)
            self.hist_table.setItem(row, 1, desc_item)

            date_item = QTableWidgetItem(item.installed_on or "--")
            self.hist_table.setItem(row, 2, date_item)

            by_item = QTableWidgetItem(item.description.replace("Installed by: ", ""))
            by_item.setForeground(QColor(_c(self._theme, "muted")))
            self.hist_table.setItem(row, 3, by_item)

    def _filter_history(self):
        if not self._report:
            return
        query = self.hist_search.text().strip().lower()
        hist = self._report.installed_history
        if not query:
            self._populate_history(hist)
            return

        filtered = [
            h
            for h in hist
            if query in h.id.lower() or query in h.title.lower() or query in h.description.lower()
        ]
        self._populate_history(filtered)

    def _install_updates(self):
        # Windows needs the whole process elevated; on Linux the backend raises
        # privileges per command through pkexec instead.
        if not is_admin() and is_windows():
            QMessageBox.warning(
                self,
                "Elevation Required",
                "Administrator privileges are required to initiate Windows Update installation.\n\n"
                "Please click 'Relaunch as Admin' and try again.",
            )
            return

        ans = QMessageBox.question(
            self,
            f"Install {self._capability.title}",
            f"Do you want to download and install all pending {self._os_name} "
            f"{self._update_noun}s now?\n\nThis process may take several minutes.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        self.install_btn.setEnabled(False)
        self.status_label.setText(f"Downloading and installing {self._update_noun}s...")
        from crapcleaner.gui.workers import WindowsUpdateInstallWorker, stop_worker

        stop_worker(getattr(self, "_install_worker", None))

        worker = WindowsUpdateInstallWorker(parent=self)
        self._install_worker = worker
        worker.done.connect(self._on_install_done)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(
            lambda: (
                setattr(self, "_install_worker", None)
                if getattr(self, "_install_worker", None) is worker
                else None
            )
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_install_done(self, ok: bool, msg: str):
        self.install_btn.setEnabled(True)
        self.result_label.setText(msg)
        self.result_icon.setPixmap(
            material_icon(
                "check" if ok else "warning", _c(self._theme, "safe" if ok else "warning")
            ).pixmap(18, 18)
        )
        self.result_banner.setVisible(True)
        self.refresh()

    def _open_settings(self):
        from crapcleaner.system.system_updates import open_update_settings

        ok, msg = open_update_settings()
        if not ok:
            self.result_label.setText(msg)
            self.result_icon.setPixmap(
                material_icon("warning", _c(self._theme, "warning")).pixmap(18, 18)
            )
            self.result_banner.setVisible(True)

    def _relaunch_admin(self):
        if elevate():
            QApplication.quit()

    def closeEvent(self, event):
        from crapcleaner.gui.workers import stop_worker

        stop_worker(getattr(self, "_worker", None))
        stop_worker(getattr(self, "_install_worker", None))
        super().closeEvent(event)

    def apply_theme(self, theme: str):
        self._theme = theme
        self.hero_title.setStyleSheet(
            f"font-size: 20px; font-weight: 800; color: {_c(theme, 'text')};"
        )
        self.status_label.setStyleSheet(f"font-size: 11px; color: {_c(theme, 'muted')};")
        self.result_label.setStyleSheet(f"font-weight: 600; color: {_c(theme, 'text')};")
        if self._report:
            self._populate_available(self._report.available_updates)
            self._populate_history(self._report.installed_history)


WindowsUpdateView = SystemUpdatesView


class AppUpdatesView(QWidget):
    """Scan for app updates via installed package managers (winget, choco, apt, flatpak, snap, pacman, dnf)."""

    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._theme = "dark"
        self._results: list = []
        self._all_updates: list = []
        self._filtered: list = []
        self._worker = None
        self._update_worker = None
        self._populating = False
        self._pending_managers: list = []
        self._pending_packages: list = []
        self._update_map: dict = {}
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        from crapcleaner.system.package_managers import detect_managers

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)
        root.addWidget(
            page_header(
                "App Updates",
                "Scan for available application updates via installed package managers.",
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(14)

        # --- Hero card ---
        hero_card = QFrame()
        hero_card.setProperty("card", "true")
        hero_lay = QVBoxLayout(hero_card)
        hero_lay.setContentsMargins(18, 16, 18, 16)
        hero_lay.setSpacing(10)

        hero_top = QHBoxLayout()
        self.hero_badge = badge("NOT YET SCANNED", "muted")
        self.managers_badge = badge("DETECTING", "muted")
        self.last_check_badge = badge("NEVER CHECKED", "muted")
        hero_top.addWidget(self.hero_badge)
        hero_top.addWidget(self.managers_badge)
        hero_top.addWidget(self.last_check_badge)
        hero_top.addStretch(1)

        self.update_selected_btn = QPushButton("Update Selected")
        self.update_selected_btn.setIcon(material_icon("download", _c(self._theme, "text")))
        self.update_selected_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_selected_btn.clicked.connect(self._update_selected)
        self.update_selected_btn.setEnabled(False)

        self.update_all_btn = QPushButton("Update All")
        self.update_all_btn.setProperty("primary", "true")
        self.update_all_btn.setIcon(material_icon("system_update", "#ffffff"))
        self.update_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_all_btn.clicked.connect(self._update_all)
        self.update_all_btn.setEnabled(False)

        self.refresh_btn = QPushButton("Check for Updates")
        self.refresh_btn.setIcon(material_icon("refresh", _c(self._theme, "text")))
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh)

        hero_top.addWidget(self.update_selected_btn)
        hero_top.addWidget(self.update_all_btn)
        hero_top.addWidget(self.refresh_btn)
        hero_lay.addLayout(hero_top)

        self.status_label = QLabel("Click 'Check for Updates' to scan installed package managers.")
        self.status_label.setWordWrap(True)
        hero_lay.addWidget(self.status_label)

        detected = detect_managers()
        if detected:
            mgr_row = QHBoxLayout()
            for mgr in detected:
                mgr_row.addWidget(badge(mgr.upper(), "accent"))
            mgr_row.addStretch(1)
            hero_lay.addLayout(mgr_row)
            plural = "S" if len(detected) != 1 else ""
            self.managers_badge.setText(f"{len(detected)} MANAGER{plural}")
        else:
            self.managers_badge.setText("NO MANAGERS FOUND")

        layout.addWidget(hero_card)

        # --- Result banner ---
        self.result_banner = QFrame()
        self.result_banner.setProperty("infoCard", "true")
        result_lay = QHBoxLayout(self.result_banner)
        result_lay.setContentsMargins(14, 10, 14, 10)
        self.result_icon = QLabel()
        self.result_icon.setPixmap(material_icon("check", _c(self._theme, "safe")).pixmap(18, 18))
        self.result_label = QLabel()
        self.result_label.setWordWrap(True)
        result_lay.addWidget(self.result_icon)
        result_lay.addWidget(self.result_label, 1)
        dismiss_btn = QPushButton()
        dismiss_btn.setAccessibleName("Dismiss")
        dismiss_btn.setToolTip("Dismiss this message")
        dismiss_btn.setIcon(material_icon("close", _c(self._theme, "muted")))
        dismiss_btn.setFlat(True)
        dismiss_btn.setFixedSize(22, 22)
        dismiss_btn.clicked.connect(lambda: self.result_banner.setVisible(False))
        result_lay.addWidget(dismiss_btn)
        self.result_banner.setVisible(False)
        layout.addWidget(self.result_banner)

        # --- Filter bar ---
        filter_card = QFrame()
        filter_card.setProperty("card", "true")
        f_lay = QHBoxLayout(filter_card)
        f_lay.setContentsMargins(12, 8, 12, 8)
        f_lay.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search packages...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter)
        f_lay.addWidget(self.search_input, 1)

        self.mgr_combo = QComboBox()
        self.mgr_combo.addItem("All Managers")
        self.mgr_combo.currentIndexChanged.connect(self._filter)
        f_lay.addWidget(self.mgr_combo)

        layout.addWidget(filter_card)

        # --- Updates table ---
        # Source is folded into the Manager column: for winget/choco/snap the two
        # always match, and a dedicated column just repeats itself down the view.
        self.table = CrapTable(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Package", "Current Version", "Available Version", "Manager"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table.setMinimumHeight(320)
        # Stretch factor, not addStretch(): the table should absorb the spare
        # height instead of being pinned to its minimum with dead space below.
        layout.addWidget(self.table, 1)

        scroll.setWidget(container)
        root.addWidget(scroll)

    # ------------------------------------------------------------------
    # Refresh / data loading
    # ------------------------------------------------------------------

    def refresh(self):
        self.status_label.setText("Scanning package managers for available updates...")
        self.refresh_btn.setEnabled(False)
        self.update_all_btn.setEnabled(False)
        self.update_selected_btn.setEnabled(False)
        self.hero_badge.setText("SCANNING...")
        self.result_banner.setVisible(False)

        from crapcleaner.gui.workers import PackageManagerWorker, stop_worker

        stop_worker(getattr(self, "_worker", None))

        worker = PackageManagerWorker(force_refresh=True, parent=self)
        self._worker = worker
        worker.done.connect(self._on_results)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(
            lambda: (
                setattr(self, "_worker", None) if getattr(self, "_worker", None) is worker else None
            )
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_results(self, results: list):
        import datetime

        self._results = results
        self._all_updates = [u for r in results for u in r.updates]
        self.refresh_btn.setEnabled(True)

        total = len(self._all_updates)
        managers_with_updates = [r.manager for r in results if r.updates]
        errors = [r for r in results if r.error]

        self.hero_badge.setText(f"{total} UPDATES" if total else "UP TO DATE")
        ts = datetime.datetime.now().strftime("%H:%M")
        self.last_check_badge.setText(f"CHECKED AT {ts}")
        self.update_all_btn.setEnabled(total > 0)

        # Repopulate manager combo
        self.mgr_combo.blockSignals(True)
        self.mgr_combo.clear()
        self.mgr_combo.addItem("All Managers")
        seen: list = []
        for u in self._all_updates:
            if u.manager not in seen:
                seen.append(u.manager)
                self.mgr_combo.addItem(u.manager)
        self.mgr_combo.blockSignals(False)

        if total:
            mgrs = len(managers_with_updates)
            err_suffix = (
                f" ({len(errors)} manager error{'s' if len(errors) != 1 else ''})" if errors else ""
            )
            self.status_label.setText(
                f"{total} update{'s' if total != 1 else ''} available across "
                f"{mgrs} manager{'s' if mgrs != 1 else ''}.{err_suffix}"
            )
        elif errors:
            err_msgs = "; ".join(r.error for r in errors if r.error)
            self.status_label.setText(f"All managers scanned. Some errors: {err_msgs}")
        else:
            self.status_label.setText("All packages are up to date.")

        self._filter()

    def _on_failed(self, msg: str):
        self._pending_packages = []
        self._pending_managers = []
        self.refresh_btn.setEnabled(True)
        self.update_all_btn.setEnabled(False)
        self.update_selected_btn.setEnabled(False)
        self.status_label.setText(f"Failed to scan: {msg}")
        self.hero_badge.setText("ERROR")

    def _filter(self):
        query = self.search_input.text().strip().lower()
        mgr_filter = self.mgr_combo.currentText()
        filtered = []
        for u in self._all_updates:
            if query and query not in u.name.lower() and query not in u.id.lower():
                continue
            if mgr_filter != "All Managers" and u.manager != mgr_filter:
                continue
            filtered.append(u)
        self._filtered = filtered
        self._populate_table(filtered)

    # ------------------------------------------------------------------
    # Table
    # ------------------------------------------------------------------

    def _populate_table(self, updates: list):
        self._update_map = {(u.manager, u.id): u for u in updates}

        self._populating = True
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.table.setRowCount(len(updates))

        for row, u in enumerate(updates):
            # Package name
            name_item = QTableWidgetItem(u.name)
            name_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            name_item.setToolTip(f"Package ID: {u.id}")
            name_item.setData(Qt.ItemDataRole.UserRole, (u.manager, u.id))
            self.table.setItem(row, 0, name_item)

            # Current version
            cur_item = QTableWidgetItem(u.current_version or "\u2014")
            cur_item.setForeground(QColor(_c(self._theme, "muted")))
            self.table.setItem(row, 1, cur_item)

            # Available version (highlighted)
            av_item = QTableWidgetItem(u.available_version)
            av_item.setForeground(QColor(_c(self._theme, "safe")))
            av_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.table.setItem(row, 2, av_item)

            # Manager (with the source appended only when it adds information)
            label = u.manager
            if u.source and u.source.lower() != u.manager.lower():
                label = f"{u.manager} \u00b7 {u.source}"
            mgr_item = QTableWidgetItem(label)
            mgr_item.setForeground(QColor(_c(self._theme, "accent")))
            self.table.setItem(row, 3, mgr_item)

        self.table.setSortingEnabled(True)
        self._populating = False
        self._on_selection_changed()

    def _update_for_row(self, row: int):
        cell = self.table.item(row, 0)
        if cell:
            key = cell.data(Qt.ItemDataRole.UserRole)
            if key:
                return self._update_map.get(key)
        return None

    def _selected_updates(self) -> list:
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        return [u for u in (self._update_for_row(row) for row in rows) if u]

    def _on_selection_changed(self):
        if self._populating:
            return
        count = len(self._selected_updates())
        busy = self._update_worker is not None
        self.update_selected_btn.setEnabled(count > 0 and not busy)
        self.update_selected_btn.setText(
            f"Update Selected ({count})" if count else "Update Selected"
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_double_click(self, table_item):
        if self._populating:
            return
        u = self._update_for_row(table_item.row())
        if u:
            self._update_package(u)

    def _update_package(self, u):
        ans = QMessageBox.question(
            self,
            "Update Package",
            f"Update  {u.name}  \u2192  {u.available_version}  via  {u.manager}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        self._run_update(manager=u.manager, pkg_id=u.id, update_all=False)

    def _update_selected(self):
        selected = self._selected_updates()
        if not selected:
            return
        preview = "\n".join(f"  • {u.name}  →  {u.available_version}" for u in selected[:10])
        if len(selected) > 10:
            preview += f"\n  … and {len(selected) - 10} more"
        ans = QMessageBox.question(
            self,
            "Update Selected Packages",
            f"Update {len(selected)} package{'s' if len(selected) != 1 else ''}?\n\n{preview}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        self._pending_packages = list(selected[1:])
        first = selected[0]
        self._run_update(manager=first.manager, pkg_id=first.id, update_all=False)

    def _update_all(self):
        managers = list(dict.fromkeys(u.manager for u in self._all_updates))
        if not managers:
            return
        ans = QMessageBox.question(
            self,
            "Update All Packages",
            f"Update all available packages via: {', '.join(managers)}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        self._pending_managers = managers[1:]
        self._run_update(manager=managers[0], update_all=True)

    def _run_update(self, manager: str, pkg_id: str = "", update_all: bool = False):
        from crapcleaner.gui.workers import PackageUpdateWorker, stop_worker

        stop_worker(getattr(self, "_update_worker", None))

        desc = "all packages" if update_all else pkg_id
        remaining = len(self._pending_packages)
        queue_suffix = f" ({remaining} more queued)" if remaining else ""
        self.status_label.setText(f"Updating {desc} via {manager}...{queue_suffix}")
        self.update_all_btn.setEnabled(False)
        self.update_selected_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)

        worker = PackageUpdateWorker(
            manager=manager, pkg_id=pkg_id, update_all=update_all, parent=self
        )
        self._update_worker = worker
        worker.done.connect(self._on_update_done)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(
            lambda: (
                setattr(self, "_update_worker", None)
                if getattr(self, "_update_worker", None) is worker
                else None
            )
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_update_done(self, ok: bool, msg: str):
        self.result_icon.setPixmap(
            material_icon(
                "check" if ok else "warning", _c(self._theme, "safe" if ok else "warning")
            ).pixmap(18, 18)
        )
        self.result_label.setText(msg)
        self.result_banner.setVisible(True)

        # Drain the "Update Selected" queue. A failed package does not stop the
        # rest - one broken installer should not strand the other selections.
        if self._pending_packages:
            nxt = self._pending_packages.pop(0)
            self._run_update(manager=nxt.manager, pkg_id=nxt.id, update_all=False)
            return

        # Chain remaining managers when doing "Update All"
        pending = getattr(self, "_pending_managers", [])
        if ok and pending:
            self._pending_managers = pending[1:]
            self._run_update(manager=pending[0], update_all=True)
            return

        self._pending_managers = []
        self.refresh()

    def _context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        u = self._update_for_row(row)
        if not u:
            return

        menu = QMenu(self)
        upd_act = menu.addAction(f"Update {u.name}")
        upd_act.triggered.connect(lambda: self._update_package(u))
        menu.addSeparator()
        copy_id = menu.addAction("Copy Package ID")
        copy_id.triggered.connect(lambda: QApplication.clipboard().setText(u.id))
        copy_ver = menu.addAction("Copy Available Version")
        copy_ver.triggered.connect(lambda: QApplication.clipboard().setText(u.available_version))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        from crapcleaner.gui.workers import stop_worker

        stop_worker(getattr(self, "_worker", None))
        stop_worker(getattr(self, "_update_worker", None))
        super().closeEvent(event)

    def apply_theme(self, theme: str):
        self._theme = theme
        self.status_label.setStyleSheet(f"font-size: 11px; color: {_c(theme, 'muted')}")
        self.result_label.setStyleSheet(f"font-weight: 600; color: {_c(theme, 'text')}")
        if self._filtered:
            self._populate_table(self._filtered)
