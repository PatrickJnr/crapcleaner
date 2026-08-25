"""Empty folder analyzer and detection engine.

Identifies empty directory structures left behind by uninstalled applications,
builds, or caches, with strict safety exclusions for protected system and developer paths.
"""

import os
import threading
from dataclasses import dataclass
from datetime import datetime

from crapcleaner.core.protected_paths import GuardStack


@dataclass
class EmptyFolderInfo:
    path: str
    name: str
    depth: int
    modified_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "name": self.name,
            "depth": self.depth,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
        }


def find_empty_folders(
    root: str,
    stop_event: threading.Event | None = None,
    min_depth: int = 1,
    max_results: int | None = 2000,
) -> list[EmptyFolderInfo]:
    """Find empty directories beneath root, strictly respecting safety guardrails."""
    if not root or not os.path.isdir(root):
        return []

    results: list[EmptyFolderInfo] = []
    guards = GuardStack()
    root_norm = os.path.abspath(root)

    for dirpath, dirnames, filenames in os.walk(root_norm, topdown=False):
        if stop_event is not None and stop_event.is_set():
            break

        guard = guards.guard_for(dirpath)
        if not guard.directory_allowed:
            continue

        rel = os.path.relpath(dirpath, root_norm)
        depth = 0 if rel == "." else len(rel.split(os.sep))
        if depth < min_depth:
            continue

        # Check if dir is currently empty on disk
        try:
            with os.scandir(dirpath) as it:
                is_empty = next(it, None) is None
        except OSError:
            continue

        if is_empty:
            mtime = None
            try:
                st = os.stat(dirpath)
                mtime = datetime.fromtimestamp(st.st_mtime)
            except OSError:
                pass

            info = EmptyFolderInfo(
                path=dirpath,
                name=os.path.basename(dirpath),
                depth=depth,
                modified_at=mtime,
            )
            results.append(info)
            if max_results is not None and len(results) >= max_results:
                break

    results.sort(key=lambda item: (item.depth, item.path), reverse=True)
    return results
