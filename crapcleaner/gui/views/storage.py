"""Storage breakdown: treemap grid, squarify layout, and the analysis view."""

import os

from PySide6.QtCore import (
    QEvent,
    QRectF,
    Qt,
    QThread,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QKeySequence,
    QPainter,
    QPen,
    QShortcut,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.config import load_settings, update_settings
from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.views.common import CrapTable, NumericItem, _c, page_header
from crapcleaner.reports import export_report
from crapcleaner.utils.format import (
    format_size,
)
from crapcleaner.utils.platform import (
    get_user_profile,
    is_windows,
    list_drives,
)


class StorageCell:
    __slots__ = ("node", "rect", "label", "size", "share", "path", "drillable")

    def __init__(self, node, rect, label, size, share, path, drillable):
        self.node = node
        self.rect = rect
        self.label = label
        self.size = size
        self.share = share
        self.path = path
        self.drillable = drillable


class StorageGrid(QWidget):
    """Proportional grid of storage consumers, largest first.

    Cell area is proportional to size, so the biggest consumers are the biggest
    blocks. Cells are laid out with a squarified treemap so they stay close to
    square and remain readable at any window size.
    """

    activated = Signal(object)
    selection_changed = Signal(object)

    _MAX_CELLS = 60
    _PALETTE_KEYS = ("accent", "info", "success", "review", "warning", "danger")

    def __init__(self, theme: str = "dark", parent=None):
        super().__init__(parent)
        self._theme = theme
        self._node = None
        self._cells: list[StorageCell] = []
        self._selected = -1
        self._hovered = -1
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName("Storage usage grid")

    def set_node(self, node):
        self._node = node
        self._selected = 0 if node is not None and node.children else -1
        self._hovered = -1
        self._relayout()
        self.update()
        self._emit_selection()

    def node(self):
        return self._node

    def selected_cell(self):
        if 0 <= self._selected < len(self._cells):
            return self._cells[self._selected]
        return None

    def apply_theme(self, theme: str):
        self._theme = theme
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _entries(self) -> list[tuple]:
        node = self._node
        if node is None or node.size <= 0:
            return []
        entries = [(child.name, child.size, child, True) for child in node.children if child.size]
        entries.sort(key=lambda e: e[1], reverse=True)
        if len(entries) > self._MAX_CELLS:
            hidden = entries[self._MAX_CELLS :]
            entries = entries[: self._MAX_CELLS]
            entries.append((f"Other ({len(hidden)} items)", sum(e[1] for e in hidden), None, False))
        direct = node.size - sum(child.size for child in node.children)
        if direct > 0:
            entries.append(("Files in this folder", direct, None, False))
        return entries

    def _relayout(self):
        self._cells = []
        entries = self._entries()
        if not entries:
            return
        total = sum(e[1] for e in entries)
        if total <= 0:
            return
        area = QRectF(2, 2, max(self.width() - 4, 1), max(self.height() - 4, 1))
        rects = _squarify([e[1] for e in entries], area)
        for (name, size, node, drillable), rect in zip(entries, rects):
            self._cells.append(
                StorageCell(
                    node=node,
                    rect=rect,
                    label=name,
                    size=size,
                    share=size / total * 100.0,
                    path=getattr(node, "path", ""),
                    drillable=drillable and node is not None,
                )
            )
        if self._selected >= len(self._cells):
            self._selected = len(self._cells) - 1

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(_c(self._theme, "panel")))

        if not self._cells:
            painter.setPen(QColor(_c(self._theme, "faint")))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Run an analysis to see where storage is used.",
            )
            painter.end()
            return

        for index, cell in enumerate(self._cells):
            base = QColor(_c(self._theme, self._PALETTE_KEYS[index % len(self._PALETTE_KEYS)]))
            fill = QColor(base)
            fill.setAlpha(72 if cell.drillable else 42)
            rect = cell.rect.adjusted(1, 1, -1, -1)
            painter.fillRect(rect, fill)

            border = QColor(_c(self._theme, "border2"))
            width = 1
            if index == self._selected:
                border = QColor(_c(self._theme, "accent"))
                width = 2
            elif index == self._hovered:
                border = base
            painter.setPen(QPen(border, width))
            painter.drawRect(rect)

            if rect.width() < 54 or rect.height() < 30:
                continue
            painter.setPen(QColor(_c(self._theme, "text")))
            text_rect = rect.adjusted(6, 4, -6, -4)
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            name = metrics.elidedText(
                cell.label, Qt.TextElideMode.ElideMiddle, int(text_rect.width())
            )
            painter.drawText(
                text_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, name
            )
            if rect.height() >= 46:
                font.setBold(False)
                painter.setFont(font)
                painter.setPen(QColor(_c(self._theme, "muted")))
                painter.drawText(
                    text_rect,
                    Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                    f"{format_size(cell.size)}  ·  {cell.share:.1f}%",
                )
        painter.end()

    def _cell_at(self, pos) -> int:
        for index, cell in enumerate(self._cells):
            if cell.rect.contains(pos):
                return index
        return -1

    def mouseMoveEvent(self, event):
        index = self._cell_at(event.position())
        if index != self._hovered:
            self._hovered = index
            self.update()

    def leaveEvent(self, event):
        self._hovered = -1
        self.update()

    def mousePressEvent(self, event):
        index = self._cell_at(event.position())
        if index >= 0:
            self._selected = index
            self.setFocus()
            self.update()
            self._emit_selection()

    def mouseDoubleClickEvent(self, event):
        index = self._cell_at(event.position())
        if index >= 0 and self._cells[index].drillable:
            self.activated.emit(self._cells[index].node)

    def keyPressEvent(self, event):
        if not self._cells:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self._select(min(self._selected + 1, len(self._cells) - 1))
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self._select(max(self._selected - 1, 0))
        elif key == Qt.Key.Key_Home:
            self._select(0)
        elif key == Qt.Key.Key_End:
            self._select(len(self._cells) - 1)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            cell = self.selected_cell()
            if cell is not None and cell.drillable:
                self.activated.emit(cell.node)
        else:
            super().keyPressEvent(event)

    def _select(self, index: int):
        if index != self._selected:
            self._selected = index
            self.update()
            self._emit_selection()

    def _emit_selection(self):
        self.selection_changed.emit(self.selected_cell())

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            index = self._cell_at(event.pos())
            if index >= 0:
                cell = self._cells[index]
                detail = f"{cell.label}\n{format_size(cell.size)} · {cell.share:.1f}%"
                if cell.path:
                    detail += f"\n{cell.path}"
                if cell.drillable:
                    detail += "\nDouble-click or press Enter to open"
                QToolTip.showText(event.globalPos(), detail, self)
            else:
                QToolTip.hideText()
            return True
        return super().event(event)


