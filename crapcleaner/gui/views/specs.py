"""System specifications view."""

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.views.common import SkeletonBlock, _c
from crapcleaner.utils.format import (
    format_size,
)
from crapcleaner.utils.platform import (
    is_windows,
    linux_drive_display_kind,
    linux_drive_display_name,
)


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
