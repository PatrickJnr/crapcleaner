# Changelog

All notable changes to **CrapCleaner** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.9.1] - 2026-08-18

Source installation fix for Python 3.10 and 3.11.

### Fixed
- **Import Failure On Python 3.10 And 3.11**: computes the installer account name outside the f-string in `crapcleaner.system.backends.updates_windows`. A backslash inside an f-string expression is a syntax error before Python 3.12, so that module could not be imported on the older interpreters this project supports, and the System Updates page raised on Windows before it could report anything. The published 1.0.9 executables bundle their own Python 3.12 and are unaffected; this reaches installations made from source with `pip`, `uv`, or a checkout.
- **Linter Coverage Of The Update Backend**: `ruff` stops at the first syntax error in a file, so the rest of `updates_windows.py` had never been checked. It is linted and formatted with the rest of the codebase now.

### Changed
- **File-Type Analysis Wording**: corrects the 1.0.9 note about where file sizes come from. On Windows the directory listing carries the size and reading it from the entry costs nothing; on Linux the entry still needs a stat, though one relative to the open directory rather than a fresh resolution of the whole path. The improvement is real on both, and largest on Windows.

### Internal
- **Cross-Platform Test Corrections**: three tests asserted Windows-specific behaviour and failed on the Linux side of the CI matrix. The services badge now takes its noun from the view rather than hard-coding *services*, since the page correctly reads *units* under systemd; the XDG autostart fixture redirects the system directory as well as the user one, so a listing no longer includes whatever the host distribution installed; and the file-type analysis test asserts that stat calls do not scale with file count rather than requiring an exact count, which differs between platforms.

---

## [1.0.9] - 2026-08-17

Platform-aware architecture release: Startup, Services, and System Updates managers that adapt to Windows or Linux, plus cross-platform App Updates.

