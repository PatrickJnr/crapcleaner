"""Docker package."""

from crapcleaner.docker.cleanup import (
    DockerInfo,
    docker_system_df,
    get_categories,
    is_docker_available,
    wsl_disk_report,
)

__all__ = [
    "get_categories",
    "docker_system_df",
    "wsl_disk_report",
    "is_docker_available",
    "DockerInfo",
]
