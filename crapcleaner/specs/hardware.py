"""Hardware and Operating System specifications inspector (Speccy-style).

Collects detailed hardware and system metrics including CPU, RAM, GPU, Motherboard,
Storage drives, Network adapters, and OS build info.
"""

import json
import os
import platform
import socket
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from crapcleaner.utils.format import format_size
from crapcleaner.utils.platform import get_drive_info, is_linux, list_drives, which


@dataclass
class OsSpec:
    name: str = ""
    edition: str = ""
    version: str = ""
    build_number: str = ""
    architecture: str = ""
    uptime: str = ""
    computer_name: str = ""
    user_name: str = ""


@dataclass
class CpuSpec:
    name: str = ""
    architecture: str = ""
    cores_physical: int = 0
    cores_logical: int = 0
    max_clock_speed_mhz: int = 0


@dataclass
class MemorySpec:
    total_bytes: int = 0
    available_bytes: int = 0
    used_bytes: int = 0
    percent_used: float = 0.0


@dataclass
class GpuSpec:
    name: str = ""
    driver_version: str = ""
    adapter_ram_bytes: int = 0
    resolution: str = ""
    refresh_rate_hz: int = 0


@dataclass
class DriveSpec:
    drive: str = ""
    label: str = ""
    file_system: str = ""
    total_bytes: int = 0
    free_bytes: int = 0
    used_bytes: int = 0
    percent_used: int = 0


@dataclass
class MotherboardSpec:
    manufacturer: str = ""
    product: str = ""
    bios_version: str = ""
    bios_date: str = ""


@dataclass
class NetworkSpec:
    adapter_name: str = ""
    ip_address: str = ""
    mac_address: str = ""
    status: str = "Connected"


@dataclass
class SystemSpecs:
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    os: OsSpec = field(default_factory=OsSpec)
    cpu: CpuSpec = field(default_factory=CpuSpec)
    memory: MemorySpec = field(default_factory=MemorySpec)
    gpus: list[GpuSpec] = field(default_factory=list)
    drives: list[DriveSpec] = field(default_factory=list)
    motherboard: MotherboardSpec = field(default_factory=MotherboardSpec)
    network: list[NetworkSpec] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def _format_uptime(seconds: int) -> str:
    days, rem = divmod(max(seconds, 0), 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hours}h {mins}m"
    return f"{hours}h {mins}m {secs}s"


def _get_windows_uptime() -> str:
    if os.name != "nt":
        return "N/A"
    try:
        import ctypes

        lib = ctypes.windll.kernel32
        ticks = lib.GetTickCount64()
        return _format_uptime(int(ticks / 1000))
    except Exception:
        return "N/A"


def _get_linux_uptime() -> str:
    try:
        with open("/proc/uptime", encoding="utf-8") as fh:
            seconds = int(float(fh.read().split()[0]))
        return _format_uptime(seconds)
    except Exception:
        return "N/A"


def _read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _read_key_value_file(path: str, sep: str = ":") -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if sep not in line:
                    continue
                key, value = line.split(sep, 1)
                values[key.strip()] = value.strip()
    except OSError:
        pass
    return values


def _get_os_specs() -> OsSpec:
    os_name = f"{platform.system()} {platform.release()}"
    version = platform.version()
    build = version
    arch = platform.machine()
    computer = platform.node()
    user = os.environ.get("USERNAME") or os.environ.get("USER", "")
    edition = ""
    uptime = _get_windows_uptime() if os.name == "nt" else "N/A"

    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
            ) as key:
                product_name, _ = winreg.QueryValueEx(key, "ProductName")
                edition = str(product_name)
                try:
                    display_ver, _ = winreg.QueryValueEx(key, "DisplayVersion")
                    build_str, _ = winreg.QueryValueEx(key, "CurrentBuildNumber")
                    build = f"{display_ver} (Build {build_str})"
                except OSError:
                    pass
        except Exception:
            pass
    elif is_linux():
        os_release = _read_key_value_file("/etc/os-release", sep="=")
        pretty = os_release.get("PRETTY_NAME", "").strip('"')
        os_version = os_release.get("VERSION", "").strip('"')
        version_id = os_release.get("VERSION_ID", "").strip('"')
        edition = pretty or os_release.get("NAME", "").strip('"')
        os_name = edition or os_name
        version = version_id or os_version or version
        build = f"Kernel {platform.release()}"
        uptime = _get_linux_uptime()

    return OsSpec(
        name=edition or os_name,
        edition=edition,
        version=version,
        build_number=build,
        architecture=arch,
        uptime=uptime,
        computer_name=computer,
        user_name=user,
    )


