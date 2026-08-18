"""Utility package: formatting, platform helpers, safe file operations."""

from crapcleaner.utils.files import (
    empty_recycle_bin,
    move_to_recycle_bin,
    path_is_locked,
    remove_file,
    remove_tree,
)
from crapcleaner.utils.format import (
    format_datetime,
    format_duration,
    format_size,
    parse_size,
)
from crapcleaner.utils.platform import (
    elevate,
    expand_env,
    get_appdata,
    get_drive_info,
    get_local_appdata,
    get_program_data,
    get_program_files_x86,
    get_user_profile,
    get_windows_dir,
    is_admin,
    is_frozen,
    list_drives,
    resolve_paths,
    run_command,
    which,
)
from crapcleaner.utils.windows_errors import (
    WINDOWS_ERROR_MAP,
    explain_windows_error,
    extract_error_code,
)

__all__ = [
    "format_size",
    "parse_size",
    "format_duration",
    "format_datetime",
    "expand_env",
    "resolve_paths",
    "get_drive_info",
    "list_drives",
    "is_admin",
    "elevate",
    "which",
    "run_command",
    "is_frozen",
    "get_user_profile",
    "get_local_appdata",
    "get_appdata",
    "get_program_data",
    "get_program_files_x86",
    "get_windows_dir",
    "remove_file",
    "remove_tree",
    "move_to_recycle_bin",
    "empty_recycle_bin",
    "path_is_locked",
    "explain_windows_error",
    "extract_error_code",
    "WINDOWS_ERROR_MAP",
]
