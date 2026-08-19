"""About view and contributor cards."""

from PySide6.QtCore import (
    Qt,
    QUrl,
)
from PySide6.QtGui import (
    QDesktopServices,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.icons import ASSETS_DIR
from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.views.common import ContributorCard, SquircleAvatarWidget, _c, badge
from crapcleaner.utils.contributors import fetch_avatar_file, fetch_contributors


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

        avatar = SquircleAvatarWidget(str(ASSETS_DIR / "avatar.jpg"), size=116, radius=28)
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
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/PatrickJnr/crapcleaner"))
        )
        links_row.addWidget(gh_btn)

        issue_btn = QPushButton("Report Issue")
        issue_btn.setProperty("secondary", "true")
        issue_btn.setIcon(material_icon("bug_report", _c(self._theme, "text")))
        issue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        issue_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/PatrickJnr/crapcleaner/issues")
            )
        )
        links_row.addWidget(issue_btn)

        help_guide_btn = QPushButton("Help && Safety Guide")
        help_guide_btn.setProperty("secondary", "true")
        help_guide_btn.setIcon(material_icon("help", _c(self._theme, "text")))
        help_guide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_guide_btn.clicked.connect(
            lambda: getattr(self._main, "show_help_dialog", lambda: None)()
        )
        links_row.addWidget(help_guide_btn)

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

        doc_btn = QPushButton("Read Full Safety Philosophy && FAQs →")
        doc_btn.setProperty("subtle", "true")
        doc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        doc_btn.setStyleSheet(
            f"font-size: 11px; font-weight: 600; text-align: left; padding: 4px 0; color: {_c(self._theme, 'accent')}; background: transparent; border: none;"
        )
        doc_btn.clicked.connect(lambda: getattr(self._main, "show_help_dialog", lambda: None)())
        s_lay.addWidget(doc_btn)

        grid_lay.addWidget(safety_card, 1)
        c_lay.addLayout(grid_lay)

        # 3. Contributors & Credits Card (Responsive Grid Layout)
        contrib_card = QFrame()
        contrib_card.setProperty("card", "true")
        contrib_lay = QVBoxLayout(contrib_card)
        contrib_lay.setContentsMargins(18, 16, 18, 16)
        contrib_lay.setSpacing(12)

        c_header = QHBoxLayout()
        c_header.setSpacing(10)
        c_title = QLabel("Community Contributors & Credits")
        c_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        c_header.addWidget(c_title)

        self.contrib_count_badge = badge("0", "accent")
        self.contrib_count_badge.setFixedHeight(20)
        self.contrib_count_badge.setVisible(False)
        c_header.addWidget(self.contrib_count_badge)

        c_header.addStretch(1)

        refresh_contrib_btn = QPushButton("Refresh")
        refresh_contrib_btn.setProperty("secondary", "true")
        refresh_contrib_btn.setIcon(material_icon("refresh", _c(self._theme, "text")))
        refresh_contrib_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_contrib_btn.clicked.connect(lambda: self._populate_contributors(force_refresh=True))
        c_header.addWidget(refresh_contrib_btn)

        contribute_btn = QPushButton("Contribute on GitHub ↗")
        contribute_btn.setProperty("primary", "true")
        contribute_btn.setIcon(material_icon("code", "#ffffff"))
        contribute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        contribute_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/PatrickJnr/crapcleaner/blob/master/CONTRIBUTING.md")
            )
        )
        c_header.addWidget(contribute_btn)
        contrib_lay.addLayout(c_header)

        c_sub = QLabel(
            "Recognizing community members who have contributed pull requests, bug fixes, and documentation to CrapCleaner."
        )
        c_sub.setProperty("subtle", "true")
        c_sub.setStyleSheet(f"font-size: 12px; color: {_c(self._theme, 'muted')};")
        contrib_lay.addWidget(c_sub)

        self.contrib_grid = QGridLayout()
        self.contrib_grid.setSpacing(12)
        self.contrib_grid.setColumnStretch(0, 1)
        self.contrib_grid.setColumnStretch(1, 1)
        contrib_lay.addLayout(self.contrib_grid)
        c_lay.addWidget(contrib_card)

        # 4. Sponsor & Support Card (Interactive FUNDING links)
        sponsor_card = QFrame()
        sponsor_card.setProperty("card", "true")
        sponsor_lay = QVBoxLayout(sponsor_card)
        sponsor_lay.setContentsMargins(18, 16, 18, 16)
        sponsor_lay.setSpacing(12)

        s_top = QHBoxLayout()
        s_title = QLabel("Support CrapCleaner Development")
        s_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        s_top.addWidget(s_title)
        s_top.addStretch(1)
        sponsor_lay.addLayout(s_top)

        s_desc = QLabel(
            "CrapCleaner is 100% free, non-commercial, and open source without advertisements or telemetry. "
            "If it helps keep your PC fast and clean, consider supporting ongoing maintenance and new features!"
        )
        s_desc.setProperty("subtle", "true")
        s_desc.setStyleSheet(
            f"font-size: 12px; color: {_c(self._theme, 'muted')}; line-height: 1.4;"
        )
        s_desc.setWordWrap(True)
        sponsor_lay.addWidget(s_desc)

        sponsor_row = QHBoxLayout()
        sponsor_row.setSpacing(10)

        sponsors_links = [
            ("GitHub Sponsors", "https://github.com/sponsors/PatrickJnr", "favorite"),
            ("Buy Me a Coffee", "https://buymeacoffee.com/PatrickJr", "local_cafe"),
            ("Ko-fi", "https://ko-fi.com/patrickjr", "local_cafe"),
            ("PayPal", "https://www.paypal.me/PatrickJnrC", "payments"),
        ]
        for name, url, icon_name in sponsors_links:
            s_btn = QPushButton(name)
            s_btn.setProperty("secondary", "true")
            s_btn.setIcon(material_icon(icon_name, _c(self._theme, "text")))
            s_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            s_btn.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            sponsor_row.addWidget(s_btn)

        sponsor_row.addStretch(1)
        sponsor_lay.addLayout(sponsor_row)
        c_lay.addWidget(sponsor_card)

        c_lay.addStretch(1)
        scroll.setWidget(content)
        root_lay.addWidget(scroll, 1)
        self._populate_contributors()

    def _populate_contributors(self, force_refresh: bool = False):
        while self.contrib_grid.count():
            item = self.contrib_grid.takeAt(0)
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

        self.contrib_grid.setColumnStretch(0, 1)
        self.contrib_grid.setColumnStretch(1, 1)

        try:
            contributors = fetch_contributors(timeout_seconds=3.0, force_refresh=force_refresh)
            # Filter out project creator/maintainer since they have the primary creator hero card
            community = [
                c for c in contributors if c.login.lower() not in ("patrickjnr", "patrickjr")
            ]
            if hasattr(self, "contrib_count_badge"):
                self.contrib_count_badge.setText(
                    f"{len(community)} {'Contributor' if len(community) == 1 else 'Contributors'}"
                )
                self.contrib_count_badge.setVisible(len(community) > 0)

            if not community:
                empty_lbl = QLabel(
                    "No community contributors cached yet. Contributions welcome on GitHub!"
                )
                empty_lbl.setProperty("subtle", "true")
                self.contrib_grid.addWidget(empty_lbl, 0, 0)
                return

            for idx, c in enumerate(community):
                avatar_file = fetch_avatar_file(c.avatar_url, c.login, timeout_seconds=1.5)
                card = ContributorCard(c, avatar_file, self._theme, self)
                row = idx // 2
                col = idx % 2
                self.contrib_grid.addWidget(card, row, col)

            if len(community) % 2 != 0:
                # Add empty spacer widget to keep the 2-column grid balanced when odd count
                spacer = QWidget()
                spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                self.contrib_grid.addWidget(spacer, len(community) // 2, 1)
        except Exception as exc:
            err_lbl = QLabel(f"Could not load contributors: {exc}")
            err_lbl.setProperty("subtle", "true")
            self.contrib_grid.addWidget(err_lbl, 0, 0)

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
                QDesktopServices.openUrl(QUrl(info.html_url))
        else:
            QMessageBox.information(
                self,
                "Up to Date!",
                f"CrapCleaner v{info.current_version} is up to date.\nYou have the latest release installed.",
            )

    def apply_theme(self, theme: str):
        self._theme = theme
