"""Gaming cleanup categories (Steam, EA Desktop, Ubisoft, Riot, FiveM, Launchers, DirectX Shaders)."""

import os

from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.utils.platform import (
    get_local_appdata,
    get_program_data,
    get_program_files_x86,
)


def get_categories() -> list[CleanupCategory]:
    local = get_local_appdata()
    program_data = get_program_data()
    prog_x86 = get_program_files_x86()

    categories: list[CleanupCategory] = []

    # 1. Steam Caches & Temporary Downloads
    steam_roots = [
        os.path.join(prog_x86, "Steam"),
        os.path.join(local, "Steam"),
    ]
    steam_targets = []
    for root in steam_roots:
        for sub in (
            "htmlcache",
            "logs",
            "appcache",
            "depotcache",
            "steamapps/downloading",
            "steamapps/temp",
        ):
            steam_targets.append(CacheTarget(path=os.path.join(root, sub.replace("/", os.sep))))
    categories.append(
        CleanupCategory(
            id="steam_caches",
            name="Steam caches & temp downloads",
            group="Gaming",
            description="Temporary web browser caches, shader depot caches, and incomplete download files for Steam.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=steam_targets,
        )
    )

    # 2. DirectX Shader Caches
    dx_targets = [
        CacheTarget(path=os.path.join(local, "D3DSCache")),
        CacheTarget(path=os.path.join(local, "DirectXShaderCache")),
        CacheTarget(path=os.path.join(local, "NVIDIA", "DXCache")),
        CacheTarget(path=os.path.join(local, "NVIDIA", "GLCache")),
        CacheTarget(path=os.path.join(local, "AMD", "DxCache")),
    ]
    categories.append(
        CleanupCategory(
            id="directx_shader_cache",
            name="DirectX & GPU shader caches",
            group="Gaming",
            description="Compiled graphics and DirectX shader caches. Rebuilt automatically during gameplay.",
            safety_level=SafetyLevel.SAFE,
            targets=dx_targets,
        )
    )

    # 3. FiveM Caches
    fivem_root = os.path.join(local, "FiveM", "FiveM.app")
    fivem_targets = [
        CacheTarget(path=os.path.join(fivem_root, sub))
        for sub in ("cache", "data", "gta_data", "logs")
    ]
    categories.append(
        CleanupCategory(
            id="fivem_cache",
            name="FiveM caches",
            group="Gaming",
            description="Cache and log data for FiveM. Does not delete saves, mods, or installed server resources.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=fivem_targets,
        )
    )

    # 4. EA Desktop & Origin Caches
    ea_targets = [
        CacheTarget(path=os.path.join(local, "Electronic Arts", "EA Desktop", "Cache")),
        CacheTarget(path=os.path.join(local, "Electronic Arts", "EA Desktop", "Logs")),
        CacheTarget(path=os.path.join(local, "Origin", "Logs")),
        CacheTarget(path=os.path.join(program_data, "Electronic Arts", "EA Desktop", "Logs")),
    ]
    categories.append(
        CleanupCategory(
            id="ea_desktop_cache",
            name="EA Desktop / Origin caches",
            group="Gaming",
            description="Web caches and log files for EA App and Origin.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=ea_targets,
        )
    )

    # 5. Ubisoft Connect Caches
    ubi_targets = [
        CacheTarget(path=os.path.join(local, "Ubisoft Game Launcher", "cache")),
        CacheTarget(path=os.path.join(local, "Ubisoft Game Launcher", "logs")),
    ]
    categories.append(
        CleanupCategory(
            id="ubisoft_cache",
            name="Ubisoft Connect caches",
            group="Gaming",
            description="Browser caches and error logs for Ubisoft Connect.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=ubi_targets,
        )
    )

    # 6. Riot Games & Valorant Logs
    riot_targets = [
        CacheTarget(path=os.path.join(local, "Riot Games", "Riot Client", "Logs")),
        CacheTarget(path=os.path.join(local, "Riot Games", "Riot Client", "Data", "Crashes")),
        CacheTarget(path=os.path.join(local, "VALORANT", "saved", "Logs")),
        CacheTarget(path=os.path.join(local, "VALORANT", "saved", "Crashes")),
    ]
    categories.append(
        CleanupCategory(
            id="riot_games_logs",
            name="Riot Games & Valorant logs",
            group="Gaming",
            description="Diagnostic logs and crash dump traces for Riot Client and Valorant.",
            safety_level=SafetyLevel.SAFE,
            targets=riot_targets,
        )
    )

    # 7. Battle.net & Epic Games Launchers
    launcher_targets = [
        CacheTarget(path=os.path.join(program_data, "Battle.net", "Agent", "Cache")),
        CacheTarget(path=os.path.join(local, "Battle.net", "BrowserCache")),
        CacheTarget(path=os.path.join(local, "Battle.net", "Cache")),
        CacheTarget(path=os.path.join(local, "Battle.net", "Logs")),
        CacheTarget(path=os.path.join(local, "Epic Games Launcher", "Saved", "webcache")),
        CacheTarget(path=os.path.join(local, "Epic Games Launcher", "Saved", "Cache")),
        CacheTarget(path=os.path.join(local, "Epic Games Launcher", "Saved", "Logs")),
    ]
    categories.append(
        CleanupCategory(
            id="launcher_caches",
            name="Battle.net & Epic Games caches",
            group="Gaming",
            description="Caches and logs for Battle.net and Epic Games Launcher. Does not delete game installs or saves.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=launcher_targets,
        )
    )

    return categories
