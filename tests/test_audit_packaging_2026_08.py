"""Regression tests for the 2026-08-19 audit: packaging and release integrity.

Finding IDs refer to audit.md.
"""

import os
import struct
import subprocess
import sys

import pytest

from crapcleaner.constants import VERSION

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestFrozenLauncherHonoursArguments:
    """PKG-01: the frozen entry point ignored argv and always opened the GUI."""

    def test_launcher_dispatches_through_the_shared_entry_point(self):
        with open(os.path.join(ROOT, "scripts", "launcher.py"), encoding="utf-8") as fh:
            source = fh.read()

        assert "from crapcleaner.app import main" in source
        assert "sys.exit(main())" in source
        assert "sys.exit(run_gui())" not in source, "the launcher bypasses argv handling again"

    def test_module_entry_point_reports_the_version(self):
        result = subprocess.run(
            [sys.executable, "-m", "crapcleaner", "--version"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=120,
        )

        assert result.returncode == 0
        assert VERSION in result.stdout

    def test_a_cli_flag_does_not_reach_the_gui(self):
        """`--scan` and friends must route to the CLI, not the window."""
        from unittest.mock import patch

        import crapcleaner.app as app_module

        with (
            patch("crapcleaner.cli.main", return_value=0) as cli_main,
            patch("crapcleaner.gui.app.run_gui") as run_gui,
        ):
            assert app_module.main(["--list-categories"]) == 0

        cli_main.assert_called_once()
        run_gui.assert_not_called()

    def test_explicit_gui_flags_still_open_the_window(self):
        from unittest.mock import patch

        import crapcleaner.app as app_module

        for flag in ("--gui", "-g"):
            with patch("crapcleaner.gui.app.run_gui", return_value=0) as run_gui:
                assert app_module.main([flag]) == 0
            run_gui.assert_called_once()

    def test_there_is_only_one_main_dispatcher(self):
        """ARCH-08: two mains disagreed about which flags launch the GUI."""
        import crapcleaner.gui as gui_package
        import crapcleaner.gui.app as gui_app

        assert not hasattr(gui_app, "main")
        assert gui_package.main.__module__ == "crapcleaner.app"


class TestApplicationIcon:
    """PKG-02: the executable shipped with PyInstaller's default icon."""

    @pytest.fixture
    def ico_path(self):
        path = os.path.join(ROOT, "crapcleaner", "assets", "crapcleaner.ico")
        assert os.path.isfile(path), "the committed application icon is missing"
        return path

    def test_the_container_is_a_valid_ico(self, ico_path):
        with open(ico_path, "rb") as fh:
            reserved, image_type, count = struct.unpack("<HHH", fh.read(6))

        assert reserved == 0
        assert image_type == 1, "not an icon container"
        assert count >= 1

    def test_every_entry_points_at_real_image_data(self, ico_path):
        with open(ico_path, "rb") as fh:
            blob = fh.read()
        _reserved, _type, count = struct.unpack("<HHH", blob[:6])

        sizes = []
        for index in range(count):
            entry = blob[6 + index * 16 : 6 + (index + 1) * 16]
            width, height, _palette, _res, _planes, _bpp, length, offset = struct.unpack(
                "<BBBBHHII", entry
            )
            assert length > 0
            assert offset + length <= len(blob), "entry points past the end of the file"
            assert blob[offset : offset + 8] == b"\x89PNG\r\n\x1a\n", "entry is not a PNG"
            sizes.append(width or 256)

        assert 16 in sizes and 256 in sizes, "no small or no large variant"
        assert len(set(sizes)) == len(sizes), "duplicate sizes"

    def test_the_spec_references_the_icon_and_version_resource(self):
        with open(os.path.join(ROOT, "CrapCleaner.spec"), encoding="utf-8") as fh:
            spec = fh.read()

        assert "icon=ICON" in spec
        assert "version=VERSION_FILE" in spec
        assert "upx=True" not in spec, "UPX packing is an antivirus heuristic magnet"


class TestVersionResource:
    """PKG-02: the executable carried no version metadata at all."""

    def test_dotted_version_becomes_four_integers(self):
        from scripts.version_info import version_tuple

        assert version_tuple("1.0.11.1") == (1, 0, 11, 1)
        assert version_tuple("1.0.11") == (1, 0, 11, 0)
        assert version_tuple("2.0") == (2, 0, 0, 0)

    def test_the_resource_carries_the_canonical_version(self):
        from scripts.version_info import render

        rendered = render(VERSION)

        assert f"'{VERSION}'" in rendered
        assert "CrapCleaner" in rendered
        assert "filevers=" in rendered

    def test_the_resource_is_valid_python(self, tmp_path):
        """PyInstaller evaluates this file, so a syntax error breaks the build."""
        from scripts.version_info import render

        compile(render(VERSION), "file_version_info.txt", "exec")


class TestReleaseVersionGate:
    """PKG-04: a tag that disagreed with the tree published the wrong version."""

    def test_the_current_tree_agrees_with_its_own_version(self):
        from scripts.check_release_version import problems

        assert problems(f"v{VERSION}") == []

    def test_a_mismatched_tag_is_rejected(self):
        from scripts.check_release_version import problems

        found = problems("v9.9.9")

        assert found
        assert any("constants.py" in line for line in found)

    def test_a_missing_changelog_section_is_rejected(self, tmp_path):
        from scripts.check_release_version import problems

        (tmp_path / "crapcleaner").mkdir()
        (tmp_path / "crapcleaner" / "constants.py").write_text('VERSION = "3.2.1"\n')
        (tmp_path / "crapcleaner" / "__init__.py").write_text('__version__ = "3.2.1"\n')
        (tmp_path / "pyproject.toml").write_text('version = "3.2.1"\n')
        (tmp_path / "CHANGELOG.md").write_text("## [3.2.0] - older\n")

        found = problems("v3.2.1", root=str(tmp_path))

        assert len(found) == 1
        assert "CHANGELOG" in found[0]

    def test_the_tag_prefix_is_optional(self):
        from scripts.check_release_version import normalize_tag

        assert normalize_tag("v1.2.3") == "1.2.3"
        assert normalize_tag("1.2.3") == "1.2.3"

    def test_the_command_exits_non_zero_on_a_mismatch(self):
        from scripts.check_release_version import main

        assert main(["v0.0.1"]) == 1
        assert main([f"v{VERSION}"]) == 0


class TestReleaseWorkflowIntegrity:
    """PKG-05, PKG-06: rebuilt assets and dispatch runs."""

    def _workflow(self, name: str) -> str:
        with open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8") as fh:
            return fh.read()

    def test_release_checkouts_use_the_requested_tag(self):
        workflow = self._workflow("release.yml")

        assert workflow.count("actions/checkout@v7") == workflow.count(
            "ref: ${{ github.event.inputs.target_tag || github.ref }}"
        )

    def test_release_verifies_the_version_before_building(self):
        assert "scripts/check_release_version.py" in self._workflow("release.yml")

    def test_rebuilt_releases_get_fresh_checksums(self):
        workflow = self._workflow("batch-rebuild-releases.yml")

        assert "Recompute Checksums" in workflow
        assert "checksums-windows.txt" in workflow
        assert "checksums-linux.txt" in workflow

    def test_ci_exercises_the_built_binary(self):
        workflow = self._workflow("ci.yml")

        assert "--version" in workflow, "CI only checked that the file exists"
        assert "requirements-dev.txt" in workflow, "CI installs unpinned tools"
