"""Regression tests for the 2026-08-19 audit: GUI, accessibility and platform parity.

Finding IDs refer to audit.md.
"""

import os
import sys
from unittest.mock import patch

import pytest

from crapcleaner.gui.color_engine import contrast_ratio
from crapcleaner.gui.theme import (
    _TEXT_BACKGROUNDS,
    _TEXT_ROLES,
    CONTRAST_EXEMPTIONS,
    MIN_TEXT_CONTRAST,
    PALETTES,
    palette_for,
)


class TestBuiltInPalettesMeetAA:
    """UX-02: ensure_contrast was applied to custom themes and not to the 44 built-ins."""

    @pytest.mark.parametrize("name", sorted(PALETTES))
    def test_rendered_text_pairs_meet_aa(self, name):
        if name in CONTRAST_EXEMPTIONS:
            pytest.skip(f"documented exemption: {CONTRAST_EXEMPTIONS[name]}")
        palette = palette_for(name)

        failures = []
        for role in _TEXT_ROLES:
            foreground = palette.get(role)
            if not foreground:
                continue
            for background_key in _TEXT_BACKGROUNDS:
                background = palette.get(background_key)
                if not background:
                    continue
                ratio = contrast_ratio(foreground, background)
                if ratio < MIN_TEXT_CONTRAST:
                    failures.append(f"{role} on {background_key}: {ratio:.2f}:1")

        assert not failures, f"{name} below AA - " + "; ".join(failures)

    def test_the_worst_previous_offender_is_readable(self):
        """commodore-64 rendered muted text at 1.21:1 on a hovered card."""
        palette = palette_for("commodore-64")

        assert contrast_ratio(palette["muted"], palette["elevated"]) >= MIN_TEXT_CONTRAST

    def test_palette_identity_is_preserved(self):
        """Only text colours move; the colours that make a theme recognisable stay."""
        for name in ("commodore-64", "gameboy", "dracula"):
            original, adjusted = PALETTES[name], palette_for(name)
            for key in ("accent", "window", "panel", "surface", "elevated", "border"):
                assert adjusted[key] == original[key], f"{name}.{key} was changed"

    def test_exemptions_carry_a_reason(self):
        for name, reason in CONTRAST_EXEMPTIONS.items():
            assert name in PALETTES, f"exemption for unknown palette {name}"
            assert reason.strip(), f"exemption for {name} has no reason"


class TestAboutPageDoesNoNetworkWhileBuilding:
    """UX-01: the About page fetched contributors and avatars on the GUI thread."""

    def test_view_constructs_with_the_network_unavailable(self, qt_app):
        """Constructing the page must not touch the network at all."""
        import crapcleaner.utils.contributors as contributors_module
        import crapcleaner.utils.updater as updater_module
        from crapcleaner.gui.views.about import AboutView

        def explode(*_args, **_kwargs):
            raise AssertionError("network access on the GUI thread")

        with (
            patch.object(contributors_module.urllib.request, "urlopen", explode),
            patch.object(updater_module.urllib.request, "urlopen", explode),
        ):
            view = AboutView(None)

        assert view is not None
        view.deleteLater()

    def test_contributor_fetching_happens_on_a_worker(self, qt_app):
        from crapcleaner.gui.views.about import AboutView
        from crapcleaner.gui.workers import ContributorsWorker

        started = []
        with patch.object(ContributorsWorker, "start", lambda self: started.append(self)):
            view = AboutView(None)

        assert started, "the contributor fetch did not go to a worker"
        assert isinstance(started[0], ContributorsWorker)
        view.deleteLater()

    def test_rendering_uses_already_fetched_data(self, qt_app):
        from crapcleaner.gui.views.about import AboutView
        from crapcleaner.gui.workers import ContributorsWorker
        from crapcleaner.utils.contributors import ContributorInfo

        with patch.object(ContributorsWorker, "start", lambda self: None):
            view = AboutView(None)
            view._show_contributors(
                [
                    (
                        ContributorInfo(
                            login="octocat",
                            contributions=7,
                            avatar_url="https://example.invalid/a.png",
                            html_url="https://example.invalid/octocat",
                        ),
                        "",
                    )
                ]
            )

        assert view.contrib_grid.count() >= 1
        view.deleteLater()

    def test_update_check_runs_on_a_worker(self, qt_app):
        from crapcleaner.gui.views.about import AboutView
        from crapcleaner.gui.workers import ContributorsWorker, UpdateCheckWorker

        with patch.object(ContributorsWorker, "start", lambda self: None):
            view = AboutView(None)

        started = []
        with patch.object(UpdateCheckWorker, "start", lambda self: started.append(self)):
            view._check_updates()

        assert started, "the update check still blocks the GUI thread"
        view.deleteLater()


class TestAccessibleNames:
    """UX-03: exactly one accessible name existed across the whole GUI."""

    def test_navigation_buttons_are_named(self, qt_app):
        from crapcleaner.gui.sidebar import NavButton

        button = NavButton("storage", "Storage Breakdown", "pie_chart")

        assert button.accessibleName() == "Storage Breakdown"
        assert button.accessibleDescription()

    def test_the_usage_chart_states_its_value(self, qt_app):
        from crapcleaner.gui.views.common import StorageDonut

        donut = StorageDonut()
        donut.set_usage(0.42, "dark")

        assert donut.accessibleName() == "Drive usage chart"
        assert "42" in donut.accessibleDescription()

    def test_drive_cards_are_named(self, qt_app):
        from crapcleaner.gui.views.common import DriveCard

        card = DriveCard("D:")

        assert "D:" in card.accessibleName()


