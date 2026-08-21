"""Windows Update inspection and installation via the Microsoft.Update COM API.

Driven through PowerShell because the COM automation interface is the only supported
way to search, download, and install updates without going through the Settings UI.
"""

import json
import os
from typing import TYPE_CHECKING

from crapcleaner.config import offline_mode
from crapcleaner.utils.platform import is_admin, run_command
from crapcleaner.utils.windows_errors import explain_windows_error

if TYPE_CHECKING:  # pragma: no cover - typing only
    from crapcleaner.system.system_updates import SystemUpdateReport

_PS = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command"]

#: Shown when Get-HotFix does not record who installed an update.
_DEFAULT_INSTALLER_ACCOUNT = "NT AUTHORITY\\SYSTEM"

OFFLINE_MESSAGE = "Update scan skipped: offline mode is on, so Windows Update was not contacted."

#: Fills $Found with every pending update the machine is offered. Windows Update Settings
#: aggregates offers from all registered services, so an empty result from the default
#: service alone is not the same as having nothing pending.
_PS_FIND_PENDING = (
    "$Session = New-Object -ComObject Microsoft.Update.Session; "
    "$Criteria = 'IsInstalled=0 and IsHidden=0'; "
    "$Found = New-Object System.Collections.ArrayList; "
    "$Seen = @{}; "
    "function Add-Results($col) { "
    "foreach ($u in $col) { "
    "$key = if ($u.Identity) { $u.Identity.UpdateID } else { $u.Title }; "
    "if (-not $Seen.ContainsKey($key)) { $Seen[$key] = $true; [void]$Found.Add($u) } "
    "} "
    "}; "
    "$Searcher = $Session.CreateUpdateSearcher(); "
    "$Searcher.Online = $true; "
    "$SearchResult = $Searcher.Search($Criteria); "
    "Add-Results $SearchResult.Updates; "
    "if ($Found.Count -eq 0) { "
    "$Sm = New-Object -ComObject Microsoft.Update.ServiceManager; "
    "foreach ($svc in $Sm.Services) { "
    "if (-not $svc.OffersWindowsUpdates) { continue }; "
    "try { "
    "$Alt = $Session.CreateUpdateSearcher(); "
    "$Alt.Online = $true; "
    "$Alt.ServerSelection = 3; "
    "$Alt.ServiceID = $svc.ServiceID; "
    "Add-Results $Alt.Search($Criteria).Updates "
    "} catch { } "
    "} "
    "}; "
)

_PS_QUERY_UPDATES = (
    "$ErrorActionPreference = 'Stop'; "
    "try { " + _PS_FIND_PENDING + "$updates = @(); "
    "foreach ($u in $Found) { "
    "$kb = @(); if ($u.KBArticleIDs) { $kb = $u.KBArticleIDs }; "
    "$cats = @(); if ($u.Categories) { foreach ($c in $u.Categories) { $cats += $c.Name } }; "
    "$urls = @(); if ($u.MoreInfoUrls) { $urls = $u.MoreInfoUrls }; "
    "$updates += [PSCustomObject]@{"
    "Id = if ($u.Identity) { $u.Identity.UpdateID } else { '' }; "
    "Title = $u.Title; "
    "KB = ($kb -join ', '); "
    "Description = if ($u.Description) { $u.Description } else { '' }; "
    "Size = $u.MaxDownloadSize; "
    "IsDownloaded = [bool]$u.IsDownloaded; "
    "IsMandatory = [bool]$u.IsMandatory; "
    "Severity = if ($u.MsrcSeverity) { $u.MsrcSeverity } else { 'Unspecified' }; "
    "Categories = ($cats -join ', '); "
    "SupportUrl = ($urls -join ', '); "
    "}; "
    "}; "
    "$updates | ConvertTo-Json -Depth 3 -Compress "
    "} catch { "
    "Write-Output ('ERROR:' + $_.Exception.Message) "
    "}"
)

