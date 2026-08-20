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
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.core.manifest import read_manifest
from crapcleaner.gui.dialogs import (
    ReportDialog,
    RestoreRunDialog,
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

        self.restore_button = QPushButton("Restore This Run...")
        self.restore_button.setIcon(material_icon("refresh", _c(self._theme, "text")))
        self.restore_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restore_button.setToolTip("Put back the files a recycle-bin cleanup removed.")
        self.restore_button.setEnabled(False)
        self.restore_button.clicked.connect(self._restore_selected)
        toolbar.addWidget(self.restore_button)

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
        self.table.itemSelectionChanged.connect(self._sync_restore_state)
        self.table.setAccessibleName("Scan and cleanup history")
        self.table.set_empty_text(
            self._theme, "No history yet. Run a scan or cleanup to get started."
        )
        table_lay.addWidget(self.table)
        layout.addWidget(table_card, 1)

        self.detail_label = QLabel(
            "Select a run to see what it removed. Double-click for the full list."
        )
        self.detail_label.setWordWrap(True)
        self.detail_label.setProperty("subtle", "true")
        layout.addWidget(self.detail_label)

    def refresh(self):
        self._entries = load_history()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for position, entry in enumerate(reversed(self._entries)):
            row = self.table.rowCount()
            self.table.insertRow(row)
            kind = f"{entry.kind.upper()}" + (" (Dry-Run)" if entry.dry_run else "")
            stamp = QTableWidgetItem(format_datetime(entry.started))
            # Carried on the item so a re-sorted table still maps a row to its run.
            stamp.setData(Qt.ItemDataRole.UserRole, position)
            self.table.setItem(row, 0, stamp)
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

        total_rec = sum(e.space_recovered for e in self._entries if not e.dry_run)
        total_files = sum(e.files_removed for e in self._entries if not e.dry_run)
        self.c1_val.setText(format_size(total_rec))
        self.c2_val.setText(f"{total_files:,} files")
        self.c3_val.setText(f"{len(self._entries)} actions")
        self._sync_restore_state()

    def _entry_for_row(self, row: int):
        item = self.table.item(row, 0)
        if item is None:
            return None
        position = item.data(Qt.ItemDataRole.UserRole)
        newest_first = list(reversed(self._entries))
        if isinstance(position, int) and 0 <= position < len(newest_first):
            return newest_first[position]
        return None

    def _selected_entry(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return self._entry_for_row(rows[0].row()) if rows else None

    def _manifest_for(self, entry) -> dict:
        """The recorded run for `entry`, or an empty dict. Never logged: it is a
        list of the user's own file paths."""
        path = getattr(entry, "manifest_path", "") if entry is not None else ""
        return read_manifest(path) if path else {}

    def _sync_restore_state(self):
        entry = self._selected_entry()
        manifest = self._manifest_for(entry)
        items = manifest.get("items") or []
        self.restore_button.setEnabled(bool(items) and bool(manifest.get("use_recycle_bin")))
        if entry is None:
            self.detail_label.setText(
                "Select a run to see what it removed. Double-click for the full list."
            )
            return
        if not items:
            self.detail_label.setText(
                "No per-file record was kept for this run — history stores counts only "
                "for dry runs and for runs older than the last 20."
            )
            return
        recycled = sum(1 for item in items if item.get("recycled"))
        removed_size = sum(int(item.get("size") or 0) for item in items)
        truncated = " (list truncated)" if manifest.get("truncated") else ""
        self.detail_label.setText(
            f"This run removed {len(items):,} item(s), {format_size(removed_size)}{truncated}. "
            f"{recycled:,} went to the Recycle Bin. Double-click the row for the full list."
        )

    def _show_details(self, item):
        entry = self._entry_for_row(item.row())
        if entry is None:
            return
        manifest = self._manifest_for(entry)
        items = manifest.get("items") or []
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
        sizes = getattr(entry, "category_sizes", None) or {}
        if sizes:
            summary += "\n\nPer category:\n" + "\n".join(
                f" - {name}: {format_size(size)}" for name, size in sizes.items()
            )
        if items:
            summary += f"\n\nRemoved ({len(items):,} item(s)):\n" + "\n".join(
                f" - {i.get('path')}  {format_size(int(i.get('size') or 0))}"
                f"{'  [recycle bin]' if i.get('recycled') else ''}"
                for i in items
            )
            if manifest.get("truncated"):
                summary += "\n - … the rest of this run was not recorded."
        ReportDialog("Operation History Details", summary, self).exec()

    def _restore_selected(self):
        entry = self._selected_entry()
        manifest = self._manifest_for(entry)
        items = [i for i in (manifest.get("items") or []) if i.get("recycled")]
        if not items:
            QMessageBox.information(
                self,
                "Restore",
                "This run has no recycled files to restore.",
            )
            return
        RestoreRunDialog([str(i.get("path") or "") for i in items], self).exec()

    def _export_json(self):
        if not self._entries:
            QMessageBox.information(self, "Export", "No history entries to export.")
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export History", "history_export.json", "JSON (*.json)"
        )
        if not dest:
            return
        # The manifest is a list of the user's own file paths, so the export carries
        # the counts only and does not follow the pointer to it.
        records = [
            {k: v for k, v in e.__dict__.items() if k != "manifest_path"} for e in self._entries
        ]
        try:
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, default=str)
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
