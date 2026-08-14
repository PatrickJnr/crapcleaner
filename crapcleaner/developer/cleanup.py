"""Developer tool cache categories (VS Code, Cursor, Windsurf, Kiro, Zed, Rust/Cargo, Go, Gradle, Maven, Unreal, s&box)."""

import os

from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.utils.platform import get_appdata, get_local_appdata, get_user_profile

_CACHE_SUBDIRS = (
    "Cache",
    "CachedData",
    "CachedExtensionVSIXs",
    "Code Cache",
    "GPUCache",
)
_LOG_SUBDIRS = ("logs",)


def _electron_tool_categories(
    tool_id: str, display: str, root: str, skip_logs: bool = False
) -> list[CleanupCategory]:
    if not root:
        return []

    cache_targets = [CacheTarget(path=os.path.join(root, sub)) for sub in _CACHE_SUBDIRS]

    categories = [
        CleanupCategory(
            id=f"{tool_id}_caches",
            name=f"{display} caches",
            group="Developer tools",
            description=f"Cache data for {display}. Does not touch settings, extensions, or workspace files.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=cache_targets,
        )
    ]
    if not skip_logs:
        log_targets = [CacheTarget(path=os.path.join(root, sub)) for sub in _LOG_SUBDIRS]
        categories.append(
            CleanupCategory(
                id=f"{tool_id}_logs",
                name=f"{display} logs",
                group="Developer tools",
                description=f"Log output for {display}. Safe to remove.",
                safety_level=SafetyLevel.SAFE,
                targets=log_targets,
            )
        )
    return categories


