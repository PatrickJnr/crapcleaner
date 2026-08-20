"""Read-only storage device health, media type, and TRIM status diagnostics.

Provides cross-platform disk health, SSD/HDD detection, bus interface reporting,
TRIM enablement status, and capacity metrics without running destructive tests.
"""

import json
import os
import re
import shutil
import threading
import time
from dataclasses import dataclass
from typing import Any

from crapcleaner.utils.platform import (
    get_drive_info,
    is_linux,
    is_windows,
    list_drives,
    run_command,
)


@dataclass
class DiskHealthInfo:
    device_id: str
    model: str
    media_type: str  # SSD, HDD, NVMe, Removable, Unknown
    bus_type: str  # NVMe, SATA, USB, SCSI, IDE, Unknown
    capacity: int
    free_space: int
    filesystem: str
    trim_supported: bool | None
    trim_enabled: bool | None
    health_status: str  # Healthy, Warning, Unhealthy, Unknown
    operational_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "model": self.model,
            "media_type": self.media_type,
            "bus_type": self.bus_type,
            "capacity": self.capacity,
            "free_space": self.free_space,
            "filesystem": self.filesystem,
            "trim_supported": self.trim_supported,
            "trim_enabled": self.trim_enabled,
            "health_status": self.health_status,
            "operational_status": self.operational_status,
        }


HEALTH_CACHE_TTL = 60.0

_cache_lock = threading.Lock()
_cached_report: tuple[float, list[DiskHealthInfo]] | None = None


def _query_storage_health() -> list[DiskHealthInfo]:
    if is_windows():
        return _get_windows_storage_health()
    if is_linux():
        return _get_linux_storage_health()
    return _get_fallback_storage_health()


def get_storage_health_report(
    force_refresh: bool = False, ttl: float = HEALTH_CACHE_TTL
) -> list[DiskHealthInfo]:
    """Read-only storage device health for every accessible drive.

    Each query spawns PowerShell or lsblk, so results are cached briefly;
    explicit refreshes bypass the cache.
    """
    global _cached_report
    now = time.monotonic()
    if not force_refresh:
        with _cache_lock:
            cached = _cached_report
        if cached is not None and now - cached[0] < ttl:
            return list(cached[1])

    report = _query_storage_health()
    with _cache_lock:
        _cached_report = (time.monotonic(), report)
    return list(report)


def clear_storage_health_cache() -> None:
    global _cached_report
    with _cache_lock:
        _cached_report = None


_FSUTIL_TRIM = re.compile(r"(?:([A-Za-z]+)\s+)?DisableDeleteNotify\s*=\s*(\d+)")


def _windows_trim_states() -> dict[str, bool]:
    """Filesystem name -> whether TRIM is enabled, as reported by fsutil.

    ``DisableDeleteNotify = 0`` means TRIM is *enabled*; the flag is inverted. fsutil
    prints one row per filesystem (NTFS, ReFS) and the rows can disagree, so a volume
    must be answered from its own row. The unnamed row is what pre-8.1 fsutil printed.
    """
    result = run_command(["fsutil", "behavior", "query", "DisableDeleteNotify"], timeout=5.0)
    states: dict[str, bool] = {}
    for line in str(result.get("stdout", "")).splitlines():
        match = _FSUTIL_TRIM.search(line)
        if match:
            states[(match.group(1) or "").upper()] = match.group(2) == "0"
    return states


def _get_windows_trim_status(
    filesystem: str = "", states: dict[str, bool] | None = None
) -> tuple[bool | None, bool | None]:
    """(supported, enabled) for one filesystem; unknown to fsutil reports (None, None)."""
    if states is None:
        states = _windows_trim_states()
    enabled = states.get(filesystem.strip().upper())
    if enabled is None:
        enabled = states.get("")
    if enabled is None:
        return None, None
    return True, enabled


