"""Zero-overhead real-time system metrics engine.

Provides high-frequency, non-blocking telemetry for Network throughput (bytes in/out),
CPU utilization, RAM pressure, GPU thermals & VRAM, and system uptime across Windows
and Linux without third-party dependencies.
"""

import ctypes
import glob
import os
import threading
import time
from dataclasses import dataclass

from crapcleaner.utils.format import format_size
from crapcleaner.utils.platform import is_linux, is_windows


@dataclass
class NetworkVitals:
    bytes_in_sec: float = 0.0
    bytes_out_sec: float = 0.0
    total_in_bytes: int = 0
    total_out_bytes: int = 0
    interface_name: str = "Active"
    is_connected: bool = True

    @property
    def in_rate_str(self) -> str:
        return f"{format_size(int(self.bytes_in_sec))}/s"

    @property
    def out_rate_str(self) -> str:
        return f"{format_size(int(self.bytes_out_sec))}/s"

    @property
    def total_in_str(self) -> str:
        return format_size(self.total_in_bytes)

    @property
    def total_out_str(self) -> str:
        return format_size(self.total_out_bytes)


@dataclass
class CpuVitals:
    percent_used: float = 0.0
    logical_cores: int = 1
    physical_cores: int = 1


@dataclass
class RamVitals:
    used_bytes: int = 0
    total_bytes: int = 0
    available_bytes: int = 0
    percent_used: float = 0.0
    pressure: str = "normal"  # "low", "normal", "high", "critical"

    @property
    def used_str(self) -> str:
        return format_size(self.used_bytes)

    @property
    def total_str(self) -> str:
        return format_size(self.total_bytes)

    @property
    def fraction_str(self) -> str:
        return f"{self.used_str} / {self.total_str}"


@dataclass
class GpuVitals:
    """Live GPU readings. A metric that could not be read stays ``None``.

    Vendors expose wildly different subsets - NVML gives everything, amdgpu sysfs
    gives load and often temperature, a plain Windows display adapter gives only a
    name and VRAM size - so every field is optional and rendered as "N/A" when
    missing rather than as a fabricated zero.
    """

    available: bool = False
    name: str = "GPU"
    temperature_c: int | None = None
    utilization_pct: float | None = None
    vram_used_bytes: int | None = None
    vram_total_bytes: int | None = None
    thermal_status: str = "optimal"  # "cool", "optimal", "warm", "hot"

    @property
    def temp_str(self) -> str:
        if not self.available or not self.temperature_c or self.temperature_c <= 0:
            return "N/A"
        return f"{self.temperature_c}°C"

    @property
    def utilization_str(self) -> str:
        if not self.available or self.utilization_pct is None:
            return "N/A"
        return f"{int(self.utilization_pct)}%"

    @property
    def vram_used_str(self) -> str:
        return format_size(self.vram_used_bytes) if self.vram_used_bytes else "--"

    @property
    def vram_total_str(self) -> str:
        return format_size(self.vram_total_bytes) if self.vram_total_bytes else "--"

    @property
    def vram_fraction_str(self) -> str:
        if not self.vram_total_bytes:
            return "-- / --"
        return f"{self.vram_used_str} / {self.vram_total_str}"

    @property
    def vram_percent(self) -> float:
        if not self.vram_total_bytes or not self.vram_used_bytes:
            return 0.0
        return round((self.vram_used_bytes / self.vram_total_bytes) * 100.0, 1)


@dataclass
class SystemLiveSnapshot:
    network: NetworkVitals
    cpu: CpuVitals
    ram: RamVitals
    gpu: GpuVitals
    uptime_str: str = ""
    power_str: str = "AC Power"
    timestamp: float = 0.0