def _squarify(sizes: list[int], area: QRectF) -> list[QRectF]:
    """Squarified treemap layout, keeping cells as close to square as possible."""
    total = float(sum(sizes))
    if total <= 0:
        return [QRectF(area) for _ in sizes]
    scale = area.width() * area.height() / total
    remaining = [float(size) * scale for size in sizes]
    rects: list[QRectF] = []
    x, y, width, height = area.x(), area.y(), area.width(), area.height()
    index = 0

    while index < len(remaining):
        row = [remaining[index]]
        index += 1
        side = min(width, height)
        while index < len(remaining) and _worst(row + [remaining[index]], side) <= _worst(
            row, side
        ):
            row.append(remaining[index])
            index += 1
        row_total = sum(row)
        if side <= 0 or row_total <= 0:
            rects.extend(QRectF(x, y, 0, 0) for _ in row)
            continue
        if width >= height:
            row_width = row_total / height
            offset = y
            for value in row:
                cell_height = value / row_total * height
                rects.append(QRectF(x, offset, row_width, cell_height))
                offset += cell_height
            x += row_width
            width -= row_width
        else:
            row_height = row_total / width
            offset = x
            for value in row:
                cell_width = value / row_total * width
                rects.append(QRectF(offset, y, cell_width, row_height))
                offset += cell_width
            y += row_height
            height -= row_height
    return rects