def _get_windows_storage_health() -> list[DiskHealthInfo]:
    disks: list[DiskHealthInfo] = []
    trim_states = _windows_trim_states()

    # Query partitions with DriveLetter mapped to their physical disk metadata
    ps_cmd = (
        "Get-Partition | Where-Object DriveLetter | ForEach-Object { "
        "$p = $_; "
        "$pd = Get-PhysicalDisk | Where-Object DeviceId -eq $p.DiskNumber; "
        "[PSCustomObject]@{"
        'DriveLetter = "$($p.DriveLetter):"; '
        "DiskNumber = $p.DiskNumber; "
        'FriendlyName = if ($pd) { $pd.FriendlyName } else { "Storage Device" }; '
        'MediaType = if ($pd) { $pd.MediaType } else { "Unknown" }; '
        'BusType = if ($pd) { $pd.BusType } else { "Unknown" }; '
        "Size = $p.Size; "
        'HealthStatus = if ($pd) { $pd.HealthStatus } else { "Unknown" }; '
        'OperationalStatus = if ($pd) { $pd.OperationalStatus } else { "Unknown" }; '
        "} } | ConvertTo-Json"
    )
    result = run_command(["powershell", "-NoProfile", "-Command", ps_cmd], timeout=8.0)
    raw_json = str(result.get("stdout", "")).strip()

    seen_drives: set[str] = set()

    if raw_json:
        try:
            data = json.loads(raw_json)
            parsed_devices = data if isinstance(data, list) else [data]
            for item in parsed_devices:
                dl = str(item.get("DriveLetter", "")).rstrip("\\")
                if not dl:
                    continue
                dev_id = dl if dl.endswith(":") else f"{dl}:"
                model = str(item.get("FriendlyName", "Storage Device"))
                media = str(item.get("MediaType", "Unknown"))
                bus = str(item.get("BusType", "Unknown"))
                size = int(item.get("Size") or 0)
                health = str(item.get("HealthStatus", "Unknown"))
                op_status = str(item.get("OperationalStatus", "Unknown"))

                if "NVME" in bus.upper() or "NVME" in model.upper():
                    media = "NVMe SSD"
                elif (
                    "SSD" in media.upper()
                    or "SOLID STATE" in media.upper()
                    or "SSD" in model.upper()
                ):
                    media = "SSD"
                elif "HDD" in media.upper() or "HARD DISK" in media.upper():
                    media = "HDD"

                free_space = 0
                filesystem = "NTFS"
                try:
                    vol_info = get_drive_info(dev_id)
                    if vol_info.get("total"):
                        size = int(vol_info.get("total", size))
                    free_space = int(vol_info.get("free", 0))
                    filesystem = str(vol_info.get("filesystem", "NTFS"))
                except Exception:
                    pass

                seen_drives.add(dev_id.upper())
                is_solid_state = "SSD" in media or "NVMe" in media
                trim_supp, trim_en = _get_windows_trim_status(filesystem, trim_states)
                disks.append(
                    DiskHealthInfo(
                        device_id=dev_id,
                        model=model,
                        media_type=media,
                        bus_type=bus,
                        capacity=size,
                        free_space=free_space,
                        filesystem=filesystem,
                        trim_supported=trim_supp if is_solid_state else False,
                        trim_enabled=trim_en if is_solid_state else False,
                        health_status=health,
                        operational_status=op_status,
                    )
                )
        except Exception:
            pass

    for drive in list_drives():
        d_clean = drive.rstrip("\\")
        d_key = (d_clean if d_clean.endswith(":") else f"{d_clean}:").upper()
        if d_key not in seen_drives:
            try:
                info = get_drive_info(drive)
                total = int(info.get("total", 0))
                free = int(info.get("free", 0))
                filesystem = str(info.get("filesystem", "NTFS"))
                trim_supp, trim_en = _get_windows_trim_status(filesystem, trim_states)
                disks.append(
                    DiskHealthInfo(
                        device_id=d_clean,
                        model=f"Local Disk ({d_clean})",
                        media_type="Storage Drive",
                        bus_type="Local",
                        capacity=total,
                        free_space=free,
                        filesystem=filesystem,
                        trim_supported=trim_supp,
                        trim_enabled=trim_en,
                        health_status="Unknown",
                        operational_status="Unknown",
                    )
                )
            except OSError:
                continue

    disks.sort(key=lambda x: x.device_id.upper())
    return disks


def _as_bytes(value: Any) -> int | None:
    try:
        return int(str(value).strip().rstrip("B") or 0)
    except (TypeError, ValueError):
        return None


