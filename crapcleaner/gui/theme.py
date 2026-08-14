"""Light and dark Fluent 2 / Linear style themes for the CrapCleaner GUI."""

from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication

DARK = {
    "window": "#0f1014",
    "panel": "#17181f",
    "surface": "#20222b",
    "surface2": "#2a2c38",
    "elevated": "#323544",
    "border": "#282a36",
    "border2": "#3b3e4f",
    "text": "#ffffff",
    "muted": "#cbd5e1",
    "faint": "#94a3b8",
    "accent": "#3b82f6",
    "accent_hover": "#60a5fa",
    "accent_pressed": "#2563eb",
    "accent_soft": "rgba(59, 130, 246, 0.18)",
    "success": "#10b981",
    "success_soft": "rgba(16, 185, 129, 0.18)",
    "warning": "#f59e0b",
    "warning_soft": "rgba(245, 158, 11, 0.18)",
    "danger": "#ef4444",
    "danger_soft": "rgba(239, 68, 68, 0.18)",
    "review": "#f97316",
    "review_soft": "rgba(249, 115, 22, 0.18)",
    "info": "#06b6d4",
    "info_soft": "rgba(6, 182, 212, 0.18)",
    "selection": "#3b82f6",
    "safe": "#10b981",
}

LIGHT = {
    "window": "#f8fafc",
    "panel": "#ffffff",
    "surface": "#f1f5f9",
    "surface2": "#e2e8f0",
    "elevated": "#ffffff",
    "border": "#e2e8f0",
    "border2": "#cbd5e1",
    "text": "#0f172a",
    "muted": "#475569",
    "faint": "#64748b",
    "accent": "#2563eb",
    "accent_hover": "#3b82f6",
    "accent_pressed": "#1d4ed8",
    "accent_soft": "rgba(37, 99, 235, 0.12)",
    "success": "#059669",
    "success_soft": "rgba(5, 150, 105, 0.12)",
    "warning": "#d97706",
    "warning_soft": "rgba(217, 119, 6, 0.12)",
    "danger": "#dc2626",
    "danger_soft": "rgba(220, 38, 38, 0.12)",
    "review": "#ea580c",
    "review_soft": "rgba(234, 88, 12, 0.12)",
    "info": "#0891b2",
    "info_soft": "rgba(8, 145, 178, 0.12)",
    "selection": "#2563eb",
    "safe": "#059669",
}


