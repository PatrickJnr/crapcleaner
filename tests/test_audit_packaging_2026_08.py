"""Regression tests for the 2026-08-19 audit: packaging and release integrity.

Finding IDs refer to audit.md.
"""

import os
import re
import struct
import subprocess
import sys

import pytest
import yaml

from crapcleaner.constants import VERSION

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _workflow_yaml(name: str) -> dict:
    with open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _script(job: dict) -> str:
    """Every shell line a job runs, as one blob."""
    return "\n".join(step.get("run") or "" for step in job["steps"])


def _released_files(job: dict) -> list[str]:
    """Asset paths the job attaches to a GitHub release."""
    return [
        line.strip()
        for step in job["steps"]
        if str(step.get("uses", "")).startswith("softprops/action-gh-release@")
        for line in (step.get("with", {}).get("files") or "").splitlines()
        if line.strip()
    ]


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
    """PKG-05, PKG-06, REL-01, REL-03: what the release path actually runs."""

    def test_release_checkouts_use_the_requested_tag(self):
        workflow = _workflow_yaml("release.yml")
        checkouts = [
            step
            for job in workflow["jobs"].values()
            for step in job["steps"]
            if str(step.get("uses", "")).startswith("actions/checkout@")
        ]

        assert len(checkouts) == len(workflow["jobs"]), "a job checks out nothing, or twice"
        for step in checkouts:
            assert step["with"]["ref"] == "${{ github.event.inputs.target_tag || github.ref }}"

    def test_release_verifies_the_version_before_building(self):
        workflow = _workflow_yaml("release.yml")

        assert "scripts/check_release_version.py" in _script(workflow["jobs"]["verify"])
        for job in ("build-windows-exe", "build-linux-bin"):
            assert workflow["jobs"][job]["needs"] == "verify"

    def test_release_lints_and_type_checks_before_building(self):
        """REL-03: a tag can be cut from a commit that never reached master, and ci.yml
        does not fire on tags, so these gates have to exist here too."""
        script = _script(_workflow_yaml("release.yml")["jobs"]["verify"])

        assert "ruff check crapcleaner tests scripts" in script
        assert "ruff format --check crapcleaner tests scripts" in script
        assert "mypy crapcleaner" in script

    def test_the_published_linux_binary_is_executed_before_release(self):
        """REL-01: the smoke test was gated to Windows, so no Linux binary ever ran."""
        workflow = _workflow_yaml("release.yml")
        script = _script(workflow["jobs"]["build-linux-bin"])

        assert "./dist/crapcleaner-linux-x86_64 --version" in script
        assert "constants import VERSION" in script, "the reported version is not checked"
        assert set(workflow["jobs"]["publish-release"]["needs"]) == {
            "build-windows-exe",
            "build-linux-bin",
        }

    def test_the_published_windows_binary_is_executed_before_release(self):
        script = _script(_workflow_yaml("release.yml")["jobs"]["build-windows-exe"])

        assert "./dist/CrapCleaner.exe --version" in script
        assert "constants import VERSION" in script

    def test_the_release_notes_step_does_not_swallow_a_failure(self):
        """REL-05: `|| echo` published the newest notes under whatever tag was asked for."""
        script = _script(_workflow_yaml("release.yml")["jobs"]["publish-release"])

        assert "extract_changelog.py" in script
        assert "||" not in script, "a fallback here substitutes the wrong release's notes"

    def test_ci_exercises_the_built_binary(self):
        script = _script(_workflow_yaml("ci.yml")["jobs"]["test"])

        assert "--version" in script, "CI only checked that the file exists"


class TestBatchRebuildIntegrity:
    """REL-02, REL-04: rebuilds republished binaries unverified, over stale checksums."""

    def test_the_canonical_checksums_file_is_regenerated(self):
        """README tells users to verify against checksums.txt; per-OS files are not it."""
        publish = _workflow_yaml("batch-rebuild-releases.yml")["jobs"]["publish"]

        assert any(name.endswith("checksums.txt") for name in _released_files(publish))
        assert "> checksums.txt" in _script(publish), "checksums.txt is uploaded but never rebuilt"

    def test_every_asset_of_a_release_is_replaced_together(self):
        publish = _workflow_yaml("batch-rebuild-releases.yml")["jobs"]["publish"]

        assert {os.path.basename(p) for p in _released_files(publish)} == {
            "CrapCleaner.exe",
            "crapcleaner-linux-x86_64",
            "crapcleaner-linux-x86_64.tar.gz",
            "checksums.txt",
        }

    def test_the_rebuilt_binary_must_report_the_tag_it_claims(self):
        script = _script(_workflow_yaml("batch-rebuild-releases.yml")["jobs"]["build"])

        assert "--version" in script, "the rebuilt binary is never run"
        assert "matrix.tag" in script, "the reported version is not compared to the tag"

    def test_only_the_publishing_job_may_write_to_releases(self):
        workflow = _workflow_yaml("batch-rebuild-releases.yml")

        assert workflow["jobs"]["build"]["permissions"] == {"contents": "read"}
        assert workflow["jobs"]["publish"]["permissions"]["contents"] == "write"
        assert workflow["jobs"]["publish"]["needs"] == "build"


