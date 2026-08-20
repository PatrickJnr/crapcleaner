"""Refuse to publish a release whose tag disagrees with the tree it was cut from.

The version lives in three files and the release notes in a fourth, all kept in step
by hand. Tagging an unbumped tree published binaries whose About page, window title
and `--version` all reported the previous release.

    python scripts/check_release_version.py v1.0.11.1

Exits non-zero, and says which file disagrees, when anything is out of step.
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def normalize_tag(tag: str) -> str:
    """`v1.0.11.1` and `1.0.11.1` both mean the same release."""
    return tag[1:] if tag.startswith(("v", "V")) else tag


def _search(path: str, pattern: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            match = re.search(pattern, fh.read(), re.MULTILINE)
    except OSError:
        return None
    return match.group(1) if match else None


def collect_versions(root: str = ROOT) -> dict[str, str | None]:
    """Every place the release version is written down."""
    return {
        "crapcleaner/constants.py": _search(
            os.path.join(root, "crapcleaner", "constants.py"),
            r'^VERSION\s*=\s*"([^"]+)"',
        ),
        "crapcleaner/__init__.py": _search(
            os.path.join(root, "crapcleaner", "__init__.py"),
            r'^__version__\s*=\s*"([^"]+)"',
        ),
        "pyproject.toml": _search(
            os.path.join(root, "pyproject.toml"),
            r'^version\s*=\s*"([^"]+)"',
        ),
    }


def changelog_has_section(version: str, root: str = ROOT) -> bool:
    """Whether CHANGELOG.md documents this version, which is where notes come from."""
    try:
        with open(os.path.join(root, "CHANGELOG.md"), encoding="utf-8") as fh:
            return (
                re.search(rf"^##\s*\[{re.escape(version)}\]", fh.read(), re.MULTILINE) is not None
            )
    except OSError:
        return False


def problems(tag: str, root: str = ROOT) -> list[str]:
    """Everything that disagrees with `tag`, as human-readable lines."""
    expected = normalize_tag(tag)
    found: list[str] = []
    if not expected:
        return ["No tag was supplied."]

    for source, value in collect_versions(root).items():
        if value is None:
            found.append(f"{source}: no version could be read")
        elif value != expected:
            found.append(f"{source}: says {value}, tag says {expected}")

    if not changelog_has_section(expected, root):
        found.append(f"CHANGELOG.md: no '## [{expected}]' section, release notes would be generic")
    return found


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: check_release_version.py <tag>", file=sys.stderr)
        return 2

    found = problems(args[0])
    if found:
        print(f"Release {args[0]} does not match the tree:", file=sys.stderr)
        for line in found:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print(f"Release {args[0]} matches constants.py, __init__.py, pyproject.toml and CHANGELOG.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
