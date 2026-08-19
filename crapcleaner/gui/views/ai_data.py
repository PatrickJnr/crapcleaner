"""Local AI model and cache inspection view."""

import os

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.views.common import CrapTable, NumericItem, _c, page_header
from crapcleaner.utils.files import file_manager_name, reveal_in_file_manager
from crapcleaner.utils.format import (
    format_datetime,
    format_size,
)


class AiDataView(QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._items = []
        self._theme = "dark"
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)
        layout.addWidget(
            page_header(
                "AI Models & Data Explorer",
                "Inspect local AI caches (Ollama, LM Studio, Hugging Face, PyTorch). Files are read-only.",
            )
        )

        info_card = QFrame()
        info_card.setProperty("card", "true")
        i_lay = QVBoxLayout(info_card)
        i_lay.setContentsMargins(14, 12, 14, 12)
        info_title = QLabel("AI Data Safety Guarantee")
        info_title.setStyleSheet(f"font-weight: 700; color: {_c(self._theme, 'accent')};")
        self.info_label = QLabel(
            "Local AI weights and checkpoints can take dozens of gigabytes. "
            "To prevent accidental model loss, CrapCleaner only inspects and lists these files read-only."
        )
        self.info_label.setWordWrap(True)
        self.info_label.setProperty("subtle", "true")
        i_lay.addWidget(info_title)
        i_lay.addWidget(self.info_label)
        layout.addWidget(info_card)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.scan_button = QPushButton("Inspect AI Data")
        self.scan_button.setProperty("primary", "true")
        self.scan_button.setIcon(material_icon("search", "#ffffff"))
        self.scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_button.clicked.connect(self._scan)

        self.min_size = QSpinBox()
        self.min_size.setRange(10, 102400)
        self.min_size.setValue(50)
        self.min_size.setSuffix(" MB")

        toolbar.addWidget(self.scan_button)
        toolbar.addWidget(QLabel("Min File Size:"))
        toolbar.addWidget(self.min_size)
        toolbar.addStretch(1)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter AI models/caches...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_table)
        toolbar.addWidget(self.search_edit)
        layout.addLayout(toolbar)

        table_card = QFrame()
        table_card.setProperty("card", "true")
        table_lay = QVBoxLayout(table_card)
        table_lay.setContentsMargins(8, 8, 8, 8)
        self.table = CrapTable(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Path", "Application", "Size", "Last Modified", "Classification"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        self.table.itemDoubleClicked.connect(self._open_row)
        self._empty_message = "Click 'Inspect AI Data' to scan for local AI models."
        self.table.set_empty_text(self._theme, self._empty_message)
        table_lay.addWidget(self.table)
        layout.addWidget(table_card, 1)

        self.status_label = QLabel("")
        self.status_label.setProperty("subtle", "true")
        layout.addWidget(self.status_label)

    def _scan(self):
        self.table.set_empty_text(
            self._theme, "Scanning directories for local AI models and checkpoints..."
        )
        self._main.scan_ai_data(self.min_size.value() * 1024 * 1024)

    def _open_row(self, item):
        row = item.row()
        path_item = self.table.item(row, 0)
        if path_item is not None and os.path.exists(path_item.text()):
            reveal_in_file_manager(path_item.text())

    def show_items(self, items):
        if not items:
            self._empty_message = "Scan complete. No local AI models or datasets were found."
            self.table.set_empty_text(self._theme, self._empty_message)
        self._items = items
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for item in items[:500]:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(item.path))
            self.table.setItem(row, 1, QTableWidgetItem(item.application))
            self.table.setItem(row, 2, NumericItem(format_size(item.size), item.size))
            self.table.setItem(
                row,
                3,
                NumericItem(
                    format_datetime(item.last_modified) if item.last_modified else "",
                    int(item.last_modified.timestamp()) if item.last_modified else None,
                ),
            )
            self.table.setItem(row, 4, QTableWidgetItem(item.classification.upper()))
        self.table.setSortingEnabled(True)
        self.table.refresh_placeholder()
        self.table.resizeColumnToContents(1)
        self.table.resizeColumnToContents(2)
        self.table.resizeColumnToContents(3)
        self.table.resizeColumnToContents(4)
        model_total = sum(i.size for i in items if i.classification == "model")
        self.status_label.setText(
            f"Identified {len(items)} AI items — Model weights total {format_size(model_total)} (Read-only review)"
        )

    def _filter_table(self, text: str):
        text = text.strip().lower()
        for row in range(self.table.rowCount()):
            item0 = self.table.item(row, 0)
            item1 = self.table.item(row, 1)
            item4 = self.table.item(row, 4)
            path = item0.text().lower() if item0 else ""
            app = item1.text().lower() if item1 else ""
            cls = item4.text().lower() if item4 else ""
            match = not text or text in path or text in app or text in cls
            self.table.setRowHidden(row, not match)

    def _menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        path = item.text()
        menu = QMenu(self)
        open_folder = menu.addAction(f"Reveal in {file_manager_name()}")
        copy_path = menu.addAction("Copy Path")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == open_folder and os.path.exists(path):
            reveal_in_file_manager(path)
        elif action == copy_path:
            QApplication.clipboard().setText(path)

    def apply_theme(self, theme: str):
        self._theme = theme
        self.info_label.setStyleSheet(f"color: {_c(theme, 'muted')};")
        self.status_label.setStyleSheet(f"color: {_c(theme, 'muted')};")
        self.table.set_empty_text(theme, self._empty_message)