def _get_cpu_specs() -> CpuSpec:
    cpu_name = platform.processor() or "Unknown CPU"
    cores_logical = os.cpu_count() or 1
    cores_physical = max(1, cores_logical // 2)
    clock_speed = 0

    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:
                name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                cpu_name = str(name).strip()
                try:
                    mhz, _ = winreg.QueryValueEx(key, "~MHz")
                    clock_speed = int(mhz)
                except OSError:
                    clock_speed = 0
                return CpuSpec(
                    name=cpu_name,
                    architecture=platform.machine(),
                    cores_physical=cores_physical,
                    cores_logical=cores_logical,
                    max_clock_speed_mhz=clock_speed,
                )
        except Exception:
            pass
    elif is_linux():
        cpuinfo = _read_key_value_file("/proc/cpuinfo")
        cpu_name = cpuinfo.get("model name") or cpuinfo.get("Hardware") or cpu_name
        mhz = cpuinfo.get("cpu MHz", "")
        try:
            clock_speed = int(float(mhz)) if mhz else 0
        except ValueError:
            clock_speed = 0
        physical_ids: set[str] = set()
        core_pairs: set[tuple[str, str]] = set()
        current_physical = "0"
        for line in _read_text("/proc/cpuinfo").splitlines():
            if ":" not in line:
                continue
            k, val = [part.strip() for part in line.split(":", 1)]
            if k == "physical id":
                current_physical = val
                physical_ids.add(val)
            elif k == "core id":
                core_pairs.add((current_physical, val))
        if core_pairs:
            cores_physical = len(core_pairs)
        elif physical_ids:
            cpu_cores = cpuinfo.get("cpu cores", "")
            try:
                cores_physical = max(1, int(cpu_cores) * len(physical_ids))
            except ValueError:
                pass

    return CpuSpec(
        name=cpu_name,
        architecture=platform.machine(),
        cores_physical=cores_physical,
        cores_logical=cores_logical,
        max_clock_speed_mhz=clock_speed,
    )


def _get_memory_specs() -> MemorySpec:
    if os.name == "nt":
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
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total = int(stat.ullTotalPhys)
                avail = int(stat.ullAvailPhys)
                used = max(0, total - avail)
                pct = round((used / total * 100) if total else 0.0, 1)
                return MemorySpec(
                    total_bytes=total,
                    available_bytes=avail,
                    used_bytes=used,
                    percent_used=pct,
                )
        except Exception:
            pass
    elif is_linux():
        meminfo = _read_key_value_file("/proc/meminfo")
        try:
            total = int(meminfo.get("MemTotal", "0 kB").split()[0]) * 1024
            avail = int(meminfo.get("MemAvailable", "0 kB").split()[0]) * 1024
            used = max(0, total - avail)
            pct = round((used / total * 100) if total else 0.0, 1)
            return MemorySpec(
                total_bytes=total,
                available_bytes=avail,
                used_bytes=used,
                percent_used=pct,
            )
        except (ValueError, IndexError):
            pass

    return MemorySpec()


def _get_gpu_specs() -> list[GpuSpec]:
    gpus: list[GpuSpec] = []
    if os.name == "nt":
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM, VideoModeDescription | ConvertTo-Json -Compress",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                raw = json.loads(res.stdout.strip())
                items = [raw] if isinstance(raw, dict) else raw
                for item in items:
                    name = item.get("Name") or "Unknown GPU"
                    drv = item.get("DriverVersion") or ""
                    ram = int(item.get("AdapterRAM") or 0)
                    mode = item.get("VideoModeDescription") or ""
                    gpus.append(
                        GpuSpec(
                            name=name,
                            driver_version=drv,
                            adapter_ram_bytes=ram,
                            resolution=mode,
                        )
                    )
        except Exception:
            pass
    elif is_linux():
        lspci = which("lspci")
        if lspci:
            try:
                res = subprocess.run([lspci], capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        lowered = line.lower()
                        if "vga compatible controller" in lowered or "3d controller" in lowered:
                            name = line.split(": ", 1)[1].strip() if ": " in line else line.strip()
                            gpus.append(GpuSpec(name=name))
            except Exception:
                pass
        if not gpus:
            drm_cards = "/sys/class/drm"
            try:
                for entry in sorted(os.listdir(drm_cards)):
                    if not entry.startswith("card") or "-" in entry:
                        continue
                    device_path = os.path.join(drm_cards, entry, "device")
                    vendor = _read_text(os.path.join(device_path, "vendor"))
                    device = _read_text(os.path.join(device_path, "device"))
                    if vendor or device:
                        gpus.append(GpuSpec(name=f"GPU {entry} ({vendor} {device})".strip()))
            except OSError:
                pass

    if not gpus:
        gpus.append(GpuSpec(name="Standard Display Adapter"))
    return gpus


def _get_drive_specs() -> list[DriveSpec]:
    drive_specs: list[DriveSpec] = []
    drives = [d.rstrip("\\") for d in list_drives()]
    for d in drives:
        try:
            info = get_drive_info(d)
            total = int(info.get("total", 0))
            free = int(info.get("free", 0))
            used = int(info.get("used", 0))
            pct = int(used / total * 100) if total else 0
            drive_specs.append(
                DriveSpec(
                    drive=d,
                    label=str(info.get("label", "")),
                    file_system=str(info.get("filesystem", "")),
                    total_bytes=total,
                    free_bytes=free,
                    used_bytes=used,
                    percent_used=pct,
                )
            )
        except Exception:
            pass
    return drive_specs


def _get_motherboard_specs() -> MotherboardSpec:
    mfg = ""
    prod = ""
    bios_ver = ""
    bios_date = ""

    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\BIOS",
            ) as key:
                try:
                    mfg_val, _ = winreg.QueryValueEx(key, "BaseBoardManufacturer")
                    mfg = str(mfg_val)
                except OSError:
                    pass
                try:
                    prod_val, _ = winreg.QueryValueEx(key, "BaseBoardProduct")
                    prod = str(prod_val)
                except OSError:
                    pass
                try:
                    bios_val, _ = winreg.QueryValueEx(key, "BIOSVersion")
                    bios_ver = str(bios_val)
                except OSError:
                    pass
                try:
                    date_val, _ = winreg.QueryValueEx(key, "BIOSReleaseDate")
                    bios_date = str(date_val)
                except OSError:
                    pass
        except Exception:
            pass
    elif is_linux():
        mfg = _read_text("/sys/class/dmi/id/board_vendor") or _read_text(
            "/sys/class/dmi/id/sys_vendor"
        )
        prod = _read_text("/sys/class/dmi/id/board_name") or _read_text(
            "/sys/class/dmi/id/product_name"
        )
        bios_ver = _read_text("/sys/class/dmi/id/bios_version")
        bios_date = _read_text("/sys/class/dmi/id/bios_date")

    return MotherboardSpec(
        manufacturer=mfg or "Unknown Manufacturer",
        product=prod or "Unknown Model",
        bios_version=bios_ver or "N/A",
        bios_date=bios_date or "N/A",
    )


def _get_network_specs() -> list[NetworkSpec]:
    adapters: list[NetworkSpec] = []
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except Exception:
        ip = "127.0.0.1"

    adapters.append(
        NetworkSpec(
            adapter_name="Primary Network Interface",
            ip_address=ip,
            mac_address="",
            status="Connected",
        )
    )
    return adapters


def get_system_specs() -> SystemSpecs:
    """Collect full system hardware, memory, drive, and OS metrics."""
    return SystemSpecs(
        os=_get_os_specs(),
        cpu=_get_cpu_specs(),
        memory=_get_memory_specs(),
        gpus=_get_gpu_specs(),
        drives=_get_drive_specs(),
        motherboard=_get_motherboard_specs(),
        network=_get_network_specs(),
    )


def print_specs_summary(specs: SystemSpecs, json_output: bool = False) -> None:
    """Print a clean Speccy-style formatted summary to the console."""
    if json_output:
        print(specs.to_json())
        return

    print("=" * 65)
    print(" CrapCleaner System Hardware & OS Specifications (Speccy)")
    print("=" * 65)
    print(f"Operating System:  {specs.os.name} {specs.os.architecture}")
    print(f"                   {specs.os.build_number} (Uptime: {specs.os.uptime})")
    print(f"Computer / User:   {specs.os.computer_name} \\ {specs.os.user_name}")
    print("-" * 65)
    print(f"Processor (CPU):   {specs.cpu.name}")
    print(
        f"                   {specs.cpu.cores_physical} Cores, {specs.cpu.cores_logical} Logical Processors"
    )
    if specs.cpu.max_clock_speed_mhz:
        print(f"                   Base Speed: {specs.cpu.max_clock_speed_mhz} MHz")
    print("-" * 65)
    mem_used = format_size(specs.memory.used_bytes)
    mem_tot = format_size(specs.memory.total_bytes)
    mem_free = format_size(specs.memory.available_bytes)
    print(f"Memory (RAM):      {mem_used} used / {mem_tot} ({specs.memory.percent_used}% load)")
    print(f"                   Available: {mem_free}")
    print("-" * 65)
    print(f"Motherboard:       {specs.motherboard.manufacturer} {specs.motherboard.product}")
    print(f"BIOS Version:      {specs.motherboard.bios_version} ({specs.motherboard.bios_date})")
    print("-" * 65)
    for i, gpu in enumerate(specs.gpus):
        ram_str = f" ({format_size(gpu.adapter_ram_bytes)} VRAM)" if gpu.adapter_ram_bytes else ""
        res_str = f" - {gpu.resolution}" if gpu.resolution else ""
        print(f"Graphics (GPU {i + 1}):   {gpu.name}{ram_str}")
        if gpu.driver_version:
            print(f"                   Driver: {gpu.driver_version}{res_str}")
    print("-" * 65)
    print("Storage Drives:")
    for d in specs.drives:
        fs_str = f" [{d.file_system}]" if d.file_system else ""
        label_str = f" ({d.label})" if d.label else ""
        print(
            f"  - Drive {d.drive}:{label_str}{fs_str} "
            f"{format_size(d.used_bytes)} / {format_size(d.total_bytes)} ({d.percent_used}% full) | Free: {format_size(d.free_bytes)}"
        )
    print("=" * 65)
