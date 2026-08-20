"""Generate a catalogue page from the cleanup categories' own metadata.

Every category already carries what_it_contains, why_it_grows, why_safe_to_delete and
regeneration_behavior. Generating the page from those fields means it cannot drift from
what the application actually does.

    python scripts/generate_category_catalogue.py --output docs/categories.md
"""

import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crapcleaner.models.category import SAFETY_DESCRIPTIONS, CleanupCategory  # noqa: E402
from crapcleaner.registry import get_all_categories  # noqa: E402

FIELDS = (
    ("What it contains", "what_it_contains"),
    ("Why it grows", "why_it_grows"),
    ("Why it is safe to delete", "why_safe_to_delete"),
    ("What happens afterwards", "regeneration_behavior"),
)


def _platform_label() -> str:
    return "Windows" if os.name == "nt" else "Linux"


def render(categories: list[CleanupCategory]) -> str:
    by_group: dict[str, list[CleanupCategory]] = defaultdict(list)
    for category in categories:
        by_group[category.group].append(category)

    lines = [
        "# Cleanup catalogue",
        "",
        f"Generated from the {len(categories)} categories registered on {_platform_label()}. "
        "Every entry below is the application's own description of the target, not a summary "
        "written separately.",
        "",
    ]

    for group in sorted(by_group):
        lines += [f"## {group}", ""]
        for category in sorted(by_group[group], key=lambda c: c.name):
            safety = SAFETY_DESCRIPTIONS.get(category.safety_level, "")
            lines += [
                f"### {category.name}",
                "",
                f"`{category.id}` · **{category.safety_level.value}** — {safety}",
                "",
            ]
            if category.requires_admin:
                lines += ["Requires administrator rights.", ""]
            for heading, attribute in FIELDS:
                text = (getattr(category, attribute, "") or "").strip()
                if text:
                    lines += [f"**{heading}.** {text}", ""]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", help="write here instead of standard output")
    args = parser.parse_args(argv)

    page = render(get_all_categories())
    if not args.output:
        sys.stdout.write(page)
        return 0

    directory = os.path.dirname(os.path.abspath(args.output))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(page)
    print(f"{args.output}: {page.count('### ')} categories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
