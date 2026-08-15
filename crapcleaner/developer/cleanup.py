"""Developer tool cache categories (VS Code, Cursor, Zed, Cargo, Go, Gradle, Maven, Unity, Godot, Unreal, CMake, s&box).

Strictly targets package caches, compiler outputs, and index artifacts without ever
touching source code, Git repositories, or user assets.
"""

import glob
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
            what_it_contains=f"UI caches, extension VSIX caches, and GPU caches for {display}.",
            why_it_grows=f"{display} caches editor sessions and extension assets locally.",
            why_safe_to_delete="Settings, extensions, and workspaces are completely preserved.",
            regeneration_behavior="Recreated automatically upon next editor launch.",
            reversible=True,
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
                what_it_contains=f"Session logs and extension output traces for {display}.",
                why_it_grows="Logging output accumulates across editor sessions.",
                why_safe_to_delete="Logs are purely diagnostic.",
                regeneration_behavior="New logs created on subsequent sessions.",
                reversible=True,
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

    # GitHub Desktop Cache
    categories.append(
        CleanupCategory(
            id="github_desktop_cache",
            name="GitHub Desktop cache",
            group="Developer tools",
            description="Web and rendering cache for GitHub Desktop. Does not touch repositories, credentials, or Git configs.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="Electron web caches and GPU caches for GitHub Desktop.",
            why_it_grows="GitHub Desktop caches UI views and web sessions.",
            why_safe_to_delete="Repositories, commits, and authentication tokens are strictly protected.",
            regeneration_behavior="Rebuilt on next launch.",
            reversible=True,
            targets=[
                CacheTarget(path=os.path.join(appdata, "GitHub Desktop", "Cache")),
                CacheTarget(path=os.path.join(appdata, "GitHub Desktop", "GPUCache")),
            ],
        )
    )

    # Zed Editor
    categories.append(
        CleanupCategory(
            id="zed_cache",
            name="Zed cache",
            group="Developer tools",
            description="Cache data for the Zed editor. Does not touch settings or project data.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="Syntax tree caches and LSP server scratch files for Zed.",
            why_it_grows="Zed caches parser states and language server indices.",
            why_safe_to_delete="Project files and keybindings are preserved.",
            regeneration_behavior="Rebuilt when files are opened in Zed.",
            reversible=True,
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
            what_it_contains="Downloaded .crate gzip files and git repository bare checkouts for dependencies.",
            why_it_grows="Cargo caches all downloaded crate archives globally.",
            why_safe_to_delete="Cargo re-downloads required crate packages upon 'cargo build'.",
            regeneration_behavior="Re-downloaded seamlessly on future builds.",
            reversible=True,
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
            what_it_contains="Go build cache binaries and downloaded module zip archives.",
            why_it_grows="The Go toolchain caches compiled build steps and module downloads.",
            why_safe_to_delete="Equivalent to 'go clean -cache -modcache'.",
            regeneration_behavior="Rebuilt during subsequent 'go build' or 'go test'.",
            reversible=True,
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
            what_it_contains="Downloaded JAR/AAR dependencies, POM files, and Gradle distribution wrappers.",
            why_it_grows="Maven and Gradle store all resolved dependencies permanently in ~/.m2 and ~/.gradle.",
            why_safe_to_delete="Dependencies are re-downloaded from repositories on next build.",
            regeneration_behavior="Re-downloaded during Gradle/Maven build execution.",
            reversible=True,
            targets=jvm_targets,
        )
    )

    # Unity Editor Caches
    unity_targets = [
        CacheTarget(path=os.path.join(local, "Unity", "cache")),
        CacheTarget(path=os.path.join(local, "Unity", "Editor", "ShaderCache")),
        CacheTarget(path=os.path.join(local, "Unity", "Editor", "EditorLog")),
    ]
    categories.append(
        CleanupCategory(
            id="unity_caches",
            name="Unity Editor caches & shader cache",
            group="Developer tools",
            description="Global Unity Editor asset store package caches and compiled shader caches.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="Unity Package Manager global cache and editor shader cache.",
            why_it_grows="Unity caches downloaded packages and precompiled shader variants.",
            why_safe_to_delete="Project assets and scene files are never touched; Unity rebuilds caches as needed.",
            regeneration_behavior="Recompiled when opening Unity projects.",
            reversible=True,
            targets=unity_targets,
        )
    )

    # Godot Engine Caches
    godot_targets = [
        CacheTarget(path=os.path.join(appdata, "Godot", "app_userdata")),
        CacheTarget(path=os.path.join(local, "Godot", "shader_cache")),
    ]
    categories.append(
        CleanupCategory(
            id="godot_caches",
            name="Godot Engine caches",
            group="Developer tools",
            description="Godot editor shader caches and temporary editor artifacts.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="Godot editor Vulkan/OpenGL shader caches and asset library temporary downloads.",
            why_it_grows="Godot compiles shader pipelines for quick scene preview.",
            why_safe_to_delete="Project sources and scenes (.tscn/.gd) are never modified.",
            regeneration_behavior="Rebuilt during scene loading.",
            reversible=True,
            targets=godot_targets,
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
            what_it_contains="Processed textures, compiled materials, and derived platform assets for Unreal Engine.",
            why_it_grows="Unreal Engine formats source art into optimized target platform data in the DDC.",
            why_safe_to_delete="Source .uasset files in projects are untouched; DDC entries are regenerated on load.",
            regeneration_behavior="Unreal Engine re-populates the DDC during asset cooking or editor load.",
            reversible=True,
            targets=[
                CacheTarget(path=os.path.join(local, "UnrealEngine", "Common", "DerivedDataCache"))
            ],
        )
    )

    # CMake temporary build leftovers
    cmake_targets = []
    for cand in (
        os.path.join(local, "CMake"),
        os.path.join(user, ".cmake", "packages"),
    ):
        if os.path.isdir(cand):
            cmake_targets.append(CacheTarget(path=cand))
    if cmake_targets:
        categories.append(
            CleanupCategory(
                id="cmake_cache",
                name="CMake global cache & packages",
                group="Developer tools",
                description="CMake global package registry and build configuration caches.",
                safety_level=SafetyLevel.LOW_RISK,
                what_it_contains="Package registries and generator cache files from CMake.",
                why_it_grows="CMake records found package paths across project builds.",
                why_safe_to_delete="CMake generates fresh configuration caches upon running 'cmake'.",
                regeneration_behavior="Rebuilt during project configuration.",
                reversible=True,
                targets=cmake_targets,
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
            what_it_contains="s&box compiled game assets and Vulkan shader pipelines.",
            why_it_grows="s&box pre-caches downloaded community content and shaders.",
            why_safe_to_delete="Content is re-downloaded from servers when joining games.",
            regeneration_behavior="Re-cached on game join or editor compile.",
            reversible=True,
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
                what_it_contains="Cached npm package archives managed by Bun.",
                why_it_grows="Bun caches packages in ~/.bun to speed up repeated installs.",
                why_safe_to_delete="Packages are re-downloaded as needed.",
                regeneration_behavior="Rebuilt during 'bun install'.",
                reversible=True,
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
                what_it_contains="AAR/DEX compilation cache and Gradle daemon execution logs.",
                why_it_grows="Android Studio caches transformed build outputs.",
                why_safe_to_delete="Safe to clean; builds will rebuild transform artifacts.",
                regeneration_behavior="Re-created during subsequent Android Studio builds.",
                reversible=True,
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
                what_it_contains="Symbol indexes, syntax caches, and session log files for JetBrains IDEs.",
                why_it_grows="JetBrains indexes project symbols to provide fast navigation.",
                why_safe_to_delete="Project files and settings are untouched; IDE will re-index on next launch.",
                regeneration_behavior="Re-indexes projects automatically.",
                reversible=True,
                targets=jb_targets,
            )
        )

    return categories
