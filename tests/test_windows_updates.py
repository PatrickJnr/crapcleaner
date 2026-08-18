"""Unit tests for the platform-neutral System Update Manager and both of its backends.

Also covers the deprecated `crapcleaner.system.windows_updates` aliases, which existing
callers still import.
"""

import json
from contextlib import contextmanager
from unittest.mock import patch

from crapcleaner.system.backends import updates_linux, updates_windows
from crapcleaner.system.system_updates import (
    SystemUpdateItem,
    SystemUpdateReport,
    check_system_updates,
    install_system_updates,
    is_available,
)
from crapcleaner.system.windows_updates import (
    WindowsUpdateItem,
    WindowsUpdateReport,
    check_windows_updates,
    ensure_windows_update_service_running,
    install_windows_updates,
    open_windows_update_settings,
)


@contextmanager
def force_platform(name: str, tooling: bool = True):
    """Pin the capability registry to one operating system."""
    with patch("crapcleaner.system.capabilities.is_windows", return_value=name == "windows"):
        with patch("crapcleaner.system.capabilities.is_linux", return_value=name == "linux"):
            with patch("crapcleaner.system.capabilities._has", return_value=tooling):
                yield


# ---------------------------------------------------------------------------
# Shared model
# ---------------------------------------------------------------------------


def test_windows_update_item_to_dict():
    item = WindowsUpdateItem(
        id="KB5041585",
        title="2026-08 Cumulative Update for Windows 11",
        kb_numbers=["KB5041585"],
        description="Security and quality improvements.",
        size_bytes=524288000,
        categories=["Security Updates", "Windows 11"],
        severity="Critical",
        is_downloaded=True,
        is_mandatory=True,
        support_url="https://support.microsoft.com/kb/5041585",
        status="Downloaded",
    )
    d = item.to_dict()
    assert d["id"] == "KB5041585"
    assert d["kb_numbers"] == ["KB5041585"]
    assert d["severity"] == "Critical"
    assert d["is_mandatory"] is True


def test_windows_update_report_to_dict():
    rep = WindowsUpdateReport(
        available_updates=[
            SystemUpdateItem(
                id="KB123456",
                title="Test Update",
                kb_numbers=["KB123456"],
                description="",
                size_bytes=1024,
                categories=["Security"],
                severity="Important",
                is_downloaded=False,
                is_mandatory=False,
                support_url="",
            )
        ],
        service_status="Running",
    )
    d = rep.to_dict()
    assert len(d["available_updates"]) == 1
    assert d["service_status"] == "Running"
    assert d["error"] is None
    assert d["reboot_required"] is False


def test_deprecated_aliases_point_at_the_shared_model():
    assert WindowsUpdateItem is SystemUpdateItem
    assert WindowsUpdateReport is SystemUpdateReport


# ---------------------------------------------------------------------------
# Windows backend
# ---------------------------------------------------------------------------

_SAMPLE_AVAILABLE = [
    {
        "Id": "update-guid-1",
        "Title": "Security Update for Windows (KB5001234)",
        "KB": "5001234",
        "Description": "Fixes critical vulnerability.",
        "Size": 204800000,
        "IsDownloaded": False,
        "IsMandatory": True,
        "Severity": "Critical",
        "Categories": "Security Updates, Windows 11",
        "SupportUrl": "https://support.microsoft.com",
    }
]

_SAMPLE_HISTORY = [
    {
        "HotFixID": "KB5005678",
        "Description": "Update",
        "InstalledOn": "2026-08-10",
        "InstalledBy": "NT AUTHORITY\\SYSTEM",
    }
]


def _fake_windows_run(args, timeout=30.0, **kwargs):
    cmd_str = " ".join(args)
    if "sc.exe" in cmd_str:
        return {"stdout": "STATE : 4 RUNNING", "returncode": 0}
    if "Microsoft.Update.Session" in cmd_str:
        return {"stdout": json.dumps(_SAMPLE_AVAILABLE), "returncode": 0}
    if "Get-HotFix" in cmd_str:
        return {"stdout": json.dumps(_SAMPLE_HISTORY), "returncode": 0}
    return {"stdout": "", "returncode": 0}


