"""GitHub Contributors fetcher with local caching and offline fallback for CrapCleaner."""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from crapcleaner import __version__
from crapcleaner.config.settings import config_dir

_logger = logging.getLogger(__name__)

GITHUB_CONTRIBUTORS_URL = "https://api.github.com/repos/PatrickJnr/crapcleaner/contributors"
_CACHE_FILE = "contributors_cache.json"
_DEFAULT_CACHE_TTL = 86400  # 24 hours in seconds


@dataclass
class ContributorInfo:
    login: str
    avatar_url: str
    html_url: str
    contributions: int


def _get_cache_path() -> Path:
    return Path(config_dir()) / _CACHE_FILE


def _load_cached_contributors() -> tuple[list[ContributorInfo], float]:
    """Load cached contributors from local filesystem. Returns (list, timestamp)."""
    cache_path = _get_cache_path()
    if not cache_path.exists():
        return [], 0.0
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            ts = data.get("timestamp", 0.0)
            items = [
                ContributorInfo(
                    login=c.get("login", ""),
                    avatar_url=c.get("avatar_url", ""),
                    html_url=c.get("html_url", ""),
                    contributions=int(c.get("contributions", 0)),
                )
                for c in data.get("contributors", [])
                if c.get("login")
            ]
            return items, ts
    except Exception as exc:
        _logger.debug("Failed to read contributor cache: %s", exc)
        return [], 0.0


def _save_cached_contributors(contributors: list[ContributorInfo]) -> None:
    """Save contributors to local cache file."""
    cache_path = _get_cache_path()
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": time.time(),
            "contributors": [asdict(c) for c in contributors],
        }
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as exc:
        _logger.debug("Failed to write contributor cache: %s", exc)


def fetch_contributors(
    timeout_seconds: float = 5.0,
    force_refresh: bool = False,
    cache_ttl: float = _DEFAULT_CACHE_TTL,
) -> list[ContributorInfo]:
    """Fetch contributors from GitHub public API with local caching and offline fallback."""
    cached, ts = _load_cached_contributors()

    # If valid cache exists and not expired, return cached list
    if cached and not force_refresh and (time.time() - ts < cache_ttl):
        return sorted(cached, key=lambda c: c.contributions, reverse=True)

    try:
        req = urllib.request.Request(
            GITHUB_CONTRIBUTORS_URL,
            headers={
                "User-Agent": f"CrapCleaner/{__version__}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            if resp.status == 200:
                raw_data = json.loads(resp.read().decode("utf-8"))
                if isinstance(raw_data, list):
                    contributors = []
                    for item in raw_data:
                        if isinstance(item, dict) and item.get("login"):
                            contributors.append(
                                ContributorInfo(
                                    login=str(item.get("login")),
                                    avatar_url=str(item.get("avatar_url") or ""),
                                    html_url=str(
                                        item.get("html_url")
                                        or f"https://github.com/{item.get('login')}"
                                    ),
                                    contributions=int(item.get("contributions") or 0),
                                )
                            )
                    contributors.sort(key=lambda c: c.contributions, reverse=True)
                    if contributors:
                        _save_cached_contributors(contributors)
                        return contributors
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
        _logger.debug("GitHub contributors fetch failed (%s); falling back to cache.", exc)

    # Fallback to cached if available
    if cached:
        return sorted(cached, key=lambda c: c.contributions, reverse=True)

    return []


def fetch_avatar_file(avatar_url: str, login: str, timeout_seconds: float = 3.0) -> str | None:
    """Download and cache contributor avatar locally, returning local file path."""
    if not avatar_url or not login:
        return None
    avatars_dir = Path(config_dir()) / "avatars"
    target = avatars_dir / f"{login.lower()}.png"
    if target.exists() and target.stat().st_size > 0:
        return str(target)
    try:
        avatars_dir.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(
            avatar_url,
            headers={
                "User-Agent": f"CrapCleaner/{__version__}",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            if resp.status == 200:
                data = resp.read()
                with open(target, "wb") as f:
                    f.write(data)
                return str(target)
    except Exception as exc:
        _logger.debug("Failed to download avatar for %s: %s", login, exc)
    return None
