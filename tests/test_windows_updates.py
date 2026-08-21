"""Unit tests for the platform-neutral System Update Manager and both of its backends.

Also covers the deprecated `crapcleaner.system.windows_updates` aliases, which existing
callers still import.
"""

import json
from contextlib import contextmanager
from unittest.mock import patch

from crapcleaner.system import package_managers
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
    if "GetTotalHistoryCount" in cmd_str:
        return {
            "stdout": json.dumps({"RebootRequired": True, "Failures": []}),
            "returncode": 0,
        }
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
    assert "Update Server Not Configured" in report.error
    assert "WUServer" in report.error


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


_APT_DRY_RUN = (
    "Reading package lists...\n"
    "Inst linux-image-generic [6.8.0-31] (6.8.0-40 Ubuntu:24.04/noble-security [amd64])\n"
    "Inst curl [8.5.0-2] (8.5.0-2ubuntu10.1 Ubuntu:24.04/noble-updates [amd64])\n"
    "Conf curl (8.5.0-2ubuntu10.1 Ubuntu:24.04/noble-updates [amd64])\n"
)


def test_check_updates_linux_apt():
    # The apt query itself lives in package_managers; both update views share it.
    with force_platform("linux"):
        with patch.object(
            updates_linux.shutil,
            "which",
            side_effect=lambda t: "/usr/bin/apt-get" if t == "apt-get" else None,
        ):
            with patch.object(package_managers, "_run", return_value=(0, _APT_DRY_RUN, "")):
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


def test_offline_mode_skips_the_windows_update_scan():
    """FEAT-15: the COM search reaches Microsoft, so offline mode must not run it."""
    commands: list[list[str]] = []

    def record(args, **_kwargs):
        commands.append(list(args))
        return {"stdout": "", "returncode": 0}

    with force_platform("windows"):
        with patch.object(updates_windows, "offline_mode", return_value=True):
            with patch.object(updates_windows, "run_command", side_effect=record):
                report = check_system_updates(include_history=False)

    assert report.available_updates == []
    assert "offline mode" in (report.error or "")
    assert not any("Microsoft.Update.Session" in " ".join(c) for c in commands)


def test_offline_mode_skips_the_linux_update_check():
    def explode(*_args, **_kwargs):
        raise AssertionError("offline mode must not query a package repository")

    with force_platform("linux"):
        with patch.object(
            updates_linux.shutil,
            "which",
            side_effect=lambda t: "/usr/bin/apt-get" if t == "apt-get" else None,
        ):
            with patch.object(updates_linux, "offline_mode", return_value=True):
                with patch.object(package_managers, "_run", explode):
                    with patch.object(updates_linux.os.path, "isfile", return_value=False):
                        with patch.object(updates_linux.os.path, "exists", return_value=False):
                            report = check_system_updates(include_history=False)

    assert report.available_updates == []
    assert "offline mode" in (report.error or "")


def test_opening_the_linux_update_gui_does_not_wait_for_it():
    """XP-05: run_command waited, timed out, killed the GUI, then claimed success."""
    launched: list[list[str]] = []

    def explode(*_args, **_kwargs):
        raise AssertionError("a GUI launch must not be waited on")

    with patch.object(
        updates_linux.shutil,
        "which",
        side_effect=lambda t: "/usr/bin/gnome-software" if t == "gnome-software" else None,
    ):
        with patch.object(updates_linux, "run_command", explode):
            with patch.object(
                updates_linux.subprocess, "Popen", side_effect=lambda a, **_k: launched.append(a)
            ):
                ok, message = updates_linux.open_settings()

    assert ok is True
    assert launched == [["gnome-software"]]
    assert "gnome-software" in message


def test_a_failed_gui_launch_is_not_reported_as_success():
    with patch.object(
        updates_linux.shutil,
        "which",
        side_effect=lambda t: "/usr/bin/gnome-software" if t == "gnome-software" else None,
    ):
        with patch.object(updates_linux.subprocess, "Popen", side_effect=OSError("denied")):
            ok, message = updates_linux.open_settings()

    assert ok is False
    assert "denied" in message


