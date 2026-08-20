"""GitHub Release and version updater utility for CrapCleaner."""

import json
import re
import urllib.error
import urllib.request
from typing import Any, NamedTuple

from crapcleaner import __version__
from crapcleaner.config import offline_mode
from crapcleaner.utils.logs import get_logger

_logger = get_logger("updater")

OFFLINE_REASON = (
    "Offline mode is on, so CrapCleaner did not contact GitHub. "
    "Turn offline mode off in Settings to check for updates."
)

GITHUB_REPO = "PatrickJnr/crapcleaner"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
ALL_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
TAGS_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/tags"


class UpdateInfo(NamedTuple):
    current_version: str
    latest_version: str
    is_newer: bool
    release_name: str
    html_url: str
    published_at: str
    body: str


def _parse_version(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", v)
    return tuple(int(n) for n in nums) or (0,)


def _fetch_json(url: str, timeout_seconds: float = 5.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"CrapCleaner/{__version__}",
            "Accept": "application/vnd.github.v3+json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        if resp.status == 200:
            return json.loads(resp.read().decode("utf-8"))
    return None


def offline_skip_reason() -> str | None:
    """Why an update check will not reach GitHub, or None when it will."""
    return OFFLINE_REASON if offline_mode() else None


def check_for_updates(timeout_seconds: float = 5.0) -> UpdateInfo | None:
    """Check GitHub API for latest published version with multi-endpoint fallback."""
    if offline_mode():
        _logger.info("Offline mode is on; skipped the update check")
        return None

    current_parsed = _parse_version(__version__)

    try:
        data = _fetch_json(RELEASES_API_URL, timeout_seconds=timeout_seconds)
        if isinstance(data, dict) and data.get("tag_name"):
            tag = str(data["tag_name"])
            latest_ver = tag.lstrip("vV")
            return UpdateInfo(
                current_version=__version__,
                latest_version=latest_ver,
                is_newer=_parse_version(latest_ver) > current_parsed,
                release_name=str(data.get("name") or tag),
                html_url=str(data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases"),
                published_at=str(data.get("published_at") or ""),
                body=str(data.get("body") or ""),
            )
    except Exception as exc:
        _logger.debug("Latest release check failed: %s", exc)

    try:
        data = _fetch_json(ALL_RELEASES_URL, timeout_seconds=timeout_seconds)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            first = data[0]
            tag = str(first.get("tag_name", ""))
            latest_ver = tag.lstrip("vV")
            return UpdateInfo(
                current_version=__version__,
                latest_version=latest_ver,
                is_newer=_parse_version(latest_ver) > current_parsed,
                release_name=str(first.get("name") or tag),
                html_url=str(first.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases"),
                published_at=str(first.get("published_at") or ""),
                body=str(first.get("body") or ""),
            )
    except Exception as exc:
        _logger.debug("All releases fallback check failed: %s", exc)

    try:
        data = _fetch_json(TAGS_API_URL, timeout_seconds=timeout_seconds)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            first_tag = str(data[0].get("name", ""))
            latest_ver = first_tag.lstrip("vV")
            return UpdateInfo(
                current_version=__version__,
                latest_version=latest_ver,
                is_newer=_parse_version(latest_ver) > current_parsed,
                release_name=f"Release {first_tag}",
                html_url=f"https://github.com/{GITHUB_REPO}/releases/tag/{first_tag}",
                published_at="",
                body="",
            )
    except Exception as exc:
        _logger.debug("Tags fallback check failed: %s", exc)

    return None
