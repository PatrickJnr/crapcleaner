#!/usr/bin/env python3
"""Extract the release notes section and title for a given version tag from CHANGELOG.md."""

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


def extract_release_title(
    version: str | None = None,
    changelog_path: Path | str = "CHANGELOG.md",
) -> str:
    """Extract a formatted release title (e.g., 'v1.0.10: Custom Theme Studio release...').

    Args:
        version: Version tag (e.g., 'v1.0.10', '1.0.10').
        changelog_path: Path to CHANGELOG.md.

    Returns:
        Formatted full title string.
    """
    path = Path(changelog_path)
    clean_ver = version.replace("refs/tags/", "").lstrip("v").strip() if version else ""

    if not clean_ver and path.is_file():
        m = re.search(r"##\s*\[([^\]]+)\]", path.read_text(encoding="utf-8"))
        if m:
            clean_ver = m.group(1).strip()

    tag_label = f"v{clean_ver}" if clean_ver else (version or "Release")
    notes = extract_changelog(version, changelog_path)
    if not notes:
        return tag_label

    # Find the summary sentence preceding the first markdown sub-heading
    first_block = notes.split("###")[0].strip()
    first_line = ""
    for line in first_block.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("---"):
            first_line = line
            break

    if not first_line:
        return tag_label

    title_summary = first_line.rstrip(".")
    return f"{tag_label}: {title_summary}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract release notes and title for a version from CHANGELOG.md."
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
    parser.add_argument(
        "--title-output",
        "-t",
        default=None,
        help="Optional file path to write formatted release title into.",
    )
    parser.add_argument(
        "--print-title",
        action="store_true",
        help="Print the formatted release title instead of the release notes.",
    )

    args = parser.parse_args()
    notes = extract_changelog(args.version, args.changelog)
    title = extract_release_title(args.version, args.changelog)

    if not notes:
        sys.stderr.write(f"Warning: No changelog section found for version '{args.version}'\n")

    if args.title_output:
        Path(args.title_output).write_text(title, encoding="utf-8")

    if args.output:
        Path(args.output).write_text(notes, encoding="utf-8")

    if args.print_title:
        sys.stdout.write(title + "\n")
    elif not args.output:
        sys.stdout.write(notes + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
