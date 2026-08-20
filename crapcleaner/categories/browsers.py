"""Browser cache cleanup categories (Windows and Linux).

Provides deep web cache, code cache, and GPU cache inspection across Chromium
and Firefox derivatives while guaranteeing absolute protection for bookmarks,
passwords, cookies, browsing history, and extensions.
"""

import glob
import os
from collections.abc import Iterable

from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.utils.platform import (
    get_appdata,
    get_local_appdata,
    get_user_profile,
    is_linux,
    is_windows,
    run_command,
)

_BROWSER_PROCESS_MAP = {
    "chrome": "chrome.exe",
    "chromium": "chromium.exe",
    "edge": "msedge.exe",
    "brave": "brave.exe",
    "opera": "opera.exe",
    "operagx": "opera.exe",
    "vivaldi": "vivaldi.exe",
    "thorium": "thorium.exe",
    "arc": "Arc.exe",
    "firefox": "firefox.exe",
    "librewolf": "librewolf.exe",
    "waterfox": "waterfox.exe",
    "floorp": "floorp.exe",
}

BROWSER_DISPLAY_NAMES = {
    "chrome": "Google Chrome",
    "chromium": "Chromium",
    "edge": "Microsoft Edge",
    "brave": "Brave Browser",
    "opera": "Opera",
    "operagx": "Opera GX",
    "vivaldi": "Vivaldi",
    "thorium": "Thorium",
    "arc": "Arc",
    "firefox": "Mozilla Firefox",
    "librewolf": "LibreWolf",
    "waterfox": "Waterfox",
    "floorp": "Floorp",
}


def _process_listing() -> str:
    """One lowercase snapshot of running process names, or "" if unavailable."""
    if is_windows():
        res = run_command(["tasklist", "/FO", "CSV", "/NH"], timeout=8.0)
    elif is_linux():
        res = run_command(["ps", "-eo", "comm="], timeout=8.0)
    else:
        return ""
    if res.get("returncode") != 0:
        return ""
    return str(res.get("stdout", "")).lower()


def running_browsers(browser_ids: Iterable[str]) -> list[str]:
    """Which of `browser_ids` currently have a running process.

    A single process listing answers for every browser at once; asking per browser
    would spawn a dozen subprocesses in front of a cleanup the user is waiting on.
    """
    wanted = {
        bid: _BROWSER_PROCESS_MAP[bid]
        for bid in dict.fromkeys(browser_ids)
        if bid in _BROWSER_PROCESS_MAP
    }
    if not wanted:
        return []
    listing = _process_listing()
    if not listing:
        return []
    running = []
    for bid, proc_name in wanted.items():
        needle = proc_name.lower() if is_windows() else proc_name[:-4].lower()
        if needle in listing:
            running.append(bid)
    return running


def is_browser_running(browser_id: str) -> bool:
    """Whether the given browser is currently running."""
    return bool(running_browsers([browser_id.lower()]))


def running_browser_names(category_ids: Iterable[str]) -> list[str]:
    """Display names of browsers that are running and own one of `category_ids`.

    Their cache files are locked while they run, so a cleanup will skip some of
    them; the user is told rather than the browser being closed for them.
    """
    ids = list(category_ids)
    involved = [
        bid
        for bid in _BROWSER_PROCESS_MAP
        if any(cid == bid or cid.startswith(f"{bid}_") for cid in ids)
    ]
    return [BROWSER_DISPLAY_NAMES.get(bid, bid) for bid in running_browsers(involved)]


def _chromium_profiles(root: str) -> list[str]:
    profiles: list[str] = []
    if not root or not os.path.isdir(root):
        return profiles
    for name in ("Default", "Profile *", "Guest Profile", "System Profile"):
        matches = glob.glob(os.path.join(root, name))
        profiles.extend(m for m in matches if os.path.isdir(m))
    return profiles


