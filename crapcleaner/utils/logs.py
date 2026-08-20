"""Application logging: one rotating file, off by default at anything but WARNING.

The application had no log at all. `LOG_FILE` was declared in constants and never
written, three modules imported `logging` with no handler configured, and 36 broad
exception handlers ended in a bare `pass` - so when something went wrong on a user's
machine there was nothing to ask them for.

What is logged is deliberately narrow: what the application was doing and what went
wrong. Filesystem paths appear where they are the subject of the failure, since the
whole product is about directories; file contents, credentials and command output
never do.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from crapcleaner.constants import LOG_FILE

_configured = False
_MAX_BYTES = 512 * 1024
_BACKUPS = 2


def log_path() -> str:
    """Where the log is written."""
    from crapcleaner.config import config_dir

    return os.path.join(config_dir(), LOG_FILE)


def configure_logging(verbose: bool = False) -> None:
    """Attach the rotating file handler once per process.

    Never raises: a machine where the config directory cannot be written must still
    run the application, just without a log.
    """
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger("crapcleaner")
    root.setLevel(logging.DEBUG if verbose else logging.WARNING)
    root.propagate = False

    try:
        path = log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        handler: logging.Handler = RotatingFileHandler(
            path, maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
        )
    except OSError:
        return

    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """A child logger under the application's namespace."""
    return logging.getLogger(f"crapcleaner.{name}")
