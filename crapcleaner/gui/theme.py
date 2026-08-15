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


OLED = {
    "window": "#000000",
    "panel": "#030405",
    "surface": "#08090c",
    "surface2": "#101115",
    "elevated": "#16181e",
    "border": "#14161c",
    "border2": "#262933",
    "text": "#f8fafc",
    "muted": "#c2cbd8",
    "faint": "#8b95a5",
    "accent": "#4f8cff",
    "accent_hover": "#7aa8ff",
    "accent_pressed": "#3570e0",
    "accent_soft": "rgba(79, 140, 255, 0.16)",
    "success": "#22c55e",
    "success_soft": "rgba(34, 197, 94, 0.16)",
    "warning": "#fbbf24",
    "warning_soft": "rgba(251, 191, 36, 0.16)",
    "danger": "#f87171",
    "danger_soft": "rgba(248, 113, 113, 0.16)",
    "review": "#fb923c",
    "review_soft": "rgba(251, 146, 60, 0.16)",
    "info": "#22d3ee",
    "info_soft": "rgba(34, 211, 238, 0.16)",
    "selection": "#4f8cff",
    "safe": "#22c55e",
}

HIGH_CONTRAST = {
    "window": "#000000",
    "panel": "#000000",
    "surface": "#0d0d0d",
    "surface2": "#1a1a1a",
    "elevated": "#1a1a1a",
    "border": "#ffffff",
    "border2": "#ffffff",
    "text": "#ffffff",
    "muted": "#ffffff",
    "faint": "#e6e6e6",
    "accent": "#00b0ff",
    "accent_hover": "#66d4ff",
    "accent_pressed": "#0080c0",
    "accent_soft": "rgba(0, 176, 255, 0.30)",
    "success": "#00e676",
    "success_soft": "rgba(0, 230, 118, 0.30)",
    "warning": "#ffd600",
    "warning_soft": "rgba(255, 214, 0, 0.30)",
    "danger": "#ff5252",
    "danger_soft": "rgba(255, 82, 82, 0.30)",
    "review": "#ffab40",
    "review_soft": "rgba(255, 171, 64, 0.30)",
    "info": "#40c4ff",
    "info_soft": "rgba(64, 196, 255, 0.30)",
    "selection": "#00b0ff",
    "safe": "#00e676",
}

MIDNIGHT = {
    "window": "#0b1020",
    "panel": "#121933",
    "surface": "#18213f",
    "surface2": "#1f2a4d",
    "elevated": "#26325a",
    "border": "#1e2748",
    "border2": "#33406b",
    "text": "#eef2ff",
    "muted": "#b6c2e6",
    "faint": "#8494c4",
    "accent": "#6366f1",
    "accent_hover": "#818cf8",
    "accent_pressed": "#4f46e5",
    "accent_soft": "rgba(99, 102, 241, 0.20)",
    "success": "#34d399",
    "success_soft": "rgba(52, 211, 153, 0.18)",
    "warning": "#fbbf24",
    "warning_soft": "rgba(251, 191, 36, 0.18)",
    "danger": "#fb7185",
    "danger_soft": "rgba(251, 113, 133, 0.18)",
    "review": "#f59e0b",
    "review_soft": "rgba(245, 158, 11, 0.18)",
    "info": "#38bdf8",
    "info_soft": "rgba(56, 189, 248, 0.18)",
    "selection": "#6366f1",
    "safe": "#34d399",
}