# Windows API Structures
if is_windows():

    class _FILETIME(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", ctypes.c_uint32),
            ("dwHighDateTime", ctypes.c_uint32),
        ]

        def to_uint64(self) -> int:
            return (self.dwHighDateTime << 32) | self.dwLowDateTime

    class _MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_uint32),
            ("dwMemoryLoad", ctypes.c_uint32),
            ("ullTotalPhys", ctypes.c_uint64),
            ("ullAvailPhys", ctypes.c_uint64),
            ("ullTotalPageFile", ctypes.c_uint64),
            ("ullAvailPageFile", ctypes.c_uint64),
            ("ullTotalVirtual", ctypes.c_uint64),
            ("ullAvailVirtual", ctypes.c_uint64),
            ("ullAvailExtendedVirtual", ctypes.c_uint64),
        ]

    class _MIB_IF_ROW2(ctypes.Structure):
        _fields_ = [
            ("InterfaceLuid", ctypes.c_uint64),
            ("InterfaceIndex", ctypes.c_uint32),
            ("InterfaceGuid", ctypes.c_byte * 16),
            ("Alias", ctypes.c_wchar * 257),
            ("Description", ctypes.c_wchar * 257),
            ("PhysicalAddressLength", ctypes.c_uint32),
            ("PhysicalAddress", ctypes.c_byte * 32),
            ("PermanentPhysicalAddress", ctypes.c_byte * 32),
            ("Mtu", ctypes.c_uint32),
            ("Type", ctypes.c_uint32),
            ("TunnelType", ctypes.c_uint32),
            ("MediaType", ctypes.c_uint32),
            ("PhysicalMediumType", ctypes.c_uint32),
            ("AccessType", ctypes.c_uint32),
            ("DirectionType", ctypes.c_uint32),
            ("InterfaceAndOperStatusFlags", ctypes.c_uint8),
            ("OperStatus", ctypes.c_uint32),
            ("AdminStatus", ctypes.c_uint32),
            ("MediaConnectState", ctypes.c_uint32),
            ("NetworkGuid", ctypes.c_byte * 16),
            ("ConnectionType", ctypes.c_uint32),
            ("TransmitLinkSpeed", ctypes.c_uint64),
            ("ReceiveLinkSpeed", ctypes.c_uint64),
            ("InOctets", ctypes.c_uint64),
            ("InUcastPkts", ctypes.c_uint64),
            ("InNUcastPkts", ctypes.c_uint64),
            ("InDiscards", ctypes.c_uint64),
            ("InErrors", ctypes.c_uint64),
            ("InUnknownProtos", ctypes.c_uint64),
            ("InUcastOctets", ctypes.c_uint64),
            ("InMulticastOctets", ctypes.c_uint64),
            ("InBroadcastOctets", ctypes.c_uint64),
            ("OutOctets", ctypes.c_uint64),
            ("OutUcastPkts", ctypes.c_uint64),
            ("OutNUcastPkts", ctypes.c_uint64),
            ("OutDiscards", ctypes.c_uint64),
            ("OutErrors", ctypes.c_uint64),
            ("OutUcastOctets", ctypes.c_uint64),
            ("OutMulticastOctets", ctypes.c_uint64),
            ("OutBroadcastOctets", ctypes.c_uint64),
            ("OutQLen", ctypes.c_uint64),
        ]

    class _MIB_IF_TABLE2(ctypes.Structure):
        _fields_ = [
            ("NumEntries", ctypes.c_uint32),
            ("Table", _MIB_IF_ROW2 * 1),
        ]


def _thermal_status(temp_c: int | None) -> str:
    if temp_c is None:
        return "optimal"
    if temp_c >= 82:
        return "hot"
    if temp_c >= 70:
        return "warm"
    if temp_c <= 50:
        return "cool"
    return "optimal"


def _read_sysfs(path: str | None) -> str | None:
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


#: PCI vendor ids of GPUs whose Linux drivers publish usable sysfs telemetry.
_GPU_VENDOR_NAMES = {"0x1002": "AMD Radeon", "0x8086": "Intel Graphics"}


