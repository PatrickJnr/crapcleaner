"""Old Files Scanner for storage analysis and age-based audit.

Finds files that have not been modified for configurable day thresholds (e.g. 30, 90, 180, 365 days).
Purely read-only analysis; never deletes files automatically.
"""

import os
import stat
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class OldFileInfo:
    path: str
    name: str
    size: int
    last_modified: datetime
    age_days: int
    extension: str


def find_old_files(
    root_path: str,
    min_age_days: int = 90,
    min_size_bytes: int = 0,
    max_results: int = 1000,
    stop_event=None,
) -> list[OldFileInfo]:
    """Scan root_path and return files older than min_age_days without modification."""
    if not root_path or not os.path.exists(root_path):
        return []

    now_ts = time.time()
    cutoff_ts = now_ts - (min_age_days * 86400)
    results: list[OldFileInfo] = []

    try:
        for root, dirs, files in os.walk(root_path):
            if stop_event is not None and stop_event.is_set():
                break

            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    st = os.lstat(fpath)
                except OSError:
                    continue

                if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
                    continue

                mtime = st.st_mtime
                if mtime <= cutoff_ts and st.st_size >= min_size_bytes:
                    age_days = int((now_ts - mtime) / 86400)
                    ext = Path(fname).suffix.lower().lstrip(".")
                    results.append(
                        OldFileInfo(
                            path=fpath,
                            name=fname,
                            size=st.st_size,
                            last_modified=datetime.fromtimestamp(mtime),
                            age_days=age_days,
                            extension=ext or "unknown",
                        )
                    )
                    if len(results) >= max_results:
                        break
            if len(results) >= max_results:
                break
    except OSError:
        pass

    results.sort(key=lambda x: x.age_days, reverse=True)
    return results
