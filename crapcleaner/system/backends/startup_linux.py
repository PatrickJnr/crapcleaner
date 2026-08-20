"""Linux startup entries: XDG autostart desktop files.

Follows the XDG Autostart specification: ``~/.config/autostart`` shadows
``/etc/xdg/autostart`` by filename, and an entry is suppressed by ``Hidden=true``
(or GNOME's ``X-GNOME-Autostart-enabled=false``).

System entries live in a root-owned directory, so disabling or removing one writes a
user-level override that hides it instead of touching ``/etc``. That is both the
spec-sanctioned mechanism and the only one that works without elevation.
"""

import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from crapcleaner.system.startup import StartupItem

SYSTEM_AUTOSTART_DIR = "/etc/xdg/autostart"

#: Only user-scope entries can be created; a system-wide entry needs root and a
#: package manager, which is not this application's job.
ADD_SCOPES = ("USER",)


def user_autostart_dir() -> str:
    config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(config_home, "autostart")


def _parse_desktop_entry(path: str) -> dict[str, str]:
    """Read the key=value pairs of a .desktop file's [Desktop Entry] group."""
    values: dict[str, str] = {}
    in_entry_group = False
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                line = raw.strip()
                if line.startswith("[") and line.endswith("]"):
                    in_entry_group = line == "[Desktop Entry]"
                    continue
                if not in_entry_group or "=" not in line or line.startswith("#"):
                    continue
                key, _, value = line.partition("=")
                values.setdefault(key.strip(), value.strip())
    except OSError:
        pass
    return values


def _is_enabled(values: dict[str, str]) -> bool:
    if values.get("Hidden", "").lower() == "true":
        return False
    if values.get("X-GNOME-Autostart-enabled", "").lower() == "false":
        return False
    return True


def list_items() -> list["StartupItem"]:
    from crapcleaner.system.startup import (
        StartupItem,
        estimate_startup_impact,
        extract_executable_path,
    )

    directories = [
        (user_autostart_dir(), "USER_STARTUP", "User Autostart (~/.config/autostart)", "USER"),
        (SYSTEM_AUTOSTART_DIR, "COMMON_STARTUP", "System Autostart (/etc/xdg/autostart)", "SYSTEM"),
    ]

    items: list[StartupItem] = []
    # A user file shadows the system file of the same name, so the user directory is
    # walked first and later duplicates are skipped.
    seen_filenames: set[str] = set()

    for dir_path, loc_key, loc_name, scope in directories:
        if not os.path.isdir(dir_path):
            continue
        try:
            entries = sorted(os.scandir(dir_path), key=lambda e: e.name)
        except OSError:
            continue

        for entry in entries:
            if not entry.is_file() or not entry.name.endswith(".desktop"):
                continue
            if entry.name in seen_filenames:
                continue
            seen_filenames.add(entry.name)

            values = _parse_desktop_entry(entry.path)
            command = values.get("Exec", "")
            exe_path = extract_executable_path(command)
            file_exists = bool(exe_path and (os.path.exists(exe_path) or _on_path(exe_path)))
            name = values.get("Name") or entry.name[:-8]

            items.append(
                StartupItem(
                    id=f"linux:{loc_key}:{entry.name}",
                    name=name,
                    command=command,
                    location=loc_name,
                    location_key=loc_key,
                    scope=scope,
                    enabled=_is_enabled(values),
                    impact=estimate_startup_impact(name, exe_path, file_exists),
                    publisher=_publisher_from_entry(values, entry.name),
                    file_path=exe_path or entry.path,
                    file_exists=file_exists,
                )
            )

    return items


def _on_path(program: str) -> bool:
    """Desktop entries usually name a bare command rather than an absolute path."""
    if os.path.sep in program:
        return False
    import shutil

    return shutil.which(program) is not None


