"""Large files view."""

import csv
import os
import tempfile

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.dialogs import (
    ConfirmDeleteDialog,
)
from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.views.common import CrapTable, NumericItem, _c, page_header
from crapcleaner.utils.files import file_manager_name, reveal_in_file_manager
from crapcleaner.utils.format import (
    format_size,
    parse_size,
)
from crapcleaner.utils.platform import (
    get_appdata,
    get_user_profile,
    is_windows,
)

_MAX_LARGE_FILE_ROWS = 500


class LargeFilesView(QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._files = []
        self._theme = "dark"
        self._build()

    def _default_root(self) -> str:
        return self._main._settings.get("large_file_default_root", "") or get_user_profile()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)
        layout.addWidget(
            page_header(
                "Large Files Finder",
                "Scan directories for disk hogs and optionally move large unneeded files to the Recycle Bin.",
            )
        )

        controls = QFrame()
        controls.setProperty("card", "true")
        controls_lay = QVBoxLayout(controls)
        controls_lay.setContentsMargins(14, 12, 14, 12)
        controls_lay.setSpacing(10)

        # Folder row
        f_row = QHBoxLayout()
        f_row.setSpacing(8)
        f_row.addWidget(QLabel("Scan Target:"))
        self.root_edit = QLineEdit()
        self.root_edit.setText(self._default_root())
        self.browse_button = QPushButton("Browse...")
        self.browse_button.setIcon(material_icon("folder_open", _c(self._theme, "text")))
        self.browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_button.clicked.connect(self._browse)
        f_row.addWidget(self.root_edit, 1)
        f_row.addWidget(self.browse_button)
        controls_lay.addLayout(f_row)

        # Quick presets & threshold row
        opts_row = QHBoxLayout()
        opts_row.setSpacing(8)
        opts_row.addWidget(QLabel("Presets:"))

        # get_appdata() resolves to %APPDATA% on Windows and $XDG_CONFIG_HOME (or
        # ~/.config) on Linux; gettempdir() honours TMPDIR/TEMP on either platform.
        presets = [
            ("User Profile", get_user_profile()),
            ("Downloads", os.path.join(get_user_profile(), "Downloads")),
            ("App Config" if not is_windows() else "AppData", get_appdata()),
            ("Temp", tempfile.gettempdir()),
        ]
        for label, path in presets:
            if os.path.exists(path):
                btn = QPushButton(label)
                btn.setProperty("chip", "true")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda _=False, p=path: self.root_edit.setText(p))
                opts_row.addWidget(btn)

        opts_row.addSpacing(10)
        opts_row.addWidget(QLabel("Min Size:"))
        self.threshold_combo = QComboBox()
        self.threshold_combo.addItems(["100 MB", "500 MB", "1 GB", "2 GB", "5 GB", "10 GB"])
        self.threshold_combo.setCurrentIndex(2)
        self.custom_threshold = QLineEdit()
        self.custom_threshold.setPlaceholderText("Custom e.g. 750MB")
        self.custom_threshold.setFixedWidth(130)
        opts_row.addWidget(self.threshold_combo)
        opts_row.addWidget(self.custom_threshold)

        opts_row.addStretch(1)
        self.scan_button = QPushButton("Find Large Files")
        self.scan_button.setProperty("primary", "true")
        self.scan_button.setIcon(material_icon("search", "#ffffff"))
        self.scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_button.clicked.connect(self._scan)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.hide()
        self.cancel_button.clicked.connect(
            lambda: (
                self._main.cancel_active_scan()
                if hasattr(self._main, "cancel_active_scan")
                else None
            )
        )

        opts_row.addWidget(self.scan_button)
        opts_row.addWidget(self.cancel_button)
        controls_lay.addLayout(opts_row)
        layout.addWidget(controls)

        # Search filter within table results
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self.table_search = QLineEdit()
        self.table_search.setPlaceholderText("Filter scanned results by name or type...")
        self.table_search.setClearButtonEnabled(True)
        self.table_search.textChanged.connect(self._filter_table)
        filter_row.addWidget(self.table_search)

        export_btn = QPushButton("Export to CSV")
        export_btn.setIcon(material_icon("file_download", _c(self._theme, "text")))
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self._export_csv)
        filter_row.addWidget(export_btn)
        layout.addLayout(filter_row)

        table_card = QFrame()
        table_card.setProperty("card", "true")
        table_lay = QVBoxLayout(table_card)
        table_lay.setContentsMargins(8, 8, 8, 8)
        self.table = CrapTable(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Size", "File Name", "Extension", "Last Modified", "Path"]
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        self.table.itemDoubleClicked.connect(self._open_row)
        self._empty_message = "Select a target folder and click 'Find Large Files' to begin."
        self.table.set_empty_text(self._theme, self._empty_message)
        table_lay.addWidget(self.table)
        layout.addWidget(table_card, 1)

        self.status_label = QLabel("")
        self.status_label.setProperty("subtle", "true")
        layout.addWidget(self.status_label)

    def _threshold(self):
        custom = self.custom_threshold.text().strip()
        if custom:
            return parse_size(custom)
        selected = self.threshold_combo.currentText().replace(" ", "")
        return parse_size(selected)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose folder to scan")
        if folder:
            self.root_edit.setText(folder)

    def _scan(self):
        self.scan_button.setEnabled(False)
        self.cancel_button.show()
        self.table.set_empty_text(self._theme, "Scanning directories for large files...")
        self.status_label.setText("Scanning directories for files exceeding size threshold...")
        self._main.scan_large_files(self.root_edit.text(), self._threshold())

    def _open_folder(self, path: str):
        if os.path.exists(path):
            reveal_in_file_manager(path)

    def _open_row(self, item):
        row = item.row()
        path_item = self.table.item(row, 4)
        if path_item is not None:
            self._open_folder(path_item.text())

    def show_files(self, files):
        self.scan_button.setEnabled(True)
        self.cancel_button.hide()
        if not files:
            self._empty_message = "Scan complete. No files above the size threshold were found."
            self.table.set_empty_text(self._theme, self._empty_message)
        self._files = files
        self.table.setRowCount(0)
        shown_files = files[:_MAX_LARGE_FILE_ROWS]
        for file in shown_files:
            row = self.table.rowCount()
            self.table.insertRow(row)
            size_item = NumericItem(format_size(file.size), file.size)
            name_item = QTableWidgetItem(file.name)
            type_item = QTableWidgetItem(file.file_type.upper())
            mtime_item = NumericItem(
                file.last_modified.strftime("%Y-%m-%d %H:%M"),
                int(file.last_modified.timestamp()),
            )
            path_item = QTableWidgetItem(file.path)
            path_item.setToolTip(file.path)
            self.table.setItem(row, 0, size_item)
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, type_item)
            self.table.setItem(row, 3, mtime_item)
            self.table.setItem(row, 4, path_item)
        self.table.refresh_placeholder()
        self.table.resizeColumnToContents(0)
        self.table.resizeColumnToContents(2)
        self.table.resizeColumnToContents(3)
        total = sum(f.size for f in files)
        found = len(files)
        shown = len(shown_files)
        self.status_label.setText(
            f"Found {found} file(s) larger than {format_size(self._threshold())} — "
            f"Total {format_size(total)} (showing top {shown} results)"
        )

    def _filter_table(self, text: str):
        text = text.strip().lower()
        for row in range(self.table.rowCount()):
            item1 = self.table.item(row, 1)
            item2 = self.table.item(row, 2)
            item4 = self.table.item(row, 4)
            name = item1.text().lower() if item1 else ""
            ext = item2.text().lower() if item2 else ""
            path = item4.text().lower() if item4 else ""
            match = not text or text in name or text in ext or text in path
            self.table.setRowHidden(row, not match)

    def _export_csv(self):
        if not self._files:
            QMessageBox.information(self, "Export", "No files to export.")
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export to CSV", "large_files.csv", "CSV (*.csv)"
        )
        if not dest:
            return
        try:
            with open(dest, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "Name",
                        "Size (Bytes)",
                        "Size (Formatted)",
                        "Type",
                        "Last Modified",
                        "Path",
                    ]
                )
                for file in self._files:
                    writer.writerow(
                        [
                            file.name,
                            file.size,
                            format_size(file.size),
                            file.file_type,
                            file.last_modified.strftime("%Y-%m-%d %H:%M:%S"),
                            file.path,
                        ]
                    )
            QMessageBox.information(
                self, "Export", f"Exported {len(self._files)} records to {dest}"
            )
        except OSError as exc:
            QMessageBox.warning(self, "Export Error", str(exc))

    def show_progress(self, visited: int):
        self.status_label.setText(f"Scanning... {visited:,} files visited")

    def _menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0 or row >= len(self._files):
            return
        path_item = self.table.item(row, 4)
        if not path_item:
            return
        file_path = path_item.text()

        menu = QMenu(self)
        open_folder = menu.addAction(f"Reveal in {file_manager_name()}")
        copy_path = menu.addAction("Copy Path")
        menu.addSeparator()
        to_recycle = menu.addAction("Move to Recycle Bin")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == open_folder:
            self._open_folder(file_path)
        elif action == copy_path:
            QApplication.clipboard().setText(file_path)
        elif action == to_recycle:
            self._recycle_path(file_path)

    def _recycle_path(self, path: str):
        from crapcleaner.utils.files import move_to_recycle_bin

        dialog = ConfirmDeleteDialog(
            "Move to Recycle Bin",
            f"Move this file to the Recycle Bin?\n\n{path}\n\nIt can be restored from the Recycle Bin if needed.",
            confirm_label="Move to Recycle Bin",
        )
        if dialog.exec() != ConfirmDeleteDialog.DialogCode.Accepted:
            return
        ok, _ = move_to_recycle_bin([path])
        if ok:
            self._files = [f for f in self._files if f.path != path]
            self.show_files(self._files)
            QMessageBox.information(self, "Recycle Bin", "File moved to the Recycle Bin.")
        else:
            QMessageBox.warning(
                self,
                "Recycle Bin",
                "Could not move the file (it may be locked or in use).",
            )

    def apply_theme(self, theme: str):
        self._theme = theme
        self.status_label.setStyleSheet(f"color: {_c(theme, 'muted')};")
        self.table.set_empty_text(theme, self._empty_message)
