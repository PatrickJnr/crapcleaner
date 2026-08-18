"""Windows startup entries: registry Run/RunOnce keys and Startup folder shortcuts.

Enablement state lives in the ``StartupApproved`` keys that Task Manager writes, so
toggling an entry here matches what the built-in Startup tab shows.
"""

import os
from typing import TYPE_CHECKING

from crapcleaner.utils.platform import is_admin

if TYPE_CHECKING:  # pragma: no cover - typing only
    from crapcleaner.system.startup import StartupItem

try:  # pragma: no cover - import guard, exercised only off Windows
    import winreg
except ImportError:  # pragma: no cover
    winreg = None  # type: ignore[assignment]

_REG_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_RUNONCE = r"Software\Microsoft\Windows\CurrentVersion\RunOnce"
_REG_APPROVED_RUN = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
_REG_APPROVED_STARTUP = (
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder"
)

_APPROVED_ENABLED = b"\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
_APPROVED_DISABLED = b"\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

#: Scopes the Add dialog offers on this platform.
ADD_SCOPES = ("USER", "SYSTEM")


def _startup_folder(common: bool) -> str:
    base = (
        os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        if common
        else os.environ.get("APPDATA", "")
    )
    return os.path.join(base, r"Microsoft\Windows\Start Menu\Programs\Startup")


def _read_startup_approved_dict(root_key, subkey_path: str) -> dict[str, bool]:
    """Read StartupApproved binary flags into a name -> enabled map.

    The first byte carries the state: even values (0x02, 0x06) are enabled, odd ones
    (0x03, 0x01) were switched off by the user.
    """
    approved: dict[str, bool] = {}
    if winreg is None:
        return approved
    try:
        with winreg.OpenKey(root_key, subkey_path, 0, winreg.KEY_READ) as key:
            i = 0
            while True:
                try:
                    name, data, _val_type = winreg.EnumValue(key, i)
                    if isinstance(data, (bytes, bytearray)) and len(data) > 0:
                        first_byte = data[0]
                        approved[name.lower()] = (first_byte % 2 == 0) and (first_byte != 0x00)
                    i += 1
                except OSError:
                    break
    except OSError:
        pass
    return approved


def _registry_items() -> list["StartupItem"]:
    from crapcleaner.system.startup import (
        StartupItem,
        estimate_startup_impact,
        extract_executable_path,
        extract_publisher,
    )

    items: list[StartupItem] = []
    if winreg is None:
        return items

    approved_hkcu = _read_startup_approved_dict(winreg.HKEY_CURRENT_USER, _REG_APPROVED_RUN)
    approved_hklm = _read_startup_approved_dict(winreg.HKEY_LOCAL_MACHINE, _REG_APPROVED_RUN)

    targets = [
        (
            winreg.HKEY_CURRENT_USER,
            _REG_RUN,
            "HKCU_RUN",
            "Registry (Current User Run)",
            "USER",
            approved_hkcu,
            0,
        ),
        (
            winreg.HKEY_LOCAL_MACHINE,
            _REG_RUN,
            "HKLM_RUN",
            "Registry (All Users Run)",
            "SYSTEM",
            approved_hklm,
            winreg.KEY_WOW64_64KEY,
        ),
        (
            winreg.HKEY_LOCAL_MACHINE,
            _REG_RUN,
            "HKLM_RUN_32",
            "Registry (All Users Run 32-bit)",
            "SYSTEM",
            approved_hklm,
            winreg.KEY_WOW64_32KEY,
        ),
        (
            winreg.HKEY_CURRENT_USER,
            _REG_RUNONCE,
            "HKCU_RUNONCE",
            "Registry (Current User RunOnce)",
            "USER",
            approved_hkcu,
            0,
        ),
        (
            winreg.HKEY_LOCAL_MACHINE,
            _REG_RUNONCE,
            "HKLM_RUNONCE",
            "Registry (All Users RunOnce)",
            "SYSTEM",
            approved_hklm,
            0,
        ),
    ]

    seen_ids: set[str] = set()

    for root, subkey, loc_key, loc_name, scope, approved_map, extra_flags in targets:
        try:
            access = winreg.KEY_READ | extra_flags if extra_flags else winreg.KEY_READ
            with winreg.OpenKey(root, subkey, 0, access) as key:
                i = 0
                while True:
                    try:
                        val_name, val_data, _val_type = winreg.EnumValue(key, i)
                        i += 1
                        if not isinstance(val_data, str) or not val_name:
                            continue

                        item_id = f"reg:{loc_key}:{val_name}"
                        if item_id in seen_ids:
                            continue
                        seen_ids.add(item_id)

                        exe_path = extract_executable_path(val_data)
                        file_exists = bool(exe_path and os.path.exists(exe_path))

                        items.append(
                            StartupItem(
                                id=item_id,
                                name=val_name,
                                command=val_data,
                                location=loc_name,
                                location_key=loc_key,
                                scope=scope,
                                enabled=approved_map.get(val_name.lower(), True),
                                impact=estimate_startup_impact(val_name, exe_path, file_exists),
                                publisher=extract_publisher(val_name, exe_path),
                                file_path=exe_path,
                                file_exists=file_exists,
                            )
                        )
                    except OSError:
                        break
        except OSError:
            pass

    return items


