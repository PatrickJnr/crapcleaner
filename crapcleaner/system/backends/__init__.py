"""Platform-specific implementations of the system-management capabilities.

Each module in this package targets exactly one operating system and is imported
only by its dispatcher in :mod:`crapcleaner.system`. Nothing here should be imported
directly by the GUI or the CLI - they talk to the platform-neutral dispatchers, which
consult :mod:`crapcleaner.system.capabilities` and route to the right backend.

Adding an operating system means adding modules here plus one entry per capability in
the registry; no caller changes.
"""
