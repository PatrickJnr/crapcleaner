"""Crash dump cleanup categories.

`analysis/crash_dumps.py` could find these all along; nothing could reach it.
A single `MEMORY.DMP` is often the largest removable file on a Windows system.
"""

from crapcleaner.analysis.crash_dumps import find_application_dump_paths, find_kernel_dump_paths
from crapcleaner.models.category import CleanupCategory, SafetyLevel
from crapcleaner.utils.platform import is_linux, is_windows


def get_categories() -> list[CleanupCategory]:
    if not (is_windows() or is_linux()):
        return []

    return [
        CleanupCategory(
            id="application_crash_dumps",
            name="Application crash dumps",
            group="System",
            description="Memory snapshots written when an application crashed.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains=(
                "A copy of an application's memory at the moment it crashed, written for "
                "a developer to debug with."
            ),
            why_it_grows="Every crash writes another file, and nothing removes the old ones.",
            why_safe_to_delete=(
                "Only useful while investigating that specific crash. Keep one if you are "
                "about to file a bug report with it."
            ),
            regeneration_behavior="Written again the next time an application crashes.",
            reversible=True,
            finder=find_application_dump_paths,
        ),
        CleanupCategory(
            id="kernel_memory_dumps",
            name="Kernel & full memory dumps",
            group="System",
            description="Dumps written by a blue screen or a live kernel report.",
            safety_level=SafetyLevel.REVIEW,
            requires_admin=True,
            what_it_contains=(
                "MEMORY.DMP and the minidumps written when Windows stops unexpectedly. "
                "A full dump is as large as the RAM that was in use."
            ),
            why_it_grows="Each crash overwrites or adds a dump; full dumps are gigabytes.",
            why_safe_to_delete=(
                "Only needed to analyse a specific blue screen. Keep them while a crash "
                "is being investigated - they cannot be regenerated on demand."
            ),
            regeneration_behavior="Written again on the next stop error.",
            reversible=True,
            finder=find_kernel_dump_paths,
        ),
    ]
