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
            what_it_contains="Discord's Electron caches: downloaded images, avatars and attachments (Cache), compiled script bytecode (Code Cache), and the GPU shader cache.",
            why_it_grows="Every server and channel you open caches its avatars, emoji, and media, and nothing prunes them.",
            why_safe_to_delete="You stay logged in: the session token, settings, and message drafts live in Discord's Local Storage, which is not targeted. Only cached copies of media go, and Discord downloads them again as you scroll.",
            regeneration_behavior="Discord refills the caches as you use it; the first launch and the first few channels are slower.",
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
            what_it_contains="Slack desktop's HTTP cache, GPU cache, and the service worker storage that holds the app shell for offline start.",
            why_it_grows="Every workspace, avatar, and file preview you open is cached, and each Slack update leaves another app shell behind.",
            why_safe_to_delete="You stay signed in to your workspaces - sessions and preferences are stored outside these folders and are not targeted. Slack re-downloads the app shell and any avatars or previews it needs, so the next launch is slower and needs a connection.",
            regeneration_behavior="Rebuilt on the next launch and as you open channels again.",
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
            description="Locally cached songs and album artwork. Playlists, library, and settings are untouched; tracks saved for offline listening live here too and would be downloaded again.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="Spotify's local media store under Local AppData - cached audio chunks and album art, including tracks saved for offline listening.",
            why_it_grows="Everything you play is cached, and Spotify keeps filling this folder up to the storage limit set in its settings.",
            why_safe_to_delete="Playlists, your library, and app settings live in your Spotify account and config, not here, so nothing you saved is lost. This is not free for offline listeners: downloaded tracks are stored in this same folder and have to be downloaded again.",
            regeneration_behavior="Spotify re-caches music as you play it; anything you keep offline needs re-downloading.",
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
            what_it_contains="Installer payloads winget downloaded while installing or upgrading applications.",
            why_it_grows="Every install and upgrade leaves its downloaded installer behind.",
            why_safe_to_delete="Installed applications are unaffected - only downloaded installers go. The folder where winget unpacks tools installed in portable mode is deliberately not touched: those are installed applications, not cache.",
            regeneration_behavior="winget downloads what it needs on the next install or upgrade.",
            targets=_targets(
                [
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
            what_it_contains="Chocolatey's download cache and its lib-bad folder, which holds the leftovers of package installs that failed.",
            why_it_grows="Every install or upgrade downloads an installer into the cache, and failed installs are moved aside into lib-bad instead of being deleted.",
            why_safe_to_delete="Installed packages under chocolatey\\lib and the applications themselves are not targeted, so nothing you use stops working. Installing or upgrading a package downloads its installer again, so the machine needs to reach its package source.",
            regeneration_behavior="The cache refills on the next choco install or upgrade.",
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
            what_it_contains="The installer archives Scoop downloaded, one per app and version it has installed.",
            why_it_grows="Scoop keeps the download for every version it installs so a reinstall or downgrade can reuse it.",
            why_safe_to_delete="Installed apps in scoop\\apps and their shims in scoop\\shims are not targeted, so nothing stops working. Reinstalling an app or rolling back to an older version re-downloads it instead of using the local copy.",
            regeneration_behavior="The cache refills on the next scoop install or update.",
            targets=_targets([os.path.join(user, "scoop", "cache")], existing_only=False),
        )
    )

    return categories


#: Electron cache folders. Identical whatever way the app was installed.
_ELECTRON_CACHE_SUBS = ("Cache", "GPUCache", "Code Cache", "Service Worker", "Partitions")


def _linux_config_roots(user: str, appdata: str, config_dir: str, flatpak_id: str, snap: str):
    """Native XDG, Flatpak (~/.var/app) and Snap (~/snap) config roots.

    Install method decides which one exists, so all three are probed.
    """
    return [
        os.path.join(appdata, config_dir),
        os.path.join(user, ".var", "app", flatpak_id, "config", config_dir),
        os.path.join(user, "snap", snap, "current", ".config", config_dir),
    ]


