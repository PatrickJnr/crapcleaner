"""Unit tests for the platform-neutral Service Manager and both of its backends."""

import json
from contextlib import contextmanager
from unittest.mock import patch

from crapcleaner.system.backends import services_linux, services_windows
from crapcleaner.system.backends.services_windows import (
    CRITICAL_SERVICES,
    _parse_start_mode,
)
from crapcleaner.system.backends.services_windows import _parse_state as _parse_service_state
from crapcleaner.system.services import (
    ServiceItem,
    clear_services_cache,
    get_services_report,
    is_available,
    is_critical_service,
    restart_service,
    set_service_startup_type,
    start_service,
    startup_types,
    stop_service,
)


@contextmanager
def force_platform(name: str):
    """Pin the capability registry to one operating system."""
    with patch("crapcleaner.system.capabilities.is_windows", return_value=name == "windows"):
        with patch("crapcleaner.system.capabilities.is_linux", return_value=name == "linux"):
            # Patch the registry's own tool probe, not shutil.which - the backends share
            # that module and would otherwise clobber each other's patches.
            with patch("crapcleaner.system.capabilities._has", return_value=True):
                clear_services_cache()
                yield
                clear_services_cache()


# ---------------------------------------------------------------------------
# Shared model
# ---------------------------------------------------------------------------


def test_service_item_to_dict():
    item = ServiceItem(
        name="wuauserv",
        display_name="Windows Update",
        status="Running",
        startup_type="Manual",
        description="Enables detection and installation of updates.",
        account="LocalSystem",
        pid=1234,
        is_system=True,
        can_stop=True,
    )
    d = item.to_dict()
    assert d["name"] == "wuauserv"
    assert d["status"] == "Running"
    assert d["startup_type"] == "Manual"
    assert d["pid"] == 1234
    assert d["scope"] == "system"


# ---------------------------------------------------------------------------
# Windows backend
# ---------------------------------------------------------------------------


def test_critical_services_detection_windows():
    with force_platform("windows"):
        assert is_critical_service("RPCSS") is True
        assert is_critical_service("dcomlaunch") is True
        assert is_critical_service("wuauserv") is False
        assert is_critical_service("Spooler") is False
    assert "rpcss" in CRITICAL_SERVICES


def test_parse_start_mode_and_state():
    assert _parse_start_mode("Auto", delayed=False) == "Automatic"
    assert _parse_start_mode("Auto", delayed=True) == "Automatic (Delayed Start)"
    assert _parse_start_mode("Manual") == "Manual"
    assert _parse_start_mode("Disabled") == "Disabled"

    assert _parse_service_state("Running") == "Running"
    assert _parse_service_state("Stopped") == "Stopped"
    assert _parse_service_state("Paused") == "Paused"


def test_get_services_report_windows():
    sample = [
        {
            "Name": "Spooler",
            "DisplayName": "Print Spooler",
            "State": "Running",
            "StartMode": "Auto",
            "DelayedAutoStart": False,
            "Description": "Spools print jobs.",
            "StartName": "LocalSystem",
            "ProcessId": 2400,
        },
        {
            "Name": "CustomAppSvc",
            "DisplayName": "Custom Application Service",
            "State": "Stopped",
            "StartMode": "Manual",
            "DelayedAutoStart": False,
            "Description": "Custom helper.",
            "StartName": "NT AUTHORITY\\NetworkService",
            "ProcessId": 0,
        },
    ]
    with force_platform("windows"):
        with patch.object(
            services_windows,
            "run_command",
            return_value={"stdout": json.dumps(sample), "returncode": 0},
        ):
            services = get_services_report(force_refresh=True)

    s_map = {s.name: s for s in services}
    assert len(services) == 2
    assert s_map["Spooler"].status == "Running"
    assert s_map["Spooler"].startup_type == "Automatic"
    assert s_map["Spooler"].pid == 2400
    assert s_map["CustomAppSvc"].status == "Stopped"
    assert s_map["CustomAppSvc"].pid is None


def test_service_control_validation():
    with force_platform("windows"):
        assert start_service("")[0] is False
        assert stop_service("")[0] is False
        assert restart_service("")[0] is False
        assert set_service_startup_type("", "Automatic")[0] is False

        ok, msg = stop_service("RPCSS")
        assert ok is False
        assert "critical" in msg.lower()

        ok, msg = set_service_startup_type("RPCSS", "Disabled")
        assert ok is False
        assert "critical" in msg.lower()


def test_service_control_admin_check():
    with force_platform("windows"):
        with patch.object(services_windows, "is_admin", return_value=False):
            assert "Administrator" in start_service("Spooler")[1]
            assert "Administrator" in stop_service("Spooler")[1]
            assert "Administrator" in restart_service("Spooler")[1]
            assert "Administrator" in set_service_startup_type("Spooler", "Disabled")[1]


