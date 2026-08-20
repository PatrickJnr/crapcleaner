"""Help and safety documentation view."""

import os
from datetime import datetime

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.views.common import _c, badge, page_header


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

        self.bundle_button = QPushButton("Save Diagnostics Bundle...")
        self.bundle_button.setProperty("secondary", "true")
        self.bundle_button.setIcon(material_icon("file_download", _c(self._theme, "text")))
        self.bundle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bundle_button.setToolTip(
            "Write a support bundle to a file. Every path in it is reduced to its root."
        )
        self.bundle_button.clicked.connect(self._save_diagnostics_bundle)
        header_row.addWidget(self.bundle_button)

        root_lay.addLayout(header_row)

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
        self.search_edit.setAccessibleName("Search documentation and FAQs")
        self.search_edit.textChanged.connect(self._apply_search)
        toolbar.addWidget(self.search_edit)

        root_lay.addLayout(toolbar)

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
        # Same text the saved bundle carries, so the two cannot drift apart.
        from crapcleaner.system.diagnostics import build_diagnostics_text

        QApplication.clipboard().setText(build_diagnostics_text())
        QMessageBox.information(
            self,
            "Diagnostics Copied",
            "System diagnostics copied to clipboard.",
        )

    def _save_diagnostics_bundle(self):
        default = os.path.join(
            os.path.expanduser("~"),
            f"crapcleaner-diagnostics-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt",
        )
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save Diagnostics Bundle", default, "Text (*.txt)"
        )
        if not dest:
            return
        from crapcleaner.gui.workers import DiagnosticsWorker

        self.bundle_button.setEnabled(False)
        worker = DiagnosticsWorker(dest, self)
        self._bundle_worker = worker
        worker.done.connect(self._bundle_written)
        worker.failed.connect(self._bundle_failed)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        return worker

    def _bundle_written(self, path: str):
        self.bundle_button.setEnabled(True)
        QMessageBox.information(
            self,
            "Diagnostics Bundle",
            f"Saved to:\n{path}\n\nEvery path inside it is reduced to its root before "
            "being written, so it is safe to attach to a bug report.",
        )

    def _bundle_failed(self, message: str):
        self.bundle_button.setEnabled(True)
        QMessageBox.warning(self, "Diagnostics Bundle", f"Could not write the bundle:\n{message}")

    def apply_theme(self, theme: str):
        self._theme = theme
