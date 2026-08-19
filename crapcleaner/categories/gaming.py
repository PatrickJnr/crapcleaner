"""Gaming cleanup categories (Steam, Epic Games, EA, Ubisoft, Riot, Battle.net, GOG Galaxy, DirectX Shaders).

Provides targeted cleanup of game launcher web caches, incomplete download staging,
and graphics shader caches while strictly preserving game installations, save files,
configuration files, and mods.
"""

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
            what_it_contains="CEF browser caches, download staging chunks, and client logs.",
            why_it_grows="Steam stores web assets for the store and community tabs and stages game download chunks.",
            why_safe_to_delete="Never touches game installations, cloud saves, or user screenshots.",
            regeneration_behavior="Steam regenerates UI caches on launch; pending downloads can be resumed.",
            reversible=True,
            targets=steam_targets,
        )
    )

    # 3. Epic Games Launcher Caches
    epic_targets = [
        CacheTarget(path=os.path.join(local, "Epic Games Launcher", "Saved", "webcache")),
        CacheTarget(path=os.path.join(local, "Epic Games Launcher", "Saved", "Cache")),
        CacheTarget(path=os.path.join(local, "Epic Games Launcher", "Saved", "Logs")),
        CacheTarget(path=os.path.join(program_data, "Epic", "EpicGamesLauncher", "Data", "EMS")),
    ]
    categories.append(
        CleanupCategory(
            id="epic_games_cache",
            name="Epic Games Launcher caches",
            group="Gaming",
            description="Web browser caches, patch staging, and logs for Epic Games Launcher.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="Web engine caches and launcher diagnostics.",
            why_it_grows="The Epic store runs an embedded browser that accumulates web caches.",
            why_safe_to_delete="Game installations, save files, and cloud sync metadata are protected.",
            regeneration_behavior="Launcher rebuilds web cache on startup.",
            reversible=True,
            targets=epic_targets,
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
            what_it_contains="Store browser caches and launcher telemetry logs.",
            why_it_grows="EA App caches store pages, promotional banners, and session logs.",
            why_safe_to_delete="Game files and local save data are untouched.",
            regeneration_behavior="EA App fetches fresh store assets on next open.",
            reversible=True,
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
            what_it_contains="Embedded browser cache and diagnostic logs for Ubisoft Connect.",
            why_it_grows="Stores cache data for game news, store, and overlay.",
            why_safe_to_delete="Installed Ubisoft games and cloud save data are unaffected.",
            regeneration_behavior="Rebuilt when launching Ubisoft Connect.",
            reversible=True,
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
            description="Diagnostic logs and crash dump traces for Riot Client, League of Legends, and Valorant.",
            safety_level=SafetyLevel.SAFE,
            what_it_contains="Text log files and minidump crash packages.",
            why_it_grows="Riot Client and Vanguard write verbose logs during matches.",
            why_safe_to_delete="Logs have no gameplay function.",
            regeneration_behavior="New logs created during subsequent matches.",
            reversible=True,
            targets=riot_targets,
        )
    )

    # 7. Battle.net Launcher Caches
    bnet_targets = [
        CacheTarget(path=os.path.join(program_data, "Battle.net", "Agent", "Cache")),
        CacheTarget(path=os.path.join(local, "Battle.net", "BrowserCache")),
        CacheTarget(path=os.path.join(local, "Battle.net", "Cache")),
        CacheTarget(path=os.path.join(local, "Battle.net", "Logs")),
        CacheTarget(path=os.path.join(local, "Blizzard Entertainment", "Battle.net", "Cache")),
    ]
    categories.append(
        CleanupCategory(
            id="battle_net_cache",
            name="Battle.net launcher caches",
            group="Gaming",
            description="Browser caches, agent update caches, and logs for Blizzard Battle.net.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="Battle.net Agent patch metadata and Chromium web caches.",
            why_it_grows="Stores web content for the Battle.net news and game launcher tabs.",
            why_safe_to_delete="Does not delete game installs or user account data.",
            regeneration_behavior="Rebuilt during Battle.net launch.",
            reversible=True,
            targets=bnet_targets,
        )
    )

    # 8. GOG Galaxy Caches
    gog_targets = [
        CacheTarget(path=os.path.join(program_data, "GOG.com", "Galaxy", "webcache")),
        CacheTarget(path=os.path.join(program_data, "GOG.com", "Galaxy", "logs")),
        CacheTarget(path=os.path.join(local, "GOG.com", "Galaxy", "Configuration", "crashdumps")),
    ]
    categories.append(
        CleanupCategory(
            id="gog_galaxy_cache",
            name="GOG Galaxy caches",
            group="Gaming",
            description="Web browser caches, crash reports, and logs for GOG Galaxy.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="GOG store web cache and client logs.",
            why_it_grows="Galaxy stores store web assets and communication logs.",
            why_safe_to_delete="Installed GOG games and cloud saves are completely protected.",
            regeneration_behavior="Rebuilt automatically upon next GOG Galaxy startup.",
            reversible=True,
            targets=gog_targets,
        )
    )

    # 9. FiveM Caches
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
            what_it_contains="Downloaded server streaming assets and temporary GTA game data.",
            why_it_grows="Connecting to FiveM custom servers downloads texture and script caches.",
            why_safe_to_delete="Server resources will be re-downloaded when joining servers.",
            regeneration_behavior="Cached on next server connection.",
            reversible=True,
            targets=fivem_targets,
        )
    )

    return categories
