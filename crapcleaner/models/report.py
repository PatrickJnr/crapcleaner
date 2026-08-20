"""Scan and cleanup report models."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ScanCategoryResult:
    category_id: str
    name: str
    size: int
    item_count: int
    skipped: int
    safety_level: str
    group: str
    description: str
    reclaimable: bool
    errors: list[str] = field(default_factory=list)
    #: True when the scan stopped at the file budget, so `size` is a floor rather
    #: than a total and the cleanup may remove more than the scan promised.
    truncated: bool = False


@dataclass
class ScanReport:
    started: datetime
    duration: float = 0.0
    results: list[ScanCategoryResult] = field(default_factory=list)
    cancelled: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        return sum(r.size for r in self.results if r.reclaimable)

    @property
    def total_files(self) -> int:
        return sum(r.item_count for r in self.results)

    def result_by_id(self, category_id: str):
        for r in self.results:
            if r.category_id == category_id:
                return r
        return None

    def to_dict(self) -> dict:
        return {
            "started": self.started.isoformat(timespec="seconds"),
            "duration": round(self.duration, 3),
            "total_size": self.total_size,
            "total_files": self.total_files,
            "cancelled": self.cancelled,
            "categories": [r.__dict__ for r in self.results],
        }


@dataclass
class CleanupResult:
    category_id: str
    category_name: str
    files_deleted: int
    space_recovered: int
    skipped: int
    errors: list[str] = field(default_factory=list)
    permission_errors: list[str] = field(default_factory=list)
    skip_reasons: list[str] = field(default_factory=list)
    dry_run: bool = False


@dataclass(frozen=True)
class RemovedPath:
    """One entry in a cleanup manifest. A recycled tree is a single entry."""

    path: str
    size: int
    recycled: bool
    file_count: int = 1


@dataclass
class CleanupReport:
    started: datetime
    duration: float = 0.0
    dry_run: bool = False
    use_recycle_bin: bool = False
    results: list[CleanupResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    manifest_path: str = ""
    #: Deliberately absent from `to_dict`, which feeds exports and `--json`: these are
    #: the user's own file paths and belong only in the manifest.
    removed: list[RemovedPath] = field(default_factory=list, repr=False)

    @property
    def total_files_deleted(self) -> int:
        return sum(r.files_deleted for r in self.results)

    @property
    def total_space_recovered(self) -> int:
        return sum(r.space_recovered for r in self.results)

    @property
    def total_skipped(self) -> int:
        return sum(r.skipped for r in self.results)

    @property
    def permission_errors(self) -> list[str]:
        return [msg for r in self.results for msg in r.permission_errors]

    @property
    def skip_reasons(self) -> list[str]:
        return [msg for r in self.results for msg in r.skip_reasons]

    def to_dict(self) -> dict:
        return {
            "started": self.started.isoformat(timespec="seconds"),
            "duration": round(self.duration, 3),
            "dry_run": self.dry_run,
            "use_recycle_bin": self.use_recycle_bin,
            "total_files_deleted": self.total_files_deleted,
            "total_space_recovered": self.total_space_recovered,
            "total_skipped": self.total_skipped,
            "permission_errors": self.permission_errors,
            "categories": [r.__dict__ for r in self.results],
        }
