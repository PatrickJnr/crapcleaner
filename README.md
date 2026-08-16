# CrapCleaner

A fast, transparent cleanup and disk analysis utility built for power users, developers, and gamers, with Windows and Linux support from a single codebase.

[![CI](https://github.com/PatrickJnr/crapcleaner/actions/workflows/ci.yml/badge.svg)](https://github.com/PatrickJnr/crapcleaner/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-3b82f6.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-blue.svg)](#)
[![Lint & Format: Ruff](https://img.shields.io/badge/lint%20%26%20format-ruff-7f52ff.svg)](https://github.com/astral-sh/ruff)

---

## Table of Contents
- [Overview](#overview)
- [Core Principles & Safety](#core-principles--safety)
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
4. **Reversible by Default**: Deletions are sent to the Windows Recycle Bin or Linux FreeDesktop Trash by default.
5. **Zero Telemetry**: No tracking, analytics, ads, or network telemetry. 100% local execution.

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
- **Live System Telemetry Dashboard**: real-time network throughput (download/upload rates, session transfer totals, and active connection adapter), RAM load with dynamic high-memory pressure alerts and one-click Memory Cleaner access, real-time multi-core CPU utilization, GPU temperature monitoring & VRAM consumption (NVIDIA NVML & Linux DRM), and live system uptime with fluid exponential moving average (EMA) smoothing and cubic eased animations.
- **Scan Insights & Space Recommendations**: interactive cleanup summary showing instant visual proportions of Safe vs Reviewable space, top storage-consuming categories, and actionable cleanup tips before execution.
- **Storage Analyzer Quick-Access Bookmarks**: one-click favorites bar in the Storage Breakdown view (Home, Downloads, Documents, AppData / .config, Temp, Videos) for instant directory navigation and inspection.
- Real-time disk capacity and reclaimable space calculation across all mounted drives.
- Storage Breakdown: proportional storage grid where each cell's area maps to its size, so the largest consumers stand out immediately. Drill into folders, navigate with the keyboard (arrows, Enter, Backspace), and hover for full paths; junction, symlink, and loop protection is preserved throughout.
- Drive health, media type, and TRIM diagnostics are cached briefly and shared across views, so switching views does not re-run the underlying platform query.
- Storage Breakdown by functional file types (Videos, Images, Audio, Code, Archives, Documents, Executables, Databases, Disk Images).

### 2. Deep Cleanup Categories (75+ targets)
- **Windows System**: User and system TEMP directories, CBS servicing logs (`C:\Windows\Logs\CBS`), Delivery Optimization cache, Font Cache, Cryptnet SSL certificate cache, DirectX and GPU shader caches, and Prefetch traces.
- **Developer Tools**: VS Code, Cursor, Windsurf, Zed, JetBrains IDEs (IntelliJ, PyCharm, WebStorm, Rider, CLion), Android SDK build caches, Gradle daemon logs, Bun cache, Unity Editor caches & ShaderCache, Godot Engine caches, Unreal Engine DDC, and CMake build packages.
- **Package Managers**: npm, yarn, pnpm store, pip, uv, poetry, conda, NuGet, Cargo/Rust cache, Go build cache, Maven, WinGet, Chocolatey, and Scoop.
- **Gaming & Launchers**: Steam shader and depot caches, Epic Games Launcher, EA Desktop / Origin, Ubisoft Connect, Battle.net, GOG Galaxy, Riot Games / Valorant crash logs, and FiveM cache.
- **Browsers**: Chrome, Edge, Brave, Opera, Opera GX, Vivaldi, Arc, Firefox, LibreWolf, Waterfox, and Floorp HTTP/GPU/Code caches (leaving bookmarks, passwords, history, and active sessions intact).
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
- Multi-tier, explained reclamation actions:
  - **Quick Flush Memory** - fast one-click memory optimizer combining multi-pass process working set trimming, application heap release, and (if elevated) standby cache purge.
  - **Flush process working sets** - trims unused physical memory pages across active processes (`EmptyWorkingSet` and `SetProcessWorkingSetSize`), reclaiming 1–3+ GB of available physical RAM without closing any applications and without requiring administrator privileges.
  - **Release CrapCleaner's own memory** - trims only this application's working set (Windows) or heap (Linux `malloc_trim`).
  - **Purge the Windows standby list** - executes a 5-stage kernel sweep purging modified page lists (`MemoryFlushModifiedList`), system working sets (`MemoryEmptyWorkingSets`), standby priority levels 0–7 (`MemoryPurgeStandbyList`), low-priority standby (`MemoryPurgeLowPriorityStandbyList`), and Windows system file cache (`SetSystemFileCacheSize`) (administrator required, with 1-click elevation button).
  - **Drop the Linux filesystem cache** - `sync` + `drop_caches`, filesystem cache only (root required).
  - **Inspect graphics memory** - read-only VRAM report covering adapter capacity and, where the driver exposes a reliable counter, live usage.
- Windows and Linux already manage memory automatically; this is optional maintenance, not an optimization. No process is ever terminated, no process priority is changed, no other application's memory is touched, and no GPU is reset. CrapCleaner does not claim that freeing RAM or VRAM improves FPS or system speed.
- **VRAM limitation, stated plainly**: graphics drivers expose no public API that lets a normal desktop application flush another application's VRAM. CrapCleaner therefore ships a VRAM *diagnostic* - capacity and, where available, live usage - and does not fake a flush. Closing the application that owns the memory is the only safe way to release it. Per-process VRAM attribution is not reported, because the driver interfaces that expose it omit graphics contexts and surface unrelated helper processes, which made the list misleading.
- **Windows privileges**: purging the standby list needs `SeProfileSingleProcessPrivilege`, which an elevated CrapCleaner normally holds. If Windows refuses it, the exact reason is reported (privilege missing from the token, token access failure, or lookup failure) rather than a generic "run as administrator".
- CrapCleaner contains **no registry cleaning, registry optimization, or registry defragmentation** - neither here nor anywhere else in the application.

### 12. Visual Theme Gallery & Themes (41 Palettes)
- **41 built-in curated themes** across 6 distinct categories: *Modern Dark* (Dark, OLED Black, Midnight Blue, Slate, Graphite, High Contrast), *Light & Pastel* (Light, Arctic Light, Bubblegum Pop, Parchment), *Retro & Vintage* (Windows 95, Commodore 64, Game Boy, Amber CRT, Matrix Terminal, Vault 1950s, Analog VHS, Pulp '70s), *Cyber & Synth* (Cyberpunk Neon, Synthwave Outrun, Vaporwave '90s, Solar Eclipse), *Code Palettes* (Dracula, Monokai Pro, Tokyo Night, Nord, Gruvbox, One Dark Pro, Catppuccin Mocha, Solarized Dark), and *Warm & Nature* (Forest, Matcha Tea, Sunset Orange, Desert Dune, Espresso Roast, Coffee, Sakura Blossom, Lavender Dream, Crimson Velvet, Ocean Deep, Facility Orange).
- **Interactive Theme Gallery**: Real-time 5-color swatch bars, active hero card, search filtering, category chips, "Surprise Me" randomizer, and default reset.
- **OLED Black** uses true black (`#000000`) backgrounds with near-black panels so OLED panels can switch pixels off, while keeping text, borders, and disabled states readable.
- Themes apply instantly and cross-fade smoothly; a *Reduce motion* preference disables the transition.
- Pure Google Material Icons integrated with dynamic theme color adaptation (zero unicode emojis).

### 13. Linux Storage Handling
- Mount points are shown with descriptive names (*System Root (/)*, *Home*, *Mounted Volume*, *External Drive*) alongside their real paths.
- The drive list covers real user storage (`/`, `/home`, `/mnt`, `/media`, `/srv`, `/var/home`) and hides pseudo, container, and boot mounts; aliases of the same device collapse into one entry.
- Storage scans skip `/proc`, `/sys`, `/dev`, `/run`, and container storage roots.
- Deletions fall back to a FreeDesktop-compliant `~/.local/share/Trash` implementation when `gio` and `trash-put` are unavailable, so choosing the Recycle Bin never silently means permanent deletion.

### 14. Preferences & Configuration
- Segmented sub-tabbed settings view for *Appearance & Themes*, *Safety & Protection*, *Exclusions & Roots*, *Scan Performance*, *Category Rules*, and *Backup & Sync*.
- Preferences, theme, window geometry, cleanup category selections, exclusions, and scan options are stored locally in `config.json` under the platform config directory.
- The config file is versioned, so future releases can migrate older files; unknown, malformed, or wrongly typed entries fall back to defaults instead of preventing startup.

---

## Development

### Run locally

```sh
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements-dev.txt
./.venv/bin/python -m crapcleaner
```

### Test

```sh
./.venv/bin/python -m pytest -q
```

### Lint and format

```sh
ruff check crapcleaner tests
ruff format --check crapcleaner tests
```
- Full JSON export, import, and factory reset support for settings migration.

---

## Installation

### Option 1: Download Pre-compiled Binary (Recommended)

Download the latest standalone executable from the [GitHub Releases](https://github.com/PatrickJnr/crapcleaner/releases/latest) page:

- **Windows (64-bit)**: `CrapCleaner.exe` (portable binary, no Python or installation required).
- **Linux (64-bit)**: `crapcleaner` (ELF executable, compatible with Ubuntu, Fedora, Arch, Debian).

### Option 2: Run via uv / pip

```bash
git clone https://github.com/PatrickJnr/crapcleaner.git
cd crapcleaner
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

# Hardware and OS specifications
crapcleaner --specs
```

---

## Keyboard Shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+1` ... `Ctrl+9`, `Ctrl+0` | Jump to a sidebar view in order (Dashboard, Cleanup, Storage, Large Files, Duplicates, AI Data, Docker, PC Specs, Memory Cleaner, History) |
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
  system/           Hardware specs, disk health, memory reporting and reclamation
  gui/              PySide6 interface (views, theme, icons, workers)
  models/           Dataclasses for categories, scan results, and reports
  utils/            Platform helpers, safe file operations, formatting, updater
  assets/           Bundled fonts and images
scripts/            Build scripts and the PyInstaller entry point
tests/              Test suite
```

Category providers expose a `get_categories()` function and are wired together in `crapcleaner/registry.py`.

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
