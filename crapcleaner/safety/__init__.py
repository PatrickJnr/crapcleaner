"""Centralized Safety and Protected Paths Layer for CrapCleaner."""

from crapcleaner.safety.protected_paths import (
    explain_protection,
    get_protected_rules_summary,
    is_path_protected,
    validate_cleanup_path,
)

__all__ = [
    "is_path_protected",
    "explain_protection",
    "validate_cleanup_path",
    "get_protected_rules_summary",
]
