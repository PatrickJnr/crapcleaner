"""Drive maintenance: fragmentation analysis and volume optimisation, per platform.

Kept apart from :mod:`crapcleaner.system.drives`, which is a read-only inventory, in the
same way memory actions are kept apart from the memory report.

On Windows, analysis goes through ``Win32_Volume.DefragAnalysis`` rather than parsing
``defrag /A``: defrag reports its own failures on stdout while still exiting 0, and its
messages are localised, so neither its exit code nor its text can be trusted.

On Linux the same two actions map onto ``e4defrag -c`` and ``fstrim``, and the scheduled
task maps onto ``fstrim.timer``. Both platforms therefore answer the same three
questions, and the caller does not branch.
"""

import json
import os
import re
import shutil
from typing import Any

from crapcleaner.utils.platform import is_admin, is_windows, run_command

#: Documented Win32_Volume.DefragAnalysis / Defrag return values worth naming.
_RETURN_CODES: dict[int, str] = {
    0: "Success",
    1: "Access denied",
    2: "Volume not found",
    3: "Volume not mounted",
    4: "Not enough free space to complete the operation",
    5: "Corrupt master file table",
    6: "Operation not supported on this volume",
    7: "Operation not supported by this version of Windows",
    8: "Volume is marked dirty and needs chkdsk first",
    9: "Volume is too small to optimise",
    10: "Path not found",
    11: "Volume cannot be optimised by Windows",
    12: "Not enough free space",
}

_LETTER = re.compile(r"^[A-Za-z]$")

#: e4defrag prints this once at the end of a `-c` run.
_FRAG_SCORE = re.compile(r"fragmentation score\s+(\d+)", re.IGNORECASE)

#: Filesystems with a fragmentation checker. The others get an honest refusal rather
#: than a reading borrowed from a tool that does not understand them.
_ANALYSABLE_LINUX_FS = {"ext2", "ext3", "ext4"}


def _elevation_required(action: str) -> str:
    if is_windows():
        return (
            f"Administrator privileges are required to {action}. "
            "Relaunch CrapCleaner as Admin and try again."
        )
    return f"Root privileges are required to {action}. Relaunch CrapCleaner as root and try again."


def _normalise_letter(letter: str) -> str | None:
    """A bare drive letter, or None when the caller passed something unusable.

    The letter is interpolated into a WMI filter and a command line, so anything that is
    not a single letter is refused rather than escaped.
    """
    cleaned = (letter or "").strip().rstrip(":\\/")
    return cleaned.upper() if _LETTER.match(cleaned) else None


def _linux_mount(target: str) -> str | None:
    """The mount point behind `target`, which may already be one or may be a device.

    ``fstrim`` and ``e4defrag`` both act on a mount point, while the inventory names a
    volume by whichever of the two its probe happened to know.
    """
    cleaned = (target or "").strip()
    if not cleaned or "\0" in cleaned or not cleaned.startswith("/"):
        return None
    if os.path.ismount(cleaned):
        return cleaned

    if shutil.which("findmnt"):
        result = run_command(
            ["findmnt", "-n", "-f", "-o", "TARGET", "--source", cleaned], timeout=10.0
        )
        mount = str(result.get("stdout", "")).strip().splitlines()
        if mount and mount[0].startswith("/"):
            return mount[0].strip()
    return cleaned if os.path.isdir(cleaned) else None


def _linux_fs(mount: str) -> str:
    if not shutil.which("findmnt"):
        return ""
    result = run_command(["findmnt", "-n", "-f", "-o", "FSTYPE", "--target", mount], timeout=10.0)
    return str(result.get("stdout", "")).strip().lower()


def optimisation_supported() -> bool:
    """Whether this machine has the tools to analyse or optimise a volume at all.

    A Linux box without ``fstrim`` cannot do either, so the page should not offer them.
    """
    if is_windows():
        return True
    return bool(shutil.which("fstrim") or shutil.which("e4defrag"))


def _describe_return(code: int) -> str:
    return _RETURN_CODES.get(code, f"Windows reported error code {code}")