SLATE = {
    "window": "#1b1f24",
    "panel": "#22272e",
    "surface": "#2a3038",
    "surface2": "#333a44",
    "elevated": "#3c444f",
    "border": "#2f353d",
    "border2": "#454d59",
    "text": "#e6edf3",
    "muted": "#b9c4cf",
    "faint": "#8d99a6",
    "accent": "#58a6ff",
    "accent_hover": "#79b8ff",
    "accent_pressed": "#3d8bdd",
    "accent_soft": "rgba(88, 166, 255, 0.18)",
    "success": "#3fb950",
    "success_soft": "rgba(63, 185, 80, 0.18)",
    "warning": "#d29922",
    "warning_soft": "rgba(210, 153, 34, 0.18)",
    "danger": "#f85149",
    "danger_soft": "rgba(248, 81, 73, 0.18)",
    "review": "#db6d28",
    "review_soft": "rgba(219, 109, 40, 0.18)",
    "info": "#39c5cf",
    "info_soft": "rgba(57, 197, 207, 0.18)",
    "selection": "#58a6ff",
    "safe": "#3fb950",
}

FOREST = {
    "window": "#0e1512",
    "panel": "#152019",
    "surface": "#1b2a21",
    "surface2": "#23362a",
    "elevated": "#2c4234",
    "border": "#1f3026",
    "border2": "#33513e",
    "text": "#e8f3ea",
    "muted": "#b5cdbb",
    "faint": "#87a691",
    "accent": "#4ade80",
    "accent_hover": "#86efac",
    "accent_pressed": "#22c55e",
    "accent_soft": "rgba(74, 222, 128, 0.16)",
    "success": "#22c55e",
    "success_soft": "rgba(34, 197, 94, 0.16)",
    "warning": "#eab308",
    "warning_soft": "rgba(234, 179, 8, 0.16)",
    "danger": "#f87171",
    "danger_soft": "rgba(248, 113, 113, 0.16)",
    "review": "#fb923c",
    "review_soft": "rgba(251, 146, 60, 0.16)",
    "info": "#2dd4bf",
    "info_soft": "rgba(45, 212, 191, 0.16)",
    "selection": "#4ade80",
    "safe": "#22c55e",
}

GRAPHITE = {
    "window": "#141414",
    "panel": "#1c1c1c",
    "surface": "#242424",
    "surface2": "#2e2e2e",
    "elevated": "#383838",
    "border": "#2a2a2a",
    "border2": "#3f3f3f",
    "text": "#ededed",
    "muted": "#bdbdbd",
    "faint": "#909090",
    "accent": "#9ca3af",
    "accent_hover": "#cbd5e1",
    "accent_pressed": "#6b7280",
    "accent_soft": "rgba(156, 163, 175, 0.18)",
    "success": "#4ade80",
    "success_soft": "rgba(74, 222, 128, 0.16)",
    "warning": "#facc15",
    "warning_soft": "rgba(250, 204, 21, 0.16)",
    "danger": "#f87171",
    "danger_soft": "rgba(248, 113, 113, 0.16)",
    "review": "#fb923c",
    "review_soft": "rgba(251, 146, 60, 0.16)",
    "info": "#67e8f9",
    "info_soft": "rgba(103, 232, 249, 0.16)",
    "selection": "#9ca3af",
    "safe": "#4ade80",
}

ARCTIC = {
    "window": "#eceff4",
    "panel": "#ffffff",
    "surface": "#e5e9f0",
    "surface2": "#d8dee9",
    "elevated": "#ffffff",
    "border": "#d8dee9",
    "border2": "#b8c2d0",
    "text": "#2e3440",
    "muted": "#4c566a",
    "faint": "#6b7688",
    "accent": "#5e81ac",
    "accent_hover": "#81a1c1",
    "accent_pressed": "#4c6f95",
    "accent_soft": "rgba(94, 129, 172, 0.16)",
    "success": "#2f855a",
    "success_soft": "rgba(47, 133, 90, 0.14)",
    "warning": "#b7791f",
    "warning_soft": "rgba(183, 121, 31, 0.14)",
    "danger": "#bf616a",
    "danger_soft": "rgba(191, 97, 106, 0.14)",
    "review": "#c07c33",
    "review_soft": "rgba(192, 124, 51, 0.14)",
    "info": "#2c7a92",
    "info_soft": "rgba(44, 122, 146, 0.14)",
    "selection": "#5e81ac",
    "safe": "#2f855a",
}