### Added
- **Platform Capability Registry**: introduces `crapcleaner.system.capabilities`, the single source of truth for which system-management features the running operating system provides and what each one is called there. The navigation rail, the page set, the view headings, and the CLI all read from it, so no user-facing code branches on the operating system. Supporting another platform means adding backend modules and one registry entry per capability.
- **Platform-Neutral Dispatchers & Per-OS Backends**: splits the startup, service, and update managers into a shared dispatcher holding the data model, cache, and safety rules, over a backend per operating system in `crapcleaner.system.backends`. Platform dependencies stay inside their own backend: `winreg`, PowerShell, and `sc.exe` appear only in the Windows modules, and `systemctl`, `pkexec`, and package-manager commands only in the Linux ones.
- **Linux Service Management via systemd**: adds full parity with the Windows Services page for systemd, listing both system and user units with their active state and unit-file state, and offering start, stop, restart, and enable/disable/mask. System units elevate per command through `pkexec` so the application need not run as root, and units that keep a session alive - `dbus`, `systemd-logind`, `polkit`, `user@`, `getty@` - are guarded the same way critical Windows services are.
- **Linux System Updates**: adds distribution update management through `apt`, `dnf`/`yum`, `pacman`, and `zypper`, reporting pending updates with security errata marked, recent package history, and whether a reboot is pending.
- **Linux Startup Entry Management**: completes XDG autostart support with enable, disable, and remove alongside the existing listing. A user entry shadows the packaged entry of the same name, and disabling or removing a system entry in root-owned `/etc/xdg/autostart` writes a user-level override that hides it rather than touching a file the package manager owns.
- **Graceful Handling of Unsupported Features**: pages whose platform tooling is absent are hidden rather than shown broken, a navigation section whose entries are all unavailable is omitted, and every dispatcher entry point returns the registry's explanation instead of letting a platform command fail. A Linux system without systemd shows no Services page at all.
- **Platform-Filtered Memory Actions**: offers only the reclamation actions the running kernel provides, so Windows lists the standby list purge and Linux lists the filesystem cache drop. Each action's description names the exact call that system will make - `EmptyWorkingSet` on Windows, `malloc_trim` and `drop_caches` on Linux - rather than listing every platform's mechanism at once. Requesting a hidden action by id still reports why it is unavailable instead of an unknown-action error.
- **`--capabilities` CLI Flag**: reports which platform features the current operating system supports, with `--json` for automation.
- **Linux Privilege Escalation**: teaches `elevate()` and `relaunch_as_admin()` to use `pkexec`, and reports administrative rights on Linux from the effective user id rather than assuming every non-Windows user is privileged.
- **Windows Startup Manager**: introduces a dedicated Startup Applications manager that allows users to view, enable, disable, add, and remove programs and scripts configured to launch automatically with Windows. Inspects Current User and All Users Registry Run/RunOnce keys, modern `StartupApproved` flags, and user/system Startup folders with intelligent publisher discovery and boot impact estimations.
- **Windows Update Manager**: adds comprehensive Windows Update inspection and management via PowerShell COM APIs (`Microsoft.Update.Session`). Displays pending update titles, KB IDs, severity levels, download states, package sizes, and support URLs, initiates update downloads and installations with administrative elevation enforcement, and provides complete installed hotfix history auditing.
- **Windows Services Manager**: introduces interactive background service management enabling users to view, start, stop, restart, and configure startup types (Automatic, Automatic (Delayed Start), Manual, Disabled) for all installed Windows services. Features safety guardrails protecting critical OS services from accidental stoppage or disablement, multi-criteria filtering, and one-click access to the system management console (`services.msc`).
- **App Updates via Package Managers**: adds a cross-platform application update manager (`crapcleaner.system.package_managers`) that detects the package managers installed on the current system and reports every available application upgrade in one place. Supports `winget` and `chocolatey` on Windows and `apt`/`apt-get`, `flatpak`, `snap`, `pacman`, and `dnf`/`yum` on Linux, with a two-minute result cache, live search, and per-manager filtering. Upgrades run one package at a time, across a multi-row selection, or across an entire manager, and a queued selection continues past any package that fails. Installers are allowed 30 minutes for a single package and 2 hours for a whole-manager upgrade, since large IDE, SDK, and creative-suite installers routinely run for many minutes.
- **Column-Accurate Package Manager Parsing**: reads `winget upgrade` output using the column offsets declared in its own header, so a value that exactly fills its column, and is therefore separated from the next by a single space, still yields a usable package ID and version.
- **Friendly Windows Error Explanations**: introduces `crapcleaner.utils.windows_errors`, translating raw `0x8024xxxx` Windows Update and servicing failure codes into a plain-language title and remediation hint instead of surfacing the bare hexadecimal code.
- **New Sidebar Navigation & Material Icons**: adds *Startup Apps*, *Services*, *App Updates*, and *System Updates* to the left navigation rail under the *System* tier, carrying the `rocket_launch`, `tune`, and `system_update` Material Icons, dynamically recoloured for each of the 43 theme palettes. The icon map also gains `miscellaneous_services`, `play_arrow`, and `stop` for use in the service control surfaces.
- **Platform-Aware Navigation Rail**: teaches the sidebar to accept the set of pages the running platform actually provides, and to take each label from the capability registry so a page reads *Windows Services* on Windows and *systemd Services* on Linux.
- **CLI Management Options**: adds `--startup`, `--services`, and `--system-updates` command-line flags with full `--json` export support for headless automation and terminal diagnostics. `--windows-updates` remains accepted as an alias.
- **Sortable Table Header Hover Feedback**: adds a `QHeaderView::section:hover` style across all 43 themes so sortable column headers visibly respond before they are clicked.
- **Shared Visual Effects Toolkit**: introduces `crapcleaner.gui.effects` with an animated count-up label, a history sparkline, a proportional segmented bar, and hover-depth and accent-glow helpers. Every colour resolves from a palette token, so all 43 themes are covered without per-theme code, and every animation honours the *Reduce motion* preference by landing on its final value instead of easing to it. Depth is split deliberately: widgets that repeat inside a scroll area use a painted hover, because a `QGraphicsEffect` renders through an offscreen pixmap that disables subpixel text antialiasing, while a real drop shadow is reserved for single hero surfaces.
- **Live Vitals Sparklines**: draws a rolling 60-sample history under the Memory, Processor, Graphics, and Network cards on the Dashboard. The strips are fed from the vitals tick the Dashboard already runs, so no card owns a timer. Percentages plot against a fixed 0–100 ceiling for comparability over time, and network throughput auto-scales to its own peak.
- **Reclaimable Breakdown Panel**: fills the empty lower third of the Dashboard with a proportional bar and the top categories by size, coloured by safety level. Before a first scan it lists the category groups a scan would check, so the panel is informative rather than blank on a fresh install.
- **Counting Headline Figures**: eases the reclaimable total on the hero card and in the breakdown panel up to its new value when a scan completes.

