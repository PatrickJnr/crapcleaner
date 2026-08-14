"""Config package."""

from crapcleaner.config.settings import (
    config_dir,
    config_path,
    load_settings,
    save_settings,
    update_settings,
)

__all__ = [
    "config_dir",
    "config_path",
    "load_settings",
    "save_settings",
    "update_settings",
]