SOLARIZED_DARK = {
    "window": "#002b36",
    "panel": "#073642",
    "surface": "#0b4250",
    "surface2": "#14505f",
    "elevated": "#1b5c6c",
    "border": "#0d4553",
    "border2": "#1f6475",
    "text": "#eee8d5",
    "muted": "#b6c2c2",
    "faint": "#93a1a1",
    "accent": "#268bd2",
    "accent_hover": "#4aa3e0",
    "accent_pressed": "#1c6fa8",
    "accent_soft": "rgba(38, 139, 210, 0.20)",
    "success": "#859900",
    "success_soft": "rgba(133, 153, 0, 0.20)",
    "warning": "#b58900",
    "warning_soft": "rgba(181, 137, 0, 0.20)",
    "danger": "#dc322f",
    "danger_soft": "rgba(220, 50, 47, 0.20)",
    "review": "#cb4b16",
    "review_soft": "rgba(203, 75, 22, 0.20)",
    "info": "#2aa198",
    "info_soft": "rgba(42, 161, 152, 0.20)",
    "selection": "#268bd2",
    "safe": "#859900",
}

PALETTES = {
    "dark": DARK,
    "light": LIGHT,
    "oled": OLED,
    "midnight": MIDNIGHT,
    "slate": SLATE,
    "forest": FOREST,
    "graphite": GRAPHITE,
    "arctic": ARCTIC,
    "solarized-dark": SOLARIZED_DARK,
    "high-contrast": HIGH_CONTRAST,
}

THEME_LABELS = {
    "dark": "Dark (default)",
    "light": "Light",
    "oled": "OLED Black",
    "midnight": "Midnight Blue",
    "slate": "Slate",
    "forest": "Forest",
    "graphite": "Graphite",
    "arctic": "Arctic Light",
    "solarized-dark": "Solarized Dark",
    "high-contrast": "High Contrast",
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
        border: none;
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

    /* Filter Tab Buttons (flat, no pill) */
    QPushButton[chip="true"] {{
        background-color: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        border-radius: 0px;
        padding: 4px 10px;
        color: {p["muted"]};
        font-size: 12px;
        font-weight: 500;
    }}
    QPushButton[chip="true"]:hover {{
        background-color: transparent;
        color: {p["text"]};
        border-bottom: 2px solid {p["border2"]};
    }}
    QPushButton[chip="true"][active="true"] {{
        background-color: transparent;
        border-bottom: 2px solid {p["accent"]};
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
    palette = palette_for(theme)
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


THEMES = tuple(PALETTES)


def palette_for(theme: str) -> dict:
    return PALETTES.get(theme, DARK)


def theme_label(theme: str) -> str:
    return THEME_LABELS.get(theme, theme.title())


def fade_theme_change(window, apply_callback, duration_ms: int = 180) -> None:
    """Cross-fade the window from its current look to the one apply_callback sets.

    A snapshot of the old appearance is laid over the window and faded out, so
    the swap is never visible as a hard flash and the GUI is never blocked.
    """
    from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
    from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel

    snapshot = None
    if duration_ms > 0 and window is not None and window.isVisible():
        try:
            snapshot = window.grab()
        except Exception:
            snapshot = None

    apply_callback()

    if snapshot is None or snapshot.isNull():
        return

    overlay = QLabel(window)
    overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    overlay.setPixmap(snapshot)
    overlay.setGeometry(0, 0, snapshot.width(), snapshot.height())
    effect = QGraphicsOpacityEffect(overlay)
    overlay.setGraphicsEffect(effect)
    overlay.show()
    overlay.raise_()

    animation = QPropertyAnimation(effect, b"opacity", overlay)
    animation.setDuration(duration_ms)
    animation.setStartValue(1.0)
    animation.setEndValue(0.0)
    animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
    animation.finished.connect(overlay.deleteLater)
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    window._theme_fade_overlay = overlay


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
