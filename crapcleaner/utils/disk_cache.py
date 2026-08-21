"""A tiny on-disk cache for probes that are expensive and rarely change.

Several inspections cost seconds of PowerShell but describe hardware that does not move
between launches. Holding them only in memory means paying that cost again on every
start.

Every entry carries a *signature* supplied by the caller: a cheap value that changes
exactly when the cached answer stops being true, such as the set of mounted drives. A
read whose signature does not match is a miss, so a stale answer is never served. There
is deliberately no expiry — a timer would either discard answers that are still correct
or serve ones that are not.
"""

import json
import os
import tempfile
import threading
from typing import Any

from crapcleaner.config import config_dir
from crapcleaner.utils.logs import get_logger

logger = get_logger(__name__)

CACHE_FILE = "probe_cache.json"

#: A corrupt or hand-edited cache must never crash a launch, and anything unreadable is
#: simply treated as empty.
_lock = threading.Lock()


def cache_path() -> str:
    return os.path.join(config_dir(), CACHE_FILE)


def _read_all() -> dict[str, Any]:
    try:
        with open(cache_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_all(data: dict[str, Any]) -> None:
    path = cache_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Written through a temporary file: a half-written cache is indistinguishable
        # from a corrupt one, and this runs while the app is being closed.
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=os.path.dirname(path),
            delete=False,
            suffix=".tmp",
        ) as handle:
            json.dump(data, handle)
            temp_path = handle.name
        os.replace(temp_path, path)
    except OSError as exc:
        logger.debug("could not write probe cache: %s", exc)


def load(name: str, signature: Any) -> Any | None:
    """The cached payload for `name`, or None when absent or out of date."""
    with _lock:
        entry = _read_all().get(name)
    if not isinstance(entry, dict):
        return None
    # JSON has no tuples, so a signature round-trips as a list.
    if entry.get("signature") != json.loads(json.dumps(signature)):
        return None
    return entry.get("payload")


def store(name: str, signature: Any, payload: Any) -> None:
    """Remember `payload` until `signature` changes."""
    with _lock:
        data = _read_all()
        data[name] = {"signature": signature, "payload": payload}
        _write_all(data)


def clear(name: str | None = None) -> None:
    """Forget one entry, or the whole cache when no name is given."""
    with _lock:
        if name is None:
            try:
                os.remove(cache_path())
            except OSError:
                pass
            return
        data = _read_all()
        if data.pop(name, None) is not None:
            _write_all(data)
