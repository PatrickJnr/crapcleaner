"""Application entry point - dispatches between CLI and GUI."""

import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    args: list[str] = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("--gui", "-g"):
        from crapcleaner.gui.app import run_gui

        return run_gui()
    from crapcleaner.cli import main as cli_main

    return cli_main(args)