def test_the_search_sweeps_every_registered_update_service():
    """Windows Update Settings aggregates all services, so one empty default is not "none"."""
    ps = updates_windows._PS_FIND_PENDING
    assert "Microsoft.Update.ServiceManager" in ps
    assert "$Alt.ServiceID = $svc.ServiceID" in ps
    assert "$Alt.ServerSelection = 3" in ps
    # Only swept when the default service came back with nothing, to keep the common
    # case down to a single network scan.
    assert "if ($Found.Count -eq 0) {" in ps


def test_check_and_install_search_for_the_same_updates():
    """A divergence here means the app lists updates that Install then refuses to see."""
    assert updates_windows._PS_FIND_PENDING in updates_windows._PS_QUERY_UPDATES
    assert updates_windows._PS_FIND_PENDING in updates_windows._PS_INSTALL
    assert (
        "$SearchResult.Updates"
        not in updates_windows._PS_INSTALL.split(updates_windows._PS_FIND_PENDING)[1]
    )


def _state_stdout(payload):
    return {"stdout": json.dumps(payload), "returncode": 0}


def test_a_pending_reboot_is_carried_into_the_report():
    report = SystemUpdateReport(backend="Windows Update")
    with patch.object(
        updates_windows,
        "run_command",
        return_value=_state_stdout({"RebootRequired": True, "Failures": []}),
    ):
        updates_windows._collect_state(report)

    assert report.reboot_required is True
    assert report.error is None


def _pending(title):
    return SystemUpdateItem(
        id=title,
        title=title,
        kb_numbers=[],
        description="",
        size_bytes=0,
        categories=[],
        severity="Important",
        is_downloaded=False,
        is_mandatory=False,
        support_url="",
    )


def test_a_failed_attempt_on_a_still_pending_update_is_reported():
    """A pending update whose last attempt failed is the one case worth surfacing."""
    title = "2026-08 .NET 10.0.11 Security Update (KB5122106)"
    report = SystemUpdateReport(backend="Windows Update", available_updates=[_pending(title)])
    with patch.object(
        updates_windows,
        "run_command",
        return_value=_state_stdout(
            {
                "RebootRequired": False,
                "Failures": [{"Title": title, "Code": "0x80240034"}],
            }
        ),
    ):
        updates_windows._collect_state(report)

    assert report.error is not None
    assert "KB5122106" in report.error
    assert "0x80240034" in report.error
    assert report.available_updates[0].status == "Failed"


def test_a_failure_for_an_already_installed_update_is_ignored():
    """Windows retries the download of updates it already installed; that is not a fault."""
    report = SystemUpdateReport(backend="Windows Update")
    with patch.object(
        updates_windows,
        "run_command",
        return_value=_state_stdout(
            {
                "RebootRequired": False,
                "Failures": [
                    {"Title": "2026-08 Security Update (KB5121003)", "Code": "0x80240034"}
                ],
            }
        ),
    ):
        updates_windows._collect_state(report)

    assert report.error is None


def test_differing_failure_codes_are_not_explained_as_one():
    report = SystemUpdateReport(
        backend="Windows Update",
        available_updates=[_pending("Update A"), _pending("Update B")],
    )
    with patch.object(
        updates_windows,
        "run_command",
        return_value=_state_stdout(
            {
                "RebootRequired": False,
                "Failures": [
                    {"Title": "Update A", "Code": "0x80240034"},
                    {"Title": "Update B", "Code": "0x80246002"},
                ],
            }
        ),
    ):
        updates_windows._collect_state(report)

    assert "Update A" in report.error
    assert "Update B" in report.error
    assert "0x80240034" not in report.error


def test_a_scan_error_is_not_overwritten_by_install_history():
    """The reason the scan failed matters more than what failed to install last week."""
    report = SystemUpdateReport(backend="Windows Update", error="Scan failed")
    with patch.object(
        updates_windows,
        "run_command",
        return_value=_state_stdout(
            {"RebootRequired": True, "Failures": [{"Title": "X", "Code": "0x80240034"}]}
        ),
    ):
        updates_windows._collect_state(report)

    assert report.error == "Scan failed"
    assert report.reboot_required is True


def test_unreadable_state_output_leaves_the_report_untouched():
    report = SystemUpdateReport(backend="Windows Update")
    for payload in ({"stdout": "ERROR:boom", "returncode": 1}, {"stdout": "", "returncode": 0}):
        with patch.object(updates_windows, "run_command", return_value=payload):
            updates_windows._collect_state(report)

    assert report.reboot_required is False
    assert report.error is None
