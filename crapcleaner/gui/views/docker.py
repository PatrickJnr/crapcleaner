"""Docker and WSL storage view."""

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.dialogs import (
    ConfirmDeleteDialog,
)
from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.views.common import CrapTable, NumericItem, _c, page_header
from crapcleaner.utils.format import (
    format_size,
)


class DockerView(QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._theme = "dark"
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)
        layout.addWidget(
            page_header(
                "Docker & WSL2 Storage",
                "Inspect Docker daemon storage and WSL virtual disks safely with confirmed prune actions.",
            )
        )

        toolbar = QHBoxLayout()
        self.df_button = QPushButton("Refresh Docker Usage (docker system df)")
        self.df_button.setProperty("primary", "true")
        self.df_button.setIcon(material_icon("refresh", "#ffffff"))
        self.df_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.df_button.clicked.connect(self._main.refresh_docker)
        toolbar.addWidget(self.df_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        output_card = QFrame()
        output_card.setProperty("card", "true")
        output_lay = QVBoxLayout(output_card)
        output_lay.setContentsMargins(14, 12, 14, 12)
        self.output = QLabel("Click 'Refresh Docker Usage' to inspect daemon state.")
        self.output.setWordWrap(True)
        self.output.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.output.setStyleSheet("font-family: 'Consolas', monospace; font-size: 12px;")
        output_lay.addWidget(self.output)
        layout.addWidget(output_card)

        wsl_header = QHBoxLayout()
        wsl_lbl = QLabel("WSL2 / Docker Virtual Disks (ext4.vhdx)")
        wsl_lbl.setStyleSheet("font-weight: 700;")
        wsl_header.addWidget(wsl_lbl)
        wsl_header.addStretch(1)

        copy_cmd_btn = QPushButton("Copy WSL Compact Command")
        copy_cmd_btn.setProperty("ghost", "true")
        copy_cmd_btn.setIcon(material_icon("code", _c(self._theme, "text")))
        copy_cmd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_cmd_btn.setToolTip("Copies the command to compact WSL virtual disks")
        copy_cmd_btn.clicked.connect(
            lambda: QApplication.clipboard().setText(
                "wsl --shutdown && wsl --manage <distro> --compact"
            )
        )
        wsl_header.addWidget(copy_cmd_btn)
        layout.addLayout(wsl_header)

        table_card = QFrame()
        table_card.setProperty("card", "true")
        table_lay = QVBoxLayout(table_card)
        table_lay.setContentsMargins(8, 8, 8, 8)
        self.wsl_table = CrapTable(0, 2)
        self.wsl_table.setAccessibleName("WSL distributions")
        self.wsl_table.setHorizontalHeaderLabels(
            ["Virtual Disk File (.vhdx)", "Allocated Disk Size"]
        )
        self.wsl_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.wsl_table.set_empty_text(self._theme, "No WSL virtual disks detected.")
        table_lay.addWidget(self.wsl_table)
        layout.addWidget(table_card, 1)

        prune_row = QHBoxLayout()
        prune_row.setSpacing(8)
        self.prune_system_button = QPushButton("docker system prune")
        self.prune_system_button.setIcon(material_icon("clean", _c(self._theme, "text")))
        self.prune_system_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prune_system_button.clicked.connect(lambda: self._prune("docker_system_prune"))
        self.prune_builder_button = QPushButton("docker builder prune")
        self.prune_builder_button.setIcon(material_icon("clean", _c(self._theme, "text")))
        self.prune_builder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prune_builder_button.clicked.connect(lambda: self._prune("docker_builder_prune"))
        prune_row.addWidget(self.prune_system_button)
        prune_row.addWidget(self.prune_builder_button)
        prune_row.addStretch(1)
        layout.addLayout(prune_row)

    def _prune(self, action_name):
        dialog = ConfirmDeleteDialog(
            "Confirm Docker Prune",
            f"Run '{action_name.replace('_', ' ')}'? "
            "This removes stopped containers and unused build caches. Volumes are NOT deleted.",
            confirm_label="Run Prune",
        )
        if dialog.exec() == ConfirmDeleteDialog.DialogCode.Accepted:
            self._main.run_docker_prune(action_name)

    def show_docker_info(self, info):
        if not info.available:
            self.output.setText(
                "Docker is not available on this system (Docker CLI not detected in PATH)."
            )
        else:
            text = f"Docker Engine {info.version or ''}\n\n"
            if info.df_raw:
                text += info.df_raw
            if info.total_reclaimable:
                text += f"\n\nTotal reclaimable space: {format_size(info.total_reclaimable)}"
            self.output.setText(text)

    def show_wsl_report(self, rows):
        self.wsl_table.setSortingEnabled(False)
        self.wsl_table.setRowCount(0)
        for row_data in rows:
            row = self.wsl_table.rowCount()
            self.wsl_table.insertRow(row)
            self.wsl_table.setItem(row, 0, QTableWidgetItem(row_data["path"]))
            self.wsl_table.setItem(
                row, 1, NumericItem(format_size(row_data["size"]), row_data["size"])
            )
        self.wsl_table.setSortingEnabled(True)
        self.wsl_table.refresh_placeholder()
        self.wsl_table.resizeColumnToContents(1)

    def apply_theme(self, theme: str):
        self._theme = theme
        self.wsl_table.set_empty_text(theme, "No WSL virtual disks detected.")
