"""Local settings persistence (JSON, stored under %APPDATA%/CrapCleaner)."""

import json
import os
import threading
from typing import Any

from crapcleaner.constants import CONFIG_DIR_NAME, CONFIG_FILE, DEFAULT_CONFIG
from crapcleaner.utils.platform import get_appdata

_lock = threading.Lock()


def config_dir() -> str:
    base = get_appdata()
    if not base:
        base = os.path.expanduser("~")
    return os.path.join(base, CONFIG_DIR_NAME)


def config_path() -> str:
    return os.path.join(config_dir(), CONFIG_FILE)


def load_settings() -> dict[str, Any]:
    path = config_path()
    settings = dict(DEFAULT_CONFIG)
    try:
        with open(path, encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, dict):
            for key, value in loaded.items():
                if key in DEFAULT_CONFIG:
                    settings[key] = value
    except (OSError, ValueError):
        pass
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    with _lock:
        os.makedirs(config_dir(), exist_ok=True)
        path = config_path()
        temp = path + ".tmp"
        merged = dict(DEFAULT_CONFIG)
        merged.update(settings)
        with open(temp, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=2, sort_keys=True)
        os.replace(temp, path)


def update_settings(**updates) -> dict[str, Any]:
    settings = load_settings()
    settings.update(updates)
    save_settings(settings)
    return settings
