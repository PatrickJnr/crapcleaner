"""Hardware and Operating System specifications inspector.

Collects detailed hardware and system metrics including CPU, RAM, GPU, Motherboard,
Storage drives, Network adapters, and OS build info.
"""

import json
import os
import platform
import socket
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from crapcleaner.config import offline_mode
from crapcleaner.utils.format import format_size
from crapcleaner.utils.logs import get_logger
from crapcleaner.utils.platform import (
    get_drive_info,
    is_linux,
    is_windows,
    list_drives,
    run_command,
    which,
)

logger = get_logger("hardware")


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
    except Exception as exc:
        logger.debug("windows uptime probe failed: %s", exc)
        return "N/A"


def _get_linux_uptime() -> str:
    try:
        with open("/proc/uptime", encoding="utf-8") as fh:
            seconds = int(float(fh.read().split()[0]))
        return _format_uptime(seconds)
    except Exception as exc:
        logger.debug("linux uptime probe failed: %s", exc)
        return "N/A"


def _read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError as exc:
        logger.debug("probe could not read %s: %s", path, exc)
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
    except OSError as exc:
        logger.debug("probe could not read %s: %s", path, exc)
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
                    # ProductName still reads "Windows 10" on Windows 11; only the
                    # build number distinguishes them.
                    if int(build_str) >= 22000 and "Windows 10" in edition:
                        edition = edition.replace("Windows 10", "Windows 11")
                except (OSError, ValueError) as exc:
                    logger.debug("windows build number probe failed: %s", exc)
        except Exception as exc:
            logger.debug("windows edition probe failed: %s", exc)
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


def os_label() -> str:
    """The operating system as a person would name it, with its architecture.

    `platform.release()` answers "10" on Windows 11, so this uses the registry
    product name on Windows and `PRETTY_NAME` on Linux.
    """
    specs = _get_os_specs()
    name = specs.name or f"{platform.system()} {platform.release()}"
    arch = {"AMD64": "64-bit", "x86_64": "64-bit", "arm64": "ARM64", "aarch64": "ARM64"}.get(
        specs.architecture, specs.architecture
    )
    return f"{name} ({arch})" if arch else name


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
        except Exception as exc:
            logger.debug("windows cpu probe failed: %s", exc)
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
        except Exception as exc:
            logger.debug("windows memory probe failed: %s", exc)
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


def _get_windows_gpu_registry() -> list[dict]:
    """Read full 64-bit GPU VRAM and driver details from Windows Registry to bypass 32-bit WMI caps."""
    gpus_reg = []
    guid_key = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
    try:
        import struct
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, guid_key) as k:
            num_subkeys = winreg.QueryInfoKey(k)[0]
            for i in range(num_subkeys):
                sub_name = winreg.EnumKey(k, i)
                if not sub_name.isdigit():
                    continue
                try:
                    with winreg.OpenKey(k, sub_name) as sub:
                        try:
                            desc, _ = winreg.QueryValueEx(sub, "DriverDesc")
                            desc = str(desc).strip()
                        except OSError:
                            continue

                        vram = 0
                        for qword_name in (
                            "HardwareInformation.qwMemorySize",
                            "qwMemorySize",
                        ):
                            try:
                                v, _ = winreg.QueryValueEx(sub, qword_name)
                                if isinstance(v, int) and v > 0:
                                    vram = v
                                    break
                                elif isinstance(v, bytes) and len(v) >= 8:
                                    vram = struct.unpack("<Q", v[:8])[0]
                                    if vram > 0:
                                        break
                            except OSError:
                                pass

                        if not vram:
                            for dword_name in (
                                "HardwareInformation.MemorySize",
                                "MemorySize",
                            ):
                                try:
                                    v, _ = winreg.QueryValueEx(sub, dword_name)
                                    if isinstance(v, int) and v > 0:
                                        vram = v
                                        break
                                    elif isinstance(v, bytes) and len(v) >= 4:
                                        vram = struct.unpack("<I", v[:4])[0]
                                        if vram > 0:
                                            break
                                except OSError:
                                    pass

                        drv = ""
                        try:
                            drv_val, _ = winreg.QueryValueEx(sub, "DriverVersion")
                            drv = str(drv_val).strip()
                        except OSError:
                            pass

                        gpus_reg.append(
                            {
                                "name": desc,
                                "driver_version": drv,
                                "vram": vram,
                            }
                        )
                except OSError as exc:
                    logger.debug("gpu registry subkey probe failed: %s", exc)
                    continue
    except Exception as exc:
        logger.debug("gpu registry probe failed: %s", exc)
    return gpus_reg