### Changed
- **Faster CLI Quick Scan**: limits the `--quick` scan to the first five non-administrative, default-selected categories and caps it at 200 files, so a terminal health check returns promptly.
- **Platform-Neutral Storage Presets**: resolves the Storage Breakdown preset buttons through the stdlib and the platform helpers, so *Temp* points at the real temporary directory and *AppData* becomes *App Config* pointing at `$XDG_CONFIG_HOME` on Linux.
- **Deprecated Windows-Flavoured Names**: `crapcleaner.system.windows_updates`, `WindowsUpdateItem`, `WindowsUpdateReport`, `WindowsUpdateView`, `WindowsUpdateWorker`, `WindowsUpdateInstallWorker`, and `open_services_msc` remain importable as aliases of their platform-neutral replacements in `system_updates`, `SystemUpdatesView`, `SystemUpdateWorker`, `SystemUpdateInstallWorker`, and `open_services_console`.

### Fixed
- **Windows Junctions Followed During Scanning And Cleanup**: skips reparse points during every filesystem traversal. A Windows directory junction reports itself as an ordinary directory through `S_ISLNK`, `os.path.islink`, and `DirEntry.is_dir(follow_symlinks=False)`, so the only reliable signal is its reparse tag, which nothing checked. A junction loop therefore recursed until the file budget ran out, counting the same files repeatedly and truncating the result, and a junction pointing outside the scanned tree presented unrelated files as reclaimable junk. `crapcleaner.utils.files.walk_safe` now backs the scan, preview, cleanup, duplicate, large-file, old-file, file-type, installer, and package-cache walks; links are reported as entries in their own right, so deleting a tree removes the link and leaves its target alone.
- **Deletion Following Junctions On Python 3.10 And 3.11**: detaches links inside a tree before calling `shutil.rmtree`, which only learned to recognise junctions in Python 3.12 via `os.DirEntry.is_junction`. On the older interpreters this project supports, removing a cleanup target that contained a junction deleted the files it pointed at. The read-only attribute pass is likewise confined to the tree being removed.
- **Storage Breakdown Performance**: analysing a large folder drops from roughly two minutes to about half a minute on Windows. `analyze_file_types` issued a fresh `os.stat` against the full path of every file, which alone accounted for about ninety of those seconds; sizes now come from the directory entry through `walk_safe_entries`. The gain is largest on Windows, where the listing already carries the size and the entry lookup is free; on Linux the entry still needs a stat, but one relative to the open directory rather than a fresh resolution of the whole path. Directory measurement additionally walks top-level subtrees in parallel, which is safe because enumeration is dominated by syscalls that release the interpreter lock, and results are summed and re-sorted afterwards so the output never depends on completion order.
- **Storage Breakdown Progress And Cancellation**: reports the current stage, files seen, and directory while an analysis runs, and adds a Cancel button. The three analysis passes all accepted a stop event and a progress callback, but the worker passed neither, so a multi-minute analysis showed no feedback and could not be stopped.
- **Application Startup**: the window appears in roughly a third of the time. All sixteen pages were constructed before the window could be shown; pages are now built the first time they are opened, and a page built after a theme change picks up the current theme.
- **Windows-Only File Manager Commands In The GUI**: replaces six unguarded `explorer` invocations with a platform-aware helper that uses the freedesktop file manager interface or `xdg-open` on Linux, and names the file manager correctly in menu labels. One of those call sites interpolated a path into a command string, so a file name containing a quote could alter the command; arguments are now always passed as a list.
- **Scan Performance**: a full scan of every non-administrative category drops from over ten minutes to roughly one second on the development machine, and directory walking rises from about 108 files per second to over 100,000. `validate_cleanup_path` rebuilt the protected-root list and re-read `config.json` for every candidate file, costing around forty `_getfinalpathname` syscalls and a JSON parse each. The protected roots and exclusion rules are now cached and invalidated explicitly, a scan resolves each directory once instead of each file, and subdirectory checks derive from their parent without touching the filesystem.
- **Truncated Scan Totals**: reclaimable totals were being cut short wherever a junction loop consumed the per-category file budget with duplicate entries, so the reported figure was both wrong and unstable between runs.
- **Exclusion Edits Not Applying**: publishes a cache invalidation when settings are saved, so an exclusion added in Preferences takes effect on the next scan rather than after a restart.
- **Unreadable Stat Cards After Switching To A Light Theme**: re-applies stat card and elevation-notice colours on every theme change. Those labels carry an inline stylesheet baked at construction time, which outranks the global sheet, so moving from a dark theme to a light one previously left the *Safe Caches*, *Dev & AI Caches*, *Drives Detected*, and *Lifetime Cleaned* values near-white on a near-white card. Affects the Dashboard and History views.
- **Ambiguous View Shortcuts**: binds `Ctrl+1`–`Ctrl+9` and `Ctrl+0` to the first ten sidebar views only. With sixteen pages the numbering previously wrapped round, binding `Ctrl+1` through `Ctrl+6` twice each, which Qt treats as ambiguous and refuses to fire at all.
- **Table Sorting `RecursionError`**: resolves `Error calling Python override of QTableWidgetItem::__lt__(): RecursionError: maximum recursion depth exceeded` when sorting any table or tree column that falls back to a text comparison. PySide re-dispatches `super().__lt__()` straight back into the Python override that calls it, so `NumericItem` and `_SizeSortedItem` compare text directly.
- **Directory Size Scan File Budget**: counts every visited entry against `max_files` in `compute_dir_size` and stops unwinding as soon as the budget is reached, keeping a deeply nested directory tree within its scan limit.
- **Repeated Protected-Path Import In Scan Loop**: hoists the `validate_cleanup_path` import out of the per-file inner loop in `compute_dir_size`.