def _build_stylesheet(p: dict) -> str:
    return f"""
    /* ---------- Base Window & Typography ---------- */
    QMainWindow, QDialog, QWidget#CentralWidget, QWidget#WindowRoot {{
        background-color: {p["window"]};
    }}
    QWidget {{
        color: {p["text"]};
        font-family: 'Segoe UI Variable Display', 'Segoe UI', -apple-system, sans-serif;
        font-size: 13px;
    }}
    QStackedWidget {{ background: transparent; }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}

    QLabel {{
        background: transparent;
    }}

    /* ---------- Headings & Labels ---------- */
    QLabel[pageTitle="true"] {{
        font-size: 22px;
        font-weight: 700;
        letter-spacing: -0.3px;
        color: {p["text"]};
    }}
    QLabel[pageSubtitle="true"] {{
        font-size: 13px;
        color: {p["muted"]};
        line-height: 1.4;
    }}
    QLabel[section="true"] {{
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        color: {p["faint"]};
    }}
    QLabel[subtle="true"] {{
        color: {p["muted"]};
    }}
    QLabel[strong="true"] {{
        font-weight: 600;
        color: {p["text"]};
    }}
    QLabel[heroValue="true"] {{
        font-size: 32px;
        font-weight: 800;
        letter-spacing: -0.5px;
        color: {p["text"]};
    }}

    /* ---------- Cards & Containers ---------- */
    QFrame[card="true"] {{
        background-color: {p["panel"]};
        border: 1px solid {p["border"]};
        border-radius: 10px;
    }}
    QFrame[cardHover="true"]:hover {{
        border-color: {p["border2"]};
        background-color: {p["surface"]};
    }}
    QFrame[statCard="true"] {{
        background-color: {p["panel"]};
        border: 1px solid {p["border"]};
        border-radius: 10px;
    }}
    QFrame[statCard="true"]:hover {{
        border-color: {p["border2"]};
    }}

    /* ---------- Badges & Chips ---------- */
    QLabel[badge="true"] {{
        background-color: {p["surface"]};
        color: {p["muted"]};
        border-radius: 9px;
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 600;
    }}
    QLabel[badge="true"][level="accent"] {{ background-color: {p["accent_soft"]}; color: {p["accent"]}; }}
    QLabel[badge="true"][level="safe"]   {{ background-color: {p["success_soft"]}; color: {p["success"]}; }}
    QLabel[badge="true"][level="warn"]   {{ background-color: {p["warning_soft"]}; color: {p["warning"]}; }}
    QLabel[badge="true"][level="danger"] {{ background-color: {p["danger_soft"]}; color: {p["danger"]}; }}
    QLabel[badge="true"][level="review"] {{ background-color: {p["review_soft"]}; color: {p["review"]}; }}
    QLabel[badge="true"][level="info"]   {{ background-color: {p["info_soft"]}; color: {p["info"]}; }}

    /* ---------- Buttons ---------- */
    QPushButton {{
        background-color: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 7px 16px;
        color: {p["text"]};
        font-weight: 500;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background-color: {p["surface2"]};
        border-color: {p["border2"]};
    }}
    QPushButton:pressed {{
        background-color: {p["elevated"]};
    }}
    QPushButton:focus {{
        border-color: {p["accent"]};
    }}
    QPushButton:disabled {{
        color: {p["faint"]};
        background-color: {p["surface"]};
        border-color: {p["border"]};
    }}

    /* Primary Button */
    QPushButton[primary="true"] {{
        background-color: {p["accent"]};
        border: 1px solid {p["accent"]};
        color: #ffffff;
        font-weight: 600;
    }}
    QPushButton[primary="true"]:hover {{
        background-color: {p["accent_hover"]};
        border-color: {p["accent_hover"]};
    }}
    QPushButton[primary="true"]:pressed {{
        background-color: {p["accent_pressed"]};
        border-color: {p["accent_pressed"]};
    }}
    QPushButton[primary="true"]:disabled {{
        background-color: {p["surface2"]};
        border-color: {p["border"]};
        color: {p["faint"]};
    }}

    /* Danger Button */
    QPushButton[danger="true"] {{
        background-color: {p["danger"]};
        border: 1px solid {p["danger"]};
        color: #ffffff;
        font-weight: 600;
    }}
    QPushButton[danger="true"]:hover {{
        background-color: #f87171;
        border-color: #f87171;
    }}
    QPushButton[danger="true"]:pressed {{
        background-color: #dc2626;
        border-color: #dc2626;
    }}
    QPushButton[danger="true"]:disabled {{
        background-color: {p["surface2"]};
        border-color: {p["border"]};
        color: {p["faint"]};
    }}

    /* Ghost Button */
    QPushButton[ghost="true"] {{
        background: transparent;
        border: none;
        color: {p["accent"]};
        padding: 4px 8px;
        font-weight: 500;
    }}
    QPushButton[ghost="true"]:hover {{
        background-color: {p["accent_soft"]};
        border-radius: 4px;
    }}

    /* Filter Chip Buttons */
    QPushButton[chip="true"] {{
        background-color: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 14px;
        padding: 4px 12px;
        color: {p["muted"]};
        font-size: 12px;
        font-weight: 500;
    }}
    QPushButton[chip="true"]:hover {{
        background-color: {p["surface2"]};
        color: {p["text"]};
        border-color: {p["border2"]};
    }}
    QPushButton[chip="true"][active="true"] {{
        background-color: {p["accent_soft"]};
        border-color: {p["accent"]};
        color: {p["accent"]};
        font-weight: 600;
    }}

    /* ---------- Sidebar Navigation ---------- */
    QFrame#SideBar {{
        background-color: {p["panel"]};
        border-right: 1px solid {p["border"]};
    }}
    QLabel#BrandTitle {{
        font-size: 16px;
        font-weight: 700;
        letter-spacing: -0.2px;
        color: {p["text"]};
    }}
    QLabel#BrandSub {{
        font-size: 11px;
        color: {p["faint"]};
    }}
    QLabel[navSection="true"] {{
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.2px;
        color: {p["faint"]};
        padding-left: 10px;
        padding-top: 10px;
        padding-bottom: 2px;
        text-transform: uppercase;
    }}
    QPushButton[nav="true"] {{
        background: transparent;
        border: none;
        border-left: 3px solid transparent;
        border-radius: 6px;
        padding-left: 10px;
        padding-right: 10px;
        color: {p["muted"]};
        font-size: 13px;
        font-weight: 500;
        text-align: left;
    }}
    QPushButton[nav="true"]:hover {{
        background-color: {p["surface"]};
        color: {p["text"]};
    }}
    QPushButton[nav="true"][active="true"] {{
        background-color: {p["accent_soft"]};
        color: {p["accent"]};
        border-left: 3px solid {p["accent"]};
        font-weight: 600;
    }}

    /* ---------- Inputs & Controls ---------- */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 6px 10px;
        color: {p["text"]};
        selection-background-color: {p["selection"]};
    }}
    QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
        border-color: {p["border2"]};
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border-color: {p["accent"]};
        background-color: {p["surface"]};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {p["elevated"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        selection-background-color: {p["accent_soft"]};
        selection-color: {p["accent"]};
        padding: 4px;
        outline: none;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        background-color: {p["surface"]};
        border: none;
        width: 18px;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background-color: {p["surface2"]};
    }}

    /* ---------- Checkboxes ---------- */
    QCheckBox {{
        spacing: 8px;
        color: {p["text"]};
        background: transparent;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {p["border2"]};
        border-radius: 4px;
        background: {p["surface"]};
    }}
    QCheckBox::indicator:hover {{
        border-color: {p["accent"]};
    }}
    QCheckBox::indicator:checked {{
        background-color: {p["accent"]};
        border-color: {p["accent"]};
    }}
    QCheckBox::indicator:disabled {{
        background: {p["border"]};
        border-color: {p["border"]};
    }}

    /* ---------- Progress Bars ---------- */
    QProgressBar {{
        border: none;
        border-radius: 5px;
        background: {p["surface"]};
        text-align: center;
        height: 18px;
        color: {p["muted"]};
        font-weight: 600;
        font-size: 11px;
    }}
    QProgressBar::chunk {{
        border-radius: 5px;
        background-color: {p["accent"]};
    }}
    QProgressBar[good="true"]::chunk {{ background-color: {p["success"]}; }}
    QProgressBar[warn="true"]::chunk {{ background-color: {p["warning"]}; }}
    QProgressBar[bad="true"]::chunk  {{ background-color: {p["danger"]}; }}
    QProgressBar[thin="true"] {{
        height: 6px;
        border-radius: 3px;
    }}
    QProgressBar[thin="true"]::chunk {{ border-radius: 3px; }}

    /* ---------- Trees, Tables & Lists ---------- */
    QTreeWidget, QTableWidget, QListWidget {{
        background-color: {p["panel"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
        alternate-background-color: {p["surface"]};
        selection-background-color: {p["accent_soft"]};
        selection-color: {p["text"]};
        outline: none;
    }}
    QTableWidget::item, QTreeWidget::item {{
        padding: 4px 6px;
    }}
    QTableWidget::item:selected, QTreeWidget::item:selected {{
        background-color: {p["accent_soft"]};
        color: {p["text"]};
    }}
    QTableWidget::item:hover, QTreeWidget::item:hover {{
        background-color: {p["surface2"]};
    }}
    QHeaderView::section {{
        background-color: {p["surface"]};
        border: none;
        border-bottom: 1px solid {p["border"]};
        padding: 8px 10px;
        color: {p["faint"]};
        font-weight: 600;
        font-size: 12px;
    }}

    /* ---------- Group Boxes ---------- */
    QGroupBox {{
        border: 1px solid {p["border"]};
        border-radius: 10px;
        margin-top: 14px;
        background-color: {p["panel"]};
        padding-top: 14px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: {p["muted"]};
        font-weight: 600;
        font-size: 12px;
    }}

    /* ---------- Drive Cards ---------- */
    QFrame#DriveCard {{
        background-color: {p["panel"]};
        border: 1px solid {p["border"]};
        border-radius: 10px;
    }}
    QFrame#DriveCard:hover {{
        border-color: {p["border2"]};
        background-color: {p["surface"]};
    }}
    QFrame#DriveCard[selected="true"] {{
        border: 2px solid {p["accent"]};
        background-color: {p["surface"]};
    }}

    /* ---------- Context Menus ---------- */
    QMenu {{
        background-color: {p["elevated"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 7px 24px 7px 12px;
        border-radius: 5px;
        color: {p["text"]};
    }}
    QMenu::item:selected {{
        background-color: {p["accent_soft"]};
        color: {p["accent"]};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {p["border"]};
        margin: 4px 6px;
    }}

    /* ---------- Tooltips & Status Bar ---------- */
    QToolTip {{
        background-color: {p["elevated"]};
        color: {p["text"]};
        border: 1px solid {p["border2"]};
        border-radius: 5px;
        padding: 5px 9px;
        font-size: 12px;
    }}
    QStatusBar {{
        background: {p["panel"]};
        border-top: 1px solid {p["border"]};
        color: {p["muted"]};
        font-size: 12px;
        padding: 2px 10px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {p["border2"]};
        border-radius: 4px;
        min-height: 26px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {p["faint"]};
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 6px;
        margin: 1px;
    }}
    QScrollBar::handle:horizontal {{
        background: {p["border2"]};
        border-radius: 3px;
        min-width: 26px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {p["faint"]};
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    """


