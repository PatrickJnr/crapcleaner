"""Tests for System Specs inspector, About view, and avatar rendering."""

import json
import time

from crapcleaner.cli import run
from crapcleaner.system.hardware import (
    CpuSpec,
    DriveSpec,
    GpuSpec,
    MemorySpec,
    MotherboardSpec,
    NetworkSpec,
    OsSpec,
    SystemSpecs,
    get_system_specs,
    print_specs_summary,
)


def test_system_specs_data_model():
    specs = SystemSpecs(
        os=OsSpec(
            name="Windows 11 Pro",
            version="10.0.22631",
            architecture="x64",
            uptime="2d 4h",
        ),
        cpu=CpuSpec(
            name="AMD Ryzen 9 7950X",
            cores_physical=16,
            cores_logical=32,
            max_clock_speed_mhz=4500,
        ),
        memory=MemorySpec(
            total_bytes=34359738368,
            available_bytes=17179869184,
            used_bytes=17179869184,
            percent_used=50.0,
        ),
        gpus=[
            GpuSpec(
                name="NVIDIA GeForce RTX 4090",
                driver_version="551.86",
                adapter_ram_bytes=25769803776,
                resolution="3840x2160",
            )
        ],
        drives=[
            DriveSpec(
                drive="C",
                label="System",
                file_system="NTFS",
                total_bytes=1000000000000,
                free_bytes=400000000000,
                used_bytes=600000000000,
                percent_used=60,
            )
        ],
        motherboard=MotherboardSpec(
            manufacturer="ASUS",
            product="ROG CROSSHAIR X670E",
            bios_version="1807",
            bios_date="12/01/2023",
        ),
        network=[NetworkSpec(adapter_name="Ethernet", ip_address="192.168.1.100")],
    )

    data = specs.to_dict()
    assert data["os"]["name"] == "Windows 11 Pro"
    assert data["cpu"]["cores_physical"] == 16
    assert data["memory"]["percent_used"] == 50.0
    assert len(data["gpus"]) == 1
    assert data["motherboard"]["manufacturer"] == "ASUS"

    json_str = specs.to_json()
    parsed = json.loads(json_str)
    assert parsed["cpu"]["name"] == "AMD Ryzen 9 7950X"


def test_get_system_specs_live():
    specs = get_system_specs()
    assert isinstance(specs, SystemSpecs)
    assert specs.os.name != ""
    assert specs.cpu.cores_logical >= 1
    assert isinstance(specs.drives, list)


def test_print_specs_summary_text(capsys):
    specs = get_system_specs()
    print_specs_summary(specs, json_output=False)
    captured = capsys.readouterr()
    assert "CrapCleaner System Hardware & OS Specifications" in captured.out
    assert "Processor" in captured.out
    assert "Operating System" in captured.out


def test_print_specs_summary_json(capsys):
    specs = get_system_specs()
    print_specs_summary(specs, json_output=True)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "os" in data
    assert "cpu" in data
    assert "memory" in data
    assert "drives" in data


def test_cli_specs_command(capsys):
    ret = run(["--specs"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "CrapCleaner System Hardware & OS Specifications" in captured.out


def test_cli_specs_json(capsys):
    ret = run(["--specs", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "os" in data
    assert "cpu" in data
    assert "memory" in data


def test_gui_about_and_specs_views():
    import os
    from unittest.mock import patch

    from PySide6.QtWidgets import QApplication

    from crapcleaner.gui.views import AboutView, ContributorCard, SpecsView, SquircleAvatarWidget
    from crapcleaner.utils.contributors import ContributorInfo

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    avatar_path = os.path.join(
        os.path.dirname(__file__), "..", "crapcleaner", "assets", "avatar.jpg"
    )
    widget = SquircleAvatarWidget(os.path.abspath(avatar_path), size=100, radius=20)
    assert widget.width() == 100
    assert widget.height() == 100

    sample_contrib = ContributorInfo(
        login="Foxils",
        avatar_url="https://avatar.url",
        html_url="https://github.com/Foxils",
        contributions=12,
    )
    card = ContributorCard(sample_contrib, avatar_file="", theme="dark")
    assert card is not None
    assert card.minimumWidth() == 240
    card.close()
    card.deleteLater()

    class DummyMain:
        def __init__(self):
            pass

    dummy = DummyMain()
    specs_view = SpecsView(dummy)
    specs_view.refresh_specs()
    # refresh_specs() runs on a QThread; pump the event loop until it lands.
    deadline = time.monotonic() + 60
    while specs_view._specs is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.05)
    assert specs_view._specs is not None

    if hasattr(specs_view, "_worker") and specs_view._worker:
        specs_view._worker.wait(5000)

    # Contributors arrive on a worker, so hand the view the data directly instead.
    from crapcleaner.gui.workers import ContributorsWorker

    with patch.object(ContributorsWorker, "start", lambda self: None):
        about_view = AboutView(dummy)
        assert about_view is not None
        about_view._show_contributors([(sample_contrib, "")])
        assert about_view.contrib_grid.count() >= 1

    specs_view.close()
    specs_view.deleteLater()
    about_view.close()
    about_view.deleteLater()
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_a_failed_probe_is_logged_and_still_degrades(monkeypatch):
    """A silent probe failure leaves a specs page with rows missing and no trace."""
    from unittest.mock import patch

    from crapcleaner.system import hardware

    def boom(_drive):
        raise OSError("drive gone")

    monkeypatch.setattr(hardware, "get_drive_info", boom)
    monkeypatch.setattr(hardware, "list_drives", lambda: ["Z:"])

    with patch.object(hardware.logger, "debug") as debug:
        assert hardware._get_drive_specs() == []

    assert debug.called
    assert "drive" in debug.call_args[0][0]


def test_offline_mode_skips_the_hostname_lookup(monkeypatch):
    """FEAT-15: gathering specs must not send a DNS query."""
    from crapcleaner.system import hardware

    lookups: list[str] = []
    monkeypatch.setattr(hardware.socket, "gethostbyname", lambda h: lookups.append(h) or "10.0.0.5")

    monkeypatch.setattr(hardware, "offline_mode", lambda: True)
    assert hardware._get_network_specs()[0].ip_address == "127.0.0.1"
    assert lookups == []

    monkeypatch.setattr(hardware, "offline_mode", lambda: False)
    assert hardware._get_network_specs()[0].ip_address == "10.0.0.5"
    assert lookups
