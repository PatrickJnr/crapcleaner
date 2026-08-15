# Changelog

All notable changes to **CrapCleaner** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.3] - 2026-08-15

### Added
- **Centralized Protected Paths Safety Layer (`crapcleaner.safety.protected_paths`)**:
  - Centralized safety engine that enforces immutable protection over critical OS system directories (`C:\Windows`, `C:\Windows\System32`, `/usr`, `/etc`, `/boot`), user profile core roots (`Documents`, `Desktop`, `Pictures`, `Music`, `Videos`), Git repositories (`.git`), SSH/GPG keys (`.ssh`, `.gnupg`), browser credentials (`Login Data`, `Cookies`, `key4.db`), game saves, and drive volume roots.
  - Deep path validation embedded across all file cleanup operations and directory walkers.
- **Transparent Category Explanations**:
  - Added structured technical metadata to every cleanup category: `what_it_contains`, `why_it_grows`, `why_safe_to_delete`, `regeneration_behavior`, and `reversible`.
- **Pre-Cleanup Preview Engine (`crapcleaner.cleaners.preview`)**:
  - Detailed pre-cleanup preview enumerating candidate files and directories, reclaimable byte estimates, staleness validation, and administrative permission requirements before any modification occurs.
- **Old Files Storage Scanner (`crapcleaner.storage.old_files`)**:
  - Non-destructive age-based storage analysis finding files unmodified for configurable thresholds (30, 90, 180, 365+ days) with path, size, and last modified date reporting.
- **Dynamic GitHub Contributors & Credits (`crapcleaner.utils.contributors`)**:
  - Real-time GitHub Contributors API integration on the About page featuring local response caching, rate-limit resilience, offline fallback, and profile navigation.
- **Storage Recycle Bin & FreeDesktop Trash Inspector (`crapcleaner.cleaners.recycle_bin`)**:
  - Windows `SHQueryRecycleBinW` and Linux FreeDesktop Trash metadata parser displaying total recoverable space, item counts, oldest/newest deleted timestamps, and safe empty actions.
- **Storage Breakdown & Hierarchical Explorer (`crapcleaner.storage.analyzer`)**:
  - Recursive directory tree analyzer with percentage-of-parent calculations, symlink/junction cycle detection via device/inode tracking, and largest-child sorting.
- **Functional File Type Storage Analysis (`crapcleaner.storage.file_types`)**:
  - Categorization of storage consumption across 10 functional groups (Videos, Images, Audio, Archives, Documents, Code, Executables, Databases, Disk Images, and Other).
- **Virtual Machine & Container Storage Inspector (`crapcleaner.storage.virtual_machines`)**:
  - Detection and non-destructive analysis of WSL2 VHDX virtual disks, Docker desktop data, VirtualBox VDI images, VMware VMDKs, and Hyper-V disks with safe optimization guidance.
- **Storage Device Health & TRIM Diagnostics (`crapcleaner.specs.storage_health`)**:
  - Detection of physical drive media types (NVMe SSD, SATA SSD, HDD), bus interfaces, capacity, free space, and TRIM support/enablement diagnostics (`fsutil` / `Get-PhysicalDisk` / `lsblk`).
- **Memory & Crash Dump Analyzer (`crapcleaner.cleaners.crash_dumps`)**:
  - Deep inspection of Windows user-mode crash dumps (`%LOCALAPPDATA%\CrashDumps`), kernel minidumps, system memory dumps, and Linux core dumps with application name attribution.
- **Old & Redundant Installer Detector (`crapcleaner.large_files.installers`)**:
  - Non-destructive scanner detecting `.msi`, `.exe`, `.msix`, `.appx`, `.iso`, `.deb`, `.rpm`, `.dmg`, and `.pkg` installers in user download folders.
- **Deep Browser Cache Inspection (`crapcleaner.browsers.cleanup`)**:
  - Expanded cache and GPU shader inspection across Chromium (Chrome, Chrome Beta, Chromium, Edge, Brave, Opera, Opera GX, Vivaldi, Arc) and Firefox (Firefox, LibreWolf, Waterfox, Floorp) with active running browser detection.
- **Developer Engine & Tooling Cache Expansions (`crapcleaner.developer.cleanup`)**:
  - Added support for Unity Editor package and shader caches, Godot Engine editor and shader caches, Unreal Engine DDC, CMake build packages, MSBuild / NuGet scratch directories, and JetBrains IDE caches.