def _worst(row: list[float], side: float) -> float:
    if not row or side <= 0:
        return float("inf")
    total = sum(row)
    if total <= 0:
        return float("inf")
    largest, smallest = max(row), min(row)
    side_squared = side * side
    total_squared = total * total
    return max(side_squared * largest / total_squared, total_squared / (side_squared * smallest))


class StorageBreakdownView(QWidget):
    """Hierarchical storage analyzer, file type breakdown, and drive health explorer."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self._theme = "dark"
        self._current_node = None
        self._file_types_data = []
        self._vm_data = []
        self._health_data = []
        self._health_worker = None
        self._expand_worker: QThread | None = None
        self._grid_stack = []
        self._build_ui()

    def _build_ui(self):
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(24, 20, 24, 16)
        root_lay.setSpacing(12)

        root_lay.addWidget(
            page_header(
                "Storage Breakdown & Drive Analyzer",
                "Explore disk consumption hierarchy, inspect distribution by file type, and diagnose storage health.",
            )
        )

        # Controls toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        toolbar.addWidget(QLabel("Drive / Path:"))
        self.drive_combo = QComboBox()
        self.drive_combo.setFixedWidth(180)
        drives = [d.rstrip("\\") if is_windows() else d for d in list_drives()]
        if not is_windows():
            home_path = get_user_profile()
            if home_path and home_path not in drives:
                drives.append(home_path)
        self.drive_combo.addItems(drives)
        self.drive_combo.currentTextChanged.connect(self._on_drive_changed)
        toolbar.addWidget(self.drive_combo)

        preset_btn = QPushButton("Home")
        preset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        preset_btn.clicked.connect(lambda: self._apply_storage_preset(get_user_profile()))
        toolbar.addWidget(preset_btn)

        cache_btn = QPushButton("Cache")
        cache_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cache_btn.clicked.connect(
            lambda: self._apply_storage_preset(os.path.join(get_user_profile(), ".cache"))
        )
        toolbar.addWidget(cache_btn)

        downloads_btn = QPushButton("Downloads")
        downloads_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        downloads_btn.clicked.connect(
            lambda: self._apply_storage_preset(os.path.join(get_user_profile(), "Downloads"))
        )
        toolbar.addWidget(downloads_btn)

        self.favorite_combo = QComboBox()
        self.favorite_combo.setFixedWidth(180)
        self._reload_storage_favorites()
        self.favorite_combo.currentTextChanged.connect(self._on_favorite_selected)
        toolbar.addWidget(self.favorite_combo)

        favorite_btn = QPushButton("Save Favorite")
        favorite_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        favorite_btn.clicked.connect(self._save_current_storage_favorite)
        toolbar.addWidget(favorite_btn)

        self.path_edit = QLineEdit()
        self.path_edit.setText(drives[0] if drives else get_user_profile())
        toolbar.addWidget(self.path_edit, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.setIcon(material_icon("folder_open", _c(self._theme, "text")))
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self._browse_path)
        toolbar.addWidget(browse_btn)

        toolbar.addWidget(QLabel("Max Depth:"))
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(1, 6)
        self.depth_spin.setValue(3)
        toolbar.addWidget(self.depth_spin)

        self.analyze_btn = QPushButton("Analyze Storage")
        self.analyze_btn.setProperty("primary", "true")
        self.analyze_btn.setIcon(material_icon("search", "#ffffff"))
        self.analyze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.analyze_btn.clicked.connect(self.run_analysis)
        toolbar.addWidget(self.analyze_btn)

        # Analysing a large drive takes tens of seconds, so it has to be stoppable.
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setIcon(material_icon("close", _c(self._theme, "text")))
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._cancel_analysis)
        self.cancel_btn.setVisible(False)
        toolbar.addWidget(self.cancel_btn)

        self.export_btn = QPushButton("Export Report...")
        self.export_btn.setIcon(material_icon("file_download", _c(self._theme, "text")))
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.clicked.connect(self._export_report)
        toolbar.addWidget(self.export_btn)

        root_lay.addLayout(toolbar)

        # Live feedback while a long analysis runs, so the view never looks frozen.
        self.progress_label = QLabel("")
        self.progress_label.setProperty("subtle", "true")
        self.progress_label.setStyleSheet(f"font-size: 11px; color: {_c(self._theme, 'muted')};")
        self.progress_label.setVisible(False)
        root_lay.addWidget(self.progress_label)

        # Drive Health & Diagnostics Header Card
        self.health_card = QFrame()
        self.health_card.setProperty("card", "true")
        h_lay = QHBoxLayout(self.health_card)
        h_lay.setContentsMargins(16, 12, 16, 12)
        h_lay.setSpacing(16)

        self.health_info_label = QLabel(
            "<b>Storage Device Health:</b> Loading diagnostics...\nTRIM Status: Checking..."
        )
        self.health_info_label.setWordWrap(True)
        h_lay.addWidget(self.health_info_label, 1)

        self._refresh_health_btn = QPushButton("Refresh Health")
        self._refresh_health_btn.setIcon(material_icon("refresh", _c(self._theme, "text")))
        self._refresh_health_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_health_btn.clicked.connect(lambda: self.refresh_health(force=True))
        h_lay.addWidget(self._refresh_health_btn)

        root_lay.addWidget(self.health_card)

        # Section Selector (Tabs)
        tab_row = QHBoxLayout()
        tab_row.setSpacing(8)
        self._section_buttons = {}
        sections = [
            ("TREE", "Directory Hierarchy"),
            ("TYPES", "Functional File Types"),
            ("OLD", "Old Files (>90d)"),
            ("VMS", "Virtual Machines && Containers"),
        ]
        for key, title in sections:
            btn = QPushButton(title)
            btn.setProperty("chip", "true")
            btn.setProperty("active", "true" if key == "TREE" else "false")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self._set_active_section(k))
            tab_row.addWidget(btn)
            self._section_buttons[key] = btn
        tab_row.addStretch(1)
        root_lay.addLayout(tab_row)

        # Content Stack
        self.content_stack = QStackedWidget()

        # 1. Proportional storage grid
        grid_card = QFrame()
        grid_card.setProperty("card", "true")
        t_lay = QVBoxLayout(grid_card)
        t_lay.setContentsMargins(8, 8, 8, 8)
        t_lay.setSpacing(8)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)
        self.grid_up_btn = QPushButton("Up")
        self.grid_up_btn.setEnabled(False)
        self.grid_up_btn.setToolTip("Go back to the parent folder (Backspace)")
        self.grid_up_btn.clicked.connect(self.grid_navigate_up)
        nav_row.addWidget(self.grid_up_btn)
        self.grid_path_label = QLabel("No analysis yet")
        self.grid_path_label.setProperty("subtle", "true")
        self.grid_path_label.setWordWrap(True)
        nav_row.addWidget(self.grid_path_label, 1)
        t_lay.addLayout(nav_row)

        self.storage_grid = StorageGrid(self._theme)
        self.storage_grid.activated.connect(self.grid_navigate_into)
        self.storage_grid.selection_changed.connect(self._on_grid_selection)
        t_lay.addWidget(self.storage_grid, 1)

        self.grid_detail_label = QLabel(
            "Cell area is proportional to size. Double-click or press Enter to open a folder."
        )
        self.grid_detail_label.setProperty("subtle", "true")
        self.grid_detail_label.setWordWrap(True)
        t_lay.addWidget(self.grid_detail_label)

        up_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Backspace), self.storage_grid)
        up_shortcut.activated.connect(self.grid_navigate_up)

        self.content_stack.addWidget(grid_card)

        # 2. File Types Table
        types_card = QFrame()
        types_card.setProperty("card", "true")
        ty_lay = QVBoxLayout(types_card)
        ty_lay.setContentsMargins(8, 8, 8, 8)
        self.types_table = CrapTable(0, 4)
        self.types_table.setHorizontalHeaderLabels(
            ["File Category", "Total Reclaimable/Used", "File Count", "Storage Share (%)"]
        )
        self.types_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        ty_lay.addWidget(self.types_table)
        self.content_stack.addWidget(types_card)

        # 3. Old Files Table
        old_card = QFrame()
        old_card.setProperty("card", "true")
        old_lay = QVBoxLayout(old_card)
        old_lay.setContentsMargins(8, 8, 8, 8)
        self.old_table = CrapTable(0, 5)
        self.old_table.setHorizontalHeaderLabels(
            ["File Name", "Age (Days)", "Size", "Last Modified", "Path"]
        )
        self.old_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        old_lay.addWidget(self.old_table)
        self.content_stack.addWidget(old_card)

        # 4. VMs & Containers Table
        vm_card = QFrame()
        vm_card.setProperty("card", "true")
        vm_lay = QVBoxLayout(vm_card)
        vm_lay.setContentsMargins(8, 8, 8, 8)
        self.vm_table = CrapTable(0, 4)
        self.vm_table.setHorizontalHeaderLabels(
            ["Platform", "Virtual Disk / Container Path", "Size", "Optimization Guidance"]
        )
        self.vm_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        vm_lay.addWidget(self.vm_table)
        self.content_stack.addWidget(vm_card)

        root_lay.addWidget(self.content_stack, 1)
        self.refresh_health()

    def _reload_storage_favorites(self):
        settings = load_settings()
        favorites = settings.get("storage_favorites", []) or []
        current = self.favorite_combo.currentText() if hasattr(self, "favorite_combo") else ""
        if hasattr(self, "favorite_combo"):
            self.favorite_combo.blockSignals(True)
            self.favorite_combo.clear()
            self.favorite_combo.addItem("Favorites...")
            for path in favorites:
                self.favorite_combo.addItem(path)
            if current and current in favorites:
                self.favorite_combo.setCurrentText(current)
            else:
                self.favorite_combo.setCurrentIndex(0)
            self.favorite_combo.blockSignals(False)

    def _save_current_storage_favorite(self):
        path = self.path_edit.text().strip()
        if not path:
            return
        settings = load_settings()
        favorites = [p for p in (settings.get("storage_favorites", []) or []) if p]
        if path not in favorites:
            favorites.append(path)
            update_settings(storage_favorites=favorites)
        self._reload_storage_favorites()
        self.favorite_combo.setCurrentText(path)

    def _on_favorite_selected(self, text: str):
        if text and text != "Favorites...":
            self._apply_storage_preset(text)

    def _apply_storage_preset(self, path: str):
        if path and os.path.exists(path):
            self.path_edit.setText(path)
            self.refresh_health()

    def _on_drive_changed(self, text: str):
        if text:
            self.path_edit.setText(text if not is_windows() else f"{text}\\")
            self.refresh_health()

    def _browse_path(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Directory to Analyze", self.path_edit.text()
        )
        if folder:
            self.path_edit.setText(folder)
            self.refresh_health()

    def _set_active_section(self, section_key: str):
        for key, btn in self._section_buttons.items():
            btn.setProperty("active", "true" if key == section_key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        idx_map = {"TREE": 0, "TYPES": 1, "OLD": 2, "VMS": 3}
        self.content_stack.setCurrentIndex(idx_map.get(section_key, 0))

    def refresh_health(self, force: bool = False):
        from crapcleaner.gui.workers import HealthWorker, is_worker_running

        if is_worker_running(getattr(self, "_health_worker", None)):
            return

        self.health_info_label.setText("<b>Storage Device Health:</b> Checking...")
        _refresh_btn = getattr(self, "_refresh_health_btn", None)
        if _refresh_btn is not None:
            _refresh_btn.setEnabled(False)

        worker = HealthWorker(force_refresh=force, parent=self)
        self._health_worker = worker
        worker.done.connect(self._on_health_loaded)
        worker.failed.connect(
            lambda msg: self.health_info_label.setText(f"Unable to read health metrics: {msg}")
        )
        worker.finished.connect(
            lambda: (
                setattr(self, "_health_worker", None)
                if getattr(self, "_health_worker", None) is worker
                else None
            )
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_health_loaded(self, health_data: list):
        self._health_data = health_data
        _refresh_btn = getattr(self, "_refresh_health_btn", None)
        if _refresh_btn is not None:
            _refresh_btn.setEnabled(True)
        if not health_data:
            self.health_info_label.setText("<b>Storage Device Health:</b> No data available.")
            return
        curr_drive = ""
        if hasattr(self, "drive_combo") and self.drive_combo.currentText():
            curr_drive = self.drive_combo.currentText().strip().rstrip("\\").upper()
        elif hasattr(self, "path_edit") and self.path_edit.text():
            curr_drive = self.path_edit.text()[:2].rstrip("\\").upper()
        d = next(
            (
                item
                for item in health_data
                if item.device_id.upper().rstrip("\\") == curr_drive
                or item.device_id.upper().startswith(curr_drive)
            ),
            health_data[0],
        )
        trim_str = "Enabled" if d.trim_enabled else ("Supported" if d.trim_supported else "N/A")
        cap_str = format_size(d.capacity) if d.capacity else "N/A"
        free_str = f" · Free: {format_size(d.free_space)}" if d.free_space else ""
        self.health_info_label.setText(
            f"<b>Drive:</b> {d.device_id} ({d.model}) · <b>Type:</b> {d.media_type} ({d.bus_type})<br>"
            f"<b>Capacity:</b> {cap_str}{free_str} · <b>Status:</b> {d.health_status} · <b>TRIM:</b> {trim_str}"
        )

    def run_analysis(self):
        target_path = self.path_edit.text().strip()
        if not target_path or not os.path.exists(target_path):
            QMessageBox.warning(self, "Invalid Path", f"Target directory not found:\n{target_path}")
            return

        from crapcleaner.gui.workers import StorageAnalysisWorker, stop_worker

        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("Analyzing...")
        self.cancel_btn.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_label.setText("Starting analysis...")

        stop_worker(getattr(self, "_analysis_worker", None))

        depth = self.depth_spin.value()
        worker = StorageAnalysisWorker(target_path, depth, parent=self)
        self._analysis_worker = worker
        worker.tree_done.connect(self._on_tree_done)
        worker.tree_partial.connect(self._on_tree_partial)
        worker.types_done.connect(self._on_types_done)
        worker.old_done.connect(self._on_old_done)
        worker.vms_done.connect(self._on_vms_done)
        worker.progress.connect(self._on_analysis_progress)
        worker.finished_all.connect(self._on_analysis_done)
        worker.cancelled.connect(self._on_analysis_cancelled)
        worker.failed.connect(self._on_analysis_failed)
        worker.finished.connect(
            lambda: (
                setattr(self, "_analysis_worker", None)
                if getattr(self, "_analysis_worker", None) is worker
                else None
            )
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def closeEvent(self, event):
        from crapcleaner.gui.workers import stop_worker

        stop_worker(getattr(self, "_health_worker", None))
        stop_worker(getattr(self, "_analysis_worker", None))
        super().closeEvent(event)

    def _on_tree_done(self, root_node):
        self._current_node = root_node
        self._populate_tree(root_node)

    def _on_tree_partial(self, root_node):
        """Show the tree as it stands, so a large volume is not a blank wait.

        Skipped once the user has navigated into a folder: replacing the view they are
        reading, every second, would be worse than showing them nothing.
        """
        if self._grid_stack:
            return
        self._current_node = root_node
        self.storage_grid.set_node(root_node)
        self._update_grid_header()

    def _on_types_done(self, file_types):
        self._file_types_data = file_types
        self._populate_types(file_types)

    def _on_old_done(self, old_files):
        self._old_files_data = old_files
        self._populate_old_files(old_files)

    def _on_vms_done(self, vms):
        self._vm_data = vms
        self._populate_vms(vms)

    def _cancel_analysis(self):
        worker = getattr(self, "_analysis_worker", None)
        if worker is not None:
            worker.request_stop()
            self.cancel_btn.setEnabled(False)
            self.progress_label.setText("Stopping...")

    def _on_analysis_progress(self, stage: str, seen: int, where: str):
        # The directory is elided from the left so the meaningful tail stays readable.
        shown = where if len(where) <= 58 else "..." + where[-55:]
        self.progress_label.setText(f"{stage}: {seen:,} files · {shown}")

    def _reset_analysis_controls(self):
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze Storage")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(True)

    def _on_analysis_cancelled(self):
        self._reset_analysis_controls()
        self.progress_label.setText("Analysis cancelled. Partial results are shown.")

    def _on_analysis_done(self):
        self._reset_analysis_controls()
        self.progress_label.setVisible(False)

    def _on_analysis_failed(self, msg: str):
        self._reset_analysis_controls()
        self.progress_label.setText("Analysis failed.")
        QMessageBox.warning(self, "Analysis Error", f"Storage analysis failed:\n{msg}")

    def _populate_tree(self, root_node):
        self._grid_stack = []
        self.storage_grid.set_node(root_node)
        self._update_grid_header()

    def grid_navigate_into(self, node):
        if node is None:
            return
        if not node.children:
            QMessageBox.information(
                self,
                "No deeper detail",
                f"{node.name} was not expanded further.\n\n"
                "Raise the analysis depth, or analyze this folder directly, to drill deeper.",
            )
            return
        current = self.storage_grid.node()
        if current is not None:
            self._grid_stack.append(current)
        self.storage_grid.set_node(node)
        self._update_grid_header()

    def _expand_on_demand(self, node):
        """Measure a folder the initial pass stopped short of, on the user's request.

        The first analysis is depth-limited so it stays fast on a whole drive; the
        levels below it are measured only when someone actually navigates there, and
        each expanded folder is kept so a second visit costs nothing.
        """
        if not node.path or not os.path.isdir(node.path):
            QMessageBox.information(
                self, "No deeper detail", f"{node.name} has no sub-folders to show."
            )
            return
        if self._expand_worker is not None:
            return

        self.progress_label.setVisible(True)
        self.progress_label.setText(f"Measuring {node.name}…")
        from crapcleaner.gui.workers import StorageExpandWorker

        worker = StorageExpandWorker(node.path, depth=2, parent=self)
        self._expand_worker = worker
        worker.done.connect(lambda path, result: self._on_expanded(node, result))
        worker.failed.connect(self._on_expand_failed)
        worker.finished.connect(self._clear_expand_worker)
        worker.start()

    def _clear_expand_worker(self) -> None:
        self._expand_worker = None

    def _on_expand_failed(self, message: str):
        self.progress_label.setVisible(False)
        QMessageBox.warning(self, "Analysis Error", f"Could not measure that folder: {message}")

    def _on_expanded(self, node, result):
        self.progress_label.setVisible(False)
        if result is None or not result.children:
            QMessageBox.information(
                self, "No deeper detail", f"{node.name} has no sub-folders to show."
            )
            return
        node.children = result.children
        node.size = result.size or node.size
        node.file_count = result.file_count or node.file_count
        node.dir_count = result.dir_count or node.dir_count
        self.grid_navigate_into(node)

    def grid_navigate_up(self):
        if not self._grid_stack:
            return
        self.storage_grid.set_node(self._grid_stack.pop())
        self._update_grid_header()

    def _update_grid_header(self):
        node = self.storage_grid.node()
        self.grid_up_btn.setEnabled(bool(self._grid_stack))
        if node is None:
            self.grid_path_label.setText("No analysis yet")
            return
        self.grid_path_label.setText(
            f"<b>{node.path}</b> - {format_size(node.size)}, "
            f"{node.file_count:,} files in {node.dir_count:,} folders"
        )

    def _on_grid_selection(self, cell):
        if cell is None:
            self.grid_detail_label.setText(
                "Cell area is proportional to size. Double-click or press Enter to open a folder."
            )
            return
        detail = (
            f"<b>{cell.label}</b> - {format_size(cell.size)} ({cell.share:.1f}% of this folder)"
        )
        if cell.path:
            detail += f"<br>{cell.path}"
        self.grid_detail_label.setText(detail)

    def _populate_types(self, summaries):
        self.types_table.setRowCount(0)
        for s in summaries:
            row = self.types_table.rowCount()
            self.types_table.insertRow(row)
            self.types_table.setItem(row, 0, QTableWidgetItem(s.category))
            self.types_table.setItem(row, 1, NumericItem(format_size(s.total_size), s.total_size))
            self.types_table.setItem(row, 2, NumericItem(f"{s.file_count:,}", s.file_count))
            self.types_table.setItem(row, 3, NumericItem(f"{s.percentage:.1f}%", s.percentage))

    def _populate_old_files(self, old_items):
        self.old_table.setRowCount(0)
        for f in old_items:
            row = self.old_table.rowCount()
            self.old_table.insertRow(row)
            self.old_table.setItem(row, 0, QTableWidgetItem(f.name))
            self.old_table.setItem(row, 1, NumericItem(f"{f.age_days} days", f.age_days))
            self.old_table.setItem(row, 2, NumericItem(format_size(f.size), f.size))
            self.old_table.setItem(row, 3, QTableWidgetItem(f.last_modified.strftime("%Y-%m-%d")))
            self.old_table.setItem(row, 4, QTableWidgetItem(f.path))

    def _populate_vms(self, vm_items):
        self.vm_table.setRowCount(0)
        for item in vm_items:
            row = self.vm_table.rowCount()
            self.vm_table.insertRow(row)
            self.vm_table.setItem(row, 0, QTableWidgetItem(item.platform))
            self.vm_table.setItem(row, 1, QTableWidgetItem(item.path))
            self.vm_table.setItem(row, 2, NumericItem(format_size(item.size), item.size))
            self.vm_table.setItem(row, 3, QTableWidgetItem(item.guidance))

    def _export_report(self):
        if not self._current_node:
            QMessageBox.information(
                self, "Export Report", "Please run an analysis before exporting."
            )
            return
        dest, sel_filter = QFileDialog.getSaveFileName(
            self,
            "Export Storage Report",
            os.path.join(os.path.expanduser("~"), "crapcleaner_storage_report.json"),
            "JSON Report (*.json);;CSV Report (*.csv);;Text Report (*.txt)",
        )
        if not dest:
            return
        fmt = "json"
        if dest.endswith(".csv"):
            fmt = "csv"
        elif dest.endswith(".txt"):
            fmt = "txt"
        try:
            export_report(
                self._current_node, report_type="storage", export_format=fmt, output_path=dest
            )
            QMessageBox.information(
                self, "Export Complete", f"Report saved successfully to:\n{dest}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "Export Error", str(exc))

    def apply_theme(self, theme: str):
        self._theme = theme
        self.storage_grid.apply_theme(theme)