_PS_QUERY_HISTORY = (
    "try { "
    "Get-HotFix | Select-Object -Property HotFixID, Description, InstalledOn, InstalledBy | "
    "Sort-Object -Property InstalledOn -Descending | "
    "ConvertTo-Json -Depth 2 -Compress "
    "} catch { "
    "Write-Output ('ERROR:' + $_.Exception.Message) "
    "}"
)

#: Reboot state plus recent failed install attempts. A search reports what Windows will
#: offer next, which is not the same as what it last tried and could not complete.
_PS_QUERY_STATE = (
    "try { "
    "$reboot = $false; "
    "try { $reboot = (New-Object -ComObject Microsoft.Update.SystemInfo).RebootRequired } catch { }; "
    "$failures = @(); "
    "try { "
    "$Searcher = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher(); "
    "$total = $Searcher.GetTotalHistoryCount(); "
    "if ($total -gt 0) { "
    "$cutoff = (Get-Date).AddDays(-7); "
    "$seen = @{}; "
    "foreach ($e in $Searcher.QueryHistory(0, [Math]::Min(100, $total))) { "
    # History is newest first, so the first record for a title is its current outcome.
    # An update that failed and was later reinstalled must not count as still failing.
    "if ($seen.ContainsKey($e.Title)) { continue }; "
    "$seen[$e.Title] = $true; "
    "if ($e.ResultCode -ne 4) { continue }; "
    "if ($e.Date -lt $cutoff) { continue }; "
    "$failures += [PSCustomObject]@{"
    "Title = $e.Title; "
    "Date = $e.Date.ToString('s'); "
    "Code = ('0x' + ('{0:X8}' -f $e.HResult)); "
    "} "
    "} "
    "} "
    "} catch { }; "
    "[PSCustomObject]@{ RebootRequired = [bool]$reboot; Failures = @($failures) } | "
    "ConvertTo-Json -Depth 3 -Compress "
    "} catch { "
    "Write-Output ('ERROR:' + $_.Exception.Message) "
    "}"
)

_PS_INSTALL = (
    "$ErrorActionPreference = 'Stop'; "
    "try { " + _PS_FIND_PENDING + "if ($Found.Count -eq 0) { "
    "Write-Output 'NO_UPDATES'; exit 0; "
    "} "
    "$UpdatesToDownload = New-Object -ComObject Microsoft.Update.UpdateColl; "
    "foreach ($u in $Found) { $UpdatesToDownload.Add($u) | Out-Null }; "
    "$Downloader = $Session.CreateUpdateDownloader(); "
    "$Downloader.Updates = $UpdatesToDownload; "
    "$Downloader.Download(); "
    "$UpdatesToInstall = New-Object -ComObject Microsoft.Update.UpdateColl; "
    "foreach ($u in $Found) { if ($u.IsDownloaded) { $UpdatesToInstall.Add($u) | Out-Null } }; "
    "if ($UpdatesToInstall.Count -eq 0) { Write-Output 'DOWNLOAD_FAILED'; exit 0; } "
    "$Installer = $Session.CreateUpdateInstaller(); "
    "$Installer.Updates = $UpdatesToInstall; "
    "$InstallResult = $Installer.Install(); "
    "Write-Output ('RESULT:' + $InstallResult.ResultCode + ':' + $InstallResult.RebootRequired); "
    "} catch { "
    "Write-Output ('ERROR:' + $_.Exception.Message); "
    "}"
)


def service_status() -> str:
    """Whether the Windows Update service (wuauserv) is running."""
    res = run_command(["sc.exe", "query", "wuauserv"], timeout=5.0)
    stdout = str(res.get("stdout", ""))
    if "RUNNING" in stdout:
        return "Running"
    if "STOPPED" in stdout:
        return "Stopped"
    if "PAUSED" in stdout:
        return "Paused"
    return "Unknown"


