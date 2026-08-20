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
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.icons import ASSETS_DIR
from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.views.common import ContributorCard, SquircleAvatarWidget, _c, badge


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

        header = QVBoxLayout()
        header.setSpacing(4)
        h1 = QLabel("About CrapCleaner")
        h1.setObjectName("ViewTitle")
        sub = QLabel("Open-source, non-destructive system cleaner and developer storage toolkit.")
        sub.setProperty("subtle", "true")
        header.addWidget(h1)
        header.addWidget(sub)
        root_lay.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        c_lay = QVBoxLayout(content)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(16)

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

        grid_lay = QHBoxLayout()
        grid_lay.setSpacing(14)

        app_card = QFrame()
        app_card.setProperty("card", "true")
        app_lay = QVBoxLayout(app_card)
        app_lay.setContentsMargins(18, 16, 18, 16)
        app_lay.setSpacing(10)
        app_title = QLabel("Application Information")
        app_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        app_lay.addWidget(app_title)

        app_items = self._application_facts()
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
            (
                "Scheduled Scans Only Scan",
                "A scan that runs on a schedule reports what it found and deletes nothing.",
            ),
            (
                "Updates Are Verified",
                "A download is checked against the published SHA-256 before it replaces "
                "anything, and the version you are running is kept until the new one starts.",
            ),
            (
                "Nothing Is Reported About You",
                "No telemetry, no tracking, no advertisements. GitHub is contacted only "
                "for the contributor list and update checks.",
            ),
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

    def _application_facts(self) -> list[tuple[str, str]]:
        """What is actually running, asked at the moment the page is built.

        These were string literals, so the page said Python 3.12 on 3.10 and
        named Windows on Linux.
        """
        import platform
        import sys

        from crapcleaner import __version__
        from crapcleaner.gui.theme import BUILTIN_THEME_IDS
        from crapcleaner.system.hardware import os_label

        try:
            import PySide6
            from PySide6.QtCore import qVersion

            toolkit = f"PySide6 {PySide6.__version__} (Qt {qVersion()})"
        except Exception:  # pragma: no cover - PySide6 is how we are drawing this
            toolkit = "PySide6 (Qt 6)"

        running = platform.python_version()
        return [
            ("Version", f"v{__version__}"),
            ("License", "MIT License (100% free and open source)"),
            ("Platform", os_label()),
            ("GUI Framework", toolkit),
            ("Themes", f"{len(BUILTIN_THEME_IDS)} built in, plus your own"),
            (
                "Python",
                f"{running} ({'frozen build' if getattr(sys, 'frozen', False) else 'source'})",
            ),
        ]

    def _populate_contributors(self, force_refresh: bool = False):
        """Start the fetch. The grid is filled in when it returns.

        This used to call the network inline - a 3 s request for the list, then a
        blocking avatar download per contributor - from the page constructor, so
        opening About froze the whole window until every request finished or timed out.
        """
        from crapcleaner.config import offline_mode
        from crapcleaner.gui.workers import ContributorsWorker, is_worker_running

        if is_worker_running(getattr(self, "_contrib_worker", None)):
            return

        if offline_mode():
            self._clear_contributor_grid()
            note = QLabel(
                "Offline mode is on, so the contributor list was not fetched from GitHub. "
                "Turn offline mode off in Settings to load it."
            )
            note.setWordWrap(True)
            note.setProperty("subtle", "true")
            self.contrib_grid.addWidget(note, 0, 0)
            return

        self._clear_contributor_grid()
        loading = QLabel("Loading contributors…")
        loading.setProperty("subtle", "true")
        self.contrib_grid.addWidget(loading, 0, 0)

        worker = ContributorsWorker(force_refresh=force_refresh, parent=self)
        self._contrib_worker = worker
        worker.done.connect(self._show_contributors)
        worker.failed.connect(self._show_contributor_error)
        worker.finished.connect(lambda: setattr(self, "_contrib_worker", None))
        worker.start()

    def _clear_contributor_grid(self):
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

    def _show_contributor_error(self, message: str):
        self._clear_contributor_grid()
        err_lbl = QLabel(f"Could not load contributors: {message}")
        err_lbl.setProperty("subtle", "true")
        self.contrib_grid.addWidget(err_lbl, 0, 0)

    def _show_contributors(self, fetched: list):
        """Render the fetched contributors. Widgets are built on the GUI thread."""
        self._clear_contributor_grid()

        # Filter out the project creator, who has the hero card above.
        community = [
            (c, avatar)
            for c, avatar in fetched
            if c.login.lower() not in ("patrickjnr", "patrickjr")
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

        for idx, (contributor, avatar_file) in enumerate(community):
            card = ContributorCard(contributor, avatar_file or None, self._theme, self)
            self.contrib_grid.addWidget(card, idx // 2, idx % 2)

        if len(community) % 2 != 0:
            # Keep the two-column grid balanced when the count is odd.
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.contrib_grid.addWidget(spacer, len(community) // 2, 1)

    def _check_updates(self):
        """Ask GitHub for the latest release without blocking the window."""
        from crapcleaner.gui.workers import UpdateCheckWorker, is_worker_running
        from crapcleaner.utils.updater import offline_skip_reason

        if is_worker_running(getattr(self, "_update_worker", None)):
            return
        skipped = offline_skip_reason()
        if skipped:
            QMessageBox.information(self, "Check for Updates", skipped)
            return
        worker = UpdateCheckWorker(parent=self)
        self._update_worker = worker
        worker.done.connect(self._show_update_result)
        worker.failed.connect(lambda _message: self._show_update_result(None))
        worker.finished.connect(lambda: setattr(self, "_update_worker", None))
        worker.start()

    def _show_update_result(self, info):
        from crapcleaner import __version__

        if info is None:
            QMessageBox.information(
                self,
                "Check for Updates",
                f"You are running CrapCleaner v{__version__}.\nCould not connect to GitHub to check for newer releases.",
            )
            return
        if info.is_newer:
            self._offer_update(info)
        else:
            QMessageBox.information(
                self,
                "Up to Date!",
                f"CrapCleaner v{info.current_version} is up to date.\nYou have the latest release installed.",
            )

    def _offer_update(self, info):
        """Offer to install the new release, or to open the page if we cannot."""
        from crapcleaner.utils.self_update import can_self_update

        allowed, reason = can_self_update()
        if not allowed:
            answer = QMessageBox.information(
                self,
                "Update Available",
                f"CrapCleaner v{info.latest_version} is available "
                f"(you have v{info.current_version}).\n\n{reason}\n\n"
                "Open the release page?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(info.html_url))
            return

        answer = QMessageBox.question(
            self,
            "Update Available",
            f"CrapCleaner v{info.latest_version} is available "
            f"(you have v{info.current_version}).\n\n"
            "It will be downloaded and checked against the published checksum, then "
            "CrapCleaner will close and reopen on the new version.\n\n"
            "Download and install it now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._start_update_download(info.latest_version)

    def _start_update_download(self, version: str):
        from crapcleaner.gui.workers import UpdateDownloadWorker

        self._update_progress = QProgressDialog(
            f"Downloading CrapCleaner v{version}…", "Cancel", 0, 100, self
        )
        self._update_progress.setWindowTitle("Updating")
        self._update_progress.setAutoClose(False)
        self._update_progress.setValue(0)
        self._update_progress.show()

        worker = UpdateDownloadWorker(version, parent=self)
        self._download_worker = worker
        worker.progress.connect(self._on_update_progress)
        worker.done.connect(self._on_update_downloaded)
        worker.failed.connect(self._on_update_failed)
        self._update_progress.canceled.connect(worker.terminate)
        worker.finished.connect(lambda: setattr(self, "_download_worker", None))
        worker.start()

    def _on_update_progress(self, received: int, total: int):
        from crapcleaner.utils.format import format_size

        dialog = getattr(self, "_update_progress", None)
        if dialog is None:
            return
        if total > 0:
            dialog.setValue(int(received / total * 100))
        else:
            dialog.setLabelText(f"Downloading… {format_size(received)}")

    def _on_update_failed(self, message: str):
        from crapcleaner import __version__

        dialog = getattr(self, "_update_progress", None)
        if dialog is not None:
            dialog.close()
        QMessageBox.warning(
            self,
            "Update Failed",
            f"{message}\n\nNothing was changed - you are still running v{__version__}.",
        )

    def _on_update_downloaded(self, update):
        """Verified. Ask once more, then hand over to the installer and quit."""
        dialog = getattr(self, "_update_progress", None)
        if dialog is not None:
            dialog.close()

        answer = QMessageBox.question(
            self,
            "Restart to finish",
            f"CrapCleaner v{update.version} has been downloaded and its checksum "
            "verified.\n\nCrapCleaner will now close and reopen on the new version. "
            "The current version is kept until the new one starts.\n\nRestart now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            QMessageBox.information(
                self,
                "Update Ready",
                "The update is downloaded and will be applied the next time you "
                "choose Check for Updates.",
            )
            return

        from crapcleaner.utils.self_update import UpdateError, apply_update

        try:
            apply_update(update)
        except UpdateError as exc:
            QMessageBox.warning(self, "Update Failed", str(exc))
            return

        # The installer is waiting on this process to exit before it swaps anything.
        from PySide6.QtWidgets import QApplication

        application = QApplication.instance()
        if application is not None:
            application.quit()

    def apply_theme(self, theme: str):
        self._theme = theme
