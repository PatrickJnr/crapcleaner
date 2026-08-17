"""PyInstaller entry point for the frozen CrapCleaner executable.

The compiled exe always opens the GUI, regardless of how it is launched,
so double-clicking the file behaves like a normal desktop app.
"""

import sys
from pathlib import Path

# Ensure repository root is on sys.path when running from source or build hooks
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from crapcleaner.gui.app import run_gui  # noqa: E402

if __name__ == "__main__":
    sys.exit(run_gui())
