"""Tests for GitHub updater utility."""

from unittest.mock import MagicMock, patch

from crapcleaner import __version__
from crapcleaner.utils.updater import _parse_version, check_for_updates


def test_parse_version():
    assert _parse_version("1.0.0") == (1, 0, 0)
    assert _parse_version("v1.2.3") == (1, 2, 3)
    assert _parse_version("2.1.0-alpha") == (2, 1, 0)


@patch("urllib.request.urlopen")
def test_check_for_updates_newer(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"tag_name": "v2.0.0", "name": "CrapCleaner 2.0", "html_url": "https://github.com/PatrickJnr/crapcleaner/releases/v2.0.0"}'
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    info = check_for_updates()
    assert info is not None
    assert info.latest_version == "2.0.0"
    assert info.is_newer is True
    assert info.html_url == "https://github.com/PatrickJnr/crapcleaner/releases/v2.0.0"


@patch("urllib.request.urlopen")
def test_check_for_updates_same(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = f'{{"tag_name": "v{__version__}", "name": "Current", "html_url": "https://github.com/PatrickJnr/crapcleaner/releases"}}'.encode()
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    info = check_for_updates()
    assert info is not None
    assert info.is_newer is False


@patch("urllib.request.urlopen")
def test_check_for_updates_network_failure(mock_urlopen):
    import urllib.error

    mock_urlopen.side_effect = urllib.error.URLError("No network connection")
    info = check_for_updates()
    assert info is None