def _mount_options(device: str) -> set[str]:
    """Mount options of every filesystem mounted from `device` or one of its partitions."""
    options: set[str] = set()
    try:
        with open("/proc/mounts", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 4 and parts[0].startswith(device):
                    options.update(parts[3].split(","))
    except OSError:
        pass
    return options


def _fstrim_timer_active() -> bool | None:
    """Whether the periodic fstrim job runs; None when systemd cannot be asked."""
    if not shutil.which("systemctl"):
        return None
    res = run_command(["systemctl", "is-enabled", "fstrim.timer"], timeout=5.0)
    state = str(res.get("stdout", "")).strip()
    if not state:
        return None
    return state in ("enabled", "enabled-runtime")


def _smart_health(device: str) -> tuple[str, str]:
    """(health, operational status) from smartctl, or Unknown when it cannot be read."""
    if not shutil.which("smartctl"):
        return "Unknown", "Unknown"
    res = run_command(["smartctl", "-H", "-j", device], timeout=10.0)
    try:
        data = json.loads(str(res.get("stdout", "")).strip() or "{}")
    except ValueError:
        return "Unknown", "Unknown"
    status = data.get("smart_status") if isinstance(data, dict) else None
    passed = status.get("passed") if isinstance(status, dict) else None
    if passed is True:
        return "Healthy", "OK"
    if passed is False:
        return "Unhealthy", "SMART self-assessment failed"
    return "Unknown", "Unknown"


def _linux_trim_status(device: str, disc_gran: Any) -> tuple[bool | None, bool | None]:
    """(supported, enabled) from lsblk's discard granularity plus how discard is run."""
    granularity = _as_bytes(disc_gran)
    if granularity is None:
        return None, None
    if granularity <= 0:
        return False, False
    if "discard" in _mount_options(device):
        return True, True
    return True, _fstrim_timer_active()


def _get_linux_storage_health() -> list[DiskHealthInfo]:
    disks: list[DiskHealthInfo] = []
    res = run_command(
        [
            "lsblk",
            "-J",
            "-b",
            "-d",
            "-o",
            "NAME,MODEL,ROTA,SIZE,TYPE,TRAN,FSTYPE,MOUNTPOINT,DISC-GRAN",
        ],
        timeout=5.0,
    )
    raw = str(res.get("stdout", "")).strip()
    if raw:
        try:
            data = json.loads(raw)
            for item in data.get("blockdevices", []):
                name = item.get("name", "")
                model = (item.get("model") or name or "Storage Drive").strip()
                rota = item.get("rota")  # True = HDD, False = SSD
                tran = (item.get("tran") or "Unknown").upper()
                media = "SSD" if rota is False else ("HDD" if rota is True else "Storage Drive")
                if tran == "NVME":
                    media = "NVMe SSD"

                raw_size = item.get("size")
                try:
                    capacity = int(raw_size) if raw_size is not None else 0
                except (ValueError, TypeError):
                    capacity = 0

                free_space = 0
                mp = item.get("mountpoint")
                if mp and os.path.exists(mp):
                    try:
                        _, _, free_space = shutil.disk_usage(mp)
                    except OSError:
                        pass

                device_id = f"/dev/{name}"
                trim_supported, trim_enabled = _linux_trim_status(device_id, item.get("disc-gran"))
                health, operational = _smart_health(device_id)
                disks.append(
                    DiskHealthInfo(
                        device_id=device_id,
                        model=model,
                        media_type=media,
                        bus_type=tran,
                        capacity=capacity,
                        free_space=free_space,
                        filesystem=item.get("fstype") or "Unknown",
                        trim_supported=trim_supported,
                        trim_enabled=trim_enabled,
                        health_status=health,
                        operational_status=operational,
                    )
                )
        except ValueError:
            pass

    if not disks:
        return _get_fallback_storage_health()
    return disks


def _get_fallback_storage_health() -> list[DiskHealthInfo]:
    disks: list[DiskHealthInfo] = []
    for mount in list_drives():
        try:
            total, used, free = shutil.disk_usage(mount)
            disks.append(
                DiskHealthInfo(
                    device_id=mount,
                    model=f"Storage Mount ({mount})",
                    media_type="Disk Volume",
                    bus_type="Local",
                    capacity=total,
                    free_space=free,
                    filesystem="Local",
                    trim_supported=None,
                    trim_enabled=None,
                    health_status="Unknown",
                    operational_status="Unknown",
                )
            )
        except OSError:
            continue
    return disks