---

## [1.0.8.1] - 2026-08-17

Astral uv build and development scripts, dependency lockfile, and documentation updates.

### Added
- **Astral uv Build & Run Scripts**: adds `scripts/builduv.sh` and `scripts/runuv.sh` for fast virtual environment bootstrapping, automated dependency synchronization, and PyInstaller binary compilation using Astral `uv`.
- **Dependency Lockfile (`uv.lock`)**: introduces `uv.lock` for deterministic, reproducible dependency resolution across environments while preserving the existing pip/venv workflow.

### Documentation
- **Updated Setup & Run Guides**: expands `README.md` with uv-based workflow instructions for local execution, development, testing, and executable builds alongside standard pip commands.

---

## [1.0.8] - 2026-08-16

Help & Safety modal dialog architecture, sidebar reorganization, sponsorship integration, and standalone packaging fixes.

### Added
- **Help & Safety Modal Dialog**: introduces `HelpSafetyDialog`, a dedicated modal window housing the comprehensive 9-part safety philosophy, technical documentation, troubleshooting guide, live FAQ search, category filter chips, and one-click system diagnostics copier.
- **Global Help & Documentation Access**: adds global `F1` shortcut trigger, sidebar "Safety First" footer card action buttons, and direct About view links to open the Help & Safety modal dialog from anywhere in the application.
- **GitHub Funding Configuration**: adds `.github/FUNDING.yml` configuration supporting GitHub Sponsors, Ko-fi, Buy Me a Coffee, and custom PayPal donation endpoints.
- **PyInstaller Packaging Specification (`CrapCleaner.spec`)**: introduces a dedicated spec file collecting all `crapcleaner` subpackages, assets, and PySide6 Qt6 platform plugins, resolving standalone executable packaging across Windows and Linux.

### Changed
- **Sidebar Navigation Reorganization**: streamlines the left navigation rail into four logical, ordered tiers (*Overview*, *Deep Scan*, *System*, and *Preferences*), placing *Settings* and *About* at the bottom of the navigation rail for intuitive desktop navigation.
- **Drive Usage Donut Theme Palette Integration**: renders the Dashboard storage capacity ring using the active theme's accent color (`pal["accent"]`), replacing the diagonal linear gradient for consistent visual cohesion across all 43 themes.
- **Contributor Card Layout**: bounds community contributor cards to a proportional maximum width in a balanced two-column grid.

### Fixed
- **PyInstaller Standalone Executable Packaging**: resolves `ModuleNotFoundError: No module named 'crapcleaner.gui'` in compiled Windows and Linux release binaries by updating release workflows to use full package installs and `CrapCleaner.spec`.

---

## [1.0.7.1] - 2026-08-16

Theme additions and worker lifecycle stability patch.

### Added
- **Adwaita Themes**: adds GNOME-inspired *Adwaita Dark* (neutral dark surfaces with restrained blue accents) and *Adwaita Light* (clean light surfaces with understated blue accents) color palettes, expanding the theme gallery to 43 curated themes.
- **Dynamic Theme Category Counts**: calculates theme category counts dynamically in the Theme Gallery filter chips (*Modern Dark (7)*, *Light & Pastel (5)*, *Retro & Vintage (8)*, *Cyber & Synth (4)*, *Code Palettes (8)*, *Warm & Nature (11)*).

