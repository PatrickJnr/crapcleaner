"""Settings versioning, migration, and persistence across restarts."""

import json
import os

from crapcleaner.config.settings import (
    config_dir,
    config_path,
    load_settings,
    migrate_settings,
    save_settings,
)
from crapcleaner.constants import CONFIG_VERSION


def _write_raw(payload):
    os.makedirs(config_dir(), exist_ok=True)
    with open(config_path(), "w", encoding="utf-8") as fh:
        if isinstance(payload, str):
            fh.write(payload)
        else:
            json.dump(payload, fh)


def test_saved_settings_are_versioned():
    save_settings({"theme": "oled"})
    with open(config_path(), encoding="utf-8") as fh:
        stored = json.load(fh)
    assert stored["config_version"] == CONFIG_VERSION


def test_theme_persists_across_reloads():
    save_settings({"theme": "high-contrast"})
    assert load_settings()["theme"] == "high-contrast"
    assert load_settings()["theme"] == "high-contrast"


def test_partial_save_keeps_other_preferences():
    save_settings({"theme": "oled", "window_geometry": "abcd", "max_scan_files": 12345})
    save_settings({"theme": "light"})
    settings = load_settings()
    assert settings["theme"] == "light"
    assert settings["window_geometry"] == "abcd"
    assert settings["max_scan_files"] == 12345


def test_unversioned_config_is_migrated():
    _write_raw({"theme": "light", "legacy_option": True, "max_scan_files": 5000})
    settings = load_settings()
    assert settings["config_version"] == CONFIG_VERSION
    assert settings["theme"] == "light"
    assert settings["max_scan_files"] == 5000
    assert "legacy_option" not in settings


def test_migration_repairs_invalid_theme_type():
    migrated = migrate_settings({"theme": 7})
    assert migrated["theme"] == "dark"
    assert migrated["config_version"] == CONFIG_VERSION


def test_migration_is_idempotent():
    once = migrate_settings({"theme": "oled"})
    twice = migrate_settings(dict(once))
    assert once == twice


def test_wrong_types_fall_back_to_defaults():
    _write_raw({"config_version": CONFIG_VERSION, "max_scan_files": "lots", "scan_roots": "C:/"})
    settings = load_settings()
    assert settings["max_scan_files"] == 200000
    assert settings["scan_roots"] == []


def test_corrupt_config_does_not_raise():
    _write_raw("{{{ definitely not json")
    settings = load_settings()
    assert settings["theme"] == "dark"
    assert settings["config_version"] == CONFIG_VERSION


def test_non_object_config_does_not_raise():
    _write_raw([1, 2, 3])
    assert load_settings()["theme"] == "dark"


def test_future_version_is_left_alone():
    _write_raw({"config_version": CONFIG_VERSION + 5, "theme": "oled"})
    settings = load_settings()
    assert settings["theme"] == "oled"
