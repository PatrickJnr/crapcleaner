"""Scheduled scanning and threshold-based notification engine.

Runs non-destructive scans at user-configured intervals and generates local
reports or notifications if reclaimable space exceeds a chosen threshold.
Never performs destructive cleanup automatically.
"""

from dataclasses import dataclass
from datetime import datetime

from crapcleaner.models.report import ScanReport
from crapcleaner.registry import get_all_categories
from crapcleaner.scanner.scanner import ScanEngine


@dataclass
class ScheduledScanConfig:
    enabled: bool = False
    interval_hours: int = 24
    threshold_mb: int = 5120  # 5 GB default
    last_run: datetime | None = None
    last_reclaimable_bytes: int = 0
    notify_on_threshold: bool = True

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "interval_hours": self.interval_hours,
            "threshold_mb": self.threshold_mb,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_reclaimable_bytes": self.last_reclaimable_bytes,
            "notify_on_threshold": self.notify_on_threshold,
        }


def run_scheduled_scan(config: ScheduledScanConfig) -> tuple[ScanReport, bool]:
    """Execute a scheduled scan and determine if the threshold is exceeded. Returns (report, threshold_exceeded)."""
    categories = get_all_categories()
    engine = ScanEngine(categories)
    report = engine.run(max_files=100000)

    config.last_run = datetime.now()
    config.last_reclaimable_bytes = report.total_size

    threshold_bytes = config.threshold_mb * 1024 * 1024
    threshold_exceeded = report.total_size >= threshold_bytes

    return report, threshold_exceeded
