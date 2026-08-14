"""History entry model (scan and cleanup records)."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class HistoryEntry:
    kind: str
    started: datetime
    duration: float = 0.0
    dry_run: bool = False
    use_recycle_bin: bool = False
    categories: list[str] = field(default_factory=list)
    files_removed: int = 0
    space_recovered: int = 0
    skipped: int = 0
    errors: int = 0
    total_identified: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["started"] = self.started.isoformat(timespec="seconds")
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        data = dict(data)
        started = data.pop("started", None)
        if isinstance(started, str):
            try:
                data["started"] = datetime.fromisoformat(started)
            except ValueError:
                data["started"] = datetime.now()
        return cls(**data)

    @classmethod
    def from_report(cls, report: Any) -> "HistoryEntry":
        return cls(
            kind="cleanup",
            started=report.started,
            duration=report.duration,
            dry_run=report.dry_run,
            use_recycle_bin=getattr(report, "use_recycle_bin", False),
            categories=[r.category_name for r in report.results],
            files_removed=report.total_files_deleted,
            space_recovered=report.total_space_recovered,
            skipped=report.total_skipped,
            errors=len(report.errors),
        )
