# CrapCleaner

A fast, transparent cleanup and disk analysis utility built for power users, developers, and gamers, with Windows and Linux support from a single codebase.

[![Latest release](https://img.shields.io/github/v/release/PatrickJnr/crapcleaner?color=3b82f6)](https://github.com/PatrickJnr/crapcleaner/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/PatrickJnr/crapcleaner/total?color=10b981)](https://github.com/PatrickJnr/crapcleaner/releases)
[![CI](https://github.com/PatrickJnr/crapcleaner/actions/workflows/ci.yml/badge.svg)](https://github.com/PatrickJnr/crapcleaner/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-3b82f6.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-blue.svg)](#)
[![Lint & Format: Ruff](https://img.shields.io/badge/lint%20%26%20format-ruff-7f52ff.svg)](https://github.com/astral-sh/ruff)
[![Package Manager: uv](https://img.shields.io/badge/package%20manager-uv-de5fe9.svg)](https://github.com/astral-sh/uv)

### Download

**[Windows (.exe)](https://github.com/PatrickJnr/crapcleaner/releases/latest/download/CrapCleaner.exe)**  ·  **[Linux (x86_64)](https://github.com/PatrickJnr/crapcleaner/releases/latest/download/crapcleaner-linux-x86_64)**  ·  [All releases and checksums](https://github.com/PatrickJnr/crapcleaner/releases/latest)

Portable single files. Nothing to install, no account, no background service, and
nothing is sent anywhere. Every cleanup is previewed first and defaults to the
Recycle Bin, so a mistake is recoverable.

---

## Table of Contents
- [Overview](#overview)
- [Core Principles & Safety](#core-principles--safety)
- [Platform Support](#platform-support)
- [Screenshots](#screenshots)
- [Features](#features)
- [Installation](#installation)
- [Command Line Interface (CLI)](#command-line-interface-cli)
- [Development](#development)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

CrapCleaner is a local disk cleaner and storage analyzer for desktop systems. It targets temporary files, developer build caches, package manager stores, browser caches, and application caches while keeping critical project files, saved credentials, and user data intact. Windows-specific cleanup modules remain available on Windows builds, while Linux builds use Linux-appropriate paths from the same codebase.

---

## Core Principles & Safety

1. **Only Technical Defensible Cleanups**: Every cleanup target has a documented reason for existing and why deleting it is safe.
2. **Absolute Prohibition on Registry Cleaning**: In strict adherence to system stability principles, CrapCleaner **does not** clean, optimize, defrag, or repair the Windows Registry.
3. **Protected Paths Centralized Safety Layer**: Hard-coded safety rules guarantee that OS system files, user document roots, `.git` repositories, SSH keys, browser credentials, and game saves are never deleted.
4. **Links Are Never Followed**: scanning, preview, and cleanup all detach symlinks and Windows directory junctions instead of descending through them, so a link inside a cleanup target can never cause files outside that target to be reported as junk or deleted. Deleting a tree removes the link and leaves whatever it pointed at untouched.
5. **Reversible by Default**: Deletions are sent to the Windows Recycle Bin or Linux FreeDesktop Trash by default.
6. **Zero Telemetry**: No tracking, analytics, ads, or network telemetry. 100% local execution.

---

## Platform Support

CrapCleaner is one application that adapts to the operating system it is running on, rather than a Windows application with Linux support bolted on. Features that only one platform can provide are hidden on the other, and shared features use each platform's native tooling and vocabulary.

### Platform-aware architecture

A **capability registry** (`crapcleaner/system/capabilities.py`) is the single source of truth for what the running system supports and what each feature is called there. The GUI, the CLI, and the dispatchers all read from it, so no navigation code branches on the operating system.

Each system-management feature is a **platform-neutral dispatcher** over per-platform **backends**:

| Layer | Module | Responsibility |
|---|---|---|
| Registry | `system/capabilities.py` | Availability, labels, and per-platform vocabulary |
| Dispatcher | `system/startup.py`, `system/services.py`, `system/system_updates.py` | Shared models, caching, safety rules, routing |
| Backend | `system/backends/*_windows.py` | Registry, PowerShell/CIM, `sc.exe`, COM update session |
| Backend | `system/backends/*_linux.py` | XDG autostart, `systemctl`, `apt`/`dnf`/`pacman`/`zypper` |

Adding another operating system means adding backend modules plus one registry entry per capability. No caller changes.

Platform-specific dependencies stay inside their backend: `winreg`, PowerShell, and `sc.exe` appear only in `*_windows.py`; `systemctl`, `pkexec`, and package-manager commands appear only in `*_linux.py`. This is enforced by tests in `tests/test_platform_views.py`.

### Feature availability

| Feature | Windows | Linux |
|---|---|---|
| Cleanup categories, Storage Breakdown, Large Files, Duplicates, AI Data, Docker | Yes | Yes |
| PC Specs, Storage Health, Memory Cleaner | Yes | Yes |
| Startup Apps | Registry `Run`/`RunOnce` keys, Startup folders, `StartupApproved` flags | XDG autostart entries (`~/.config/autostart`, `/etc/xdg/autostart`) |
| Services | Windows services via CIM/PowerShell with an `sc.exe` fallback | systemd system and user units via `systemctl` |
| System Updates | Windows Update (`Microsoft.Update` COM), hotfix history | Distribution updates via `apt`, `dnf`/`yum`, `pacman`, or `zypper`, with reboot-required detection |
| App Updates | `winget`, `chocolatey` | `apt`, `flatpak`, `snap`, `pacman`, `dnf`/`yum` |
| Recycle Bin / Trash | Windows Recycle Bin | FreeDesktop Trash (`gio`, `trash-put`, or a built-in fallback) |

A feature whose tooling is missing is hidden rather than shown broken: on a Linux system without systemd, the *Services* page does not appear at all, and a navigation section whose entries are all unavailable is omitted entirely. Run `crapcleaner --capabilities` to see what the current system reports.

### Privilege escalation

Windows elevates the whole process through UAC. Linux elevates individual commands through `pkexec`, so the application does not need to run as root; when neither `pkexec` nor a non-interactive `sudo` is available, the action is refused with an explanation instead of hanging on a hidden password prompt.

Because system-wide XDG autostart entries live in root-owned `/etc/xdg/autostart` and belong to distribution packages, disabling or removing one writes a user-level override that hides it, which is the mechanism the XDG specification defines for exactly this case.

---

## Screenshots

<p align="center">
  <b>Storage Dashboard and Reclaimable Space Gauge</b><br>
  <img width="1262" alt="Storage Dashboard" src="https://github.com/user-attachments/assets/4f227648-df10-426d-9000-73ecec879afe" />
</p>

<p align="center">
  <b>Deep Cleanup Categories and Scan Inspection</b><br>
  <img width="1262" alt="Cleanup Categories" src="https://github.com/user-attachments/assets/bafe415b-6809-41f7-9e83-35a04bd9640b" />
</p>

<p align="center">
  <b>Audit History and Lifetime Analytics</b><br>
  <img width="1262" alt="Audit History and Analytics" src="https://github.com/user-attachments/assets/16942ba4-ebcb-4064-818c-a1695c80b876" />
</p>

---

## Features

### 1. Storage Dashboard, Live System Vitals & Quick-Access
- **Live System Telemetry Dashboard**: real-time network throughput (download/upload rates, session transfer totals, and active connection adapter), RAM load with dynamic high-memory pressure alerts and one-click Memory Cleaner access, real-time multi-core CPU utilization, GPU load, temperature, and VRAM consumption (NVIDIA through NVML, AMD and Intel through Linux DRM sysfs, and any Windows display adapter for name and VRAM size) - a metric the hardware does not expose is shown as `N/A` rather than as a zero, and live system uptime with fluid exponential moving average (EMA) smoothing and cubic eased animations.
- **Live Vitals Sparklines**: a rolling 60-sample history strip under the Memory, Processor, Graphics, and Network cards, fed from the Dashboard's existing vitals tick so no card runs a timer of its own.
- **Reclaimable Breakdown**: a proportional bar and the top categories by size, coloured by safety level. Before a first scan it lists the category groups a scan would check, so the panel is informative on a fresh install rather than blank.
- **Scan Insights & Space Recommendations**: interactive cleanup summary showing instant visual proportions of Safe vs Reviewable space, top storage-consuming categories, and actionable cleanup tips before execution.
- **Storage Analyzer Quick-Access Bookmarks**: one-click favorites bar in the Storage Breakdown view (Home, Downloads, Documents, AppData / .config, Temp, Videos) for instant directory navigation and inspection.
- Real-time disk capacity and reclaimable space calculation across all mounted drives.
- Storage Breakdown: proportional storage grid where each cell's area maps to its size, so the largest consumers stand out immediately. Drill into folders, navigate with the keyboard (arrows, Enter, Backspace), and hover for full paths; junction, symlink, and loop protection is preserved throughout, and a folder deeper than the analyzed depth is measured on demand when you navigate into it instead of forcing a slower whole-drive pass up front.
- Drive health, media type, and TRIM diagnostics are cached briefly and shared across views, so switching views does not re-run the underlying platform query.
- Storage Breakdown by functional file types (Videos, Images, Audio, Code, Archives, Documents, Executables, Databases, Disk Images).

### 2. Deep Cleanup Categories (75+ targets)
- **Windows System**: User and system TEMP directories, CBS servicing logs (`C:\Windows\Logs\CBS`), Delivery Optimization cache, Font Cache, Cryptnet SSL certificate cache, DirectX and GPU shader caches, and Prefetch traces.
- **Developer Tools**: VS Code, Cursor, Windsurf, Zed, JetBrains IDEs (IntelliJ, PyCharm, WebStorm, Rider, CLion), Android SDK build caches, Gradle daemon logs, Bun cache, Unity Editor caches & ShaderCache, Godot Engine caches, Unreal Engine DDC, CMake build packages, the shared sccache and Zig compiler caches, and the Docker Buildx cache (cleared through `docker buildx prune`, never by deleting files).
- **Project-local tool caches**: `.ruff_cache`, `.mypy_cache`, `.pytest_cache`, and `.tox` folders found inside the projects under your configured scan roots. Only these four names are ever collected, and only within those roots - no drive-wide sweep, and no project source is touched.
- **Package Managers**: npm, yarn, pnpm store, pip, uv, poetry, conda, NuGet, Cargo/Rust cache, Go build cache, Maven, WinGet, Chocolatey, and Scoop.
- **Gaming & Launchers**: Steam shader and depot caches, Epic Games Launcher, EA Desktop / Origin, Ubisoft Connect, Battle.net, GOG Galaxy, Riot Games / Valorant crash logs, and FiveM cache.
- **Browsers**: Chrome, Chromium, Edge, Brave, Opera, Opera GX, Vivaldi, Thorium, Arc, Firefox, LibreWolf, Waterfox, and Floorp HTTP/GPU/Code caches (leaving bookmarks, passwords, history, and active sessions intact). Running browsers are detected before a cleanup: you get a warning that locked files will be skipped, never a forced shutdown, and the report says exactly what was skipped.
- **Linux Package Managers**: APT, DNF, pacman, Flatpak, and Snap caches.

### 3. Recycle Bin & Trash Inspector
- Platform-native Recycle Bin inspection (Windows `SHQueryRecycleBinW` & Linux FreeDesktop Trash).
- View recoverable space, total items, and oldest/newest item timestamps.

### 4. Hardware Specifications & Storage Health
- Detailed PC Specs inspector detailing OS, CPU, Motherboard/BIOS, RAM slots, GPU, Network interfaces, and NVMe/SATA storage drives.
- **Hardware Specs Skeleton Loading**: Renders smooth, animated pulsing placeholder cards during async hardware and sensor queries.
- Physical drive detection (NVMe SSD, SATA SSD, HDD), bus type, filesystem, and capacity.
- TRIM support and enablement diagnostics (`fsutil` / `Get-PhysicalDisk` / `lsblk`).

### 5. Memory & Crash Dump Analyzer
- Identifies user-mode crash dumps (`%LOCALAPPDATA%\CrashDumps`), kernel minidumps (`C:\Windows\Minidump`), memory dumps, and core dumps with application attribution.

### 6. Old Installer Detector
- Scans user folders for potentially removable installers (`.msi`, `.exe`, `.iso`, `.deb`, `.rpm`, `.dmg`, `.pkg`).

### 7. Virtual Machine & Container Storage
- WSL2 VHDX virtual disk detection, Docker desktop storage metrics, and VM disk images (VirtualBox VDI, VMware VMDK, Hyper-V VHDX).

### 8. Multi-Stage Duplicate File Finder
- Three-stage identification pipeline: exact size matching -> 8 KB header hashing -> full SHA-256 validation.
- Smart duplicate resolution helpers: Keep Oldest, Keep Newest, Keep Shortest Path, and Keep First.

### 9. Pre-Cleanup Preview Engine
- Manifest generation displaying every candidate item, size, safety level, reversibility, and administrator requirement before execution.

### 10. Multi-Format Report Exporter
- Export storage breakdown, scan results, disk health diagnostics, and audit history to structured JSON, CSV, or TXT.

### 11. Memory Cleaner
- Overhauled view featuring a prominent top Hero usage gauge, dynamic memory pressure badges, and 2-column hardware vitals (Physical RAM 4-metric grid, Swap & GPU VRAM).
- Live RAM report: total, in use, available, utilization percentage, cached/standby memory, committed memory against the commit limit, coarse memory pressure, and swap / pagefile usage. Counters a platform does not expose are shown as *unknown*, never as zero.
- Graphics memory report per adapter: capacity, and live VRAM usage where the driver exposes it (NVIDIA via `nvidia-smi` and NVML, AMD on Linux via `amdgpu` sysfs). Adapters without a reliable counter are shown as *unknown*, never as zero.
- Multi-tier, explained reclamation actions. Only the actions the running kernel can perform are listed, and each one names the exact call that system will make:
  - **Flush all available memory** *(both)* - one-click sweep combining multi-pass process working set trimming, application heap release, and (if elevated) the standby cache purge on Windows or the filesystem cache drop on Linux.
  - **Flush process working sets** *(both)* - trims unused physical memory pages across active processes (`EmptyWorkingSet` on Windows, heap trim and page release on Linux), reclaiming 1–3+ GB of available physical RAM without closing any applications and without requiring administrator privileges.
  - **Release CrapCleaner's own memory** *(both)* - trims only this application's working set (`SetProcessWorkingSetSize` on Windows, `malloc_trim` on Linux).
  - **Purge the standby list** *(Windows only)* - a 5-stage kernel sweep purging modified page lists (`MemoryFlushModifiedList`), system working sets (`MemoryEmptyWorkingSets`), standby priority levels 0–7 (`MemoryPurgeStandbyList`), low-priority standby (`MemoryPurgeLowPriorityStandbyList`), and the system file cache (`SetSystemFileCacheSize`). Administrator required, with a 1-click elevation button.
  - **Drop the filesystem cache** *(Linux only)* - `sync` then `drop_caches`, filesystem cache only. Root required.
  - **Inspect graphics memory** *(both)* - read-only VRAM report covering adapter capacity and, where the driver exposes a reliable counter, live usage.
- Windows and Linux already manage memory automatically; this is optional maintenance, not an optimization. No process is ever terminated, no process priority is changed, no other application's memory is touched, and no GPU is reset. CrapCleaner does not claim that freeing RAM or VRAM improves FPS or system speed.
- **VRAM limitation, stated plainly**: graphics drivers expose no public API that lets a normal desktop application flush another application's VRAM. CrapCleaner therefore ships a VRAM *diagnostic* - capacity and, where available, live usage - and does not fake a flush. Closing the application that owns the memory is the only safe way to release it. Per-process VRAM attribution is not reported, because the driver interfaces that expose it omit graphics contexts and surface unrelated helper processes, which made the list misleading.
- **Windows privileges**: purging the standby list needs `SeProfileSingleProcessPrivilege`, which an elevated CrapCleaner normally holds. If Windows refuses it, the exact reason is reported (privilege missing from the token, token access failure, or lookup failure) rather than a generic "run as administrator".
- CrapCleaner contains **no registry cleaning, registry optimization, or registry defragmentation** - neither here nor anywhere else in the application.

### 12. Startup Applications Manager
- Inspects everything configured to run at login and reports its location, enabled state, inferred publisher, resolved executable, whether that executable still exists, and an estimated boot impact.
- **Windows**: Current User and All Users `Run`/`RunOnce` registry keys (including the 32-bit view), the user and All Users Startup folders, and the `StartupApproved` flags that Task Manager writes, so toggling an entry here matches what the built-in Startup tab shows.
- **Linux**: XDG autostart entries from `~/.config/autostart` and `/etc/xdg/autostart`. A user entry shadows the packaged entry of the same name, as the specification requires.
- Enable, disable, remove, and add entries. On Linux, disabling or removing a packaged entry in root-owned `/etc/xdg/autostart` writes a user-level override that hides it rather than deleting a file the package manager owns.

### 13. Services Manager
- **Windows**: every Windows service with its status, startup type, description, log-on account, and process id, queried through CIM/PowerShell with an `sc.exe` fallback. Start, stop, restart, and set Automatic, Automatic (Delayed Start), Manual, or Disabled.
- **Linux**: systemd system and user units with their active state and unit-file state, driven through `systemctl`. Start, stop, restart, and set Automatic, Manual, or Disabled - where Disabled masks the unit, which is what actually prevents it from being started.
- Critical components are protected from being stopped or disabled: `RPCSS`, `DcomLaunch`, `PlugPlay` and friends on Windows; `dbus`, `systemd-logind`, `polkit`, `user@`, and `getty@` on Linux.
- Search across name, display name, description, and account, with status, startup type, and system/third-party filters. Startup types offered always match the platform, so no delayed-start mode is shown for systemd.

### 14. System Updates
- **Windows**: pending updates via the `Microsoft.Update` COM API, with titles, KB IDs, MSRC severity, download state, package size, and support URLs, plus the full installed hotfix history. Installation is initiated with administrator elevation enforced, falling back to the Windows Update Orchestrator when the COM session is refused.
- **Linux**: distribution, kernel, and security updates from `apt`, `dnf`/`yum`, `pacman`, or `zypper`, with security errata marked, recent package history read from the package manager's own log, and reboot-required detection.
- Raw `0x8024xxxx` Windows Update failure codes are translated into a plain-language title and remediation hint instead of being shown as a bare hexadecimal code.

### 15. App Updates
- Detects the package managers installed on the current system and reports every available application upgrade in one place.
- **Windows**: `winget` and `chocolatey`. **Linux**: `apt`/`apt-get`, `flatpak`, `snap`, `pacman`, and `dnf`/`yum`.
- Live search, per-manager filtering, and upgrades run one package at a time, across a multi-row selection, or across an entire manager. A queued selection continues past any package that fails.
- Installers are allowed 30 minutes for a single package and 2 hours for a whole-manager upgrade, because a half-installed package is worse than a slow one.

### 16. Custom Theme Studio & Built-in Themes Gallery (43+ Palettes)
- **Dedicated Custom Theme Studio**: A creative workspace inside Preferences for designing, fine-tuning, and instantly applying custom themes without manual configuration of dozens of hex codes.
  - **Perceptual Color Theory Engine (`color_engine.py`)**: Features hue-dependent brightness bias compensation (`hue_lightness_bias`) and perceptual lightness tuning, ensuring high-luminance hues (amber, yellow, lime) avoid blinding glare while deep blues and violets maintain rich vibrancy.
  - **6 Palette Harmony Mood Styles**: Choose between *Cohesive* (balanced surface tinting with 14% saturation), *Vibrant* (high-energy saturated surfaces and neon accents), *Muted* (subdued slate undertones), *OLED Pure* (true `#000000` deep black canvas), *Pastel* (soft, airy gentle tones), and *Minimal* (clean monochromatic neutral greys with single accent focus).
  - **15 Curated Designer Presets**: Instant one-click palettes (*Sapphire Blue, Emerald Forest, Cyber Violet, Sunset Amber, Crimson Velvet, Rose Gold, Hyper Cyan, Deep Slate, Mint Sage, Solar Orange, Royal Indigo, Cherry Blossom, Arctic Frost, Matrix Lime, Espresso Gold*).
  - **Multi-View Interactive Live Preview**: Switch between Overview Mockup, Clean-up Candidate Table, and 27-Token Palette Matrix with a real-time WCAG 2.1 contrast ratio rating meter (`AAA`, `AA`, `LOW`).
  - **Harmonies, Magic Dice & JSON Sharing**: Automatic generation of Analogous, Complementary, Triadic, and Split-Complementary palettes, a "Surprise Me (Magic Dice)" one-click randomizer, and seamless theme JSON export/import.
  - **Real-Time Live Application**: Color picker choices, hex typing, slider tweaks, and mood switches update the live app instantly.
- **43 Built-in Curated Themes** across 6 distinct categories: *Modern Dark* (Dark, Adwaita Dark, OLED Black, Midnight Blue, Slate, Graphite, High Contrast), *Light & Pastel* (Light, Adwaita Light, Arctic Light, Bubblegum Pop, Parchment), *Retro & Vintage* (Windows 95, Commodore 64, Game Boy, Amber CRT, Matrix Terminal, Vault 1950s, Analog VHS, Pulp '70s), *Cyber & Synth* (Cyberpunk Neon, Synthwave Outrun, Vaporwave '90s, Solar Eclipse), *Code Palettes* (Dracula, Monokai Pro, Tokyo Night, Nord, Gruvbox, One Dark Pro, Catppuccin Mocha, Solarized Dark), and *Warm & Nature* (Forest, Matcha Tea, Sunset Orange, Desert Dune, Espresso Roast, Coffee, Sakura Blossom, Lavender Dream, Crimson Velvet, Ocean Deep, Facility Orange).
- **Interactive Theme Gallery**: Real-time 5-color swatch bars, active hero card with direct "Custom Studio" shortcut, search filtering, dynamic category count chips, "Surprise Me" randomizer, and default reset.
- **OLED Black** uses true black (`#000000`) backgrounds with near-black panels so OLED panels can switch pixels off, while keeping text, borders, and disabled states readable.
- Themes apply instantly and cross-fade smoothly; a *Reduce motion* preference disables the transition.
- Pure Google Material Icons integrated with dynamic theme color adaptation (zero unicode emojis).

### 17. Linux Storage Handling
- Mount points are shown with descriptive names (*System Root (/)*, *Home*, *Mounted Volume*, *External Drive*) alongside their real paths.
- The drive list covers real user storage (`/`, `/home`, `/mnt`, `/media`, `/srv`, `/var/home`) and hides pseudo, container, and boot mounts; aliases of the same device collapse into one entry.
- Storage scans skip `/proc`, `/sys`, `/dev`, `/run`, and container storage roots.
- Deletions fall back to a FreeDesktop-compliant `~/.local/share/Trash` implementation when `gio` and `trash-put` are unavailable, so choosing the Recycle Bin never silently means permanent deletion.

### 18. Preferences & Configuration
- Segmented sub-tabbed settings view for *Theme Gallery*, *Custom Theme Studio*, *Safety & Protection*, *Exclusions & Roots*, *Scan Performance*, *Category Rules*, and *Backup & Sync*.
- Preferences, custom theme configuration, window geometry, cleanup category selections, exclusions, and scan options are stored locally in `config.json` under the platform config directory.
- The config file is versioned, so future releases can migrate older files; unknown, malformed, or wrongly typed entries fall back to defaults instead of preventing startup.
- Full JSON export, import, and factory reset support for settings migration.

### 19. Help, Safety Philosophy & Technical Documentation
- **Dedicated Modal Dialog**: comprehensive 9-part interactive documentation guide (`HelpSafetyDialog`) covering core design principles, technical justification for omitting registry cleaners, performance and placebo disclaimers, protected paths safety architecture (`.git`, SSH keys, credentials, user document folders), and regeneration behavior of temporary files.
- Features real-time FAQ search, category filter chips, and a one-click **Copy System Diagnostics** button for bug reporting.
- Accessible globally via `F1`, the sidebar "Safety First" footer card, and the About view.

---

## Installation

### Option 1: Download Pre-compiled Binary (Recommended)

Download the latest standalone executable from the [GitHub Releases](https://github.com/PatrickJnr/crapcleaner/releases/latest) page:

- **Windows (64-bit)**: [`CrapCleaner.exe`](https://github.com/PatrickJnr/crapcleaner/releases/latest/download/CrapCleaner.exe) - portable binary, no Python or installation required.
- **Linux (64-bit)**: [`crapcleaner-linux-x86_64`](https://github.com/PatrickJnr/crapcleaner/releases/latest/download/crapcleaner-linux-x86_64) - ELF executable built against glibc 2.35 (Ubuntu 22.04), so it also runs on newer Debian, Fedora, and Arch installs. Mark it executable with `chmod +x` after downloading.

Every release ships a `checksums.txt` with SHA-256 sums for all binaries. The Windows
build is not code-signed, so SmartScreen will warn on first run.

### Option 2: Run via Astral uv / pip

```bash
git clone https://github.com/PatrickJnr/crapcleaner.git
cd crapcleaner

# Option A: Run directly with uv (fastest)
./scripts/runuv.sh

# Option B: Run manually with uv
uv venv
uv pip install -e .
uv run crapcleaner --gui

# Option C: Run with standard pip
python3 -m venv .venv
# Activate .venv
pip install -e .
crapcleaner --gui
```

---

## Command Line Interface (CLI)

```bash
# Launch the graphical interface
crapcleaner --gui

# Scan for reclaimable space
crapcleaner --scan

# Output machine-readable JSON
crapcleaner --scan --json

# Display pre-cleanup preview manifest
crapcleaner --cleanup-preview

# Inspect Recycle Bin / Trash storage
crapcleaner --recycle-bin

# Inspect physical storage device health and TRIM status
crapcleaner --disk-health

# Hierarchical storage breakdown of user profile or specific path
crapcleaner --storage C:\Users\Username

# Analyze storage by file type
crapcleaner --file-types C:\Users\Username

# Detect old installers in Downloads and User folders
crapcleaner --installers

# Report RAM, swap/pagefile, and graphics memory (add --json for machine-readable output)
crapcleaner --memory
```

```bash
# Report which platform features this operating system supports
crapcleaner --capabilities

# List startup entries (registry Run keys on Windows, XDG autostart on Linux)
crapcleaner --startup

# List services (Windows services, or systemd units on Linux)
crapcleaner --services

# Check for operating-system updates (Windows Update, or the distro package manager)
crapcleaner --system-updates

# --windows-updates remains accepted as an alias for --system-updates
```

Every command above accepts `--json`. When a feature is unavailable on the running
system, the command prints the reason and exits non-zero rather than failing partway
through a platform command.

```bash
# List the memory actions this system supports
crapcleaner --memory-clean list

# Run a memory action (dry run by default; add --execute to perform it)
crapcleaner --memory-clean working_set --execute

# List active protected filesystem rules and safety layer
crapcleaner --protected-paths

# Export report to JSON, CSV, or TXT
crapcleaner --scan --export csv --output scan_report.csv
crapcleaner --disk-health --export json --output health.json
crapcleaner --storage --export txt --output storage.txt

# Perform dry-run cleanup of safe categories
crapcleaner --clean-safe --dry-run

# Execute cleanup of safe categories with Recycle Bin protection
crapcleaner --clean-safe --execute

# Find duplicates larger than 10MB
crapcleaner --duplicates "C:\Users\Username\Downloads" --min-dup-size 10MB

# Stream progress as JSONL/NDJSON for CI or an external frontend
crapcleaner --scan --progress-jsonl
crapcleaner --clean-safe --execute --yes --progress-jsonl

# Hardware and OS specifications
crapcleaner --specs
```

### Streaming progress (`--progress-jsonl`)

`--progress-jsonl` turns `--scan` and the cleanup commands into a JSONL/NDJSON
stream: one standalone JSON object per line on stdout, with no human-readable
text mixed in. Without the flag nothing about the normal output changes.

| Event | Emitted when |
| --- | --- |
| `scan_start` / `cleanup_start` | the run begins, with the category count |
| `scan_progress` / `cleanup_progress` | a category starts or finishes |
| `category_result` / `cleanup_result` | per-category totals |
| `warning` | a locked file, a permission failure, or a running browser |
| `error` | a category-level failure |
| `cancelled` | the run was interrupted |
| `scan_complete` / `cleanup_complete` | totals; cleanups also report `partial` |

Every object carries `event` and a `time` timestamp. A cleanup that could not
remove everything reports `partial: true` and lists what was skipped - a
cleanup is never reported as complete when locked files remain.

---

## Development

### Run locally

#### Using `uv` (Fastest)

```sh
# Automated bootstrap and run:
./scripts/runuv.sh

# Or manually:
uv venv
uv pip install -r requirements-dev.txt
uv pip install -e .
uv run python -m crapcleaner
```

#### Using standard `pip` / `venv`

```sh
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements-dev.txt
./.venv/bin/python -m pip install -e .
./.venv/bin/python -m crapcleaner
```

### Build Standalone Executables

```sh
# Fast PyInstaller build using Astral uv:
./scripts/builduv.sh

# Windows (Batch script):
scripts\build_windows.bat

# Linux (Shell script):
scripts/build_linux.sh
```

### Test

```sh
# With uv:
uv run pytest -q

# With standard pytest in active environment:
pytest -q
```

### Lint and format

```sh
# With uv:
uv run ruff check crapcleaner tests scripts
uv run ruff format --check crapcleaner tests scripts

# Or directly with ruff:
ruff check crapcleaner tests scripts
ruff format --check crapcleaner tests scripts
```

---

## Keyboard Shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+1` ... `Ctrl+9`, `Ctrl+0` | Jump to one of the first ten sidebar views, in rail order: Dashboard, Cleanup, Storage Breakdown, Large Files, Duplicates, AI Data, Docker, PC Specs, Memory Cleaner, Startup Apps. Later views are reached from the rail; they are deliberately left unbound rather than wrapping round and making `Ctrl+1` ambiguous |
| `F1` | Open the Help, Safety Philosophy & Technical Documentation modal dialog |
| `Ctrl+R` | Start a scan |
| `F5` | Refresh the active view |
| `Ctrl+F` | Focus the search box in views that have one |
| `Esc` | Cancel the running scan |

---

## Project Structure

```
crapcleaner/
  app.py            Entry point that dispatches to the GUI or the CLI
  cli.py            Command line interface
  registry.py       Assembles cleanup categories from every provider
  config.py         Settings load/save and config directory resolution
  history.py        Local cleanup audit log
  reports.py        JSON / CSV / TXT report exporter
  constants.py      Shared constants
  categories/       Cleanup category providers (windows, browsers, gaming, ...)
  core/             Scan and cleanup engine, safety rules, scheduler
  analysis/         Storage breakdown, duplicates, large files, recycle bin, crash dumps
  system/           Hardware specs, disk health, memory, startup, services, updates
    capabilities.py   Platform capability registry: availability and per-OS wording
    startup.py        Startup manager dispatcher (shared model and heuristics)
    services.py       Service manager dispatcher (shared model, cache, safety rules)
    system_updates.py OS update dispatcher (shared report model)
    package_managers.py  Cross-platform application update scanning
    backends/         Per-OS implementations, one module per platform and capability
  gui/              PySide6 interface (views, theme, icons, workers)
    effects.py        Shared visual toolkit: animated values, sparklines,
                      segmented bars, hover depth and accent glow
  models/           Dataclasses for categories, scan results, and reports
  utils/            Platform helpers, safe file operations, formatting, updater
  assets/           Bundled fonts and images
scripts/            Build scripts, run helpers, and PyInstaller launcher
  builduv.sh        Build standalone executable using Astral uv
  runuv.sh          Setup environment and run application using Astral uv
  build_windows.bat Build standalone Windows executable via PyInstaller
  build_linux.sh    Build standalone Linux binary via PyInstaller
  launcher.py       PyInstaller launcher entry point
  extract_changelog.py  Extract version release notes from CHANGELOG.md
tests/              Test suite
```

Category providers expose a `get_categories()` function and are wired together in `crapcleaner/registry.py`.

Platform-specific code belongs in `crapcleaner/system/backends/`. To support a feature on another operating system, add a backend module exposing that capability's functions and one entry per capability in `crapcleaner/system/capabilities.py`; the dispatchers, the navigation rail, and the CLI pick it up without further changes.

---

## Contributing

1. Fork the repository on GitHub.
2. Create a feature branch: `git checkout -b feature/new-cleanup-category`.
3. Ensure all tests pass: `pytest`.
4. Commit your changes: `git commit -m "Add new category"`.
5. Open a Pull Request.

---

## License

This project is licensed under the [MIT License](LICENSE).
