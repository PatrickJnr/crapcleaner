"""Docker / WSL disk usage reporting and safe prune operations.

WSL virtual disks (ext4.vhdx) are NEVER manually deleted. Only supported
`docker` prune commands are offered, and only with explicit confirmation.
"""

import os
import re
from dataclasses import dataclass, field

from crapcleaner.models.category import CleanupCategory, SafetyLevel
from crapcleaner.utils.files import walk_safe
from crapcleaner.utils.platform import run_command, which


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
            what_it_contains="Disk the Docker daemon holds: stopped containers with their writable layers, images no container is using, unused networks, and the build cache.",
            why_it_grows="Every build produces new image layers and every stopped container keeps its own layer; Docker never reclaims either on its own.",
            why_safe_to_delete="Volumes are not pruned, so database and named-volume data survives, and running containers and the images behind them are kept. Because this runs with -a, every image no container currently uses is removed - including images you built locally and never pushed, which can only come back by being rebuilt or re-pulled from a registry.",
            regeneration_behavior="The next 'docker run' pulls its image again and the next build starts from an empty cache, so the first one after a prune is slow.",
            action="docker_system_prune",
        ),
        CleanupCategory(
            id="docker_builder_prune",
            name="Docker build cache",
            group="Docker",
            description="Runs 'docker builder prune -af' - clears the Docker build cache. Requires confirmation.",
            safety_level=SafetyLevel.REVIEW,
            what_it_contains="The BuildKit cache the daemon keeps so an unchanged Dockerfile step can be reused instead of run again.",
            why_it_grows="Every build writes new cache entries, and entries from old builds stay until they are pruned.",
            why_safe_to_delete="Images, containers, and volumes are all kept - only cached build steps are reclaimed. The cost is real: with -a nothing is left to reuse, so your next 'docker build' runs every layer from scratch and re-downloads base images over the network.",
            regeneration_behavior="The cache refills as you build again; the first build after the prune is the slow one.",
            action="docker_builder_prune",
        ),
        CleanupCategory(
            id="docker_buildx_prune",
            name="Docker Buildx cache",
            group="Docker",
            description="Runs 'docker buildx prune -af' - clears cached BuildKit layers for every buildx builder. Images and volumes are untouched. Requires confirmation.",
            safety_level=SafetyLevel.REVIEW,
            what_it_contains="Cached BuildKit layers held by the buildx builders, including the separate cache each containerised or multi-platform builder keeps.",
            why_it_grows="Builders cache per platform, so a multi-arch project stores several copies of the same work and keeps them across builds.",
            why_safe_to_delete="Images, volumes, and the builder instances themselves are kept; only their cached layers are reclaimed. Every builder is emptied at once, so the next build for each platform runs from scratch and re-fetches base images over the network.",
            regeneration_behavior="Builders rebuild their caches on the next build, one platform at a time.",
            action="docker_buildx_prune",
        ),
    ]
