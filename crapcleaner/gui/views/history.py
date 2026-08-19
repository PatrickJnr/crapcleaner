"""Cleanup history view."""

import json

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.dialogs import (
    ReportDialog,
)
from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.views.common import (
    CrapTable,
    NumericItem,
    _c,
    page_header,
    restyle_stat_card,
    stat_card,
)
from crapcleaner.history import clear as clear_history
from crapcleaner.history import load as load_history
from crapcleaner.utils.format import (
    format_datetime,
    format_duration,
    format_size,
)


class HistoryView(QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._theme = "dark"
        self._entries = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)
        layout.addWidget(
            page_header(
                "Audit History & Analytics",
                "Review lifetime cleanups, space recovered, and audit records of previous operations.",
            )
        )

        # 3 Top Metric Cards
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self.c1, self.c1_val, self.c1_sub = stat_card(
            "Total Space Recovered", "--", "Permanent cleanups", self._theme
        )
        self.c2, self.c2_val, self.c2_sub = stat_card(
            "Total Files Cleaned", "--", "Files removed", self._theme
        )
        self.c3, self.c3_val, self.c3_sub = stat_card(
            "Operations Run", "--", "Scans & cleanups", self._theme
        )
        stats_row.addWidget(self.c1)
        stats_row.addWidget(self.c2)
        stats_row.addWidget(self.c3)
        layout.addLayout(stats_row)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setIcon(material_icon("refresh", _c(self._theme, "text")))
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.clicked.connect(self.refresh)
        toolbar.addWidget(self.refresh_button)

        export_btn = QPushButton("Export Log to JSON")
        export_btn.setIcon(material_icon("file_download", _c(self._theme, "text")))
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self._export_json)
        toolbar.addWidget(export_btn)

        toolbar.addStretch(1)
        self.clear_button = QPushButton("Clear History Log")
        self.clear_button.setIcon(material_icon("delete_sweep", _c(self._theme, "danger")))
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.clicked.connect(self._clear)
        toolbar.addWidget(self.clear_button)
        layout.addLayout(toolbar)

        table_card = QFrame()
        table_card.setProperty("card", "true")
        table_lay = QVBoxLayout(table_card)
        table_lay.setContentsMargins(8, 8, 8, 8)
        self.table = CrapTable(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Timestamp",
                "Operation",
                "Duration",
                "Categories",
                "Files Removed",
                "Skipped",
                "Space Recovered",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.itemDoubleClicked.connect(self._show_details)
        self.table.set_empty_text(
            self._theme, "No history yet. Run a scan or cleanup to get started."
        )
        table_lay.addWidget(self.table)
        layout.addWidget(table_card, 1)

    def refresh(self):
        self._entries = load_history()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for entry in reversed(self._entries):
            row = self.table.rowCount()
            self.table.insertRow(row)
            kind = f"{entry.kind.upper()}" + (" (Dry-Run)" if entry.dry_run else "")
            self.table.setItem(row, 0, QTableWidgetItem(format_datetime(entry.started)))
            self.table.setItem(row, 1, QTableWidgetItem(kind))
            self.table.setItem(row, 2, NumericItem(format_duration(entry.duration), entry.duration))
            self.table.setItem(row, 3, QTableWidgetItem(", ".join(entry.categories[:5])))
            self.table.setItem(row, 4, NumericItem(str(entry.files_removed), entry.files_removed))
            self.table.setItem(row, 5, NumericItem(str(entry.skipped), entry.skipped))
            self.table.setItem(
                row,
                6,
                NumericItem(format_size(entry.space_recovered), entry.space_recovered),
            )
        self.table.setSortingEnabled(True)
        self.table.refresh_placeholder()
        for col in (0, 1, 2, 4, 5, 6):
            self.table.resizeColumnToContents(col)

        # Update metrics
        total_rec = sum(e.space_recovered for e in self._entries if not e.dry_run)
        total_files = sum(e.files_removed for e in self._entries if not e.dry_run)
        self.c1_val.setText(format_size(total_rec))
        self.c2_val.setText(f"{total_files:,} files")
        self.c3_val.setText(f"{len(self._entries)} actions")

    def _show_details(self, item):
        row = item.row()
        if 0 <= row < len(self._entries):
            entry = list(reversed(self._entries))[row]
            summary = (
                f"Operation: {entry.kind.upper()}\n"
                f"Dry-Run: {entry.dry_run}\n"
                f"Started: {format_datetime(entry.started)}\n"
                f"Duration: {format_duration(entry.duration)}\n"
                f"Space Recovered: {format_size(entry.space_recovered)}\n"
                f"Files Removed: {entry.files_removed}\n"
                f"Skipped: {entry.skipped}\n\n"
                f"Categories:\n" + "\n".join(f" - {c}" for c in entry.categories)
            )
            ReportDialog("Operation History Details", summary, self).exec()

    def _export_json(self):
        if not self._entries:
            QMessageBox.information(self, "Export", "No history entries to export.")
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export History", "history_export.json", "JSON (*.json)"
        )
        if not dest:
            return
        try:
            with open(dest, "w", encoding="utf-8") as f:
                json.dump([e.__dict__ for e in self._entries], f, indent=2, default=str)
            QMessageBox.information(
                self, "Export", f"Exported {len(self._entries)} records to {dest}"
            )
        except OSError as exc:
            QMessageBox.warning(self, "Export Error", str(exc))

    def _clear(self):
        result = QMessageBox.question(
            self,
            "Clear History",
            "Clear all scan and cleanup audit logs? This cannot be undone.",
        )
        if result == QMessageBox.StandardButton.Yes:
            clear_history()
            self.refresh()

    def apply_theme(self, theme: str):
        self._theme = theme
        self.table.set_empty_text(theme, "No history yet. Run a scan or cleanup to get started.")
        for pair in (
            (self.c1_val, self.c1_sub),
            (self.c2_val, self.c2_sub),
            (self.c3_val, self.c3_sub),
        ):
            restyle_stat_card(pair[0], pair[1], theme)
