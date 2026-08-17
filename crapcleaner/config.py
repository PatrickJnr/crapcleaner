"""Local settings persistence stored in the platform config directory."""

import json
import os
import threading
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
            settings[key] = value
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    with _lock:
        os.makedirs(config_dir(), exist_ok=True)
        path = config_path()
        temp = path + ".tmp"
        # Merge onto what is already stored so partial saves (e.g. the settings
        # form) never reset untouched keys such as window_geometry.
        merged = load_settings()
        merged.update(settings)
        merged["config_version"] = CONFIG_VERSION
        with open(temp, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=2, sort_keys=True)
        os.replace(temp, path)

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