def test_check_updates_windows():
    with force_platform("windows"):
        with patch.object(updates_windows, "run_command", side_effect=_fake_windows_run):
            report = check_system_updates(include_history=True)

    assert report.backend == "Windows Update"
    assert report.service_status == "Running"
    assert len(report.available_updates) == 1
    assert report.available_updates[0].id == "update-guid-1"
    assert report.available_updates[0].severity == "Critical"
    assert "KB5001234" in report.available_updates[0].kb_numbers
    assert len(report.installed_history) == 1
    assert report.installed_history[0].id == "KB5005678"


def test_check_updates_windows_error_handling():
    with force_platform("windows"):
        with patch.object(
            updates_windows,
            "run_command",
            return_value={
                "stdout": "ERROR:Windows Update COM server is not registered.",
                "returncode": 1,
            },
        ):
            report = check_windows_updates(include_history=False)

    assert report.error is not None
    assert "Windows Update COM server" in report.error


def test_check_updates_windows_hresult_explanation():
    with force_platform("windows"):
        with patch.object(
            updates_windows,
            "run_command",
            return_value={"stdout": "ERROR:Exception from HRESULT: 0x80244011", "returncode": 1},
        ):
            report = check_windows_updates(include_history=False)

    assert report.error is not None
    assert "0x80244011" in report.error
    assert "Update Server Connection Failure" in report.error
    assert "SOAP" in report.error


def test_install_updates_windows_elevation_check():
    with force_platform("windows"):
        with patch.object(updates_windows, "is_admin", return_value=False):
            ok, msg = install_windows_updates()
    assert ok is False
    assert "Administrator" in msg


def test_install_updates_windows_success():
    with force_platform("windows"):
        with patch.object(updates_windows, "is_admin", return_value=True):
            with patch.object(
                updates_windows,
                "run_command",
                return_value={"stdout": "RESULT:2:False", "returncode": 0},
            ):
                ok, msg = install_system_updates()
    assert ok is True
    assert "installation finished" in msg.lower()


def test_ensure_update_service_running_windows():
    with force_platform("windows"):
        with patch.object(updates_windows, "is_admin", return_value=True):
            with patch.object(
                updates_windows,
                "run_command",
                return_value={
                    "stdout": "The Windows Update service was started successfully.",
                    "returncode": 0,
                },
            ):
                ok, msg = ensure_windows_update_service_running()
    assert ok is True
    assert "running" in msg.lower()


def test_open_windows_update_settings():
    with force_platform("windows"):
        with patch("os.startfile", return_value=None, create=True):
            assert open_windows_update_settings() is True


# ---------------------------------------------------------------------------
# Linux backend
# ---------------------------------------------------------------------------

_APT_DRY_RUN = (
    "Reading package lists...\n"
    "Inst linux-image-generic [6.8.0-31] (6.8.0-40 Ubuntu:24.04/noble-security [amd64])\n"
    "Inst curl [8.5.0-2] (8.5.0-2ubuntu10.1 Ubuntu:24.04/noble-updates [amd64])\n"
    "Conf curl (8.5.0-2ubuntu10.1 Ubuntu:24.04/noble-updates [amd64])\n"
)


