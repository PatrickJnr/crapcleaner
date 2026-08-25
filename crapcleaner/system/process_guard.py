"""Running process detection and active application warnings for cleanup categories.

Identifies active applications (browsers, IDEs, communication tools, game launchers,
and AI apps) whose caches or logs may be locked during cleanup, warning the user
before execution without ever forcefully killing processes.
"""

import os
from collections.abc import Iterable

from crapcleaner.utils.platform import is_linux, is_windows, run_command

# Maps application key -> (Windows process name, Linux process name, Display name, category prefixes)
APP_DEFINITIONS: dict[str, tuple[str, str, str, list[str]]] = {
    # Browsers
    "chrome": ("chrome.exe", "chrome", "Google Chrome", ["chrome", "google_chrome"]),
    "chromium": ("chromium.exe", "chromium", "Chromium", ["chromium"]),
    "edge": ("msedge.exe", "msedge", "Microsoft Edge", ["edge", "msedge"]),
    "brave": ("brave.exe", "brave", "Brave Browser", ["brave"]),
    "opera": ("opera.exe", "opera", "Opera", ["opera"]),
    "operagx": ("opera.exe", "opera", "Opera GX", ["operagx"]),
    "vivaldi": ("vivaldi.exe", "vivaldi", "Vivaldi", ["vivaldi"]),
    "thorium": ("thorium.exe", "thorium", "Thorium", ["thorium"]),
    "arc": ("Arc.exe", "arc", "Arc", ["arc"]),
    "firefox": ("firefox.exe", "firefox", "Mozilla Firefox", ["firefox", "mozilla"]),
    "librewolf": ("librewolf.exe", "librewolf", "LibreWolf", ["librewolf"]),
    "waterfox": ("waterfox.exe", "waterfox", "Waterfox", ["waterfox"]),
    "floorp": ("floorp.exe", "floorp", "Floorp", ["floorp"]),
    "zen": ("zen.exe", "zen", "Zen Browser", ["zen"]),
    # Developer IDEs & Tools
    "vscode": ("code.exe", "code", "VS Code", ["vscode", "code"]),
    "vscode_insiders": (
        "code - insiders.exe",
        "code-insiders",
        "VS Code Insiders",
        ["vscode_insiders"],
    ),
    "cursor": ("cursor.exe", "cursor", "Cursor", ["cursor"]),
    "windsurf": ("windsurf.exe", "windsurf", "Windsurf", ["windsurf"]),
    "kiro": ("kiro.exe", "kiro", "Kiro", ["kiro"]),
    "claude_desktop": ("claude.exe", "claude", "Claude Desktop", ["claude_desktop", "claude"]),
    "github_desktop": ("githubdesktop.exe", "github-desktop", "GitHub Desktop", ["github_desktop"]),
    "zed": ("zed.exe", "zed", "Zed", ["zed"]),
    "android_studio": (
        "studio64.exe",
        "studio",
        "Android Studio",
        ["android_gradle_daemon", "android_studio"],
    ),
    "jetbrains": ("idea64.exe", "idea", "JetBrains IDEs", ["jetbrains_caches", "jetbrains"]),
    # Communication & Media
    "discord": ("discord.exe", "discord", "Discord", ["discord_cache", "discord"]),
    "slack": ("slack.exe", "slack", "Slack", ["slack_cache", "slack"]),
    "spotify": ("spotify.exe", "spotify", "Spotify", ["spotify_cache", "spotify"]),
    # Gaming & Launchers
    "steam": ("steam.exe", "steam", "Steam", ["steam_caches", "steam_caches_linux", "steam"]),
    "heroic": ("heroic.exe", "heroic", "Heroic Games Launcher", ["heroic_cache_linux", "heroic"]),
    "lutris": ("lutris.exe", "lutris", "Lutris", ["lutris_bottles_cache_linux", "lutris"]),
    "epic": (
        "epicgameslauncher.exe",
        "epicgameslauncher",
        "Epic Games Launcher",
        ["launcher_caches", "epic"],
    ),
    # AI Apps
    "lmstudio": ("lm studio.exe", "lm-studio", "LM Studio", ["ai_app_cache", "lmstudio"]),
    "jan": ("jan.exe", "jan", "Jan.ai", ["ai_app_cache", "jan"]),
    "ollama": ("ollama.exe", "ollama", "Ollama", ["ai_models", "ollama"]),
}


def get_running_process_snapshot() -> str:
    """Take a single snapshot of running process names on the system in lowercase."""
    if is_windows():
        res = run_command(["tasklist", "/FO", "CSV", "/NH"], timeout=8.0)
    elif is_linux():
        res = run_command(["ps", "-eo", "comm="], timeout=8.0)
    else:
        return ""
    if res.get("returncode") != 0:
        return ""
    return str(res.get("stdout", "")).lower()


def process_names(snapshot: str) -> set[str]:
    """The distinct process names in a snapshot.

    Substring-matching the raw text made every short name a trap: `zen` matches
    `zenity`, `arc` matches `arch`, `jan` matches any `janitor`.
    """
    names: set[str] = set()
    for line in snapshot.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('"'):
            # tasklist /FO CSV: "image name","pid","session",...
            line = line.split('","', 1)[0].strip('"')
        name = os.path.basename(line).strip()
        if name:
            names.add(name)
    return names


def running_processes_for_categories(
    category_ids: Iterable[str], process_snapshot: str | None = None
) -> list[str]:
    """Return display names of running processes corresponding to the given cleanup category IDs."""
    cat_id_set = set(category_ids)
    if not cat_id_set:
        return []

    snapshot = process_snapshot if process_snapshot is not None else get_running_process_snapshot()
    if not snapshot:
        return []

    present = process_names(snapshot)
    running_apps: list[str] = []
    seen_names: set[str] = set()

    for app_key, (win_proc, linux_proc, display_name, prefixes) in APP_DEFINITIONS.items():
        # Check if this app matches any of the requested category IDs
        matches_category = any(
            cid == app_key
            or cid.startswith(f"{app_key}_")
            or any(cid == p or cid.startswith(f"{p}_") for p in prefixes)
            for cid in cat_id_set
        )
        if not matches_category:
            continue

        target_proc = win_proc.lower() if is_windows() else linux_proc.lower()
        if target_proc in present:
            if display_name not in seen_names:
                seen_names.add(display_name)
                running_apps.append(display_name)

    return running_apps