def _linux_cache_roots(user: str, local: str, cache_dir: str, flatpak_id: str, snap: str):
    """The cache-side equivalent of :func:`_linux_config_roots`."""
    return [
        os.path.join(local, cache_dir),
        os.path.join(user, ".var", "app", flatpak_id, "cache", cache_dir),
        os.path.join(user, "snap", snap, "current", ".cache", cache_dir),
    ]


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
            what_it_contains="Discord's Electron caches for native, Flatpak, and Snap installs: HTTP cache, GPU and code caches, service worker storage, and the per-partition web data of embedded views.",
            why_it_grows="Every server you open caches its avatars, emoji, and media, and each install method keeps its own copy of the lot.",
            why_safe_to_delete="Your Discord login and settings live in Local Storage, which is not targeted. The partition folders do hold sign-in state for pages embedded inside Discord, so an embedded service may ask you to log in again.",
            regeneration_behavior="Discord refills the caches as you use it; the first launch after cleaning is slower.",
            targets=[
                target
                for root in _linux_config_roots(
                    user, appdata, "discord", "com.discordapp.Discord", "discord"
                )
                for target in _electron_subtargets(root, _ELECTRON_CACHE_SUBS, existing_only=False)
            ],
        )
    )

    categories.append(
        CleanupCategory(
            id="slack_cache",
            name="Slack cache",
            group="Applications",
            description="Cached web resources and logs for Slack desktop.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="Slack desktop's HTTP, GPU, and code caches plus its service worker storage, for native, Flatpak, and Snap installs.",
            why_it_grows="Every workspace, avatar, and file preview you open is cached, and each Slack update leaves another app shell behind.",
            why_safe_to_delete="You stay signed in to your workspaces - sessions and preferences are stored outside these folders and are not targeted. Slack re-downloads the app shell and the avatars and previews it needs, so the next launch is slower and needs a connection.",
            regeneration_behavior="Rebuilt on the next launch and as you open channels again.",
            targets=[
                target
                for root in _linux_config_roots(user, appdata, "Slack", "com.slack.Slack", "slack")
                for target in _electron_subtargets(
                    root, ("Cache", "GPUCache", "Code Cache", "Service Worker"), existing_only=False
                )
            ],
        )
    )

    categories.append(
        CleanupCategory(
            id="spotify_cache",
            name="Spotify cache",
            group="Applications",
            description="Locally cached songs and album artwork. Playlists, library, and settings are untouched; tracks saved for offline listening live here too and would be downloaded again.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="Spotify's local media store for native, Flatpak, and Snap installs - cached audio chunks and album art, including tracks saved for offline listening.",
            why_it_grows="Everything you play is cached, and Spotify keeps filling the folder up to the storage limit set in its settings.",
            why_safe_to_delete="Playlists, your library, and app settings live in your Spotify account and config, not here, so nothing you saved is lost. This is not free for offline listeners: downloaded tracks share this folder and have to be downloaded again.",
            regeneration_behavior="Spotify re-caches music as you play it; anything you keep offline needs re-downloading.",
            targets=_targets(
                [
                    os.path.join(root, sub)
                    for root in (
                        _linux_config_roots(
                            user, appdata, "spotify", "com.spotify.Client", "spotify"
                        )
                        + _linux_cache_roots(
                            user, local, "spotify", "com.spotify.Client", "spotify"
                        )
                    )
                    for sub in ("Data", "Storage")
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
            what_it_contains="The .deb archives APT downloaded in order to install or upgrade software, kept in /var/cache/apt/archives.",
            why_it_grows="Every apt install and upgrade leaves its .deb behind, and APT only removes them when asked.",
            why_safe_to_delete="The packages are already installed and unpacked; these are the archives they came from, and this is what 'apt clean' deletes. Reinstalling or downgrading a package afterwards has to fetch it from a mirror instead of the local copy.",
            regeneration_behavior="Refilled by the next apt install or upgrade.",
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
            what_it_contains="Downloaded RPM packages and the per-repository metadata DNF and libdnf5 cache under /var/cache.",
            why_it_grows="Each enabled repository caches its metadata and refreshes it periodically, and installed packages leave their RPMs behind.",
            why_safe_to_delete="Installed software is unaffected - this is exactly what 'dnf clean all' clears. DNF re-downloads repository metadata on the next transaction, so that command takes longer and needs network access.",
            regeneration_behavior="Rebuilt on the next dnf command that touches a repository.",
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
            what_it_contains="Every package archive pacman has downloaded, including older versions of packages you currently have installed.",
            why_it_grows="pacman keeps each version it downloads rather than deleting it, and a rolling release adds new ones constantly.",
            why_safe_to_delete="Installed packages keep working; only the downloaded archives go. This cache is your only local copy of previous versions, so after clearing it a rollback from a bad update has to come from a mirror or the Arch Linux Archive - 'paccache -r', which keeps the last few versions, is the safer middle ground.",
            regeneration_behavior="Refilled as pacman downloads packages for the next upgrade.",
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
            what_it_contains="Flatpak's user cache and the temporary staging folders under /var - partial downloads, repository scratch data, and checksum caches.",
            why_it_grows="Every install and update stages data here, and interrupted downloads leave their partial objects behind.",
            why_safe_to_delete="Installed applications, runtimes, and per-app data in ~/.var/app are not targeted, so nothing you have installed is removed. An update that was interrupted loses its partial download and starts over from the beginning.",
            regeneration_behavior="Recreated during the next flatpak install or update.",
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
            what_it_contains="snapd's download and assertion caches under /var.",
            why_it_grows="snapd caches every snap it downloads.",
            why_safe_to_delete="Installed snaps live under /snap and are not removed. ~/snap is deliberately not touched: it holds each snap's own settings and any files an application saved there, which is user data rather than cache.",
            regeneration_behavior="snapd re-downloads what it needs on the next install or refresh.",
            targets=_targets(
                [
                    "/var/lib/snapd/cache",
                    "/var/cache/snapd",
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
