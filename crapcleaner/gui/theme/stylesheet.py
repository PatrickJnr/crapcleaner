"""Qt stylesheet generation and theme application.

Separate from the palette data (:mod:`crapcleaner.gui.theme.palettes`) so adding a
colour scheme is a data change and restyling widgets is a code change.
"""

from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication

from crapcleaner.gui.theme.palettes import palette_for


def _build_stylesheet(p: dict) -> str:
    # Callers pass raw palettes as well as prepared ones, so derive rather than assume.
    from crapcleaner.gui.theme.palettes import derive_ink

    p = derive_ink(p)
    return f"""
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
    QFrame[card="true"] {{
        background-color: {p["panel"]};
        border: 1px solid {p["border"]};
        border-radius: 10px;
    }}
    QFrame[cardHover="true"]:hover {{
        border-color: {p["border2"]};
        background-color: {p["surface"]};
    }}
    /* Driven by effects.elevate(). A property toggle rather than a geometry change,
       so a lifting card cannot reflow the row it sits in. */
    QFrame[hovered="true"] {{
        border: 1px solid {p["accent"]};
        background-color: {p["elevated"]};
    }}
    QFrame[statCard="true"] {{
        background-color: {p["panel"]};
        border: 1px solid {p["border"]};
        border-radius: 10px;
    }}
    QFrame[statCard="true"]:hover {{
        border-color: {p["border2"]};
    }}
    QLabel[badge="true"] {{
        background-color: {p["surface"]};
        color: {p["muted"]};
        border-radius: 9px;
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 600;
    }}
    QLabel[badge="true"][level="accent"] {{ background-color: {p["accent_soft"]}; color: {p["on_accent_soft"]}; }}
    QLabel[badge="true"][level="safe"]   {{ background-color: {p["success_soft"]}; color: {p["on_success_soft"]}; }}
    QLabel[badge="true"][level="warn"]   {{ background-color: {p["warning_soft"]}; color: {p["on_warning_soft"]}; }}
    QLabel[badge="true"][level="danger"] {{ background-color: {p["danger_soft"]}; color: {p["on_danger_soft"]}; }}
    QLabel[badge="true"][level="review"] {{ background-color: {p["review_soft"]}; color: {p["on_review_soft"]}; }}
    QLabel[badge="true"][level="info"]   {{ background-color: {p["info_soft"]}; color: {p["on_info_soft"]}; }}
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
    QPushButton[primary="true"] {{
        background-color: {p["accent"]};
        border: 1px solid {p["accent"]};
        color: {p["on_accent"]};
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
    QPushButton[danger="true"] {{
        background-color: {p["danger"]};
        border: 1px solid {p["danger"]};
        color: {p["on_danger"]};
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
    QHeaderView::section:hover {{
        background-color: {p["surface2"]};
        color: {p["text"]};
    }}
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


def apply_theme(app: QApplication, theme: str, window=None) -> None:
    """Apply a theme, on the window when there is one.

    `QApplication.setStyleSheet` re-polishes every top-level: 1115ms against 243ms
    on the window for the same 845 widgets, which is the difference between a theme
    you can edit live and one you cannot. Dialogs are parented inside the window, so
    they inherit either way; the app-level sheet is only for start-up, before the
    window exists.
    """
    palette = palette_for(theme)
    sheet = _build_stylesheet(palette)
    if window is not None:
        window.setStyleSheet(sheet)
    else:
        app.setStyleSheet(sheet)
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


def fade_theme_change(window, apply_callback, duration_ms: int = 180) -> None:
    from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
    from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel

    fade_anim = getattr(window, "_theme_fade_anim", None)
    if fade_anim:
        try:
            fade_anim.stop()
        except Exception:
            pass
        setattr(window, "_theme_fade_anim", None)

    fade_overlay = getattr(window, "_theme_fade_overlay", None)
    if fade_overlay:
        try:
            fade_overlay.deleteLater()
        except Exception:
            pass
        setattr(window, "_theme_fade_overlay", None)

    snapshot = None
    if duration_ms > 0 and window is not None and window.isVisible():
        try:
            snapshot = window.grab()
        except Exception:
            snapshot = None
    apply_callback()
    if snapshot is None or snapshot.isNull():
        return
    try:
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
        setattr(window, "_theme_fade_anim", animation)
        setattr(window, "_theme_fade_overlay", overlay)
        animation.start()
    except Exception:
        pass


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
