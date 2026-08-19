"""Recycle Bin / Trash emptying, presented in the host platform's own terms."""

from crapcleaner.models.category import CleanupCategory, SafetyLevel
from crapcleaner.utils.platform import is_windows


def get_categories() -> list[CleanupCategory]:
    """One category, named for the platform it runs on.

    The id stays `recycle_bin` on both platforms so an existing
    `disabled_categories` setting keeps working.
    """
    if is_windows():
        return [
            CleanupCategory(
                id="recycle_bin",
                name="Recycle Bin",
                group="Windows",
                description=(
                    "Empties the Recycle Bin using the official Windows API. Permanently "
                    "deletes its contents - requires explicit confirmation."
                ),
                safety_level=SafetyLevel.REVIEW,
                action="empty_recycle_bin",
                what_it_contains="Items previously sent to the Windows Recycle Bin across all drives.",
                why_it_grows="Deleted files remain stored in the Recycle Bin until explicitly emptied.",
                why_safe_to_delete="Permanently removes files you previously chose to delete.",
                regeneration_behavior="Empty until more items are deleted to the Recycle Bin.",
                reversible=False,
                targets=[],
            )
        ]

    return [
        CleanupCategory(
            id="recycle_bin",
            name="Trash",
            group="System",
            description=(
                "Empties the FreeDesktop trash for your user account. Permanently deletes "
                "its contents - requires explicit confirmation."
            ),
            safety_level=SafetyLevel.REVIEW,
            action="empty_recycle_bin",
            what_it_contains="Files you previously moved to the trash, and their restore metadata.",
            why_it_grows="Trashed files stay on disk until the trash is emptied.",
            why_safe_to_delete="Permanently removes files you already chose to delete.",
            regeneration_behavior="Empty until more files are moved to the trash.",
            reversible=False,
            targets=[],
        )
    ]
