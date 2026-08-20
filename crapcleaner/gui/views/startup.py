"""Startup program manager view."""

import os
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
    QDialog,
    QFileDialog,
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
from crapcleaner.gui.views.common import CrapTable, NumericItem, _c, badge, page_header, stat_card
from crapcleaner.system.capabilities import (
    STARTUP,
    get_capability,
)
from crapcleaner.utils.files import file_manager_name, reveal_in_file_manager
from crapcleaner.utils.platform import (
    elevate,
    is_admin,
    is_windows,
)


class AddStartupDialog(QDialog):
    """Modal dialog to add a new application to Windows Startup."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Startup Application")
        self.resize(500, 240)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)

        title = QLabel("Add New Startup Application")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        lay.addWidget(title)

        desc = QLabel("Specify the application name, executable path, and target user scope.")
        desc.setProperty("subtle", "true")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        name_row = QHBoxLayout()
        name_lbl = QLabel("App Name:")
        name_lbl.setFixedWidth(80)
        self.name_input = QLineEdit()
        self.name_input.setAccessibleName("Startup entry name")
        self.name_input.setPlaceholderText("e.g. My Utility")
        name_row.addWidget(name_lbl)
        name_row.addWidget(self.name_input)
        lay.addLayout(name_row)

        path_row = QHBoxLayout()
        path_lbl = QLabel("Executable:")
        path_lbl.setFixedWidth(80)
        self.path_input = QLineEdit()
        self.path_input.setAccessibleName("Program to run at startup")
        self.path_input.setPlaceholderText(r"e.g. C:\Program Files\App\app.exe")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        path_row.addWidget(path_lbl)
        path_row.addWidget(self.path_input)
        path_row.addWidget(browse_btn)
        lay.addLayout(path_row)

        scope_row = QHBoxLayout()
        scope_lbl = QLabel("Scope:")
        scope_lbl.setFixedWidth(80)
        self.scope_combo = QComboBox()
        self.scope_combo.setAccessibleName("Where the entry is registered")
        self.scope_combo.addItems(
            ["Current User (User Registry)", "All Users (System Registry - Admin Required)"]
        )
        scope_row.addWidget(scope_lbl)
        scope_row.addWidget(self.scope_combo)
        lay.addLayout(scope_row)

        lay.addStretch(1)

        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        add_btn = QPushButton("Add to Startup")
        add_btn.setProperty("primary", "true")
        add_btn.clicked.connect(self._validate_and_accept)
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(add_btn)
        lay.addLayout(btn_box)

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Executable or Shortcut",
            "",
            "Executable / Script (*.exe *.bat *.cmd *.vbs *.lnk);;All Files (*.*)",
        )
        if file_path:
            self.path_input.setText(file_path)
            if not self.name_input.text():
                base = os.path.splitext(os.path.basename(file_path))[0]
                self.name_input.setText(base.capitalize())

    def _validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Invalid Input", "Please enter an application name.")
            return
        if not self.path_input.text().strip():
            QMessageBox.warning(self, "Invalid Input", "Please specify an executable path.")
            return
        self.accept()

    def get_data(self) -> tuple[str, str, str]:
        scope = "SYSTEM" if "All Users" in self.scope_combo.currentText() else "USER"
        return self.name_input.text().strip(), self.path_input.text().strip(), scope


class StartupView(QWidget):
    """View and manage applications configured to start automatically at login.

    Wording comes from the capability registry, so the page describes registry Run
    keys on Windows and XDG autostart entries on Linux without branching here.
    """

    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._theme = "dark"
        self._items: list[Any] = []
        self._filtered_items: list[Any] = []
        self._worker = None
        self._action_worker = None
        self._capability = get_capability(STARTUP)
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
        self.hero_badge = badge("0 APPS", "accent")
        self.enabled_badge = badge("0 ENABLED", "safe")
        self.disabled_badge = badge("0 DISABLED", "muted")
        self.elevated_badge = badge(
            "ELEVATED (ADMIN)" if is_admin() else "STANDARD USER",
            "safe" if is_admin() else "muted",
        )
        hero_top.addWidget(self.hero_badge)
        hero_top.addWidget(self.enabled_badge)
        hero_top.addWidget(self.disabled_badge)
        hero_top.addWidget(self.elevated_badge)
        hero_top.addStretch(1)

        if not is_admin() and is_windows():
            self.elevate_btn = QPushButton("Relaunch as Admin")
            self.elevate_btn.setProperty("secondary", "true")
            self.elevate_btn.setIcon(material_icon("security", _c(self._theme, "accent")))
            self.elevate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.elevate_btn.clicked.connect(self._relaunch_admin)
            hero_top.addWidget(self.elevate_btn)

        self.add_btn = QPushButton("Add Startup App")
        self.add_btn.setProperty("primary", "true")
        self.add_btn.setIcon(material_icon("add", "#ffffff"))
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self._add_item)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(material_icon("refresh", _c(self._theme, "text")))
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh)

        hero_top.addWidget(self.add_btn)
        hero_top.addWidget(self.refresh_btn)
        hero_lay.addLayout(hero_top)

        self.hero_title = QLabel("Startup Applications")
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
            "TOTAL STARTUP", "0", "Configured entries", self._theme
        )
        c2, self.enabled_card_val, self.enabled_card_sub = stat_card(
            "ENABLED", "0", "Launch on boot", self._theme
        )
        c3, self.disabled_card_val, self.disabled_card_sub = stat_card(
            "DISABLED", "0", "Bypassed by system", self._theme
        )
        c4, self.impact_card_val, self.impact_card_sub = stat_card(
            "HIGH IMPACT", "0", "Resource heavy", self._theme
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
        self.search_input.setAccessibleName("Search startup applications")
        self.search_input.setPlaceholderText(
            "Search startup apps by name, publisher, location, or command..."
        )
        self.search_input.textChanged.connect(self._filter_items)
        f_lay.addWidget(self.search_input, 2)

        self.scope_combo = QComboBox()
        self.scope_combo.setAccessibleName("Filter by scope")
        self.scope_combo.addItems(
            ["All Scopes", "Current User (HKCU)", "All Users (HKLM)", "Startup Folders"]
        )
        self.scope_combo.currentIndexChanged.connect(self._filter_items)
        f_lay.addWidget(self.scope_combo)

        self.state_combo = QComboBox()
        self.state_combo.setAccessibleName("Filter by enabled state")
        self.state_combo.addItems(["All States", "Enabled Only", "Disabled Only"])
        self.state_combo.currentIndexChanged.connect(self._filter_items)
        f_lay.addWidget(self.state_combo)

        layout.addWidget(filter_card)

        self._populating = False  # Guard against reentrant itemClicked during sort
        self.table = CrapTable(0, 6)
        self.table.setAccessibleName("Startup applications")
        self.table.setHorizontalHeaderLabels(
            [
                "State",
                "Application",
                "Publisher",
                "Location",
                "Impact",
                "Command Line",
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
        self.table.itemClicked.connect(self._on_table_item_clicked)
        self.table.itemDoubleClicked.connect(self._on_table_double_clicked)
        self.table.setSortingEnabled(True)
        self.table.setMinimumHeight(350)
        layout.addWidget(self.table)

        scroll.setWidget(container)
        root.addWidget(scroll)

    def refresh(self):
        self.status_label.setText("Scanning startup configuration...")
        self.refresh_btn.setEnabled(False)
        from crapcleaner.gui.workers import StartupWorker, stop_worker

        stop_worker(getattr(self, "_worker", None))

        worker = StartupWorker(parent=self)
        self._worker = worker
        worker.done.connect(self._on_startup_loaded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(
            lambda: (
                setattr(self, "_worker", None) if getattr(self, "_worker", None) is worker else None
            )
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_startup_loaded(self, items: list[Any]):
        self._items = items
        self.refresh_btn.setEnabled(True)
        total = len(items)
        enabled = sum(1 for i in items if i.enabled)
        disabled = total - enabled
        high_impact = sum(1 for i in items if i.impact == "High")

        self.hero_badge.setText(f"{total} APPS")
        self.enabled_badge.setText(f"{enabled} ENABLED")
        self.disabled_badge.setText(f"{disabled} DISABLED")
        self.total_card_val.setText(str(total))
        self.enabled_card_val.setText(str(enabled))
        self.disabled_card_val.setText(str(disabled))
        self.impact_card_val.setText(str(high_impact))

        self.status_label.setText(
            f"Loaded {total} startup items ({enabled} enabled, {disabled} disabled)."
        )
        self._filter_items()

    def _on_failed(self, msg: str):
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"Failed to load startup items: {msg}")

    def _filter_items(self):
        query = self.search_input.text().strip().lower()
        scope_filter = self.scope_combo.currentText()
        state_filter = self.state_combo.currentText()

        filtered = []
        for item in self._items:
            if query:
                match = (
                    query in item.name.lower()
                    or query in item.publisher.lower()
                    or query in item.location.lower()
                    or query in item.command.lower()
                )
                if not match:
                    continue

            if "HKCU" in scope_filter and "HKCU" not in item.location_key:
                continue
            if "HKLM" in scope_filter and "HKLM" not in item.location_key:
                continue
            if "Startup Folders" in scope_filter and "STARTUP" not in item.location_key:
                continue

            if state_filter == "Enabled Only" and not item.enabled:
                continue
            if state_filter == "Disabled Only" and item.enabled:
                continue

            filtered.append(item)

        self._filtered_items = filtered
        self._populate_table(filtered)

    def _populate_table(self, items: list[Any]):
        def _impact_rank(impact: str) -> int:
            return {"High": 3, "Medium": 2, "Low": 1}.get(impact, 0)

        # id -> item map: sorting reorders the rows, so look up by id.
        self._item_map: dict[str, Any] = {it.id: it for it in items}

        self._populating = True
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            state_item = NumericItem(
                "Enabled" if item.enabled else "Disabled", value=1 if item.enabled else 0
            )
            state_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            state_item.setCheckState(
                Qt.CheckState.Checked if item.enabled else Qt.CheckState.Unchecked
            )
            if item.enabled:
                state_item.setForeground(QColor(_c(self._theme, "safe")))
            else:
                state_item.setForeground(QColor(_c(self._theme, "muted")))
            # A plain string in UserRole is safe across every Qt version.
            state_item.setData(Qt.ItemDataRole.UserRole, item.id)
            self.table.setItem(row, 0, state_item)

            name_item = QTableWidgetItem(item.name)
            name_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            if not item.file_exists:
                name_item.setToolTip(f"File not found on disk: {item.file_path}")
            name_item.setData(Qt.ItemDataRole.UserRole, item.id)
            self.table.setItem(row, 1, name_item)

            pub_item = QTableWidgetItem(item.publisher)
            pub_item.setForeground(QColor(_c(self._theme, "muted")))
            self.table.setItem(row, 2, pub_item)

            loc_item = QTableWidgetItem(item.location)
            self.table.setItem(row, 3, loc_item)

            impact_item = NumericItem(item.impact, value=_impact_rank(item.impact))
            if item.impact == "High":
                impact_item.setForeground(QColor(_c(self._theme, "danger")))
            elif item.impact == "Medium":
                impact_item.setForeground(QColor(_c(self._theme, "warning")))
            elif item.impact == "Low":
                impact_item.setForeground(QColor(_c(self._theme, "safe")))
            self.table.setItem(row, 4, impact_item)

            cmd_item = QTableWidgetItem(item.command)
            cmd_item.setToolTip(item.command)
            cmd_item.setForeground(QColor(_c(self._theme, "muted")))
            self.table.setItem(row, 5, cmd_item)

        self.table.setSortingEnabled(True)
        self._populating = False

    def _item_for_row(self, row: int) -> Any:
        """Return the StartupItem for the given (possibly sorted) table row."""
        for col in (0, 1):
            cell = self.table.item(row, col)
            if cell:
                item_id = cell.data(Qt.ItemDataRole.UserRole)
                if item_id and hasattr(self, "_item_map"):
                    return self._item_map.get(item_id)
        return None

    def _on_table_item_clicked(self, table_item: QTableWidgetItem):
        if self._populating:
            return
        if table_item.column() == 0:
            item = self._item_for_row(table_item.row())
            if item:
                new_state = table_item.checkState() == Qt.CheckState.Checked
                if new_state != item.enabled:
                    self._toggle_item(item, new_state)

    def _on_table_double_clicked(self, table_item: QTableWidgetItem):
        if self._populating:
            return
        item = self._item_for_row(table_item.row())
        if item:
            self._open_file_location(item)

    def _toggle_item(self, item: Any, new_state: bool):
        from crapcleaner.gui.workers import StartupActionWorker, stop_worker

        stop_worker(getattr(self, "_action_worker", None))

        worker = StartupActionWorker("toggle", item_id=item.id, enabled=new_state, parent=self)
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

    def _delete_item(self, item: Any):
        ans = QMessageBox.question(
            self,
            "Delete Startup Entry",
            f"Are you sure you want to permanently delete the startup entry for:\n\n"
            f"  {item.name} ({item.location})\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        from crapcleaner.gui.workers import StartupActionWorker, stop_worker

        stop_worker(getattr(self, "_action_worker", None))

        worker = StartupActionWorker("remove", item_id=item.id, parent=self)
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

    def _add_item(self):
        dlg = AddStartupDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, cmd, scope = dlg.get_data()
            from crapcleaner.gui.workers import StartupActionWorker, stop_worker

            stop_worker(getattr(self, "_action_worker", None))

            worker = StartupActionWorker("add", name=name, command=cmd, scope=scope, parent=self)
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

    def _on_action_done(self, ok: bool, message: str):
        self.result_label.setText(message)
        self.result_icon.setPixmap(
            material_icon(
                "check" if ok else "warning", _c(self._theme, "safe" if ok else "warning")
            ).pixmap(18, 18)
        )
        self.result_banner.setVisible(True)
        if ok:
            self.refresh()

    def _open_file_location(self, item: Any):
        if item.file_path and os.path.exists(item.file_path):
            try:
                reveal_in_file_manager(item.file_path)
            except Exception:
                pass
        else:
            QMessageBox.information(
                self, "Open Location", f"Target file not found:\n{item.file_path}"
            )

    def _copy_command(self, item: Any):
        QApplication.clipboard().setText(item.command)
        self.result_label.setText(f"Copied command line to clipboard: {item.command}")
        self.result_icon.setPixmap(material_icon("check", _c(self._theme, "safe")).pixmap(18, 18))
        self.result_banner.setVisible(True)

    def _context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        item = self._item_for_row(row)
        if not item:
            return

        menu = QMenu(self)
        toggle_act = menu.addAction("Disable" if item.enabled else "Enable")
        toggle_act.triggered.connect(lambda: self._toggle_item(item, not item.enabled))

        menu.addSeparator()
        open_act = menu.addAction(f"Open File Location in {file_manager_name()}")
        open_act.triggered.connect(lambda: self._open_file_location(item))

        copy_act = menu.addAction("Copy Command Line")
        copy_act.triggered.connect(lambda: self._copy_command(item))

        menu.addSeparator()
        del_act = menu.addAction("Delete Startup Entry")
        del_act.triggered.connect(lambda: self._delete_item(item))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _relaunch_admin(self):
        if elevate():
            QApplication.quit()

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
        if self._filtered_items:
            self._populate_table(self._filtered_items)
