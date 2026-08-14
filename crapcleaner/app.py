"""Application entry point - dispatches between CLI and GUI."""

import sys


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("--gui", "-g"):
        from crapcleaner.gui.app import run_gui

        return run_gui()
    from crapcleaner.cli import main as cli_main

    return cli_main(argv)