class TestBuildToolingIsPinned:
    """SUP-01: shipped binaries were bundled against whatever pip resolved that morning."""

    @staticmethod
    def _pins() -> dict[str, str]:
        pins = {}
        with open(os.path.join(ROOT, "requirements-build.txt"), encoding="utf-8") as fh:
            for line in fh:
                entry = line.split("#")[0].strip()
                if entry:
                    name, _, version = entry.partition("==")
                    pins[name.lower()] = version
        return pins

    def test_the_build_requirements_are_exact_versions(self):
        pins = self._pins()

        assert set(pins) == {"pyside6", "pyinstaller"}
        for name, version in pins.items():
            assert re.fullmatch(r"\d+(\.\d+)+", version), f"{name} is a range, not a pin"

    def test_every_job_that_runs_pyinstaller_installs_the_pins(self):
        for name in ("ci.yml", "release.yml", "batch-rebuild-releases.yml"):
            jobs = _workflow_yaml(name)["jobs"]
            builders = {
                job_name: _script(job)
                for job_name, job in jobs.items()
                if "pyinstaller --noconfirm" in _script(job)
            }

            assert builders, f"{name} no longer builds a binary"
            for job_name, script in builders.items():
                where = f"{name}:{job_name}"
                assert re.search(r"-r requirements-(build|dev)\.txt", script), where
                assert not re.search(r"pip install\s+pyinstaller\b", script), where


class TestBuildProvenance:
    """DIST-05: a published binary had no verifiable link to the commit that built it."""

    def test_the_publishing_job_attests_every_binary(self):
        publish = _workflow_yaml("release.yml")["jobs"]["publish-release"]
        attestations = [
            step
            for step in publish["steps"]
            if str(step.get("uses", "")).startswith("actions/attest-build-provenance@")
        ]

        assert len(attestations) == 1
        subjects = {
            os.path.basename(path) for path in attestations[0]["with"]["subject-path"].split()
        }

        # Taken from what the release actually publishes rather than a list kept by
        # hand: adding a binary and forgetting to attest it is the failure this guards
        # against, and a hand-written list only catches it if someone remembers to
        # extend it too.
        release = next(
            step
            for step in publish["steps"]
            if str(step.get("uses", "")).startswith("softprops/action-gh-release@")
        )
        published = {os.path.basename(path) for path in release["with"]["files"].split()}
        binaries = published - {"checksums.txt"}

        assert binaries, "the release publishes nothing to attest"
        assert subjects == binaries, (
            f"published but unattested: {sorted(binaries - subjects)}; "
            f"attested but unpublished: {sorted(subjects - binaries)}"
        )

    def test_the_publishing_job_holds_the_tokens_attestation_needs(self):
        permissions = _workflow_yaml("release.yml")["jobs"]["publish-release"]["permissions"]

        assert permissions["id-token"] == "write"
        assert permissions["attestations"] == "write"
        assert permissions["contents"] == "write"


class TestDistributionMetadata:
    """DIST-03: pyproject carried name, version and description, and nothing publishable."""

    @staticmethod
    def _project() -> dict:
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as fh:
            return tomllib.load(fh)["project"]

    def test_the_package_describes_itself(self):
        project = self._project()

        assert project["readme"] == "README.md"
        assert project["license"] == "MIT"
        assert project["license-files"] == ["LICENSE"]
        assert project["authors"]
        assert project["keywords"]

    def test_the_classifiers_cover_the_tested_pythons(self):
        classifiers = self._project()["classifiers"]

        for minor in (10, 11, 12):
            assert f"Programming Language :: Python :: 3.{minor}" in classifiers
        # PEP 639: a license expression and a license classifier must not both appear.
        assert not any(entry.startswith("License ::") for entry in classifiers)

    def test_the_python_bound_matches_what_ci_actually_tests(self):
        matrix = _workflow_yaml("ci.yml")["jobs"]["test"]["strategy"]["matrix"]["python-version"]

        assert matrix == ["3.10", "3.11", "3.12"]
        assert self._project()["requires-python"] == ">=3.10,<3.14"

    def test_the_urls_point_at_the_repository(self):
        urls = self._project()["urls"]

        assert set(urls) == {"Homepage", "Repository", "Issues", "Changelog"}
        for url in urls.values():
            assert url.startswith("https://github.com/PatrickJnr/crapcleaner")

    def test_a_gui_launch_gets_a_windowless_entry_point(self):
        """A console entry point opens a terminal behind the window on Windows."""
        project = self._project()

        assert project["gui-scripts"] == {"crapcleaner-gui": "crapcleaner.app:main"}
        assert project["scripts"] == {"crapcleaner": "crapcleaner.app:main"}


def test_every_workflow_job_declares_its_permissions():
    """Code scanning flagged five jobs inheriting the default token scope."""
    import pathlib

    import yaml

    offenders = []
    for path in sorted(pathlib.Path(".github/workflows").glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data.get("permissions") is not None:
            continue
        for job, body in (data.get("jobs") or {}).items():
            if (body or {}).get("permissions") is None:
                offenders.append(f"{path.name}:{job}")
    assert not offenders, f"jobs inheriting the default token scope: {offenders}"


def test_only_publishing_jobs_may_write():
    import pathlib

    import yaml

    writers = []
    for path in sorted(pathlib.Path(".github/workflows").glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job, body in (data.get("jobs") or {}).items():
            perms = (body or {}).get("permissions") or {}
            if perms.get("contents") == "write":
                writers.append(job)
    assert writers, "something must be able to publish a release"
    assert all("publish" in job for job in writers), (
        f"non-publishing job with write access: {writers}"
    )
