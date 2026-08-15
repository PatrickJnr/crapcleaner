"""Read-only RAM, swap/pagefile, and graphics memory reporting."""

import os
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Any

from crapcleaner.utils.platform import is_linux, is_windows, which

_UNKNOWN = -1


@dataclass
class MemoryStats:
    total_bytes: int = 0
    available_bytes: int = 0
    used_bytes: int = 0
    percent_used: float = 0.0
    swap_total_bytes: int = 0
    swap_used_bytes: int = 0
    swap_available_bytes: int = 0
    swap_supported: bool = False
    cached_bytes: int = _UNKNOWN
    commit_bytes: int = 0
    commit_limit_bytes: int = 0

    @property
    def cached_known(self) -> bool:
        return self.cached_bytes >= 0

    @property
    def pressure(self) -> str:
        """Coarse memory pressure label derived from utilization."""
        if self.total_bytes <= 0:
            return "unknown"
        if self.percent_used >= 90:
            return "critical"
        if self.percent_used >= 75:
            return "high"
        if self.percent_used >= 50:
            return "moderate"
        return "low"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["cached_known"] = self.cached_known
        data["pressure"] = self.pressure
        return data


@dataclass
class GpuMemoryStats:
    """VRAM figures for one adapter.

    ``used_bytes`` / ``free_bytes`` are ``-1`` when the platform exposes no
    reliable live counter, which is different from a genuine zero.
    """

    name: str = ""
    vendor: str = ""
    driver_version: str = ""
    total_bytes: int = 0
    used_bytes: int = _UNKNOWN
    free_bytes: int = _UNKNOWN
    source: str = ""

    @property
    def live_usage_available(self) -> bool:
        return self.used_bytes >= 0 and self.total_bytes > 0

    @property
    def percent_used(self) -> float:
        if not self.live_usage_available:
            return 0.0
        return round(self.used_bytes / self.total_bytes * 100, 1)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["live_usage_available"] = self.live_usage_available
        data["percent_used"] = self.percent_used
        return data


@dataclass
class VramConsumer:
    pid: int = 0
    name: str = ""
    used_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryReport:
    ram: MemoryStats = field(default_factory=MemoryStats)
    gpus: list[GpuMemoryStats] = field(default_factory=list)
    vram_consumers: list[VramConsumer] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ram": self.ram.to_dict(),
            "gpus": [g.to_dict() for g in self.gpus],
            "vram_consumers": [c.to_dict() for c in self.vram_consumers],
        }


def _windows_memory_stats() -> MemoryStats | None:
    try:
        import ctypes
        from ctypes import wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("sullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return None
        total = int(stat.ullTotalPhys)
        avail = int(stat.ullAvailPhys)
        used = max(0, total - avail)
        # ullTotalPageFile is physical + pagefile; the pagefile alone is the difference.
        commit_total = int(stat.ullTotalPageFile)
        commit_avail = int(stat.ullAvailPageFile)
        swap_total = max(0, commit_total - total)
        swap_avail = min(swap_total, max(0, commit_avail - avail))
        return MemoryStats(
            cached_bytes=_windows_system_cache(),
            commit_bytes=max(0, commit_total - commit_avail),
            commit_limit_bytes=commit_total,
            total_bytes=total,
            available_bytes=avail,
            used_bytes=used,
            percent_used=round((used / total * 100) if total else 0.0, 1),
            swap_total_bytes=swap_total,
            swap_used_bytes=max(0, swap_total - swap_avail),
            swap_available_bytes=swap_avail,
            swap_supported=swap_total > 0,
        )
    except Exception:
        return None


def _windows_system_cache() -> int:
    """Standby/system file cache size, or -1 when the counter is unavailable."""
    try:
        import ctypes
        from ctypes import wintypes

        class PERFORMANCE_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("CommitTotal", ctypes.c_size_t),
                ("CommitLimit", ctypes.c_size_t),
                ("CommitPeak", ctypes.c_size_t),
                ("PhysicalTotal", ctypes.c_size_t),
                ("PhysicalAvailable", ctypes.c_size_t),
                ("SystemCache", ctypes.c_size_t),
                ("KernelTotal", ctypes.c_size_t),
                ("KernelPaged", ctypes.c_size_t),
                ("KernelNonpaged", ctypes.c_size_t),
                ("PageSize", ctypes.c_size_t),
                ("HandleCount", wintypes.DWORD),
                ("ProcessCount", wintypes.DWORD),
                ("ThreadCount", wintypes.DWORD),
            ]

        info = PERFORMANCE_INFORMATION()
        info.cb = ctypes.sizeof(info)
        if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(info), info.cb):
            return _UNKNOWN
        return int(info.SystemCache) * int(info.PageSize)
    except Exception:
        return _UNKNOWN


def _linux_meminfo(path: str = "/proc/meminfo") -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                key, _, rest = line.partition(":")
                parts = rest.split()
                if parts:
                    try:
                        values[key.strip()] = int(parts[0]) * 1024
                    except ValueError:
                        continue
    except OSError:
        pass
    return values


def _linux_memory_stats(path: str = "/proc/meminfo") -> MemoryStats | None:
    info = _linux_meminfo(path)
    total = info.get("MemTotal", 0)
    if not total:
        return None
    avail = info.get("MemAvailable", info.get("MemFree", 0))
    used = max(0, total - avail)
    swap_total = info.get("SwapTotal", 0)
    swap_free = info.get("SwapFree", 0)
    cached = info.get("Cached", _UNKNOWN)
    if cached >= 0:
        cached += info.get("SReclaimable", 0)
    commit_limit = info.get("CommitLimit", 0)
    return MemoryStats(
        cached_bytes=cached,
        commit_bytes=info.get("Committed_AS", 0),
        commit_limit_bytes=commit_limit,
        total_bytes=total,
        available_bytes=avail,
        used_bytes=used,
        percent_used=round(used / total * 100, 1),
        swap_total_bytes=swap_total,
        swap_used_bytes=max(0, swap_total - swap_free),
        swap_available_bytes=swap_free,
        swap_supported=swap_total > 0,
    )


