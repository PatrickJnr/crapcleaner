"""System memory reporting and safe reclamation."""

from crapcleaner.memory.cleaner import (
    MemoryAction,
    MemoryActionResult,
    PrivilegeStatus,
    available_actions,
    enable_privilege,
    get_action,
    run_action,
)
from crapcleaner.memory.report import (
    GpuMemoryStats,
    MemoryReport,
    MemoryStats,
    get_gpu_memory,
    get_memory_report,
    get_memory_stats,
    get_vram_consumers,
)

__all__ = [
    "GpuMemoryStats",
    "MemoryAction",
    "MemoryActionResult",
    "MemoryReport",
    "MemoryStats",
    "PrivilegeStatus",
    "available_actions",
    "enable_privilege",
    "get_action",
    "get_gpu_memory",
    "get_memory_report",
    "get_memory_stats",
    "get_vram_consumers",
    "run_action",
]