def test_service_control_success_windows():
    with force_platform("windows"):
        with patch.object(services_windows, "is_admin", return_value=True):
            with patch.object(
                services_windows, "run_command", return_value={"returncode": 0, "stdout": ""}
            ):
                assert start_service("Spooler")[0] is True
                assert stop_service("Spooler")[0] is True
                assert restart_service("Spooler")[0] is True
                ok, msg = set_service_startup_type("Spooler", "Disabled")
                assert ok is True
                assert "Disabled" in msg


def test_windows_startup_types_exposed():
    with force_platform("windows"):
        assert "Automatic" in startup_types()
        assert "Disabled" in startup_types()


# ---------------------------------------------------------------------------
# Linux backend
# ---------------------------------------------------------------------------

_UNITS_SAMPLE = (
    "ssh.service           loaded active   running OpenBSD Secure Shell server\n"
    "cups.service          loaded inactive dead    CUPS Scheduler\n"
    "dbus.service          loaded active   running D-Bus System Message Bus\n"
    "cron.service          loaded failed   failed  Regular background program processing\n"
)

_UNIT_FILES_SAMPLE = (
    "ssh.service     enabled\n"
    "cups.service    disabled\n"
    "dbus.service    static\n"
    "cron.service    masked\n"
)


def _linux_run_command(args, timeout=0.0, **kwargs):
    joined = " ".join(args)
    if "--user" in args:
        return {"returncode": 1, "stdout": "", "stderr": "no user manager"}
    if "list-unit-files" in joined:
        return {"returncode": 0, "stdout": _UNIT_FILES_SAMPLE, "stderr": ""}
    if "list-units" in joined:
        return {"returncode": 0, "stdout": _UNITS_SAMPLE, "stderr": ""}
    return {"returncode": 0, "stdout": "", "stderr": ""}


def test_get_services_report_linux():
    with force_platform("linux"):
        with patch.object(services_linux, "run_command", side_effect=_linux_run_command):
            services = get_services_report(force_refresh=True)

    s_map = {s.name: s for s in services}
    assert set(s_map) == {"ssh", "cups", "dbus", "cron"}
    assert s_map["ssh"].status == "Running"
    assert s_map["ssh"].startup_type == "Automatic"
    assert s_map["cups"].status == "Stopped"
    assert s_map["cups"].startup_type == "Manual"
    assert s_map["cron"].status == "Failed"
    assert s_map["cron"].startup_type == "Disabled"
    assert s_map["dbus"].startup_type == "Static"
    assert s_map["dbus"].can_stop is False  # critical unit
    assert all(s.scope == "system" for s in services)


def test_linux_critical_units_protected():
    with force_platform("linux"):
        assert is_critical_service("dbus") is True
        assert is_critical_service("systemd-logind.service") is True
        assert is_critical_service("getty@tty1") is True
        assert is_critical_service("cups") is False

        ok, msg = stop_service("dbus")
        assert ok is False
        assert "critical" in msg.lower()


def test_linux_startup_type_maps_to_systemctl_verbs():
    assert services_linux.normalize_startup_type("Automatic") == ("Automatic", "enable")
    assert services_linux.normalize_startup_type("Manual") == ("Manual", "disable")
    assert services_linux.normalize_startup_type("Disabled") == ("Disabled", "mask")


def test_linux_actions_target_the_unit():
    calls: list[list[str]] = []

    def record(args, timeout=0.0, **kwargs):
        calls.append(args)
        return {"returncode": 0, "stdout": "", "stderr": ""}

    with force_platform("linux"):
        with patch.object(services_linux, "run_command", side_effect=record):
            with patch.object(services_linux.os, "geteuid", return_value=0, create=True):
                ok, msg = start_service("cups")

    assert ok is True
    assert any("cups.service" in " ".join(c) and "start" in c for c in calls)


def test_linux_reports_missing_elevation_helper():
    with force_platform("linux"):
        with patch.object(services_linux.shutil, "which", return_value=None):
            with patch.object(services_linux.os, "geteuid", return_value=1000, create=True):
                ok, msg = stop_service("cups")

    assert ok is False
    assert "pkexec" in msg or "root" in msg.lower()


# ---------------------------------------------------------------------------
# Unsupported platform
# ---------------------------------------------------------------------------


def test_unsupported_platform_refuses_gracefully():
    with patch("crapcleaner.system.capabilities.is_windows", return_value=False):
        with patch("crapcleaner.system.capabilities.is_linux", return_value=False):
            clear_services_cache()
            assert is_available() is False
            assert get_services_report(force_refresh=True) == []
            ok, msg = start_service("anything")
            assert ok is False
            assert "not available" in msg.lower()
            assert startup_types() == ()
            clear_services_cache()


def test_linux_without_systemd_is_unsupported():
    with patch("crapcleaner.system.capabilities.is_windows", return_value=False):
        with patch("crapcleaner.system.capabilities.is_linux", return_value=True):
            with patch("crapcleaner.system.capabilities._has", return_value=False):
                clear_services_cache()
                assert is_available() is False
                ok, msg = start_service("cups")
                assert ok is False
                assert "systemd" in msg.lower()
                clear_services_cache()
