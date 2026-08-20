"""GUI package."""

# `main` lives in crapcleaner.app - the console script's entry point - so there is
# one dispatcher rather than two that disagreed about which flags launch the GUI.
from crapcleaner.app import main
from crapcleaner.gui.app import run_gui

__all__ = ["main", "run_gui"]