def analyze_volume(letter: str, timeout: float = 600.0) -> tuple[bool, str, int | None]:
    """Measure fragmentation on one volume.

    Returns ``(ok, message, fragmentation_percent)``. The percentage is None whenever
    Windows did not return a trustworthy reading.
    """
    if not is_windows():
        return _linux_analyze(letter, timeout)

    drive = _normalise_letter(letter)
    if drive is None:
        return False, f"'{letter}' is not a drive letter.", None
    if not is_admin():
        return False, _elevation_required("analyse a drive"), None

    ps_cmd = (
        f"$v = Get-CimInstance -ClassName Win32_Volume -Filter \"DriveLetter='{drive}:'\"; "
        "if (-not $v) { Write-Output 'ERROR:Volume not found'; exit 0 }; "
        "$r = $v | Invoke-CimMethod -MethodName DefragAnalysis; "
        "[PSCustomObject]@{"
        "ReturnValue = [int]$r.ReturnValue; "
        "DefragRecommended = [bool]$r.DefragRecommended; "
        "TotalPercent = $r.DefragAnalysis.TotalPercentFragmentation; "
        "FilePercent = $r.DefragAnalysis.FilePercentFragmentation; "
        "} | ConvertTo-Json -Compress"
    )
    result = run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        timeout=timeout,
    )
    stdout = str(result.get("stdout", "")).strip()
    if stdout.startswith("ERROR:"):
        return False, stdout[6:].strip(), None
    if not stdout:
        return False, f"Windows returned no analysis for {drive}:.", None

    try:
        data = json.loads(stdout)
    except Exception:
        return False, f"Could not read the analysis result for {drive}:.", None
    if not isinstance(data, dict):
        return False, f"Could not read the analysis result for {drive}:.", None

    code = int(data.get("ReturnValue") or 0)
    if code != 0:
        return False, f"{drive}: could not be analysed. {_describe_return(code)}.", None

    percent = _as_percent(data.get("TotalPercent"))
    recommended = bool(data.get("DefragRecommended"))
    if percent is None:
        verdict = (
            f"{drive}: needs optimising." if recommended else f"{drive}: does not need optimising."
        )
        return True, verdict, None

    verdict = (
        f"{drive}: is {percent}% fragmented. "
        f"{'Windows recommends optimising it.' if recommended else 'No optimisation needed.'}"
    )
    return True, verdict, percent


def optimize_volume(letter: str, timeout: float = 7200.0) -> tuple[bool, str]:
    """Run Windows' own optimisation, which retrims an SSD and defragments an HDD."""
    if not is_windows():
        return _linux_optimize(letter, timeout)

    drive = _normalise_letter(letter)
    if drive is None:
        return False, f"'{letter}' is not a drive letter."
    if not is_admin():
        return False, _elevation_required("optimise a drive")

    ps_cmd = (
        "$ErrorActionPreference = 'Stop'; "
        "try { "
        f"Optimize-Volume -DriveLetter {drive} -ErrorAction Stop; "
        "Write-Output 'OK' "
        "} catch { Write-Output ('ERROR:' + $_.Exception.Message) }"
    )
    result = run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        timeout=timeout,
    )
    stdout = str(result.get("stdout", "")).strip()

    if stdout.startswith("ERROR:"):
        return False, f"{drive}: could not be optimised. {stdout[6:].strip()}"
    if "OK" not in stdout:
        return False, f"{drive}: optimisation did not report success."
    return True, f"{drive}: optimised successfully."


