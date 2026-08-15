# Changelog

All notable changes to **CrapCleaner** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **Linux Hardware Diagnostics**: Speccy-style inspection using `/proc/cpuinfo`, `/proc/meminfo`, `/sys/class/dmi/id`, `/etc/os-release`, and `lspci`.
- **Linux Build Script**: Standalone executable packaging via `scripts/build_linux.sh`.

## [1.0.0] - 2026-08-14

### Added
- **Fluent 2 Dark GUI**: High-contrast typography, interactive Storage Donut gauge, stat cards, badges, and responsive controls.
- **Grouped Sidebar Navigation**: Overview (Dashboard, Cleanup), Deep Scan (Large Files, Duplicates, AI Data, Docker), System (Specs, History, Settings), and About with live reclaimable badge counters.
- **Hardware and OS Specs Inspector**: Speccy-style real-time hardware diagnostics (CPU, GPU, RAM, Motherboard, BIOS, Storage partitions, and Network) with copy and JSON export.
- **Multi-Stage Parallel Duplicate Finder**: Fast 8 KB prefix hashing + full SHA-256 duplicate detection with smart resolution helpers (Keep Oldest, Keep Newest, Keep Shortest, Keep First).
- **Deep Scan and Analytics**:
  - Large Files Finder: Instant folder presets, threshold filters, table search, CSV export, and Recycle Bin context actions.
  - AI Models and Data Explorer: Read-only weight inspection for Ollama, LM Studio, Hugging Face, PyTorch.
  - Docker and WSL2 Storage: Status metrics, virtual disk (.vhdx) table, and safe prune actions.
  - Audit History: Operation records, lifetime space recovered metrics, and JSON export.
- **Expanded Ecosystem Coverage (65+ Categories)**:
  - Windows: Cryptnet SSL Cache, Font Cache, Prefetch, WER, Minidumps, Delivery Optimization, DirectX Shaders.
  - Developer Tools: VS Code, Cursor, Windsurf, Zed, Rust / Cargo, Go, Gradle & Maven, Bun, Android SDK, JetBrains, Unreal DDC, s&box.
  - Applications and Package Managers: WinGet, Chocolatey, Scoop, Discord, Slack, Spotify.
  - Gaming: Steam shader and depot caches, EA Desktop, Origin, Ubisoft Connect, Riot Games, Valorant, FiveM.
  - Python / Node / .NET: pip, uv, poetry, conda, npm, yarn, pnpm, NuGet.
- **Enhanced CLI and Diagnostics**:
  - `--list-categories`: Formatted overview of all categories and safety levels.
  - `--duplicates <folder>`: Scan directories for duplicates from the terminal.
  - `--health-check`: System storage overview and junk ratios.
  - `--specs`: Output hardware and OS specifications in ASCII or JSON.
  - `--benchmark`: Scanner throughput and file traversal benchmarks.
- **Windows Resilience**: Automatic long-path (`\\?\`) normalization and locked/readonly attribute clearing.
- **GitHub Infrastructure**: CI workflows, automated PyInstaller release builds, and issue templates.