def get_memory_stats() -> MemoryStats:
    stats = _windows_memory_stats() if is_windows() else _linux_memory_stats()
    return stats or MemoryStats()


def _nvidia_smi_path() -> str | None:
    smi = which("nvidia-smi")
    if smi:
        return smi
    if is_windows():
        for candidate in (
            os.path.expandvars(r"%ProgramFiles%\NVIDIA Corporation\NVSMI\nvidia-smi.exe"),
            os.path.expandvars(r"%SystemRoot%\System32\nvidia-smi.exe"),
        ):
            if os.path.exists(candidate):
                return candidate
    return None


def _run_smi(args: list[str]) -> list[str]:
    smi = _nvidia_smi_path()
    if not smi:
        return []
    try:
        out = subprocess.run([smi, *args], capture_output=True, text=True, timeout=6)
    except Exception:
        return []
    if out.returncode != 0:
        return []
    return [line for line in out.stdout.splitlines() if line.strip()]


def _nvidia_gpu_memory() -> list[GpuMemoryStats]:
    lines = _run_smi(
        [
            "--query-gpu=name,driver_version,memory.total,memory.used,memory.free",
            "--format=csv,noheader,nounits",
        ]
    )
    gpus = []
    mib = 1024 * 1024
    for line in lines:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        try:
            total = int(float(parts[2])) * mib
        except ValueError:
            continue

        used = _UNKNOWN
        free = _UNKNOWN
        try:
            used = int(float(parts[3])) * mib
            free = int(float(parts[4])) * mib
        except ValueError:
            pass

        gpus.append(
            GpuMemoryStats(
                name=parts[0],
                vendor="NVIDIA",
                driver_version=parts[1],
                total_bytes=total,
                used_bytes=used,
                free_bytes=free,
                source="nvidia-smi",
            )
        )
    return gpus


def _vendor_from_name(name: str) -> str:
    lowered = name.lower()
    if "nvidia" in lowered or "geforce" in lowered or "quadro" in lowered or "rtx" in lowered:
        return "NVIDIA"
    if "amd" in lowered or "radeon" in lowered or "ati " in lowered:
        return "AMD"
    if "intel" in lowered or "arc " in lowered or "iris" in lowered:
        return "Intel"
    return ""


def _amdgpu_sysfs_memory() -> list[GpuMemoryStats]:
    gpus: list[GpuMemoryStats] = []
    base = "/sys/class/drm"
    try:
        cards = sorted(d for d in os.listdir(base) if d.startswith("card") and "-" not in d)
    except OSError:
        return gpus
    for card in cards:
        device = os.path.join(base, card, "device")
        total_path = os.path.join(device, "mem_info_vram_total")
        used_path = os.path.join(device, "mem_info_vram_used")
        try:
            with open(total_path, encoding="utf-8") as fh:
                total = int(fh.read().strip())
            with open(used_path, encoding="utf-8") as fh:
                used = int(fh.read().strip())
        except (OSError, ValueError):
            continue
        name = card
        try:
            with open(os.path.join(device, "product_name"), encoding="utf-8") as fh:
                name = fh.read().strip() or card
        except OSError:
            pass
        gpus.append(
            GpuMemoryStats(
                name=name,
                vendor="AMD",
                total_bytes=total,
                used_bytes=used,
                free_bytes=max(0, total - used),
                source="amdgpu sysfs",
            )
        )
    return gpus


def _capacity_only_gpus() -> list[GpuMemoryStats]:
    """Adapter capacities from the hardware inspector, without live usage counters."""
    try:
        from crapcleaner.specs.hardware import _get_gpu_specs
    except Exception:
        return []
    try:
        specs = _get_gpu_specs()
    except Exception:
        return []
    return [
        GpuMemoryStats(
            name=gpu.name,
            vendor=_vendor_from_name(gpu.name),
            driver_version=gpu.driver_version,
            total_bytes=gpu.adapter_ram_bytes,
            source="adapter capacity",
        )
        for gpu in specs
        if gpu.name
    ]


def get_gpu_memory() -> list[GpuMemoryStats]:
    live = _nvidia_gpu_memory()
    if is_linux():
        live.extend(_amdgpu_sysfs_memory())
    live_names = {g.name.lower() for g in live}
    for gpu in _capacity_only_gpus():
        if gpu.name.lower() in live_names:
            continue
        if any(gpu.name.lower() in known or known in gpu.name.lower() for known in live_names):
            continue
        live.append(gpu)
    return live


def get_vram_consumers() -> list[VramConsumer]:
    """Processes holding GPU memory, where the driver reports them.

    Disabled in the default report because NVIDIA's exposed process lists are often
    incomplete or noisy on desktop Linux (for example, graphics contexts may not
    appear in the compute-apps query, while other interfaces surface low-signal
    helper processes). The GUI and CLI now focus on adapter-level VRAM figures.
    """
    return []


def get_memory_report(include_gpu: bool = True) -> MemoryReport:
    report = MemoryReport(ram=get_memory_stats())
    if include_gpu:
        report.gpus = get_gpu_memory()
        report.vram_consumers = get_vram_consumers()
    return report
