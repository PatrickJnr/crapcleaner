"""Docker / WSL disk usage reporting and safe prune operations.

WSL virtual disks (ext4.vhdx) are NEVER manually deleted. Only supported
`docker` prune commands are offered, and only with explicit confirmation.
"""

import os
import re
from dataclasses import dataclass, field

from crapcleaner.models.category import CleanupCategory, SafetyLevel
from crapcleaner.utils.platform import run_command, which
from crapcleaner.utils.files import walk_safe


@dataclass
class DockerInfo:
    available: bool
    version: str = ""
    df_raw: str = ""
    parsed: list[dict[str, str]] = field(default_factory=list)
    total_reclaimable: int = 0

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "version": self.version,
            "df": self.df_raw,
            "total_reclaimable": self.total_reclaimable,
            "summary": self.parsed,
        }


def is_docker_available() -> bool:
    return which("docker") is not None


def get_docker_version() -> str:
    result = run_command(["docker", "version", "--format", "{{.Client.Version}}"], timeout=15.0)
    if result["returncode"] == 0:
        return str(result.get("stdout", "")).strip()
    return ""


def docker_system_df() -> DockerInfo:
    info = DockerInfo(available=False)
    if not is_docker_available():
        return info
    info.available = True
    info.version = get_docker_version()
    result = run_command(["docker", "system", "df"], timeout=60.0)
    info.df_raw = (str(result.get("stdout", "")) + str(result.get("stderr", ""))).strip()
    info.parsed = _parse_docker_df(info.df_raw)
    info.total_reclaimable = _sum_reclaimable(info.parsed)
    return info


def _parse_docker_df(raw: str) -> list[dict[str, str]]:
    rows = []
    for line in raw.splitlines():
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) >= 4 and "TYPE" not in line.upper():
            rows.append(
                {
                    "type": parts[0],
                    "total": parts[1],
                    "active": parts[2],
                    "size": parts[3],
                    "reclaimable": parts[4] if len(parts) > 4 else "",
                }
            )
    return rows


def _sum_reclaimable(rows: list[dict[str, str]]) -> int:
    total = 0
    for row in rows:
        raw = row.get("reclaimable", "")
        match = re.search(r"([\d.]+)([KMGT]?i?B)", raw, re.IGNORECASE)
        if not match:
            continue
        value = float(match.group(1))
        unit = match.group(2).upper().replace("I", "")
        total += int(
            value
            * {
                "B": 1,
                "KB": 1024,
                "MB": 1024**2,
                "GB": 1024**3,
                "TB": 1024**4,
            }.get(unit, 1024)
        )
    return total


def wsl_disk_report() -> list[dict[str, object]]:
    vhdx: list[dict[str, object]] = []
    user = os.environ.get("USERPROFILE", "")
    for base in (
        os.path.join(user, "AppData", "Local", "Docker", "wsl"),
        os.path.join(user, "AppData", "Local", "Packages"),
    ):
        if not os.path.isdir(base):
            continue
        for root, _dirs, files in walk_safe(base):
            for name in files:
                if name.lower().endswith(".vhdx"):
                    full = os.path.join(root, name)
                    try:
                        size = os.path.getsize(full)
                    except OSError:
                        size = 0
                    vhdx.append({"path": full, "size": size, "managed_by": "Docker Desktop/WSL"})
    return vhdx


def get_categories() -> list[CleanupCategory]:
    return [
        CleanupCategory(
            id="docker_system_prune",
            name="Docker prune (containers, images, networks)",
            group="Docker",
            description="Runs 'docker system prune -af' - removes stopped containers, unused images, and networks. Volumes are NOT touched. Requires confirmation.",
            safety_level=SafetyLevel.REVIEW,
            action="docker_system_prune",
        ),
        CleanupCategory(
            id="docker_builder_prune",
            name="Docker build cache",
            group="Docker",
            description="Runs 'docker builder prune -af' - clears the Docker build cache. Requires confirmation.",
            safety_level=SafetyLevel.REVIEW,
            action="docker_builder_prune",
        ),
    ]