@dataclass
class _SysfsGpu:
    """Paths under /sys/class/drm for one GPU. Any of them may be absent."""

    name: str
    busy_path: str | None = None
    temp_path: str | None = None
    vram_total_path: str | None = None
    vram_used_path: str | None = None

    def sample(self) -> GpuVitals:
        busy = _read_sysfs(self.busy_path)
        raw_temp = _read_sysfs(self.temp_path)
        temp_c = None
        if raw_temp is not None:
            try:
                temp_c = int(raw_temp) // 1000  # hwmon reports millidegrees
            except ValueError:
                temp_c = None

        def _bytes(path: str | None) -> int | None:
            raw = _read_sysfs(path)
            try:
                return int(raw) if raw is not None else None
            except ValueError:
                return None

        utilization = None
        if busy is not None:
            try:
                utilization = min(100.0, max(0.0, float(busy)))
            except ValueError:
                utilization = None

        return GpuVitals(
            available=True,
            name=self.name,
            temperature_c=temp_c,
            utilization_pct=utilization,
            vram_used_bytes=_bytes(self.vram_used_path),
            vram_total_bytes=_bytes(self.vram_total_path),
            thermal_status=_thermal_status(temp_c),
        )


def _discover_sysfs_gpu(drm_root: str = "/sys/class/drm") -> _SysfsGpu | None:
    for card in sorted(glob.glob(os.path.join(drm_root, "card[0-9]"))):
        device = os.path.join(card, "device")
        vendor = _read_sysfs(os.path.join(device, "vendor"))
        name = _GPU_VENDOR_NAMES.get((vendor or "").lower())
        if not name:
            continue

        def _present(*parts: str) -> str | None:
            candidate = os.path.join(device, *parts)
            return candidate if os.path.exists(candidate) else None

        temp_path = next(
            iter(sorted(glob.glob(os.path.join(device, "hwmon", "hwmon*", "temp1_input")))), None
        )
        gpu = _SysfsGpu(
            name=name,
            busy_path=_present("gpu_busy_percent"),
            temp_path=temp_path,
            vram_total_path=_present("mem_info_vram_total"),
            vram_used_path=_present("mem_info_vram_used"),
        )
        if gpu.busy_path or gpu.temp_path or gpu.vram_total_path:
            return gpu
    return None