def apply_theme(app: QApplication, theme: str) -> None:
    palette = DARK if theme == "dark" else LIGHT
    app.setStyleSheet(_build_stylesheet(palette))
    from PySide6.QtGui import QPalette

    pal = QPalette()
    bg = QColor(palette["window"])
    surface = QColor(palette["surface"])
    text = QColor(palette["text"])
    muted = QColor(palette["muted"])
    accent = QColor(palette["accent"])
    pal.setColor(QPalette.ColorRole.Window, bg)
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.Base, surface)
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(palette["panel"]))
    pal.setColor(QPalette.ColorRole.Text, text)
    pal.setColor(QPalette.ColorRole.Button, surface)
    pal.setColor(QPalette.ColorRole.ButtonText, text)
    pal.setColor(QPalette.ColorRole.Highlight, accent)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, muted)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, muted)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, muted)
    app.setPalette(pal)


THEMES = ("dark", "light")


def palette_for(theme: str) -> dict:
    return DARK if theme == "dark" else LIGHT


def color(theme: str, name: str) -> str:
    return palette_for(theme)[name]


def accent_color(theme: str) -> QColor:
    return QColor(color(theme, "accent"))


def make_window_icon() -> QIcon:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QBrush, QLinearGradient, QPainter, QPen, QPixmap

    from crapcleaner.gui.icons import draw_glyph

    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)

    rect = QRectF(2, 2, 60, 60)
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, QColor("#2563eb"))
    gradient.setColorAt(1.0, QColor("#60a5fa"))
    painter.setBrush(QBrush(gradient))
    painter.setPen(QPen(QColor("#3b82f6"), 1))
    painter.drawRoundedRect(rect, 14, 14)
    draw_glyph(painter, rect, "brand", "#ffffff", 38)
    painter.end()
    return QIcon(pixmap)