def _get_nvidia_smi_vram() -> dict[str, int]:
    """Query nvidia-smi if available to get exact VRAM in bytes."""
    vram_map = {}
    smi = which("nvidia-smi")
    if not smi and os.name == "nt":
        for cand in [
            os.path.expandvars(r"%ProgramFiles%\NVIDIA Corporation\NVSMI\nvidia-smi.exe"),
            os.path.expandvars(r"%SystemRoot%\System32\nvidia-smi.exe"),
        ]:
            if os.path.exists(cand):
                smi = cand
                break
    if smi:
        try:
            out = run_command(
                [smi, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                timeout=4.0,
            )
            if out.ok:
                for line in out.stdout.splitlines():
                    if "," in line:
                        g_name, mem_mb = line.split(",", 1)
                        try:
                            vram_map[g_name.strip().lower()] = (
                                int(float(mem_mb.strip())) * 1024 * 1024
                            )
                        except ValueError as exc:
                            logger.debug("nvidia-smi vram value unreadable: %s", exc)
        except Exception as exc:
            logger.debug("nvidia-smi probe failed: %s", exc)
    return vram_map


def _get_gpu_specs() -> list[GpuSpec]:
    gpus: list[GpuSpec] = []
    if os.name == "nt":
        reg_gpus = _get_windows_gpu_registry()
        smi_vram = _get_nvidia_smi_vram()

        wmi_gpus = []
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM, VideoModeDescription | ConvertTo-Json -Compress",
        ]
        try:
            res = run_command(cmd, timeout=5.0)
            if res.ok and res.stdout.strip():
                raw = json.loads(res.stdout.strip())
                items = [raw] if isinstance(raw, dict) else raw
                for item in items:
                    name = item.get("Name") or "Unknown GPU"
                    drv = item.get("DriverVersion") or ""
                    ram = int(item.get("AdapterRAM") or 0)
                    mode = item.get("VideoModeDescription") or ""
                    wmi_gpus.append(
                        {
                            "name": name,
                            "driver_version": drv,
                            "adapter_ram_bytes": ram,
                            "resolution": mode,
                        }
                    )
        except Exception as exc:
            logger.debug("wmi gpu probe failed: %s", exc)

        # Match WMI and Registry GPUs to obtain true 64-bit VRAM
        matched_reg_indices = set()
        for wmi in wmi_gpus:
            w_name = str(wmi.get("name", ""))
            w_lower = w_name.lower()
            drv = str(wmi.get("driver_version", ""))
            ram = int(wmi.get("adapter_ram_bytes", 0))
            mode = str(wmi.get("resolution", ""))

            best_vram = ram
            for idx, reg in enumerate(reg_gpus):
                r_lower = str(reg.get("name", "")).lower()
                if r_lower in w_lower or w_lower in r_lower:
                    matched_reg_indices.add(idx)
                    r_vram = int(reg.get("vram", 0))
                    if r_vram > best_vram or (best_vram >= 4293918720 and r_vram > 0):
                        best_vram = r_vram
                    if not drv and reg.get("driver_version"):
                        drv = str(reg["driver_version"])
                    break

            for smi_name, smi_bytes in smi_vram.items():
                if smi_name in w_lower or w_lower in smi_name:
                    if smi_bytes > best_vram or (best_vram >= 4293918720 and smi_bytes > 0):
                        best_vram = smi_bytes
                    break

            gpus.append(
                GpuSpec(
                    name=w_name,
                    driver_version=drv,
                    adapter_ram_bytes=best_vram,
                    resolution=mode,
                )
            )

        for idx, reg in enumerate(reg_gpus):
            if idx not in matched_reg_indices:
                r_name = reg["name"]
                r_lower = r_name.lower()
                best_vram = reg["vram"]
                for smi_name, smi_bytes in smi_vram.items():
                    if smi_name in r_lower or r_lower in smi_name:
                        if smi_bytes > best_vram:
                            best_vram = smi_bytes
                        break
                gpus.append(
                    GpuSpec(
                        name=r_name,
                        driver_version=reg["driver_version"],
                        adapter_ram_bytes=best_vram,
                    )
                )

    elif is_linux():
        smi_vram = _get_nvidia_smi_vram()
        lspci = which("lspci")
        if lspci:
            try:
                res = run_command([lspci], timeout=5.0)
                if res.ok:
                    for line in res.stdout.splitlines():
                        lowered = line.lower()
                        if "vga compatible controller" in lowered or "3d controller" in lowered:
                            name = line.split(": ", 1)[1].strip() if ": " in line else line.strip()
                            vram = 0
                            for smi_name, smi_bytes in smi_vram.items():
                                if smi_name in name.lower() or name.lower() in smi_name:
                                    vram = smi_bytes
                                    break
                            gpus.append(GpuSpec(name=name, adapter_ram_bytes=vram))
            except Exception as exc:
                logger.debug("lspci gpu probe failed: %s", exc)
        if not gpus:
            drm_cards = "/sys/class/drm"
            try:
                for entry in sorted(os.listdir(drm_cards)):
                    if not entry.startswith("card") or "-" in entry:
                        continue
                    device_path = os.path.join(drm_cards, entry, "device")
                    vendor = _read_text(os.path.join(device_path, "vendor"))
                    device = _read_text(os.path.join(device_path, "device"))
                    vram_file = os.path.join(device_path, "mem_info_vram_total")
                    vram = 0
                    if os.path.exists(vram_file):
                        try:
                            vram = int(_read_text(vram_file).strip())
                        except ValueError:
                            pass
                    if vendor or device:
                        gpus.append(
                            GpuSpec(
                                name=f"GPU {entry} ({vendor} {device})".strip(),
                                adapter_ram_bytes=vram,
                            )
                        )
            except OSError as exc:
                logger.debug("drm gpu probe failed: %s", exc)

    if not gpus:
        gpus.append(GpuSpec(name="Standard Display Adapter"))

    def _gpu_sort_priority(g: GpuSpec) -> int:
        low = g.name.lower()
        if any(k in low for k in ["rtx", "gtx", "geforce", "nvidia", "radeon", "rx ", "arc "]):
            return 0
        if any(v in low for v in ["virtual", "basic", "remote", "citrix", "spacedesk"]):
            return 2
        return 1

    gpus.sort(key=_gpu_sort_priority)
    return gpus


