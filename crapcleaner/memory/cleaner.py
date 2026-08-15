"""Safe, transparent memory reclamation actions.

Nothing here terminates processes, touches another application's working set,
or resets a GPU. Every action states exactly what the operating system is asked
to do, and unsupported actions are reported instead of attempted.
"""

import os
import subprocess
from dataclasses import asdict, dataclass, field

from crapcleaner.memory.report import MemoryStats, get_gpu_memory, get_memory_stats
from crapcleaner.utils.platform import is_admin, is_linux, is_windows

RAM = "ram"
VRAM = "vram"


@dataclass
class MemoryAction:
    id: str
    name: str
    kind: str
    description: str
    effect: str
    requires_admin: bool = False
    supported: bool = True
    unsupported_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MemoryActionResult:
    action_id: str = ""
    success: bool = False
    message: str = ""
    dry_run: bool = False
    reclaimed_bytes: int = 0
    measurable: bool = True
    before: MemoryStats = field(default_factory=MemoryStats)
    after: MemoryStats = field(default_factory=MemoryStats)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["before"] = self.before.to_dict()
        data["after"] = self.after.to_dict()
        return data


def _working_set_action() -> MemoryAction:
    return MemoryAction(
        id="working_set",
        name="Release CrapCleaner's own memory",
        kind=RAM,
        description=(
            "Asks the operating system to trim this application's own working set and "
            "return unused heap pages. It never touches other processes."
        ),
        effect=(
            "Windows: SetProcessWorkingSetSize on our own process. "
            "Linux: malloc_trim on our own heap."
        ),
    )


def _standby_action() -> MemoryAction:
    supported = is_windows()
    return MemoryAction(
        id="standby_list",
        name="Purge the Windows standby list",
        kind=RAM,
        description=(
            "Discards cached file data the system is holding in the standby list. "
            "That memory is already available to applications on demand, so this "
            "mainly changes how memory is reported. Files re-read from disk afterwards "
            "will be slower until the cache warms up again."
        ),
        effect="NtSetSystemInformation(SystemMemoryListInformation, MemoryPurgeStandbyList).",
        requires_admin=True,
        supported=supported,
        unsupported_reason="" if supported else "The standby list only exists on Windows.",
    )


def _fs_cache_action() -> MemoryAction:
    supported = is_linux()
    return MemoryAction(
        id="fs_cache",
        name="Drop the Linux filesystem cache",
        kind=RAM,
        description=(
            "Writes pending data to disk and drops clean page cache, dentries and inodes. "
            "This is filesystem cache only - application memory is never touched. "
            "Cached reads will hit the disk again until the cache refills."
        ),
        effect="sync, then echo 3 > /proc/sys/vm/drop_caches.",
        requires_admin=True,
        supported=supported,
        unsupported_reason="" if supported else "drop_caches is a Linux kernel interface.",
    )


def _vram_action() -> MemoryAction:
    return MemoryAction(
        id="vram_report",
        name="Inspect graphics memory",
        kind=VRAM,
        description=(
            "Reports VRAM usage and, on NVIDIA hardware, which processes are holding it. "
            "Graphics drivers expose no public API to flush another application's VRAM, "
            "so CrapCleaner reports instead of forcing anything. Closing the listed "
            "application is the only safe way to release its graphics memory."
        ),
        effect="Read-only driver query. Nothing is freed, reset, or terminated.",
    )


def available_actions() -> list[MemoryAction]:
    return [_working_set_action(), _standby_action(), _fs_cache_action(), _vram_action()]


def get_action(action_id: str) -> MemoryAction | None:
    for action in available_actions():
        if action.id == action_id:
            return action
    return None


def _trim_working_set() -> tuple[bool, str]:
    if is_windows():
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            kernel32.SetProcessWorkingSetSize.argtypes = [
                wintypes.HANDLE,
                ctypes.c_size_t,
                ctypes.c_size_t,
            ]
            kernel32.SetProcessWorkingSetSize.restype = wintypes.BOOL
            handle = kernel32.GetCurrentProcess()
            if kernel32.SetProcessWorkingSetSize(handle, ctypes.c_size_t(-1), ctypes.c_size_t(-1)):
                return True, "Working set trimmed."
            return False, f"Windows refused the working set trim (error {ctypes.get_last_error()})."
        except Exception as exc:
            return False, f"Working set trim failed: {exc}"
    try:
        import ctypes

        libc = ctypes.CDLL("libc.so.6")
        libc.malloc_trim(0)
        return True, "Heap trimmed via malloc_trim."
    except Exception as exc:
        return False, f"malloc_trim unavailable: {exc}"


ERROR_NOT_ALL_ASSIGNED = 1300


