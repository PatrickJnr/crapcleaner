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


def load_settings() -> dict[str, Any]:
    path = config_path()
    settings = dict(DEFAULT_CONFIG)
    try:
        with open(path, encoding="utf-8") as fh:
            loaded = json.load(fh)
    except (OSError, ValueError):
        return settings

    if not isinstance(loaded, dict):
        return settings

    loaded = migrate_settings(loaded)
    for key, value in loaded.items():
        if key in DEFAULT_CONFIG and isinstance(value, type(DEFAULT_CONFIG[key])):
            if key == "custom_theme" and isinstance(value, dict):
                merged_custom = dict(DEFAULT_CONFIG["custom_theme"])
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

            # Resilient atomic replace for Windows with retry backoff against transient file locks
            replaced = False
            for attempt in range(8):
                try:
                    os.replace(temp, path)
                    replaced = True
                    break
                except (PermissionError, OSError):
                    time.sleep(0.015 * (attempt + 1))

            if not replaced:
                # Fallback: direct write if replace is blocked by antivirus or indexer
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
        pass


def update_settings(**updates) -> dict[str, Any]:
    settings = load_settings()
    settings.update(updates)
    save_settings(settings)
    return settings
