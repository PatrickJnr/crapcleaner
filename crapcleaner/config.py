import json
import os
import threading
import time
from typing import Any

from crapcleaner.constants import CONFIG_DIR_NAME, CONFIG_FILE, CONFIG_VERSION, DEFAULT_CONFIG
from crapcleaner.utils.platform import get_appdata

_lock = threading.Lock()


def config_dir() -> str:
    base = get_appdata()
    if not base:
        base = os.path.expanduser("~")
    return os.path.join(base, CONFIG_DIR_NAME)


def config_path() -> str:
    return os.path.join(config_dir(), CONFIG_FILE)


def _migrate_v0(data: dict[str, Any]) -> dict[str, Any]:
    """Pre-versioned configs: drop unknown keys and normalise the theme name."""
    migrated = {key: value for key, value in data.items() if key in DEFAULT_CONFIG}
    if not isinstance(migrated.get("theme"), str):
        migrated["theme"] = DEFAULT_CONFIG["theme"]
    return migrated


_MIGRATIONS = {0: _migrate_v0}


def migrate_settings(data: dict[str, Any]) -> dict[str, Any]:
    version = data.get("config_version")
    if not isinstance(version, int) or version < 0:
        version = 0
    while version < CONFIG_VERSION:
        migration = _MIGRATIONS.get(version)
        if migration is not None:
            data = migration(data)
        version += 1
    data["config_version"] = CONFIG_VERSION
    return data


#: Set when a damaged settings file was moved aside, so the UI can say so once.
#: `excluded_paths` is a safety setting; the user must know it is no longer in force.
_recovery_notice: str | None = None


def take_recovery_notice() -> str | None:
    """Return and clear the message about a settings file that had to be recovered."""
    global _recovery_notice
    notice, _recovery_notice = _recovery_notice, None
    return notice


def _quarantine_unreadable_config(path: str, reason: str) -> None:
    """Move a damaged settings file aside instead of overwriting it.

    The next save merges onto whatever load_settings returned, so without this one
    bad parse permanently replaces every stored preference - exclusions included.
    """
    global _recovery_notice
    backup = f"{path}.corrupt"
    try:
        index = 1
        while os.path.exists(backup):
            backup = f"{path}.corrupt.{index}"
            index += 1
        os.replace(path, backup)
    except OSError:
        _recovery_notice = (
            f"Settings could not be read ({reason}) and could not be backed up. "
            "Defaults are in use; your excluded paths are not in force."
        )
        return
    _recovery_notice = (
        f"Settings could not be read ({reason}). The file was kept as "
        f"{os.path.basename(backup)} and defaults are in use - check your excluded paths."
    )


def load_settings() -> dict[str, Any]:
    path = config_path()
    settings = dict(DEFAULT_CONFIG)
    try:
        with open(path, encoding="utf-8") as fh:
            loaded = json.load(fh)
    except OSError:
        return settings
    except ValueError as exc:
        _quarantine_unreadable_config(path, str(exc).split("\n")[0][:120])
        return settings

    if not isinstance(loaded, dict):
        _quarantine_unreadable_config(path, "file does not contain a settings object")
        return settings

    loaded = migrate_settings(loaded)
    for key, value in loaded.items():
        if key in DEFAULT_CONFIG and isinstance(value, type(DEFAULT_CONFIG[key])):
            if key == "custom_theme" and isinstance(value, dict):
                custom_default = DEFAULT_CONFIG.get("custom_theme")
                merged_custom = dict(custom_default) if isinstance(custom_default, dict) else {}
                merged_custom.update(value)
                settings["custom_theme"] = merged_custom
            else:
                settings[key] = value
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    with _lock:
        os.makedirs(config_dir(), exist_ok=True)
        path = config_path()
        temp = f"{path}.{os.getpid()}.{time.time_ns()}.tmp"
        # Merge onto what is already stored so partial saves (e.g. the settings
        # form) never reset untouched keys such as window_geometry.
        merged = load_settings()
        merged.update(settings)
        merged["config_version"] = CONFIG_VERSION

        payload = json.dumps(merged, indent=2, sort_keys=True)
        try:
            with open(temp, "w", encoding="utf-8") as fh:
                fh.write(payload)

            # os.replace fails on Windows while an indexer or antivirus holds the file.
            replaced = False
            for attempt in range(8):
                try:
                    os.replace(temp, path)
                    replaced = True
                    break
                except (PermissionError, OSError):
                    time.sleep(0.015 * (attempt + 1))

            if not replaced:
                # Still blocked: a non-atomic write beats losing the settings.
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(payload)
        finally:
            if os.path.exists(temp):
                try:
                    os.remove(temp)
                except OSError:
                    pass

    # The safety layer caches the user's exclusion rules, so an edit here has to be
    # published or it would not take effect until the process restarted.
    try:
        from crapcleaner.core.protected_paths import refresh_protection_cache

        refresh_protection_cache()
    except Exception:  # pragma: no cover - a cache drop must never fail a save
        from crapcleaner.utils.logs import get_logger

        get_logger("config").warning(
            "Saved settings but could not refresh the protection cache; "
            "exclusion changes apply on next start",
            exc_info=True,
        )


def offline_mode() -> bool:
    """Whether every automatic network call must be skipped."""
    return bool(load_settings().get("offline_mode", False))


def update_settings(**updates) -> dict[str, Any]:
    settings = load_settings()
    settings.update(updates)
    save_settings(settings)
    return settings
