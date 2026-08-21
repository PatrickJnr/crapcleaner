"""Left navigation rail for the CrapCleaner main window."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
    # Eight items under one heading was the longest undifferentiated run in the rail,
    # and the two update pages sat adjacent reading as near-duplicates of each other.
    (
        "SYSTEM",
        [
            ("specs", "PC Specs", "specs"),
            ("drives", "Drives", "drives"),
            ("memory", "Memory Cleaner", "memory"),
        ],
    ),
    (
        "MAINTENANCE",
        [
            # Startup and Services are relabelled per platform by the capability
            # registry; the text here is only the fallback.
            ("startup", "Startup Apps", "rocket"),
            ("services", "Services", "tune"),
            ("history", "History", "history"),
        ],
    ),
    (
        "UPDATES",
        [
            ("app_updates", "App Updates", "app_update"),
            ("updates", "System Updates", "system_update"),
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
    """Navigation button using native Qt icon + text with a right-aligned badge pill."""

    def __init__(self, key: str, label: str, icon_name: str, parent=None):
        clean_label = label.replace("&", "&&") if "&&" not in label else label
        super().__init__(clean_label, parent)
        self.key = key
        self.base_label = clean_label
        self._icon_name = icon_name
        self.setProperty("nav", "true")
        self.setProperty("active", "false")
        self.setAccessibleName(clean_label.replace("&&", "&"))
        self.setAccessibleDescription(f"Open the {clean_label.replace('&&', '&')} page")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(38)
        self.setIconSize(QSize(18, 18))
        # The rail is a fixed width, so a long label must give way rather than push the
        # button wider than the rail: inside a scroll area an oversized minimum is
        # honoured, and everything to the right of it - the badge - is clipped away.
        # Ignored, not a zero minimum: the default policy refuses to shrink below the
        # text's own hint.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

        # The badge floats over the button's own right edge rather than being appended to
        # the label: a label that grows with its count pushes against a fixed-width rail
        # and cannot be styled or aligned.
        badge_lay = QHBoxLayout(self)
        badge_lay.setContentsMargins(0, 0, 9, 0)
        # The pill is an overlay, not content: without this it adds its own width to the
        # button's minimum, which pushed the buttons wider than the rail and clipped the
        # badges off the right edge.
        badge_lay.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        badge_lay.addStretch(1)
        self._badge = QLabel("")
        self._badge.setProperty("navBadge", "true")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # Without a fixed height the label takes the whole row and the pill becomes a
        # block; without a Fixed policy it stretches past the rail's right edge.
        self._badge.setFixedHeight(18)
        # A single digit is narrower than twice the corner radius, which collapses
        # the pill into a square.
        self._badge.setMinimumWidth(20)
        self._badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._badge.setVisible(False)
        badge_lay.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_badge(self, text: str, level: str = ""):
        """`level` picks the pill colour: "" is neutral, "accent" asks for attention."""
        self._badge.setText(text)
        self._badge.setVisible(bool(text))
        self._badge.setProperty("level", level)
        self._badge.style().unpolish(self._badge)
        self._badge.style().polish(self._badge)
        self.setAccessibleDescription(
            f"Open the {self.base_label.replace('&&', '&')} page" + (f", {text}" if text else "")
        )


class Sidebar(QFrame):
    navigation_requested = Signal(str)
    help_requested = Signal()

    def __init__(self, version: str, page_keys: list | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("SideBar")
        self.setFixedWidth(230)
        self._theme = "dark"
        self._buttons: dict[str, NavButton] = {}
        self._page_keys = set(page_keys) if page_keys is not None else None
        self._build(version)

    def _build(self, version: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 14)
        layout.setSpacing(3)

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

        # Every nav button is a fixed 38px tall, so the rail cannot compress: on a window
        # shorter than the full list the bottom of it was simply cut off. The brand and
        # the footer stay pinned and the navigation scrolls between them.
        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Scoped by object name on purpose: a selector-less widget stylesheet applies
        # to the whole subtree, which blanked the active row's fill and the badge pills.
        nav_scroll.setObjectName("NavScroll")
        nav_scroll.setStyleSheet("#NavScroll, #NavScroll > QWidget { background: transparent; }")
        nav_host = QWidget()
        nav_host.setObjectName("NavHost")
        nav_host.setStyleSheet("#NavHost { background: transparent; }")
        nav_lay = QVBoxLayout(nav_host)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(3)

        for section_title, items in NAV_SECTIONS:
            visible_items = [
                (k, lbl, ico)
                for k, lbl, ico in items
                if self._page_keys is None or k in self._page_keys
            ]
            if not visible_items:
                continue
            sec_lbl = QLabel(section_title)
            sec_lbl.setProperty("navSection", "true")
            nav_lay.addWidget(sec_lbl)
            for key, label, icon_name in visible_items:
                button = NavButton(key, nav_label(key, label), icon_name)
                button.setIcon(icon(icon_name, theme_color(self._theme, "muted")))
                button.clicked.connect(lambda _=False, k=key: self.navigation_requested.emit(k))
                nav_lay.addWidget(button)
                self._buttons[key] = button
            nav_lay.addSpacing(4)

        nav_lay.addStretch(1)
        nav_scroll.setWidget(nav_host)
        layout.addWidget(nav_scroll, 1)

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

    def set_badge(self, key: str, text: str, level: str = ""):
        if key in self._buttons:
            self._buttons[key].set_badge(text, level)

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
