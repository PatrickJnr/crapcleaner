"""Duplicate file finder view."""

import os

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.dialogs import (
    DuplicateFilesDialog,
)
from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.views.common import CrapTable, NumericItem, _c, page_header
from crapcleaner.utils.format import (
    format_size,
)
from crapcleaner.utils.platform import (
    get_user_profile,
)

_MAX_DUPLICATE_GROUP_ROWS = 150


_MAX_DUPLICATE_TOOLTIP_FILES = 20


class DuplicatesView(QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._groups = []
        self._theme = "dark"
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)
        layout.addWidget(
            page_header(
                "Duplicate Files Finder",
                "Identify identical files across folders by hash comparison and reclaim wasted storage.",
            )
        )

        controls = QFrame()
        controls.setProperty("card", "true")
        controls_lay = QHBoxLayout(controls)
        controls_lay.setContentsMargins(14, 12, 14, 12)
        controls_lay.setSpacing(12)

        folder_box = QVBoxLayout()
        folder_box.setSpacing(4)
        folder_box.addWidget(QLabel("Folders to scan for duplicates:"))
        self.folder_list = QListWidget()
        self.folder_list.setFixedHeight(90)
        folder_box.addWidget(self.folder_list)

        # Quick preset folders
        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        for label, name in [
            ("Downloads", "Downloads"),
            ("Documents", "Documents"),
            ("Pictures", "Pictures"),
        ]:
            p = os.path.join(get_user_profile(), name)
            if os.path.exists(p):
                btn = QPushButton(label)
                btn.setProperty("chip", "true")
                btn.clicked.connect(lambda _=False, path=p: self._add_preset_folder(path))
                preset_row.addWidget(btn)
        preset_row.addStretch(1)
        folder_box.addLayout(preset_row)
        controls_lay.addLayout(folder_box, 1)

        side = QVBoxLayout()
        side.setSpacing(6)
        add_button = QPushButton("Add Folder...")
        add_button.setIcon(material_icon("add", _c(self._theme, "text")))
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.clicked.connect(self._add_folder)
        remove_button = QPushButton("Remove Selected")
        remove_button.setIcon(material_icon("delete", _c(self._theme, "danger")))
        remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_button.clicked.connect(self._remove_folder)
        side.addWidget(add_button)
        side.addWidget(remove_button)
        side.addStretch(1)
        controls_lay.addLayout(side)
        layout.addWidget(controls)

        min_row = QHBoxLayout()
        min_row.setSpacing(8)
        min_row.addWidget(QLabel("Minimum File Size:"))
        self.min_size = QSpinBox()
        self.min_size.setRange(1, 102400)
        self.min_size.setValue(1)
        self.min_size.setSuffix(" MB")
        min_row.addWidget(self.min_size)
        min_row.addStretch(1)

        self.scan_button = QPushButton("Find Duplicates")
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

        min_row.addWidget(self.scan_button)
        min_row.addWidget(self.cancel_button)
        layout.addLayout(min_row)

        table_card = QFrame()
        table_card.setProperty("card", "true")
        table_lay = QVBoxLayout(table_card)
        table_lay.setContentsMargins(8, 8, 8, 8)
        self.table = CrapTable(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Group Size", "Duplicates Count", "Wasted Space", "Copies Overview"]
        )
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        self.table.itemDoubleClicked.connect(self._open_group)
        self._empty_message = "Add one or more folders and scan for duplicates."
        self.table.set_empty_text(self._theme, self._empty_message)
        table_lay.addWidget(self.table)
        layout.addWidget(table_card, 1)

        self.status_label = QLabel("Select folders, then scan.")
        self.status_label.setProperty("subtle", "true")
        layout.addWidget(self.status_label)

    def _add_preset_folder(self, path: str):
        if not self.folder_list.findItems(path, Qt.MatchFlag.MatchExactly):
            self.folder_list.addItem(path)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose folder")
        if folder and not self.folder_list.findItems(folder, Qt.MatchFlag.MatchExactly):
            self.folder_list.addItem(folder)

    def _remove_folder(self):
        for item in self.folder_list.selectedItems():
            self.folder_list.takeItem(self.folder_list.row(item))

    def _scan(self):
        folders = [self.folder_list.item(i).text() for i in range(self.folder_list.count())]
        if not folders:
            QMessageBox.warning(self, "Duplicates", "Please add at least one folder to scan.")
            return
        self.scan_button.setEnabled(False)
        self.cancel_button.show()
        self.table.set_empty_text(
            self._theme, "Scanning folders and calculating SHA-256 file hashes..."
        )
        self.status_label.setText("Scanning folders and calculating SHA-256 file hashes...")
        self._main.scan_duplicates(folders, self.min_size.value() * 1024 * 1024)

    def show_groups(self, groups):
        self.scan_button.setEnabled(True)
        self.cancel_button.hide()
        if not groups:
            self._empty_message = "Scan complete. No duplicate files were found in these folders."
            self.table.set_empty_text(self._theme, self._empty_message)
        self._groups = groups
        self.table.setRowCount(0)
        shown_groups = groups[:_MAX_DUPLICATE_GROUP_ROWS]
        for group in shown_groups:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, NumericItem(format_size(group.size), group.size))
            self.table.setItem(
                row, 1, NumericItem(str(group.duplicate_count), group.duplicate_count)
            )
            self.table.setItem(
                row, 2, NumericItem(format_size(group.reclaimable), group.reclaimable)
            )
            files_item = QTableWidgetItem(f"{len(group.files)} copies — {group.files[0]}")
            preview_files = group.files[:_MAX_DUPLICATE_TOOLTIP_FILES]
            tooltip = "\n".join(preview_files)
            remaining = len(group.files) - len(preview_files)
            if remaining > 0:
                tooltip += f"\n... and {remaining} more"
            files_item.setToolTip(tooltip)
            self.table.setItem(row, 3, files_item)
        self.table.refresh_placeholder()
        self.table.resizeColumnToContents(0)
        self.table.resizeColumnToContents(1)
        self.table.resizeColumnToContents(2)
        total = sum(g.reclaimable for g in groups)
        self.status_label.setText(
            f"Found {len(groups)} duplicate group(s) — up to {format_size(total)} reclaimable "
            f"(showing top {len(shown_groups)} groups). Double-click any row to review and recycle duplicate copies."
        )

    def _open_group(self, item):
        row = item.row()
        if not (0 <= row < len(self._groups)):
            return
        group = self._groups[row]
        dialog = DuplicateFilesDialog(group, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        targets = dialog.targets()
        if not targets:
            QMessageBox.information(
                self,
                "Duplicates",
                "No copies were selected for recycling, or the selection would not have "
                "left a copy behind.",
            )
            return
        # Every deletion in the application goes through the same validated helper, so
        # a protected path cannot be removed from here either.
        from crapcleaner.core.cleaner import remove_selected_paths

        outcomes = remove_selected_paths(targets, use_recycle_bin=True)
        moved = [o for o in outcomes if o.removed]
        refused = [o for o in outcomes if not o.removed]
        self._groups = [g for g in self._groups if g is not group]
        self.show_groups(self._groups)
        if not refused:
            QMessageBox.information(
                self,
                "Recycle Bin",
                f"Moved {len(moved)} duplicate copy/copies to the Recycle Bin.",
            )
        else:
            detail = "\n".join(f"{o.path}\n    {o.reason}" for o in refused[:5])
            QMessageBox.warning(
                self,
                "Recycle Bin",
                f"Moved {len(moved)} copy/copies. {len(refused)} were not removed:\n\n{detail}",
            )

    def _menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0 or row >= len(self._groups):
            return
        group = self._groups[row]
        menu = QMenu(self)
        review = menu.addAction("Review and Recycle Copies...")
        copy = menu.addAction("Copy File Paths")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == review:
            item = self.table.item(row, 0)
            if item is not None:
                self._open_group(item)
        elif action == copy:
            QApplication.clipboard().setText("\n".join(group.files))

    def apply_theme(self, theme: str):
        self._theme = theme
        self.status_label.setStyleSheet(f"color: {_c(theme, 'muted')};")
        self.table.set_empty_text(theme, self._empty_message)