### Fixed
- **Worker Thread Internal C++ Object Deletion**: resolves Shiboken `RuntimeError: libshiboken: Internal C++ object (...) already deleted` when re-triggering storage health diagnostics (`refresh_health`), hardware queries (`refresh_specs`), storage analysis (`run_analysis`), or memory actions by introducing `is_worker_running` and `stop_worker` safe lifecycle helpers and automatically clearing finished worker references.

---

## [1.0.7] - 2026-08-16

Quality of Life, Scan Insights, and Stability release.

### Added
- **Scan Insights & Space Recommendations**: adds an interactive `ScanInsightsWidget` directly in the Deep Cleanup view providing immediate visual breakdowns of safe vs reviewable reclaimable space, top storage-consuming categories, and actionable recommendations.
- **Storage Analyzer Quick-Access Bookmarks**: introduces a one-click directory favorites bar in the Storage Breakdown view (Home, Downloads, Documents, AppData / .config, Temp, Videos) for instant storage exploration without manual folder browsing.
- **Async Worker Thread Lifecycle & Stability**: introduces strict QThread lifecycle management across all async inspectors (`SpecsWorker`, `HealthWorker`, `StorageAnalysisWorker`, `MemoryReportWorker`, `MemoryActionWorker`), ensuring clean thread termination, graceful parent widget destruction, and zero headless CI/Windows access violations.
- **Theme Fade Transition Polish**: optimizes UI theme cross-fades by safeguarding against widget and animation double-deletion, with resilient fallback handling in headless and virtual display environments.

### Improved
- **Hardware & GPU Detection**: enhances GPU and VRAM introspection across Windows and Linux platforms with robust error handling for hybrid multi-GPU setups and virtual display environments.
- **Test Suite Teardown & Isolation**: adds automated Qt top-level widget and thread cleanup fixtures in pytest, ensuring 100% test isolation and zero cross-test event leaks.

---

## [1.0.6] - 2026-08-16

Theme Gallery and Preferences redesign release.

### Added
- **Visual Theme Gallery**: replaces the plain dropdown with an interactive visual gallery displaying all 41 themes. Features real-time 5-color swatch bars, active theme preview banner, category filter chips (*Modern Dark*, *Light & Pastel*, *Retro & Vintage*, *Cyber & Synth*, *Code Palettes*, *Warm & Nature*), live search filtering, "Surprise Me" randomizer, and default reset.
- **Live System Vitals Dashboard**: introduces zero-overhead real-time telemetry cards on the Dashboard for Network bandwidth (download & upload transfer rates, session transfer totals, and active connection adapter), RAM utilization with dynamic high-memory pressure alerts and quick Memory Cleaner access, real-time multi-core CPU load, GPU temperature monitoring & VRAM utilization, and live system uptime with fluid OutCubic animated transitions.
- **Hardware Specs Skeleton Loading**: renders modern animated pulsing skeleton placeholder cards across the PC Specs view during async hardware, GPU, and SMART sensor queries, eliminating empty layout states.
- **Overhauled Memory Cleaner View & Kernel Cache Purging**: redesigns the Memory Cleaner view with a high-impact Hero status banner, 2-column hardware vitals, and a multi-tier memory flush engine. Supports multi-pass process working set trimming (`psapi.EmptyWorkingSet`) for standard users, alongside one-click administrator elevation to purge the Windows kernel standby list (priorities 0–7), modified page list, and system file cache.
- **Segmented Settings Architecture**: organizes Preferences & Configuration into dedicated sub-tabs (*Appearance & Themes*, *Safety & Protection*, *Exclusions & Roots*, *Scan Performance*, *Category Rules*, *Backup & Sync*) with sticky top actions and quick-tuning performance presets.
- **Pure Material Icon Typography & View Upgrades**: renders crisp Google Material Icons dynamically colored to match the active theme palette across all preferences, action buttons, category chips, and toolbar controls in every view, alongside real-time active scanning indicators.

### Changed
- **Branding consistency**: standardizes application title and branding to pure *CrapCleaner*, removing legacy comparison references.

---

## [1.0.5] - 2026-08-16

