"""Remember what a scan measured, so the next one can say what changed.

A treemap answers "what is big". The question people actually arrive with is "my
drive filled up this week and I do not know why", which needs two points in time.
The storage scan already builds a full directory index; keeping a trimmed copy of
it costs a fraction of a second and makes the comparison free.

Only directories worth naming are stored - anything below `MIN_TRACKED_SIZE`, and
never more than `MAX_TRACKED_DIRS` of them - so the file stays small on a volume
with hundreds of thousands of folders.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass

from crapcleaner.utils.logs import get_logger

logger = get_logger("snapshots")

SNAPSHOT_DIR_NAME = "storage_snapshots"
#: Directories smaller than this are not worth reporting a change for.
MIN_TRACKED_SIZE = 1024 * 1024
#: Upper bound on stored directories, largest first.
MAX_TRACKED_DIRS = 20_000
SNAPSHOT_VERSION = 1


@dataclass(frozen=True)
class StorageChange:
    """One directory's change between two scans."""

    path: str
    previous_size: int
    current_size: int
    kind: str  # "grew", "shrank", "added", "removed"

    @property
    def delta(self) -> int:
        return self.current_size - self.previous_size

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "previous_size": self.previous_size,
            "current_size": self.current_size,
            "delta": self.delta,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class SnapshotComparison:
    """What changed under one root between two scans."""

    root: str
    previous_taken_at: float
    changes: list[StorageChange]
    previous_total: int
    current_total: int

    @property
    def total_delta(self) -> int:
        return self.current_total - self.previous_total

    def growth(self, limit: int = 20) -> list[StorageChange]:
        return [c for c in self.changes if c.delta > 0][:limit]

    def shrinkage(self, limit: int = 20) -> list[StorageChange]:
        return sorted([c for c in self.changes if c.delta < 0], key=lambda c: c.delta)[:limit]

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "previous_taken_at": self.previous_taken_at,
            "previous_total": self.previous_total,
            "current_total": self.current_total,
            "total_delta": self.total_delta,
            "changes": [c.to_dict() for c in self.changes],
        }


def snapshot_dir() -> str:
    from crapcleaner.config import config_dir

    return os.path.join(config_dir(), SNAPSHOT_DIR_NAME)


def snapshot_path(root: str) -> str:
    """One file per scanned root, named by a digest so any path is a valid filename."""
    key = hashlib.sha1(os.path.normcase(os.path.abspath(root)).encode("utf-8")).hexdigest()
    return os.path.join(snapshot_dir(), f"{key}.json")


def _tracked(sizes: dict[str, int]) -> dict[str, int]:
    worth_keeping = {path: size for path, size in sizes.items() if size >= MIN_TRACKED_SIZE}
    if len(worth_keeping) <= MAX_TRACKED_DIRS:
        return worth_keeping
    largest = sorted(worth_keeping.items(), key=lambda kv: kv[1], reverse=True)
    return dict(largest[:MAX_TRACKED_DIRS])


def sizes_from_index(index) -> dict[str, int]:
    """Directory sizes out of a `StorageIndex`."""
    return {path: node.size for path, node in index.nodes.items()}


def save_snapshot(root: str, sizes: dict[str, int], size_mode: str = "logical") -> str | None:
    """Store this scan's directory sizes. Returns the file written, or None."""
    payload = {
        "version": SNAPSHOT_VERSION,
        "root": os.path.abspath(root),
        "taken_at": time.time(),
        "size_mode": size_mode,
        "total": sizes.get(os.path.abspath(root), sizes.get(root, 0)),
        "dirs": _tracked(sizes),
    }
    path = snapshot_path(root)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temp = path + ".tmp"
        with open(temp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(temp, path)
    except OSError:
        logger.debug("Could not write the storage snapshot for %s", root, exc_info=True)
        return None
    return path


def load_snapshot(root: str) -> dict | None:
    """The previous scan of this root, or None if there is not one to compare with."""
    try:
        with open(snapshot_path(root), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != SNAPSHOT_VERSION:
        return None
    if not isinstance(data.get("dirs"), dict):
        return None
    return data


def compare(
    root: str,
    sizes: dict[str, int],
    previous: dict | None = None,
    min_delta: int = MIN_TRACKED_SIZE,
) -> SnapshotComparison | None:
    """What changed under `root` since the stored scan.

    Returns None when there is nothing to compare against, or when the stored scan
    used a different size mode - comparing logical against allocated sizes would
    report a change that is only a change of units.
    """
    previous = previous if previous is not None else load_snapshot(root)
    if previous is None:
        return None

    before: dict[str, int] = {str(k): int(v) for k, v in previous.get("dirs", {}).items()}
    after = _tracked(sizes)

    changes: list[StorageChange] = []
    for path, current in after.items():
        was = before.get(path)
        if was is None:
            if current >= min_delta:
                changes.append(StorageChange(path, 0, current, "added"))
            continue
        if abs(current - was) >= min_delta:
            changes.append(StorageChange(path, was, current, "grew" if current > was else "shrank"))
    for path, was in before.items():
        if path not in after and was >= min_delta:
            changes.append(StorageChange(path, was, 0, "removed"))

    changes.sort(key=lambda c: abs(c.delta), reverse=True)
    absolute_root = os.path.abspath(root)
    return SnapshotComparison(
        root=absolute_root,
        previous_taken_at=float(previous.get("taken_at", 0.0)),
        changes=changes,
        previous_total=int(previous.get("total", 0)),
        current_total=int(sizes.get(absolute_root, sizes.get(root, 0))),
    )


def clear_snapshots() -> None:
    """Forget every stored scan."""
    directory = snapshot_dir()
    try:
        for name in os.listdir(directory):
            if name.endswith(".json"):
                os.remove(os.path.join(directory, name))
    except OSError:
        pass
