"""Tests for GitHub contributors fetching, caching, rate limit handling, and offline fallback."""

import json
import time
import urllib.error
from unittest.mock import MagicMock, patch

from crapcleaner.utils.contributors import (
    fetch_contributors,
)


def test_contributors_success(tmp_path, monkeypatch):
    monkeypatch.setattr("crapcleaner.utils.contributors.config_dir", lambda: str(tmp_path))

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_payload = [
        {
            "login": "Alice",
            "avatar_url": "https://avatar.alice",
            "html_url": "https://github.com/Alice",
            "contributions": 15,
        },
        {
            "login": "Bob",
            "avatar_url": "https://avatar.bob",
            "html_url": "https://github.com/Bob",
            "contributions": 42,
        },
    ]
    mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = fetch_contributors(force_refresh=True)

    assert len(res) == 2
    # Should be sorted by contributions descending
    assert res[0].login == "Bob"
    assert res[0].contributions == 42
    assert res[1].login == "Alice"
    assert res[1].contributions == 15

    # Verify cache file was written
    cache_file = tmp_path / "contributors_cache.json"
    assert cache_file.exists()


def test_contributors_rate_limit_fallback_to_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("crapcleaner.utils.contributors.config_dir", lambda: str(tmp_path))

    # Pre-populate cache
    cache_file = tmp_path / "contributors_cache.json"
    payload = {
        "timestamp": time.time() - 100,
        "contributors": [
            {
                "login": "CachedDev",
                "avatar_url": "",
                "html_url": "https://github.com/CachedDev",
                "contributions": 10,
            }
        ],
    }
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    # Mock rate limit HTTPError 403
    http_err = urllib.error.HTTPError(
        url="https://api.github.com/...",
        code=403,
        msg="rate limit exceeded",
        hdrs={},
        fp=None,
    )
    with patch("urllib.request.urlopen", side_effect=http_err):
        res = fetch_contributors(force_refresh=True)

    assert len(res) == 1
    assert res[0].login == "CachedDev"


def test_contributors_timeout_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr("crapcleaner.utils.contributors.config_dir", lambda: str(tmp_path))

    with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
        res = fetch_contributors(force_refresh=True)

    # Offline without cache should return empty list gracefully
    assert res == []


def test_contributors_cached_without_network_call(tmp_path, monkeypatch):
    monkeypatch.setattr("crapcleaner.utils.contributors.config_dir", lambda: str(tmp_path))

    cache_file = tmp_path / "contributors_cache.json"
    payload = {
        "timestamp": time.time(),  # Fresh cache
        "contributors": [
            {"login": "FastDev", "avatar_url": "", "html_url": "", "contributions": 5}
        ],
    }
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    with patch("urllib.request.urlopen") as mock_url:
        res = fetch_contributors(force_refresh=False)
        mock_url.assert_not_called()

    assert len(res) == 1
    assert res[0].login == "FastDev"
