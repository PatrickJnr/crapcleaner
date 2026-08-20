"""Category registry: assembles categories from all providers."""

from collections.abc import Callable

from crapcleaner.categories.ai import get_categories as ai_categories
from crapcleaner.categories.apps import get_categories as apps_categories
from crapcleaner.categories.browsers import get_categories as browser_categories
from crapcleaner.categories.crash_dumps import get_categories as crash_dump_categories
from crapcleaner.categories.developer import get_categories as developer_categories
from crapcleaner.categories.docker import get_categories as docker_categories
from crapcleaner.categories.dotnet import get_categories as dotnet_categories
from crapcleaner.categories.gaming import get_categories as gaming_categories
from crapcleaner.categories.gpu import get_categories as gpu_categories
from crapcleaner.categories.node import get_categories as node_categories
from crapcleaner.categories.python import get_categories as python_categories
from crapcleaner.categories.trash import get_categories as trash_categories
from crapcleaner.categories.windows import get_categories as windows_categories
from crapcleaner.models.category import CleanupCategory
from crapcleaner.utils.logs import get_logger

logger = get_logger("registry")

SIMPLE_PROVIDERS: list[tuple[str, Callable[[], list[CleanupCategory]]]] = [
    ("Windows", windows_categories),
    ("Browsers", browser_categories),
    ("Node.js", node_categories),
    (".NET", dotnet_categories),
    ("Developer tools", developer_categories),
    ("Applications", apps_categories),
    ("GPU", gpu_categories),
    ("Gaming", gaming_categories),
    ("AI", ai_categories),
    ("Docker", docker_categories),
    ("System", trash_categories),
    ("Crash dumps", crash_dump_categories),
]


def get_all_categories() -> list[CleanupCategory]:
    from crapcleaner.config import load_settings

    settings = load_settings()
    scan_roots = settings.get("scan_roots", [])
    include_all_drives = bool(settings.get("scan_all_drives", True))

    categories: list[CleanupCategory] = []
    for group, provider in SIMPLE_PROVIDERS:
        try:
            categories.extend(provider())
        except Exception:
            # One broken provider must not remove every other category, but a
            # section vanishing silently has no explanation either.
            logger.warning("Category provider %r failed to load", group, exc_info=True)
            continue

    try:
        categories.extend(
            python_categories(scan_roots=scan_roots, include_all_drives=include_all_drives)
        )
    except Exception:
        logger.warning("Category provider 'Python' failed to load", exc_info=True)

    return categories


def get_category_by_name(
    name: str, categories: list[CleanupCategory] | None = None
) -> CleanupCategory:
    for category in categories if categories is not None else get_all_categories():
        if category.name.lower() == name.lower():
            return category
    raise KeyError(f"No category named {name!r}")


def find_categories(
    name_substring: str, categories: list[CleanupCategory] | None = None
) -> list[CleanupCategory]:
    """Categories whose name or id contains `name_substring`.

    Pass `categories` when resolving several names in a row: building the registry
    runs every provider and probes hundreds of paths, once per name otherwise.
    """
    needle = name_substring.lower()
    pool = categories if categories is not None else get_all_categories()
    return [c for c in pool if needle in c.name.lower() or needle in c.id.lower()]


def group_categories(categories: list[CleanupCategory]) -> dict[str, list[CleanupCategory]]:
    groups: dict[str, list[CleanupCategory]] = {}
    for category in categories:
        groups.setdefault(category.group, []).append(category)
    return groups