- **Gaming Launchers & Shader Caches (`crapcleaner.gaming.cleanup`)**:
  - Added targeted cleanup of launcher web caches and DirectX/GPU shader caches for Steam, Epic Games Launcher, EA Desktop / Origin, Ubisoft Connect, Battle.net, GOG Galaxy, Riot Games / Valorant, and FiveM while strictly preserving save files, games, and mods.
- **Centralized Multi-Format Report Exporter (`crapcleaner.reports.exporter`)**:
  - Export storage analyses, scan results, disk health diagnostics, and audit history to structured JSON, CSV, and formatted TXT files.
- **Threshold-Based Scheduler Scanner (`crapcleaner.scheduler.scanner`)**:
  - Non-destructive automated scan engine with configurable notification thresholds.
- **Expanded CLI Commands**:
  - `--storage [PATH]`: Hierarchical storage usage tree.
  - `--file-types [PATH]`: Storage distribution by file category.
  - `--disk-health`: Physical drive health and TRIM diagnostic report.
  - `--recycle-bin`: Inspect Recycle Bin / Trash storage.
  - `--empty-recycle-bin`: Empty Recycle Bin / Trash with confirmation.
  - `--cleanup-preview`: Pre-cleanup candidate inspection.
  - `--installers`: Detect old installer files.
  - `--cache-report`: Developer and application cache breakdown.
  - `--protected-paths`: List and audit active safety rules.
  - `--export <json|csv|txt>` with `--output <path>`: Multi-format report export.
- **Memory Cleaner (`crapcleaner.memory`)**: adds a Memory Cleaner view and CLI reporting total, used, available, cached/standby and committed memory, memory pressure, swap/pagefile usage, and per-adapter graphics memory.
  - Reports live VRAM usage on NVIDIA hardware (`nvidia-smi`) and AMD hardware on Linux (`amdgpu` sysfs). Adapters without a reliable counter report capacity only and state that usage is *unknown* rather than zero.
  - Provides separate, individually explained reclamation actions instead of one opaque button:
    - *Release CrapCleaner's own memory* trims only this application's working set (Windows) or heap (Linux `malloc_trim`), with no elevation required.
    - *Purge the Windows standby list* discards cached file data through `NtSetSystemInformation` and requires administrator rights.
    - *Drop the Linux filesystem cache* runs `sync` followed by `drop_caches` and requires root; it touches filesystem cache only.
    - *Inspect graphics memory* is a read-only VRAM report listing the processes holding VRAM where the driver exposes them.
  - States the exact system call each action performs, confirms before running, and reports before/after available memory plus the amount actually reclaimed. Failed or refused operations are reported honestly instead of being shown as successful.
  - Never terminates processes, changes process priorities, modifies pagefile configuration, resets the GPU, or allocates memory as a placebo.
  - Adds `--memory` (with `--json`) for statistics and `--memory-clean <action>`, which dry-runs until `--execute` is passed; `--memory-clean list` shows what the current system supports.
- **Themes**: adds **OLED Black**, **Midnight Blue**, **Slate**, **Forest**, **Graphite**, **Arctic Light**, **Solarized Dark**, and **High Contrast** alongside the refined Dark and Light themes - ten in total, each a complete palette defined as design tokens in `crapcleaner.gui.theme`.
- **Reduce motion setting**: skips the theme cross-fade for users who prefer no animation.
- **Storage grid visualization**: replaces the Storage Breakdown directory tree with a proportional grid where cell area maps to size, so the largest consumers are the largest blocks. Supports drill-down navigation with breadcrumbs and an Up control, keyboard selection (arrows, Home/End, Enter, Backspace), tooltips for cells too small to label, an aggregate cell for the long tail, and a separate cell for files held directly in the current folder.
- **Versioned settings**: the local configuration file carries a `config_version` so future releases can migrate older files; unknown, malformed, or wrongly typed entries fall back to defaults instead of preventing startup.

