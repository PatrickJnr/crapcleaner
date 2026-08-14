"""Cleaners package."""

from crapcleaner.cleaners.actions import (
    ACTION_REGISTRY,
    available_actions,
    describe_action,
    run_action,
)
from crapcleaner.cleaners.cleaner import clean_categories

__all__ = [
    "clean_categories",
    "run_action",
    "describe_action",
    "available_actions",
    "ACTION_REGISTRY",
]
