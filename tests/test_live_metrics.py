"""Tests for real-time system metrics engine."""

import time

from crapcleaner.system.live_metrics import (
    CpuVitals,
    LiveMetricsCollector,
    NetworkVitals,
    RamVitals,
    SystemLiveSnapshot,
    sample_live_metrics,
)


def test_sample_live_metrics_returns_valid_snapshot():
    snap = sample_live_metrics()
    assert isinstance(snap, SystemLiveSnapshot)
    assert isinstance(snap.network, NetworkVitals)
    assert isinstance(snap.cpu, CpuVitals)
    assert isinstance(snap.ram, RamVitals)
    assert snap.timestamp > 0


def test_ram_vitals_calculations():
    vitals = RamVitals(
        used_bytes=8 * 1024 * 1024 * 1024,
        total_bytes=16 * 1024 * 1024 * 1024,
        available_bytes=8 * 1024 * 1024 * 1024,
        percent_used=50.0,
        pressure="normal",
    )
    assert "8.0 GB" in vitals.used_str
    assert "16.0 GB" in vitals.total_str
    assert "8.0 GB / 16.0 GB" in vitals.fraction_str


def test_network_vitals_formatting():
    net = NetworkVitals(
        bytes_in_sec=1024 * 1024 * 2.5,
        bytes_out_sec=1024 * 512,
        total_in_bytes=1024 * 1024 * 100,
        total_out_bytes=1024 * 1024 * 20,
        interface_name="Wi-Fi",
        is_connected=True,
    )
    assert "2.5 MB/s" in net.in_rate_str
    assert "512.0 KB/s" in net.out_rate_str
    assert "100.0 MB" in net.total_in_str
    assert "20.0 MB" in net.total_out_str


def test_collector_consecutive_sampling_delta():
    collector = LiveMetricsCollector()
    snap1 = collector.sample()
    time.sleep(0.05)
    snap2 = collector.sample()
    assert snap2.timestamp >= snap1.timestamp
    assert snap2.cpu.percent_used >= 0.0
    assert snap2.cpu.percent_used <= 100.0
    assert snap2.ram.total_bytes >= 0


def test_gpu_vitals_calculations():
    from crapcleaner.system.live_metrics import GpuVitals

    gpu = GpuVitals(
        available=True,
        name="RTX 4090",
        temperature_c=54,
        utilization_pct=42.0,
        vram_used_bytes=8 * 1024 * 1024 * 1024,
        vram_total_bytes=24 * 1024 * 1024 * 1024,
        thermal_status="optimal",
    )
    assert gpu.temp_str == "54°C"
    assert "8.0 GB" in gpu.vram_used_str
    assert "24.0 GB" in gpu.vram_total_str
    assert gpu.vram_percent == 33.3


def test_dashboard_view_vitals_widgets(app):
    from crapcleaner.gui.views import DashboardView

    class FakeMain:
        def start_scan(self):
            pass

        def review_and_clean(self):
            pass

        def navigate(self, page):
            pass

    dashboard = DashboardView(FakeMain())
    dashboard.show()
    dashboard._update_live_vitals()
    assert hasattr(dashboard, "ram_val")
    assert hasattr(dashboard, "cpu_val")
    assert hasattr(dashboard, "gpu_val")
    assert hasattr(dashboard, "gpu_badge")
    assert hasattr(dashboard, "net_in_label")
    assert hasattr(dashboard, "net_out_label")
    assert dashboard.ram_val.text() != "-- / --"
    dashboard.apply_theme("oled")
    dashboard.close()