def _folder_items() -> list["StartupItem"]:
    from crapcleaner.system.startup import (
        StartupItem,
        estimate_startup_impact,
        extract_publisher,
    )

    items: list[StartupItem] = []
    if winreg is None:
        return items

    approved_user = _read_startup_approved_dict(winreg.HKEY_CURRENT_USER, _REG_APPROVED_STARTUP)
    approved_common = _read_startup_approved_dict(winreg.HKEY_LOCAL_MACHINE, _REG_APPROVED_STARTUP)

    folders = [
        (_startup_folder(False), "USER_STARTUP", "Startup Folder (User)", "USER", approved_user),
        (
            _startup_folder(True),
            "COMMON_STARTUP",
            "Startup Folder (All Users)",
            "SYSTEM",
            approved_common,
        ),
    ]

    for folder_path, loc_key, loc_name, scope, approved_map in folders:
        if not os.path.isdir(folder_path):
            continue
        try:
            for entry in os.scandir(folder_path):
                if not entry.is_file():
                    continue
                fname = entry.name
                if fname.lower() == "desktop.ini":
                    continue

                is_disabled_ext = fname.lower().endswith(".disabled")
                display_name = fname[:-9] if is_disabled_ext else fname
                clean_name = (
                    display_name[:-4] if display_name.lower().endswith(".lnk") else display_name
                )

                enabled = (
                    not is_disabled_ext
                    and approved_map.get(display_name.lower(), True)
                    and approved_map.get(fname.lower(), True)
                )

                items.append(
                    StartupItem(
                        id=f"folder:{loc_key}:{fname}",
                        name=clean_name,
                        command=entry.path,
                        location=loc_name,
                        location_key=loc_key,
                        scope=scope,
                        enabled=enabled,
                        impact=estimate_startup_impact(clean_name, entry.path, True),
                        publisher=extract_publisher(clean_name, entry.path),
                        file_path=entry.path,
                        file_exists=True,
                    )
                )
        except OSError:
            pass

    return items


def list_items() -> list["StartupItem"]:
    return _registry_items() + _folder_items()