@dataclass
class PrivilegeStatus:
    name: str
    enabled: bool = False
    present_in_token: bool = False
    elevated: bool = False
    error_code: int = 0
    stage: str = ""
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def enable_privilege(name: str) -> PrivilegeStatus:
    """Enable a Windows privilege on this process token.

    An elevated process still only holds the privileges present in its token,
    so ``AdjustTokenPrivileges`` succeeding is not enough: Windows reports
    ERROR_NOT_ALL_ASSIGNED when the privilege is simply not in the token.
    """
    status = PrivilegeStatus(name=name, elevated=is_admin())
    if not is_windows():
        status.stage = "platform"
        status.message = "Windows privileges do not exist on this platform."
        return status

    import ctypes
    from ctypes import wintypes

    TOKEN_ADJUST_PRIVILEGES = 0x0020
    TOKEN_QUERY = 0x0008
    SE_PRIVILEGE_ENABLED = 0x00000002

    class LUID(ctypes.Structure):
        _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

    class LUID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]

    class TOKEN_PRIVILEGES(ctypes.Structure):
        _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.LookupPrivilegeValueW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.POINTER(LUID),
    ]
    advapi32.LookupPrivilegeValueW.restype = wintypes.BOOL
    advapi32.AdjustTokenPrivileges.argtypes = [
        wintypes.HANDLE,
        wintypes.BOOL,
        ctypes.POINTER(TOKEN_PRIVILEGES),
        wintypes.DWORD,
        ctypes.POINTER(TOKEN_PRIVILEGES),
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.AdjustTokenPrivileges.restype = wintypes.BOOL

    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(),
        TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
        ctypes.byref(token),
    ):
        status.stage = "OpenProcessToken"
        status.error_code = ctypes.get_last_error()
        status.message = f"Could not open this process token (error {status.error_code})."
        return status

    try:
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
            status.stage = "LookupPrivilegeValue"
            status.error_code = ctypes.get_last_error()
            status.message = f"Windows does not know the privilege {name}."
            return status

        privileges = TOKEN_PRIVILEGES()
        privileges.PrivilegeCount = 1
        privileges.Privileges[0].Luid = luid
        privileges.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
        ctypes.set_last_error(0)
        ok = advapi32.AdjustTokenPrivileges(token, False, ctypes.byref(privileges), 0, None, None)
        code = ctypes.get_last_error()
        status.error_code = code
        if not ok:
            status.stage = "AdjustTokenPrivileges"
            status.message = f"Adjusting the token failed (error {code})."
            return status
        if code == ERROR_NOT_ALL_ASSIGNED:
            status.stage = "not_in_token"
            status.message = f"{name} is not held by this process token" + (
                ", even though CrapCleaner is elevated. Local policy or the account "
                "in use does not grant it."
                if status.elevated
                else ". Restart CrapCleaner as administrator."
            )
            return status
        status.present_in_token = True
        status.enabled = True
        status.stage = "enabled"
        status.message = f"{name} enabled."
        return status
    finally:
        kernel32.CloseHandle(token)


def _purge_standby_list() -> tuple[bool, str]:
    try:
        import ctypes

        privilege = enable_privilege("SeProfileSingleProcessPrivilege")
        if not privilege.enabled:
            return False, privilege.message

        SystemMemoryListInformation = 80
        MemoryPurgeStandbyList = ctypes.c_int(4)
        status = ctypes.windll.ntdll.NtSetSystemInformation(
            SystemMemoryListInformation,
            ctypes.byref(MemoryPurgeStandbyList),
            ctypes.sizeof(MemoryPurgeStandbyList),
        )
        if status == 0:
            return True, "Standby list purged."
        return False, f"The kernel rejected the request (NTSTATUS 0x{status & 0xFFFFFFFF:08X})."
    except Exception as exc:
        return False, f"Standby list purge failed: {exc}"


def _drop_caches() -> tuple[bool, str]:
    try:
        subprocess.run(["sync"], check=False, timeout=30)
    except Exception:
        getattr(os, "sync", lambda: None)()
    try:
        with open("/proc/sys/vm/drop_caches", "w", encoding="ascii") as fh:
            fh.write("3\n")
        return True, "Filesystem cache dropped."
    except PermissionError:
        return False, "Dropping the filesystem cache requires root."
    except OSError as exc:
        return False, f"Could not write to /proc/sys/vm/drop_caches: {exc}"


def run_action(action_id: str, dry_run: bool = False) -> MemoryActionResult:
    action = get_action(action_id)
    if action is None:
        return MemoryActionResult(action_id=action_id, message=f"Unknown action: {action_id}")

    before = get_memory_stats()
    result = MemoryActionResult(action_id=action_id, dry_run=dry_run, before=before, after=before)

    if not action.supported:
        result.message = action.unsupported_reason or "Not supported on this platform."
        return result

    if action.kind == VRAM:
        result.success = True
        result.measurable = False
        gpus = get_gpu_memory()
        live = [g for g in gpus if g.live_usage_available]
        if live:
            result.message = "; ".join(f"{g.name}: {g.percent_used}% of VRAM in use" for g in live)
        elif gpus:
            result.message = (
                "Adapter capacity is known, but no driver interface reports live VRAM usage."
            )
        else:
            result.message = "No graphics adapter with readable memory counters was found."
        return result

    if action.requires_admin and not is_admin():
        result.message = f"{action.name} requires elevated privileges."
        return result

    if dry_run:
        result.success = True
        result.message = f"Dry run: would perform {action.effect}"
        return result

    if action_id == "working_set":
        ok, message = _trim_working_set()
    elif action_id == "standby_list":
        ok, message = _purge_standby_list()
    elif action_id == "fs_cache":
        ok, message = _drop_caches()
    else:
        ok, message = False, f"No handler for {action_id}."

    after = get_memory_stats()
    result.success = ok
    result.message = message
    result.after = after
    result.reclaimed_bytes = max(0, after.available_bytes - before.available_bytes)
    return result
