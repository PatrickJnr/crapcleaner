"""Application entry point - dispatches between CLI and GUI."""

import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    from crapcleaner.utils.logs import configure_logging

    args: list[str] = list(sys.argv[1:] if argv is None else argv)
    # One log for both front ends. `--verbose` raises it from WARNING to DEBUG.
    configure_logging(verbose="--verbose" in args)
    if args and args[0] in ("--gui", "-g"):
        from crapcleaner.gui.app import run_gui

        return run_gui()
    from crapcleaner.cli import main as cli_main

    return cli_main(args)
