"""Allow running as `python -m crapcleaner`."""

from crapcleaner.app import main

if __name__ == "__main__":
    raise SystemExit(main())
