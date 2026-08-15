"""Storage hierarchy, file type analysis, and virtual machine detection."""

from crapcleaner.storage.analyzer import StorageNode, analyze_storage_hierarchy
from crapcleaner.storage.file_types import FileTypeSummary, analyze_file_types
from crapcleaner.storage.virtual_machines import VmStorageItem, detect_virtual_machine_storage

__all__ = [
    "StorageNode",
    "analyze_storage_hierarchy",
    "FileTypeSummary",
    "analyze_file_types",
    "VmStorageItem",
    "detect_virtual_machine_storage",
]