class LiveMetricsCollector:
    """Singleton-style metrics collector holding previous tick deltas."""

    def __init__(self):
        self._last_time: float = 0.0
        # Network state
        self._last_in_bytes: int = 0
        self._last_out_bytes: int = 0
        self._initial_in_bytes: int = 0
        self._initial_out_bytes: int = 0
        self._first_net_sample: bool = True
        # Rate smoothing
        self._smooth_in_sec: float = 0.0
        self._smooth_out_sec: float = 0.0
        self._smooth_cpu_percent: float = 0.0
        self._primary_interface_name = "Network"
        # CPU state
        self._last_idle_time: int = 0
        self._last_kernel_time: int = 0
        self._last_user_time: int = 0
        self._last_cpu_percent: float = 0.0
        self._last_linux_total: int = 0
        self._last_linux_idle: int = 0
        self._cpu_cores = os.cpu_count() or 4
        # GPU / NVML / Sysfs state
        self._nvml = None
        self._nvml_initialized = False
        self._nvml_handle = None
        self._gpu_name = "GPU"
        self._sysfs_gpu: _SysfsGpu | None = None
        self._adapter_gpu: GpuVitals | None = None
        self._init_gpu()

    def _init_gpu(self):
        try:
            if is_windows():
                self._nvml = ctypes.CDLL("nvml.dll")
            elif is_linux():
                self._nvml = ctypes.CDLL("libnvidia-ml.so.1")
            if self._nvml and self._nvml.nvmlInit() == 0:
                device = ctypes.c_void_p()
                if self._nvml.nvmlDeviceGetHandleByIndex(0, ctypes.byref(device)) == 0:
                    self._nvml_handle = device
                    self._nvml_initialized = True
                    name_buf = ctypes.create_string_buffer(64)
                    if self._nvml.nvmlDeviceGetName(device, name_buf, 64) == 0:
                        raw_name = name_buf.value.decode("utf-8", "ignore").strip()
                        self._gpu_name = (
                            raw_name.replace("NVIDIA GeForce ", "")
                            .replace("NVIDIA ", "")
                            .replace("GeForce ", "")
                        )
        except Exception:
            self._nvml_initialized = False

        if self._nvml_initialized:
            return

        if is_linux():
            self._sysfs_gpu = _discover_sysfs_gpu()
            if self._sysfs_gpu is not None:
                self._gpu_name = self._sysfs_gpu.name
        elif is_windows():
            # A display adapter with no vendor telemetry library still has a name and
            # a VRAM size worth showing. The query talks to WMI, so it runs off the
            # sampling path and only fills in once it answers.
            threading.Thread(target=self._load_adapter_gpu, daemon=True).start()

    def _load_adapter_gpu(self) -> None:
        try:
            from crapcleaner.system.hardware import _get_gpu_specs

            specs = _get_gpu_specs()
        except Exception:
            return
        if not specs:
            return
        primary = specs[0]
        self._adapter_gpu = GpuVitals(
            available=True,
            name=primary.name or "Display Adapter",
            vram_total_bytes=primary.adapter_ram_bytes or None,
        )

    def sample(self) -> SystemLiveSnapshot:
        now = time.monotonic()
        dt = max(now - self._last_time, 0.001) if self._last_time > 0 else 1.0

        net_vitals = self._sample_network(now, dt)
        cpu_vitals = self._sample_cpu(now)
        ram_vitals = self._sample_ram()
        gpu_vitals = self._sample_gpu()
        uptime_str, power_str = self._sample_uptime_and_power()

        self._last_time = now
        return SystemLiveSnapshot(
            network=net_vitals,
            cpu=cpu_vitals,
            ram=ram_vitals,
            gpu=gpu_vitals,
            uptime_str=uptime_str,
            power_str=power_str,
            timestamp=now,
        )

    def _sample_network(self, now: float, dt: float) -> NetworkVitals:
        total_in = 0
        total_out = 0
        active_iface = "Ethernet"

        if is_windows():
            try:
                iphlpapi = ctypes.windll.iphlpapi
                pTable = ctypes.POINTER(_MIB_IF_TABLE2)()
                ret = iphlpapi.GetIfTable2(ctypes.byref(pTable))
                if ret == 0 and pTable:
                    table = pTable.contents
                    num_entries = table.NumEntries
                    row_array_type = _MIB_IF_ROW2 * num_entries
                    rows_ptr = ctypes.cast(
                        ctypes.addressof(table.Table), ctypes.POINTER(row_array_type)
                    )
                    rows = rows_ptr.contents

                    found_iface = False
                    for i in range(num_entries):
                        row = rows[i]
                        if row.Type == 24 or "loopback" in row.Description.lower():
                            continue
                        if row.InOctets > 0 or row.OutOctets > 0:
                            total_in += row.InOctets
                            total_out += row.OutOctets
                            if (
                                row.OperStatus == 1 or row.MediaConnectState == 1
                            ) and not found_iface:
                                raw_alias = (row.Alias or row.Description or "").strip()
                                if "-" in raw_alias and not raw_alias.startswith("Wi-Fi"):
                                    raw_alias = raw_alias.split("-")[0]
                                active_iface = raw_alias or "Connected"
                                found_iface = True

                    iphlpapi.FreeMibTable(pTable)
            except Exception:
                pass
        elif is_linux():
            try:
                if os.path.exists("/proc/net/dev"):
                    with open("/proc/net/dev", encoding="utf-8") as f:
                        lines = f.readlines()
                    for line in lines[2:]:
                        parts = line.split()
                        if len(parts) >= 10:
                            iface = parts[0].rstrip(":")
                            if iface != "lo":
                                r_bytes = int(parts[1])
                                t_bytes = int(parts[9])
                                total_in += r_bytes
                                total_out += t_bytes
                                if r_bytes > 0 or t_bytes > 0:
                                    active_iface = iface
            except Exception:
                pass

        if self._first_net_sample:
            self._initial_in_bytes = total_in
            self._initial_out_bytes = total_out
            self._last_in_bytes = total_in
            self._last_out_bytes = total_out
            self._first_net_sample = False
            raw_in_sec = 0.0
            raw_out_sec = 0.0
            self._smooth_in_sec = 0.0
            self._smooth_out_sec = 0.0
        else:
            delta_in = max(0, total_in - self._last_in_bytes)
            delta_out = max(0, total_out - self._last_out_bytes)
            raw_in_sec = delta_in / dt
            raw_out_sec = delta_out / dt
            self._last_in_bytes = total_in
            self._last_out_bytes = total_out

            if self._smooth_in_sec == 0.0 and raw_in_sec > 0:
                self._smooth_in_sec = raw_in_sec
            else:
                self._smooth_in_sec = 0.60 * raw_in_sec + 0.40 * self._smooth_in_sec

            if self._smooth_out_sec == 0.0 and raw_out_sec > 0:
                self._smooth_out_sec = raw_out_sec
            else:
                self._smooth_out_sec = 0.60 * raw_out_sec + 0.40 * self._smooth_out_sec

        session_in = max(0, total_in - self._initial_in_bytes)
        session_out = max(0, total_out - self._initial_out_bytes)

        return NetworkVitals(
            bytes_in_sec=self._smooth_in_sec,
            bytes_out_sec=self._smooth_out_sec,
            total_in_bytes=session_in,
            total_out_bytes=session_out,
            interface_name=active_iface,
            is_connected=total_in > 0 or total_out > 0,
        )

    def _sample_cpu(self, now: float) -> CpuVitals:
        cpu_percent = self._last_cpu_percent

        if is_windows():
            try:
                idle = _FILETIME()
                kernel = _FILETIME()
                user = _FILETIME()
                if ctypes.windll.kernel32.GetSystemTimes(
                    ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
                ):
                    curr_idle = idle.to_uint64()
                    curr_kernel = kernel.to_uint64()
                    curr_user = user.to_uint64()

                    if self._last_kernel_time > 0:
                        d_idle = curr_idle - self._last_idle_time
                        d_kernel = curr_kernel - self._last_kernel_time
                        d_user = curr_user - self._last_user_time
                        total_sys = d_kernel + d_user
                        if total_sys > 0:
                            used = max(0, total_sys - d_idle)
                            cpu_percent = round((used / total_sys) * 100.0, 1)

                    self._last_idle_time = curr_idle
                    self._last_kernel_time = curr_kernel
                    self._last_user_time = curr_user
            except Exception:
                pass
        elif is_linux():
            try:
                if os.path.exists("/proc/stat"):
                    with open("/proc/stat", encoding="utf-8") as f:
                        line = f.readline()
                    parts = [int(x) for x in line.split()[1:]]
                    linux_idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
                    total = sum(parts)
                    if self._last_linux_total > 0:
                        d_total = total - self._last_linux_total
                        d_idle = linux_idle - self._last_linux_idle
                        if d_total > 0:
                            cpu_percent = round(((d_total - d_idle) / d_total) * 100.0, 1)
                    self._last_linux_total = total
                    self._last_linux_idle = linux_idle
            except Exception:
                pass

        raw_cpu = min(max(cpu_percent, 0.0), 100.0)
        if self._smooth_cpu_percent == 0.0 and raw_cpu > 0:
            self._smooth_cpu_percent = raw_cpu
        else:
            self._smooth_cpu_percent = round(0.65 * raw_cpu + 0.35 * self._smooth_cpu_percent, 1)

        self._last_cpu_percent = self._smooth_cpu_percent
        return CpuVitals(
            percent_used=self._last_cpu_percent,
            logical_cores=self._cpu_cores,
            physical_cores=max(1, self._cpu_cores // 2),
        )

    def _sample_ram(self) -> RamVitals:
        used = 0
        total = 0
        available = 0
        pct = 0.0

        if is_windows():
            try:
                mem = _MEMORYSTATUSEX()
                mem.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
                    total = mem.ullTotalPhys
                    available = mem.ullAvailPhys
                    used = max(0, total - available)
                    pct = float(mem.dwMemoryLoad)
            except Exception:
                pass
        elif is_linux():
            try:
                if os.path.exists("/proc/meminfo"):
                    info = {}
                    with open("/proc/meminfo", encoding="utf-8") as f:
                        for line in f:
                            parts = line.split(":")
                            if len(parts) == 2:
                                k = parts[0].strip()
                                v = parts[1].strip().split()[0]
                                info[k] = int(v) * 1024
                    total = info.get("MemTotal", 0)
                    available = info.get("MemAvailable", info.get("MemFree", 0))
                    used = max(0, total - available)
                    if total > 0:
                        pct = round((used / total) * 100.0, 1)
            except Exception:
                pass

        pressure = "normal"
        if pct >= 90.0:
            pressure = "critical"
        elif pct >= 75.0:
            pressure = "high"
        elif pct <= 35.0:
            pressure = "low"

        return RamVitals(
            used_bytes=used,
            total_bytes=total,
            available_bytes=available,
            percent_used=pct,
            pressure=pressure,
        )

    def _sample_gpu(self) -> GpuVitals:
        if self._nvml_initialized and self._nvml_handle and self._nvml:
            try:
                temp = ctypes.c_uint32()
                self._nvml.nvmlDeviceGetTemperature(self._nvml_handle, 0, ctypes.byref(temp))
                t_val = int(temp.value)

                class _nvmlUtilization_t(ctypes.Structure):
                    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

                util = _nvmlUtilization_t()
                self._nvml.nvmlDeviceGetUtilizationRates(self._nvml_handle, ctypes.byref(util))

                class _nvmlMemory_t(ctypes.Structure):
                    _fields_ = [
                        ("total", ctypes.c_ulonglong),
                        ("free", ctypes.c_ulonglong),
                        ("used", ctypes.c_ulonglong),
                    ]

                mem = _nvmlMemory_t()
                self._nvml.nvmlDeviceGetMemoryInfo(self._nvml_handle, ctypes.byref(mem))

                return GpuVitals(
                    available=True,
                    name=self._gpu_name,
                    temperature_c=t_val,
                    utilization_pct=float(util.gpu),
                    vram_used_bytes=int(mem.used),
                    vram_total_bytes=int(mem.total),
                    thermal_status=_thermal_status(t_val),
                )
            except Exception:
                return GpuVitals()

        if self._sysfs_gpu is not None:
            return self._sysfs_gpu.sample()

        if self._adapter_gpu is not None:
            return self._adapter_gpu

        return GpuVitals()

    def _sample_uptime_and_power(self) -> tuple[str, str]:
        uptime_str = ""
        power_str = "AC Power"
        if is_windows():
            try:
                sec = ctypes.windll.kernel32.GetTickCount64() // 1000
                hours, remainder = divmod(sec, 3600)
                minutes, _ = divmod(remainder, 60)
                days, hours = divmod(hours, 24)
                if days > 0:
                    uptime_str = f"{days}d {hours}h"
                else:
                    uptime_str = f"{hours}h {minutes}m"

                class _SYSTEM_POWER_STATUS(ctypes.Structure):
                    _fields_ = [
                        ("ACLineStatus", ctypes.c_byte),
                        ("BatteryFlag", ctypes.c_byte),
                        ("BatteryLifePercent", ctypes.c_byte),
                        ("SystemStatusFlag", ctypes.c_byte),
                        ("BatteryLifeTime", ctypes.c_ulong),
                        ("BatteryFullLifeTime", ctypes.c_ulong),
                    ]

                sps = _SYSTEM_POWER_STATUS()
                if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
                    if sps.BatteryLifePercent != -1 and sps.BatteryLifePercent <= 100:
                        ac_txt = "Charging" if sps.ACLineStatus == 1 else "Battery"
                        power_str = f"{ac_txt} {sps.BatteryLifePercent}%"
                    else:
                        power_str = "AC Power"
            except Exception:
                pass
        elif is_linux():
            try:
                if os.path.exists("/proc/uptime"):
                    with open("/proc/uptime", encoding="utf-8") as f:
                        sec = int(float(f.readline().split()[0]))
                    hours, remainder = divmod(sec, 3600)
                    minutes, _ = divmod(remainder, 60)
                    days, hours = divmod(hours, 24)
                    if days > 0:
                        uptime_str = f"{days}d {hours}h"
                    else:
                        uptime_str = f"{hours}h {minutes}m"
            except Exception:
                pass
        return uptime_str, power_str


# Global singleton instance
_collector: LiveMetricsCollector | None = None


def get_live_metrics_collector() -> LiveMetricsCollector:
    global _collector
    if _collector is None:
        _collector = LiveMetricsCollector()
    return _collector


def sample_live_metrics() -> SystemLiveSnapshot:
    return get_live_metrics_collector().sample()
