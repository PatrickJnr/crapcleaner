"""Safe, transparent memory reclamation actions.

Nothing here terminates processes, touches another application's working set,
or resets a GPU. Every action states exactly what the operating system is asked
to do, and unsupported actions are reported instead of attempted.
"""

import os
from dataclasses import asdict, dataclass, field

from crapcleaner.system.memory_report import MemoryStats, get_gpu_memory, get_memory_stats
from crapcleaner.utils.platform import is_admin, is_linux, is_windows, run_command

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
    #: Change in system-wide available memory across the action, not a measure of
    #: what the action released. Never clamped at zero: available memory genuinely
    #: falls sometimes.
    available_delta_bytes: int = 0
    measurable: bool = True
    before: MemoryStats = field(default_factory=MemoryStats)
    after: MemoryStats = field(default_factory=MemoryStats)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["before"] = self.before.to_dict()
        data["after"] = self.after.to_dict()
        return data


def _platform_text(windows: str, linux: str, fallback: str = "") -> str:
    """Pick the wording for the running platform.

    Descriptions name the exact system call made, so only this platform's applies.
    """
    if is_windows():
        return windows
    if is_linux():
        return linux
    return fallback or linux


def _process_working_sets_action() -> MemoryAction:
    return MemoryAction(
        id="process_working_sets",
        name="Flush process working sets",
        kind=RAM,
        description=(
            "Asks the operating system to trim unused working set pages from active processes "
            "and return physical memory to the available pool. No applications or processes "
            "are closed, terminated, or disrupted."
        ),
        effect=_platform_text(
            "EmptyWorkingSet then SetProcessWorkingSetSize on every process this "
            "account may open, twice.",
            "malloc_trim on this process's own heap, then a garbage collection.",
        ),
        requires_admin=False,
    )


def _flush_all_action() -> MemoryAction:
    return MemoryAction(
        id="flush_all",
        name="Flush all available memory",
        kind=RAM,
        description=_platform_text(
            "Performs a comprehensive memory sweep: trims working sets across active "
            "processes, releases CrapCleaner's own heap, and (if elevated) purges the "
            "system standby cache.",
            "Performs a comprehensive memory sweep: trims working sets across active "
            "processes, releases CrapCleaner's own heap, and (if run as root) drops the "
            "filesystem cache.",
        ),
        effect=_platform_text(
            "Working set flush + application heap trim + standby purge (if elevated).",
            "Working set flush + application heap trim + filesystem cache drop (if root).",
        ),
        requires_admin=False,
    )


def _working_set_action() -> MemoryAction:
    return MemoryAction(
        id="working_set",
        name="Release CrapCleaner's own memory",
        kind=RAM,
        description=(
            "Asks the operating system to trim this application's own working set and "
            "return unused heap pages. It never touches other processes."
        ),
        effect=_platform_text(
            "SetProcessWorkingSetSize on our own process.",
            "malloc_trim on our own heap.",
        ),
    )


def _standby_action() -> MemoryAction:
    supported = is_windows()
    return MemoryAction(
        id="standby_list",
        name="Purge the standby list",
        kind=RAM,
        description=(
            "Discards cached file data the system is holding in the standby list, and "
            "empties system working sets along the way. That memory is already "
            "available to applications on demand, so this mainly changes how memory is "
            "reported - and everything running has to fault its pages back in, so the "
            "machine is slower for a while afterwards, not faster."
        ),
        effect=(
            "NtSetSystemInformation(SystemMemoryListInformation) with, in order: "
            "MemoryFlushModifiedList, MemoryEmptyWorkingSets, MemoryPurgeStandbyList, "
            "MemoryPurgeLowPriorityStandbyList; then SetSystemFileCacheSize(-1, -1) to "
            "release the system file cache working set."
        ),
        requires_admin=True,
        supported=supported,
        unsupported_reason="" if supported else "The standby list only exists on Windows.",
    )


def _fs_cache_action() -> MemoryAction:
    supported = is_linux()
    return MemoryAction(
        id="fs_cache",
        name="Drop the filesystem cache",
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
            "Reports per-adapter VRAM capacity and, where the driver exposes a reliable "
            "counter, live usage. Graphics drivers expose no public API to flush another "
            "application's VRAM, so CrapCleaner reports instead of forcing anything. "
            "Closing the application that owns the memory is the only safe way to release it."
        ),
        effect="Read-only driver query. Nothing is freed, reset, or terminated.",
    )


def _all_actions() -> list[MemoryAction]:
    """Every action this application knows about, supported here or not."""
    return [
        _flush_all_action(),
        _process_working_sets_action(),
        _working_set_action(),
        _standby_action(),
        _fs_cache_action(),
        _vram_action(),
    ]


def available_actions(include_unsupported: bool = False) -> list[MemoryAction]:
    """Actions the running platform can actually perform.

    Other platforms' actions are omitted rather than shown disabled; the user
    cannot install a kernel interface. ``include_unsupported`` returns the full set.
    """
    actions = _all_actions()
    if include_unsupported:
        return actions
    return [action for action in actions if action.supported]


def get_action(action_id: str) -> MemoryAction | None:
    """Look up an action by id, including ones this platform cannot run.

    Resolving unsupported ids lets `run_action` explain *why* one is unavailable
    instead of reporting an unknown id.
    """
    for action in _all_actions():
        if action.id == action_id:
            return action
    return None