def _build_browser_categories(browser_id: str, display: str, root: str) -> list[CleanupCategory]:
    if not root or not os.path.isdir(root):
        return []
    profiles = _chromium_profiles(root)
    if not profiles:
        return []

    def _targets(subpaths: tuple[str, ...]) -> list[CacheTarget]:
        targets = []
        for profile in profiles:
            for sub in subpaths:
                # sub is a "a/b" string, not a sequence: split it or join() walks characters.
                p = os.path.join(profile, *sub.split("/"))
                if os.path.isdir(p):
                    targets.append(CacheTarget(path=p))
        return targets

    return [
        CleanupCategory(
            id=f"{browser_id}_cache",
            name=f"{display} cache",
            group="Browsers",
            description=f"HTTP/web cache for {display}. Clears cached pages and files; does NOT touch bookmarks, passwords, cookies, extensions, profiles, or saved sessions.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains=f"Cached images, stylesheets, scripts, and media files from visited web pages in {display}.",
            why_it_grows="Browsers cache website assets locally to speed up repeat visits.",
            why_safe_to_delete="Safe to delete. Strictly preserves bookmarks, passwords, cookies, history, and extensions.",
            regeneration_behavior="Websites will re-download required assets on your next visit.",
            reversible=True,
            targets=_targets(("Cache",)),
        ),
        CleanupCategory(
            id=f"{browser_id}_code_cache",
            name=f"{display} code cache",
            group="Browsers",
            description=f"Compiled JavaScript code cache for {display}. Rebuilt on next visit.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains=f"V8/Blink compiled bytecode and WebAssembly code caches for {display}.",
            why_it_grows="Browsers compile JS scripts to machine bytecode to reduce script compilation overhead.",
            why_safe_to_delete="Scripts are re-compiled automatically on page load.",
            regeneration_behavior="Rebuilt during subsequent page visits.",
            reversible=True,
            targets=_targets(("Code Cache",)),
        ),
        CleanupCategory(
            id=f"{browser_id}_gpu_cache",
            name=f"{display} GPU cache",
            group="Browsers",
            description=f"GPU-accelerated cache for {display}. Rebuilt as needed.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains=f"Hardware-accelerated shader and rendering caches used by {display}.",
            why_it_grows="GPU rendering pipelines compile graphics shaders for smooth UI rendering.",
            why_safe_to_delete="Shaders are recompiled by the graphics driver and browser engine.",
            regeneration_behavior="Recompiled on subsequent browser launches.",
            reversible=True,
            targets=_targets(("GPUCache",)),
        ),
        CleanupCategory(
            id=f"{browser_id}_service_worker",
            name=f"{display} service worker cache",
            group="Browsers",
            description=f"Service worker and CacheStorage data for {display}. Websites re-download resources; may require a reload.",
            safety_level=SafetyLevel.REVIEW,
            what_it_contains=f"Progressive Web App (PWA) offline caches and CacheStorage data for {display}.",
            why_it_grows="PWAs store offline web assets in CacheStorage.",
            why_safe_to_delete="Does not delete logins or account databases; offline resources re-sync on next load.",
            regeneration_behavior="PWA sites will re-cache offline resources when opened.",
            reversible=True,
            targets=_targets(("Service Worker", "CacheStorage")),
        ),
    ]


def _firefox_categories(browser_id: str, display: str, profiles_root: str) -> list[CleanupCategory]:
    profiles = []
    if profiles_root and os.path.isdir(profiles_root):
        for entry in glob.glob(os.path.join(profiles_root, "*.default*")):
            if os.path.isdir(entry):
                profiles.append(entry)

    targets = []
    for profile in profiles:
        for sub in ("cache2", "startupCache", "jumpListCache"):
            p = os.path.join(profile, sub)
            if os.path.isdir(p):
                targets.append(CacheTarget(path=p))

    if not targets:
        return []

    return [
        CleanupCategory(
            id=f"{browser_id}_cache",
            name=f"{display} cache",
            group="Browsers",
            description=f"{display} HTTP and startup cache. Does NOT touch bookmarks, passwords, cookies, extensions, profiles, or saved sessions.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains=f"Cached web assets (cache2) and startup cache for {display}.",
            why_it_grows="Firefox engine caches web resources and UI startup components.",
            why_safe_to_delete="Safe to delete. Bookmarks, logins, and session state are strictly preserved.",
            regeneration_behavior="Rebuilt automatically as you browse.",
            reversible=True,
            targets=targets,
        )
    ]


