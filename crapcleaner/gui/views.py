"""Tab views for the CrapCleaner main window."""

import csv
import json
import os
import shutil
import subprocess

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
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
    QGraphicsOpacityEffect,
    QGridLayout,
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
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.config import config_path, load_settings, save_settings, update_settings
from crapcleaner.constants import DEFAULT_CONFIG
from crapcleaner.gui.dialogs import (
    ConfirmDeleteDialog,
    DuplicateFilesDialog,
    ReportDialog,
)
from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.theme import THEMES
from crapcleaner.gui.theme import color as theme_color
from crapcleaner.gui.theme_picker import ThemeGalleryWidget
from crapcleaner.history import clear as clear_history
from crapcleaner.history import load as load_history
from crapcleaner.models.category import SafetyLevel
from crapcleaner.models.report import ScanReport
from crapcleaner.registry import get_all_categories
from crapcleaner.reports import export_report
from crapcleaner.system.live_metrics import sample_live_metrics
from crapcleaner.system.memory_actions import available_actions as available_memory_actions
from crapcleaner.system.memory_actions import get_action as get_memory_action
from crapcleaner.utils.contributors import fetch_avatar_file, fetch_contributors
from crapcleaner.utils.format import (
    format_datetime,
    format_duration,
    format_size,
    parse_size,
)
from crapcleaner.utils.platform import (
    elevate,
    get_drive_info,
    get_user_profile,
    is_admin,
    is_windows,
    linux_drive_display_kind,
    linux_drive_display_name,
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


class _SizeSortedItem(QTreeWidgetItem):
    """Tree item whose size column sorts numerically instead of alphabetically."""

    _SIZE_ROLE = Qt.ItemDataRole.UserRole + 1

    def set_sort_size(self, size: int):
        self.setData(3, self._SIZE_ROLE, size)

    def __lt__(self, other):
        column = self.treeWidget().sortColumn() if self.treeWidget() else 0
        if column == 3:
            mine = self.data(3, self._SIZE_ROLE) or 0
            theirs = other.data(3, self._SIZE_ROLE) or 0
            return mine < theirs
        return super().__lt__(other)


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


class SkeletonBlock(QFrame):
    """A rounded placeholder block simulating text or UI elements during async data fetching."""

    def __init__(
        self,
        width: int | None = None,
        height: int = 14,
        radius: int = 4,
        theme: str = "dark",
        parent=None,
    ):
        super().__init__(parent)
        self.setFixedHeight(height)
        if width:
            self.setFixedWidth(width)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._radius = radius
        self._theme = theme
        self.apply_theme(theme)

    def apply_theme(self, theme: str):
        self._theme = theme
        is_dark = theme not in ("light", "soft_light", "warm_paper", "cream")
        color = "255, 255, 255" if is_dark else "0, 0, 0"
        self.setStyleSheet(
            f"background-color: rgba({color}, 0.08); "
            f"border-radius: {self._radius}px; "
            f"border: 1px solid rgba({color}, 0.04);"
        )


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
        display_name = f"Drive {drive}" if is_windows() else linux_drive_display_name(drive)
        self.title = QLabel(display_name)
        font = self.title.font()
        font.setPointSize(13)
        font.setBold(True)
        self.title.setFont(font)
        top_row.addWidget(self.title)
        top_row.addStretch(1)

        if is_windows():
            badge_text = "SYSTEM" if drive.upper().startswith("C") else "LOCAL"
        else:
            badge_text = linux_drive_display_kind(drive)
        self.type_badge = QLabel(badge_text)
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
        self.scan_button.setIcon(material_icon("search", "#ffffff"))
        self.scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_button.setFixedHeight(34)
        self.scan_button.clicked.connect(self._main.start_scan)

        self.cancel_button = QPushButton("Cancel Scan")
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setFixedHeight(34)
        self.cancel_button.hide()
        self.cancel_button.clicked.connect(self._cancel_scan)

        self.review_button = QPushButton("Review && Clean")
        self.review_button.setProperty("danger", "true")
        self.review_button.setIcon(material_icon("clean", "#ffffff"))
        self.review_button.setCursor(Qt.CursorShape.PointingHandCursor)
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

        # Live System Vitals Row (RAM, CPU, GPU & Thermals, Network)
        layout.addWidget(section_label("Live System Vitals"))
        vitals_row = QHBoxLayout()
        vitals_row.setSpacing(12)

        # 1. RAM Vitals Card
        self.ram_card = QFrame()
        self.ram_card.setProperty("card", "true")
        self.ram_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ram_card.setToolTip("Click to open Memory Cleaner")
        self.ram_card.mousePressEvent = lambda _: (
            self._main.navigate("memory") if hasattr(self._main, "navigate") else None
        )
        rc_lay = QVBoxLayout(self.ram_card)
        rc_lay.setContentsMargins(14, 12, 14, 12)
        rc_lay.setSpacing(6)

        rc_top = QHBoxLayout()
        rc_title = QLabel("Memory (RAM)")
        rc_title.setProperty("subtle", "true")
        rc_top.addWidget(rc_title)
        rc_top.addStretch(1)
        self.ram_badge = badge("NORMAL", "safe")
        rc_top.addWidget(self.ram_badge)
        rc_lay.addLayout(rc_top)

        self.ram_val = QLabel("-- / --")
        self.ram_val.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {_c(self._theme, 'text')};"
        )
        rc_lay.addWidget(self.ram_val)

        self.ram_bar = QProgressBar()
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setValue(0)
        self.ram_bar.setTextVisible(False)
        self.ram_bar.setFixedHeight(5)
        self.ram_bar.setProperty("thin", "true")
        self.ram_bar.setProperty("good", "true")
        rc_lay.addWidget(self.ram_bar)

        self.ram_sub = QLabel("Click to open Memory Cleaner ->")
        self.ram_sub.setProperty("subtle", "true")
        self.ram_sub.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'muted')};")
        rc_lay.addWidget(self.ram_sub)
        vitals_row.addWidget(self.ram_card, 1)

        # 2. CPU Vitals Card
        self.cpu_card = QFrame()
        self.cpu_card.setProperty("card", "true")
        cpu_lay = QVBoxLayout(self.cpu_card)
        cpu_lay.setContentsMargins(14, 12, 14, 12)
        cpu_lay.setSpacing(6)

        cpu_top = QHBoxLayout()
        cpu_title = QLabel("Processor (CPU)")
        cpu_title.setProperty("subtle", "true")
        cpu_top.addWidget(cpu_title)
        cpu_top.addStretch(1)
        self.cpu_badge = badge(f"{os.cpu_count() or 4} Cores", "accent")
        cpu_top.addWidget(self.cpu_badge)
        cpu_lay.addLayout(cpu_top)

        self.cpu_val = QLabel("-- % Load")
        self.cpu_val.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {_c(self._theme, 'text')};"
        )
        cpu_lay.addWidget(self.cpu_val)

        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setValue(0)
        self.cpu_bar.setTextVisible(False)
        self.cpu_bar.setFixedHeight(5)
        self.cpu_bar.setProperty("thin", "true")
        self.cpu_bar.setProperty("good", "true")
        cpu_lay.addWidget(self.cpu_bar)

        self.cpu_sub = QLabel("Uptime: -- · AC Power")
        self.cpu_sub.setProperty("subtle", "true")
        self.cpu_sub.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'muted')};")
        cpu_lay.addWidget(self.cpu_sub)
        vitals_row.addWidget(self.cpu_card, 1)

        # 3. GPU / Graphics & Thermals Card
        self.gpu_card = QFrame()
        self.gpu_card.setProperty("card", "true")
        gpu_lay = QVBoxLayout(self.gpu_card)
        gpu_lay.setContentsMargins(14, 12, 14, 12)
        gpu_lay.setSpacing(6)

        gpu_top = QHBoxLayout()
        gpu_title = QLabel("Graphics (GPU)")
        gpu_title.setProperty("subtle", "true")
        gpu_top.addWidget(gpu_title)
        gpu_top.addStretch(1)
        self.gpu_badge = badge("OPTIMAL", "safe")
        gpu_top.addWidget(self.gpu_badge)
        gpu_lay.addLayout(gpu_top)

        self.gpu_val = QLabel("--")
        self.gpu_val.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {_c(self._theme, 'text')};"
        )
        gpu_lay.addWidget(self.gpu_val)

        self.gpu_bar = QProgressBar()
        self.gpu_bar.setRange(0, 100)
        self.gpu_bar.setValue(0)
        self.gpu_bar.setTextVisible(False)
        self.gpu_bar.setFixedHeight(5)
        self.gpu_bar.setProperty("thin", "true")
        self.gpu_bar.setProperty("good", "true")
        gpu_lay.addWidget(self.gpu_bar)

        self.gpu_sub = QLabel("VRAM: -- / --")
        self.gpu_sub.setProperty("subtle", "true")
        self.gpu_sub.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'muted')};")
        gpu_lay.addWidget(self.gpu_sub)
        vitals_row.addWidget(self.gpu_card, 1)

        # 4. Network Throughput Card
        self.net_card = QFrame()
        self.net_card.setProperty("card", "true")
        net_lay = QVBoxLayout(self.net_card)
        net_lay.setContentsMargins(14, 12, 14, 12)
        net_lay.setSpacing(6)

        net_top = QHBoxLayout()
        net_title = QLabel("Network Activity")
        net_title.setProperty("subtle", "true")
        net_top.addWidget(net_title)
        net_top.addStretch(1)
        self.net_badge = badge("Connected", "accent")
        net_top.addWidget(self.net_badge)
        net_lay.addLayout(net_top)

        net_rates_row = QHBoxLayout()
        net_rates_row.setSpacing(8)

        self.net_in_label = QLabel("↓ 0 B/s")
        self.net_in_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_c(self._theme, 'safe')};"
        )
        self.net_out_label = QLabel("↑ 0 B/s")
        self.net_out_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_c(self._theme, 'accent')};"
        )
        net_rates_row.addWidget(self.net_in_label)
        net_rates_row.addWidget(self.net_out_label)
        net_rates_row.addStretch(1)
        net_lay.addLayout(net_rates_row)

        self.net_sub = QLabel("Session: 0 B in · 0 B out")
        self.net_sub.setProperty("subtle", "true")
        self.net_sub.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'muted')};")
        net_lay.addWidget(self.net_sub)
        vitals_row.addWidget(self.net_card, 1)

        layout.addLayout(vitals_row)

        # Setup Vitals Live Polling Timer (1.2s smooth polling)
        self._vitals_timer = QTimer(self)
        self._vitals_timer.setInterval(1200)
        self._vitals_timer.timeout.connect(self._update_live_vitals)

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
        layout.addStretch(1)

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
        self._update_live_vitals()

    def _select_drive(self, drive: str):
        if drive not in self._cards:
            return
        self._selected_drive = drive
        for d, card in self._cards.items():
            card.set_selected(d == drive)
        try:
            info = get_drive_info(drive)
            total = int(info.get("total", 0))
            used = int(info.get("used", 0))
            free = int(info.get("free", 0))
            self._used_fraction = used / total if total else 0.0
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
            drive_name = drive if is_windows() else linux_drive_display_name(drive)
            path_line = "" if is_windows() else f"<br><span style='font-size:11px'>{drive}</span>"
            self.drive_detail.setText(
                f"<b>{drive_name}</b>{path_line}<br>"
                f"Used: {format_size(used)} · Free: {format_size(free)} · Total: {format_size(total)}"
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

    def _animate_bar(self, bar: QProgressBar, target_val: int, anim_attr: str):
        existing = getattr(self, anim_attr, None)
        if existing is not None and existing.state() == QVariantAnimation.State.Running:
            existing.stop()
        curr = bar.value()
        if curr == target_val:
            return
        anim = QVariantAnimation(self)
        anim.setDuration(550)
        anim.setStartValue(curr)
        anim.setEndValue(target_val)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(lambda v: bar.setValue(int(v)))
        setattr(self, anim_attr, anim)
        anim.start()

    def _update_live_vitals(self):
        if not self.isVisible():
            return
        try:
            snap = sample_live_metrics()
            # 1. Update RAM
            ram_pct = int(snap.ram.percent_used)
            self.ram_val.setText(f"{snap.ram.used_str} / {snap.ram.total_str} ({ram_pct}%)")
            self._animate_bar(self.ram_bar, ram_pct, "_ram_anim")

            pressure = snap.ram.pressure
            if getattr(self, "_last_ram_level", None) != pressure:
                self._last_ram_level = pressure
                if pressure == "critical":
                    self.ram_badge.setText("CRITICAL")
                    self.ram_badge.setProperty("level", "danger")
                    self.ram_bar.setProperty("good", "false")
                    self.ram_bar.setProperty("warn", "false")
                    self.ram_bar.setProperty("bad", "true")
                elif pressure == "high":
                    self.ram_badge.setText("HIGH USAGE")
                    self.ram_badge.setProperty("level", "warn")
                    self.ram_bar.setProperty("good", "false")
                    self.ram_bar.setProperty("warn", "true")
                    self.ram_bar.setProperty("bad", "false")
                elif pressure == "moderate":
                    self.ram_badge.setText("MODERATE")
                    self.ram_badge.setProperty("level", "review")
                    self.ram_bar.setProperty("good", "true")
                    self.ram_bar.setProperty("warn", "false")
                    self.ram_bar.setProperty("bad", "false")
                else:
                    self.ram_badge.setText("NORMAL")
                    self.ram_badge.setProperty("level", "safe")
                    self.ram_bar.setProperty("good", "true")
                    self.ram_bar.setProperty("warn", "false")
                    self.ram_bar.setProperty("bad", "false")
                self.ram_badge.style().unpolish(self.ram_badge)
                self.ram_badge.style().polish(self.ram_badge)
                self.ram_bar.style().unpolish(self.ram_bar)
                self.ram_bar.style().polish(self.ram_bar)

            # 2. Update CPU
            cpu_pct = int(snap.cpu.percent_used)
            self.cpu_val.setText(f"{snap.cpu.percent_used:.1f}% Load")
            self._animate_bar(self.cpu_bar, cpu_pct, "_cpu_anim")
            if snap.uptime_str:
                self.cpu_sub.setText(f"Uptime: {snap.uptime_str} · {snap.power_str}")

            cpu_level = "bad" if cpu_pct >= 85 else ("warn" if cpu_pct >= 60 else "good")
            if getattr(self, "_last_cpu_level", None) != cpu_level:
                self._last_cpu_level = cpu_level
                self.cpu_bar.setProperty("good", "true" if cpu_level == "good" else "false")
                self.cpu_bar.setProperty("warn", "true" if cpu_level == "warn" else "false")
                self.cpu_bar.setProperty("bad", "true" if cpu_level == "bad" else "false")
                self.cpu_bar.style().unpolish(self.cpu_bar)
                self.cpu_bar.style().polish(self.cpu_bar)

            # 3. Update GPU & Thermals
            if snap.gpu.available:
                self.gpu_val.setText(f"{snap.gpu.name} · {snap.gpu.temp_str}")
                gpu_load = int(snap.gpu.utilization_pct)
                self._animate_bar(self.gpu_bar, gpu_load, "_gpu_anim")
                self.gpu_sub.setText(
                    f"VRAM: {snap.gpu.vram_fraction_str} ({int(snap.gpu.vram_percent)}%)"
                )

                t_status = snap.gpu.thermal_status
                if getattr(self, "_last_gpu_status", None) != t_status:
                    self._last_gpu_status = t_status
                    if t_status == "hot":
                        self.gpu_badge.setText(f"{snap.gpu.temp_str} HOT")
                        self.gpu_badge.setProperty("level", "danger")
                        self.gpu_bar.setProperty("good", "false")
                        self.gpu_bar.setProperty("warn", "false")
                        self.gpu_bar.setProperty("bad", "true")
                    elif t_status == "warm":
                        self.gpu_badge.setText(f"{snap.gpu.temp_str} WARM")
                        self.gpu_badge.setProperty("level", "warn")
                        self.gpu_bar.setProperty("good", "false")
                        self.gpu_bar.setProperty("warn", "true")
                        self.gpu_bar.setProperty("bad", "false")
                    else:
                        self.gpu_badge.setText(f"{snap.gpu.temp_str} {t_status.upper()}")
                        self.gpu_badge.setProperty("level", "safe")
                        self.gpu_bar.setProperty("good", "true")
                        self.gpu_bar.setProperty("warn", "false")
                        self.gpu_bar.setProperty("bad", "false")
                    self.gpu_badge.style().unpolish(self.gpu_badge)
                    self.gpu_badge.style().polish(self.gpu_badge)
                    self.gpu_bar.style().unpolish(self.gpu_bar)
                    self.gpu_bar.style().polish(self.gpu_bar)
            else:
                self.gpu_val.setText("Display Adapter")
                self.gpu_badge.setText("READY")
                self.gpu_sub.setText(f"System: {snap.uptime_str} · {snap.power_str}")

            # 4. Update Network
            self.net_in_label.setText(f"↓ {snap.network.in_rate_str}")
            self.net_out_label.setText(f"↑ {snap.network.out_rate_str}")
            self.net_sub.setText(
                f"Session: {snap.network.total_in_str} in · {snap.network.total_out_str} out"
            )
            if snap.network.interface_name:
                self.net_badge.setText(snap.network.interface_name[:16])
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "_vitals_timer") and not self._vitals_timer.isActive():
            self._vitals_timer.start()
            self._update_live_vitals()

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, "_vitals_timer") and self._vitals_timer.isActive():
            self._vitals_timer.stop()

    def apply_theme(self, theme: str):
        self._theme = theme
        for card in self._cards.values():
            card.apply_theme(theme)
        self.drive_detail.setStyleSheet(f"color: {_c(theme, 'muted')};")
        self.donut.set_usage(self._used_fraction, theme)
        self.reclaimable_label.setStyleSheet(
            f"font-size: 32px; font-weight: 800; color: {_c(theme, 'text')};"
        )
        self.ram_val.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {_c(theme, 'text')};"
        )
        self.cpu_val.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {_c(theme, 'text')};"
        )
        self.gpu_val.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {_c(theme, 'text')};"
        )
        self.net_in_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_c(theme, 'safe')};"
        )
        self.net_out_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_c(theme, 'accent')};"
        )
        self.ram_sub.setStyleSheet(f"font-size: 10px; color: {_c(theme, 'muted')};")
        self.cpu_sub.setStyleSheet(f"font-size: 10px; color: {_c(theme, 'muted')};")
        self.gpu_sub.setStyleSheet(f"font-size: 10px; color: {_c(theme, 'muted')};")
        self.net_sub.setStyleSheet(f"font-size: 10px; color: {_c(theme, 'muted')};")


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
        self._sort_descending = True
        self._current_explained_category = None
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
        self.scan_button.setIcon(material_icon("search", "#ffffff"))
        self.scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self.safe_button.setIcon(material_icon("security", _c(self._theme, "text")))
        self.safe_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.safe_button.clicked.connect(lambda: self._select_by_safety(True))

        self.all_button = QPushButton("Select All")
        self.all_button.setIcon(material_icon("done_all", _c(self._theme, "text")))
        self.all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.all_button.clicked.connect(lambda: self._select_all(True))

        self.none_button = QPushButton("Deselect All")
        self.none_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.none_button.clicked.connect(lambda: self._select_all(False))

        self.invert_button = QPushButton("Invert")
        self.invert_button.setCursor(Qt.CursorShape.PointingHandCursor)
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

        sort_btn = QPushButton("Sort by Size")
        sort_btn.setProperty("ghost", "true")
        sort_btn.setToolTip("Order categories by how much space they can reclaim.")
        sort_btn.clicked.connect(lambda: self.sort_by_size(not self._sort_descending))
        filter_row.addWidget(sort_btn)

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
        self.tree.currentItemChanged.connect(self._on_current_item_changed)
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
        self.clean_button.setIcon(material_icon("clean", "#ffffff"))
        self.clean_button.setCursor(Qt.CursorShape.PointingHandCursor)
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

        self.scan_delta_label = QLabel("Run a scan to compare it with the previous one.")
        self.scan_delta_label.setWordWrap(True)
        self.scan_delta_label.setProperty("subtle", "true")
        layout.addWidget(self.scan_delta_label)

        explain_card = QFrame()
        explain_card.setProperty("card", "true")
        explain_lay = QVBoxLayout(explain_card)
        explain_lay.setContentsMargins(14, 12, 14, 12)
        explain_lay.setSpacing(6)
        explain_title = QLabel("Why is this here?")
        explain_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        explain_lay.addWidget(explain_title)
        self.explain_label = QLabel(
            "Select a cleanup category to see what it contains, why it grows, why it is safe to remove, and what will be regenerated."
        )
        self.explain_label.setWordWrap(True)
        self.explain_label.setProperty("subtle", "true")
        explain_lay.addWidget(self.explain_label)
        layout.addWidget(explain_card)

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

    def _on_current_item_changed(self, item, _previous):
        category = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        self._current_explained_category = category
        if category is None:
            self.explain_label.setText(
                "Select a cleanup category to see what it contains, why it grows, why it is safe to remove, and what will be regenerated."
            )
            return
        parts = [f"<b>{category.name}</b>", category.description]
        if category.what_it_contains:
            parts.append(f"<b>Contains:</b> {category.what_it_contains}")
        if category.why_it_grows:
            parts.append(f"<b>Why it grows:</b> {category.why_it_grows}")
        if category.why_safe_to_delete:
            parts.append(f"<b>Why safe to delete:</b> {category.why_safe_to_delete}")
        if category.regeneration_behavior:
            parts.append(f"<b>After cleanup:</b> {category.regeneration_behavior}")
        if category.requires_admin:
            parts.append("<b>Permission:</b> Requires administrator privileges.")
        if not category.reversible:
            parts.append("<b>Reversibility:</b> This action is not reversible.")
        self.explain_label.setText("<br><br>".join(parts))

    def set_scan_delta(self, previous_snapshot, current_snapshot):
        if not previous_snapshot:
            self.scan_delta_label.setText("Run a scan to compare it with the previous one.")
            return
        previous_total = int(previous_snapshot.get("total_identified", 0) or 0)
        if not current_snapshot:
            self.scan_delta_label.setText(
                f"Last scan found {format_size(previous_total)} reclaimable. Run another scan to see what changed."
            )
            return
        current_total = int(current_snapshot.get("total_identified", 0) or 0)
        delta = current_total - previous_total
        prev_categories = previous_snapshot.get("categories", {}) or {}
        curr_categories = current_snapshot.get("categories", {}) or {}
        changes = []
        for category in self._categories:
            before = int(prev_categories.get(category.id, 0) or 0)
            after = int(curr_categories.get(category.id, 0) or 0)
            diff = after - before
            if diff > 0:
                changes.append((diff, category.name))
        changes.sort(reverse=True)
        if delta > 0:
            headline = f"Since the last scan: reclaimable space increased by {format_size(delta)}."
        elif delta < 0:
            headline = (
                f"Since the last scan: reclaimable space decreased by {format_size(abs(delta))}."
            )
        else:
            headline = "Since the last scan: total reclaimable space is unchanged."
        if changes:
            top = ", ".join(f"{name} (+{format_size(diff)})" for diff, name in changes[:3])
            headline += f" Biggest growth: {top}."
        self.scan_delta_label.setText(headline)

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

    def sort_by_size(self, descending: bool = True):
        """Order every group, and the categories inside it, by reclaimable size."""
        self._sort_descending = descending
        order = Qt.SortOrder.DescendingOrder if descending else Qt.SortOrder.AscendingOrder
        self.tree.sortItems(3, order)
        for index in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(index)
            if group is not None:
                group.sortChildren(3, order)

    def populate(self, categories):
        self._categories = categories
        self.tree.blockSignals(True)
        try:
            self.tree.clear()
            groups: dict = {}
            for category in categories:
                groups.setdefault(category.group, []).append(category)

            for group_name, members in groups.items():
                group_item = _SizeSortedItem([group_name])
                group_item.setFlags(
                    group_item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable & ~Qt.ItemFlag.ItemIsAutoTristate
                )
                group_item.setCheckState(0, Qt.CheckState.Unchecked)
                for category in members:
                    safety = category.safety_level
                    item = _SizeSortedItem()
                    item.setText(1, safety.label)
                    item.setText(2, str(category.item_count) if category.item_count else "")
                    item.setText(3, format_size(category.size) if category.size else "")
                    item.set_sort_size(category.size)
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
                if hasattr(child, "set_sort_size"):
                    child.set_sort_size(category.size)
                group_total += category.size
            group.setText(2, f"{group.childCount()} categories")
            group.setText(3, format_size(group_total) if group_total else "")
            if hasattr(group, "set_sort_size"):
                group.set_sort_size(group_total)
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
            subprocess.Popen(["explorer", "/select,", path])

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
        self.table.set_empty_text(theme, self._empty_message)


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
        self.table.set_empty_text(theme, self._empty_message)


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
            subprocess.Popen(["explorer", "/select,", path_item.text()])

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
        self.table.set_empty_text(theme, self._empty_message)


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
        self.df_button.setIcon(material_icon("refresh", "#ffffff"))
        self.df_button.setCursor(Qt.CursorShape.PointingHandCursor)
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
        copy_cmd_btn.setIcon(material_icon("code", _c(self._theme, "text")))
        copy_cmd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self.prune_system_button.setIcon(material_icon("clean", _c(self._theme, "text")))
        self.prune_system_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prune_system_button.clicked.connect(lambda: self._prune("docker_system_prune"))
        self.prune_builder_button = QPushButton("docker builder prune")
        self.prune_builder_button.setIcon(material_icon("clean", _c(self._theme, "text")))
        self.prune_builder_button.setCursor(Qt.CursorShape.PointingHandCursor)
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