def _trim_process_working_sets() -> tuple[bool, str]:
    if is_windows():
        try:
            import ctypes
            import gc
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)

            # No system-wide flush here: it needs a privilege this path never
            # requests. That work lives in "Flush all available memory".

            PROCESS_QUERY_INFORMATION = 0x0400
            PROCESS_SET_QUOTA = 0x0100

            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.SetProcessWorkingSetSize.argtypes = [
                wintypes.HANDLE,
                ctypes.c_size_t,
                ctypes.c_size_t,
            ]
            kernel32.SetProcessWorkingSetSize.restype = wintypes.BOOL
            psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
            psapi.EmptyWorkingSet.restype = wintypes.BOOL
            psapi.EnumProcesses.argtypes = [
                ctypes.POINTER(wintypes.DWORD),
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
            ]
            psapi.EnumProcesses.restype = wintypes.BOOL

            pids = (wintypes.DWORD * 4096)()
            cb_needed = wintypes.DWORD()
            if not psapi.EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(cb_needed)):
                return False, f"Could not enumerate processes (error {ctypes.get_last_error()})."

            count = cb_needed.value // ctypes.sizeof(wintypes.DWORD)
            trimmed_count = 0

            # Second pass catches background worker allocations made during the first.
            for _ in range(2):
                for i in range(count):
                    pid = pids[i]
                    if pid <= 4:
                        continue
                    h = kernel32.OpenProcess(
                        PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, False, pid
                    )
                    if h:
                        try:
                            if psapi.EmptyWorkingSet(h):
                                trimmed_count += 1
                            kernel32.SetProcessWorkingSetSize(
                                h, ctypes.c_size_t(-1), ctypes.c_size_t(-1)
                            )
                        finally:
                            kernel32.CloseHandle(h)

            gc.collect()
            return True, f"Flushed working sets across {trimmed_count} process passes."
        except Exception as exc:
            return False, f"Process working set flush failed: {exc}"
    elif is_linux():
        try:
            import ctypes
            import gc

            libc = ctypes.CDLL("libc.so.6")
            libc.malloc_trim(0)
            gc.collect()
            return True, "Process heaps trimmed via malloc_trim."
        except Exception as exc:
            return False, f"Process memory trim unavailable: {exc}"
    return False, "Unsupported platform."


def _flush_all() -> tuple[bool, str]:
    """Run every applicable step, and report success only if one of them worked.

    Returning True unconditionally reported "Memory flush completed." for runs in
    which every step failed. Steps skipped for lack of elevation count as neither.
    """
    done: list[str] = []
    failed: list[str] = []

    for step, (ok, message) in (
        ("working sets", _trim_process_working_sets()),
        ("own heap", _trim_working_set()),
    ):
        (done if ok else failed).append(message if ok else f"{step}: {message}")

    if is_windows():
        if is_admin():
            ok_st, msg_st = _purge_standby_list()
            (done if ok_st else failed).append(msg_st if ok_st else f"standby list: {msg_st}")
        else:
            failed.append("standby list: skipped, needs elevation")
    elif is_linux():
        if is_admin():
            ok_fc, msg_fc = _drop_caches()
            (done if ok_fc else failed).append(
                "Filesystem cache dropped." if ok_fc else f"filesystem cache: {msg_fc}"
            )
        else:
            failed.append("filesystem cache: skipped, needs root")

    message = " · ".join(done)
    if failed:
        message = (
            f"{message} · Not done: {'; '.join(failed)}"
            if done
            else (f"Nothing was done. {'; '.join(failed)}")
        )
    return bool(done), message or "Nothing to do on this platform."


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
    """Enable a Windows privilege on this process token."""
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
        from ctypes import wintypes

        privilege = enable_privilege("SeProfileSingleProcessPrivilege")
        enable_privilege("SeIncreaseQuotaPrivilege")
        if not privilege.enabled:
            return False, privilege.message

        SystemMemoryListInformation = 80
        ntdll = ctypes.windll.ntdll

        cmd_flush_mod = ctypes.c_int(3)
        ntdll.NtSetSystemInformation(
            SystemMemoryListInformation,
            ctypes.byref(cmd_flush_mod),
            ctypes.sizeof(cmd_flush_mod),
        )

        cmd_empty_ws = ctypes.c_int(2)
        ntdll.NtSetSystemInformation(
            SystemMemoryListInformation,
            ctypes.byref(cmd_empty_ws),
            ctypes.sizeof(cmd_empty_ws),
        )

        cmd_purge_standby = ctypes.c_int(4)
        status = ntdll.NtSetSystemInformation(
            SystemMemoryListInformation,
            ctypes.byref(cmd_purge_standby),
            ctypes.sizeof(cmd_purge_standby),
        )

        cmd_purge_low = ctypes.c_int(5)
        ntdll.NtSetSystemInformation(
            SystemMemoryListInformation,
            ctypes.byref(cmd_purge_low),
            ctypes.sizeof(cmd_purge_low),
        )

        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.SetSystemFileCacheSize.argtypes = [
                ctypes.c_size_t,
                ctypes.c_size_t,
                wintypes.DWORD,
            ]
            kernel32.SetSystemFileCacheSize.restype = wintypes.BOOL
            kernel32.SetSystemFileCacheSize(ctypes.c_size_t(-1), ctypes.c_size_t(-1), 0)
        except Exception:
            pass

        if status == 0:
            return True, "Standby list & system cache purged."
        return False, f"The kernel rejected the request (NTSTATUS 0x{status & 0xFFFFFFFF:08X})."
    except Exception as exc:
        return False, f"Standby list purge failed: {exc}"


def _drop_caches() -> tuple[bool, str]:
    # run_command reports failure in the result; it never raises.
    if not run_command(["sync"], timeout=30.0).ok:
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

    if action_id == "flush_all":
        ok, message = _flush_all()
    elif action_id == "process_working_sets":
        ok, message = _trim_process_working_sets()
    elif action_id == "working_set":
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
    result.available_delta_bytes = after.available_bytes - before.available_bytes
    return result