### Improved
- Applies theme changes the moment they are selected and cross-fades between the old and new appearance instead of switching abruptly, without blocking the interface.
- Persists the selected theme and the reduce-motion preference immediately, so neither has to be reselected after a restart.
- Deepens the OLED theme to true black backgrounds with near-black panels while keeping text, borders, and disabled states readable.
- Applies the active theme consistently in the PC Specs, About, and Help views, which previously used hard-coded dark colours.
- Sorts cleanup categories by reclaimable size, ascending or descending, from the Cleanup toolbar.
- Separates permission failures from genuine errors in cleanup results and explains why individual items were skipped (protected path, file in use, or locked) in both the GUI report and CLI output.
- Speeds up Storage Breakdown scans by roughly 20-25 percent on large trees (measured 4.24s to 3.35s over 163,000 files) by dropping one filesystem stat per directory, while preserving symlink, junction, mount-point, and loop protection and producing byte-identical results.
- Caches drive health, media type, and TRIM diagnostics for a minute and shares them between the Storage and PC Specs views, so revisiting a view no longer re-spawns a PowerShell query that took about three seconds; the Refresh Health button still forces a fresh read.
- Loads PC Specs and storage analysis off the GUI thread, keeping the interface responsive while hardware is queried.
- Distinguishes "nothing found" from "not scanned yet" in the Large Files, Duplicates, and AI Data views, so a completed scan with no results no longer looks like it never ran.

### Fixed
- Fixes privilege reporting on Windows: enabling `SeProfileSingleProcessPrivilege` claimed *"Run as administrator"* even on an already elevated process, because the Windows last-error code was read through a handle that does not preserve it. Privilege acquisition now uses explicit argument types, reads the error code immediately after `AdjustTokenPrivileges`, and distinguishes token-open failure, unknown privilege, adjust failure, and `ERROR_NOT_ALL_ASSIGNED` (the privilege is absent from the token), reporting the real reason. The Memory Cleaner also shows whether the process is elevated.
- Fixes the *Appearance & Theme* settings group rendering its ampersand as a stray underline (Qt mnemonic escaping).
- Fixes saving preferences resetting untouched settings such as the stored window geometry.

### Security & Philosophy Guarantees
- **Strict Prohibition on Registry Cleaning**: In accordance with core principles, CrapCleaner explicitly contains zero registry cleaners, optimizers, or defragmenters.
- **Zero Telemetry**: No tracking, analytics, ads, or network telemetry.
- **Reversible by Default**: Reversible cleanup via Recycle Bin / FreeDesktop Trash.

---

## [1.0.2] - 2026-08-15

### Added
- **Linux Trash Support**: Integration with FreeDesktop trash specification via `gio trash`, `trash-cli`, and `~/.local/share/Trash`.
- **Advanced Linux Mount Detection**: Intelligent filesystem filtering and deduplication for `/proc/mounts` with drive label and filesystem type reporting.
- **Cross-Platform Developer Caches**: Restored developer tools and package manager categories across all supported operating systems.
- **Large Scan Performance Optimization**: Bounded memory scanning and result virtualization for Large Files and Duplicates finders on massive drives.

## [1.0.1] - 2026-08-14

### Added
- **Linux Compatibility & Packaging**: Full Linux support across desktop applications, package managers, and system diagnostics from a single codebase.
- **Linux Package Managers**: Cleanup targets for APT, DNF, pacman, Flatpak, and Snap caches.
- **Linux Browsers & Electron Apps**: Cache cleanup support for Linux Chrome, Chromium, Firefox, Edge, Brave, Discord, Slack, and Spotify.
- **Linux Hardware Diagnostics**: Hardware and system inspection using `/proc/cpuinfo`, `/proc/meminfo`, `/sys/class/dmi/id`, `/etc/os-release`, and `lspci`.
- **Linux Build Script**: Standalone executable packaging via `scripts/build_linux.sh`.

## [1.0.0] - 2026-08-14

### Added
- **Fluent 2 Dark GUI**: High-contrast typography, interactive Storage Donut gauge, stat cards, badges, and responsive controls.
- **Grouped Sidebar Navigation**: Overview, Deep Scan, System, and About with live reclaimable badge counters.
- **Hardware and OS Specs Inspector**: Real-time hardware diagnostics and OS specifications.
- **Multi-Stage Parallel Duplicate Finder**: Fast 8 KB prefix hashing + full SHA-256 duplicate detection.
- **Deep Scan and Analytics**: Large Files, AI Models Explorer, Docker/WSL2 storage, Audit History.
