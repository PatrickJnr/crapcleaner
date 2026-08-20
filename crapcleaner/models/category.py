"""Safety classification and cleanup category definitions."""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum


class SafetyLevel(str, Enum):
    SAFE = "SAFE"
    LOW_RISK = "LOW_RISK"
    REVIEW = "REVIEW"
    DANGEROUS = "DANGEROUS"

    @property
    def auto_selected(self) -> bool:
        return self in (SafetyLevel.SAFE, SafetyLevel.LOW_RISK)

    @property
    def label(self) -> str:
        return {
            SafetyLevel.SAFE: "Safe",
            SafetyLevel.LOW_RISK: "Low risk",
            SafetyLevel.REVIEW: "Review",
            SafetyLevel.DANGEROUS: "Dangerous",
        }[self]


SAFETY_DESCRIPTIONS = {
    SafetyLevel.SAFE: "Safe to remove and automatically selected.",
    SafetyLevel.LOW_RISK: "Normally safe but may cause rebuilding or temporary performance impact.",
    SafetyLevel.REVIEW: "Requires explicit user selection.",
    SafetyLevel.DANGEROUS: "Never automatically deleted.",
}


@dataclass
class CacheTarget:
    path: str
    patterns: tuple[str, ...] = ()
    recurse: bool = True
    only_files: bool = False

    @property
    def exists(self) -> bool:
        from os import path

        return path.exists(self.path) or path.islink(self.path)


@dataclass
class CleanupCategory:
    id: str
    name: str
    description: str
    safety_level: SafetyLevel
    group: str = "Other"
    targets: list[CacheTarget] = field(default_factory=list)
    action: str | None = None
    finder: Callable[..., list[str]] | None = None
    finder_args: tuple = field(default_factory=tuple)
    requires_admin: bool = False
    auto_selected: bool | None = None

    size: int = 0
    item_count: int = 0
    reclaimable: bool = True
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    application: str | None = None

    what_it_contains: str = ""
    why_it_grows: str = ""
    why_safe_to_delete: str = ""
    regeneration_behavior: str = ""
    reversible: bool = True

    @property
    def selected_by_default(self) -> bool:
        if self.auto_selected is not None:
            return self.auto_selected
        return self.safety_level.auto_selected

    @property
    def has_targets(self) -> bool:
        return bool(self.action) or bool(self.targets) or bool(self.finder)
