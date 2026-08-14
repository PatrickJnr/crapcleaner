"""Tab views for the CrapCleaner main window."""

import csv
import json
import os
import shutil
import subprocess

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.config.settings import config_path, load_settings, save_settings
from crapcleaner.constants import DEFAULT_CONFIG
from crapcleaner.gui.dialogs import (
    ConfirmDeleteDialog,
    DuplicateFilesDialog,
    ReportDialog,
)
from crapcleaner.gui.theme import color as theme_color
from crapcleaner.history.store import clear as clear_history
from crapcleaner.history.store import load as load_history
from crapcleaner.models.category import SafetyLevel
from crapcleaner.models.report import ScanReport
from crapcleaner.registry import get_all_categories
from crapcleaner.utils.format import (
    format_datetime,
    format_duration,
    format_size,
    parse_size,
)
from crapcleaner.utils.platform import (
    get_drive_info,
    get_user_profile,
    is_admin,
    is_windows,
    list_drives,
)

_MAX_LARGE_FILE_ROWS = 500
_MAX_DUPLICATE_GROUP_ROWS = 150
_MAX_DUPLICATE_TOOLTIP_FILES = 20


def _c(theme: str, name: str) -> str:
    return theme_color(theme, name)


def _safety_color(theme: str, safety: SafetyLevel) -> str:
    return {
        SafetyLevel.SAFE: _c(theme, "success"),
        SafetyLevel.LOW_RISK: _c(theme, "warning"),
        SafetyLevel.REVIEW: _c(theme, "review"),
        SafetyLevel.DANGEROUS: _c(theme, "danger"),
    }[safety]


def page_header(title: str, subtitle: str = "") -> QWidget:
    """Consistent page header used across all main views."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    title_label = QLabel(title)
    title_label.setProperty("pageTitle", "true")
    layout.addWidget(title_label)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setProperty("pageSubtitle", "true")
        sub.setWordWrap(True)
        layout.addWidget(sub)
    return widget


def badge(text: str, level: str = "") -> QLabel:
    """Small pill label used for status and safety markers."""
    label = QLabel(text)
    label.setProperty("badge", "true")
    if level:
        label.setProperty("level", level)
    return label


def section_label(text: str) -> QLabel:
    """Uppercase section heading used inside cards."""
    label = QLabel(text)
    label.setProperty("section", "true")
    return label


def stat_card(
    title: str, value: str = "--", subtitle: str = "", theme: str = "dark"
) -> tuple[QFrame, QLabel, QLabel]:
    """Reusable metric card component."""
    card = QFrame()
    card.setProperty("statCard", "true")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(5)

    t_lbl = QLabel(title)
    t_lbl.setProperty("section", "true")

    v_lbl = QLabel(value)
    v_lbl.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {_c(theme, 'text')};")

    s_lbl = QLabel(subtitle)
    s_lbl.setProperty("subtle", "true")
    s_lbl.setStyleSheet(f"font-size: 11px; color: {_c(theme, 'muted')};")

    lay.addWidget(t_lbl)
    lay.addWidget(v_lbl)
    lay.addWidget(s_lbl)
    return card, v_lbl, s_lbl


class NumericItem(QTableWidgetItem):
    """Table item that sorts by a numeric value stored in UserRole."""

    def __init__(self, text: str = "", value=None):
        super().__init__(text)
        if value is not None:
            self.setData(Qt.ItemDataRole.UserRole, value)

    def __lt__(self, other):
        a = self.data(Qt.ItemDataRole.UserRole)
        b = other.data(Qt.ItemDataRole.UserRole)
        if a is not None and b is not None and a != b:
            return a < b
        return super().__lt__(other)


class CrapTable(QTableWidget):
    """Table with a centered placeholder label shown while it is empty."""

    def __init__(self, rows=0, cols=0, parent=None):
        super().__init__(rows, cols, parent)
        self._empty_text = ""
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(32)
        self._placeholder = QLabel(self.viewport())
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._placeholder.hide()

    def set_empty_text(self, theme: str, text: str):
        self._empty_text = text
        self._placeholder.setText(text)
        self._placeholder.setStyleSheet(
            f"color: {_c(theme, 'muted')}; font-size: 13px; padding: 24px;"
        )
        self.refresh_placeholder()

    def refresh_placeholder(self):
        if not self._empty_text or self.rowCount() > 0:
            self._placeholder.hide()
        else:
            self._placeholder.setGeometry(self.viewport().rect())
            self._placeholder.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._placeholder.setGeometry(self.viewport().rect())


class StorageDonut(QWidget):
    """High-DPI circular used/free ring shown on the dashboard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fraction = 0.0
        self._theme = "dark"
        self.setFixedSize(148, 148)

    def set_usage(self, fraction: float, theme: str):
        self._fraction = max(0.0, min(1.0, fraction))
        self._theme = theme
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        from crapcleaner.gui.theme import palette_for

        pal = palette_for(self._theme)
        pen_width = 12.0
        rect = QRectF(self.rect()).adjusted(12, 12, -12, -12)

        # Background track
        painter.setPen(
            QPen(
                QColor(pal["border2"]),
                pen_width,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        painter.drawArc(rect, 0, 360 * 16)

        pct = int(self._fraction * 100)
        if pct > 85:
            fill_color = pal["danger"]
        elif pct >= 70:
            fill_color = pal["warning"]
        else:
            fill_color = pal["accent"]

        if self._fraction > 0.001:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0.0, QColor(fill_color))
            gradient.setColorAt(1.0, QColor(pal["accent_hover"]))
            painter.setPen(
                QPen(
                    QBrush(gradient),
                    pen_width,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
            )
            span = int(-self._fraction * 360 * 16)
            painter.drawArc(rect, 90 * 16, span)

        # Centered text
        font = QFont(self.font())
        font.setPointSize(18)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(pal["text"]))
        painter.drawText(
            self.rect().adjusted(0, -10, 0, 0), Qt.AlignmentFlag.AlignCenter, f"{pct}%"
        )
        font.setPointSize(9)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(pal["muted"]))
        painter.drawText(
            self.rect().adjusted(0, 18, 0, 0),
            Qt.AlignmentFlag.AlignCenter,
            "used space",
        )


class DriveCard(QFrame):
    """Compact clickable card showing one drive's usage."""

    clicked = Signal(str)

    def __init__(self, drive: str, parent=None):
        super().__init__(parent)
        self.drive = drive
        self._theme = "dark"
        self.setObjectName("DriveCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", "false")
        self.setFixedWidth(184)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        top_row = QHBoxLayout()
        self.title = QLabel(f"Drive {drive}" if is_windows() else drive)
        font = self.title.font()
        font.setPointSize(13)
        font.setBold(True)
        self.title.setFont(font)
        top_row.addWidget(self.title)
        top_row.addStretch(1)

        self.type_badge = QLabel(
            "SYSTEM"
            if (
                drive.upper().startswith("C")
                if is_windows()
                else drive in ("/", "/boot", "/boot/efi")
            )
            else "LOCAL"
        )
        self.type_badge.setProperty("badge", "true")
        self.type_badge.setStyleSheet("font-size: 9px; padding: 1px 5px;")
        top_row.addWidget(self.type_badge)
        lay.addLayout(top_row)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        lay.addWidget(self.bar)

        self.used_label = QLabel("Used: --")
        self.free_label = QLabel("Free: --")
        self.total_label = QLabel("Total: --")
        for lbl in (self.used_label, self.free_label, self.total_label):
            lbl.setStyleSheet(f"font-size: 11px; color: {_c(self._theme, 'muted')};")
            lay.addWidget(lbl)

    def _show_menu(self, pos):
        menu = QMenu(self)
        open_action = menu.addAction("Open in File Explorer")
        action = menu.exec(self.mapToGlobal(pos))
        if action == open_action:
            if is_windows():
                path = f"{self.drive}\\"
                if os.path.exists(path):
                    subprocess.Popen(["explorer", path])
            elif os.path.exists(self.drive):
                subprocess.Popen(["xdg-open", self.drive])

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit(self.drive)
        super().mouseReleaseEvent(event)

    def set_data(self, info):
        if info is None:
            self.total_label.setText("Total: --")
            self.used_label.setText("Used: --")
            self.free_label.setText("Free: --")
            self.bar.setValue(0)
            return
        self.total_label.setText(f"Total: {format_size(info['total'])}")
        self.used_label.setText(f"Used: {format_size(info['used'])}")
        self.free_label.setText(f"Free: {format_size(info['free'])}")
        pct = int(info["used"] / info["total"] * 100) if info["total"] else 0
        self.bar.setValue(pct)
        self.bar.setProperty("good", pct < 70)
        self.bar.setProperty("warn", 70 <= pct <= 85)
        self.bar.setProperty("bad", pct > 85)
        self.bar.style().unpolish(self.bar)
        self.bar.style().polish(self.bar)

    def set_selected(self, selected: bool):
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def apply_theme(self, theme: str):
        self._theme = theme
        muted = _c(theme, "muted")
        for lbl in (self.used_label, self.free_label, self.total_label):
            lbl.setStyleSheet(f"font-size: 11px; color: {muted};")