class SettingsView(QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._categories = get_all_categories()
        self._theme = "dark"
        self._section_buttons: dict[str, QPushButton] = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)
        self.settings = load_settings()

        # 1. Header with Page Title + Global Action Buttons
        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        header_text = page_header(
            "Preferences & Configuration",
            "Customize interface themes, safety protections, scan engine speed, and cleanup rules.",
        )
        header_row.addWidget(header_text, 1)

        # Quick Save and Reset Actions in Header
        actions_box = QHBoxLayout()
        actions_box.setSpacing(8)

        self.reset_top_btn = QPushButton("Reset Defaults")
        self.reset_top_btn.setIcon(material_icon("refresh", "#888888"))
        self.reset_top_btn.setFixedHeight(34)
        self.reset_top_btn.clicked.connect(self._reset_defaults)
        actions_box.addWidget(self.reset_top_btn)

        self.save_button = QPushButton("Save Preferences")
        self.save_button.setProperty("primary", "true")
        self.save_button.setIcon(material_icon("check", "#ffffff"))
        self.save_button.setFixedHeight(34)
        self.save_button.setFixedWidth(160)
        self.save_button.clicked.connect(self._save)
        actions_box.addWidget(self.save_button)

        header_row.addLayout(actions_box)
        root.addLayout(header_row)

        # 2. Horizontal Sub-Navigation Tab Bar (Segmented Tabs)
        nav_row = QHBoxLayout()
        nav_row.setSpacing(6)

        self._sections = [
            ("themes", "Appearance & Themes", "palette"),
            ("safety", "Safety & Protection", "security"),
            ("exclusions", "Exclusions & Roots", "folder"),
            ("performance", "Scan Performance", "speed"),
            ("rules", "Category Rules", "checklist"),
            ("backup", "Backup & Sync", "backup"),
        ]

        for idx, (key, label, icon_name) in enumerate(self._sections):
            btn = QPushButton(label.replace("&", "&&"))
            btn.setProperty("chip", "true")
            btn.setProperty("active", "true" if idx == 0 else "false")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(material_icon(icon_name, "#3b82f6" if idx == 0 else "#888888"))
            btn.setIconSize(QSize(16, 16))
            btn.clicked.connect(lambda _, k=key, i=idx: self._set_active_tab(k, i))
            self._section_buttons[key] = btn
            nav_row.addWidget(btn)

        nav_row.addStretch(1)
        root.addLayout(nav_row)

        # 3. Stack of Tab Pages
        self.tab_stack = QStackedWidget()

        # --- PAGE 0: Appearance & Themes ---
        page_themes = QWidget()
        lay_themes = QVBoxLayout(page_themes)
        lay_themes.setContentsMargins(0, 4, 0, 0)
        lay_themes.setSpacing(10)

        current_theme = self.settings.get("theme", "dark")
        self.theme_gallery = ThemeGalleryWidget(current_theme, page_themes)
        self.theme_combo = self.theme_gallery.theme_combo
        self.theme_gallery.theme_changed.connect(self._on_theme_changed)
        lay_themes.addWidget(self.theme_gallery, 1)

        motion_card = QFrame()
        motion_card.setProperty("card", "true")
        motion_lay = QVBoxLayout(motion_card)
        motion_lay.setContentsMargins(14, 10, 14, 10)
        motion_lay.setSpacing(4)
        motion_title = QLabel("Motion & Visual Transitions")
        motion_title.setProperty("strong", "true")
        motion_lay.addWidget(motion_title)
        self.reduce_motion_check = QCheckBox("Reduce motion (skip the theme cross-fade)")
        self.reduce_motion_check.setChecked(bool(self.settings.get("reduce_motion", False)))
        self.reduce_motion_check.toggled.connect(self._save_reduce_motion)
        motion_lay.addWidget(self.reduce_motion_check)
        lay_themes.addWidget(motion_card)

        self.tab_stack.addWidget(page_themes)

        # --- PAGE 1: Safety & Protection ---
        page_safety = QWidget()
        lay_safety = QVBoxLayout(page_safety)
        lay_safety.setContentsMargins(0, 4, 0, 0)
        lay_safety.setSpacing(12)

        safety_card = QFrame()
        safety_card.setProperty("card", "true")
        sc_lay = QVBoxLayout(safety_card)
        sc_lay.setContentsMargins(16, 16, 16, 16)
        sc_lay.setSpacing(12)

        sc_title = QLabel("System Safety Defaults")
        sc_title.setProperty("strong", "true")
        sc_lay.addWidget(sc_title)

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
        self.auto_rescan_check = QCheckBox(
            "Automatically rescan system after cleanup (verify actual recovered space)"
        )
        self.auto_rescan_check.setChecked(
            bool(self.settings.get("auto_rescan_after_cleanup", True))
        )
        self.cmd_preview_check = QCheckBox(
            "Show command preview before running external operations (Docker / WSL)"
        )
        self.cmd_preview_check.setChecked(bool(self.settings.get("show_command_preview", True)))

        sc_lay.addWidget(self.dry_run_check)
        sc_lay.addWidget(self.confirm_check)
        sc_lay.addWidget(self.recycle_check)
        sc_lay.addWidget(self.auto_rescan_check)
        sc_lay.addWidget(self.cmd_preview_check)
        lay_safety.addWidget(safety_card)

        guide_card = QFrame()
        guide_card.setProperty("card", "true")
        g_lay = QVBoxLayout(guide_card)
        g_lay.setContentsMargins(16, 16, 16, 16)
        g_lay.setSpacing(10)
        guide_title = QLabel("Safety Level Architecture")
        guide_title.setProperty("strong", "true")
        g_lay.addWidget(guide_title)

        levels_grid = QGridLayout()
        levels_grid.setSpacing(10)

        badge_safe = QLabel("SAFE")
        badge_safe.setProperty("badge", "true")
        badge_safe.setProperty("level", "safe")
        desc_safe = QLabel(
            "Standard temporary cache files, crash dumps, and browser histories. Zero risk."
        )
        desc_safe.setProperty("subtle", "true")

        badge_low = QLabel("LOW RISK")
        badge_low.setProperty("badge", "true")
        badge_low.setProperty("level", "warn")
        desc_low = QLabel("Package manager caches (pip, npm, cargo), old downloads, thumbnails.")
        desc_low.setProperty("subtle", "true")

        badge_review = QLabel("REVIEW")
        badge_review.setProperty("badge", "true")
        badge_review.setProperty("level", "review")
        desc_review = QLabel(
            "AI model checkpoints, Docker image caches, virtualenvs. Review recommended."
        )
        desc_review.setProperty("subtle", "true")

        badge_danger = QLabel("DANGEROUS")
        badge_danger.setProperty("badge", "true")
        badge_danger.setProperty("level", "danger")
        desc_danger = QLabel(
            "System component stores, recovery images, registry caches. Use with caution."
        )
        desc_danger.setProperty("subtle", "true")

        levels_grid.addWidget(badge_safe, 0, 0)
        levels_grid.addWidget(desc_safe, 0, 1)
        levels_grid.addWidget(badge_low, 1, 0)
        levels_grid.addWidget(desc_low, 1, 1)
        levels_grid.addWidget(badge_review, 2, 0)
        levels_grid.addWidget(desc_review, 2, 1)
        levels_grid.addWidget(badge_danger, 3, 0)
        levels_grid.addWidget(desc_danger, 3, 1)

        g_lay.addLayout(levels_grid)
        lay_safety.addWidget(guide_card)
        lay_safety.addStretch(1)

        self.tab_stack.addWidget(page_safety)

        # --- PAGE 2: Exclusions & Roots ---
        page_excl = QWidget()
        lay_excl = QHBoxLayout(page_excl)
        lay_excl.setContentsMargins(0, 4, 0, 0)
        lay_excl.setSpacing(12)

        card_excl = QFrame()
        card_excl.setProperty("card", "true")
        ce_lay = QVBoxLayout(card_excl)
        ce_lay.setContentsMargins(14, 14, 14, 14)
        ce_lay.setSpacing(8)

        ce_title = QLabel("Cleanup Exclusions")
        ce_title.setProperty("strong", "true")
        ce_sub = QLabel("Permanently skip these folders during all scans and cleanups.")
        ce_sub.setProperty("subtle", "true")
        ce_sub.setWordWrap(True)
        ce_lay.addWidget(ce_title)
        ce_lay.addWidget(ce_sub)

        self.exclusions_list = QListWidget()
        for excl_path in self.settings.get("excluded_paths", []):
            self.exclusions_list.addItem(excl_path)
        ce_lay.addWidget(self.exclusions_list, 1)

        row_excl_btns = QHBoxLayout()
        add_excl_btn = QPushButton("Add Folder...")
        add_excl_btn.setIcon(material_icon("add", "#888888"))
        add_excl_btn.clicked.connect(self._add_exclusion)
        rem_excl_btn = QPushButton("Remove Selected")
        rem_excl_btn.setIcon(material_icon("delete", "#888888"))
        rem_excl_btn.clicked.connect(self._remove_exclusion)
        row_excl_btns.addWidget(add_excl_btn)
        row_excl_btns.addWidget(rem_excl_btn)
        row_excl_btns.addStretch(1)
        ce_lay.addLayout(row_excl_btns)
        lay_excl.addWidget(card_excl, 1)

        card_roots = QFrame()
        card_roots.setProperty("card", "true")
        cr_lay = QVBoxLayout(card_roots)
        cr_lay.setContentsMargins(14, 14, 14, 14)
        cr_lay.setSpacing(8)

        cr_title = QLabel("Developer Scan Roots")
        cr_title.setProperty("strong", "true")
        self.all_drives_check = QCheckBox(
            "Automatically search all local drives for developer caches"
        )
        self.all_drives_check.setChecked(bool(self.settings.get("scan_all_drives", True)))
        cr_lay.addWidget(cr_title)
        cr_lay.addWidget(self.all_drives_check)

        self.roots_list = QListWidget()
        for root_path in self.settings.get("scan_roots", []):
            self.roots_list.addItem(root_path)
        cr_lay.addWidget(self.roots_list, 1)

        row_roots_btns = QHBoxLayout()
        add_root_btn = QPushButton("Add Root Folder...")
        add_root_btn.setIcon(material_icon("add", "#888888"))
        add_root_btn.clicked.connect(self._add_root)
        rem_root_btn = QPushButton("Remove Selected")
        rem_root_btn.setIcon(material_icon("delete", "#888888"))
        rem_root_btn.clicked.connect(self._remove_root)
        row_roots_btns.addWidget(add_root_btn)
        row_roots_btns.addWidget(rem_root_btn)
        row_roots_btns.addStretch(1)
        cr_lay.addLayout(row_roots_btns)
        lay_excl.addWidget(card_roots, 1)

        self.tab_stack.addWidget(page_excl)

        # --- PAGE 3: Scan Performance ---
        page_perf = QWidget()
        lay_perf = QVBoxLayout(page_perf)
        lay_perf.setContentsMargins(0, 4, 0, 0)
        lay_perf.setSpacing(12)

        perf_card = QFrame()
        perf_card.setProperty("card", "true")
        pc_lay = QVBoxLayout(perf_card)
        pc_lay.setContentsMargins(16, 16, 16, 16)
        pc_lay.setSpacing(14)

        pc_title = QLabel("Scanning Engine Performance")
        pc_title.setProperty("strong", "true")
        pc_lay.addWidget(pc_title)

        row_files = QHBoxLayout()
        row_files.addWidget(QLabel("Max Files Scanned per Run:"))
        self.max_files_spin = QSpinBox()
        self.max_files_spin.setRange(5000, 2000000)
        self.max_files_spin.setSingleStep(10000)
        self.max_files_spin.setSuffix(" files")
        self.max_files_spin.setValue(int(self.settings.get("max_scan_files", 200000)))
        row_files.addWidget(self.max_files_spin)

        p_fast = QPushButton("Quick (50k)")
        p_fast.clicked.connect(lambda: self.max_files_spin.setValue(50000))
        p_std = QPushButton("Standard (200k)")
        p_std.clicked.connect(lambda: self.max_files_spin.setValue(200000))
        p_deep = QPushButton("Deep (1M)")
        p_deep.clicked.connect(lambda: self.max_files_spin.setValue(1000000))
        row_files.addWidget(p_fast)
        row_files.addWidget(p_std)
        row_files.addWidget(p_deep)
        row_files.addStretch(1)
        pc_lay.addLayout(row_files)

        row_ttl = QHBoxLayout()
        row_ttl.addWidget(QLabel("Scan Cache TTL (Seconds):"))
        self.cache_ttl_spin = QSpinBox()
        self.cache_ttl_spin.setRange(0, 3600)
        self.cache_ttl_spin.setSuffix(" s")
        self.cache_ttl_spin.setValue(int(self.settings.get("scan_cache_ttl", 300)))
        row_ttl.addWidget(self.cache_ttl_spin)
        row_ttl.addStretch(1)
        pc_lay.addLayout(row_ttl)

        ttl_sub = QLabel(
            "Higher TTL avoids re-scanning unmodified directories within the specified time window."
        )
        ttl_sub.setProperty("subtle", "true")
        pc_lay.addWidget(ttl_sub)

        lay_perf.addWidget(perf_card)
        lay_perf.addStretch(1)
        self.tab_stack.addWidget(page_perf)

        # --- PAGE 4: Category Rules ---
        page_rules = QWidget()
        lay_rules = QVBoxLayout(page_rules)
        lay_rules.setContentsMargins(0, 4, 0, 0)
        lay_rules.setSpacing(10)

        rules_card = QFrame()
        rules_card.setProperty("card", "true")
        rc_lay = QVBoxLayout(rules_card)
        rc_lay.setContentsMargins(14, 14, 14, 14)
        rc_lay.setSpacing(10)

        r_header = QHBoxLayout()
        r_title = QLabel("Active Category Rules (Disabled rules are skipped)")
        r_title.setProperty("strong", "true")
        r_header.addWidget(r_title, 1)

        btn_all = QPushButton("Enable All")
        btn_all.clicked.connect(self._enable_all_categories)
        btn_safe = QPushButton("Safe Only")
        btn_safe.clicked.connect(self._enable_safe_only_categories)
        btn_none = QPushButton("Disable All")
        btn_none.clicked.connect(self._disable_all_categories)
        r_header.addWidget(btn_all)
        r_header.addWidget(btn_safe)
        r_header.addWidget(btn_none)
        rc_lay.addLayout(r_header)

        self.cat_list = QListWidget()
        self._rebuild_cat_list()
        rc_lay.addWidget(self.cat_list, 1)
        lay_rules.addWidget(rules_card)

        self.tab_stack.addWidget(page_rules)

        # --- PAGE 5: Backup & Sync ---
        page_backup = QWidget()
        lay_backup = QVBoxLayout(page_backup)
        lay_backup.setContentsMargins(0, 4, 0, 0)
        lay_backup.setSpacing(12)

        backup_card = QFrame()
        backup_card.setProperty("card", "true")
        bc_lay = QVBoxLayout(backup_card)
        bc_lay.setContentsMargins(16, 16, 16, 16)
        bc_lay.setSpacing(12)

        bc_title = QLabel("Configuration Backup & Migration")
        bc_title.setProperty("strong", "true")
        bc_sub = QLabel(
            "Export your settings to JSON to create backups or transfer rules between machines."
        )
        bc_sub.setProperty("subtle", "true")
        bc_lay.addWidget(bc_title)
        bc_lay.addWidget(bc_sub)

        bc_btns = QHBoxLayout()
        export_btn = QPushButton("Export Settings...")
        export_btn.setIcon(material_icon("download", "#888888"))
        export_btn.clicked.connect(self._export)
        import_btn = QPushButton("Import Settings...")
        import_btn.setIcon(material_icon("upload", "#888888"))
        import_btn.clicked.connect(self._import)
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setIcon(material_icon("refresh", "#888888"))
        reset_btn.clicked.connect(self._reset_defaults)

        bc_btns.addWidget(export_btn)
        bc_btns.addWidget(import_btn)
        bc_btns.addWidget(reset_btn)
        bc_btns.addStretch(1)
        bc_lay.addLayout(bc_btns)

        cfg_loc = QLabel(f"Active Config Path: {config_path()}")
        cfg_loc.setProperty("subtle", "true")
        cfg_loc.setStyleSheet("font-size: 11px; font-family: monospace;")
        bc_lay.addWidget(cfg_loc)

        lay_backup.addWidget(backup_card)
        lay_backup.addStretch(1)
        self.tab_stack.addWidget(page_backup)

        root.addWidget(self.tab_stack, 1)

    def _set_active_tab(self, key: str, index: int):
        self.tab_stack.setCurrentIndex(index)
        for k, btn in self._section_buttons.items():
            is_active = k == key
            btn.setProperty("active", "true" if is_active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _enable_all_categories(self):
        for i in range(self.cat_list.count()):
            self.cat_list.item(i).setCheckState(Qt.CheckState.Checked)

    def _disable_all_categories(self):
        for i in range(self.cat_list.count()):
            self.cat_list.item(i).setCheckState(Qt.CheckState.Unchecked)

    def _enable_safe_only_categories(self):
        cat_map = {c.id: c for c in self._categories}
        for i in range(self.cat_list.count()):
            cat_id = self.cat_list.item(i).data(Qt.ItemDataRole.UserRole)
            cat = cat_map.get(cat_id)
            if cat and cat.safety_level == SafetyLevel.SAFE:
                self.cat_list.item(i).setCheckState(Qt.CheckState.Checked)
            else:
                self.cat_list.item(i).setCheckState(Qt.CheckState.Unchecked)

    def _rebuild_cat_list(self):
        self.cat_list.clear()
        disabled_raw = self.settings.get("disabled_categories", [])
        disabled = set(disabled_raw) if isinstance(disabled_raw, (list, set, tuple)) else set()
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

    def _add_exclusion(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Choose folder to permanently exclude from cleanup"
        )
        if folder and not self.exclusions_list.findItems(folder, Qt.MatchFlag.MatchExactly):
            self.exclusions_list.addItem(folder)

    def _save_reduce_motion(self, enabled: bool):
        self.settings["reduce_motion"] = enabled
        save_settings({"reduce_motion": enabled})
        main_settings = getattr(self._main, "_settings", None)
        if isinstance(main_settings, dict):
            main_settings["reduce_motion"] = enabled

    def _select_theme(self, theme: str):
        if theme in THEMES:
            if hasattr(self, "theme_gallery"):
                self.theme_gallery.select_theme(theme, emit_signal=False)
            else:
                self.theme_combo.setCurrentIndex(THEMES.index(theme))

    def _on_theme_changed(self, theme: str):
        """Apply theme selected from the visual theme gallery."""
        self.settings["theme"] = theme
        save_settings({"theme": theme})
        switch = getattr(self._main, "switch_theme", None)
        if switch is not None:
            switch(theme)

    def _preview_theme(self, _label: str):
        """Apply the selected theme immediately and remember it across launches."""
        theme = self.theme_combo.currentData()
        if not theme:
            return
        self.settings["theme"] = theme
        save_settings({"theme": theme})
        if hasattr(self, "theme_gallery"):
            self.theme_gallery.select_theme(theme, emit_signal=False)
        switch = getattr(self._main, "switch_theme", None)
        if switch is not None:
            switch(theme)

    def apply_theme(self, theme: str):
        self._theme = theme
        if hasattr(self, "theme_gallery"):
            self.theme_gallery.select_theme(theme, emit_signal=False)

        # Update tab button icons and styles
        accent_col = theme_color(theme, "accent")
        muted_col = theme_color(theme, "muted")

        self.save_button.setIcon(material_icon("check", "#ffffff"))
        self.reset_top_btn.setIcon(material_icon("refresh", muted_col))

        curr_idx = self.tab_stack.currentIndex()
        for idx, (key, _, icon_name) in enumerate(self._sections):
            if key in self._section_buttons:
                btn = self._section_buttons[key]
                icon_col = accent_col if idx == curr_idx else muted_col
                btn.setIcon(material_icon(icon_name, icon_col))

    def _remove_exclusion(self):
        for item in self.exclusions_list.selectedItems():
            self.exclusions_list.takeItem(self.exclusions_list.row(item))

    def _save(self):
        roots = [self.roots_list.item(i).text() for i in range(self.roots_list.count())]
        exclusions = [
            self.exclusions_list.item(i).text() for i in range(self.exclusions_list.count())
        ]
        disabled = [
            self.cat_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.cat_list.count())
            if self.cat_list.item(i).checkState() == Qt.CheckState.Unchecked
        ]
        settings = {
            "theme": self.theme_combo.currentData(),
            "reduce_motion": self.reduce_motion_check.isChecked(),
            "dry_run_default": self.dry_run_check.isChecked(),
            "confirm_cleanup": self.confirm_check.isChecked(),
            "use_recycle_bin": self.recycle_check.isChecked(),
            "auto_rescan_after_cleanup": self.auto_rescan_check.isChecked(),
            "show_command_preview": self.cmd_preview_check.isChecked(),
            "scan_roots": roots,
            "excluded_paths": exclusions,
            "scan_all_drives": self.all_drives_check.isChecked(),
            "scan_cache_ttl": self.cache_ttl_spin.value(),
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
            self._select_theme(self.settings.get("theme", "dark"))
            self.dry_run_check.setChecked(self.settings.get("dry_run_default", True))
            self.confirm_check.setChecked(self.settings.get("confirm_cleanup", True))
            self.recycle_check.setChecked(bool(self.settings.get("use_recycle_bin", True)))
            self.auto_rescan_check.setChecked(
                bool(self.settings.get("auto_rescan_after_cleanup", True))
            )
            self.cmd_preview_check.setChecked(bool(self.settings.get("show_command_preview", True)))
            self.reduce_motion_check.setChecked(bool(self.settings.get("reduce_motion", False)))
            self.max_files_spin.setValue(int(self.settings.get("max_scan_files", 200000)))
            self.all_drives_check.setChecked(bool(self.settings.get("scan_all_drives", True)))
            self.cache_ttl_spin.setValue(int(self.settings.get("scan_cache_ttl", 300)))
            self.roots_list.clear()
            self.exclusions_list.clear()
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
            self._select_theme(self.settings.get("theme", "dark"))
            self.dry_run_check.setChecked(self.settings.get("dry_run_default", True))
            self.confirm_check.setChecked(self.settings.get("confirm_cleanup", True))
            self.recycle_check.setChecked(bool(self.settings.get("use_recycle_bin", True)))
            self.auto_rescan_check.setChecked(
                bool(self.settings.get("auto_rescan_after_cleanup", True))
            )
            self.cmd_preview_check.setChecked(bool(self.settings.get("show_command_preview", True)))
            self.reduce_motion_check.setChecked(bool(self.settings.get("reduce_motion", False)))
            self.max_files_spin.setValue(int(self.settings.get("max_scan_files", 200000)))
            self.all_drives_check.setChecked(bool(self.settings.get("scan_all_drives", True)))
            self.cache_ttl_spin.setValue(int(self.settings.get("scan_cache_ttl", 300)))
            self.roots_list.clear()
            for root_path in self.settings.get("scan_roots", []):
                self.roots_list.addItem(root_path)
            self.exclusions_list.clear()
            for excl_path in self.settings.get("excluded_paths", []):
                self.exclusions_list.addItem(excl_path)
            self._rebuild_cat_list()
            self._main.apply_settings()
            QMessageBox.information(self, "Import Settings", "Settings imported successfully.")
        except OSError as exc:
            QMessageBox.warning(self, "Import Error", str(exc))


class SquircleAvatarWidget(QWidget):
    """Profile avatar rendered inside a smooth anti-aliased squircle (rounded-rect) path."""

    def __init__(
        self,
        image_path: str = "",
        size: int = 120,
        radius: int = 28,
        initials: str = "PJ",
        parent=None,
    ):
        super().__init__(parent)
        self.image_path = image_path
        self._size = size
        self._radius = radius
        self._initials = initials
        self.setFixedSize(size, size)
        self._pixmap = QPixmap(image_path) if image_path and os.path.exists(image_path) else None

    def set_avatar_path(self, image_path: str):
        self.image_path = image_path
        self._pixmap = QPixmap(image_path) if os.path.exists(image_path) else None
        self.update()

    def set_pixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        rect = QRectF(1.5, 1.5, self._size - 3, self._size - 3)
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
            painter.setBrush(QBrush(QColor("#2563eb")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(0, 0, self._size, self._size)
            painter.setPen(QColor("#ffffff"))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(8, int(self._size * 0.36)))
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._initials)

        painter.setClipping(False)
        pen = QPen(QColor(59, 130, 246, 160), 1.5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, self._radius, self._radius)
        painter.end()


class SpecsView(QWidget):
    """PC hardware, memory, graphics, storage, and Operating System specifications inspector."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self._theme = "dark"
        self._specs = None
        self._health_data: list = []
        self._active_category = "All"
        self._filter_query = ""
        self._card_widgets = []
        self._skeleton_anims = []
        self._build_ui()
        self._show_skeletons()

    def _build_ui(self):
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(28, 24, 28, 24)
        root_lay.setSpacing(16)

        # 1. Header with title, subtitle, and primary actions
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        h1 = QLabel("System Hardware & OS Specifications")
        h1.setObjectName("ViewTitle")
        sub = QLabel("Real-time hardware diagnostics, utilization gauges, and OS details.")
        sub.setProperty("subtle", "true")
        titles.addWidget(h1)
        titles.addWidget(sub)
        header.addLayout(titles)
        header.addStretch(1)

        self.copy_btn = QPushButton("Copy Summary")
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

        # 2. Quick Specs Hero Strip (4 Key Stats)
        self.hero_container = QHBoxLayout()
        self.hero_container.setSpacing(12)
        root_lay.addLayout(self.hero_container)

        # 3. Filter Chips & Search Toolbar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)

        self.chip_buttons = {}
        categories = [
            ("All", "All Components"),
            ("cpu_ram", "CPU && RAM"),
            ("gpu", "Graphics"),
            ("storage", "Storage"),
            ("motherboard", "Motherboard"),
            ("os_net", "OS && Network"),
        ]
        for key, label in categories:
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if key == "All":
                btn.setProperty("primary", "true")
            else:
                btn.setProperty("secondary", "true")
            btn.clicked.connect(lambda _=False, k=key: self._set_category(k))
            self.chip_buttons[key] = btn
            filter_bar.addWidget(btn)

        filter_bar.addStretch(1)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search specifications (e.g. RTX, Ryzen, NVMe)...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(280)
        self.search_edit.textChanged.connect(self._on_search_changed)
        filter_bar.addWidget(self.search_edit)

        root_lay.addLayout(filter_bar)

        # 4. Scrollable 2-Column Content Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 4, 0, 16)
        self.content_layout.setSpacing(14)

        # 2-Column container
        self.grid_widget = QWidget()
        self.grid_layout = QHBoxLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(14)

        self.col_left = QVBoxLayout()
        self.col_left.setSpacing(14)
        self.col_right = QVBoxLayout()
        self.col_right.setSpacing(14)

        self.grid_layout.addLayout(self.col_left, 1)
        self.grid_layout.addLayout(self.col_right, 1)

        self.content_layout.addWidget(self.grid_widget)
        self.content_layout.addStretch(1)

        scroll.setWidget(content)
        root_lay.addWidget(scroll, 1)

    def _show_skeletons(self):
        """Render modern animated skeleton placeholder blocks while loading."""
        self._clear_animations()

        # 1. Clear Hero
        while self.hero_container.count():
            item = self.hero_container.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        # 2. Clear Columns
        while self.col_left.count():
            item = self.col_left.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        while self.col_right.count():
            item = self.col_right.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        self._card_widgets.clear()

        # 3. Add 4 Hero Skeletons
        hero_titles = ["PROCESSOR", "GRAPHICS", "MEMORY (RAM)", "OPERATING SYSTEM"]
        for idx, title in enumerate(hero_titles):
            card = QFrame()
            card.setObjectName("SpecsHeroCard")
            card.setProperty("card", "true")
            lay = QVBoxLayout(card)
            lay.setContentsMargins(14, 12, 14, 12)
            lay.setSpacing(8)

            t_lbl = QLabel(title)
            t_lbl.setStyleSheet(
                f"font-size: 11px; font-weight: 700; color: {_c(self._theme, 'muted')}; letter-spacing: 0.5px;"
            )
            lay.addWidget(t_lbl)

            bar1 = SkeletonBlock(height=16, radius=4, theme=self._theme)
            lay.addWidget(bar1)

            bar2 = SkeletonBlock(width=130, height=11, radius=3, theme=self._theme)
            lay.addWidget(bar2)

            self._apply_skeleton_pulse(card, delay_offset=idx * 120)
            self.hero_container.addWidget(card)

        # 4. Add Left Column Skeleton Cards
        left_skeletons = [
            ("Operating System Details", 5),
            ("Central Processor (CPU)", 6),
            ("Motherboard & BIOS", 4),
            ("Network Interfaces", 3),
        ]
        for idx, (title, row_count) in enumerate(left_skeletons):
            card = self._make_skeleton_card(title, row_count)
            self._apply_skeleton_pulse(card, delay_offset=(idx + 4) * 100)
            self.col_left.addWidget(card)

        # 5. Add Right Column Skeleton Cards
        right_skeletons = [
            ("Physical Memory & RAM Slots", 4),
            ("Graphics & Display Adapters", 5),
            ("Storage & NVMe Drives", 4),
        ]
        for idx, (title, row_count) in enumerate(right_skeletons):
            card = self._make_skeleton_card(title, row_count)
            self._apply_skeleton_pulse(card, delay_offset=(idx + 8) * 100)
            self.col_right.addWidget(card)

        self.col_left.addStretch(1)
        self.col_right.addStretch(1)

    def _make_skeleton_card(self, title: str, row_count: int) -> QFrame:
        card = QFrame()
        card.setObjectName("SpecsCard")
        card.setProperty("card", "true")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {_c(self._theme, 'text')};")
        hdr.addWidget(t_lbl)
        hdr.addStretch(1)

        copy_skel = SkeletonBlock(width=52, height=22, radius=4, theme=self._theme)
        hdr.addWidget(copy_skel)
        lay.addLayout(hdr)

        # Key-Value Skeleton Rows
        for i in range(row_count):
            row = QHBoxLayout()
            row.setSpacing(12)
            lbl_skel = SkeletonBlock(width=120, height=13, radius=3, theme=self._theme)
            row.addWidget(lbl_skel)

            val_width = None if i % 2 == 0 else 180
            val_skel = SkeletonBlock(width=val_width, height=13, radius=3, theme=self._theme)
            row.addWidget(val_skel, 1)

            lay.addLayout(row)

        return card

    def _apply_skeleton_pulse(self, widget: QWidget, delay_offset: int = 0):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(1400)
        anim.setKeyValueAt(0.0, 0.40)
        anim.setKeyValueAt(0.5, 0.85)
        anim.setKeyValueAt(1.0, 0.40)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        anim.setLoopCount(-1)
        if delay_offset > 0:
            QTimer.singleShot(delay_offset % 1000, anim.start)
        else:
            anim.start()
        self._skeleton_anims.append(anim)

    def _clear_animations(self):
        for anim in self._skeleton_anims:
            try:
                anim.stop()
            except Exception:
                pass
        self._skeleton_anims.clear()

    def _set_category(self, category_key: str):
        self._active_category = category_key
        for k, btn in self.chip_buttons.items():
            if k == category_key:
                btn.setProperty("primary", "true")
                btn.setProperty("secondary", None)
            else:
                btn.setProperty("primary", None)
                btn.setProperty("secondary", "true")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._apply_filter()

    def _on_search_changed(self, text: str):
        self._filter_query = text.strip().lower()
        self._apply_filter()

    def _apply_filter(self):
        for card_widget, category, searchable_text in self._card_widgets:
            match_cat = (self._active_category == "All") or (self._active_category == category)
            match_text = (not self._filter_query) or (self._filter_query in searchable_text.lower())
            card_widget.setVisible(match_cat and match_text)

    def refresh_specs(self):
        if self._specs is None:
            self._show_skeletons()
        from crapcleaner.gui.workers import SpecsWorker, stop_worker

        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Loading...")

        stop_worker(getattr(self, "_worker", None))

        worker = SpecsWorker(parent=self)
        self._worker = worker
        worker.done.connect(self._on_specs_loaded)
        worker.failed.connect(self._on_specs_failed)
        worker.finished.connect(
            lambda: (
                setattr(self, "_worker", None) if getattr(self, "_worker", None) is worker else None
            )
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def closeEvent(self, event):
        from crapcleaner.gui.workers import stop_worker

        stop_worker(getattr(self, "_worker", None))
        super().closeEvent(event)

    def _on_specs_loaded(self, specs, health_data):
        self._specs = specs
        self._health_data = health_data
        self._populate(specs, health_data)
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh Specs")

    def _on_specs_failed(self, msg: str):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh Specs")
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.warning(self, "Specs Error", f"Could not load system specifications:\n{msg}")

    def _make_hero_card(
        self, title: str, main_val: str, sub_val: str, badge_type: str = "accent"
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("SpecsHeroCard")
        card.setProperty("card", "true")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        title_lbl = QLabel(title.upper())
        title_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {_c(self._theme, 'muted')}; letter-spacing: 0.5px; background: transparent; border: none;"
        )
        top_row.addWidget(title_lbl)
        top_row.addStretch(1)
        lay.addLayout(top_row)

        val_lbl = QLabel(main_val)
        val_lbl.setStyleSheet(
            "font-size: 14px; font-weight: 700; background: transparent; border: none;"
        )
        val_lbl.setWordWrap(True)
        lay.addWidget(val_lbl)

        if sub_val:
            sub_lbl = QLabel(sub_val)
            sub_lbl.setStyleSheet(
                f"font-size: 11px; color: {_c(self._theme, 'muted')}; background: transparent; border: none;"
            )
            lay.addWidget(sub_lbl)

        return card

    def _make_card_frame(
        self,
        title: str,
        category: str,
        rows: list[tuple[str, str]],
        copy_text: str,
    ) -> tuple[QFrame, str]:
        card = QFrame()
        card.setObjectName("SpecsCard")
        card.setProperty("card", "true")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(18, 14, 18, 14)
        card_lay.setSpacing(10)

        # Header Row
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(
            "font-size: 14px; font-weight: 700; background: transparent; border: none;"
        )
        header_row.addWidget(t_lbl)
        header_row.addStretch(1)

        copy_btn = QPushButton("Copy")
        copy_btn.setProperty("secondary", "true")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setFixedHeight(26)
        copy_btn.setMinimumWidth(56)
        copy_btn.setStyleSheet("font-size: 12px; font-weight: 600; padding: 2px 10px;")
        copy_btn.clicked.connect(lambda _=False, text=copy_text: self._copy_single(text))
        header_row.addWidget(copy_btn)

        card_lay.addLayout(header_row)

        # Key-Value Rows
        searchable_lines = [title]
        for label, val in rows:
            row = QHBoxLayout()
            row.setSpacing(10)
            lbl = QLabel(label)
            lbl.setMinimumWidth(130)
            lbl.setMaximumWidth(160)
            lbl.setStyleSheet(
                f"color: {_c(self._theme, 'muted')}; font-size: 13px; font-weight: 600; background: transparent; border: none;"
            )

            val_lbl = QLabel(val)
            val_lbl.setStyleSheet("font-size: 13px; background: transparent; border: none;")
            val_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            val_lbl.setWordWrap(True)

            row.addWidget(lbl)
            row.addWidget(val_lbl, 1)
            card_lay.addLayout(row)
            searchable_lines.append(f"{label} {val}")

        searchable_text = " ".join(searchable_lines)
        return card, searchable_text

    def _copy_single(self, text: str):
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copied", "Component specifications copied to clipboard!")

    def _populate(self, specs, health_data: list | None = None):
        self._clear_animations()

        # 1. Clear Hero
        while self.hero_container.count():
            item = self.hero_container.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        # 2. Clear Grid Columns
        while self.col_left.count():
            item = self.col_left.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        while self.col_right.count():
            item = self.col_right.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()

        self._card_widgets.clear()

        # 3. Populate Hero Strip (4 Cards)
        # Hero 1: CPU
        cpu_short = specs.cpu.name.replace("Processor", "").replace("8-Core", "").strip()
        self.hero_container.addWidget(
            self._make_hero_card(
                "Processor",
                cpu_short,
                f"{specs.cpu.cores_physical} Cores · {specs.cpu.cores_logical} Threads",
            )
        )

        # Hero 2: Primary GPU
        primary_gpu = specs.gpus[0].name if specs.gpus else "Display Adapter"
        gpu_sub = (
            f"{format_size(specs.gpus[0].adapter_ram_bytes)} VRAM"
            if specs.gpus and specs.gpus[0].adapter_ram_bytes
            else (specs.gpus[0].driver_version if specs.gpus else "")
        )
        self.hero_container.addWidget(self._make_hero_card("Graphics", primary_gpu, gpu_sub))

        # Hero 3: Memory
        mem_tot = format_size(specs.memory.total_bytes)
        mem_used = format_size(specs.memory.used_bytes)
        self.hero_container.addWidget(
            self._make_hero_card(
                "Memory (RAM)", mem_tot, f"{mem_used} Used ({specs.memory.percent_used}%)"
            )
        )

        # Hero 4: OS
        os_short = f"{specs.os.name} {specs.os.architecture}"
        self.hero_container.addWidget(
            self._make_hero_card(
                "Operating System",
                os_short,
                f"Build {specs.os.build_number} · Up {specs.os.uptime}",
            )
        )

        # 4. Left Column Cards (OS, CPU, Motherboard, Network)
        # Card 1: Operating System
        os_rows = [
            ("Operating System", f"{specs.os.name} ({specs.os.architecture})"),
            ("Build & Version", specs.os.build_number),
            ("System Uptime", specs.os.uptime),
            ("Computer Name", specs.os.computer_name),
            ("Current User", specs.os.user_name),
        ]
        os_copy = f"Operating System: {specs.os.name} ({specs.os.architecture})\nBuild: {specs.os.build_number}\nUptime: {specs.os.uptime}\nComputer: {specs.os.computer_name}\\{specs.os.user_name}"
        os_card, os_search = self._make_card_frame("Operating System", "os_net", os_rows, os_copy)
        self.col_left.addWidget(os_card)
        self._card_widgets.append((os_card, "os_net", os_search))

        # Card 2: CPU Processor
        cpu_rows = [
            ("Processor", specs.cpu.name),
            ("Architecture", specs.cpu.architecture),
            ("Physical Cores", f"{specs.cpu.cores_physical} Cores"),
            ("Logical Processors", f"{specs.cpu.cores_logical} Threads"),
        ]
        if specs.cpu.max_clock_speed_mhz:
            cpu_rows.append(("Base Clock Speed", f"{specs.cpu.max_clock_speed_mhz} MHz"))
        cpu_copy = f"Processor: {specs.cpu.name}\nArchitecture: {specs.cpu.architecture}\nCores: {specs.cpu.cores_physical} Physical, {specs.cpu.cores_logical} Logical\nClock Speed: {specs.cpu.max_clock_speed_mhz} MHz"
        cpu_card, cpu_search = self._make_card_frame(
            "CPU (Processor)", "cpu_ram", cpu_rows, cpu_copy
        )
        self.col_left.addWidget(cpu_card)
        self._card_widgets.append((cpu_card, "cpu_ram", cpu_search))

        # Card 3: Motherboard & BIOS
        mb_rows = [
            ("Manufacturer", specs.motherboard.manufacturer),
            ("Product Model", specs.motherboard.product),
            ("BIOS Version", specs.motherboard.bios_version),
            ("BIOS Release Date", specs.motherboard.bios_date),
        ]
        mb_copy = f"Motherboard: {specs.motherboard.manufacturer} {specs.motherboard.product}\nBIOS: {specs.motherboard.bios_version} ({specs.motherboard.bios_date})"
        mb_card, mb_search = self._make_card_frame(
            "Motherboard & BIOS", "motherboard", mb_rows, mb_copy
        )
        self.col_left.addWidget(mb_card)
        self._card_widgets.append((mb_card, "motherboard", mb_search))

        # Card 4: Network Interfaces Card (Clean Full-Width List)
        net_card = QFrame()
        net_card.setObjectName("SpecsCard")
        net_card.setProperty("card", "true")
        net_lay = QVBoxLayout(net_card)
        net_lay.setContentsMargins(18, 14, 18, 14)
        net_lay.setSpacing(10)

        net_head = QHBoxLayout()
        net_title = QLabel("Network Interfaces")
        net_title.setStyleSheet(
            "font-size: 14px; font-weight: 700; background: transparent; border: none;"
        )
        net_head.addWidget(net_title)
        net_head.addStretch(1)

        net_copy_lines = ["Network Interfaces:"]
        for net in specs.network:
            net_copy_lines.append(f"- {net.adapter_name}: {net.ip_address} ({net.status})")
        net_copy_btn = QPushButton("Copy")
        net_copy_btn.setProperty("secondary", "true")
        net_copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        net_copy_btn.setFixedHeight(26)
        net_copy_btn.setMinimumWidth(56)
        net_copy_btn.setStyleSheet("font-size: 12px; font-weight: 600; padding: 2px 10px;")
        net_copy_btn.clicked.connect(
            lambda _=False, text="\n".join(net_copy_lines): self._copy_single(text)
        )
        net_head.addWidget(net_copy_btn)
        net_lay.addLayout(net_head)

        net_search_lines = ["Network Interfaces Ethernet Wi-Fi"]
        for i, net in enumerate(specs.network):
            n_box = QVBoxLayout()
            n_box.setSpacing(3)
            n_name = QLabel(f"<b>{net.adapter_name}</b>")
            n_name.setStyleSheet("font-size: 13px; background: transparent; border: none;")
            n_name.setWordWrap(True)
            n_box.addWidget(n_name)

            n_ip = QLabel(f"IPv4 Address: {net.ip_address} • Status: {net.status}")
            n_ip.setStyleSheet(
                f"font-size: 12px; color: {_c(self._theme, 'muted')}; background: transparent; border: none;"
            )
            n_box.addWidget(n_ip)
            net_lay.addLayout(n_box)

            if i < len(specs.network) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet(
                    f"background-color: {_c(self._theme, 'border')}; max-height: 1px;"
                )
                net_lay.addWidget(sep)
            net_search_lines.append(f"{net.adapter_name} {net.ip_address}")

        self.col_left.addWidget(net_card)
        self._card_widgets.append((net_card, "os_net", " ".join(net_search_lines)))
        self.col_left.addStretch(1)

        # 5. Right Column Cards (RAM, GPUs, Storage Drives)
        # Card 5: Memory (RAM) with Live Gauge
        ram_card = QFrame()
        ram_card.setObjectName("SpecsCard")
        ram_card.setProperty("card", "true")
        ram_lay = QVBoxLayout(ram_card)
        ram_lay.setContentsMargins(18, 14, 18, 14)
        ram_lay.setSpacing(10)

        ram_header = QHBoxLayout()
        ram_header.setSpacing(8)
        ram_title = QLabel("Memory (RAM)")
        ram_title.setStyleSheet(
            "font-size: 14px; font-weight: 700; background: transparent; border: none;"
        )
        ram_header.addWidget(ram_title)
        ram_header.addStretch(1)

        ram_copy_btn = QPushButton("Copy")
        ram_copy_btn.setProperty("secondary", "true")
        ram_copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ram_copy_btn.setFixedHeight(26)
        ram_copy_btn.setMinimumWidth(56)
        ram_copy_btn.setStyleSheet("font-size: 12px; font-weight: 600; padding: 2px 10px;")
        ram_copy_text = f"Memory: Total {format_size(specs.memory.total_bytes)}, Used {format_size(specs.memory.used_bytes)} ({specs.memory.percent_used}%), Available {format_size(specs.memory.available_bytes)}"
        ram_copy_btn.clicked.connect(lambda _=False, text=ram_copy_text: self._copy_single(text))
        ram_header.addWidget(ram_copy_btn)
        ram_lay.addLayout(ram_header)

        # Progress bar
        ram_bar = QProgressBar()
        ram_bar.setFixedHeight(8)
        ram_bar.setTextVisible(False)
        ram_bar.setRange(0, 100)
        ram_bar.setValue(int(specs.memory.percent_used))
        ram_lay.addWidget(ram_bar)

        ram_rows = [
            ("Total Physical RAM", format_size(specs.memory.total_bytes)),
            (
                "Used Memory",
                f"{format_size(specs.memory.used_bytes)} ({specs.memory.percent_used}% load)",
            ),
            ("Available Memory", format_size(specs.memory.available_bytes)),
        ]
        ram_search_lines = ["Memory RAM"]
        for label, val in ram_rows:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setMinimumWidth(130)
            lbl.setMaximumWidth(160)
            lbl.setStyleSheet(
                f"color: {_c(self._theme, 'muted')}; font-size: 13px; font-weight: 600; background: transparent; border: none;"
            )
            val_lbl = QLabel(val)
            val_lbl.setStyleSheet("font-size: 13px; background: transparent; border: none;")
            val_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(lbl)
            row.addWidget(val_lbl, 1)
            ram_lay.addLayout(row)
            ram_search_lines.append(f"{label} {val}")

        self.col_right.addWidget(ram_card)
        self._card_widgets.append((ram_card, "cpu_ram", " ".join(ram_search_lines)))

        # Card 6: Graphics (GPU) Cards
        gpu_card = QFrame()
        gpu_card.setObjectName("SpecsCard")
        gpu_card.setProperty("card", "true")
        g_lay = QVBoxLayout(gpu_card)
        g_lay.setContentsMargins(18, 14, 18, 14)
        g_lay.setSpacing(10)

        g_head = QHBoxLayout()
        g_title = QLabel("Graphics (Video Adapters)")
        g_title.setStyleSheet(
            "font-size: 14px; font-weight: 700; background: transparent; border: none;"
        )
        g_head.addWidget(g_title)
        g_head.addStretch(1)

        gpu_copy_lines = ["Graphics Adapters:"]
        for g in specs.gpus:
            gpu_copy_lines.append(
                f"- {g.name} (Driver: {g.driver_version}, VRAM: {format_size(g.adapter_ram_bytes)}, Res: {g.resolution})"
            )
        g_copy_btn = QPushButton("Copy")
        g_copy_btn.setProperty("secondary", "true")
        g_copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        g_copy_btn.setFixedHeight(26)
        g_copy_btn.setMinimumWidth(56)
        g_copy_btn.setStyleSheet("font-size: 12px; font-weight: 600; padding: 2px 10px;")
        g_copy_btn.clicked.connect(
            lambda _=False, text="\n".join(gpu_copy_lines): self._copy_single(text)
        )
        g_head.addWidget(g_copy_btn)
        g_lay.addLayout(g_head)

        gpu_search_lines = ["Graphics GPU Video"]
        for i, gpu in enumerate(specs.gpus):
            g_box = QVBoxLayout()
            g_box.setSpacing(4)
            g_name = QLabel(f"<b>{gpu.name}</b>")
            g_name.setStyleSheet("font-size: 13px; background: transparent; border: none;")
            g_box.addWidget(g_name)

            detail_parts = []
            if gpu.adapter_ram_bytes:
                detail_parts.append(f"VRAM: {format_size(gpu.adapter_ram_bytes)}")
            if gpu.driver_version:
                detail_parts.append(f"Driver: {gpu.driver_version}")
            if gpu.resolution:
                clean_res = gpu.resolution.split(" x 4294967296")[0].split(" x 16777216")[0].strip()
                detail_parts.append(f"Resolution: {clean_res}")

            if detail_parts:
                d_lbl = QLabel(" • ".join(detail_parts))
                d_lbl.setStyleSheet(
                    f"font-size: 12px; color: {_c(self._theme, 'muted')}; background: transparent; border: none;"
                )
                d_lbl.setWordWrap(True)
                g_box.addWidget(d_lbl)

            g_lay.addLayout(g_box)
            if i < len(specs.gpus) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet(
                    f"background-color: {_c(self._theme, 'border')}; max-height: 1px;"
                )
                g_lay.addWidget(sep)
            gpu_search_lines.append(f"{gpu.name} {gpu.driver_version} {gpu.resolution}")

        self.col_right.addWidget(gpu_card)
        self._card_widgets.append((gpu_card, "gpu", " ".join(gpu_search_lines)))

        # Card 7: Storage Drives Card
        drive_card = QFrame()
        drive_card.setObjectName("SpecsCard")
        drive_card.setProperty("card", "true")
        d_lay = QVBoxLayout(drive_card)
        d_lay.setContentsMargins(18, 14, 18, 14)
        d_lay.setSpacing(12)

        d_head = QHBoxLayout()
        d_title = QLabel("Storage Drives & Partitions")
        d_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        d_head.addWidget(d_title)
        d_head.addStretch(1)

        drive_copy_lines = ["Storage Drives:"]
        for d in specs.drives:
            d_name = (
                d.drive.rstrip(":").rstrip("\\") + ":"
                if is_windows()
                else linux_drive_display_name(d.drive)
            )
            drive_copy_lines.append(
                f"- Drive {d_name} {format_size(d.used_bytes)} / {format_size(d.total_bytes)} ({d.percent_used}% full) | Free: {format_size(d.free_bytes)} [{d.file_system}]"
            )
        d_copy_btn = QPushButton("Copy")
        d_copy_btn.setProperty("secondary", "true")
        d_copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        d_copy_btn.setFixedHeight(26)
        d_copy_btn.setMinimumWidth(56)
        d_copy_btn.setStyleSheet("font-size: 12px; font-weight: 600; padding: 2px 10px;")
        d_copy_btn.clicked.connect(
            lambda _=False, text="\n".join(drive_copy_lines): self._copy_single(text)
        )
        d_head.addWidget(d_copy_btn)
        d_lay.addLayout(d_head)

        # Build a drive-letter -> media type lookup from pre-fetched health data
        health_lookup: dict[str, str] = {}
        for dh in health_data or []:
            if is_windows():
                key = dh.device_id.upper().rstrip("\\")
                if not key.endswith(":"):
                    key = key + ":"
            else:
                key = dh.device_id.rstrip("/").upper() or "/"
            health_lookup[key] = f"{dh.media_type} · {dh.bus_type}"

        drive_search_lines = ["Storage Drives SSD NVMe"]
        for d in specs.drives:
            d_box = QVBoxLayout()
            d_box.setSpacing(4)
            d_row_head = QHBoxLayout()
            fs_info = f" [{d.file_system}]" if d.file_system else ""
            label_info = f" ({d.label})" if d.label else ""
            d_name = (
                d.drive.rstrip(":").rstrip("\\") + ":"
                if is_windows()
                else linux_drive_display_name(d.drive)
            )
            path_info = "" if is_windows() else f" <span style='font-weight:400'>{d.drive}</span>"
            name_lbl = QLabel(f"<b>Drive {d_name}</b>{path_info}{label_info}{fs_info}")
            name_lbl.setStyleSheet("font-size: 13px; background: transparent; border: none;")
            used_str = format_size(d.used_bytes)
            tot_str = format_size(d.total_bytes)
            free_str = format_size(d.free_bytes)

            # Disk type on the right of the header row
            drive_key = (
                (d_name if d_name.endswith(":") else d_name + ":").upper()
                if is_windows()
                else (d.drive.rstrip("/").upper() or "/")
            )
            disk_type_str = health_lookup.get(drive_key, "")
            if not disk_type_str and not is_windows():
                disk_type_str = linux_drive_display_kind(d.drive).title()

            d_row_head.addWidget(name_lbl)
            d_row_head.addStretch(1)

            if disk_type_str:
                type_lbl = QLabel(disk_type_str)
                type_lbl.setStyleSheet(
                    f"font-size: 11px; color: {_c(self._theme, 'muted')}; background: transparent; border: none;"
                )
                d_row_head.addWidget(type_lbl)

            d_box.addLayout(d_row_head)

            stat_lbl = QLabel(f"{used_str} / {tot_str} ({d.percent_used}%) · Free: {free_str}")
            stat_lbl.setStyleSheet(
                f"font-size: 12px; color: {_c(self._theme, 'muted')}; background: transparent; border: none;"
            )
            d_box.addWidget(stat_lbl)

            bar = QProgressBar()
            bar.setFixedHeight(6)
            bar.setTextVisible(False)
            bar.setRange(0, 100)
            bar.setValue(d.percent_used)
            d_box.addWidget(bar)
            d_lay.addLayout(d_box)
            drive_search_lines.append(
                f"{d.drive} {d.label} {d.file_system} {disk_type_str} {used_str} {tot_str}"
            )

        self.col_right.addWidget(drive_card)
        self._card_widgets.append((drive_card, "storage", " ".join(drive_search_lines)))
        self.col_right.addStretch(1)

        # Apply any active filter
        self._apply_filter()

    def _copy_specs(self):
        if self._specs is None:
            self.refresh_specs()
        if self._specs is None:
            return
        import contextlib
        import io

        from crapcleaner.system.hardware import print_specs_summary

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
            self._populate(self._specs, self._health_data)
        else:
            self._show_skeletons()


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
        sub = QLabel("Open-source, non-destructive system cleaner and developer storage toolkit.")
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
        c_name.setStyleSheet("font-size: 24px; font-weight: 800;")
        info_box.addWidget(c_name)

        c_desc = QLabel(
            "Engineered CrapCleaner from the ground up to give Windows and Linux power users, developers, and gamers "
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
        gh_btn.setIcon(material_icon("code", _c(self._theme, "text")))
        gh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gh_btn.clicked.connect(
            lambda: subprocess.Popen(["explorer", "https://github.com/PatrickJnr/crapcleaner"])
        )
        links_row.addWidget(gh_btn)

        issue_btn = QPushButton("Report Issue")
        issue_btn.setProperty("secondary", "true")
        issue_btn.setIcon(material_icon("bug_report", _c(self._theme, "text")))
        issue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        issue_btn.clicked.connect(
            lambda: subprocess.Popen(
                ["explorer", "https://github.com/PatrickJnr/crapcleaner/issues"]
            )
        )
        links_row.addWidget(issue_btn)

        update_btn = QPushButton("Check for Updates")
        update_btn.setProperty("primary", "true")
        update_btn.setIcon(material_icon("refresh", "#ffffff"))
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
        app_title.setStyleSheet("font-size: 15px; font-weight: 700;")
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
            v_lbl.setStyleSheet("font-size: 12px;")
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
        s_title.setStyleSheet("font-size: 15px; font-weight: 700;")
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
            t_lbl = QLabel(title_str)
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

        # 3. Contributors & Credits Card
        contrib_card = QFrame()
        contrib_card.setProperty("card", "true")
        contrib_lay = QVBoxLayout(contrib_card)
        contrib_lay.setContentsMargins(18, 16, 18, 16)
        contrib_lay.setSpacing(12)

        c_header = QHBoxLayout()
        c_title = QLabel("GitHub Contributors & Credits")
        c_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        c_header.addWidget(c_title)
        c_header.addStretch(1)

        refresh_contrib_btn = QPushButton("Refresh")
        refresh_contrib_btn.setProperty("secondary", "true")
        refresh_contrib_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_contrib_btn.clicked.connect(lambda: self._populate_contributors(force_refresh=True))
        c_header.addWidget(refresh_contrib_btn)
        contrib_lay.addLayout(c_header)

        self.contrib_box = QVBoxLayout()
        self.contrib_box.setSpacing(8)
        contrib_lay.addLayout(self.contrib_box)
        c_lay.addWidget(contrib_card)

        c_lay.addStretch(1)
        scroll.setWidget(content)
        root_lay.addWidget(scroll, 1)
        self._populate_contributors()

    def _populate_contributors(self, force_refresh: bool = False):
        while self.contrib_box.count():
            item = self.contrib_box.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()
                elif item.layout():
                    lay = item.layout()
                    if lay is not None:
                        while lay.count():
                            sub_item = lay.takeAt(0)
                            if sub_item is not None:
                                sub_w = sub_item.widget()
                                if sub_w is not None:
                                    sub_w.deleteLater()

        try:
            contributors = fetch_contributors(timeout_seconds=3.0, force_refresh=force_refresh)
            # Filter out project creator/maintainer since they have the primary creator hero card
            community = [
                c for c in contributors if c.login.lower() not in ("patrickjnr", "patrickjr")
            ]
            if not community:
                empty_lbl = QLabel(
                    "No community contributors yet. Contributions welcome on GitHub!"
                )
                empty_lbl.setProperty("subtle", "true")
                self.contrib_box.addWidget(empty_lbl)
                return

            for c in community:
                row = QHBoxLayout()
                row.setSpacing(12)

                # Contributor Avatar
                avatar_file = fetch_avatar_file(c.avatar_url, c.login, timeout_seconds=1.5)
                initials = c.login[:2].upper() if c.login else "??"
                av_widget = SquircleAvatarWidget(
                    image_path=avatar_file or "",
                    size=36,
                    radius=10,
                    initials=initials,
                )
                row.addWidget(av_widget)

                name_lbl = QLabel(f"<b>@{c.login}</b>")
                name_lbl.setStyleSheet("font-size: 13px;")
                row.addWidget(name_lbl)

                badge_lbl = badge(
                    f"{c.contributions} {'contribution' if c.contributions == 1 else 'contributions'}",
                    "accent",
                )
                badge_lbl.setFixedHeight(20)
                row.addWidget(badge_lbl)
                row.addStretch(1)

                gh_profile_btn = QPushButton("GitHub Profile")
                gh_profile_btn.setProperty("secondary", "true")
                gh_profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                gh_profile_btn.clicked.connect(
                    lambda _=False, url=c.html_url: subprocess.Popen(["explorer", url])
                )
                row.addWidget(gh_profile_btn)
                self.contrib_box.addLayout(row)
        except Exception as exc:
            err_lbl = QLabel(f"Could not load contributors: {exc}")
            err_lbl.setProperty("subtle", "true")
            self.contrib_box.addWidget(err_lbl)

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

        self.export_btn = QPushButton("Export Report...")
        self.export_btn.setIcon(material_icon("file_download", _c(self._theme, "text")))
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.clicked.connect(self._export_report)
        toolbar.addWidget(self.export_btn)

        root_lay.addLayout(toolbar)

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

        stop_worker(getattr(self, "_analysis_worker", None))

        depth = self.depth_spin.value()
        worker = StorageAnalysisWorker(target_path, depth, parent=self)
        self._analysis_worker = worker
        worker.tree_done.connect(self._on_tree_done)
        worker.types_done.connect(self._on_types_done)
        worker.old_done.connect(self._on_old_done)
        worker.vms_done.connect(self._on_vms_done)
        worker.finished_all.connect(self._on_analysis_done)
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

    def _on_types_done(self, file_types):
        self._file_types_data = file_types
        self._populate_types(file_types)

    def _on_old_done(self, old_files):
        self._old_files_data = old_files
        self._populate_old_files(old_files)

    def _on_vms_done(self, vms):
        self._vm_data = vms
        self._populate_vms(vms)

    def _on_analysis_done(self):
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze Storage")

    def _on_analysis_failed(self, msg: str):
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze Storage")
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


class HelpSafetyView(QWidget):
    """Comprehensive Help, Safety Philosophy, Technical Documentation, and FAQ view."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self._theme = "dark"
        self._cards: list[tuple[str, QFrame, list[str]]] = []
        self._build_ui()

    def _build_ui(self):
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(24, 20, 24, 16)
        root_lay.setSpacing(12)

        # Header with Copy Diagnostics Action
        header_row = QHBoxLayout()
        header_row.addWidget(
            page_header(
                "Help, Safety & Technical Philosophy",
                "Understanding CrapCleaner's cleanup mechanics, protected paths, safety guarantees, and FAQs.",
            ),
            1,
        )

        diag_btn = QPushButton("Copy System Diagnostics")
        diag_btn.setProperty("secondary", "true")
        diag_btn.setIcon(material_icon("code", _c(self._theme, "text")))
        diag_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        diag_btn.clicked.connect(self._copy_diagnostics)
        header_row.addWidget(diag_btn)

        root_lay.addLayout(header_row)

        # Filter Chips & Search Bar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._chip_buttons = {}
        filters = [
            ("ALL", "All Topics"),
            ("PHILOSOPHY", "Core Philosophy"),
            ("REGISTRY", "Registry Policy"),
            ("SAFETY", "Safety && Protection"),
            ("CACHES", "Caches vs Data"),
            ("FAQ", "FAQs"),
            ("TROUBLESHOOTING", "Troubleshooting"),
        ]
        for key, label in filters:
            btn = QPushButton(label)
            btn.setProperty("chip", "true")
            btn.setProperty("active", "true" if key == "ALL" else "false")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self._set_filter(k))
            toolbar.addWidget(btn)
            self._chip_buttons[key] = btn

        toolbar.addStretch(1)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search documentation & FAQs (Ctrl+F)...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(260)
        self.search_edit.textChanged.connect(self._apply_search)
        toolbar.addWidget(self.search_edit)

        root_lay.addLayout(toolbar)

        # Scrollable Cards Container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self.cards_layout = QVBoxLayout(container)
        self.cards_layout.setContentsMargins(0, 4, 8, 4)
        self.cards_layout.setSpacing(14)

        self._build_content_cards()
        self.cards_layout.addStretch(1)

        scroll.setWidget(container)
        root_lay.addWidget(scroll, 1)

    def _make_card(
        self, title: str, category_tag: str, text_html: str, search_keywords: list[str]
    ) -> QFrame:
        card = QFrame()
        card.setProperty("card", "true")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        top = QHBoxLayout()
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-size: 15px; font-weight: 700;")
        top.addWidget(t_lbl, 1)

        tag_badge = badge(category_tag.replace("_", " ").title(), "accent")
        tag_badge.setFixedHeight(22)
        tag_badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        top.addWidget(tag_badge, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        lay.addLayout(top)

        b_lbl = QLabel(text_html)
        b_lbl.setWordWrap(True)
        b_lbl.setTextFormat(Qt.TextFormat.RichText)
        b_lbl.setStyleSheet(f"color: {_c(self._theme, 'text')}; font-size: 12px; line-height: 1.5;")
        lay.addWidget(b_lbl)

        self._cards.append(
            (category_tag, card, [title.lower()] + [k.lower() for k in search_keywords])
        )
        return card

    def _build_content_cards(self):
        # 1. Core Philosophy
        self.cards_layout.addWidget(
            self._make_card(
                "1. Core Philosophy & Design Principles",
                "PHILOSOPHY",
                "• <b>Transparency over marketing claims:</b> Every cleanup target has a technically defensible reason for existing and why removing it is safe.<br>"
                "• <b>Safety over aggressive deletion:</b> CrapCleaner strictly prefers reversible cleanup via the Windows Recycle Bin / FreeDesktop Trash.<br>"
                "• <b>Never delete user data:</b> Personal documents, desktop files, credentials, Git repos, and project workspaces are never touched.<br>"
                "• <b>Zero Telemetry & 100% Local:</b> No background network analytics, no third-party trackers, no advertisements, and no bundled installers.",
                [
                    "transparency",
                    "philosophy",
                    "safety",
                    "telemetry",
                    "principles",
                    "local",
                    "privacy",
                ],
            )
        )

        # 2. Strict Prohibition on Registry Cleaning
        self.cards_layout.addWidget(
            self._make_card(
                "2. Absolute Strict Prohibition on Registry Cleaning",
                "REGISTRY",
                "<b>Why doesn't CrapCleaner clean or optimize the Windows Registry?</b><br>"
                "• <b>Registry cleaning is snake oil:</b> Modern Windows operating systems (Windows 10 / 11) use high-performance memory-mapped B-tree hive storage. Unused keys occupy negligible disk space and have zero impact on system latency or CPU execution.<br>"
                "• <b>High Risk of System Damage:</b> Automated registry cleaners frequently delete shared COM CLSIDs, installer registration keys, and file association handlers, causing application crashes or OS boot failure.<br>"
                "• <b>Our Guarantee:</b> CrapCleaner contains <b>zero</b> registry cleaners, defragmenters, or repair tools. We focus exclusively on measurable, technically sound disk cleanup.",
                [
                    "registry",
                    "registry cleaner",
                    "snake oil",
                    "optimization",
                    "system stability",
                    "clsid",
                    "windows registry",
                ],
            )
        )

        # 3. Performance & Placebo Disclaimer
        self.cards_layout.addWidget(
            self._make_card(
                "3. Performance & Placebo Disclaimer",
                "PHILOSOPHY",
                "<b>Honest Performance Guarantees:</b><br>"
                "• CrapCleaner delivers <b>measurable disk storage recovery</b> by reclaiming gigabytes of orphaned build caches, shader depots, and temporary files.<br>"
                "• CrapCleaner does <b>NOT</b> claim to provide magical FPS boosts, CPU overclocking, or instantaneous boot-time speedups. Deleting disk junk frees storage space; it does not replace hardware performance.",
                ["fps", "gaming", "performance", "speed", "boot time", "placebo", "disclaimer"],
            )
        )

        # 4. Understanding File Types
        self.cards_layout.addWidget(
            self._make_card(
                "4. Understanding File Types & Regeneration Behavior",
                "CACHES",
                "• <b>Temporary Files (%TEMP%):</b> Scratch files generated by installers or running programs. Safe to remove; active files remain locked by OS.<br>"
                "• <b>Compiler & Package Caches:</b> Global download caches (pip, npm, cargo, go-build). Safe to clean; re-downloaded seamlessly when building.<br>"
                "• <b>DirectX / GPU Shader Caches:</b> Compiled binary graphics shaders. Removing them clears outdated shaders; games recompile shaders automatically during gameplay.<br>"
                "• <b>Diagnostic Logs:</b> Text traces generated by applications. Purely diagnostic; safe to delete.<br>"
                "• <b>User Data:</b> Documents, project sources, credentials, and settings. Strictly protected and never deleted.",
                [
                    "temp",
                    "cache",
                    "shader",
                    "logs",
                    "artifacts",
                    "regeneration",
                    "package manager",
                    "gpu",
                ],
            )
        )

        # 5. Centralized Safety Layer & Protected Paths
        self.cards_layout.addWidget(
            self._make_card(
                "5. Centralized Protected Paths Safety Layer",
                "SAFETY",
                "CrapCleaner enforces immutable safety rules across all operations:<br>"
                "• <b>OS Roots Protected:</b> <code>C:\\Windows</code>, <code>System32</code>, <code>/usr</code>, <code>/etc</code>, <code>/boot</code>.<br>"
                "• <b>User Folders Protected:</b> <code>Documents</code>, <code>Desktop</code>, <code>Pictures</code>, <code>Music</code>, <code>Videos</code>, <code>Saved Games</code>.<br>"
                "• <b>Credentials Protected:</b> SSH keys (<code>.ssh</code>), GPG keys (<code>.gnupg</code>), browser passwords (<code>Login Data</code>), cookies (<code>Cookies</code>), tokens.<br>"
                "• <b>Development Repositories:</b> Git metadata (<code>.git</code>) is strictly blocked from modification.<br>"
                "• <b>Volume Roots:</b> Drive roots (e.g. <code>C:\\</code>, <code>/</code>) can never be deleted recursively.",
                [
                    "protected paths",
                    "safety",
                    "git",
                    "ssh",
                    "passwords",
                    "cookies",
                    "windows",
                    "documents",
                ],
            )
        )

        # 6. Exclusions Manager
        self.cards_layout.addWidget(
            self._make_card(
                "6. Cleanup Exclusions Manager",
                "SAFETY",
                "You can permanently exclude specific folders from all scans and cleanups:<br>"
                "1. Navigate to <b>Settings</b> in the left sidebar.<br>"
                "2. Under <b>Cleanup Exclusions</b>, click <b>Add Excluded Folder...</b>.<br>"
                "3. Select the folder you wish to protect permanently. CrapCleaner will skip this directory and all subfolders during scanning and cleanup.",
                ["exclusions", "excluded folders", "custom protection", "settings", "exclude"],
            )
        )

        # 7. Safety Model: Recycle Bin & Dry Run
        self.cards_layout.addWidget(
            self._make_card(
                "7. Recycle Bin Safety Model & Dry-Run Simulation",
                "SAFETY",
                "• <b>Reversible by Default:</b> All deletions are routed through the Windows Recycle Bin or Linux FreeDesktop Trash so files can be restored if needed.<br>"
                "• <b>Dry-Run Mode:</b> When dry-run is enabled (default), CrapCleaner simulates the cleanup process, calculating exact recoverable bytes without deleting a single file.<br>"
                "• <b>Confirmation Prompts:</b> Destructive actions always require explicit user confirmation.",
                ["recycle bin", "trash", "dry run", "reversible", "simulation", "restore"],
            )
        )

        # 8. Complete FAQ Section
        faq_html = (
            "<b>Q: What can CrapCleaner safely remove?</b><br>"
            "A: Web caches, package manager caches (npm, pip, cargo, go), temporary files, crash dumps, old installers, and shader caches.<br><br>"
            "<b>Q: Why did my disk space increase/re-fill after cleaning?</b><br>"
            "A: Active applications (browsers, IDEs, games) re-cache assets as you use them. This is normal behavior.<br><br>"
            "<b>Q: Why are some files skipped during cleanup?</b><br>"
            "A: Files currently locked by running processes or matching safety protection rules are safely skipped.<br><br>"
            "<b>Q: Why does a cleanup require Administrator permissions?</b><br>"
            "A: System-wide folders (e.g. Windows Delivery Optimization, CBS logs, system temp) require elevated privileges to clean.<br><br>"
            "<b>Q: Can CrapCleaner delete personal documents or project files?</b><br>"
            "A: No. User profile document folders, source code, and .git repos are hard-coded as immutable protected paths.<br><br>"
            "<b>Q: Does CrapCleaner clean the Windows Registry?</b><br>"
            "A: No. Registry cleaners are snake oil and carry high risks of system instability. We intentionally do not include one.<br><br>"
            "<b>Q: Can shader caches and browser caches be safely removed?</b><br>"
            "A: Yes. Graphics drivers and browsers recompile shaders and re-download web assets seamlessly on next launch.<br><br>"
            "<b>Q: What happens when I clean a Docker or AI model cache?</b><br>"
            "A: Docker prunes unused containers/build cache. AI Model Explorer is strictly read-only and never deletes model weights automatically."
        )
        self.cards_layout.addWidget(
            self._make_card(
                "8. Frequently Asked Questions (FAQ)",
                "FAQ",
                faq_html,
                [
                    "faq",
                    "questions",
                    "answers",
                    "troubleshooting",
                    "locked files",
                    "admin",
                    "documents",
                ],
            )
        )

        # 9. Troubleshooting & Common Issues
        self.cards_layout.addWidget(
            self._make_card(
                "9. Troubleshooting & Permissions Guide",
                "TROUBLESHOOTING",
                "• <b>Locked Files:</b> If a browser or IDE is open, close the program and re-run cleanup to remove its in-use cache.<br>"
                "• <b>Permission Denied:</b> Run CrapCleaner as Administrator to clean system-level caches.<br>"
                "• <b>Slow Scans:</b> If scanning across network shares or massive drives, adjust 'Max Files Scanned' in Settings.<br>"
                "• <b>Antivirus Interference:</b> Add CrapCleaner to your security exclusions if file deletion prompts are intercepted.",
                [
                    "troubleshooting",
                    "permissions",
                    "locked",
                    "slow",
                    "admin",
                    "access denied",
                    "errors",
                ],
            )
        )

    def _set_filter(self, filter_key: str):
        self._filter = filter_key
        for key, btn in self._chip_buttons.items():
            btn.setProperty("active", "true" if key == filter_key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._apply_search()

    def _apply_search(self):
        query = self.search_edit.text().strip().lower()
        for cat_tag, card, keywords in self._cards:
            match_filter = (self._filter == "ALL") or (cat_tag == self._filter)
            match_search = (not query) or any(query in kw for kw in keywords)
            card.setVisible(match_filter and match_search)

    def _copy_diagnostics(self):
        import platform

        from crapcleaner import __version__
        from crapcleaner.config import load_settings

        settings = load_settings()
        excl_count = len(settings.get("excluded_paths", []))
        cats = get_all_categories()
        drives = list_drives()

        diag_text = (
            f"=== CrapCleaner System Diagnostics ===\n"
            f"Version:       v{__version__}\n"
            f"OS:            {platform.system()} {platform.release()} ({platform.machine()})\n"
            f"Python:        {platform.python_version()}\n"
            f"Admin Rights:  {'Yes' if is_admin() else 'No'}\n"
            f"Drives:        {', '.join(drives)}\n"
            f"Categories:    {len(cats)} loaded\n"
            f"Exclusions:    {excl_count} active rules\n"
            f"====================================="
        )
        clipboard = QApplication.clipboard()
        clipboard.setText(diag_text)
        QMessageBox.information(
            self,
            "Diagnostics Copied",
            "System diagnostics copied to clipboard.",
        )

    def apply_theme(self, theme: str):
        self._theme = theme


class MemoryView(QWidget):
    """RAM, swap, and graphics memory reporting with safe reclamation actions."""

    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._theme = "dark"
        self._report = None
        self._busy = False
        self._action_rows = {}
        self._action_cards = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)
        root.addWidget(
            page_header(
                "Memory Cleaner",
                "Inspect physical memory, swap, and graphics VRAM, then safely optimize and reclaim memory across active processes.",
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(14)

        # 1. Top Hero Card: Status, Usage Gauge & Quick Flush Action
        self.hero_card = QFrame()
        self.hero_card.setProperty("card", "true")
        hero_lay = QVBoxLayout(self.hero_card)
        hero_lay.setContentsMargins(18, 16, 18, 16)
        hero_lay.setSpacing(10)

        hero_top = QHBoxLayout()
        self.hero_badge = badge("NORMAL PRESSURE", "safe")
        self.elevated_badge = badge(
            "ELEVATED (ADMIN)" if is_admin() else "STANDARD USER",
            "accent" if is_admin() else "muted",
        )
        hero_top.addWidget(self.hero_badge)
        hero_top.addWidget(self.elevated_badge)
        hero_top.addStretch(1)

        if not is_admin() and is_windows():
            self.elevate_btn = QPushButton("Relaunch as Admin (Full Standby Flush)")
            self.elevate_btn.setProperty("secondary", "true")
            self.elevate_btn.setIcon(material_icon("security", _c(self._theme, "accent")))
            self.elevate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.elevate_btn.clicked.connect(self._relaunch_admin)
            hero_top.addWidget(self.elevate_btn)

        self.flush_btn = QPushButton("Quick Flush Memory")
        self.flush_btn.setProperty("primary", "true")
        self.flush_btn.setIcon(material_icon("bolt", "#ffffff"))
        self.flush_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.flush_btn.clicked.connect(lambda: self._run_action("flush_all"))

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(material_icon("refresh", _c(self._theme, "text")))
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh)

        hero_top.addWidget(self.flush_btn)
        hero_top.addWidget(self.refresh_btn)
        hero_lay.addLayout(hero_top)

        self.hero_title = QLabel("-- / -- Used")
        self.hero_title.setStyleSheet(
            f"font-size: 24px; font-weight: 800; color: {_c(self._theme, 'text')};"
        )
        hero_lay.addWidget(self.hero_title)

        self.ram_bar = QProgressBar()
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setValue(0)
        self.ram_bar.setFixedHeight(8)
        self.ram_bar.setTextVisible(False)
        self.ram_bar.setProperty("good", "true")
        hero_lay.addWidget(self.ram_bar)

        hero_sub_row = QHBoxLayout()
        self.status_label = QLabel("Reading memory statistics...")
        self.status_label.setProperty("subtle", "true")
        self.status_label.setStyleSheet(f"font-size: 11px; color: {_c(self._theme, 'muted')};")
        self.pressure_label = QLabel("Memory pressure: normal")
        self.pressure_label.setProperty("subtle", "true")
        self.pressure_label.setStyleSheet(f"font-size: 11px; color: {_c(self._theme, 'muted')};")
        hero_sub_row.addWidget(self.status_label)
        hero_sub_row.addStretch(1)
        hero_sub_row.addWidget(self.pressure_label)
        hero_lay.addLayout(hero_sub_row)

        # Embedded result banner
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

        # 2. Hardware & Memory Breakdown Cards (RAM 4-metric grid, Swap Card, GPU VRAM Card)
        layout.addWidget(section_label("Memory Allocation & Hardware VRAM"))
        vitals_grid = QHBoxLayout()
        vitals_grid.setSpacing(12)

        # RAM Breakdown Card
        self.ram_group = QFrame()
        self.ram_group.setProperty("card", "true")
        rc_lay = QVBoxLayout(self.ram_group)
        rc_lay.setContentsMargins(14, 12, 14, 12)
        rc_lay.setSpacing(8)
        rc_head = QLabel("Physical RAM (4-Metric)")
        rc_head.setProperty("strong", "true")
        rc_lay.addWidget(rc_head)

        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(8)
        self.ram_total_card, self.ram_total_value, _ = stat_card("Total", "--", "", self._theme)
        self.ram_used_card, self.ram_used_value, _ = stat_card("In Use", "--", "", self._theme)
        self.ram_free_card, self.ram_free_value, _ = stat_card("Available", "--", "", self._theme)
        self.ram_cached_card, self.ram_cached_value, _ = stat_card(
            "Cached / Standby", "--", "", self._theme
        )
        metrics_grid.addWidget(self.ram_total_card, 0, 0)
        metrics_grid.addWidget(self.ram_used_card, 0, 1)
        metrics_grid.addWidget(self.ram_free_card, 1, 0)
        metrics_grid.addWidget(self.ram_cached_card, 1, 1)
        rc_lay.addLayout(metrics_grid)
        vitals_grid.addWidget(self.ram_group, 5)

        # Side Column for Swap & GPU VRAM
        side_col = QVBoxLayout()
        side_col.setSpacing(10)

        # Swap Card
        self.swap_group = QFrame()
        self.swap_group.setProperty("card", "true")
        sc_lay = QVBoxLayout(self.swap_group)
        sc_lay.setContentsMargins(14, 12, 14, 12)
        sc_lay.setSpacing(6)
        sc_top = QHBoxLayout()
        sc_title = QLabel("Swap / Pagefile")
        sc_title.setProperty("subtle", "true")
        sc_top.addWidget(sc_title)
        sc_top.addStretch(1)
        self.swap_badge = badge("--", "accent")
        sc_top.addWidget(self.swap_badge)
        sc_lay.addLayout(sc_top)

        self.swap_bar = QProgressBar()
        self.swap_bar.setRange(0, 100)
        self.swap_bar.setValue(0)
        self.swap_bar.setFixedHeight(5)
        self.swap_bar.setTextVisible(False)
        sc_lay.addWidget(self.swap_bar)

        self.swap_label = QLabel("--")
        self.swap_label.setProperty("subtle", "true")
        self.swap_label.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'muted')};")
        sc_lay.addWidget(self.swap_label)
        side_col.addWidget(self.swap_group)

        # GPU VRAM Card
        self.gpu_group = QFrame()
        self.gpu_group.setProperty("card", "true")
        self.gpu_layout = QVBoxLayout(self.gpu_group)
        self.gpu_layout.setContentsMargins(14, 12, 14, 12)
        self.gpu_layout.setSpacing(6)

        gpu_placeholder = QLabel("Reading graphics adapters...")
        gpu_placeholder.setProperty("subtle", "true")
        gpu_placeholder.setWordWrap(True)
        self.gpu_layout.addWidget(gpu_placeholder)
        side_col.addWidget(self.gpu_group)

        vitals_grid.addLayout(side_col, 4)
        layout.addLayout(vitals_grid)

        # 3. Reclamation Actions Section
        layout.addWidget(section_label("Reclamation & Optimization Actions"))
        actions_grid = QGridLayout()
        actions_grid.setSpacing(10)

        row_idx = 0
        for action in available_memory_actions():
            card = self._create_action_card(action)
            r, c = divmod(row_idx, 2)
            actions_grid.addWidget(card, r, c)
            row_idx += 1

        layout.addLayout(actions_grid)
        layout.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

    def _create_action_card(self, action) -> QFrame:
        card = QFrame()
        card.setProperty("card", "true")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        top = QHBoxLayout()
        title = QLabel(action.name)
        title.setProperty("strong", "true")
        top.addWidget(title)
        top.addStretch(1)

        if action.requires_admin:
            top.addWidget(badge("ADMIN", "warn" if not is_admin() else "safe"))
        elif action.id in ("flush_all", "process_working_sets"):
            top.addWidget(badge("RECOMMENDED", "accent"))
        elif action.kind == "vram":
            top.addWidget(badge("DIAGNOSTIC", "muted"))
        lay.addLayout(top)

        desc = QLabel(action.description)
        desc.setWordWrap(True)
        desc.setProperty("subtle", "true")
        desc.setStyleSheet(f"font-size: 11px; color: {_c(self._theme, 'muted')};")
        lay.addWidget(desc)

        effect = QLabel(action.effect)
        effect.setWordWrap(True)
        effect.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'faint')};")
        lay.addWidget(effect)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn = QPushButton("Inspect" if action.kind == "vram" else "Run Action")
        if action.id in ("flush_all", "process_working_sets"):
            btn.setProperty("primary", "true")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _=False, a=action.id: self._run_action(a))
        if not action.supported:
            btn.setEnabled(False)
            btn.setToolTip(action.unsupported_reason)
        btn_row.addWidget(btn)
        lay.addLayout(btn_row)

        self._action_rows[action.id] = effect
        self._action_cards[action.id] = (card, desc, effect, btn)
        return card

    def refresh(self):
        if self._busy:
            return
        self._busy = True
        self.refresh_btn.setEnabled(False)
        if hasattr(self, "flush_btn"):
            self.flush_btn.setEnabled(False)
        self.status_label.setText("Reading memory statistics...")
        from crapcleaner.gui.workers import MemoryReportWorker, stop_worker

        stop_worker(getattr(self, "_report_worker", None))

        worker = MemoryReportWorker(parent=self)
        self._report_worker = worker
        worker.done.connect(self._on_report)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(
            lambda: (
                setattr(self, "_report_worker", None)
                if getattr(self, "_report_worker", None) is worker
                else None
            )
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_failed(self, message: str):
        self._busy = False
        self.refresh_btn.setEnabled(True)
        if hasattr(self, "flush_btn"):
            self.flush_btn.setEnabled(True)
        self.status_label.setText(f"Could not read memory statistics: {message}")

    def _on_report(self, report):
        self._busy = False
        self.refresh_btn.setEnabled(True)
        if hasattr(self, "flush_btn"):
            self.flush_btn.setEnabled(True)
        self._report = report
        ram = report.ram

        pct = int(ram.percent_used)
        self.hero_title.setText(
            f"{format_size(ram.used_bytes)} / {format_size(ram.total_bytes)} ({pct}% in use)"
        )
        self.ram_bar.setValue(pct)
        self.ram_bar.setProperty("good", ram.percent_used < 70)
        self.ram_bar.setProperty("warn", 70 <= ram.percent_used <= 90)
        self.ram_bar.setProperty("bad", ram.percent_used > 90)
        self.ram_bar.style().unpolish(self.ram_bar)
        self.ram_bar.style().polish(self.ram_bar)

        self.hero_badge.setText(f"{ram.pressure.upper()} PRESSURE")
        self.hero_badge.setProperty(
            "level",
            (
                "safe"
                if ram.pressure in ("low", "normal")
                else ("warn" if ram.pressure == "high" else "danger")
            ),
        )
        self.hero_badge.style().unpolish(self.hero_badge)
        self.hero_badge.style().polish(self.hero_badge)

        self.status_label.setText(
            f"{format_size(ram.available_bytes)} available of {format_size(ram.total_bytes)}"
        )
        self.pressure_label.setText(
            f"Memory pressure: {ram.pressure}"
            + (
                ""
                if ram.cached_known
                else "  -  cached/standby memory is not reported on this platform"
            )
        )

        self.ram_total_value.setText(format_size(ram.total_bytes))
        self.ram_used_value.setText(format_size(ram.used_bytes))
        self.ram_free_value.setText(format_size(ram.available_bytes))
        self.ram_cached_value.setText(
            format_size(ram.cached_bytes) if ram.cached_known else "unknown"
        )

        if ram.swap_supported:
            swap_pct = (
                int(round(ram.swap_used_bytes / ram.swap_total_bytes * 100))
                if ram.swap_total_bytes > 0
                else 0
            )
            self.swap_bar.setValue(swap_pct)
            self.swap_badge.setText(f"{swap_pct}% Used")
            self.swap_label.setText(
                f"{format_size(ram.swap_used_bytes)} used of {format_size(ram.swap_total_bytes)}"
            )
        else:
            self.swap_bar.setValue(0)
            self.swap_badge.setText("Disabled")
            self.swap_label.setText("No swap or pagefile is configured on this system.")

        self._populate_gpus(report)

    def _populate_gpus(self, report):
        while self.gpu_layout.count():
            item = self.gpu_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

        if not report.gpus:
            empty = QLabel("No graphics adapter with readable memory counters was detected.")
            empty.setProperty("subtle", "true")
            empty.setWordWrap(True)
            self.gpu_layout.addWidget(empty)
            return

        for gpu in report.gpus:
            holder = QWidget()
            box = QVBoxLayout(holder)
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(4)
            vendor = f" ({gpu.vendor})" if gpu.vendor else ""
            title = QLabel(f"<b>{gpu.name}</b>{vendor}")
            title.setWordWrap(True)
            box.addWidget(title)

            if gpu.live_usage_available:
                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(int(gpu.percent_used))
                bar.setFixedHeight(5)
                bar.setTextVisible(False)
                box.addWidget(bar)
                detail = QLabel(
                    f"{format_size(gpu.used_bytes)} used of {format_size(gpu.total_bytes)}, "
                    f"{format_size(gpu.free_bytes)} free (source: {gpu.source})"
                )
            elif gpu.total_bytes:
                detail = QLabel(
                    f"{format_size(gpu.total_bytes)} of VRAM installed. This driver exposes no "
                    "live usage counter, so used and free memory are unknown rather than zero."
                )
            else:
                detail = QLabel("This adapter does not report its memory capacity.")
            detail.setProperty("subtle", "true")
            detail.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'muted')};")
            detail.setWordWrap(True)
            box.addWidget(detail)
            self.gpu_layout.addWidget(holder)

        if report.vram_consumers:
            consumers = QLabel(
                "Processes holding VRAM: "
                + ", ".join(
                    f"{c.name} (PID {c.pid}, {format_size(c.used_bytes)})"
                    for c in report.vram_consumers[:8]
                )
            )
            consumers.setWordWrap(True)
            consumers.setProperty("subtle", "true")
            consumers.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'muted')};")
            self.gpu_layout.addWidget(consumers)

    def _run_action(self, action_id: str):
        if self._busy:
            return
        action = get_memory_action(action_id)
        if action is None:
            return
        if action.requires_admin and not is_admin():
            QMessageBox.information(
                self,
                action.name,
                f"{action.name} needs administrator privileges.\n\n"
                "Restart CrapCleaner elevated to use this action.",
            )
            return
        if action.kind != "vram" and action.requires_admin:
            confirm = QMessageBox.question(
                self,
                action.name,
                f"{action.description}\n\nWhat runs:\n{action.effect}\n\nContinue?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        self._busy = True
        self.refresh_btn.setEnabled(False)
        if hasattr(self, "flush_btn"):
            self.flush_btn.setEnabled(False)
        self.result_label.setText(f"Running: {action.name}...")
        self.result_banner.setVisible(True)
        from crapcleaner.gui.workers import MemoryActionWorker, stop_worker

        stop_worker(getattr(self, "_action_worker", None))

        worker = MemoryActionWorker(action_id, parent=self)
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

    def closeEvent(self, event):
        from crapcleaner.gui.workers import stop_worker

        stop_worker(getattr(self, "_report_worker", None))
        stop_worker(getattr(self, "_action_worker", None))
        super().closeEvent(event)

    def _relaunch_admin(self):
        if elevate():
            QApplication.quit()

    def _on_action_done(self, result):
        self._busy = False
        self.refresh_btn.setEnabled(True)
        if hasattr(self, "flush_btn"):
            self.flush_btn.setEnabled(True)
        if not result.success:
            self.result_label.setText(f"Not performed: {result.message}")
            self.result_icon.setPixmap(
                material_icon("warning", _c(self._theme, "warning")).pixmap(18, 18)
            )
            self.result_banner.setVisible(True)
            return
        if not result.measurable:
            self.result_label.setText(result.message)
            self.result_icon.setPixmap(
                material_icon("info", _c(self._theme, "accent")).pixmap(18, 18)
            )
            self.result_banner.setVisible(True)
            return
        before = format_size(result.before.available_bytes)
        after = format_size(result.after.available_bytes)
        reclaimed = format_size(result.reclaimed_bytes)
        extra_tip = ""
        if (
            not is_admin()
            and is_windows()
            and self._report
            and getattr(self._report.ram, "cached_bytes", 0) > 500 * 1024**2
        ):
            cached_str = format_size(self._report.ram.cached_bytes)
            extra_tip = (
                f" (Tip: Relaunch as Administrator to also purge {cached_str} of Standby Cache)."
            )
        self.result_label.setText(
            f"{result.message} Available memory increased from {before} to {after} (+{reclaimed} reclaimed).{extra_tip}"
        )
        self.result_icon.setPixmap(material_icon("check", _c(self._theme, "safe")).pixmap(18, 18))
        self.result_banner.setVisible(True)
        self.refresh()

    def apply_theme(self, theme: str):
        self._theme = theme
        self.hero_title.setStyleSheet(
            f"font-size: 24px; font-weight: 800; color: {_c(theme, 'text')};"
        )
        self.status_label.setStyleSheet(f"font-size: 11px; color: {_c(theme, 'muted')};")
        self.pressure_label.setStyleSheet(f"font-size: 11px; color: {_c(theme, 'muted')};")
        self.result_label.setStyleSheet(f"font-weight: 600; color: {_c(theme, 'text')};")
        for _, desc, effect, _ in self._action_cards.values():
            desc.setStyleSheet(f"font-size: 11px; color: {_c(theme, 'muted')};")
            effect.setStyleSheet(f"font-size: 10px; color: {_c(theme, 'faint')};")
        for effect in self._action_rows.values():
            effect.setStyleSheet(f"font-size: 11px; color: {_c(theme, 'faint')};")