Repository reorganization release. Behaviour is unchanged; module paths are not.

### Changed
- **Cleanup providers live in one package**: the eleven single-module packages (`crapcleaner.ai`, `apps`, `browsers`, `developer`, `docker`, `dotnet`, `gaming`, `gpu`, `node`, `python`, `windows`) collapse into `crapcleaner.categories.<name>`, so every provider sits side by side instead of behind its own `cleanup.py`.
- **Scan and cleanup engine sits in `crapcleaner.core`**: `cleaners.cleaner`, `cleaners.actions`, `cleaners.preview`, `scanner.scanner`, `scanner.cache`, `scanner.size`, `safety.protected_paths`, and `scheduler.scanner` move to `core.cleaner`, `core.actions`, `core.preview`, `core.scanner`, `core.cache`, `core.size`, `core.protected_paths`, and `core.scheduler`.
- **Read-only disk inspection sits in `crapcleaner.analysis`**: `storage.analyzer`, `storage.file_types`, `storage.old_files`, `storage.virtual_machines`, `large_files.scanner`, `large_files.installers`, `duplicates.finder`, `cleaners.crash_dumps`, and `cleaners.recycle_bin` move to `analysis.storage`, `analysis.file_types`, `analysis.old_files`, `analysis.virtual_machines`, `analysis.large_files`, `analysis.installers`, `analysis.duplicates`, `analysis.crash_dumps`, and `analysis.recycle_bin`.
- **Hardware and memory introspection sits in `crapcleaner.system`**: `specs.hardware`, `specs.storage_health`, `memory.cleaner`, and `memory.report` move to `system.hardware`, `system.storage_health`, `system.memory_actions`, and `system.memory_report`.
- **Single-module packages flatten to modules**: `config.settings`, `history.store`, and `reports.exporter` become `crapcleaner.config`, `crapcleaner.history`, and `crapcleaner.reports`.
- **Assets consolidate into `crapcleaner/assets/`**: the Material Icons font, its codepoints, its licence (as `FONT-LICENSE`), and the About-page avatar share one directory, so frozen builds bundle a single `--add-data` path instead of two.
- **Build tooling moves under `scripts/`**: `build.bat` becomes `scripts/build_windows.bat` and `build_launcher.py` becomes `scripts/launcher.py`, joining the existing `scripts/build_linux.sh`.

### Added
- Packaging declares `crapcleaner/assets/*` as package data, so a built wheel carries the icon font and avatar rather than relying on an editable install.

### Documentation
- README gains a Project Structure section describing the current layout.
- CONTRIBUTING points at `crapcleaner/categories/` for new cleanup categories and documents the build scripts.

---

## [1.0.4] - 2026-08-15

Linux-focused hotfix release.

### Added
- **FreeDesktop Trash fallback**: when neither `gio` nor `trash-put` is available, deletions are written to `~/.local/share/Trash` following the FreeDesktop specification, complete with `.trashinfo` metadata and collision-safe naming. Previously a Linux system without those tools silently fell back to permanent deletion even when the Recycle Bin option was selected.
- **Descriptive Linux drive names**: mount points are presented as *System Root (/)*, *Home*, *Mounted Volume (name)*, *External Drive (name)*, and *Service Storage (name)*, each with a matching category badge, while the underlying path stays visible.

### Improved
- Skips `/proc`, `/sys`, `/dev`, `/run`, and container storage roots during Linux storage scans, so pseudo-filesystems no longer inflate or stall a breakdown.
- Restricts the Linux drive list to real user-facing storage (`/`, `/home`, `/mnt`, `/media`, `/srv`, `/var/home`) and hides pseudo, container, and boot mounts.
- Deduplicates Linux mounts by device and inode instead of by disk-usage totals, so bind mounts and symlinked aliases collapse to a single entry rather than being matched by coincidence.
- Adds the user home directory to the Storage Breakdown path selector on Linux and widens the selector for longer paths.
- Reports storage device type per mount on Linux in the PC Specs drive list.

### Fixed
- Preserves NVIDIA adapter capacity when the driver reports `N/A` for live VRAM usage, instead of discarding the adapter entirely.
- Stops reporting per-process VRAM attribution. The driver interfaces that expose it omit graphics contexts while surfacing unrelated helper processes, which made the list misleading rather than useful.

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
    - *Inspect graphics memory* is a read-only VRAM report covering adapter capacity and live usage where the driver exposes it.
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