class DashboardView(QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._theme = "dark"
        self._used_fraction = 0.0
        self._build()

    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(14)
        layout.addWidget(
            page_header(
                "System Overview & Health",
                "Inspect disk storage, identify junk, and safely reclaim gigabytes in seconds.",
            )
        )

        # Top row: Hero banner & Storage Donut
        content = QHBoxLayout()
        content.setSpacing(14)

        hero = QFrame()
        hero.setProperty("card", "true")
        hero_lay = QVBoxLayout(hero)
        hero_lay.setContentsMargins(22, 20, 22, 20)
        hero_lay.setSpacing(8)

        hero_top = QHBoxLayout()
        hero_top.addWidget(section_label("Potential Reclaimable Space"))
        hero_top.addStretch(1)
        self.status_badge = badge("Ready to scan", "accent")
        hero_top.addWidget(self.status_badge)
        hero_lay.addLayout(hero_top)

        self.reclaimable_label = QLabel("Not scanned yet")
        self.reclaimable_label.setProperty("heroValue", "true")
        self.reclaimable_label.setStyleSheet(
            f"font-size: 32px; font-weight: 800; color: {_c(self._theme, 'text')};"
        )
        hero_lay.addWidget(self.reclaimable_label)

        self.last_scan_label = QLabel("Last scan: never")
        self.last_cleanup_label = QLabel("Last cleanup: never")
        for lbl in (self.last_scan_label, self.last_cleanup_label):
            lbl.setProperty("subtle", "true")
            hero_lay.addWidget(lbl)

        hero_lay.addSpacing(6)
        self.admin_label = QLabel()
        self.admin_label.setWordWrap(True)
        self.admin_label.setProperty("subtle", "true")
        hero_lay.addWidget(self.admin_label)

        hero_lay.addSpacing(10)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.scan_button = QPushButton("Scan for Crap")
        self.scan_button.setProperty("primary", "true")
        self.scan_button.setFixedHeight(34)
        self.scan_button.clicked.connect(self._main.start_scan)

        self.cancel_button = QPushButton("Cancel Scan")
        self.cancel_button.setFixedHeight(34)
        self.cancel_button.hide()
        self.cancel_button.clicked.connect(self._cancel_scan)

        self.review_button = QPushButton("Review && Clean")
        self.review_button.setProperty("danger", "true")
        self.review_button.setFixedHeight(34)
        self.review_button.setEnabled(False)
        self.review_button.setToolTip("Go to Cleanup with safe categories pre-selected.")
        self.review_button.clicked.connect(self._main.review_and_clean)

        buttons.addWidget(self.scan_button)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.review_button)
        buttons.addStretch(1)
        hero_lay.addLayout(buttons)

        self.scan_progress = QProgressBar()
        self.scan_progress.setRange(0, 100)
        self.scan_progress.setValue(0)
        self.scan_progress.setTextVisible(True)
        self.scan_progress.setFormat("Scanning...")
        self.scan_progress.setFixedHeight(22)
        self.scan_progress.setVisible(False)
        hero_lay.addWidget(self.scan_progress)

        content.addWidget(hero, 1)

        donut_card = QFrame()
        donut_card.setProperty("card", "true")
        donut_card.setFixedWidth(260)
        donut_lay = QVBoxLayout(donut_card)
        donut_lay.setContentsMargins(18, 16, 18, 16)
        donut_lay.setSpacing(6)
        donut_lay.addWidget(section_label("Selected Drive Usage"))
        donut_lay.addSpacing(4)
        self.donut = StorageDonut()
        donut_lay.addWidget(self.donut, 0, Qt.AlignmentFlag.AlignCenter)
        self.drive_detail = QLabel()
        self.drive_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drive_detail.setWordWrap(True)
        self.drive_detail.setProperty("subtle", "true")
        donut_lay.addWidget(self.drive_detail)
        content.addWidget(donut_card, 0, Qt.AlignmentFlag.AlignTop)

        layout.addLayout(content)

        # Middle: 4 Quick Stat Cards
        layout.addWidget(section_label("System Metrics & Categories"))
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)

        self.c1, self.c1_val, self.c1_sub = stat_card(
            "Safe Caches", "--", "Temporary files & browser caches", self._theme
        )
        self.c2, self.c2_val, self.c2_sub = stat_card(
            "Dev & AI Caches", "--", "Python, Docker & AI models", self._theme
        )
        self.c3, self.c3_val, self.c3_sub = stat_card(
            "Drives Detected", "--", "Monitored storage volumes", self._theme
        )
        self.c4, self.c4_val, self.c4_sub = stat_card(
            "Lifetime Cleaned", "--", "Recovered across sessions", self._theme
        )

        stats_row.addWidget(self.c1)
        stats_row.addWidget(self.c2)
        stats_row.addWidget(self.c3)
        stats_row.addWidget(self.c4)
        layout.addLayout(stats_row)

        # Bottom: Drives carousel
        layout.addWidget(section_label("Drives & Partitions"))

        self.drives = [d.rstrip("\\") if is_windows() else d for d in list_drives()]
        self._selected_drive = self.drives[0] if self.drives else ("C:" if is_windows() else "/")
        self._cards = {}

        cards_scroll = QScrollArea()
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        cards_scroll.setFixedHeight(150)
        cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        cards_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        cards_container = QWidget()
        cards_row = QHBoxLayout(cards_container)
        cards_row.setContentsMargins(0, 0, 0, 0)
        cards_row.setSpacing(12)
        for drive in self.drives:
            card = DriveCard(drive)
            card.clicked.connect(self._select_drive)
            cards_row.addWidget(card)
            self._cards[drive] = card
        cards_row.addStretch(1)
        cards_scroll.setWidget(cards_container)
        layout.addWidget(cards_scroll)

        scroll.setWidget(container)
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.addWidget(scroll)

    def _cancel_scan(self):
        if hasattr(self._main, "cancel_active_scan"):
            self._main.cancel_active_scan()

    def refresh(self):
        for drive, card in self._cards.items():
            try:
                card.set_data(get_drive_info(drive))
            except OSError:
                card.set_data(None)
        self._select_drive(self._selected_drive)
        self.admin_label.setText(
            "Running with Administrator privileges."
            if is_admin()
            else "Running as Standard User. Some system categories may require elevation."
        )
        self.admin_label.setStyleSheet(
            f"color: {_c(self._theme, 'success' if is_admin() else 'muted')}; font-size: 12px;"
        )

        # Update metrics
        self.c3_val.setText(f"{len(self.drives)} Drives")
        self.c3_sub.setText(f"Active: {self._selected_drive}")

        entries = load_history()
        total_rec = sum(e.space_recovered for e in entries if not e.dry_run)
        self.c4_val.setText(format_size(total_rec))
        self.c4_sub.setText(f"{len(entries)} total actions logged")

    def _select_drive(self, drive: str):
        if drive not in self._cards:
            return
        self._selected_drive = drive
        for d, card in self._cards.items():
            card.set_selected(d == drive)
        try:
            info = get_drive_info(drive)
            total = info["total"]
            self._used_fraction = info["used"] / total if total else 0.0
            self.donut.set_usage(self._used_fraction, self._theme)
            label = str(info.get("label", ""))
            fs_name = str(info.get("filesystem", ""))
            extra = []
            if label:
                extra.append(label)
            if fs_name:
                extra.append(fs_name)
            extra_line = (
                f"<br><span style='font-size:11px'>{' · '.join(extra)}</span>" if extra else ""
            )
            self.drive_detail.setText(
                f"<b>{drive}</b><br>"
                f"Used: {format_size(info['used'])} · Free: {format_size(info['free'])} · Total: {format_size(info['total'])}"
                f"{extra_line}"
            )
        except OSError:
            self._used_fraction = 0.0
            self.donut.set_usage(0.0, self._theme)
            self.drive_detail.setText(f"{drive}<br>Unavailable")
        self.drive_detail.setStyleSheet(f"color: {_c(self._theme, 'muted')};")

    def set_scan(self, report: ScanReport):
        self.reclaimable_label.setText(format_size(report.total_size))
        categories = [r for r in report.results if r.size > 0]
        self.last_scan_label.setText(
            f"Last scan: {format_datetime(report.started)} · {len(categories)} categories identified"
        )
        self.status_badge.setText("Scan Complete")
        self.status_badge.setProperty("level", "safe" if report.total_size > 0 else "accent")
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

        safe_total = sum(r.size for r in report.results if r.safety_level in ("SAFE", "LOW_RISK"))
        self.c1_val.setText(format_size(safe_total))

        dev_total = sum(
            r.size
            for r in report.results
            if r.group in ("Python", "Node.js", ".NET", "Developer tools", "AI", "Docker")
        )
        self.c2_val.setText(format_size(dev_total))
        self.review_button.setEnabled(report.total_size > 0)

    def set_cleanup(self, text: str):
        self.last_cleanup_label.setText(f"Last cleanup: {text}")

    def set_scanning(self, scanning: bool):
        self.scan_button.setEnabled(not scanning)
        self.cancel_button.setVisible(scanning)
        if scanning:
            self.review_button.setEnabled(False)
            self.scan_progress.setRange(0, 100)
            self.scan_progress.setValue(0)
            self.scan_progress.setFormat("Scanning system...")
            self.scan_progress.setVisible(True)
            self.status_badge.setText("Scanning...")
            self.status_badge.setProperty("level", "warn")
        else:
            self.scan_progress.setVisible(False)
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    def set_scan_progress(self, name: str, pct: int):
        if pct < 0:
            self.scan_progress.setRange(0, 0)
            self.scan_progress.setFormat(f"Scanning: {name}")
        else:
            self.scan_progress.setRange(0, 100)
            self.scan_progress.setValue(pct)
            self.scan_progress.setFormat(f"Scanning: {name} ({pct}%)")
        self.scan_progress.setVisible(True)

    def apply_theme(self, theme: str):
        self._theme = theme
        for card in self._cards.values():
            card.apply_theme(theme)
        self.drive_detail.setStyleSheet(f"color: {_c(theme, 'muted')};")
        self.donut.set_usage(self._used_fraction, theme)


