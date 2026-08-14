"""Browser cache cleanup categories (Windows and Linux)."""

import glob
import os

from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.utils.platform import get_local_appdata, get_user_profile, is_linux, is_windows


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
                p = os.path.join(profile, *sub)
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
            targets=_targets(("Cache",)),
        ),
        CleanupCategory(
            id=f"{browser_id}_code_cache",
            name=f"{display} code cache",
            group="Browsers",
            description=f"Compiled JavaScript code cache for {display}. Rebuilt on next visit.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=_targets(("Code Cache",)),
        ),
        CleanupCategory(
            id=f"{browser_id}_gpu_cache",
            name=f"{display} GPU cache",
            group="Browsers",
            description=f"GPU-accelerated cache for {display}. Rebuilt as needed.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=_targets(("GPUCache",)),
        ),
        CleanupCategory(
            id=f"{browser_id}_service_worker",
            name=f"{display} service worker cache",
            group="Browsers",
            description=f"Service worker and CacheStorage data for {display}. Websites re-download resources; may require a reload.",
            safety_level=SafetyLevel.REVIEW,
            targets=_targets(("Service Worker", "CacheStorage")),
        ),
    ]


def _firefox_categories(_display: str, profiles_root: str) -> list[CleanupCategory]:
    profiles = []
    if profiles_root and os.path.isdir(profiles_root):
        for entry in glob.glob(os.path.join(profiles_root, "*.default*")):
            if os.path.isdir(entry):
                profiles.append(entry)

    targets = []
    for profile in profiles:
        for sub in ("cache2", "startupCache"):
            p = os.path.join(profile, sub)
            if os.path.isdir(p):
                targets.append(CacheTarget(path=p))

    if not targets:
        return []

    return [
        CleanupCategory(
            id="firefox_cache",
            name="Firefox cache",
            group="Browsers",
            description="Firefox HTTP and startup cache. Does NOT touch bookmarks, passwords, cookies, extensions, profiles, or saved sessions.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=targets,
        )
    ]


def get_categories() -> list[CleanupCategory]:
    local = get_local_appdata()
    user = get_user_profile()
    categories: list[CleanupCategory] = []

    if is_windows():
        categories.extend(
            _build_browser_categories(
                "chrome",
                "Chrome",
                os.path.join(local, "Google", "Chrome", "User Data"),
            )
        )
        categories.extend(
            _build_browser_categories(
                "edge",
                "Edge",
                os.path.join(local, "Microsoft", "Edge", "User Data"),
            )
        )
        categories.extend(
            _build_browser_categories(
                "brave",
                "Brave",
                os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data"),
            )
        )
        categories.extend(
            _firefox_categories(
                "Firefox",
                os.path.join(local, "Mozilla", "Firefox", "Profiles"),
            )
        )

    elif is_linux():
        categories.extend(
            _build_browser_categories(
                "chrome",
                "Chrome",
                os.path.join(user, ".config", "google-chrome"),
            )
        )
        categories.extend(
            _build_browser_categories(
                "chrome_beta",
                "Chrome Beta",
                os.path.join(user, ".config", "google-chrome-beta"),
            )
        )
        categories.extend(
            _build_browser_categories(
                "chromium",
                "Chromium",
                os.path.join(user, ".config", "chromium"),
            )
        )
        categories.extend(
            _build_browser_categories(
                "edge",
                "Edge",
                os.path.join(user, ".config", "microsoft-edge"),
            )
        )
        categories.extend(
            _build_browser_categories(
                "brave",
                "Brave",
                os.path.join(user, ".config", "BraveSoftware", "Brave-Browser"),
            )
        )
        categories.extend(
            _firefox_categories(
                "Firefox",
                os.path.join(user, ".mozilla", "firefox"),
            )
        )

    return categories