def _publisher_from_entry(values: dict[str, str], filename: str) -> str:
    # Reverse-DNS desktop ids carry the vendor: org.gnome.Software -> GNOME.
    ident = filename[:-8]
    parts = ident.split(".")
    if len(parts) >= 3 and parts[0] in ("org", "com", "io", "net", "dev"):
        return parts[1].replace("-", " ").title()
    categories = values.get("Categories", "")
    if "KDE" in categories:
        return "KDE"
    if "GNOME" in categories:
        return "GNOME"
    return "Desktop Application"


def _override_path(entry_name: str) -> str:
    return os.path.join(user_autostart_dir(), entry_name)


def _write_flags(path: str, source: str, enabled: bool) -> tuple[bool, str]:
    """Copy `source` to `path` if needed, then stamp the enablement flags on it."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.isfile(source):
            with open(source, encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        else:
            return False, f"Desktop entry '{os.path.basename(source)}' was not found."

        hidden_value = "false" if enabled else "true"
        gnome_value = "true" if enabled else "false"
        rewritten: list[str] = []
        saw_hidden = saw_gnome = False

        for line in lines:
            if line.startswith("Hidden="):
                rewritten.append(f"Hidden={hidden_value}\n")
                saw_hidden = True
            elif line.startswith("X-GNOME-Autostart-enabled="):
                rewritten.append(f"X-GNOME-Autostart-enabled={gnome_value}\n")
                saw_gnome = True
            else:
                rewritten.append(line)

        if rewritten and not rewritten[-1].endswith("\n"):
            rewritten[-1] += "\n"
        if not saw_hidden:
            rewritten.append(f"Hidden={hidden_value}\n")
        if not saw_gnome:
            rewritten.append(f"X-GNOME-Autostart-enabled={gnome_value}\n")

        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(rewritten)
        return True, ""
    except OSError as exc:
        return False, f"Failed to update desktop entry: {exc}"


def set_enabled(kind: str, loc_key: str, entry_name: str, enabled: bool) -> tuple[bool, str]:
    is_system = "COMMON" in loc_key
    source = os.path.join(SYSTEM_AUTOSTART_DIR if is_system else user_autostart_dir(), entry_name)
    target = _override_path(entry_name)

    ok, err = _write_flags(target, source, enabled)
    if not ok:
        return False, err

    state = "enabled" if enabled else "disabled"
    if is_system:
        return True, (
            f"System autostart entry '{entry_name}' {state} via a user override in "
            f"{user_autostart_dir()}."
        )
    return True, f"Autostart entry '{entry_name}' {state}."


def remove(kind: str, loc_key: str, entry_name: str) -> tuple[bool, str]:
    is_system = "COMMON" in loc_key

    if is_system:
        # /etc is package-manager-owned; hide it for this user instead of deleting.
        source = os.path.join(SYSTEM_AUTOSTART_DIR, entry_name)
        ok, err = _write_flags(_override_path(entry_name), source, False)
        if not ok:
            return False, err
        return True, (
            f"System autostart entry '{entry_name}' is a packaged file and was hidden for "
            "this user rather than deleted."
        )

    file_path = os.path.join(user_autostart_dir(), entry_name)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True, f"Autostart entry '{entry_name}' removed."
        return False, f"File '{file_path}' not found."
    except OSError as exc:
        return False, f"Failed to delete autostart entry: {exc}"


def add(name: str, command: str, scope: str = "USER") -> tuple[bool, str]:
    if scope.upper() == "SYSTEM":
        return False, (
            "System-wide autostart entries are managed by your distribution's packages. "
            "Add a user entry instead."
        )

    dest_dir = user_autostart_dir()
    safe_fname = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.lower()) + ".desktop"
    file_path = os.path.join(dest_dir, safe_fname)
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={name}\n"
        f"Exec={command}\n"
        "Hidden=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    try:
        os.makedirs(dest_dir, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return True, f"Created autostart entry '{safe_fname}'."
    except OSError as exc:
        return False, f"Failed to create autostart entry: {exc}"
