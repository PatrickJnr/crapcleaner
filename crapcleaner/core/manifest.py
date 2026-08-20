"""A record of what one cleanup run actually removed.

History stores counts; this stores paths, which is what a restore would need. A
manifest is a list of the files a user had, so it stays inside the config directory,
is never logged - not even in an error - and only the most recent runs are kept.
"""

import json
import os

from crapcleaner.models.report import CleanupReport

MANIFEST_DIR_NAME = "cleanup_manifests"
MANIFEST_VERSION = 1
#: Runs kept on disk.
MAX_MANIFESTS = 20
#: Paths recorded for one run. A cleanup can remove hundreds of thousands of files and
#: the whole list is held in memory before it is written.
MAX_MANIFEST_ITEMS = 50_000


def manifest_dir(config_dir: str) -> str:
    return os.path.join(config_dir, MANIFEST_DIR_NAME)


def write_manifest(report: CleanupReport, config_dir: str) -> str | None:
    """Record the paths `report` removed. Returns the file written, or None."""
    if report.dry_run or not report.removed:
        return None

    items = report.removed[:MAX_MANIFEST_ITEMS]
    payload = {
        "version": MANIFEST_VERSION,
        "started": report.started.isoformat(timespec="seconds"),
        "use_recycle_bin": report.use_recycle_bin,
        "truncated": len(report.removed) > len(items),
        "items": [
            {
                "path": item.path,
                "size": item.size,
                "recycled": item.recycled,
                "file_count": item.file_count,
            }
            for item in items
        ],
    }

    directory = manifest_dir(config_dir)
    path = os.path.join(directory, f"{report.started.strftime('%Y%m%d-%H%M%S-%f')}.json")
    try:
        os.makedirs(directory, exist_ok=True)
        temp = path + ".tmp"
        with open(temp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(temp, path)
    except OSError:
        return None
    _prune(directory)
    return path


def _prune(directory: str) -> None:
    """Drop all but the newest MAX_MANIFESTS runs. Names sort chronologically."""
    try:
        names = sorted(name for name in os.listdir(directory) if name.endswith(".json"))
    except OSError:
        return
    for name in names[:-MAX_MANIFESTS]:
        try:
            os.remove(os.path.join(directory, name))
        except OSError:
            pass


def read_manifest(path: str) -> dict:
    """The stored run at `path`, or an empty dict when it cannot be read."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("version") != MANIFEST_VERSION:
        return {}
    return data