def _as_percent(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        percent = int(value)
    except (TypeError, ValueError):
        return None
    return percent if 0 <= percent <= 100 else None


def scheduled_optimization_status() -> tuple[str, str]:
    """Windows' own ScheduledDefrag task: ``(state, detail)``.

    A task that has never run is the interesting case, and it is invisible everywhere
    else in the app.
    """
    if not is_windows():
        return _linux_schedule()

    ps_cmd = (
        "try { "
        "$t = Get-ScheduledTask -TaskName 'ScheduledDefrag' -ErrorAction Stop; "
        "$i = $t | Get-ScheduledTaskInfo; "
        "[PSCustomObject]@{"
        "State = [string]$t.State; "
        "LastRun = [string]$i.LastRunTime; "
        "LastResult = [int]$i.LastTaskResult; "
        "} | ConvertTo-Json -Compress "
        "} catch { Write-Output ('ERROR:' + $_.Exception.Message) }"
    )
    result = run_command(["powershell", "-NoProfile", "-Command", ps_cmd], timeout=15.0)
    stdout = str(result.get("stdout", "")).strip()
    if not stdout or stdout.startswith("ERROR:"):
        return "Unknown", "Could not read Windows' scheduled optimisation task."

    try:
        data = json.loads(stdout)
    except Exception:
        return "Unknown", "Could not read Windows' scheduled optimisation task."
    if not isinstance(data, dict):
        return "Unknown", "Could not read Windows' scheduled optimisation task."

    state = str(data.get("State") or "Unknown")
    # 0x00041303: the task exists but has never been run.
    if int(data.get("LastResult") or 0) == 267011:
        return state, "Windows has never run its scheduled drive optimisation."

    last_run = str(data.get("LastRun") or "").strip()
    return state, f"Last run {last_run}." if last_run else "Last run time unknown."


def _linux_analyze(target: str, timeout: float) -> tuple[bool, str, int | None]:
    """``e4defrag -c``, which scores fragmentation without changing anything.

    The score is not a percentage: e4defrag calls 0-30 fine, 31-55 mildly fragmented,
    and 56 upwards worth defragmenting. It is reported as the tool reports it.
    """
    mount = _linux_mount(target)
    if mount is None:
        return False, f"'{target}' is not a mounted volume.", None

    fs = _linux_fs(mount)
    if fs and fs not in _ANALYSABLE_LINUX_FS:
        return False, f"Fragmentation analysis is not available for {fs}.", None
    if not shutil.which("e4defrag"):
        return False, "e4defrag is not installed, so fragmentation cannot be measured.", None
    if not is_admin():
        return False, _elevation_required("analyse a drive"), None

    result = run_command(["e4defrag", "-c", mount], timeout=timeout)
    output = f"{result.get('stdout', '')}\n{result.get('stderr', '')}"
    match = _FRAG_SCORE.search(output)
    if match is None:
        return False, f"{mount}: e4defrag returned no fragmentation score.", None

    score = int(match.group(1))
    verdict = (
        "No defragmentation needed."
        if score <= 30
        else ("Mildly fragmented." if score <= 55 else "Defragmentation recommended.")
    )
    return True, f"{mount}: fragmentation score {score}. {verdict}", score


def _linux_optimize(target: str, timeout: float) -> tuple[bool, str]:
    """``fstrim``, which discards unused blocks — the Linux side of Optimize-Volume."""
    mount = _linux_mount(target)
    if mount is None:
        return False, f"'{target}' is not a mounted volume."
    if not shutil.which("fstrim"):
        return False, "fstrim is not installed, so this volume cannot be trimmed."
    if not is_admin():
        return False, _elevation_required("optimise a drive")

    result = run_command(["fstrim", "-v", mount], timeout=timeout)
    if result.get("returncode") != 0:
        # fstrim explains itself well on stderr: an unsupported discard, a read-only
        # mount, and a missing path all read differently and all matter.
        detail = str(result.get("stderr", "")).strip() or str(result.get("stdout", "")).strip()
        return False, f"{mount}: could not be trimmed. {detail or 'fstrim reported a failure.'}"

    # "/: 1.2 GiB (1288490188 bytes) trimmed" — worth passing through verbatim.
    trimmed = str(result.get("stdout", "")).strip().splitlines()
    return True, trimmed[-1].strip() if trimmed else f"{mount}: trimmed successfully."


def _linux_schedule() -> tuple[str, str]:
    """``fstrim.timer``: systemd's own periodic trim, the counterpart of ScheduledDefrag."""
    if not shutil.which("systemctl"):
        return "Unavailable", "systemd is not managing this system, so nothing is scheduled."

    enabled = run_command(["systemctl", "is-enabled", "fstrim.timer"], timeout=10.0)
    state = str(enabled.get("stdout", "")).strip()
    if not state:
        return "Unknown", "Could not read the state of fstrim.timer."
    if state != "enabled":
        return state.capitalize(), "Periodic TRIM is off. Enable fstrim.timer to turn it on."

    shown = run_command(
        ["systemctl", "show", "fstrim.timer", "--property=LastTriggerUSec", "--value"],
        timeout=10.0,
    )
    last = str(shown.get("stdout", "")).strip()
    # systemd prints an empty value, or "n/a", for a timer that has not fired yet.
    if not last or last in ("n/a", "0"):
        return "Enabled", "systemd has not run a scheduled TRIM yet."
    return "Enabled", f"Last run {last}."
