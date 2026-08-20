"""Reload themes when their files change, so editing one does not mean restarting.

An editor's "save" is usually a write to a temporary file followed by a rename,
which arrives as several events and, briefly, as the file having disappeared. So
every event goes through a short timer, and the directory is watched as well as
the files to catch the rename.
"""

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal

from crapcleaner.gui.theme.palettes import BUNDLED_THEME_DIR, reload_themes, user_theme_dir
from crapcleaner.utils.logs import get_logger

logger = get_logger("theme_watcher")

#: Long enough to coalesce an editor's write-then-rename, short enough to feel live.
_SETTLE_MS = 300


class ThemeWatcher(QObject):
    """Watches the user theme directory and reloads when something changes."""

    #: Emitted after the registry has been reloaded.
    themes_changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._watcher = QFileSystemWatcher(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(_SETTLE_MS)
        self._timer.timeout.connect(self._reload)

        self._watcher.directoryChanged.connect(self._schedule)
        self._watcher.fileChanged.connect(self._schedule)
        self.rewatch()

    def directories(self) -> list[str]:
        """Every directory themes are read from.

        The bundled one is watched too: a theme being tried out often lands there.
        """
        found = [BUNDLED_THEME_DIR]
        try:
            found.append(user_theme_dir())
        except Exception:  # pragma: no cover - config resolution must not break the GUI
            pass
        return [d for d in found if d]

    def directory(self) -> str:
        """The user's theme directory, which is the one that is created on demand."""
        try:
            return user_theme_dir()
        except Exception:  # pragma: no cover - config resolution must not break the GUI
            return ""

    def rewatch(self) -> None:
        """Watch the directory and everything currently in it.

        Called again after each reload: a file replaced by a rename is a different
        inode, so the old watch no longer refers to anything.
        """
        import os

        user_directory = self.directory()
        if user_directory:
            try:
                os.makedirs(user_directory, exist_ok=True)
            except OSError:
                logger.debug("Could not create the user theme directory", exc_info=True)

        existing = set(self._watcher.directories()) | set(self._watcher.files())
        wanted: set[str] = set()
        for directory in self.directories():
            if not os.path.isdir(directory):
                continue
            wanted.add(directory)
            try:
                wanted |= {
                    os.path.join(directory, name)
                    for name in os.listdir(directory)
                    if name.endswith(".json")
                }
            except OSError:
                continue
        if not wanted:
            return

        stale = existing - wanted
        if stale:
            self._watcher.removePaths(sorted(stale))
        fresh = wanted - existing
        if fresh:
            self._watcher.addPaths(sorted(fresh))

    def _schedule(self, _path: str = "") -> None:
        self._timer.start()

    def _reload(self) -> None:
        try:
            reload_themes()
        except Exception:  # pragma: no cover - a bad file must not take the window down
            logger.warning("Reloading themes failed", exc_info=True)
            return
        self.rewatch()
        logger.info("Themes reloaded from disk")
        self.themes_changed.emit()

    def stop(self) -> None:
        self._timer.stop()
        paths = list(self._watcher.directories()) + list(self._watcher.files())
        if paths:
            self._watcher.removePaths(paths)
