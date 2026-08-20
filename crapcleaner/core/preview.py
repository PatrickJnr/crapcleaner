"""Pre-cleanup preview and item enumeration engine.

Generates a detailed manifest of all files, folders, and actions that would be
affected prior to execution, supporting item-level deselection and staleness checking.
"""

import fnmatch
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from crapcleaner.core.protected_paths import validate_cleanup_path
from crapcleaner.models.category import CacheTarget, CleanupCategory
from crapcleaner.utils.files import walk_safe


@dataclass
class PreviewItem:
    path: str
    size: int
    category_id: str
    category_name: str
    is_directory: bool
    selected: bool = True
    exists: bool = True

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "size": self.size,
            "category_id": self.category_id,
            "category_name": self.category_name,
            "is_directory": self.is_directory,
            "selected": self.selected,
            "exists": self.exists,
        }


@dataclass
class CategoryPreview:
    category_id: str
    category_name: str
    group: str
    safety_level: str
    requires_admin: bool
    reversible: bool
    action: str | None
    estimated_size: int = 0
    item_count: int = 0
    items: list[PreviewItem] = field(default_factory=list)
    selected: bool = True
    errors: list[str] = field(default_factory=list)
    #: True when more files were found than the manifest keeps. The totals still
    #: cover everything; only the listed sample is capped.
    items_truncated: bool = False

    def to_dict(self) -> dict:
        return {
            "category_id": self.category_id,
            "category_name": self.category_name,
            "group": self.group,
            "safety_level": self.safety_level,
            "requires_admin": self.requires_admin,
            "reversible": self.reversible,
            "action": self.action,
            "estimated_size": self.estimated_size,
            "item_count": self.item_count,
            "selected": self.selected,
            "items": [item.to_dict() for item in self.items],
            "items_truncated": self.items_truncated,
            "errors": self.errors,
        }


@dataclass
class CleanupPreview:
    generated_at: datetime
    categories: list[CategoryPreview] = field(default_factory=list)
    is_stale: bool = False

    @property
    def total_estimated_size(self) -> int:
        return sum(c.estimated_size for c in self.categories if c.selected)

    @property
    def total_item_count(self) -> int:
        return sum(c.item_count for c in self.categories if c.selected)

    def check_staleness(self) -> bool:
        """Verify if previewed items still exist on disk."""
        stale = False
        for cat in self.categories:
            for item in cat.items:
                if not os.path.exists(item.path) and not os.path.islink(item.path):
                    item.exists = False
                    stale = True
        self.is_stale = stale
        return stale

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "total_estimated_size": self.total_estimated_size,
            "total_item_count": self.total_item_count,
            "is_stale": self.is_stale,
            "categories": [c.to_dict() for c in self.categories],
        }