def _get_drive_specs() -> list[DriveSpec]:
    drive_specs: list[DriveSpec] = []
    drives = [d.rstrip("\\") if is_windows() else d for d in list_drives()]
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
        except Exception as exc:
            logger.debug("drive probe failed for %s: %s", d, exc)
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
                except OSError as exc:
                    logger.debug("board manufacturer probe failed: %s", exc)
                try:
                    prod_val, _ = winreg.QueryValueEx(key, "BaseBoardProduct")
                    prod = str(prod_val)
                except OSError as exc:
                    logger.debug("board product probe failed: %s", exc)
                try:
                    bios_val, _ = winreg.QueryValueEx(key, "BIOSVersion")
                    bios_ver = str(bios_val)
                except OSError as exc:
                    logger.debug("bios version probe failed: %s", exc)
                try:
                    date_val, _ = winreg.QueryValueEx(key, "BIOSReleaseDate")
                    bios_date = str(date_val)
                except OSError as exc:
                    logger.debug("bios release date probe failed: %s", exc)
        except Exception as exc:
            logger.debug("motherboard probe failed: %s", exc)
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

    # stdlib first: PowerShell subprocesses have crashed on Windows CI when this
    # runs from a Qt worker thread.
    hostname = socket.gethostname()
    ip = "127.0.0.1"
    if not offline_mode():
        try:
            ip = socket.gethostbyname(hostname)
        except OSError as exc:
            logger.debug("hostname resolution probe failed: %s", exc)
    if ip and not ip.startswith("127."):
        adapters.append(
            NetworkSpec(
                adapter_name="Primary Network Interface",
                ip_address=ip,
                mac_address="",
                status="Connected",
            )
        )

    if adapters:
        return adapters

    return [
        NetworkSpec(
            adapter_name="Primary Network Interface",
            ip_address=ip,
            mac_address="",
            status="Connected",
        )
    ]


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
    """Print a clean formatted summary to the console."""
    if json_output:
        print(specs.to_json())
        return

    print("=" * 65)
    print(" CrapCleaner System Hardware & OS Specifications")
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
        drive_name = d.drive if d.drive.endswith(":") or not is_windows() else f"{d.drive}:"
        prefix = f"Drive {drive_name}" if is_windows() else drive_name
        print(
            f"  - {prefix}{label_str}{fs_str} "
            f"{format_size(d.used_bytes)} / {format_size(d.total_bytes)} ({d.percent_used}% full) | Free: {format_size(d.free_bytes)}"
        )
    print("=" * 65)
