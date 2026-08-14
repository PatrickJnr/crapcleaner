"""GitHub Release and version updater utility for CrapCleaner."""

import json
import logging
import re
import urllib.error
import urllib.request
from typing import NamedTuple

from crapcleaner import __version__

_logger = logging.getLogger(__name__)

GITHUB_REPO = "PatrickJnr/crapcleaner"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


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


def check_for_updates(timeout_seconds: float = 4.0) -> UpdateInfo | None:
    """Check GitHub Releases API for latest published version."""
    try:
        req = urllib.request.Request(
            RELEASES_API_URL,
            headers={
                "User-Agent": f"CrapCleaner/{__version__}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode("utf-8"))

        tag = data.get("tag_name", "")
        latest_ver = tag.lstrip("vV")
        current_parsed = _parse_version(__version__)
        latest_parsed = _parse_version(latest_ver)

        is_newer = latest_parsed > current_parsed

        return UpdateInfo(
            current_version=__version__,
            latest_version=latest_ver,
            is_newer=is_newer,
            release_name=data.get("name", tag),
            html_url=data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases"),
            published_at=data.get("published_at", ""),
            body=data.get("body", ""),
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        _logger.debug("Failed to check for updates: %s", exc)
        return None