def set_enabled(kind: str, loc_key: str, entry_name: str, enabled: bool) -> tuple[bool, str]:
    if winreg is None:
        return False, "The Windows registry is unavailable on this system."

    if kind == "reg":
        is_hklm = "HKLM" in loc_key
        if is_hklm and not is_admin():
            return (
                False,
                "Administrator elevation is required to modify system-wide startup entries.",
            )
        root = winreg.HKEY_LOCAL_MACHINE if is_hklm else winreg.HKEY_CURRENT_USER
        try:
            with winreg.CreateKeyEx(
                root, _REG_APPROVED_RUN, 0, winreg.KEY_SET_VALUE | winreg.KEY_READ
            ) as app_key:
                winreg.SetValueEx(
                    app_key,
                    entry_name,
                    0,
                    winreg.REG_BINARY,
                    _APPROVED_ENABLED if enabled else _APPROVED_DISABLED,
                )
            return (
                True,
                f"Startup entry '{entry_name}' {'enabled' if enabled else 'disabled'} successfully.",
            )
        except OSError as exc:
            return False, f"Failed to modify registry: {exc}"

    if kind == "folder":
        is_common = "COMMON" in loc_key
        if is_common and not is_admin():
            return (
                False,
                "Administrator elevation is required to modify system-wide startup folders.",
            )

        folder_path = _startup_folder(is_common)
        current_file = os.path.join(folder_path, entry_name)

        if enabled and entry_name.lower().endswith(".disabled"):
            new_file = os.path.join(folder_path, entry_name[:-9])
            try:
                if os.path.exists(current_file):
                    os.rename(current_file, new_file)
                    return True, f"Startup shortcut '{os.path.basename(new_file)}' enabled."
            except OSError as exc:
                return False, f"Failed to rename file: {exc}"
        elif not enabled and not entry_name.lower().endswith(".disabled"):
            try:
                if os.path.exists(current_file):
                    os.rename(current_file, current_file + ".disabled")
                    return True, f"Startup shortcut '{entry_name}' disabled."
            except OSError as exc:
                return False, f"Failed to rename file: {exc}"

        root = winreg.HKEY_LOCAL_MACHINE if is_common else winreg.HKEY_CURRENT_USER
        try:
            with winreg.CreateKeyEx(
                root, _REG_APPROVED_STARTUP, 0, winreg.KEY_SET_VALUE
            ) as app_key:
                winreg.SetValueEx(
                    app_key,
                    entry_name,
                    0,
                    winreg.REG_BINARY,
                    _APPROVED_ENABLED if enabled else _APPROVED_DISABLED,
                )
            return (
                True,
                f"Startup entry '{entry_name}' {'enabled' if enabled else 'disabled'} successfully.",
            )
        except OSError:
            pass
        return True, f"Updated startup shortcut '{entry_name}'."

    return False, f"Unknown startup entry type '{kind}'."


def remove(kind: str, loc_key: str, entry_name: str) -> tuple[bool, str]:
    if winreg is None:
        return False, "The Windows registry is unavailable on this system."

    if kind == "reg":
        is_hklm = "HKLM" in loc_key
        if is_hklm and not is_admin():
            return (
                False,
                "Administrator elevation is required to delete system-wide startup entries.",
            )
        root = winreg.HKEY_LOCAL_MACHINE if is_hklm else winreg.HKEY_CURRENT_USER
        subkey = _REG_RUNONCE if "RUNONCE" in loc_key else _REG_RUN
        extra_flags = winreg.KEY_WOW64_32KEY if "32" in loc_key else winreg.KEY_WOW64_64KEY
        try:
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_SET_VALUE | extra_flags) as key:
                winreg.DeleteValue(key, entry_name)
            try:
                with winreg.OpenKey(root, _REG_APPROVED_RUN, 0, winreg.KEY_SET_VALUE) as app_key:
                    winreg.DeleteValue(app_key, entry_name)
            except OSError:
                pass
            return True, f"Startup registry entry '{entry_name}' removed successfully."
        except OSError as exc:
            return False, f"Failed to delete registry entry: {exc}"

    if kind == "folder":
        is_common = "COMMON" in loc_key
        if is_common and not is_admin():
            return (
                False,
                "Administrator elevation is required to delete system-wide startup shortcuts.",
            )
        file_path = os.path.join(_startup_folder(is_common), entry_name)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True, f"Startup shortcut '{entry_name}' deleted."
            return False, f"File '{file_path}' not found."
        except OSError as exc:
            return False, f"Failed to delete startup shortcut: {exc}"

    return False, f"Unknown startup entry type '{kind}'."


def add(name: str, command: str, scope: str = "USER") -> tuple[bool, str]:
    if winreg is None:
        return False, "The Windows registry is unavailable on this system."

    is_system = scope.upper() == "SYSTEM"
    if is_system and not is_admin():
        return False, "Administrator elevation is required to add system-wide startup entries."

    root = winreg.HKEY_LOCAL_MACHINE if is_system else winreg.HKEY_CURRENT_USER
    try:
        with winreg.OpenKey(root, _REG_RUN, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
        try:
            with winreg.CreateKeyEx(root, _REG_APPROVED_RUN, 0, winreg.KEY_SET_VALUE) as app_key:
                winreg.SetValueEx(app_key, name, 0, winreg.REG_BINARY, _APPROVED_ENABLED)
        except OSError:
            pass
        return (
            True,
            f"Added '{name}' to startup registry ({'All Users' if is_system else 'Current User'}).",
        )
    except OSError as exc:
        return False, f"Failed to add startup entry: {exc}"