def generate_cleanup_preview(
    categories: list[CleanupCategory],
    max_items_per_category: int = 500,
    stop_event: threading.Event | None = None,
    progress_cb: Callable[[str, int, int], None] | None = None,
    resolve_finders: bool = False,
) -> CleanupPreview:
    """Enumerate all files and directories targeted by categories and build a pre-cleanup manifest.

    `max_items_per_category` caps the *listed* items only. Sizes and counts always
    cover everything that would be deleted: capping them made the preview understate
    exactly the categories where the number matters, and disagree with the scan.

    Categories that discover their targets through a finder normally reuse the
    numbers from the last scan, so opening the preview after a scan is instant.
    Set `resolve_finders` when no scan has run - a caller that previews cold, like
    the CLI, would otherwise show zero for categories that will really delete
    thousands of files.
    """
    preview = CleanupPreview(generated_at=datetime.now())
    total_cats = len(categories)

    for idx, cat in enumerate(categories):
        if stop_event is not None and stop_event.is_set():
            break
        if progress_cb is not None:
            progress_cb(cat.name, idx, total_cats)

        cat_prev = CategoryPreview(
            category_id=cat.id,
            category_name=cat.name,
            group=cat.group,
            safety_level=cat.safety_level.value,
            requires_admin=cat.requires_admin,
            reversible=cat.reversible,
            action=cat.action,
            selected=cat.selected_by_default,
        )

        if cat.action:
            cat_prev.estimated_size = cat.size
            cat_prev.item_count = 1
            cat_prev.items.append(
                PreviewItem(
                    path=f"Action: {cat.action}",
                    size=cat.size,
                    category_id=cat.id,
                    category_name=cat.name,
                    is_directory=False,
                )
            )
            preview.categories.append(cat_prev)
            continue

        targets = list(cat.targets)
        if cat.finder is not None and not targets:
            if not resolve_finders:
                cat_prev.estimated_size = cat.size
                cat_prev.item_count = cat.item_count
                preview.categories.append(cat_prev)
                continue
            try:
                targets = [CacheTarget(path=path) for path in cat.finder(*cat.finder_args)]
            except OSError as exc:
                cat_prev.errors.append(f"{cat.name}: {exc}")

        total_cat_size = 0
        total_cat_items = 0
        items: list[PreviewItem] = []

        for target in targets:
            if stop_event is not None and stop_event.is_set():
                break
            if not target.exists:
                continue

            is_safe, reason = validate_cleanup_path(target.path)
            if not is_safe:
                cat_prev.errors.append(reason)
                continue

            if os.path.isfile(target.path):
                try:
                    sz = os.path.getsize(target.path)
                    total_cat_size += sz
                    total_cat_items += 1
                    if len(items) < max_items_per_category:
                        items.append(
                            PreviewItem(
                                path=target.path,
                                size=sz,
                                category_id=cat.id,
                                category_name=cat.name,
                                is_directory=False,
                            )
                        )
                except OSError:
                    continue
                continue

            if not os.path.isdir(target.path):
                continue

            # Walk target directory
            try:
                if not target.recurse:
                    with os.scandir(target.path) as it:
                        for entry in it:
                            if entry.is_file(follow_symlinks=False):
                                if target.patterns and not any(
                                    fnmatch.fnmatch(entry.name.lower(), p.lower())
                                    for p in target.patterns
                                ):
                                    continue
                                is_f_safe, _ = validate_cleanup_path(entry.path)
                                if not is_f_safe:
                                    continue
                                try:
                                    sz = entry.stat(follow_symlinks=False).st_size
                                    total_cat_size += sz
                                    total_cat_items += 1
                                    if len(items) < max_items_per_category:
                                        items.append(
                                            PreviewItem(
                                                path=entry.path,
                                                size=sz,
                                                category_id=cat.id,
                                                category_name=cat.name,
                                                is_directory=False,
                                            )
                                        )
                                except OSError:
                                    continue
                else:
                    for root, dirs, files in walk_safe(target.path, topdown=True):
                        if stop_event is not None and stop_event.is_set():
                            break

                        for name in files:
                            if target.patterns and not any(
                                fnmatch.fnmatch(name.lower(), p.lower()) for p in target.patterns
                            ):
                                continue
                            full = os.path.join(root, name)
                            is_f_safe, _ = validate_cleanup_path(full)
                            if not is_f_safe:
                                continue
                            try:
                                sz = os.path.getsize(full)
                                total_cat_size += sz
                                total_cat_items += 1
                                if len(items) < max_items_per_category:
                                    items.append(
                                        PreviewItem(
                                            path=full,
                                            size=sz,
                                            category_id=cat.id,
                                            category_name=cat.name,
                                            is_directory=False,
                                        )
                                    )
                            except OSError:
                                continue
            except OSError as exc:
                cat_prev.errors.append(str(exc))

        cat_prev.estimated_size = total_cat_size
        cat_prev.item_count = total_cat_items
        cat_prev.items = items
        cat_prev.items_truncated = total_cat_items > len(items)
        preview.categories.append(cat_prev)

    return preview