def get_categories() -> list[CleanupCategory]:
    appdata = get_appdata()
    local = get_local_appdata()
    user = get_user_profile()

    categories: list[CleanupCategory] = []
    categories.extend(_electron_tool_categories("vscode", "VS Code", os.path.join(appdata, "Code")))
    categories.extend(
        _electron_tool_categories(
            "vscode_insiders",
            "VS Code Insiders",
            os.path.join(appdata, "Code - Insiders"),
        )
    )
    categories.extend(
        _electron_tool_categories("cursor", "Cursor", os.path.join(appdata, "Cursor"))
    )
    categories.extend(
        _electron_tool_categories("windsurf", "Windsurf", os.path.join(appdata, "Windsurf"))
    )
    categories.extend(_electron_tool_categories("kiro", "Kiro", os.path.join(appdata, "Kiro")))

    # Zed Editor
    categories.append(
        CleanupCategory(
            id="zed_cache",
            name="Zed cache",
            group="Developer tools",
            description="Cache data for the Zed editor. Does not touch settings or project data.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=[CacheTarget(path=os.path.join(appdata, "Zed", "cache"))],
        )
    )

    # Rust / Cargo package & git caches
    cargo_targets = [
        CacheTarget(path=os.path.join(user, ".cargo", "registry", "cache")),
        CacheTarget(path=os.path.join(user, ".cargo", "git", "db")),
        CacheTarget(path=os.path.join(user, ".rustup", "downloads")),
    ]
    categories.append(
        CleanupCategory(
            id="cargo_cache",
            name="Rust / Cargo cache",
            group="Developer tools",
            description="Downloaded crate archives and git index caches. Re-downloaded when building projects.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=cargo_targets,
        )
    )

    # Go build and module download caches
    go_targets = [
        CacheTarget(path=os.path.join(local, "go-build")),
        CacheTarget(path=os.path.join(user, "go", "pkg", "mod", "cache")),
    ]
    categories.append(
        CleanupCategory(
            id="go_cache",
            name="Go build & module cache",
            group="Developer tools",
            description="Compiled Go package artifacts and downloaded modules. Re-downloaded on build.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=go_targets,
        )
    )

    # Gradle / Maven build tool caches
    jvm_targets = [
        CacheTarget(path=os.path.join(user, ".gradle", "caches")),
        CacheTarget(path=os.path.join(user, ".m2", "repository")),
    ]
    categories.append(
        CleanupCategory(
            id="jvm_build_cache",
            name="Gradle & Maven package cache",
            group="Developer tools",
            description="Downloaded dependencies and wrapper caches for Gradle and Maven.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=jvm_targets,
        )
    )

    # GitHub Desktop
    github_desktop_targets = [
        CacheTarget(path=os.path.join(local, "GitHubDesktop", "Cache")),
        CacheTarget(path=os.path.join(appdata, "GitHub Desktop", "Cache")),
        CacheTarget(path=os.path.join(local, "GitHubDesktop", "packages")),
    ]
    categories.append(
        CleanupCategory(
            id="github_desktop_cache",
            name="GitHub Desktop caches",
            group="Developer tools",
            description="Cache and bundled runtime data for GitHub Desktop. Re-downloaded as needed.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=github_desktop_targets,
        )
    )

    # Unreal Engine DDC
    categories.append(
        CleanupCategory(
            id="unreal_ddc",
            name="Unreal Engine Derived Data Cache",
            group="Developer tools",
            description="Unreal Engine Derived Data Cache (DDC). Rebuilt as needed; the next editor load may be slower and recompile shaders.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=[
                CacheTarget(path=os.path.join(local, "UnrealEngine", "Common", "DerivedDataCache"))
            ],
        )
    )

    # s&box
    sbox_root = os.path.join(local, "s&box")
    sbox_targets = [
        CacheTarget(path=os.path.join(sbox_root, "cachedata")),
        CacheTarget(path=os.path.join(sbox_root, "shadercache")),
    ]
    categories.append(
        CleanupCategory(
            id="sbox_caches",
            name="s&box caches",
            group="Developer tools",
            description="Cache data for the s&box editor and games. Rebuilt on demand; may cause slower first load after cleaning.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=sbox_targets,
        )
    )

    # Bun Cache
    bun_root = os.path.join(user, ".bun", "install", "cache")
    if os.path.isdir(bun_root):
        categories.append(
            CleanupCategory(
                id="bun_cache",
                name="Bun package cache",
                group="Developer tools",
                description="Global package cache for the Bun JavaScript runtime and package manager.",
                safety_level=SafetyLevel.SAFE,
                targets=[CacheTarget(path=bun_root)],
            )
        )

    # Android SDK & Gradle Daemon Logs
    android_targets = []
    for candidate in (
        os.path.join(user, ".android", "cache"),
        os.path.join(user, ".android", "build-cache"),
        os.path.join(user, ".gradle", "daemon"),
    ):
        if os.path.isdir(candidate):
            android_targets.append(CacheTarget(path=candidate))
    if android_targets:
        categories.append(
            CleanupCategory(
                id="android_gradle_daemon",
                name="Android & Gradle daemon caches",
                group="Developer tools",
                description="Android build-cache and Gradle daemon log files. Re-generated on subsequent builds.",
                safety_level=SafetyLevel.LOW_RISK,
                targets=android_targets,
            )
        )

    # JetBrains IDE Caches
    jb_targets = []
    jb_local = os.path.join(local, "JetBrains")
    if os.path.isdir(jb_local):
        try:
            for entry in os.listdir(jb_local):
                ide_dir = os.path.join(jb_local, entry)
                if os.path.isdir(ide_dir):
                    for sub in ("caches", "log"):
                        p = os.path.join(ide_dir, sub)
                        if os.path.isdir(p):
                            jb_targets.append(CacheTarget(path=p))
        except OSError:
            pass
    if jb_targets:
        categories.append(
            CleanupCategory(
                id="jetbrains_caches",
                name="JetBrains IDE caches & logs",
                group="Developer tools",
                description="Index caches and log files for IntelliJ, PyCharm, WebStorm, Rider, and CLion.",
                safety_level=SafetyLevel.LOW_RISK,
                targets=jb_targets,
            )
        )

    return categories