def get_categories() -> list[CleanupCategory]:
    local = get_local_appdata()
    appdata = get_appdata()
    user = get_user_profile()
    categories: list[CleanupCategory] = []

    if is_windows():
        categories.extend(
            _build_browser_categories(
                "chrome", "Google Chrome", os.path.join(local, "Google", "Chrome", "User Data")
            )
        )
        categories.extend(
            _build_browser_categories(
                "edge", "Microsoft Edge", os.path.join(local, "Microsoft", "Edge", "User Data")
            )
        )
        categories.extend(
            _build_browser_categories(
                "brave",
                "Brave Browser",
                os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data"),
            )
        )
        categories.extend(
            _build_browser_categories(
                "opera", "Opera", os.path.join(appdata, "Opera Software", "Opera Stable")
            )
        )
        categories.extend(
            _build_browser_categories(
                "operagx", "Opera GX", os.path.join(appdata, "Opera Software", "Opera GX Stable")
            )
        )
        categories.extend(
            _build_browser_categories(
                "vivaldi", "Vivaldi", os.path.join(local, "Vivaldi", "User Data")
            )
        )
        categories.extend(
            _build_browser_categories(
                "thorium", "Thorium", os.path.join(local, "Thorium", "User Data")
            )
        )
        categories.extend(
            _build_browser_categories(
                "arc",
                "Arc",
                os.path.join(
                    local,
                    "Packages",
                    "TheBrowserCompany.Arc_ttt1ap7aakyb4",
                    "LocalCache",
                    "Local",
                    "Arc",
                    "User Data",
                ),
            )
        )

        categories.extend(
            _firefox_categories(
                "firefox", "Mozilla Firefox", os.path.join(local, "Mozilla", "Firefox", "Profiles")
            )
        )
        categories.extend(
            _firefox_categories(
                "librewolf", "LibreWolf", os.path.join(local, "LibreWolf", "Profiles")
            )
        )
        categories.extend(
            _firefox_categories("waterfox", "Waterfox", os.path.join(local, "Waterfox", "Profiles"))
        )
        categories.extend(
            _firefox_categories("floorp", "Floorp", os.path.join(local, "Floorp", "Profiles"))
        )

    elif is_linux():
        categories.extend(
            _build_browser_categories(
                "chrome", "Google Chrome", os.path.join(user, ".config", "google-chrome")
            )
        )
        categories.extend(
            _build_browser_categories(
                "chrome_beta",
                "Google Chrome Beta",
                os.path.join(user, ".config", "google-chrome-beta"),
            )
        )
        categories.extend(
            _build_browser_categories(
                "chromium", "Chromium", os.path.join(user, ".config", "chromium")
            )
        )
        categories.extend(
            _build_browser_categories(
                "edge", "Microsoft Edge", os.path.join(user, ".config", "microsoft-edge")
            )
        )
        categories.extend(
            _build_browser_categories(
                "brave",
                "Brave Browser",
                os.path.join(user, ".config", "BraveSoftware", "Brave-Browser"),
            )
        )
        categories.extend(
            _build_browser_categories("opera", "Opera", os.path.join(user, ".config", "opera"))
        )
        categories.extend(
            _build_browser_categories(
                "vivaldi", "Vivaldi", os.path.join(user, ".config", "vivaldi")
            )
        )
        categories.extend(
            _build_browser_categories(
                "thorium", "Thorium", os.path.join(user, ".config", "thorium")
            )
        )

        categories.extend(
            _firefox_categories(
                "firefox", "Mozilla Firefox", os.path.join(user, ".mozilla", "firefox")
            )
        )
        categories.extend(
            _firefox_categories("librewolf", "LibreWolf", os.path.join(user, ".librewolf"))
        )
        categories.extend(
            _firefox_categories("waterfox", "Waterfox", os.path.join(user, ".waterfox"))
        )
        categories.extend(_firefox_categories("floorp", "Floorp", os.path.join(user, ".floorp")))

    return categories
