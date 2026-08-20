"""GUI views package.

Each major view lives in its own module; this package re-exports every public
name so `from crapcleaner.gui.views import SettingsView` keeps working.
"""

from crapcleaner.gui.views.about import (
    AboutView,
)
from crapcleaner.gui.views.ai_data import (
    AiDataView,
)
from crapcleaner.gui.views.cleanup import (
    CleanupView,
)
from crapcleaner.gui.views.common import (
    ClickableCard,
    ContributorCard,
    CrapTable,
    DriveCard,
    NumericItem,
    SkeletonBlock,
    SquircleAvatarWidget,
    StorageDonut,
    _c,
    _safety_color,
    _SizeSortedItem,
    badge,
    delete_paths,
    offline_skip_note,
    page_header,
    restyle_stat_card,
    section_label,
    stat_card,
)
from crapcleaner.gui.views.dashboard import (
    DashboardView,
)
from crapcleaner.gui.views.docker import (
    DockerView,
)
from crapcleaner.gui.views.duplicates import (
    _MAX_DUPLICATE_GROUP_ROWS,
    _MAX_DUPLICATE_TOOLTIP_FILES,
    DuplicatesView,
)
from crapcleaner.gui.views.help_safety import (
    HelpSafetyView,
)
from crapcleaner.gui.views.history import (
    HistoryView,
)
from crapcleaner.gui.views.large_files import (
    _MAX_LARGE_FILE_ROWS,
    LargeFilesView,
)
from crapcleaner.gui.views.memory import (
    MemoryView,
)
from crapcleaner.gui.views.services import (
    ServicesView,
)
from crapcleaner.gui.views.settings import (
    SettingsView,
)
from crapcleaner.gui.views.specs import (
    SpecsView,
)
from crapcleaner.gui.views.startup import (
    AddStartupDialog,
    StartupView,
)
from crapcleaner.gui.views.storage import (
    StorageBreakdownView,
    StorageCell,
    StorageGrid,
    _squarify,
    _worst,
)
from crapcleaner.gui.views.updates import (
    AppUpdatesView,
    SystemUpdatesView,
    WindowsUpdateView,
)

__all__ = [
    "AboutView",
    "AddStartupDialog",
    "AiDataView",
    "AppUpdatesView",
    "CleanupView",
    "ClickableCard",
    "ContributorCard",
    "CrapTable",
    "DashboardView",
    "DockerView",
    "DriveCard",
    "DuplicatesView",
    "HelpSafetyView",
    "HistoryView",
    "LargeFilesView",
    "MemoryView",
    "NumericItem",
    "ServicesView",
    "SettingsView",
    "SkeletonBlock",
    "SpecsView",
    "SquircleAvatarWidget",
    "StartupView",
    "StorageBreakdownView",
    "StorageCell",
    "StorageDonut",
    "StorageGrid",
    "SystemUpdatesView",
    "WindowsUpdateView",
    "_MAX_DUPLICATE_GROUP_ROWS",
    "_MAX_DUPLICATE_TOOLTIP_FILES",
    "_MAX_LARGE_FILE_ROWS",
    "_SizeSortedItem",
    "_c",
    "_safety_color",
    "_squarify",
    "_worst",
    "badge",
    "delete_paths",
    "offline_skip_note",
    "page_header",
    "restyle_stat_card",
    "section_label",
    "stat_card",
]
