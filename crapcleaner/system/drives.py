"""Per-physical-disk drive inventory: hardware, reliability counters, and volumes.

Health readings such as temperature and wear belong to a physical disk, while TRIM and
fragmentation belong to a volume. This module returns that shape directly rather than
leaving callers to regroup a flat per-drive-letter list.

Reading fragmentation is deliberately not part of this inventory: it needs elevation and
real time per volume. See :mod:`crapcleaner.system.drive_actions`.
"""

import json
import threading
from dataclasses import dataclass, field, replace
from typing import Any

from crapcleaner.system.storage_health import (
    _as_counter,
    _get_windows_trim_status,
    _windows_trim_states,
    get_storage_health_report,
)
from crapcleaner.utils import disk_cache
from crapcleaner.utils.platform import (
    get_drive_info,
    is_windows,
    list_drives,
    run_command,
)

#: Volumes with no backing physical disk still belong to the user's mental model of
#: their machine, so they are grouped rather than dropped.
UNMAPPED_DISK_NUMBER = -1

#: Key for the inventory kept between launches.
_CACHE_NAME = "drives"


@dataclass
class VolumeInfo:
    letter: str
    label: str = ""
    filesystem: str = ""
    capacity: int = 0
    free_space: int = 0
    trim_supported: bool | None = None
    trim_enabled: bool | None = None
    #: Filled in only by an explicit analyse; None means "not measured", not "zero".
    fragmentation_percent: int | None = None
    defrag_verdict: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "letter": self.letter,
            "label": self.label,
            "filesystem": self.filesystem,
            "capacity": self.capacity,
            "free_space": self.free_space,
            "trim_supported": self.trim_supported,
            "trim_enabled": self.trim_enabled,
            "fragmentation_percent": self.fragmentation_percent,
            "defrag_verdict": self.defrag_verdict,
        }


