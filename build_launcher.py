"""PyInstaller entry point for the frozen CrapCleaner executable.

The compiled exe always opens the GUI, regardless of how it is launched,
so double-clicking the file behaves like a normal desktop app.
"""

import sys

from crapcleaner.gui.app import run_gui

if __name__ == "__main__":
    sys.exit(run_gui())
