"""Sub-command surface for the command line.

Commands are declared here as data and translated into the legacy flags the
dispatcher already understands, so both spellings keep working:

    crapcleaner scan --json
    crapcleaner --scan --json          # still fine

`crapcleaner <command> --help` then describes one command rather than all of them.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Command:
    """One sub-command, and the legacy flag it is a name for."""

    name: str
    flag: str
    help: str
    #: Positional argument appended to `flag`, if the command takes one.
    argument: str | None = None
    #: `argparse` nargs for that positional.
    nargs: str | int | None = None
    #: Shared option groups this command accepts.
    options: tuple[str, ...] = ()
    aliases: tuple[str, ...] = field(default_factory=tuple)


#: Option groups, so "every command that writes a report" is stated once.
_OPTION_GROUPS: dict[str, tuple[tuple[tuple[str, ...], dict], ...]] = {
    "json": ((("--json",), {"action": "store_true", "help": "Machine-readable JSON output."}),),
    "export": (
        (("--export",), {"metavar": "FORMAT", "help": "Write a report as json, csv, or txt."}),
        (("--output",), {"metavar": "FILE", "help": "Where to write the report."}),
    ),
    "execute": (
        (
            ("--execute",),
            {"action": "store_true", "help": "Actually perform it. Without this it is a dry run."},
        ),
        (("--yes",), {"action": "store_true", "help": "Skip the confirmation prompt."}),
    ),
    "progress": (
        (
            ("--progress-jsonl",),
            {"action": "store_true", "help": "Stream progress as one JSON object per line."},
        ),
    ),
    "root": ((("--root",), {"metavar": "PATH", "help": "Directory to scan."}),),
    "output": ((("--output",), {"metavar": "FILE", "help": "Where to write it."}),),
    "manifest": (
        (
            ("--manifest",),
            {"metavar": "RUN", "help": "List what one run removed (position or timestamp)."},
        ),
    ),
    "schedule": (
        (("--at",), {"metavar": "HH:MM", "help": "Time of day to run."}),
        (("--frequency",), {"choices": ("daily", "weekly"), "help": "How often to run."}),
        (
            ("--threshold-mb",),
            {"type": int, "metavar": "MB", "help": "Notify above this much reclaimable."},
        ),
    ),
    "storage": (
        (
            ("--compare",),
            {"action": "store_true", "help": "Report what changed since the last scan."},
        ),
        (
            ("--allocated",),
            {"action": "store_true", "help": "Measure what files occupy on disk."},
        ),
    ),
    "min-dup-size": (
        (("--min-dup-size",), {"metavar": "SIZE", "help": "Smallest file to consider."}),
    ),
}

COMMANDS: tuple[Command, ...] = (
    Command("gui", "--gui", "Open the graphical interface."),
    Command(
        "scan",
        "--scan",
        "Scan for reclaimable space.",
        options=("json", "export", "progress"),
    ),
    Command(
        "clean",
        "--clean-safe",
        "Clean categories. With no name, everything safe by default.",
        argument="categories",
        nargs="*",
        options=("json", "execute", "progress"),
    ),
    Command(
        "preview",
        "--cleanup-preview",
        "List every file a cleanup would remove, without removing anything.",
        options=("json",),
    ),
    Command("categories", "--list-categories", "List every cleanup category.", options=("json",)),
    Command(
        "storage",
        "--storage",
        "Hierarchical storage breakdown for a path.",
        argument="path",
        nargs="?",
        options=("json", "export", "storage"),
    ),
    Command(
        "file-types",
        "--file-types",
        "Storage grouped by file type.",
        argument="path",
        nargs="?",
        options=("json", "export"),
    ),
    Command(
        "large-files",
        "--large-files",
        'Find files larger than SIZE (for example "1GB").',
        argument="size",
        options=("json", "root", "export"),
    ),
    Command(
        "duplicates",
        "--duplicates",
        "Find duplicate files across one or more folders.",
        argument="folders",
        nargs="+",
        options=("json", "min-dup-size"),
    ),
    Command(
        "installers",
        "--installers",
        "Find installers left in Downloads and on the Desktop.",
        options=("json", "root"),
    ),
    Command(
        "crash-dumps",
        "--crash-dumps",
        "List crash dumps and kernel memory dumps, grouped by application.",
        options=("json", "export"),
    ),
    Command("recycle-bin", "--recycle-bin", "Inspect the Recycle Bin or Trash.", options=("json",)),
    Command("disk-health", "--disk-health", "Storage device health and TRIM.", options=("json",)),
    Command("specs", "--specs", "Hardware and operating system specifications.", options=("json",)),
    Command(
        "memory",
        "--memory",
        "Memory report: RAM, swap, and graphics memory.",
        options=("json",),
    ),
    Command("startup", "--startup", "Applications configured to run at login.", options=("json",)),
    Command("services", "--services", "System services or systemd units.", options=("json",)),
    Command(
        "updates",
        "--system-updates",
        "Pending operating-system updates.",
        options=("json",),
        aliases=("system-updates",),
    ),
    Command(
        "capabilities", "--capabilities", "What this operating system supports.", options=("json",)
    ),
    Command("protected-paths", "--protected-paths", "The active safety rules.", options=("json",)),
    Command(
        "history",
        "--history",
        "Recent scan and cleanup history.",
        options=("json", "export", "manifest"),
    ),
    Command(
        "diagnostics",
        "--diagnostics",
        "Write a diagnostics bundle for a bug report.",
        options=("json", "output"),
    ),
    Command(
        "schedule",
        "--schedule",
        "Inspect or change the scheduled scan. Scheduled runs never delete anything.",
        argument="action",
        nargs="?",
        options=("json", "schedule"),
    ),
    Command(
        "update",
        "--update",
        "Check for a new release, or download, verify, and install it.",
        argument="action",
        nargs="?",
        options=("json", "execute"),
    ),
    Command(
        "scheduled-scan",
        "--scheduled-scan",
        "Run the unattended scan. This is what the scheduler invokes.",
        options=("json",),
    ),
)

_BY_NAME: dict[str, Command] = {}
for _command in COMMANDS:
    _BY_NAME[_command.name] = _command
    for _alias in _command.aliases:
        _BY_NAME[_alias] = _command


def is_command(token: str) -> bool:
    """Whether `token` names a sub-command."""
    return token in _BY_NAME


def build_command_parser() -> argparse.ArgumentParser:
    """A parser whose help lists the commands rather than every legacy flag."""
    from crapcleaner import __version__

    parser = argparse.ArgumentParser(
        prog="crapcleaner",
        description="CrapCleaner - disk cleanup, storage analysis, and system tools.",
        epilog="Run 'crapcleaner <command> --help' for one command's options.",
    )
    parser.add_argument("--version", action="version", version=f"CrapCleaner {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    for command in COMMANDS:
        sub = subparsers.add_parser(command.name, help=command.help, aliases=list(command.aliases))
        if command.argument:
            sub.add_argument(command.argument, nargs=command.nargs)
        for group in command.options:
            for flags, options in _OPTION_GROUPS[group]:
                sub.add_argument(*flags, **options)
        sub.add_argument("--verbose", action="store_true", help="Write debug detail to the log.")
        sub.add_argument("--quiet", action="store_true", help="Suppress non-essential output.")
    return parser


def to_legacy_argv(argv: list[str]) -> list[str]:
    """Translate `<command> [args]` into the flags the dispatcher understands.

    Exits through argparse for an unknown command or a bad argument, so the user
    gets the usual message rather than a traceback.
    """
    parser = build_command_parser()
    args = parser.parse_args(argv)
    name = getattr(args, "command", None)
    if not name:
        parser.print_help()
        raise SystemExit(0)

    command = _BY_NAME[name]
    translated: list[str] = []
    values = vars(args)

    if command.argument:
        value = values.get(command.argument)
        if isinstance(value, list):
            if command.name == "clean":
                # "clean" with no names means everything safe by default.
                for entry in value:
                    translated += ["--clean-category", entry]
                if not value:
                    translated.append(command.flag)
            else:
                translated.append(command.flag)
                translated += [str(v) for v in value]
        elif value is None:
            translated.append(command.flag)
        else:
            translated += [command.flag, str(value)]
    else:
        translated.append(command.flag)

    for group in command.options:
        for flags, options in _OPTION_GROUPS[group]:
            dest = flags[0].lstrip("-").replace("-", "_")
            value = values.get(dest)
            if not value:
                continue
            if options.get("action") == "store_true":
                translated.append(flags[0])
            else:
                translated += [flags[0], str(value)]

    for flag in ("verbose", "quiet"):
        if values.get(flag):
            translated.append(f"--{flag}")
    return translated