@dataclass
class PhysicalDiskInfo:
    disk_number: int
    model: str = "Storage Device"
    media_type: str = "Unknown"
    bus_type: str = "Unknown"
    size: int = 0
    health_status: str = "Unknown"
    operational_status: str = "Unknown"
    temperature_c: int | None = None
    wear_percent: int | None = None
    power_on_hours: int | None = None
    start_stop_cycles: int | None = None
    read_errors: int | None = None
    write_errors: int | None = None
    volumes: list[VolumeInfo] = field(default_factory=list)

    @property
    def is_unmapped(self) -> bool:
        """Whether this is the catch-all group rather than a real physical disk."""
        return self.disk_number == UNMAPPED_DISK_NUMBER

    @property
    def has_telemetry(self) -> bool:
        """Whether the drive reported any reliability counter at all."""
        return any(
            value is not None
            for value in (
                self.temperature_c,
                self.wear_percent,
                self.power_on_hours,
                self.start_stop_cycles,
                self.read_errors,
                self.write_errors,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "disk_number": self.disk_number,
            "model": self.model,
            "media_type": self.media_type,
            "bus_type": self.bus_type,
            "size": self.size,
            "health_status": self.health_status,
            "operational_status": self.operational_status,
            "temperature_c": self.temperature_c,
            "wear_percent": self.wear_percent,
            "power_on_hours": self.power_on_hours,
            "start_stop_cycles": self.start_stop_cycles,
            "read_errors": self.read_errors,
            "write_errors": self.write_errors,
            "volumes": [v.to_dict() for v in self.volumes],
        }


_PS_DRIVES = (
    "$disks = @(); "
    "foreach ($pd in Get-PhysicalDisk) { "
    "$rc = $null; "
    "try { $rc = $pd | Get-StorageReliabilityCounter -ErrorAction Stop } catch { $rc = $null }; "
    "$vols = @(); "
    "foreach ($p in (Get-Partition -DiskNumber $pd.DeviceId -ErrorAction SilentlyContinue | "
    "Where-Object DriveLetter)) { "
    "$v = Get-Volume -DriveLetter $p.DriveLetter -ErrorAction SilentlyContinue; "
    "$vols += [PSCustomObject]@{"
    'Letter = "$($p.DriveLetter):"; '
    'Label = if ($v) { $v.FileSystemLabel } else { "" }; '
    'FileSystem = if ($v) { $v.FileSystem } else { "" }; '
    "Capacity = if ($v) { $v.Size } else { $p.Size }; "
    "Free = if ($v) { $v.SizeRemaining } else { 0 }; "
    "} "
    "}; "
    "$disks += [PSCustomObject]@{"
    "DiskNumber = $pd.DeviceId; "
    "Model = $pd.FriendlyName; "
    'MediaType = "$($pd.MediaType)"; '
    'BusType = "$($pd.BusType)"; '
    "Size = $pd.Size; "
    'HealthStatus = "$($pd.HealthStatus)"; '
    'OperationalStatus = "$($pd.OperationalStatus)"; '
    "Temperature = if ($rc) { $rc.Temperature } else { $null }; "
    "Wear = if ($rc) { $rc.Wear } else { $null }; "
    "PowerOnHours = if ($rc) { $rc.PowerOnHours } else { $null }; "
    "StartStopCycles = if ($rc) { $rc.StartStopCycleCount } else { $null }; "
    "ReadErrors = if ($rc) { $rc.ReadErrorsTotal } else { $null }; "
    "WriteErrors = if ($rc) { $rc.WriteErrorsTotal } else { $null }; "
    "Volumes = @($vols); "
    "} "
    "}; "
    "$disks | ConvertTo-Json -Depth 4 -Compress"
)

_cache_lock = threading.Lock()
#: (drive signature, disks). Invalidated when a drive appears or disappears, not on a timer.
_cached_drives: tuple[tuple[str, ...], list[PhysicalDiskInfo]] | None = None


def _clean_counters(disk: "PhysicalDiskInfo") -> None:
    """Drop readings the drive did not really report.

    NVMe controllers answer this counter with zeroes rather than refusing it, and wear is
    a solid-state concept, so a spinning disk reporting 0% wear is noise, not health.

    A controller answering 0 °C while reporting no running hours at all is not reporting,
    so its 0% wear is the same zero, not a pristine drive.
    """
    silent_controller = (
        disk.temperature_c == 0 and disk.power_on_hours is None and disk.wear_percent == 0
    )

    if disk.temperature_c == 0:
        disk.temperature_c = None
    if silent_controller or "SSD" not in disk.media_type.upper():
        disk.wear_percent = None


def _normalise_media(media: str, bus: str, model: str) -> str:
    """Windows reports NVMe drives as plain 'SSD'; the bus is what distinguishes them."""
    upper_bus, upper_model, upper_media = bus.upper(), model.upper(), media.upper()
    if "NVME" in upper_bus or "NVME" in upper_model:
        return "NVMe SSD"
    if "SSD" in upper_media or "SOLID STATE" in upper_media:
        return "SSD"
    if "HDD" in upper_media or upper_media == "UNSPECIFIED":
        return "HDD"
    return media or "Unknown"


def _volume_from_item(item: dict, trim_states: dict[str, bool], solid_state: bool) -> VolumeInfo:
    filesystem = str(item.get("FileSystem") or "")
    trim_supported, trim_enabled = _get_windows_trim_status(filesystem, trim_states)
    return VolumeInfo(
        letter=str(item.get("Letter") or ""),
        label=str(item.get("Label") or ""),
        filesystem=filesystem,
        capacity=int(item.get("Capacity") or 0),
        free_space=int(item.get("Free") or 0),
        trim_supported=trim_supported if solid_state else False,
        trim_enabled=trim_enabled if solid_state else False,
    )


def _get_windows_drives() -> list[PhysicalDiskInfo]:
    result = run_command(
        ["powershell", "-NoProfile", "-Command", _PS_DRIVES],
        timeout=40.0,
    )
    raw = str(result.get("stdout", "")).strip()
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except Exception:
        return []

    trim_states = _windows_trim_states()
    disks: list[PhysicalDiskInfo] = []

    for item in data if isinstance(data, list) else [data]:
        if not isinstance(item, dict):
            continue
        model = str(item.get("Model") or "Storage Device")
        bus = str(item.get("BusType") or "Unknown")
        media = _normalise_media(str(item.get("MediaType") or ""), bus, model)
        solid_state = "SSD" in media

        raw_volumes = item.get("Volumes") or []
        if isinstance(raw_volumes, dict):
            raw_volumes = [raw_volumes]

        disk = PhysicalDiskInfo(
            disk_number=int(item.get("DiskNumber") or 0),
            model=model,
            media_type=media,
            bus_type=bus,
            size=int(item.get("Size") or 0),
            health_status=str(item.get("HealthStatus") or "Unknown"),
            operational_status=str(item.get("OperationalStatus") or "Unknown"),
            temperature_c=_as_counter(item.get("Temperature")),
            wear_percent=_as_counter(item.get("Wear")),
            power_on_hours=_as_counter(item.get("PowerOnHours")),
            start_stop_cycles=_as_counter(item.get("StartStopCycles")),
            read_errors=_as_counter(item.get("ReadErrors")),
            write_errors=_as_counter(item.get("WriteErrors")),
            volumes=[
                _volume_from_item(v, trim_states, solid_state)
                for v in raw_volumes
                if isinstance(v, dict) and v.get("Letter")
            ],
        )
        _clean_counters(disk)
        disks.append(disk)

    disks.sort(key=lambda d: d.disk_number)
    return disks


def _unmapped_group(disks: list[PhysicalDiskInfo]) -> PhysicalDiskInfo | None:
    """Drives the user sees in Explorer that sit on no physical disk, such as a
    virtual or network mount. Dropping them would make the view disagree with Explorer.
    """
    mapped = {v.letter.upper() for d in disks for v in d.volumes}
    strays = [
        VolumeInfo(
            letter=disk.device_id,
            label="",
            filesystem=disk.filesystem,
            capacity=disk.capacity,
            free_space=disk.free_space,
            trim_supported=disk.trim_supported,
            trim_enabled=disk.trim_enabled,
        )
        for disk in get_storage_health_report()
        if disk.device_id.upper() not in mapped
    ]
    if not strays:
        return None
    return PhysicalDiskInfo(
        disk_number=UNMAPPED_DISK_NUMBER,
        model="Other volumes",
        media_type="Virtual / Removable",
        bus_type="Unknown",
        size=sum(v.capacity for v in strays),
        health_status="Unknown",
        operational_status="Unknown",
        volumes=strays,
    )


def _query_drives() -> list[PhysicalDiskInfo]:
    if not is_windows():
        return _drives_from_health_report()

    disks = _get_windows_drives()
    if not disks:
        return _drives_from_health_report()

    stray = _unmapped_group(disks)
    if stray is not None:
        disks.append(stray)
    return disks


def _drives_from_health_report() -> list[PhysicalDiskInfo]:
    """One disk per device, for platforms without the Windows storage cmdlets."""
    return [
        PhysicalDiskInfo(
            disk_number=index,
            model=disk.model,
            media_type=disk.media_type,
            bus_type=disk.bus_type,
            size=disk.capacity,
            health_status=disk.health_status,
            operational_status=disk.operational_status,
            temperature_c=disk.temperature_c,
            wear_percent=disk.wear_percent,
            power_on_hours=disk.power_on_hours,
            start_stop_cycles=disk.start_stop_cycles,
            read_errors=disk.read_errors,
            write_errors=disk.write_errors,
            volumes=[
                VolumeInfo(
                    letter=disk.device_id,
                    filesystem=disk.filesystem,
                    capacity=disk.capacity,
                    free_space=disk.free_space,
                    trim_supported=disk.trim_supported,
                    trim_enabled=disk.trim_enabled,
                )
            ],
        )
        for index, disk in enumerate(get_storage_health_report())
    ]


def drive_signature() -> tuple[str, ...]:
    """The set of mounted drives, which is cheap to read and changes only on plug or eject."""
    try:
        return tuple(sorted(list_drives()))
    except Exception:
        return ()


def _refresh_free_space(disks: list[PhysicalDiskInfo]) -> list[PhysicalDiskInfo]:
    """Re-read capacity and free space, which move constantly, on cached hardware."""
    refreshed = []
    for disk in disks:
        clone = replace(disk, volumes=[replace(v) for v in disk.volumes])
        for volume in clone.volumes:
            try:
                info = get_drive_info(volume.letter)
            except Exception:
                continue
            volume.capacity = int(info.get("total") or volume.capacity)
            volume.free_space = int(info.get("free") or volume.free_space)
        refreshed.append(clone)
    return refreshed


def _from_payload(payload: Any) -> list[PhysicalDiskInfo] | None:
    """Rebuild an inventory written by an earlier run, or None if it is unusable."""
    if not isinstance(payload, list):
        return None
    try:
        return [
            PhysicalDiskInfo(
                **{k: v for k, v in disk.items() if k != "volumes"},
                volumes=[VolumeInfo(**volume) for volume in disk.get("volumes", [])],
            )
            for disk in payload
        ]
    except (AttributeError, TypeError, ValueError):
        # A cache written by a different version of the model is simply a miss.
        return None


def cached_drives_report() -> list[PhysicalDiskInfo] | None:
    """The stored inventory, or None when nothing usable is cached.

    Never probes the hardware. This is for a caller that wants to paint what it already
    knows immediately and refresh afterwards; a probe is the very thing it is avoiding.
    """
    global _cached_drives
    signature = drive_signature()

    with _cache_lock:
        cached = _cached_drives
    if cached is not None and cached[0] == signature:
        return _refresh_free_space(cached[1])

    stored = _from_payload(disk_cache.load(_CACHE_NAME, list(signature)))
    if stored:
        with _cache_lock:
            _cached_drives = (signature, stored)
        return _refresh_free_space(stored)
    return None


def get_drives_report(force_refresh: bool = False) -> list[PhysicalDiskInfo]:
    """Physical disks with their volumes nested.

    Probing the hardware costs seconds of PowerShell, and none of what it returns changes
    while a drive stays plugged in, so it is cached until the set of mounted drives
    changes. The cache outlives the process, so only the first launch after plugging a
    drive in pays for it. Capacity and free space are re-read on every call, since those
    do move.
    """
    global _cached_drives
    signature = drive_signature()

    if not force_refresh:
        with _cache_lock:
            cached = _cached_drives
        if cached is not None and cached[0] == signature:
            return _refresh_free_space(cached[1])

        stored = _from_payload(disk_cache.load(_CACHE_NAME, list(signature)))
        if stored:
            with _cache_lock:
                _cached_drives = (signature, stored)
            return _refresh_free_space(stored)

    drives = _query_drives()
    with _cache_lock:
        _cached_drives = (signature, drives)
    if drives:
        disk_cache.store(_CACHE_NAME, list(signature), [d.to_dict() for d in drives])
    return _refresh_free_space(drives)


def clear_drives_cache() -> None:
    """Drop the cached inventory so the next read re-queries the hardware."""
    global _cached_drives
    with _cache_lock:
        _cached_drives = None
    disk_cache.clear(_CACHE_NAME)
