"""Left navigation rail for the CrapCleaner main window."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.icons import icon
from crapcleaner.gui.theme import color as theme_color
from crapcleaner.gui.theme import make_window_icon
from crapcleaner.system.capabilities import get_capability
from crapcleaner.utils.platform import is_admin


def nav_label(key: str, fallback: str) -> str:
    """The label this platform uses for a page, falling back to the generic one."""
    capability = get_capability(key)
    return capability.nav_label if capability.supported else fallback


NAV_SECTIONS = [
    (
        "OVERVIEW",
        [
            ("dashboard", "Dashboard", "home"),
            ("cleanup", "Cleanup", "delete"),
            ("storage", "Storage Breakdown", "pie_chart"),
        ],
    ),
    (
        "DEEP SCAN",
        [
            ("large", "Large Files", "search"),
            ("duplicates", "Duplicates", "content_copy"),
            ("ai", "AI Data", "psychology"),
            ("docker", "Docker", "storage"),
        ],
    ),
    (
        "SYSTEM",
        [
            ("specs", "PC Specs", "specs"),
            ("memory", "Memory Cleaner", "memory"),
            # The label for these four comes from the capability registry, so each
            # platform names them in its own vocabulary. The text here is a fallback.
            ("startup", "Startup Apps", "rocket"),
            ("services", "Services", "tune"),
            ("app_updates", "App Updates", "system_update"),
            ("updates", "System Updates", "system_update"),
            ("history", "History", "history"),
        ],
    ),
    (
        "PREFERENCES",
        [
            ("settings", "Settings", "settings"),
            ("about", "About", "about"),
        ],
    ),
]

NAV_ITEMS = [item for _, items in NAV_SECTIONS for item in items]


class NavButton(QPushButton):
    """Navigation button using native Qt icon + text with dynamic badge text."""

    def __init__(self, key: str, label: str, icon_name: str, parent=None):
        clean_label = label.replace("&", "&&") if "&&" not in label else label
        super().__init__(clean_label, parent)
        self.key = key
        self.base_label = clean_label
        self._icon_name = icon_name
        self.setProperty("nav", "true")
        self.setProperty("active", "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(38)
        self.setIconSize(QSize(18, 18))

    def set_badge(self, text: str):
        if text:
            self.setText(f"{self.base_label}  ({text})")
        else:
            self.setText(self.base_label)


class Sidebar(QFrame):
    navigation_requested = Signal(str)
    help_requested = Signal()

    def __init__(self, version: str, page_keys: list | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("SideBar")
        self.setFixedWidth(230)
        self._theme = "dark"
        self._buttons: dict[str, NavButton] = {}
        # page_keys controls which nav items are visible (None = show all)
        self._page_keys = set(page_keys) if page_keys is not None else None
        self._build(version)

    def _build(self, version: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 14)
        layout.setSpacing(3)

        # Brand header
        brand_card = QWidget()
        brand_card.setStyleSheet("background: transparent;")
        brand_lay = QHBoxLayout(brand_card)
        brand_lay.setContentsMargins(4, 0, 4, 10)
        brand_lay.setSpacing(10)

        brand_icon = QLabel()
        brand_icon.setPixmap(make_window_icon().pixmap(36, 36))
        brand_icon.setFixedSize(36, 36)
        brand_icon.setScaledContents(True)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(2)
        title = QLabel("CrapCleaner")
        title.setObjectName("BrandTitle")

        sub_row = QHBoxLayout()
        sub_row.setSpacing(6)
        ver_label = QLabel(f"v{version}")
        ver_label.setObjectName("BrandSub")
        sub_row.addWidget(ver_label)

        admin_badge = QLabel("ADMIN" if is_admin() else "USER")
        admin_badge.setProperty("badge", "true")
        admin_badge.setProperty("level", "safe" if is_admin() else "accent")
        admin_badge.setStyleSheet(
            "font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 4px;"
        )
        sub_row.addWidget(admin_badge)
        sub_row.addStretch(1)

        brand_text.addWidget(title)
        brand_text.addLayout(sub_row)

        brand_lay.addWidget(brand_icon)
        brand_lay.addLayout(brand_text)
        layout.addWidget(brand_card)
        layout.addSpacing(4)

        # Navigation sections — only show items whose key is in _page_keys
        for section_title, items in NAV_SECTIONS:
            visible_items = [
                (k, lbl, ico)
                for k, lbl, ico in items
                if self._page_keys is None or k in self._page_keys
            ]
            if not visible_items:
                continue  # skip section if all items hidden on this platform
            sec_lbl = QLabel(section_title)
            sec_lbl.setProperty("navSection", "true")
            layout.addWidget(sec_lbl)
            for key, label, icon_name in visible_items:
                button = NavButton(key, nav_label(key, label), icon_name)
                button.setIcon(icon(icon_name, theme_color(self._theme, "muted")))
                button.clicked.connect(lambda _=False, k=key: self.navigation_requested.emit(k))
                layout.addWidget(button)
                self._buttons[key] = button
            layout.addSpacing(4)

        layout.addStretch(1)

        # Footer
        footer_card = QFrame()
        footer_card.setProperty("card", "true")
        footer_card.setStyleSheet("border-radius: 8px; padding: 8px;")
        footer_lay = QVBoxLayout(footer_card)
        footer_lay.setContentsMargins(10, 8, 10, 8)
        footer_lay.setSpacing(4)

        top_foot = QHBoxLayout()
        tip_title = QLabel("Safety First")
        tip_title.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {theme_color(self._theme, 'accent')};"
        )
        top_foot.addWidget(tip_title, 1)

        help_btn = QPushButton("?")
        help_btn.setFixedSize(18, 18)
        help_btn.setToolTip("Help, Safety Philosophy & FAQs (F1)")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.setStyleSheet("font-size: 10px; font-weight: 700; border-radius: 9px; padding: 0;")
        help_btn.clicked.connect(self.help_requested.emit)
        top_foot.addWidget(help_btn)
        footer_lay.addLayout(top_foot)

        self.footer = QLabel("Scans never delete files.\nCleanups use Recycle Bin.")
        self.footer.setProperty("subtle", "true")
        self.footer.setStyleSheet(f"font-size: 11px; color: {theme_color(self._theme, 'muted')};")
        self.footer.setWordWrap(True)
        footer_lay.addWidget(self.footer)

        learn_btn = QPushButton("Help && Safety Guide →")
        learn_btn.setProperty("subtle", "true")
        learn_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        learn_btn.setStyleSheet(
            f"font-size: 10px; font-weight: 600; text-align: left; padding: 2px 0; color: {theme_color(self._theme, 'accent')}; background: transparent; border: none;"
        )
        learn_btn.clicked.connect(self.help_requested.emit)
        footer_lay.addWidget(learn_btn)
        self._learn_btn = learn_btn
        self._tip_title = tip_title

        layout.addWidget(footer_card)

    def set_active(self, key: str):
        for k, button in self._buttons.items():
            active = k == key
            button.setProperty("active", "true" if active else "false")
            button.setIcon(
                icon(
                    button._icon_name,
                    theme_color(self._theme, "accent" if active else "muted"),
                )
            )
            button.style().unpolish(button)
            button.style().polish(button)

    def set_badge(self, key: str, text: str):
        if key in self._buttons:
            self._buttons[key].set_badge(text)

    def apply_theme(self, theme: str):
        self._theme = theme
        self.footer.setStyleSheet(f"font-size: 11px; color: {theme_color(theme, 'muted')};")
        if hasattr(self, "_tip_title"):
            self._tip_title.setStyleSheet(
                f"font-size: 11px; font-weight: 700; color: {theme_color(theme, 'accent')};"
            )
        if hasattr(self, "_learn_btn"):
            self._learn_btn.setStyleSheet(
                f"font-size: 10px; font-weight: 600; text-align: left; padding: 2px 0; color: {theme_color(theme, 'accent')}; background: transparent; border: none;"
            )
        for key, button in self._buttons.items():
            active = button.property("active") == "true"
            button.setIcon(
                icon(
                    button._icon_name,
                    theme_color(theme, "accent" if active else "muted"),
                )
            )
