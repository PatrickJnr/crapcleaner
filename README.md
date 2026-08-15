# CrapCleaner

A fast, transparent cleanup and disk analysis utility built for power users, developers, and gamers, with Windows and Linux support from a single codebase.

[![CI](https://github.com/PatrickJnr/crapcleaner/actions/workflows/ci.yml/badge.svg)](https://github.com/PatrickJnr/crapcleaner/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-3b82f6.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-blue.svg)](#)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## Screenshots

<img width="1262" height="845" alt="image" src="https://github.com/user-attachments/assets/4f227648-df10-426d-9000-73ecec879afe" />
<img width="1262" height="845" alt="image" src="https://github.com/user-attachments/assets/bafe415b-6809-41f7-9e83-35a04bd9640b" />
<img width="1262" height="845" alt="image" src="https://github.com/user-attachments/assets/16942ba4-ebcb-4064-818c-a1695c80b876" />

---

## Overview

CrapCleaner is a local disk cleaner and storage analyzer for desktop systems. It targets temporary files, developer build caches, package manager stores, browser caches, and application caches while keeping critical project files, saved credentials, and user data intact. Windows-specific cleanup modules remain available on Windows builds, while Linux builds use Linux-appropriate paths from the same codebase.

## Features

### 1. Storage Dashboard
- Real-time disk capacity and reclaimable space calculation across all mounted drives.
- Storage partition breakdown with visual capacity gauges and warning indicators.
- Quick scan triggering with lifetime cleanup history metrics.

### 2. Deep Cleanup Categories (65+ targets)
- **Windows System**: User and system TEMP directories, crash dumps, Delivery Optimization cache, Font Cache, Cryptnet SSL certificate cache, DirectX and GPU shader caches, and Prefetch traces.
- **Developer Tools**: VS Code, Cursor, Windsurf, Zed, JetBrains IDEs (IntelliJ, PyCharm, WebStorm, Rider, CLion), Android SDK build caches, Gradle daemon logs, Bun cache, and Unreal Engine Derived Data Cache (DDC).
- **Package Managers**: npm, yarn, pnpm store, pip, uv, poetry, conda, NuGet, Cargo/Rust cache, Go build cache, Maven, WinGet, Chocolatey, and Scoop.
- **Gaming & Launchers**: Steam shader and depot caches, EA Desktop and Origin logs/caches, Ubisoft Connect caches, Riot Games and Valorant crash logs, DirectX shader caches, and FiveM cache.
- **Browsers & Desktop Apps**: Chrome, Chromium, Edge, Brave, and Firefox HTTP/GPU caches (leaving bookmarks, passwords, history, and active sessions intact), Discord, Slack, and Spotify caches.
- **Linux Package Managers**: APT, DNF, pacman, Flatpak, and Snap caches from Linux builds.

### 3. Multi-Stage Duplicate File Finder
- Three-stage identification pipeline: exact size matching -> 8 KB header hashing -> full SHA-256 validation.
- Multi-threaded traversal optimized for fast SSD/NVMe disk I/O.
- Smart duplicate resolution helpers: Keep Oldest, Keep Newest, Keep Shortest Path, and Keep First.

### 4. Large Files Scanner
- Pre-configured search targets (User Profile, Downloads, AppData, Temp) or custom root directory scanning.
- Live file size and extension filters with right-click Explorer reveal.

### 5. AI Models and Weights Explorer
- Read-only inspection for local machine learning model weights (Ollama, LM Studio, Hugging Face, PyTorch).
- Protected by default to prevent accidental deletion of large model files.

### 6. Docker and WSL2 Storage Inspector
- Live Docker container and volume disk usage breakdown (`docker system df`).
- WSL2 virtual disk (`.vhdx`) file size detection and manual compaction instructions.

### 7. Hardware and OS Specifications Inspector
- Speccy-style hardware diagnostics: CPU cores and frequency, GPU name and dedicated VRAM, Motherboard model and BIOS version, RAM utilization and capacity, active network interfaces, and Windows build details.
- One-click copy or JSON export (`crapcleaner --specs --json`).

### 8. Safety Guarantees
- Scans are read-only and never modify files.
- Cleanup operations send files to the Windows Recycle Bin by default.
- Directory traversal uses Windows long-path prefixing (`\\?\`) and cycle detection to prevent infinite junction loops.
- Zero advertisements, zero third-party telemetry, and 100% local execution.

---

## Installation

### Prerequisites
- Windows 10 / 11 or a modern Linux distribution
- Python 3.10, 3.11, or 3.12

### Option 1: Run from Source

```bash
git clone https://github.com/PatrickJnr/crapcleaner.git
cd crapcleaner

python -m venv .venv
```

On Windows:

```powershell
.venv\Scripts\activate
pip install -e .
crapcleaner
```

On Linux:

```bash
. .venv/bin/activate
pip install -e .
crapcleaner
```

### Option 2: Windows Batch Launcher

Double-click `run_crapcleaner.bat` in the project root, or execute:

```cmd
run_crapcleaner.bat
```

### Option 3: Build Platform Package

Windows build:

```cmd
build.bat
```

The compiled standalone executable will be placed in `dist\CrapCleaner.exe`.

Linux builds use the same Python source tree and can be packaged into a Linux binary with:

```bash
./scripts/build_linux.sh
```

The Linux executable will be written to `dist/crapcleaner-linux-x86_64`.

---

## Command Line Interface (CLI)

CrapCleaner provides a full CLI for scripted and headless execution:

```bash
# Scan system for reclaimable space
crapcleaner --scan

# Output scan report in machine-readable JSON format
crapcleaner --scan --json

# List all registered cleanup categories
crapcleaner --list-categories

# Perform a dry-run cleanup of safe categories
crapcleaner --clean-safe

# Execute cleanup with Recycle Bin protection
crapcleaner --clean-safe --execute

# Clean specific categories by name or pattern
crapcleaner --clean-category "pip" "npm" --execute

# Find files larger than 1 GB in a directory
crapcleaner --large-files 1GB --root C:\Users\Username

# Find duplicate files in a directory
crapcleaner --duplicates "C:\Users\Username\Downloads" --min-dup-size 10MB

# Print hardware and operating system specifications
crapcleaner --specs
crapcleaner --specs --json

# Run disk traversal performance benchmark
crapcleaner --benchmark
```

---

## Keyboard Shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl + 1` to `8` | Switch view tabs |
| `Ctrl + R` | Start scan |
| `Ctrl + F` | Focus search filter |
| `F5` | Refresh view data |
| `Escape` | Cancel active operation |

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for local development setup, code formatting standards, and testing procedures.

---

## License

Distributed under the [MIT License](LICENSE). Copyright (c) 2026 Patrick Jr.
