"""Windows/systemd service manager view."""

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
from crapcleaner.gui.views.common import CrapTable, _c, badge, page_header, stat_card
from crapcleaner.system.capabilities import (
    SERVICES,
    get_capability,
)
from crapcleaner.system.services import startup_types as service_startup_types
from crapcleaner.utils.platform import (
    elevate,
    is_admin,
    is_windows,
)


class ServicesView(QWidget):
    """View, control, and configure background services.

    Drives Windows services or systemd units depending on the platform; the wording
    and the available startup types both come from the capability registry and the
    service dispatcher rather than being hard-coded here.
    """

    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._theme = "dark"
        self._services: list[Any] = []
        self._filtered_services: list[Any] = []
        self._worker = None
        self._action_worker = None
        self._capability = get_capability(SERVICES)
        self._unit_noun = self._capability.terms.get("unit_noun", "service")
        self._unit_plural = self._capability.terms.get("unit_noun_plural", "services")
        self._os_name = self._capability.terms.get("os_name", "system")
        self._startup_types = list(service_startup_types()) or ["Automatic", "Manual", "Disabled"]
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

        self.hero_card = QFrame()
        self.hero_card.setProperty("card", "true")
        hero_lay = QVBoxLayout(self.hero_card)
        hero_lay.setContentsMargins(18, 16, 18, 16)
        hero_lay.setSpacing(10)

        hero_top = QHBoxLayout()
        self.hero_badge = badge("0 SERVICES", "accent")
        self.running_badge = badge("0 RUNNING", "safe")
        self.stopped_badge = badge("0 STOPPED", "muted")
        self.elevated_badge = badge(
            "ELEVATED (ADMIN)" if is_admin() else "STANDARD USER",
            "safe" if is_admin() else "muted",
        )
        hero_top.addWidget(self.hero_badge)
        hero_top.addWidget(self.running_badge)
        hero_top.addWidget(self.stopped_badge)
        hero_top.addWidget(self.elevated_badge)
        hero_top.addStretch(1)

        if not is_admin() and is_windows():
            self.elevate_btn = QPushButton("Relaunch as Admin")
            self.elevate_btn.setProperty("secondary", "true")
            self.elevate_btn.setIcon(material_icon("security", _c(self._theme, "accent")))
            self.elevate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.elevate_btn.clicked.connect(self._relaunch_admin)
            hero_top.addWidget(self.elevate_btn)

        self.services_msc_btn = QPushButton(
            self._capability.terms.get("console_label", "Open Service Manager")
        )
        self.services_msc_btn.setIcon(material_icon("tune", _c(self._theme, "text")))
        self.services_msc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.services_msc_btn.clicked.connect(self._open_services_msc)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(material_icon("refresh", _c(self._theme, "text")))
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh)

        hero_top.addWidget(self.services_msc_btn)
        hero_top.addWidget(self.refresh_btn)
        hero_lay.addLayout(hero_top)

        self.hero_title = QLabel("Services Manager")
        self.hero_title.setStyleSheet(
            f"font-size: 20px; font-weight: 800; color: {_c(self._theme, 'text')};"
        )
        hero_lay.addWidget(self.hero_title)

        self.status_label = QLabel("Ready")
        self.status_label.setProperty("subtle", "true")
        self.status_label.setStyleSheet(f"font-size: 11px; color: {_c(self._theme, 'muted')};")
        hero_lay.addWidget(self.status_label)

        self.result_banner = QFrame()
        self.result_banner.setProperty("card", "true")
        self.result_banner.setVisible(False)
        rb_lay = QHBoxLayout(self.result_banner)
        rb_lay.setContentsMargins(12, 8, 12, 8)
        self.result_icon = QLabel()
        self.result_icon.setPixmap(material_icon("check", _c(self._theme, "safe")).pixmap(18, 18))
        self.result_label = QLabel("")
        self.result_label.setStyleSheet(f"font-weight: 600; color: {_c(self._theme, 'text')};")
        self.result_label.setWordWrap(True)
        rb_lay.addWidget(self.result_icon)
        rb_lay.addWidget(self.result_label, 1)
        hero_lay.addWidget(self.result_banner)

        layout.addWidget(self.hero_card)

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(12)
        c1, self.total_card_val, self.total_card_sub = stat_card(
            "TOTAL SERVICES", "0", "Installed services", self._theme
        )
        c2, self.running_card_val, self.running_card_sub = stat_card(
            "RUNNING", "0", "Active processes", self._theme
        )
        c3, self.stopped_card_val, self.stopped_card_sub = stat_card(
            "STOPPED", "0", "Inactive", self._theme
        )
        c4, self.disabled_card_val, self.disabled_card_sub = stat_card(
            "DISABLED", "0", "Cannot start", self._theme
        )
        for c in (c1, c2, c3, c4):
            metrics_row.addWidget(c)
        layout.addLayout(metrics_row)

        filter_card = QFrame()
        filter_card.setProperty("card", "true")
        f_lay = QHBoxLayout(filter_card)
        f_lay.setContentsMargins(14, 10, 14, 10)
        f_lay.setSpacing(10)

        search_icon = QLabel()
        search_icon.setPixmap(material_icon("search", _c(self._theme, "muted")).pixmap(16, 16))
        f_lay.addWidget(search_icon)

        self.search_input = QLineEdit()
        self.search_input.setAccessibleName("Search services")
        self.search_input.setPlaceholderText(
            f"Search {self._unit_plural} by display name, {self._unit_noun} name, or description..."
        )
        self.search_input.textChanged.connect(self._filter_services)
        f_lay.addWidget(self.search_input, 2)

        self.status_combo = QComboBox()
        self.status_combo.setAccessibleName("Filter by service status")
        self.status_combo.addItems(["All Status", "Running Only", "Stopped Only"])
        self.status_combo.currentIndexChanged.connect(self._filter_services)
        f_lay.addWidget(self.status_combo)

        self.startup_combo = QComboBox()
        self.startup_combo.setAccessibleName("Filter by startup type")
        # Startup types differ per platform - systemd has no delayed-start mode.
        self.startup_combo.addItems(["All Startup Types"] + self._startup_types)
        self.startup_combo.currentIndexChanged.connect(self._filter_services)
        f_lay.addWidget(self.startup_combo)

        self.type_combo = QComboBox()
        self.type_combo.setAccessibleName("Filter by service kind")
        self.type_combo.addItems(
            [
                f"All {self._unit_plural.title()}",
                "Third-Party Only",
                f"System {self._unit_plural.title()}",
            ]
        )
        self.type_combo.currentIndexChanged.connect(self._filter_services)
        f_lay.addWidget(self.type_combo)

        layout.addWidget(filter_card)

        self.table = CrapTable(0, 6)
        self.table.setAccessibleName("System services")
        self.table.setHorizontalHeaderLabels(
            [
                "Display Name",
                "Service Name",
                "Status",
                "Startup Type",
                "Log On As",
                "Description",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.setSortingEnabled(True)
        self.table.setMinimumHeight(380)
        layout.addWidget(self.table)

        scroll.setWidget(container)
        root.addWidget(scroll)

    def refresh(self):
        self.status_label.setText(f"Reading {self._os_name} {self._unit_plural}...")
        self.refresh_btn.setEnabled(False)
        from crapcleaner.gui.workers import ServicesWorker, stop_worker

        stop_worker(getattr(self, "_worker", None))

        worker = ServicesWorker(parent=self)
        self._worker = worker
        worker.done.connect(self._on_services_loaded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(
            lambda: (
                setattr(self, "_worker", None) if getattr(self, "_worker", None) is worker else None
            )
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_services_loaded(self, items: list[Any]):
        self._services = items
        self.refresh_btn.setEnabled(True)

        total = len(items)
        running = sum(1 for s in items if s.status == "Running")
        stopped = sum(1 for s in items if s.status == "Stopped")
        disabled = sum(1 for s in items if "Disabled" in s.startup_type)

        self.hero_badge.setText(f"{total} {self._unit_plural.upper()}")
        self.running_badge.setText(f"{running} RUNNING")
        self.stopped_badge.setText(f"{stopped} STOPPED")

        self.total_card_val.setText(str(total))
        self.running_card_val.setText(str(running))
        self.stopped_card_val.setText(str(stopped))
        self.disabled_card_val.setText(str(disabled))

        self.status_label.setText(
            f"Loaded {total} {self._unit_plural} ({running} running, {stopped} stopped, {disabled} disabled)."
        )
        self._filter_services()

    def _on_failed(self, msg: str):
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"Failed to load {self._unit_plural}: {msg}")

    def _filter_services(self):
        query = self.search_input.text().strip().lower()
        status_filter = self.status_combo.currentText()
        startup_filter = self.startup_combo.currentText()
        type_filter = self.type_combo.currentText()

        filtered = []
        for s in self._services:
            if query:
                match = (
                    query in s.display_name.lower()
                    or query in s.name.lower()
                    or query in s.description.lower()
                    or query in s.account.lower()
                )
                if not match:
                    continue

            if status_filter == "Running Only" and s.status != "Running":
                continue
            if status_filter == "Stopped Only" and s.status != "Stopped":
                continue

            # The combo is filled from the platform's own startup types, so a prefix
            # match covers every one of them.
            if startup_filter != "All Startup Types" and startup_filter not in s.startup_type:
                continue

            if type_filter == "Third-Party Only" and s.is_system:
                continue
            if type_filter.startswith("System ") and not s.is_system:
                continue

            filtered.append(s)

        self._filtered_services = filtered
        self._populate_table(filtered)

    def _populate_table(self, items: list[Any]):
        # name -> service map: sorting reorders the rows, so look up by name.
        self._svc_map: dict[str, Any] = {s.name: s for s in items}

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.table.setRowCount(len(items))

        for row, s in enumerate(items):
            d_item = QTableWidgetItem(s.display_name)
            d_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            if s.description:
                d_item.setToolTip(s.description)
            d_item.setData(Qt.ItemDataRole.UserRole, s.name)
            self.table.setItem(row, 0, d_item)

            n_item = QTableWidgetItem(s.name)
            n_item.setForeground(QColor(_c(self._theme, "muted")))
            n_item.setData(Qt.ItemDataRole.UserRole, s.name)
            self.table.setItem(row, 1, n_item)

            st_item = QTableWidgetItem(s.status)
            if s.status == "Running":
                st_item.setForeground(QColor(_c(self._theme, "safe")))
            elif s.status == "Stopped":
                st_item.setForeground(QColor(_c(self._theme, "muted")))
            elif s.status == "Paused":
                st_item.setForeground(QColor(_c(self._theme, "warning")))
            self.table.setItem(row, 2, st_item)

            su_item = QTableWidgetItem(s.startup_type)
            if "Disabled" in s.startup_type:
                su_item.setForeground(QColor(_c(self._theme, "danger")))
            elif "Automatic" in s.startup_type:
                su_item.setForeground(QColor(_c(self._theme, "safe")))
            self.table.setItem(row, 3, su_item)

            acc_item = QTableWidgetItem(s.account)
            acc_item.setForeground(QColor(_c(self._theme, "faint")))
            self.table.setItem(row, 4, acc_item)

            desc_item = QTableWidgetItem(s.description)
            desc_item.setForeground(QColor(_c(self._theme, "muted")))
            self.table.setItem(row, 5, desc_item)

        self.table.setSortingEnabled(True)

    def _svc_for_row(self, row: int) -> Any:
        """Return the ServiceItem for the given (possibly sorted) table row."""
        for col in (1, 0):
            cell = self.table.item(row, col)
            if cell:
                svc_name = cell.data(Qt.ItemDataRole.UserRole)
                if svc_name and hasattr(self, "_svc_map"):
                    return self._svc_map.get(svc_name)
        return None

    def _start_service(self, name: str):
        self._run_service_action("start", name)

    def _stop_service(self, name: str):
        from crapcleaner.system.services import is_critical_service

        if is_critical_service(name):
            QMessageBox.critical(
                self,
                f"Critical System {self._unit_noun.title()}",
                f"'{name}' is a critical {self._os_name} operating system component.\n\n"
                f"Stopping this {self._unit_noun} may destabilize or crash your computer.",
            )
            return

        ans = QMessageBox.question(
            self,
            f"Stop {self._unit_noun.title()}",
            f"Are you sure you want to stop {self._unit_noun} '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        self._run_service_action("stop", name)

    def _restart_service(self, name: str):
        self._run_service_action("restart", name)

    def _set_startup_type(self, name: str, startup_type: str):
        from crapcleaner.system.services import is_critical_service

        if is_critical_service(name) and startup_type == "Disabled":
            QMessageBox.critical(
                self,
                f"Critical System {self._unit_noun.title()}",
                f"'{name}' is required by {self._os_name} and cannot be disabled.",
            )
            return

        if startup_type == "Disabled":
            ans = QMessageBox.question(
                self,
                f"Disable {self._unit_noun.title()}",
                f"Are you sure you want to disable {self._unit_noun} '{name}'?\n\n"
                f"Disabled {self._unit_plural} cannot start until their startup type is changed.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

        self._run_service_action("startup_type", name, startup_type=startup_type)

    def _run_service_action(self, action: str, service_name: str, startup_type: str = ""):
        # On Linux the backend elevates per action through pkexec, so the whole
        # application does not need to be running as root to get this far.
        if not is_admin() and is_windows():
            QMessageBox.warning(
                self,
                "Administrator Elevation Required",
                f"Administrator privileges are required to modify service '{service_name}'.\n\n"
                "Please click 'Relaunch as Admin' and try again.",
            )
            return

        from crapcleaner.gui.workers import ServiceActionWorker, stop_worker

        stop_worker(getattr(self, "_action_worker", None))

        worker = ServiceActionWorker(action, service_name, startup_type=startup_type, parent=self)
        self._action_worker = worker
        worker.done.connect(self._on_action_done)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(
            lambda: (
                setattr(self, "_action_worker", None)
                if getattr(self, "_action_worker", None) is worker
                else None
            )
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_action_done(self, ok: bool, msg: str):
        self.result_label.setText(msg)
        self.result_icon.setPixmap(
            material_icon(
                "check" if ok else "warning", _c(self._theme, "safe" if ok else "warning")
            ).pixmap(18, 18)
        )
        self.result_banner.setVisible(True)
        if ok:
            self.refresh()

    def _open_services_msc(self):
        from crapcleaner.system.services import open_services_console

        ok, msg = open_services_console()
        if not ok:
            self.result_label.setText(msg)
            self.result_icon.setPixmap(
                material_icon("warning", _c(self._theme, "warning")).pixmap(18, 18)
            )
            self.result_banner.setVisible(True)

    def _relaunch_admin(self):
        if elevate():
            QApplication.quit()

    def _context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        svc = self._svc_for_row(row)
        if not svc:
            return

        noun = self._unit_noun.title()
        menu = QMenu(self)
        if svc.status != "Running":
            start_act = menu.addAction(f"Start {noun}")
            start_act.triggered.connect(lambda: self._start_service(svc.name))
        else:
            stop_act = menu.addAction(f"Stop {noun}")
            stop_act.triggered.connect(lambda: self._stop_service(svc.name))
            restart_act = menu.addAction(f"Restart {noun}")
            restart_act.triggered.connect(lambda: self._restart_service(svc.name))

        menu.addSeparator()
        st_menu = menu.addMenu("Set Startup Type")
        for startup_type in self._startup_types:
            action = st_menu.addAction(startup_type)
            action.triggered.connect(
                lambda _=False, st=startup_type: self._set_startup_type(svc.name, st)
            )

        menu.addSeparator()
        copy_act = menu.addAction(f"Copy {noun} Name")
        copy_act.triggered.connect(lambda: QApplication.clipboard().setText(svc.name))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def closeEvent(self, event):
        from crapcleaner.gui.workers import stop_worker

        stop_worker(getattr(self, "_worker", None))
        stop_worker(getattr(self, "_action_worker", None))
        super().closeEvent(event)

    def apply_theme(self, theme: str):
        self._theme = theme
        self.hero_title.setStyleSheet(
            f"font-size: 20px; font-weight: 800; color: {_c(theme, 'text')};"
        )
        self.status_label.setStyleSheet(f"font-size: 11px; color: {_c(theme, 'muted')};")
        self.result_label.setStyleSheet(f"font-weight: 600; color: {_c(theme, 'text')};")
        if self._filtered_services:
            self._populate_table(self._filtered_services)
