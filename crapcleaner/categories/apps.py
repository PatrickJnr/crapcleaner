"""Desktop application cache categories for Windows and Linux."""

import os

from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.utils.platform import (
    get_appdata,
    get_local_appdata,
    get_program_data,
    get_user_profile,
    is_linux,
    is_windows,
)


def _targets(paths: list[str], existing_only: bool = True) -> list[CacheTarget]:
    if existing_only:
        return [CacheTarget(path=path) for path in paths if os.path.isdir(path)]
    return [CacheTarget(path=path) for path in paths]


def _electron_subtargets(
    root: str, subs: tuple[str, ...], existing_only: bool = True
) -> list[CacheTarget]:
    return _targets([os.path.join(root, sub) for sub in subs], existing_only=existing_only)


def _get_windows_categories(
    appdata: str, local: str, user: str, program_data: str
) -> list[CleanupCategory]:
    _ = is_windows
    categories: list[CleanupCategory] = []

    discord_root = os.path.join(appdata, "discord")
    categories.append(
        CleanupCategory(
            id="discord_cache",
            name="Discord cache",
            group="Applications",
            description="Cached media, avatars, and electron runtime data for Discord. Re-downloaded as needed.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=_electron_subtargets(
                discord_root, ("Cache", "GPUCache", "Code Cache"), existing_only=False
            ),
        )
    )

    slack_root = os.path.join(appdata, "Slack")
    categories.append(
        CleanupCategory(
            id="slack_cache",
            name="Slack cache",
            group="Applications",
            description="Cached web resources and logs for Slack desktop.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=_electron_subtargets(
                slack_root, ("Cache", "GPUCache", "Service Worker"), existing_only=False
            ),
        )
    )

    categories.append(
        CleanupCategory(
            id="spotify_cache",
            name="Spotify cache",
            group="Applications",
            description="Locally cached songs and album artwork. Does not delete playlists, offline downloads, or user settings.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=_targets(
                [
                    os.path.join(local, "Spotify", "Data"),
                    os.path.join(local, "Spotify", "Storage"),
                ],
                existing_only=False,
            ),
        )
    )

    categories.append(
        CleanupCategory(
            id="winget_cache",
            name="WinGet package cache",
            group="Package managers",
            description="Downloaded installer payloads cached by Windows Package Manager (winget). Safe to remove.",
            safety_level=SafetyLevel.SAFE,
            targets=_targets(
                [
                    os.path.join(local, "Microsoft", "WinGet", "Packages"),
                    os.path.join(
                        local,
                        "Packages",
                        "Microsoft.DesktopAppInstaller_8wekyb3d8bbwe",
                        "LocalCache",
                    ),
                ],
                existing_only=False,
            ),
        )
    )

    categories.append(
        CleanupCategory(
            id="chocolatey_cache",
            name="Chocolatey cache",
            group="Package managers",
            description="Downloaded package installer cache for Chocolatey.",
            safety_level=SafetyLevel.SAFE,
            targets=_targets(
                [
                    os.path.join(program_data, "chocolatey", "cache"),
                    os.path.join(program_data, "chocolatey", "lib-bad"),
                ],
                existing_only=False,
            ),
        )
    )

    categories.append(
        CleanupCategory(
            id="scoop_cache",
            name="Scoop cache",
            group="Package managers",
            description="Downloaded installer archives for Scoop package manager.",
            safety_level=SafetyLevel.SAFE,
            targets=_targets([os.path.join(user, "scoop", "cache")], existing_only=False),
        )
    )

    return categories


def _get_linux_categories(
    appdata: str, local: str, user: str, program_data: str
) -> list[CleanupCategory]:
    categories: list[CleanupCategory] = []

    categories.append(
        CleanupCategory(
            id="discord_cache",
            name="Discord cache",
            group="Applications",
            description="Cached media, avatars, and Electron runtime data for Discord. Re-downloaded as needed.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=_electron_subtargets(
                os.path.join(appdata, "discord"),
                ("Cache", "GPUCache", "Code Cache", "Service Worker", "Partitions"),
                existing_only=False,
            ),
        )
    )

    categories.append(
        CleanupCategory(
            id="slack_cache",
            name="Slack cache",
            group="Applications",
            description="Cached web resources and logs for Slack desktop.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=_electron_subtargets(
                os.path.join(appdata, "Slack"),
                ("Cache", "GPUCache", "Code Cache", "Service Worker"),
                existing_only=False,
            ),
        )
    )

    categories.append(
        CleanupCategory(
            id="spotify_cache",
            name="Spotify cache",
            group="Applications",
            description="Locally cached songs and album artwork. Does not delete playlists, offline downloads, or user settings.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=_targets(
                [
                    os.path.join(appdata, "spotify", "Storage"),
                    os.path.join(local, "spotify", "Data"),
                    os.path.join(local, "spotify", "Storage"),
                ],
                existing_only=False,
            ),
        )
    )

    categories.append(
        CleanupCategory(
            id="apt_cache",
            name="APT package cache",
            group="Package managers",
            description="Downloaded package files cached by APT. Safe to remove; packages can be downloaded again later.",
            safety_level=SafetyLevel.SAFE,
            targets=_targets([os.path.join(program_data, "apt", "archives")], existing_only=False),
        )
    )

    categories.append(
        CleanupCategory(
            id="dnf_cache",
            name="DNF package cache",
            group="Package managers",
            description="Downloaded package metadata and payloads cached by DNF. Safe to remove; DNF will refresh what it needs.",
            safety_level=SafetyLevel.SAFE,
            targets=_targets(
                [
                    os.path.join(program_data, "dnf"),
                    os.path.join(program_data, "libdnf5"),
                ],
                existing_only=False,
            ),
        )
    )

    categories.append(
        CleanupCategory(
            id="pacman_cache",
            name="Pacman package cache",
            group="Package managers",
            description="Downloaded package archives cached by pacman. Safe to remove, though Arch users may prefer to keep some versions for rollback.",
            safety_level=SafetyLevel.REVIEW,
            targets=_targets(["/var/cache/pacman/pkg"], existing_only=False),
        )
    )

    categories.append(
        CleanupCategory(
            id="flatpak_cache",
            name="Flatpak cache",
            group="Package managers",
            description="User and system Flatpak temporary cache data. Installed applications and runtimes are not targeted.",
            safety_level=SafetyLevel.SAFE,
            targets=_targets(
                [
                    os.path.join(local, "flatpak"),
                    "/var/tmp/flatpak-cache",
                    "/var/lib/flatpak/repo/tmp",
                ],
                existing_only=False,
            ),
        )
    )

    categories.append(
        CleanupCategory(
            id="snap_cache",
            name="Snap cache",
            group="Package managers",
            description="Downloaded assertions and temporary package cache files used by snapd. Installed snaps are not removed.",
            safety_level=SafetyLevel.SAFE,
            targets=_targets(
                [
                    "/var/lib/snapd/cache",
                    "/var/cache/snapd",
                    os.path.join(user, "snap"),
                ],
                existing_only=False,
            ),
        )
    )

    return categories


def get_categories() -> list[CleanupCategory]:
    appdata = get_appdata()
    local = get_local_appdata()
    user = get_user_profile()
    program_data = get_program_data()

    if is_linux():
        categories = _get_linux_categories(appdata, local, user, program_data)
    else:
        categories = _get_windows_categories(appdata, local, user, program_data)

    return [category for category in categories if category.targets or category.finder]
