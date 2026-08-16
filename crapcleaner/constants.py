"""Application-wide constants."""

APP_NAME = "CrapCleaner"
APP_DISPLAY_NAME = "CrapCleaner"
VERSION = "1.0.7.1"
COMPANY_NAME = "CrapCleaner"
APP_URL = "https://github.com/PatrickJnr/crapcleaner"

CONFIG_DIR_NAME = "CrapCleaner"
CONFIG_FILE = "config.json"
HISTORY_FILE = "history.jsonl"
LOG_FILE = "crapcleaner.log"

CONFIG_VERSION = 1

DEFAULT_CONFIG = {
    "config_version": CONFIG_VERSION,
    "theme": "dark",
    "scan_roots": [],
    "scan_all_drives": True,
    "scan_cache_ttl": 300,
    "duplicate_min_size_mb": 1,
    "large_file_default_threshold_mb": 1024,
    "dry_run_default": True,
    "confirm_cleanup": True,
    "use_recycle_bin": True,
    "max_scan_files": 200000,
    "recent_categories": [],
    "large_file_default_root": "",
    "disabled_categories": [],
    "excluded_paths": [],
    "auto_rescan_after_cleanup": True,
    "show_command_preview": True,
    "reduce_motion": False,
    "window_geometry": "",
    "storage_favorites": [],
    "last_scan_snapshot": {},
}