def test_check_updates_linux_apt():
    with force_platform("linux"):
        with patch.object(
            updates_linux.shutil,
            "which",
            side_effect=lambda t: "/usr/bin/apt-get" if t == "apt-get" else None,
        ):
            with patch.object(
                updates_linux, "run_command", return_value={"stdout": _APT_DRY_RUN, "returncode": 0}
            ):
                with patch.object(updates_linux.os.path, "isfile", return_value=False):
                    with patch.object(updates_linux.os.path, "exists", return_value=False):
                        report = check_system_updates(include_history=True)

    assert report.backend == "apt-get"
    titles = {u.id: u for u in report.available_updates}
    assert set(titles) == {"linux-image-generic", "curl"}
    # noble-security marks the kernel update as a security fix.
    assert titles["linux-image-generic"].severity == "Critical"
    assert titles["linux-image-generic"].is_mandatory is True
    assert titles["curl"].severity == "Moderate"
    assert titles["curl"].description == "8.5.0-2 → 8.5.0-2ubuntu10.1"
    assert report.reboot_required is False


def test_check_updates_linux_reboot_marker():
    with force_platform("linux"):
        with patch.object(
            updates_linux.shutil,
            "which",
            side_effect=lambda t: "/usr/bin/apt-get" if t == "apt-get" else None,
        ):
            with patch.object(
                updates_linux, "run_command", return_value={"stdout": "", "returncode": 0}
            ):
                with patch.object(updates_linux.os.path, "isfile", return_value=False):
                    with patch.object(updates_linux.os.path, "exists", return_value=True):
                        report = check_system_updates(include_history=False)

    assert report.reboot_required is True


def test_check_updates_linux_pacman():
    def which(tool):
        return "/usr/bin/pacman" if tool in ("pacman", "checkupdates") else None

    with force_platform("linux"):
        with patch.object(updates_linux.shutil, "which", side_effect=which):
            with patch.object(
                updates_linux,
                "run_command",
                return_value={
                    "stdout": "linux 6.9.1 -> 6.9.2\nvim 9.1.1 -> 9.1.2\n",
                    "returncode": 0,
                },
            ):
                with patch.object(updates_linux.os.path, "isfile", return_value=False):
                    with patch.object(updates_linux.os.path, "exists", return_value=False):
                        report = check_system_updates(include_history=False)

    assert report.backend == "pacman"
    assert {u.id for u in report.available_updates} == {"linux", "vim"}


def test_install_updates_linux_uses_elevation():
    calls: list[list[str]] = []

    def record(args, timeout=0.0, **kwargs):
        calls.append(args)
        return {"returncode": 0, "stdout": "", "stderr": ""}

    def which(tool):
        return f"/usr/bin/{tool}" if tool in ("apt-get", "pkexec") else None

    with force_platform("linux"):
        with patch.object(updates_linux.shutil, "which", side_effect=which):
            with patch.object(updates_linux.os, "geteuid", return_value=1000, create=True):
                with patch.object(updates_linux.os.path, "exists", return_value=False):
                    with patch.object(updates_linux, "run_command", side_effect=record):
                        ok, msg = install_system_updates()

    assert ok is True
    assert calls and calls[0][0] == "pkexec"
    assert "apt-get" in calls[0]


def test_install_updates_linux_without_elevation_helper():
    def which(tool):
        return "/usr/bin/apt-get" if tool == "apt-get" else None

    with force_platform("linux"):
        with patch.object(updates_linux.shutil, "which", side_effect=which):
            with patch.object(updates_linux.os, "geteuid", return_value=1000, create=True):
                ok, msg = install_system_updates()

    assert ok is False
    assert "pkexec" in msg


# ---------------------------------------------------------------------------
# Unsupported platform
# ---------------------------------------------------------------------------


def test_unsupported_platform_refuses_gracefully():
    with force_platform("other"):
        assert is_available() is False
        report = check_system_updates()
        assert report.available_updates == []
        assert report.error is not None
        ok, msg = install_system_updates()
        assert ok is False
        assert "not available" in msg.lower()


def test_linux_without_package_manager_is_unsupported():
    with force_platform("linux", tooling=False):
        assert is_available() is False
        ok, msg = install_system_updates()
        assert ok is False
        assert "package manager" in msg.lower()


def test_windows_only_alias_refuses_on_linux():
    with force_platform("linux"):
        ok, msg = ensure_windows_update_service_running()
    assert ok is False
    assert "Windows" in msg