def _normalise_kb_numbers(kb_str: str) -> list[str]:
    return [
        k.strip() if k.strip().upper().startswith("KB") else f"KB{k.strip()}"
        for k in kb_str.split(",")
        if k.strip()
    ]


def _collect_available(report: "SystemUpdateReport", timeout: float) -> None:
    from crapcleaner.system.system_updates import SystemUpdateItem

    res = run_command(_PS + [_PS_QUERY_UPDATES], timeout=timeout)
    stdout = str(res.get("stdout", "")).strip()

    if stdout.startswith("ERROR:"):
        report.error = explain_windows_error(stdout[6:].strip())
        return
    if not stdout:
        return

    try:
        data = json.loads(stdout)
    except Exception as exc:
        if not report.error:
            report.error = explain_windows_error(f"Failed to parse available updates: {exc}")
        return

    for item in data if isinstance(data, list) else [data]:
        title = str(item.get("Title") or "Windows Update")
        kb_str = str(item.get("KB") or "")
        report.available_updates.append(
            SystemUpdateItem(
                id=str(item.get("Id") or kb_str or title),
                title=title,
                kb_numbers=_normalise_kb_numbers(kb_str),
                description=str(item.get("Description") or ""),
                size_bytes=int(item.get("Size") or 0),
                categories=[
                    c.strip() for c in str(item.get("Categories") or "").split(",") if c.strip()
                ],
                severity=str(item.get("Severity") or "Unspecified"),
                is_downloaded=bool(item.get("IsDownloaded", False)),
                is_mandatory=bool(item.get("IsMandatory", False)),
                support_url=str(item.get("SupportUrl") or ""),
                status="Downloaded" if item.get("IsDownloaded") else "Available",
            )
        )


def _collect_history(report: "SystemUpdateReport") -> None:
    from crapcleaner.system.system_updates import SystemUpdateItem

    res = run_command(_PS + [_PS_QUERY_HISTORY], timeout=15.0)
    stdout = str(res.get("stdout", "")).strip()
    if not stdout or stdout.startswith("ERROR:"):
        return

    try:
        data = json.loads(stdout)
    except Exception:
        return

    for item in data if isinstance(data, list) else [data]:
        hotfix_id = str(item.get("HotFixID") or "")
        if not hotfix_id:
            continue
        desc = str(item.get("Description") or "Hotfix Update")

        installed_on_val = item.get("InstalledOn")
        if isinstance(installed_on_val, dict):
            installed_on = str(
                installed_on_val.get("DateTime") or installed_on_val.get("value") or ""
            )
        else:
            installed_on = str(installed_on_val) if installed_on_val else ""

        # Outside the f-string: a backslash in an f-string expression is a syntax
        # error before Python 3.12, and this project supports 3.10.
        installed_by = item.get("InstalledBy") or _DEFAULT_INSTALLER_ACCOUNT

        report.installed_history.append(
            SystemUpdateItem(
                id=hotfix_id,
                title=f"{hotfix_id} ({desc})",
                kb_numbers=[hotfix_id],
                description=f"Installed by: {installed_by}",
                size_bytes=0,
                categories=[desc],
                severity="Installed",
                is_downloaded=True,
                is_mandatory=False,
                support_url="",
                installed_on=installed_on,
                status="Installed",
            )
        )


