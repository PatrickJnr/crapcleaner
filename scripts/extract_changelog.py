#!/usr/bin/env python3
"""Extract the release notes section for a given version tag from CHANGELOG.md."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def extract_changelog(
    version: str | None = None,
    changelog_path: Path | str = "CHANGELOG.md",
) -> str:
    """Extract markdown notes for a specific version or the latest version from CHANGELOG.md.

    Args:
        version: Version string (e.g., '1.0.6', 'v1.0.6', 'refs/tags/v1.0.6'). If None,
            the topmost release section is extracted.
        changelog_path: Path to the CHANGELOG.md file.

    Returns:
        Extracted markdown string for the release notes.
    """
    path = Path(changelog_path)
    if not path.is_file():
        return ""

    content = path.read_text(encoding="utf-8")

    if version:
        # Normalize version string: remove refs/tags/ and leading v
        clean_ver = version.replace("refs/tags/", "").lstrip("v").strip()
        pattern = rf"##\s*\[{re.escape(clean_ver)}\][^\n]*\n(.*?)(?=\n##\s*\[|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            body = match.group(1).strip()
            body = re.sub(r"\n---\s*$", "", body).strip()
            return body

    # Fallback: extract the first/latest release section
    first_match = re.search(r"##\s*\[[^\]]+\][^\n]*\n(.*?)(?=\n##\s*\[|\Z)", content, re.DOTALL)
    if first_match:
        body = first_match.group(1).strip()
        body = re.sub(r"\n---\s*$", "", body).strip()
        return body

    return ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract release notes for a version from CHANGELOG.md."
    )
    parser.add_argument(
        "version",
        nargs="?",
        default=None,
        help="Version tag to extract (e.g. 'v1.0.6', '1.0.6'). Defaults to topmost section.",
    )
    parser.add_argument(
        "--changelog",
        "-c",
        default="CHANGELOG.md",
        help="Path to CHANGELOG.md (default: CHANGELOG.md).",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Optional file path to write extracted notes into instead of stdout.",
    )

    args = parser.parse_args()
    notes = extract_changelog(args.version, args.changelog)

    if not notes:
        sys.stderr.write(f"Warning: No changelog section found for version '{args.version}'\n")

    if args.output:
        Path(args.output).write_text(notes, encoding="utf-8")
    else:
        sys.stdout.write(notes + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
