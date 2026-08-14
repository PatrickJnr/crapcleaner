"""Data models: safety levels, cleanup categories, scan results, reports."""

from crapcleaner.models.category import (
    CacheTarget,
    CleanupCategory,
    SafetyLevel,
)
from crapcleaner.models.history import HistoryEntry
from crapcleaner.models.report import (
    CleanupReport,
    CleanupResult,
    ScanCategoryResult,
    ScanReport,
)

__all__ = [
    "CacheTarget",
    "CleanupCategory",
    "SafetyLevel",
    "CleanupReport",
    "CleanupResult",
    "ScanReport",
    "ScanCategoryResult",
    "HistoryEntry",
]