def _collect_state(report: "SystemUpdateReport") -> None:
    """Record a pending reboot and any update Windows recently failed to install."""
    res = run_command(_PS + [_PS_QUERY_STATE], timeout=30.0)
    stdout = str(res.get("stdout", "")).strip()
    if not stdout or stdout.startswith("ERROR:"):
        return

    try:
        data = json.loads(stdout)
    except Exception:
        return
    if not isinstance(data, dict):
        return

    report.reboot_required = bool(data.get("RebootRequired", False))

    failures = data.get("Failures") or []
    if isinstance(failures, dict):
        failures = [failures]
    if not failures or report.error:
        return

    # Windows keeps retrying the download of updates it has already installed, so a failed
    # history entry on its own means nothing. Only an update that is *still pending* and
    # whose last attempt failed is worth reporting.
    pending = {u.title: u for u in report.available_updates}
    failures = [f for f in failures if str(f.get("Title") or "") in pending]
    if not failures:
        return

    for failure in failures:
        item = pending[str(failure.get("Title"))]
        item.status = "Failed"
        item.description = (
            f"{item.description}\n" if item.description else ""
        ) + f"Last attempt failed: {explain_windows_error(str(failure.get('Code') or ''))}"

    titles = "; ".join(str(f.get("Title") or "An update") for f in failures[:3])
    if len(failures) > 3:
        titles += f"; and {len(failures) - 3} more"
    codes = {str(f.get("Code") or "") for f in failures}
    detail = explain_windows_error(codes.pop()) if len(codes) == 1 else ""
    report.error = (
        f"Windows could not install {len(failures)} pending update(s): {titles}."
        f"{' ' + detail if detail else ''}"
    )


def check(include_history: bool = True, timeout: float = 180.0) -> "SystemUpdateReport":
    from crapcleaner.system.system_updates import SystemUpdateReport

    report = SystemUpdateReport(backend="Windows Update", service_status=service_status())
    if offline_mode():
        report.error = OFFLINE_MESSAGE
    else:
        _collect_available(report, timeout)
        _collect_state(report)
    if include_history:
        _collect_history(report)
    return report


def install(update_ids: list[str] | None = None) -> tuple[bool, str]:
    if not is_admin():
        return (
            False,
            "Administrator privileges are required to initiate Windows Update installation.",
        )

    result = run_command(_PS + [_PS_INSTALL], timeout=180.0)
    stdout = str(result.get("stdout", "")).strip()

    if "NO_UPDATES" in stdout:
        return True, "No pending updates to install. System is up to date."

    if stdout.startswith("RESULT:"):
        parts = stdout.split(":")
        result_code = parts[1] if len(parts) > 1 else ""
        reboot_req = parts[2] if len(parts) > 2 else "False"
        reboot_msg = (
            " A system reboot is required to complete installation."
            if "true" in reboot_req.lower()
            else ""
        )
        return True, f"Windows Update installation finished (Code {result_code}).{reboot_msg}"

    if stdout.startswith("ERROR:"):
        # The orchestrator can still make progress when the COM session is refused.
        try:
            run_command(["usoclient.exe", "StartInteractiveScan"], timeout=30.0)
            run_command(["usoclient.exe", "StartDownload"], timeout=30.0)
            return True, "Triggered Windows Update background download and installation."
        except Exception:
            return False, explain_windows_error(f"Update installation failed: {stdout[6:].strip()}")

    try:
        run_command(["usoclient.exe", "StartInteractiveScan"], timeout=30.0)
        return True, "Initiated Windows Update scan and download."
    except Exception as exc:
        return False, explain_windows_error(f"Failed to start update client: {exc}")


def open_settings() -> tuple[bool, str]:
    try:
        os.startfile("ms-settings:windowsupdate")
        return True, "Opened Windows Update settings."
    except Exception:
        try:
            run_command(["cmd", "/c", "start", "ms-settings:windowsupdate"], timeout=15.0)
            return True, "Opened Windows Update settings."
        except Exception as exc:
            return False, f"Could not open Windows Update settings: {exc}"


def ensure_service_running() -> tuple[bool, str]:
    """Start the wuauserv service, which the COM search needs."""
    if not is_admin():
        return False, "Administrator elevation required to start Windows services."

    res = run_command(["net", "start", "wuauserv"], timeout=10.0)
    if res.get("returncode") == 0 or "already been started" in str(res.get("stdout", "")).lower():
        return True, "Windows Update service (wuauserv) is running."
    return False, explain_windows_error(
        f"Failed to start Windows Update service: {res.get('stderr') or res.get('stdout')}"
    )
