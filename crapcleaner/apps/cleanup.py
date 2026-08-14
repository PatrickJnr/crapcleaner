"""Desktop application cache categories (Discord, Slack, Spotify, WinGet, Scoop, Chocolatey)."""

import os

from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.utils.platform import (
    get_appdata,
    get_local_appdata,
    get_program_data,
    get_user_profile,
)


def get_categories() -> list[CleanupCategory]:
    appdata = get_appdata()
    local = get_local_appdata()
    user = get_user_profile()
    program_data = get_program_data()

    categories: list[CleanupCategory] = []

    # Discord Cache
    discord_targets = []
    discord_root = os.path.join(appdata, "discord")
    for sub in ("Cache", "GPUCache", "Code Cache"):
        discord_targets.append(CacheTarget(path=os.path.join(discord_root, sub)))
    categories.append(
        CleanupCategory(
            id="discord_cache",
            name="Discord cache",
            group="Applications",
            description="Cached media, avatars, and electron runtime data for Discord. Re-downloaded as needed.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=discord_targets,
        )
    )

    # Slack Cache
    slack_targets = []
    slack_root = os.path.join(appdata, "Slack")
    for sub in ("Cache", "GPUCache", "Service Worker"):
        slack_targets.append(CacheTarget(path=os.path.join(slack_root, sub)))
    categories.append(
        CleanupCategory(
            id="slack_cache",
            name="Slack cache",
            group="Applications",
            description="Cached web resources and logs for Slack desktop.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=slack_targets,
        )
    )

    # Spotify Cache
    spotify_targets = [
        CacheTarget(path=os.path.join(local, "Spotify", "Data")),
        CacheTarget(path=os.path.join(local, "Spotify", "Storage")),
    ]
    categories.append(
        CleanupCategory(
            id="spotify_cache",
            name="Spotify cache",
            group="Applications",
            description="Locally cached songs and album artwork. Does not delete playlists, offline downloads, or user settings.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=spotify_targets,
        )
    )

    # WinGet package manager cache
    winget_targets = [
        CacheTarget(path=os.path.join(local, "Microsoft", "WinGet", "Packages")),
        CacheTarget(
            path=os.path.join(
                local,
                "Packages",
                "Microsoft.DesktopAppInstaller_8wekyb3d8bbwe",
                "LocalCache",
            )
        ),
    ]
    categories.append(
        CleanupCategory(
            id="winget_cache",
            name="WinGet package cache",
            group="Package managers",
            description="Downloaded installer payloads cached by Windows Package Manager (winget). Safe to remove.",
            safety_level=SafetyLevel.SAFE,
            targets=winget_targets,
        )
    )

    # Chocolatey cache
    choco_targets = [
        CacheTarget(path=os.path.join(program_data, "chocolatey", "cache")),
        CacheTarget(path=os.path.join(program_data, "chocolatey", "lib-bad")),
    ]
    categories.append(
        CleanupCategory(
            id="chocolatey_cache",
            name="Chocolatey cache",
            group="Package managers",
            description="Downloaded package installer cache for Chocolatey.",
            safety_level=SafetyLevel.SAFE,
            targets=choco_targets,
        )
    )

    # Scoop cache
    scoop_targets = [
        CacheTarget(path=os.path.join(user, "scoop", "cache")),
    ]
    categories.append(
        CleanupCategory(
            id="scoop_cache",
            name="Scoop cache",
            group="Package managers",
            description="Downloaded installer archives for Scoop package manager.",
            safety_level=SafetyLevel.SAFE,
            targets=scoop_targets,
        )
    )

    return categories
