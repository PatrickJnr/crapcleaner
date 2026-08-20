"""Offline mode: no automatic GitHub call, and the skip is reported rather than silent."""

from unittest.mock import patch

import pytest

from crapcleaner.config import offline_mode, update_settings
from crapcleaner.constants import DEFAULT_CONFIG
from crapcleaner.utils import contributors, updater


@pytest.fixture
def offline():
    update_settings(offline_mode=True)


def _explode(*args, **kwargs):
    raise AssertionError("offline mode must not touch the network")


def test_offline_mode_is_off_until_it_is_turned_on():
    assert DEFAULT_CONFIG["offline_mode"] is False
    assert offline_mode() is False
    update_settings(offline_mode=True)
    assert offline_mode() is True


def test_the_update_check_is_skipped_and_has_a_reason(offline):
    with patch("urllib.request.urlopen", _explode):
        assert updater.check_for_updates() is None
    assert "offline mode" in (updater.offline_skip_reason() or "").lower()


def test_an_update_check_that_ran_has_no_reason():
    assert updater.offline_skip_reason() is None


def test_asking_for_updates_says_offline_mode_blocked_it(offline, capsys):
    from crapcleaner.cli import run

    assert run(["update"]) == 1
    assert "offline mode" in capsys.readouterr().err.lower()


def test_contributors_come_from_the_cache_without_the_network(offline, tmp_path, monkeypatch):
    monkeypatch.setattr(contributors, "config_dir", lambda: str(tmp_path))
    contributors._save_cached_contributors(
        [contributors.ContributorInfo("Alice", "", "https://github.com/Alice", 7)]
    )

    with patch("urllib.request.urlopen", _explode):
        people = contributors.fetch_contributors(force_refresh=True)

    assert [c.login for c in people] == ["Alice"]


def test_avatars_are_not_downloaded_offline(offline, tmp_path, monkeypatch):
    monkeypatch.setattr(contributors, "config_dir", lambda: str(tmp_path))

    with patch("urllib.request.urlopen", _explode):
        avatar = contributors.fetch_avatar_file(
            "https://avatars.githubusercontent.com/u/1", "alice"
        )

    assert avatar is None


def test_the_network_utilities_log_where_configure_logging_listens():
    assert updater._logger.name == "crapcleaner.updater"
    assert contributors._logger.name == "crapcleaner.contributors"