class TestWindowClosesPromptly:
    """UX-05: close stopped and waited for each worker in turn, on the UI thread."""

    def test_all_workers_are_stopped_before_any_wait(self, qt_app):
        from crapcleaner.gui.app import MainWindow

        order = []

        class FakeWorker:
            def __init__(self, name):
                self.name = name

            def request_stop(self):
                order.append(("stop", self.name))

            def wait(self, _ms):
                order.append(("wait", self.name))
                return True

        window = MainWindow.__new__(MainWindow)
        window._workers = [FakeWorker("a"), FakeWorker("b")]

        with patch.object(MainWindow, "saveGeometry", create=True):
            try:
                MainWindow.closeEvent(window, _FakeEvent())
            except Exception:
                pass  # the rest of closeEvent needs a real window

        stops = [i for i, (kind, _) in enumerate(order) if kind == "stop"]
        waits = [i for i, (kind, _) in enumerate(order) if kind == "wait"]
        assert len(stops) == 2
        assert not waits or max(stops) < min(waits), "waited before asking everything to stop"

    def test_the_worker_list_is_iterated_as_a_copy(self):
        import inspect

        from crapcleaner.gui.app import MainWindow

        source = inspect.getsource(MainWindow.closeEvent)

        assert "list(self._workers)" in source


class _FakeEvent:
    def accept(self):
        pass

    def ignore(self):
        pass


class TestPlatformParity:
    """PLAT-02 and PLAT-03."""

    def test_drive_info_has_the_same_keys_on_every_platform(self):
        from crapcleaner.utils.platform import get_drive_info, list_drives

        info = get_drive_info(list_drives()[0])

        assert {
            "total",
            "used",
            "free",
            "label",
            "filesystem",
            "display_name",
            "display_kind",
        } <= set(info)

    def test_headless_linux_is_reported_rather_than_rendered_offscreen(self, monkeypatch):
        from crapcleaner.gui import app as app_module

        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.delenv("DISPLAY", raising=False)

        with pytest.raises(app_module.NoDisplayError) as excinfo:
            app_module._prepare_linux_qt_environment()

        assert "QT_QPA_PLATFORM=offscreen" in str(excinfo.value)
        assert os.environ.get("QT_QPA_PLATFORM") is None

    def test_an_explicit_platform_choice_is_honoured(self, monkeypatch):
        from crapcleaner.gui import app as app_module

        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

        app_module._prepare_linux_qt_environment()

        assert os.environ["QT_QPA_PLATFORM"] == "offscreen"

    def test_a_wayland_session_selects_wayland(self, monkeypatch):
        from crapcleaner.gui import app as app_module

        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")

        app_module._prepare_linux_qt_environment()

        assert os.environ["QT_QPA_PLATFORM"] == "wayland"


class TestLinuxCategoryCoverage:
    """PLAT-01: gaming and GPU categories built Windows paths and matched nothing."""

    def _linux_categories(self, module, home="/home/tester"):
        with (
            patch.object(module, "is_linux", return_value=True),
            patch.object(module, "is_windows", return_value=False),
            patch.object(module, "get_user_profile", return_value=home),
            patch.object(module, "get_local_appdata", return_value=f"{home}/.cache"),
        ):
            return module.get_categories()

    def test_linux_gaming_targets_real_steam_locations(self):
        import crapcleaner.categories.gaming as gaming

        categories = self._linux_categories(gaming)
        paths = [t.path for c in categories for t in c.targets]

        assert categories, "no gaming categories on Linux"
        assert any(".local" in p and "Steam" in p for p in paths)
        assert any(".var" in p and "com.valvesoftware.Steam" in p for p in paths)
        assert not any("Program Files" in p for p in paths)

    def test_linux_gaming_covers_the_other_launchers(self):
        import crapcleaner.categories.gaming as gaming

        ids = {c.id for c in self._linux_categories(gaming)}

        assert "heroic_cache_linux" in ids
        assert "lutris_bottles_cache_linux" in ids

    def test_linux_gpu_knows_the_mesa_cache(self, tmp_path, monkeypatch):
        import crapcleaner.categories.gpu as gpu

        home = tmp_path / "home"
        (home / ".cache" / "mesa_shader_cache").mkdir(parents=True)

        with (
            patch.object(gpu, "is_linux", return_value=True),
            patch.object(gpu, "is_windows", return_value=False),
            patch.object(gpu, "get_user_profile", return_value=str(home)),
            patch.object(gpu, "get_local_appdata", return_value=str(home / ".cache")),
        ):
            categories = gpu.get_categories()

        assert any(c.id == "mesa_shader_cache" for c in categories)

    def test_windows_categories_are_unchanged(self):
        import crapcleaner.categories.gaming as gaming

        with (
            patch.object(gaming, "is_linux", return_value=False),
            patch.object(gaming, "is_windows", return_value=True),
        ):
            ids = {c.id for c in gaming.get_categories()}

        assert "steam_caches" in ids
        assert "fivem_cache" in ids
