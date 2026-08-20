"""GitHub Contributors fetcher with local caching and offline fallback for CrapCleaner."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from crapcleaner import __version__
from crapcleaner.config import config_dir, offline_mode
from crapcleaner.utils.logs import get_logger

_logger = get_logger("contributors")

GITHUB_CONTRIBUTORS_URL = "https://api.github.com/repos/PatrickJnr/crapcleaner/contributors"
_CACHE_FILE = "contributors_cache.json"
_DEFAULT_CACHE_TTL = 86400  # 24 hours


@dataclass
class ContributorInfo:
    login: str
    avatar_url: str
    html_url: str
    contributions: int


def _get_cache_path() -> Path:
    return Path(config_dir()) / _CACHE_FILE


def _load_cached_contributors() -> tuple[list[ContributorInfo], float]:
    """Return the cached contributors and the timestamp they were written."""
    cache_path = _get_cache_path()
    if not cache_path.exists():
        return [], 0.0
    try:
        with open(cache_path, encoding="utf-8") as f:
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

    if offline_mode():
        _logger.info("Offline mode is on; serving %d cached contributors", len(cached))
        return sorted(cached, key=lambda c: c.contributions, reverse=True)

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

    if cached:
        return sorted(cached, key=lambda c: c.contributions, reverse=True)

    return []


# The avatar URL comes from a writable cache file and urlopen honours file://,
# so it is restricted to GitHub over HTTPS and capped in size.
_AVATAR_MAX_BYTES = 2 * 1024 * 1024


def _is_github_avatar_url(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return host == "github.com" or host.endswith(".githubusercontent.com")


def fetch_avatar_file(avatar_url: str, login: str, timeout_seconds: float = 3.0) -> str | None:
    """Download and cache contributor avatar locally, returning local file path."""
    if not avatar_url or not login:
        return None
    if not _is_github_avatar_url(avatar_url):
        _logger.debug("Refusing avatar URL for %s: %s", login, avatar_url)
        return None
    avatars_dir = Path(config_dir()) / "avatars"
    target = avatars_dir / f"{login.lower()}.png"
    if target.exists() and target.stat().st_size > 0:
        return str(target)
    if offline_mode():
        _logger.info("Offline mode is on; no avatar downloaded for %s", login)
        return None
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
                data = resp.read(_AVATAR_MAX_BYTES + 1)
                if len(data) > _AVATAR_MAX_BYTES:
                    _logger.debug("Avatar for %s exceeds %d bytes", login, _AVATAR_MAX_BYTES)
                    return None
                with open(target, "wb") as f:
                    f.write(data)
                return str(target)
    except Exception as exc:
        _logger.debug("Failed to download avatar for %s: %s", login, exc)
    return None