class CleanupView(QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._categories: list = []
        self._scanning = False
        self._theme = "dark"
        self._touched = set()
        self._last_checked = set()
        self._safety_filter = "ALL"
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)
        layout.addWidget(
            page_header(
                "Cleanup Manager",
                "Select categories to clean. Safe items are pre-selected. Dangerous categories are protected.",
            )
        )

        # Primary toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.scan_button = QPushButton("Scan Now")
        self.scan_button.setProperty("primary", "true")
        self.scan_button.clicked.connect(self._main.start_scan)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.hide()
        self.cancel_button.clicked.connect(
            lambda: (
                self._main.cancel_active_scan()
                if hasattr(self._main, "cancel_active_scan")
                else None
            )
        )

        self.safe_button = QPushButton("Select Safe")
        self.safe_button.clicked.connect(lambda: self._select_by_safety(True))

        self.all_button = QPushButton("Select All")
        self.all_button.clicked.connect(lambda: self._select_all(True))

        self.none_button = QPushButton("Deselect All")
        self.none_button.clicked.connect(lambda: self._select_all(False))

        self.invert_button = QPushButton("Invert")
        self.invert_button.clicked.connect(self._invert_selection)

        toolbar.addWidget(self.scan_button)
        toolbar.addWidget(self.cancel_button)
        toolbar.addWidget(self.safe_button)
        toolbar.addWidget(self.all_button)
        toolbar.addWidget(self.none_button)
        toolbar.addWidget(self.invert_button)
        toolbar.addStretch(1)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search categories (Ctrl+F)...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(220)
        self.search_edit.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.search_edit)
        layout.addLayout(toolbar)

        # Filter chips & Expand/Collapse row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self._chip_buttons = {}
        chips = [
            ("ALL", "All"),
            ("SAFE", "Safe Only"),
            ("LOW_RISK", "Low Risk"),
            ("REVIEW", "Review Required"),
            ("ADMIN", "Requires Admin"),
        ]
        for key, text in chips:
            btn = QPushButton(text)
            btn.setProperty("chip", "true")
            btn.setProperty("active", "true" if key == "ALL" else "false")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self._set_safety_filter(k))
            filter_row.addWidget(btn)
            self._chip_buttons[key] = btn

        filter_row.addStretch(1)

        exp_btn = QPushButton("Expand All")
        exp_btn.setProperty("ghost", "true")
        exp_btn.clicked.connect(self.tree_expand_all)
        col_btn = QPushButton("Collapse All")
        col_btn.setProperty("ghost", "true")
        col_btn.clicked.connect(self.tree_collapse_all)
        filter_row.addWidget(exp_btn)
        filter_row.addWidget(col_btn)

        layout.addLayout(filter_row)

        shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut.activated.connect(self.search_edit.setFocus)

        # Category Tree
        tree_card = QFrame()
        tree_card.setProperty("card", "true")
        tree_card_lay = QVBoxLayout(tree_card)
        tree_card_lay.setContentsMargins(8, 8, 8, 8)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Category", "Safety Level", "Item Count", "Reclaimable Size"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setIndentation(18)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_menu)
        self.tree.itemClicked.connect(self._on_group_clicked)
        self.tree.itemChanged.connect(self._on_item_changed)
        tree_card_lay.addWidget(self.tree)
        layout.addWidget(tree_card, 1)

        # Floating / Sticky Summary Footer
        summary_card = QFrame()
        summary_card.setProperty("card", "true")
        summary_lay = QHBoxLayout(summary_card)
        summary_lay.setContentsMargins(18, 12, 18, 12)
        summary_lay.setSpacing(12)

        self.clean_button = QPushButton("Clean Selected")
        self.clean_button.setProperty("danger", "true")
        self.clean_button.setEnabled(False)
        self.clean_button.setFixedHeight(36)
        self.clean_button.setFixedWidth(160)
        self.clean_button.clicked.connect(self._main.clean_selected)
        summary_lay.addWidget(self.clean_button)

        self.summary_label = QLabel("Run a scan to calculate reclaimable space.")
        self.summary_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        summary_lay.addWidget(self.summary_label, 1)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(8)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(180)
        self.progress_bar.setVisible(False)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {_c(self._theme, 'muted')}; font-size: 12px;")
        progress_row.addWidget(self.progress_bar)
        progress_row.addWidget(self.status_label)
        summary_lay.addLayout(progress_row)

        layout.addWidget(summary_card)

    def tree_expand_all(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item is not None:
                item.setExpanded(True)

    def tree_collapse_all(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item is not None:
                item.setExpanded(False)

    def _set_safety_filter(self, filter_key: str):
        self._safety_filter = filter_key
        for k, btn in self._chip_buttons.items():
            active = k == filter_key
            btn.setProperty("active", "true" if active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._apply_filter(self.search_edit.text())

    def _show_tree_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        category = item.data(0, Qt.ItemDataRole.UserRole)
        menu = QMenu(self)

        if category is not None:
            toggle_action = menu.addAction("Toggle Selection")
            copy_action = menu.addAction("Copy Category Name")
            open_folder_action = None
            if category.targets:
                first_target = category.targets[0].path
                if os.path.exists(first_target):
                    open_folder_action = menu.addAction("Open Target in File Explorer")

            action = menu.exec(self.tree.viewport().mapToGlobal(pos))
            if action == toggle_action and (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                cur = item.checkState(0)
                item.setCheckState(
                    0,
                    (
                        Qt.CheckState.Unchecked
                        if cur == Qt.CheckState.Checked
                        else Qt.CheckState.Checked
                    ),
                )
            elif action == copy_action:
                QApplication.clipboard().setText(category.name)
            elif open_folder_action and action == open_folder_action:
                target_path = category.targets[0].path
                if os.path.isdir(target_path):
                    subprocess.Popen(["explorer", target_path])
                else:
                    subprocess.Popen(["explorer", "/select,", target_path])

    def _set_children_checked(self, group_item, checked: bool):
        self.tree.blockSignals(True)
        try:
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                if not (child.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                    continue
                child.setCheckState(
                    0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                )
        finally:
            self.tree.blockSignals(False)

    def _on_group_clicked(self, item, column):
        if column != 0:
            return
        if item.data(0, Qt.ItemDataRole.UserRole) is not None or item.childCount() == 0:
            return
        checked = item.checkState(0) == Qt.CheckState.Checked
        self._set_children_checked(item, checked)
        self._sync_group_state(item)
        self._update_summary()

    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        if column != 0:
            return
        if item.data(0, Qt.ItemDataRole.UserRole) is None:
            return
        category = item.data(0, Qt.ItemDataRole.UserRole)
        self._touched.add(category.id)
        if item.checkState(0) == Qt.CheckState.Checked:
            self._last_checked.add(category.id)
        else:
            self._last_checked.discard(category.id)
        parent = item.parent()
        if parent is not None:
            self._sync_group_state(parent)
        self._update_summary()

    def _sync_group_state(self, group_item):
        checked = unchecked = 0
        for j in range(group_item.childCount()):
            child = group_item.child(j)
            if not (child.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                continue
            state = child.checkState(0)
            if state == Qt.CheckState.Checked:
                checked += 1
            elif state == Qt.CheckState.Unchecked:
                unchecked += 1
            else:
                group_item.setCheckState(0, Qt.CheckState.PartiallyChecked)
                return
        if checked and not unchecked:
            group_item.setCheckState(0, Qt.CheckState.Checked)
        elif unchecked and not checked:
            group_item.setCheckState(0, Qt.CheckState.Unchecked)
        else:
            group_item.setCheckState(0, Qt.CheckState.PartiallyChecked)

    def _select_by_safety(self, recommended_only: bool = False):
        self.tree.blockSignals(True)
        try:
            for i in range(self.tree.topLevelItemCount()):
                group = self.tree.topLevelItem(i)
                if group is None:
                    continue
                for j in range(group.childCount()):
                    child = group.child(j)
                    if child is None:
                        continue
                    category = child.data(0, Qt.ItemDataRole.UserRole)
                    if category is None:
                        continue
                    if recommended_only:
                        check = (
                            category.safety_level in (SafetyLevel.SAFE, SafetyLevel.LOW_RISK)
                            and category.selected_by_default
                        )
                    else:
                        check = True
                    child.setCheckState(
                        0, Qt.CheckState.Checked if check else Qt.CheckState.Unchecked
                    )
                self._sync_group_state(group)
        finally:
            self.tree.blockSignals(False)
        self._update_summary()

    def _select_all(self, selected: bool):
        for category in self._categories:
            if category.safety_level != SafetyLevel.DANGEROUS:
                self._set_category_checked(category, selected)

    def _invert_selection(self):
        self.tree.blockSignals(True)
        try:
            for i in range(self.tree.topLevelItemCount()):
                group = self.tree.topLevelItem(i)
                if group is None:
                    continue
                for j in range(group.childCount()):
                    child = group.child(j)
                    if child is not None and (child.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                        cur = child.checkState(0)
                        child.setCheckState(
                            0,
                            (
                                Qt.CheckState.Unchecked
                                if cur == Qt.CheckState.Checked
                                else Qt.CheckState.Checked
                            ),
                        )
                self._sync_group_state(group)
        finally:
            self.tree.blockSignals(False)
        self._update_summary()

    def review_recommended(self):
        """Pre-check the safe and low-risk categories, leaving dangerous ones locked."""
        self._select_by_safety(True)
        self.tree.scrollToTop()

    def _set_category_checked(self, category, checked: bool):
        item = self._item_for_category(category)
        if item is not None:
            item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _item_for_category(self, category):
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            if group is None:
                continue
            for j in range(group.childCount()):
                child = group.child(j)
                if child is not None and child.data(0, Qt.ItemDataRole.UserRole) is category:
                    return child
        return None

    def _find_category_item(self, name: str):
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            if group is None:
                continue
            for j in range(group.childCount()):
                child = group.child(j)
                if child is not None:
                    category = child.data(0, Qt.ItemDataRole.UserRole)
                    if category is not None and category.name == name:
                        return child
        return None

    def populate(self, categories):
        self._categories = categories
        self.tree.blockSignals(True)
        try:
            self.tree.clear()
            groups: dict = {}
            for category in categories:
                groups.setdefault(category.group, []).append(category)

            for group_name, members in groups.items():
                group_item = QTreeWidgetItem([group_name])
                group_item.setFlags(
                    group_item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable & ~Qt.ItemFlag.ItemIsAutoTristate
                )
                group_item.setCheckState(0, Qt.CheckState.Unchecked)
                for category in members:
                    safety = category.safety_level
                    item = QTreeWidgetItem()
                    item.setText(1, safety.label)
                    item.setText(2, str(category.item_count) if category.item_count else "")
                    item.setText(3, format_size(category.size) if category.size else "")
                    color = QColor(_safety_color(self._theme, safety))
                    item.setForeground(1, color)
                    item.setToolTip(0, category.description)
                    item.setToolTip(1, category.description)
                    item.setData(0, Qt.ItemDataRole.UserRole, category)
                    if safety == SafetyLevel.DANGEROUS:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                        item.setForeground(0, QColor(_c(self._theme, "danger")))
                        item.setCheckState(0, Qt.CheckState.Unchecked)
                    else:
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        if category.id in self._touched:
                            state = (
                                Qt.CheckState.Checked
                                if category.id in self._last_checked
                                else Qt.CheckState.Unchecked
                            )
                        else:
                            state = (
                                Qt.CheckState.Checked
                                if category.selected_by_default and category.size > 0
                                else Qt.CheckState.Unchecked
                            )
                        item.setCheckState(0, state)
                    item.setText(
                        0,
                        category.name + ("  [requires admin]" if category.requires_admin else ""),
                    )
                    group_item.addChild(item)
                self._sync_group_state(group_item)
                self.tree.addTopLevelItem(group_item)
                group_item.setExpanded(True)
        finally:
            self.tree.blockSignals(False)
        self._apply_filter(self.search_edit.text() if hasattr(self, "search_edit") else "")
        for col in range(4):
            self.tree.resizeColumnToContents(col)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._update_summary()

    def _auto_check_defaults(self):
        updated_groups = set()
        self.tree.blockSignals(True)
        try:
            for i in range(self.tree.topLevelItemCount()):
                group = self.tree.topLevelItem(i)
                if group is None:
                    continue
                for j in range(group.childCount()):
                    child = group.child(j)
                    if child is None:
                        continue
                    category = child.data(0, Qt.ItemDataRole.UserRole)
                    if category is None or category.id in self._touched:
                        continue
                    if (
                        category.selected_by_default
                        and category.size > 0
                        and child.checkState(0) != Qt.CheckState.Checked
                    ):
                        child.setCheckState(0, Qt.CheckState.Checked)
                        updated_groups.add(group)
        finally:
            self.tree.blockSignals(False)
        for group in updated_groups:
            self._sync_group_state(group)

    def update_sizes(self):
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            if group is None:
                continue
            group_total = 0
            for j in range(group.childCount()):
                child = group.child(j)
                if child is None:
                    continue
                category = child.data(0, Qt.ItemDataRole.UserRole)
                if category is None:
                    continue
                child.setText(2, str(category.item_count) if category.item_count else "")
                child.setText(3, format_size(category.size) if category.size else "")
                group_total += category.size
            group.setText(2, f"{group.childCount()} categories")
            group.setText(3, format_size(group_total) if group_total else "")
        self._auto_check_defaults()
        for col in range(4):
            self.tree.resizeColumnToContents(col)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._update_summary()

    def selected_categories(self):
        selected = []
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            if group is None:
                continue
            for j in range(group.childCount()):
                child = group.child(j)
                if child is not None and child.checkState(0) == Qt.CheckState.Checked:
                    category = child.data(0, Qt.ItemDataRole.UserRole)
                    if category is not None:
                        selected.append(category)
        return selected

    def _apply_filter(self, text: str):
        text = (text or "").strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            if group is None:
                continue
            visible = 0
            for j in range(group.childCount()):
                child = group.child(j)
                if child is None:
                    continue
                cat = child.data(0, Qt.ItemDataRole.UserRole)
                match_text = (
                    not text or text in child.text(0).lower() or text in child.text(1).lower()
                )

                match_safety = True
                if self._safety_filter == "SAFE":
                    match_safety = cat is not None and cat.safety_level == SafetyLevel.SAFE
                elif self._safety_filter == "LOW_RISK":
                    match_safety = cat is not None and cat.safety_level == SafetyLevel.LOW_RISK
                elif self._safety_filter == "REVIEW":
                    match_safety = cat is not None and cat.safety_level == SafetyLevel.REVIEW
                elif self._safety_filter == "ADMIN":
                    match_safety = cat is not None and cat.requires_admin

                match = match_text and match_safety
                child.setHidden(not match)
                if match:
                    visible += 1
            group.setHidden(visible == 0)

    def _update_summary(self):
        selected = self.selected_categories()
        total = sum(c.size for c in selected)
        self.clean_button.setEnabled(bool(selected) and total > 0)
        self.summary_label.setText(
            f"<b>{len(selected)} categories</b> selected — Estimated space recovery: "
            f"<b style='color: {_c(self._theme, 'accent')};'>{format_size(total)}</b>"
        )

    def set_scanning(self, scanning: bool):
        self._scanning = scanning
        self.scan_button.setEnabled(not scanning)
        self.cancel_button.setVisible(scanning)
        if scanning:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setVisible(True)
            self.status_label.setText("Scanning categories...")
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_bar.setVisible(False)
            self.status_label.setText("")

    def highlight_category(self, name: str):
        self.clear_highlight()
        item = self._find_category_item(name)
        if item is None:
            return
        base = QColor(_c(self._theme, "selection"))
        base.setAlpha(50)
        for col in range(self.tree.columnCount()):
            item.setBackground(col, QBrush(base))
        self.tree.scrollToItem(item)

    def clear_highlight(self):
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            if group is None:
                continue
            for j in range(group.childCount()):
                child = group.child(j)
                if child is not None:
                    for col in range(self.tree.columnCount()):
                        child.setBackground(col, QBrush())

    def set_cleaning(self, cleaning: bool, total: int = 1):
        self.clean_button.setEnabled(not cleaning)
        if cleaning:
            self.progress_bar.setRange(0, max(total, 1))
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)

    def set_clean_progress(self, name: str, index: int):
        self.progress_bar.setValue(index)
        self.status_label.setText(f"Cleaning: {name}")

    def clear_status(self):
        self.progress_bar.setVisible(False)
        self.status_label.setText("")

    def apply_theme(self, theme: str):
        self._theme = theme
        self.status_label.setStyleSheet(f"color: {_c(theme, 'muted')};")


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
        self.browse_button.clicked.connect(self._browse)
        f_row.addWidget(self.root_edit, 1)
        f_row.addWidget(self.browse_button)
        controls_lay.addLayout(f_row)

        # Quick presets & threshold row
        opts_row = QHBoxLayout()
        opts_row.setSpacing(8)
        opts_row.addWidget(QLabel("Presets:"))

        presets = [
            ("User Profile", get_user_profile()),
            ("Downloads", os.path.join(get_user_profile(), "Downloads")),
            ("AppData", os.path.join(get_user_profile(), "AppData")),
            ("Temp", os.environ.get("TEMP", "C:\\Windows\\Temp")),
        ]
        for label, path in presets:
            if os.path.exists(path):
                btn = QPushButton(label)
                btn.setProperty("chip", "true")
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
        self.scan_button.clicked.connect(self._scan)

        self.cancel_button = QPushButton("Cancel")
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
        self.table.set_empty_text(
            self._theme, "Select a target folder and click 'Find Large Files' to begin."
        )
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
        self._main.scan_large_files(self.root_edit.text(), self._threshold())

    def _open_folder(self, path: str):
        if os.path.exists(path):
            subprocess.Popen(["explorer", "/select,", path])

    def _open_row(self, item):
        row = item.row()
        path_item = self.table.item(row, 4)
        if path_item is not None:
            self._open_folder(path_item.text())

    def show_files(self, files):
        self.scan_button.setEnabled(True)
        self.cancel_button.hide()
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
        open_folder = menu.addAction("Reveal in File Explorer")
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
        self.table.set_empty_text(
            theme, "Select a target folder and click 'Find Large Files' to begin."
        )


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
        add_button.clicked.connect(self._add_folder)
        remove_button = QPushButton("Remove Selected")
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
        self.scan_button.clicked.connect(self._scan)

        self.cancel_button = QPushButton("Cancel")
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
        self.table.set_empty_text(self._theme, "Add one or more folders and scan for duplicates.")
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
        self._main.scan_duplicates(folders, self.min_size.value() * 1024 * 1024)

    def show_groups(self, groups):
        self.scan_button.setEnabled(True)
        self.cancel_button.hide()
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
            QMessageBox.information(self, "Duplicates", "No copies were selected for recycling.")
            return
        from crapcleaner.utils.files import move_to_recycle_bin

        ok, failed = move_to_recycle_bin(targets)
        self._groups = [g for g in self._groups if g is not group]
        self.show_groups(self._groups)
        if ok:
            QMessageBox.information(
                self,
                "Recycle Bin",
                f"Moved {len(targets)} duplicate copy/copies to the Recycle Bin.",
            )
        else:
            QMessageBox.warning(
                self,
                "Recycle Bin",
                f"Some files could not be moved ({len(failed)} locked or in use).",
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
        self.table.set_empty_text(theme, "Add one or more folders and scan for duplicates.")


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
        self.table.set_empty_text(
            self._theme, "Click 'Inspect AI Data' to scan for local AI models."
        )
        table_lay.addWidget(self.table)
        layout.addWidget(table_card, 1)

        self.status_label = QLabel("")
        self.status_label.setProperty("subtle", "true")
        layout.addWidget(self.status_label)

    def _scan(self):
        self._main.scan_ai_data(self.min_size.value() * 1024 * 1024)

    def _open_row(self, item):
        row = item.row()
        path_item = self.table.item(row, 0)
        if path_item is not None and os.path.exists(path_item.text()):
            subprocess.Popen(["explorer", "/select,", path_item.text()])

    def show_items(self, items):
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
        open_folder = menu.addAction("Reveal in File Explorer")
        copy_path = menu.addAction("Copy Path")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == open_folder and os.path.exists(path):
            subprocess.Popen(["explorer", "/select,", path])
        elif action == copy_path:
            QApplication.clipboard().setText(path)

    def apply_theme(self, theme: str):
        self._theme = theme
        self.info_label.setStyleSheet(f"color: {_c(theme, 'muted')};")
        self.status_label.setStyleSheet(f"color: {_c(theme, 'muted')};")
        self.table.set_empty_text(theme, "Click 'Inspect AI Data' to scan for local AI models.")


class DockerView(QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._theme = "dark"
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)
        layout.addWidget(
            page_header(
                "Docker & WSL2 Storage",
                "Inspect Docker daemon storage and WSL virtual disks safely with confirmed prune actions.",
            )
        )

        toolbar = QHBoxLayout()
        self.df_button = QPushButton("Refresh Docker Usage (docker system df)")
        self.df_button.setProperty("primary", "true")
        self.df_button.clicked.connect(self._main.refresh_docker)
        toolbar.addWidget(self.df_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        output_card = QFrame()
        output_card.setProperty("card", "true")
        output_lay = QVBoxLayout(output_card)
        output_lay.setContentsMargins(14, 12, 14, 12)
        self.output = QLabel("Click 'Refresh Docker Usage' to inspect daemon state.")
        self.output.setWordWrap(True)
        self.output.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.output.setStyleSheet("font-family: 'Consolas', monospace; font-size: 12px;")
        output_lay.addWidget(self.output)
        layout.addWidget(output_card)

        # WSL Virtual Disks
        wsl_header = QHBoxLayout()
        wsl_lbl = QLabel("WSL2 / Docker Virtual Disks (ext4.vhdx)")
        wsl_lbl.setStyleSheet("font-weight: 700;")
        wsl_header.addWidget(wsl_lbl)
        wsl_header.addStretch(1)

        copy_cmd_btn = QPushButton("Copy WSL Compact Command")
        copy_cmd_btn.setProperty("ghost", "true")
        copy_cmd_btn.setToolTip("Copies the command to compact WSL virtual disks")
        copy_cmd_btn.clicked.connect(
            lambda: QApplication.clipboard().setText(
                "wsl --shutdown && wsl --manage <distro> --compact"
            )
        )
        wsl_header.addWidget(copy_cmd_btn)
        layout.addLayout(wsl_header)

        table_card = QFrame()
        table_card.setProperty("card", "true")
        table_lay = QVBoxLayout(table_card)
        table_lay.setContentsMargins(8, 8, 8, 8)
        self.wsl_table = CrapTable(0, 2)
        self.wsl_table.setHorizontalHeaderLabels(
            ["Virtual Disk File (.vhdx)", "Allocated Disk Size"]
        )
        self.wsl_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.wsl_table.set_empty_text(self._theme, "No WSL virtual disks detected.")
        table_lay.addWidget(self.wsl_table)
        layout.addWidget(table_card, 1)

        # Safe Prune Buttons
        prune_row = QHBoxLayout()
        prune_row.setSpacing(8)
        self.prune_system_button = QPushButton("docker system prune")
        self.prune_system_button.clicked.connect(lambda: self._prune("docker_system_prune"))
        self.prune_builder_button = QPushButton("docker builder prune")
        self.prune_builder_button.clicked.connect(lambda: self._prune("docker_builder_prune"))
        prune_row.addWidget(self.prune_system_button)
        prune_row.addWidget(self.prune_builder_button)
        prune_row.addStretch(1)
        layout.addLayout(prune_row)

    def _prune(self, action_name):
        dialog = ConfirmDeleteDialog(
            "Confirm Docker Prune",
            f"Run '{action_name.replace('_', ' ')}'? "
            "This removes stopped containers and unused build caches. Volumes are NOT deleted.",
            confirm_label="Run Prune",
        )
        if dialog.exec() == ConfirmDeleteDialog.DialogCode.Accepted:
            self._main.run_docker_prune(action_name)

    def show_docker_info(self, info):
        if not info.available:
            self.output.setText(
                "Docker is not available on this system (Docker CLI not detected in PATH)."
            )
        else:
            text = f"Docker Engine {info.version or ''}\n\n"
            if info.df_raw:
                text += info.df_raw
            if info.total_reclaimable:
                text += f"\n\nTotal reclaimable space: {format_size(info.total_reclaimable)}"
            self.output.setText(text)

    def show_wsl_report(self, rows):
        self.wsl_table.setSortingEnabled(False)
        self.wsl_table.setRowCount(0)
        for row_data in rows:
            row = self.wsl_table.rowCount()
            self.wsl_table.insertRow(row)
            self.wsl_table.setItem(row, 0, QTableWidgetItem(row_data["path"]))
            self.wsl_table.setItem(
                row, 1, NumericItem(format_size(row_data["size"]), row_data["size"])
            )
        self.wsl_table.setSortingEnabled(True)
        self.wsl_table.refresh_placeholder()
        self.wsl_table.resizeColumnToContents(1)

    def apply_theme(self, theme: str):
        self._theme = theme
        self.wsl_table.set_empty_text(theme, "No WSL virtual disks detected.")


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
        self.refresh_button.clicked.connect(self.refresh)
        toolbar.addWidget(self.refresh_button)

        export_btn = QPushButton("Export Log to JSON")
        export_btn.clicked.connect(self._export_json)
        toolbar.addWidget(export_btn)

        toolbar.addStretch(1)
        self.clear_button = QPushButton("Clear History Log")
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


class SettingsView(QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._categories = get_all_categories()
        self._theme = "dark"
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(10)
        root.addWidget(
            page_header(
                "Preferences & Configuration",
                "Customize theme, safety defaults, scan speed, and enabled category rules.",
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)
        self.settings = load_settings()

        # Appearance Card
        group = QGroupBox("Appearance & Theme")
        g1 = QVBoxLayout(group)
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Interface Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.setCurrentText(self.settings.get("theme", "dark"))
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch(1)
        g1.addLayout(theme_row)
        layout.addWidget(group)

        # Safety Card
        group2 = QGroupBox("Safety Defaults")
        g2 = QVBoxLayout(group2)
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
        g2.addWidget(self.dry_run_check)
        g2.addWidget(self.confirm_check)
        g2.addWidget(self.recycle_check)
        layout.addWidget(group2)

        # Scanning Card
        group3 = QGroupBox("Scanning Engine Performance")
        g3 = QVBoxLayout(group3)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Max Files Scanned per Run:"))
        self.max_files_spin = QSpinBox()
        self.max_files_spin.setRange(5000, 2000000)
        self.max_files_spin.setSingleStep(10000)
        self.max_files_spin.setSuffix(" files")
        self.max_files_spin.setValue(int(self.settings.get("max_scan_files", 200000)))
        row1.addWidget(self.max_files_spin)
        row1.addStretch(1)
        g3.addLayout(row1)

        row_ttl = QHBoxLayout()
        row_ttl.addWidget(QLabel("Scan Cache TTL (Seconds):"))
        self.cache_ttl_spin = QSpinBox()
        self.cache_ttl_spin.setRange(0, 3600)
        self.cache_ttl_spin.setSuffix(" s")
        self.cache_ttl_spin.setValue(int(self.settings.get("scan_cache_ttl", 300)))
        row_ttl.addWidget(self.cache_ttl_spin)
        row_ttl.addStretch(1)
        g3.addLayout(row_ttl)
        layout.addWidget(group3)

        # Scan Roots
        group4 = QGroupBox("Developer Roots (Python Junk, __pycache__, Virtualenvs)")
        g4 = QVBoxLayout(group4)
        self.all_drives_check = QCheckBox(
            "Automatically search all local drives for developer caches"
        )
        self.all_drives_check.setChecked(bool(self.settings.get("scan_all_drives", True)))
        g4.addWidget(self.all_drives_check)
        self.roots_list = QListWidget()
        for root_path in self.settings.get("scan_roots", []):
            self.roots_list.addItem(root_path)
        row_roots = QHBoxLayout()
        add_btn = QPushButton("Add Root Folder...")
        add_btn.clicked.connect(self._add_root)
        rem_btn = QPushButton("Remove Selected")
        rem_btn.clicked.connect(self._remove_root)
        row_roots.addWidget(add_btn)
        row_roots.addWidget(rem_btn)
        row_roots.addStretch(1)
        g4.addWidget(self.roots_list)
        g4.addLayout(row_roots)
        layout.addWidget(group4)

        # Categories
        group5 = QGroupBox("Category Rules (Disabled categories are skipped)")
        g5 = QVBoxLayout(group5)
        self.cat_list = QListWidget()
        self._rebuild_cat_list()
        g5.addWidget(self.cat_list)
        layout.addWidget(group5)

        # Backup & Export
        group6 = QGroupBox("Import / Export Configuration")
        g6 = QHBoxLayout(group6)
        export_btn = QPushButton("Export Settings...")
        export_btn.clicked.connect(self._export)
        import_btn = QPushButton("Import Settings...")
        import_btn.clicked.connect(self._import)
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        g6.addWidget(export_btn)
        g6.addWidget(import_btn)
        g6.addWidget(reset_btn)
        g6.addStretch(1)
        layout.addWidget(group6)

        # Save Button
        save_row = QHBoxLayout()
        self.save_button = QPushButton("Save Preferences")
        self.save_button.setProperty("primary", "true")
        self.save_button.setFixedHeight(36)
        self.save_button.setFixedWidth(160)
        self.save_button.clicked.connect(self._save)
        save_row.addWidget(self.save_button)
        save_row.addStretch(1)
        layout.addLayout(save_row)

        layout.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

    def _rebuild_cat_list(self):
        self.cat_list.clear()
        disabled = set(self.settings.get("disabled_categories", []))
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

    def _save(self):
        roots = [self.roots_list.item(i).text() for i in range(self.roots_list.count())]
        disabled = [
            self.cat_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.cat_list.count())
            if self.cat_list.item(i).checkState() == Qt.CheckState.Unchecked
        ]
        settings = {
            "theme": self.theme_combo.currentText(),
            "dry_run_default": self.dry_run_check.isChecked(),
            "confirm_cleanup": self.confirm_check.isChecked(),
            "use_recycle_bin": self.recycle_check.isChecked(),
            "scan_roots": roots,
            "scan_all_drives": self.all_drives_check.isChecked(),
            "scan_cache_ttl": int(self.cache_ttl_spin.value()),
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
            self.theme_combo.setCurrentText(self.settings.get("theme", "dark"))
            self.dry_run_check.setChecked(self.settings.get("dry_run_default", True))
            self.confirm_check.setChecked(self.settings.get("confirm_cleanup", True))
            self.recycle_check.setChecked(bool(self.settings.get("use_recycle_bin", True)))
            self.max_files_spin.setValue(int(self.settings.get("max_scan_files", 200000)))
            self.all_drives_check.setChecked(bool(self.settings.get("scan_all_drives", True)))
            self.cache_ttl_spin.setValue(int(self.settings.get("scan_cache_ttl", 300)))
            self.roots_list.clear()
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
            self.theme_combo.setCurrentText(self.settings.get("theme", "dark"))
            self.dry_run_check.setChecked(self.settings.get("dry_run_default", True))
            self.confirm_check.setChecked(self.settings.get("confirm_cleanup", True))
            self.recycle_check.setChecked(bool(self.settings.get("use_recycle_bin", True)))
            self.max_files_spin.setValue(int(self.settings.get("max_scan_files", 200000)))
            self.all_drives_check.setChecked(bool(self.settings.get("scan_all_drives", True)))
            self.cache_ttl_spin.setValue(int(self.settings.get("scan_cache_ttl", 300)))
            self.roots_list.clear()
            for root_path in self.settings.get("scan_roots", []):
                self.roots_list.addItem(root_path)
            self._rebuild_cat_list()
            self._main.apply_settings()
            QMessageBox.information(self, "Import Settings", "Settings imported successfully.")
        except OSError as exc:
            QMessageBox.warning(self, "Import Error", str(exc))

    def apply_theme(self, theme: str):
        self._theme = theme


class SquircleAvatarWidget(QWidget):
    """Profile avatar rendered inside a smooth anti-aliased squircle (rounded-rect) path."""

    def __init__(self, image_path: str, size: int = 120, radius: int = 28, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self._size = size
        self._radius = radius
        self.setFixedSize(size, size)
        self._pixmap = QPixmap(image_path) if os.path.exists(image_path) else None

    def set_avatar_path(self, image_path: str):
        self.image_path = image_path
        self._pixmap = QPixmap(image_path) if os.path.exists(image_path) else None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        rect = QRectF(2, 2, self._size - 4, self._size - 4)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        painter.setClipPath(path)

        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self._size,
                self._size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x_off = (self._size - scaled.width()) // 2
            y_off = (self._size - scaled.height()) // 2
            painter.drawPixmap(x_off, y_off, scaled)
        else:
            painter.setBrush(QBrush(QColor("#3b82f6")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(0, 0, self._size, self._size)
            painter.setPen(QColor("#ffffff"))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(26)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "PJ")

        painter.setClipping(False)
        pen = QPen(QColor(59, 130, 246, 180), 2.5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, self._radius, self._radius)
        painter.end()


class SpecsView(QWidget):
    """Speccy-style PC hardware and Operating System specifications inspector."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self._theme = "dark"
        self._specs = None
        self._build_ui()

    def _build_ui(self):
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(28, 24, 28, 24)
        root_lay.setSpacing(16)

        # Header
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        h1 = QLabel("System Hardware & OS Specifications")
        h1.setObjectName("ViewTitle")
        sub = QLabel(
            "Comprehensive overview of your PC components, memory, storage, and operating system."
        )
        sub.setProperty("subtle", "true")
        titles.addWidget(h1)
        titles.addWidget(sub)
        header.addLayout(titles)
        header.addStretch(1)

        self.copy_btn = QPushButton("Copy Specs")
        self.copy_btn.setProperty("secondary", "true")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.clicked.connect(self._copy_specs)
        header.addWidget(self.copy_btn)

        self.export_btn = QPushButton("Export JSON")
        self.export_btn.setProperty("secondary", "true")
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.clicked.connect(self._export_json)
        header.addWidget(self.export_btn)

        self.refresh_btn = QPushButton("Refresh Specs")
        self.refresh_btn.setProperty("primary", "true")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_specs)
        header.addWidget(self.refresh_btn)

        root_lay.addLayout(header)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        self.cards_layout = QVBoxLayout(content)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(14)

        scroll.setWidget(content)
        root_lay.addWidget(scroll, 1)

    def refresh_specs(self):
        from crapcleaner.specs.hardware import get_system_specs

        self._specs = get_system_specs()
        self._populate(self._specs)

    def _make_spec_card(self, title_text: str, rows: list[tuple[str, str]]) -> QFrame:
        card = QFrame()
        card.setProperty("card", "true")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(18, 14, 18, 14)
        card_lay.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        title = QLabel(title_text)
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        header_row.addWidget(title)
        header_row.addStretch(1)
        card_lay.addLayout(header_row)

        for label, val in rows:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(180)
            lbl.setStyleSheet(
                f"color: {_c(self._theme, 'muted')}; font-size: 13px; font-weight: 600;"
            )
            val_lbl = QLabel(str(val))
            val_lbl.setStyleSheet("color: #ffffff; font-size: 13px;")
            val_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            val_lbl.setWordWrap(True)
            row.addWidget(lbl)
            row.addWidget(val_lbl, 1)
            card_lay.addLayout(row)

        return card

    def _populate(self, specs):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        # 1. OS Card
        os_rows = [
            ("Operating System", f"{specs.os.name} ({specs.os.architecture})"),
            ("Build & Version", specs.os.build_number),
            ("System Uptime", specs.os.uptime),
            ("Computer / User", f"{specs.os.computer_name} \\ {specs.os.user_name}"),
        ]
        self.cards_layout.addWidget(self._make_spec_card("Operating System", os_rows))

        # 2. CPU Card
        cpu_rows = [
            ("Processor", specs.cpu.name),
            ("Architecture", specs.cpu.architecture),
            (
                "Cores & Threads",
                f"{specs.cpu.cores_physical} Cores, {specs.cpu.cores_logical} Logical Processors",
            ),
        ]
        if specs.cpu.max_clock_speed_mhz:
            cpu_rows.append(("Base Clock Speed", f"{specs.cpu.max_clock_speed_mhz} MHz"))
        self.cards_layout.addWidget(self._make_spec_card("CPU (Processor)", cpu_rows))

        # 3. RAM Card
        mem_rows = [
            ("Total Installed RAM", format_size(specs.memory.total_bytes)),
            (
                "Used Memory",
                f"{format_size(specs.memory.used_bytes)} ({specs.memory.percent_used}% load)",
            ),
            ("Available Memory", format_size(specs.memory.available_bytes)),
        ]
        self.cards_layout.addWidget(self._make_spec_card("Memory (RAM)", mem_rows))

        # 4. Motherboard Card
        mb_rows = [
            ("Manufacturer", specs.motherboard.manufacturer),
            ("Product Model", specs.motherboard.product),
            (
                "BIOS Version",
                f"{specs.motherboard.bios_version} ({specs.motherboard.bios_date})",
            ),
        ]
        self.cards_layout.addWidget(self._make_spec_card("Motherboard & BIOS", mb_rows))

        # 5. GPU Card
        for i, gpu in enumerate(specs.gpus):
            gpu_rows = [("Graphics Card", gpu.name)]
            if gpu.adapter_ram_bytes:
                gpu_rows.append(("Dedicated VRAM", format_size(gpu.adapter_ram_bytes)))
            if gpu.driver_version:
                gpu_rows.append(("Driver Version", gpu.driver_version))
            if gpu.resolution:
                gpu_rows.append(("Active Resolution", gpu.resolution))
            title = "Graphics (GPU)" if len(specs.gpus) == 1 else f"Graphics (GPU {i + 1})"
            self.cards_layout.addWidget(self._make_spec_card(title, gpu_rows))

        # 6. Storage Drives Card
        drive_card = QFrame()
        drive_card.setProperty("card", "true")
        d_lay = QVBoxLayout(drive_card)
        d_lay.setContentsMargins(18, 14, 18, 14)
        d_lay.setSpacing(12)

        d_title = QLabel("Storage Drives")
        d_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        d_lay.addWidget(d_title)

        for d in specs.drives:
            d_box = QVBoxLayout()
            d_box.setSpacing(4)
            d_head = QHBoxLayout()
            fs_info = f" [{d.file_system}]" if d.file_system else ""
            label_info = f" ({d.label})" if d.label else ""
            name_lbl = QLabel(f"<b>Drive {d.drive}:</b>{label_info}{fs_info}")
            name_lbl.setStyleSheet("font-size: 13px; color: #ffffff;")
            used_str = format_size(d.used_bytes)
            tot_str = format_size(d.total_bytes)
            free_str = format_size(d.free_bytes)
            stat_lbl = QLabel(f"{used_str} / {tot_str} ({d.percent_used}% full) | Free: {free_str}")
            stat_lbl.setStyleSheet(f"font-size: 12px; color: {_c(self._theme, 'muted')};")
            d_head.addWidget(name_lbl)
            d_head.addStretch(1)
            d_head.addWidget(stat_lbl)
            d_box.addLayout(d_head)

            bar = QProgressBar()
            bar.setFixedHeight(6)
            bar.setTextVisible(False)
            bar.setRange(0, 100)
            bar.setValue(d.percent_used)
            d_box.addWidget(bar)
            d_lay.addLayout(d_box)

        self.cards_layout.addWidget(drive_card)
        self.cards_layout.addStretch(1)

    def _copy_specs(self):
        if self._specs is None:
            self.refresh_specs()
        if self._specs is None:
            return
        import contextlib
        import io

        from crapcleaner.specs.hardware import print_specs_summary

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print_specs_summary(self._specs)
        QApplication.clipboard().setText(buf.getvalue())
        QMessageBox.information(self, "Copy Specs", "System specifications copied to clipboard!")

    def _export_json(self):
        if self._specs is None:
            self.refresh_specs()
        if self._specs is None:
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export Specs JSON", "pc_specs.json", "JSON (*.json)"
        )
        if not dest:
            return
        try:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(self._specs.to_json())
            QMessageBox.information(self, "Export Specs", f"Specifications saved to:\n{dest}")
        except OSError as exc:
            QMessageBox.warning(self, "Export Error", str(exc))

    def apply_theme(self, theme: str):
        self._theme = theme
        if self._specs is not None:
            self._populate(self._specs)


class AboutView(QWidget):
    """Modern About view featuring Patrick Jr.'s profile, mission, tech stack, and links."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self._theme = "dark"
        self._build_ui()

    def _build_ui(self):
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(28, 24, 28, 24)
        root_lay.setSpacing(16)

        # Header
        header = QVBoxLayout()
        header.setSpacing(4)
        h1 = QLabel("About CrapCleaner")
        h1.setObjectName("ViewTitle")
        sub = QLabel("Open-source, non-destructive Windows cleaner & developer storage toolkit.")
        sub.setProperty("subtle", "true")
        header.addWidget(h1)
        header.addWidget(sub)
        root_lay.addLayout(header)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        c_lay = QVBoxLayout(content)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(16)

        # 1. Creator Hero Card with Squircle Avatar
        hero_card = QFrame()
        hero_card.setProperty("card", "true")
        hero_card.setStyleSheet("border-radius: 12px; padding: 12px;")
        h_lay = QHBoxLayout(hero_card)
        h_lay.setContentsMargins(20, 20, 20, 20)
        h_lay.setSpacing(24)

        avatar_path = os.path.join(os.path.dirname(__file__), "..", "assets", "avatar.jpg")
        avatar = SquircleAvatarWidget(os.path.abspath(avatar_path), size=116, radius=28)
        h_lay.addWidget(avatar)

        info_box = QVBoxLayout()
        info_box.setSpacing(8)

        c_name = QLabel("Patrick Jr.")
        c_name.setStyleSheet("font-size: 24px; font-weight: 800; color: #ffffff;")
        info_box.addWidget(c_name)

        c_desc = QLabel(
            "Engineered CrapCleaner from the ground up to give Windows power users, developers, and gamers "
            "a transparent, ultra-fast, and completely safe system cleaner without bloatware, advertisements, or telemetry."
        )
        c_desc.setStyleSheet(
            f"font-size: 13px; color: {_c(self._theme, 'muted')}; line-height: 1.4;"
        )
        c_desc.setWordWrap(True)
        info_box.addWidget(c_desc)

        links_row = QHBoxLayout()
        links_row.setSpacing(10)
        gh_btn = QPushButton("GitHub Repository")
        gh_btn.setProperty("secondary", "true")
        gh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gh_btn.clicked.connect(
            lambda: subprocess.Popen(["explorer", "https://github.com/PatrickJnr/crapcleaner"])
        )
        links_row.addWidget(gh_btn)

        issue_btn = QPushButton("Report Issue")
        issue_btn.setProperty("secondary", "true")
        issue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        issue_btn.clicked.connect(
            lambda: subprocess.Popen(
                ["explorer", "https://github.com/PatrickJnr/crapcleaner/issues"]
            )
        )
        links_row.addWidget(issue_btn)

        update_btn = QPushButton("Check for Updates")
        update_btn.setProperty("primary", "true")
        update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        update_btn.clicked.connect(self._check_updates)
        links_row.addWidget(update_btn)

        links_row.addStretch(1)
        info_box.addLayout(links_row)

        h_lay.addLayout(info_box, 1)
        c_lay.addWidget(hero_card)

        # 2. Application Specs & Transparency Grid
        grid_lay = QHBoxLayout()
        grid_lay.setSpacing(14)

        # App Card
        app_card = QFrame()
        app_card.setProperty("card", "true")
        app_lay = QVBoxLayout(app_card)
        app_lay.setContentsMargins(18, 16, 18, 16)
        app_lay.setSpacing(10)
        app_title = QLabel("Application Information")
        app_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        app_lay.addWidget(app_title)

        from crapcleaner import __version__

        app_items = [
            ("Version", f"v{__version__} (Stable)"),
            ("License", "MIT License (100% Free & Open Source)"),
            ("Platform", "Windows 10 / 11 / Linux (64-bit)"),
            ("GUI Framework", "PySide6 (Qt 6) & Fluent 2 Dark Theme"),
            ("Python Core", "Python 3.12 (Strict Type Safe)"),
        ]
        for label, val in app_items:
            row = QHBoxLayout()
            l_lbl = QLabel(label)
            l_lbl.setFixedWidth(120)
            l_lbl.setStyleSheet(
                f"color: {_c(self._theme, 'muted')}; font-size: 12px; font-weight: 600;"
            )
            v_lbl = QLabel(val)
            v_lbl.setStyleSheet("color: #ffffff; font-size: 12px;")
            row.addWidget(l_lbl)
            row.addWidget(v_lbl, 1)
            app_lay.addLayout(row)

        grid_lay.addWidget(app_card, 1)

        # Safety Card
        safety_card = QFrame()
        safety_card.setProperty("card", "true")
        s_lay = QVBoxLayout(safety_card)
        s_lay.setContentsMargins(18, 16, 18, 16)
        s_lay.setSpacing(10)
        s_title = QLabel("Safety & Security Guarantees")
        s_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        s_lay.addWidget(s_title)

        safety_items = [
            (
                "Recycle Bin Safe",
                "Files moved to Recycle Bin by default so nothing is lost.",
            ),
            (
                "AI Models Protected",
                "Read-only inspection for GGUF & Safetensor weights.",
            ),
            ("Junction Safe", "Loop prevention avoids circular directory recursion."),
            ("Zero Telemetry", "100% local, no network tracking, no advertisements."),
        ]
        for title_str, desc_str in safety_items:
            item_box = QVBoxLayout()
            item_box.setSpacing(2)
            t_lbl = QLabel(f"✓  {title_str}")
            t_lbl.setStyleSheet(
                f"color: {_c(self._theme, 'safe')}; font-size: 12px; font-weight: 700;"
            )
            d_lbl = QLabel(desc_str)
            d_lbl.setStyleSheet(f"color: {_c(self._theme, 'muted')}; font-size: 11px;")
            item_box.addWidget(t_lbl)
            item_box.addWidget(d_lbl)
            s_lay.addLayout(item_box)

        grid_lay.addWidget(safety_card, 1)
        c_lay.addLayout(grid_lay)

        c_lay.addStretch(1)
        scroll.setWidget(content)
        root_lay.addWidget(scroll, 1)

    def _check_updates(self):
        from crapcleaner import __version__
        from crapcleaner.utils.updater import check_for_updates

        info = check_for_updates(timeout_seconds=5.0)
        if info is None:
            QMessageBox.information(
                self,
                "Check for Updates",
                f"You are running CrapCleaner v{__version__}.\nCould not connect to GitHub to check for newer releases.",
            )
            return
        if info.is_newer:
            ans = QMessageBox.information(
                self,
                "Update Available!",
                f"A new version of CrapCleaner is available: v{info.latest_version}\n"
                f"Current installed version: v{info.current_version}\n\n"
                f"Would you like to open the GitHub release page to download it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans == QMessageBox.StandardButton.Yes:
                subprocess.Popen(["explorer", info.html_url])
        else:
            QMessageBox.information(
                self,
                "Up to Date!",
                f"CrapCleaner v{info.current_version} is up to date.\nYou have the latest release installed.",
            )

    def apply_theme(self, theme: str):
        self._theme = theme
