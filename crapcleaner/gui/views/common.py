"""Shared widgets, helpers, and small components used across the views."""

import os

from PySide6.QtCore import (
    QRectF,
    Qt,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.theme import color as theme_color
from crapcleaner.models.category import SafetyLevel
from crapcleaner.utils.files import file_manager_name, reveal_in_file_manager
from crapcleaner.utils.format import (
    format_size,
)
from crapcleaner.utils.platform import (
    is_windows,
    linux_drive_display_kind,
    linux_drive_display_name,
)


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
        # No super().__lt__() here: PySide re-dispatches it back into this
        # override, which recurses until RecursionError.
        return self.text(column).lower() < other.text(column).lower()


def page_header(title: str, subtitle: str = "") -> QWidget:
    """Consistent page header used across all main views."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    title_label = QLabel(title)
    title_label.setTextFormat(Qt.TextFormat.PlainText)
    title_label.setProperty("pageTitle", "true")
    layout.addWidget(title_label)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setTextFormat(Qt.TextFormat.PlainText)
        sub.setProperty("pageSubtitle", "true")
        sub.setWordWrap(True)
        layout.addWidget(sub)
    return widget


def badge(text: str, level: str = "") -> QLabel:
    """Small pill label used for status and safety markers."""
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setProperty("badge", "true")
    if level:
        label.setProperty("level", level)
    return label


def section_label(text: str) -> QLabel:
    """Uppercase section heading used inside cards."""
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
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
    t_lbl.setTextFormat(Qt.TextFormat.PlainText)
    t_lbl.setProperty("section", "true")

    v_lbl = QLabel(value)
    v_lbl.setTextFormat(Qt.TextFormat.PlainText)
    v_lbl.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {_c(theme, 'text')};")

    s_lbl = QLabel(subtitle)
    s_lbl.setTextFormat(Qt.TextFormat.PlainText)
    s_lbl.setProperty("subtle", "true")
    s_lbl.setStyleSheet(f"font-size: 11px; color: {_c(theme, 'muted')};")

    lay.addWidget(t_lbl)
    lay.addWidget(v_lbl)
    lay.addWidget(s_lbl)
    return card, v_lbl, s_lbl


def restyle_stat_card(value_label: QLabel, sub_label: QLabel, theme: str) -> None:
    """Re-apply stat card colours after a theme change.

    `stat_card` bakes the theme into an inline stylesheet, which outranks the global
    sheet. Without this, switching from a dark theme to a light one leaves the value
    near-white on a near-white card.
    """
    value_label.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {_c(theme, 'text')};")
    sub_label.setStyleSheet(f"font-size: 11px; color: {_c(theme, 'muted')};")


class ClickableCard(QFrame):
    """A card frame that emits `clicked` instead of needing its handler patched in."""

    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit()
        super().mousePressEvent(event)


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
    """Table item that sorts by a numeric value stored in a dedicated sort role."""

    _SORT_ROLE = Qt.ItemDataRole.UserRole + 99

    def __init__(self, text: str = "", value=None):
        super().__init__(text)
        if value is not None:
            self.setData(self._SORT_ROLE, value)

    def set_sort_value(self, value):
        self.setData(self._SORT_ROLE, value)

    def __lt__(self, other):
        if not isinstance(other, QTableWidgetItem):
            return False

        a = self.data(self._SORT_ROLE)
        if a is None:
            a = self.data(Qt.ItemDataRole.UserRole)

        b = other.data(self._SORT_ROLE)
        if b is None:
            b = other.data(Qt.ItemDataRole.UserRole)

        if a is not None and b is not None:
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if a != b:
                    return a < b
            elif type(a) is type(b):
                try:
                    if a != b:
                        return a < b
                except TypeError:
                    pass

        self_txt = self.text() or ""
        other_txt = other.text() or ""
        return self_txt.casefold() < other_txt.casefold()


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
        self.setAccessibleName("Drive usage chart")
        self.setAccessibleDescription("Drive usage: not measured yet")

    def set_usage(self, fraction: float, theme: str):
        self._fraction = max(0.0, min(1.0, fraction))
        self._theme = theme
        # The figure is drawn, so it also has to be stated for anyone not seeing it.
        self.setAccessibleDescription(f"Drive usage: {self._fraction * 100:.0f} percent used")
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
        fill_color = pal["accent"]

        if self._fraction > 0.001:
            painter.setPen(
                QPen(
                    QColor(fill_color),
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
        self.setAccessibleName(f"Drive {drive}")
        self.setAccessibleDescription(f"Select drive {drive} to analyse")
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
        open_action = menu.addAction(f"Open in {file_manager_name()}")
        action = menu.exec(self.mapToGlobal(pos))
        if action == open_action:
            # A drive is named "C:" on Windows and needs the trailing separator to be a
            # path; on Linux it is already a mount point.
            target = f"{self.drive}\\" if is_windows() else self.drive
            reveal_in_file_manager(target, select=False)

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


class ContributorCard(QFrame):
    """Polished, responsive card representing a community GitHub contributor."""

    def __init__(
        self, contributor, avatar_file: str | None = None, theme: str = "dark", parent=None
    ):
        super().__init__(parent)
        self._theme = theme
        self.setProperty("card", "true")
        self.setAccessibleName(f"Contributor {getattr(contributor, 'login', '')}")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(64)
        self.setMinimumWidth(240)
        self.setMaximumWidth(420)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        # Squircle Avatar
        initials = contributor.login[:2].upper() if contributor.login else "??"
        avatar = SquircleAvatarWidget(
            image_path=avatar_file or "",
            size=40,
            radius=12,
            initials=initials,
            parent=self,
        )
        lay.addWidget(avatar)

        # Info Box (Username & Contribution Badge)
        info_lay = QVBoxLayout()
        info_lay.setSpacing(3)
        info_lay.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        name_lbl = QLabel(f"@{contributor.login}")
        name_lbl.setStyleSheet("font-size: 13px; font-weight: 700;")
        info_lay.addWidget(name_lbl)

        cnt_str = f"{contributor.contributions} {'contribution' if contributor.contributions == 1 else 'contributions'}"
        sub_badge = badge(cnt_str, "accent")
        sub_badge.setFixedHeight(18)
        sub_badge.setStyleSheet("font-size: 10px; font-weight: 600; padding: 0 6px;")
        info_lay.addWidget(sub_badge)

        lay.addLayout(info_lay)
        lay.addStretch(1)

        # Compact profile button
        profile_btn = QPushButton("Profile ↗")
        profile_btn.setProperty("secondary", "true")
        profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        profile_btn.setFixedHeight(28)
        profile_btn.setStyleSheet("font-size: 11px; padding: 2px 12px;")
        profile_btn.clicked.connect(
            lambda _=False, url=contributor.html_url: QDesktopServices.openUrl(QUrl(url))
        )
        lay.addWidget(profile_btn)
