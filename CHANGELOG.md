# Changelog

All notable changes to **CrapCleaner** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-08-21

A dedicated Drives section, and a working update check.

### Added

- **Drives**, a section of its own. Each physical disk lists its model, media and bus, and whatever reliability counters the controller actually reports - temperature, wear, powered-on hours, read and write errors. Under it sit that disk's volumes with capacity, filesystem, TRIM state, fragmentation and a per-volume Analyse and Optimise, plus Analyse All and Optimise All across every volume at once. Counters an unelevated session cannot read, and drives that report none, are said once for the machine rather than repeated under every row.
- **Drive maintenance on Linux, not only Windows.** The same three questions are answered by `e4defrag -c`, `fstrim` and `fstrim.timer` where Windows uses `Win32_Volume.DefragAnalysis`, `Optimize-Volume` and the `ScheduledDefrag` task. A filesystem `e4defrag` cannot read is refused by name rather than given a number borrowed from a tool that does not understand it, and e4defrag's 0-100 fragmentation score is labelled a score, because it is not a percentage.
- **Counts in the sidebar.** Reclaimable space, disks, enabled startup entries, running services and pending updates appear as a badge beside the page that owns them. They come from probes that are cheap or already cached, and a page you have opened overrides them - including when it finds nothing, since a stale count is worse than none.
- **The same drive work from the command line:** `--drives` for the inventory with its counters, `--analyze-drive` for fragmentation, and `--optimize-drive`, which is a dry run until `--execute` is given, as the cleanup and memory actions already are. Both accept a drive letter on Windows or a mount point on Linux, and `--drives` supports `--json` and `--export`.
- **An inventory that survives the process.** Drive hardware, storage health and graphics adapters are written to a signature-keyed cache in the configuration directory, so only the first launch after the hardware changes pays for the query. Capacity, free space and uptime are never cached.

### Fixed

- **"Check for Updates" always failed with `0x80244011`** while Windows Settings worked: the searcher was pinned to `ServerSelection = 1`, which is the managed-server option, on a machine with no WSUS server configured. The error map called this a SOAP fault from the update server, which sent anyone reading it looking in the wrong place.
- **Updates Windows Settings offered were reported as none.** Settings aggregates the offers of every registered update service; the search asked only the default one. Every registered service that offers Windows updates is now searched when the default one comes back empty, and the same search drives both the check and the install, so the two can never disagree about what is pending.
- **"3 updates failed to install" alongside an "UP TO DATE" badge.** Windows keeps retrying updates it has already installed, so a failed entry in the update history means nothing on its own. Only an update that is still pending and whose most recent attempt failed is reported.
- **"Open file location" opened Documents, and renaming an entry to `.disabled` opened the "Open with" dialog.** `explorer` only honours `/select` when the switch is unquoted, and an argument list cannot express that once the path contains a space - so Explorer received one quoted string, could not parse it, and fell back to the default folder.
- **"Target file not found: C:\Program".** A `Run` value is not required to quote its executable, and `CreateProcess` resolves an unquoted one by trying successively longer prefixes. Splitting on whitespace made `C:\Program Files\App\app.exe --min` into `C:\Program`. The same prefix walk is now used.
- **The Dashboard labelled a Google Drive mount `LOCAL`** while the Drives tab had it right: `GetDriveTypeW` reports a virtual drive as fixed, and only `QueryDosDeviceW` distinguishes it.
- **`__pycache__` was counted twice** wherever OneDrive redirects a folder that sits inside the user profile: both roots were scanned, and every file below the nested one was found through each. 377 reported `.pyc` files were 191 real ones.
- **The update list rated every driver and definition update "Unspecified".** Microsoft sets a severity only for security bulletins, so the column was describing the state of a field as though it were a verdict on the update.
- **The sidebar was taller than the window is allowed to be.** Nav buttons are a fixed height, so the rail could not compress: it needed 1013 pixels against a 660-pixel minimum window, and everything below the fold was silently cut off. Navigation now scrolls between a pinned brand and footer.

### Changed

- **The drive health card left Storage Breakdown** for the Drives section, where the rest of the per-disk detail now lives.
- **Drives and Services open with what is already known** and refresh in the background, rather than showing an empty page while the query runs. Inspecting services takes about four seconds; the page no longer waits for it before showing anything.
- **PC Specs no longer re-queries the graphics adapters on every visit.** The adapter probe was 96% of the cost of the page and its answer only changes when a driver does, so it is keyed on the installed adapters and their driver versions.
- **App Updates and System Updates no longer share an icon.** They sat next to each other in the sidebar under the same glyph, and the eight-item System group they were part of is now three shorter groups.

## [1.2.1] - 2026-08-20

Self-update could not replace the application.

### Fixed

- **The updater downloaded and verified the new build, then left the old one in place**: the installer script waits for the application to close by polling `tasklist` and piping it through `find`, and Git for Windows ships a GNU `find` earlier in PATH. GNU find reads the process id as a filename, fails, and returns the same exit status the loop uses to mean "it has closed" - so the wait ended immediately and the swap raced the still-running application. The download and its SHA-256 check had already succeeded; only the swap failed, which is why the new build was left sitting beside the old one as a hidden file. `find` and `tasklist` are now called by absolute path, so nothing on PATH can stand in for them.
- **A locked executable no longer abandons the update**: a one-file build keeps a second process alive briefly after the application exits, so the file can still be held at the moment the script tries to move it. The move is now retried for up to a minute rather than being given up on at the first refusal, and if it never succeeds the installed version is left running and the reason is written to the log.
- **The installer script no longer prints "The batch file cannot be found."** when it deletes itself.

## [1.2.0] - 2026-08-20

Safety audit, cleanup manifests, and offline mode.

A second audit of the codebase, implemented. Three defects in this release deleted
files the application had already refused to delete. The first one hardened the deletion paths
the application knew about; this one found the ones it did not. Three defects in this
release deleted files the application had already decided not to delete, and three
categories that are ticked by default were pointed at installed software and user data
rather than at cache. Everything the audit raised is fixed, and the roadmap it proposed
is implemented: cleanup manifests, a restore path, a diagnostics bundle, offline mode,
regrowth rates, a high-contrast mode, bulk duplicate rules, and a generated catalogue.

### Fixed

- **A protected file was refused by name and then deleted with its parent directory**: the cleanup engine validated every file in a directory and skipped the protected ones, and the directory loop that followed removed the whole containing folder - taking the refused files with it. The run reported them as skipped, with the protection reason, after they were already gone. Validation was per file; deletion was per tree. A directory is now unlinked only if processing left it empty.
- **The Recycle Bin path validated nothing at all**: with the Recycle Bin on and no filename pattern, which is what the interface does by default, the walk only counted files and then handed the whole tree to the shell in one call. No file inside was ever checked against the protected-path rules. The walk that measures the tree now validates it at the same time: a clean tree still moves in a single call, and one protected file inside drops it to the per-file path, which refuses that file and keeps the rest.
- **Every Chromium browser cache category matched nothing**: `os.path.join(profile, *sub)` unpacked the string one character at a time, so `"Cache"` resolved to `<profile>/C/a/c/h/e`. All sixteen registered Chrome, Edge, Brave and Opera GX cache entries reported zero bytes and deleted nothing, on both platforms, since 1.0.11. Firefox was unaffected. Browser cache is the most-used category in a disk cleaner.
- **Three categories that are ticked by default were not caches**: the WinGet entry claimed `%LOCALAPPDATA%\Microsoft\WinGet\Packages`, which is where winget unpacks tools installed in portable mode - cleaning it uninstalled them. The Poetry entry claimed the whole `pypoetry\Cache` directory, which holds every project virtual environment Poetry creates unless the user has moved them. The Snap entry claimed `~/snap`, which is each snap's own settings and saved files. All three are narrowed to the directories that actually hold cache, and a test now fails if any default-selected category reaches for them again.
- **A cancelled cleanup reported that it had deleted nothing**: counts were folded into the result only after the walk finished, and cancelling skipped the fold. Three hundred files, cancelled halfway: a hundred and fifty deleted, and the report and history both recorded zero.
- **A folder could measure smaller than the sum of its own children**: in the parallel storage walk a child became runnable before its parent had been recorded, so a child that finished first found no parent and its bytes never reached any ancestor - permanently, since the roll-up runs once per directory.
- **Scan and cleanup disagreed about which files a pattern matched**: the scan's fast path matched extensionless names that the deletion refused, so `catalog`, `backlog`, `changelog` and `dialog` were all counted as `*.log`. The scan promised bytes the cleanup then left behind.
- **A fully expired scan cache was never rewritten**: it was pruned to nothing in memory and left untouched on disk, so every start re-parsed the same dead entries. The file could grow and never shrink.
- **Comparing storage snapshots ignored the size mode they were taken in**: an on-disk-size scan compared against a logical snapshot reported the change of unit as growth, on the one feature whose entire purpose is answering what grew. A mismatch is now refused and explained.
- **The contrast engine could return a worse colour than the one it was given**: when no candidate reached the target ratio it fell back to a fixed extreme, which on some accents replaced readable dark ink at 5.01:1 with white at 3.68:1. It now takes the extreme only when the extreme actually reads better.
- **TRIM was reported enabled on systems where it is disabled**: the Windows query matched any line containing `= 0`, and real output has one line per filesystem, so a machine with NTFS disabled and ReFS enabled read as enabled for the filesystem holding the data.
- **Linux storage health was asserted rather than measured**: every device was reported "Healthy" and every SSD was reported as having TRIM support and TRIM enabled, none of which the underlying tool reports. A failing NVMe was described as healthy. Trim support now comes from the device's discard granularity, trim activity from the mount option or the systemd timer, and health from SMART when it is installed - and anything that cannot be determined says "Unknown" rather than inventing a reassuring answer.
- **Installing an update failed on every Linux distribution except Debian's**: pacman, dnf and snap all need root and only the apt paths asked for it, so the button always returned a permission error on Arch, Fedora and openSUSE. Two separate implementations of "list available updates" also disagreed with each other; there is one now.
- **Opening a Linux settings or services window froze the application for five seconds, killed the window, and reported success**: the launcher waited on a process it should have detached from, hit its own timeout, terminated it, and then said "Opened".
- **The window froze for two seconds whenever a background probe was still running**: every worker in the application overrides its thread body and never runs an event loop, so the quit request could not do anything and the call degraded to a blocking wait on the interface thread - at the head of twenty-seven refresh and action handlers. Nineteen of the twenty-seven workers had no way to be interrupted at all, so closing during a Windows Update check hung and then tore down a thread that was still running.
- **Recycling a large selection left the window not responding**: the Duplicates and Large Files views deleted inline in the button handler, with no progress and no cancel.
- **History rows pointed at the wrong run once the table was sorted**.

### Security

- **A contributor avatar URL was passed to the network layer unchecked**: the URL comes from the API response or from a cache file in the user's own configuration directory, and no scheme, host or size was enforced. Anyone able to write that file could have had arbitrary URLs opened, `file://` included. Restricted to GitHub over HTTPS, with the response capped.
- **Opening the Updates tab ran `sudo apt update`**: a read-only check mutated the package lists on any machine with a passwordless sudo rule. Listing upgradable packages reads the lists apt already has.
- **Package names scraped from command output were appended to a command running as root**: a name beginning with a dash is read as an option by apt and pacman. Every id is now shape-checked before it can reach an elevated package manager.
- **The last `shell=True` call is gone**, along with the PATH and working-directory lookup it implied.
- **Self-updating no longer fights the package manager that installed it**: a copy installed through WinGet, Scoop, Chocolatey, Flatpak or Snap is detected and refused with that manager's own upgrade command, instead of silently replacing itself and leaving the manager's records stale. And a failed swap can no longer leave nothing behind: the target is proved replaceable before the application exits, and both installer scripts restore and report rather than exiting into an empty directory.
- **Every CI job now declares the token scope it needs.** Five jobs inherited the repository default; only the two publishing jobs hold write access.

### Added

- **A record of what a cleanup actually removed**: every run writes a manifest - each path, its size, and whether it went to the Recycle Bin or was removed permanently - kept for the last twenty runs. History shows it per run, and for a run that used the Recycle Bin, *Restore this run* lists the exact paths and opens the bin. Neither Windows nor the FreeDesktop trash exposes an undo this application can call, so it does not pretend to have one. The manifest is a list of the user's own paths: it is never logged, and never leaves the machine.
- **A diagnostics bundle**: one file with version, platform, capability report, drive summary and the tail of the log, with every path reduced to its root. *Save Diagnostics Bundle…* on the Help page, or `crapcleaner diagnostics`.
- **Offline mode**: one setting that stops the update check, the contributor fetch, the package-manager queries and the hostname lookup. Everything that would have gone to the network says it was skipped, rather than failing as though the network were down.
- **How long ago a category was cleaned, and how fast it comes back**: "regrows about 400 MB per week", from the run history. Where there is not enough history it says so instead of showing zero, which is the honest answer to whether cleaning something is worth it.
- **A high-contrast mode**: a setting that routes the *active* palette through the contrast engine at a stricter 7:1 ratio, rather than being one theme among forty-five. Across every shipped theme, 663 of 675 colour pairs now reach AAA.
- **One keep-rule across every duplicate group**: keep the first, oldest, newest, shortest path, or the copy in a folder you pick - applied to all groups at once, with the resulting selection shown before anything moves. The per-group dialog only ever reached one group at a time, and groups past the display cap could not be acted on at all.
- **A generated category catalogue**: `scripts/generate_category_catalogue.py` builds a browsable page from each category's own description of what it contains, why it grows, why it is safe to delete, and what happens afterwards. Generated, so it cannot drift from the application. Filling it in found that a quarter of the categories had never had that metadata written.
- **`crapcleaner history --manifest`** to list what a given run removed.

### Changed

- **Accessibility is enforced rather than remembered**: a test walks every view and dialog and fails on any interactive control that has neither an accessible name nor visible text. Two hundred and twenty-two controls, none unnamed; the exemptions are two documented rules rather than a list of names.
- **Released binaries are built from pinned tooling**: PyInstaller and Qt were previously whatever pip resolved on the morning of the build, so two releases a week apart could carry different Qt versions with no record of which. `uv.lock` is removed - nothing read it.
- **The release path verifies what it publishes**: the Linux binary is now executed before release rather than only built, lint and type checks run on tag, a rebuilt release regenerates the checksum file users are told to verify against, and every binary carries build provenance linking it to the commit and workflow that produced it.
- **Release notes fail loudly** rather than silently publishing the newest version's notes under an older tag.
- **The test suite gained a configuration**: a bare `pytest` at the repository root collected whatever it found, an unrecognised marker did nothing, and warnings passed unnoticed. Coverage is measured by branch now. Three guards that asserted only that certain strings appeared in a workflow file - and passed while the bug they named was live - now parse the workflow.
- **Comments are 59% fewer**: narration, numbered build outlines and decorative banners removed across the codebase; the rationale comments - platform quirks, measured performance decisions, approaches tried and rejected - kept and compressed. Three were stale rather than verbose and described a Studio that no longer looks like that.
- **`pyproject.toml` carries the metadata a published package needs** - readme, licence, classifiers, project URLs - and a windowed entry point so a pip-installed launch does not open a console. Nothing is published yet.
- Dead code removed: a duplicate worker, a superseded file scanner, and two configuration keys that were written to every settings file and read by nothing.

## [1.1.0] - 2026-08-20

Codebase audit, self-update and live theme editing.

The 2026-08-19 audit, implemented, and the features it recommended.

Deletion outside the cleanup engine now goes through the same protected-path layer; the shipped
executable honours command-line arguments and carries an icon and version metadata; the
Storage view measures the tree once instead of three times; Linux gets real gaming and
GPU cache coverage. Crash dumps, storage snapshots, scheduled scans, verified in-place
updates, sub-commands and file-level review are new. Every colour pair the interface
draws now meets WCAG AA on every theme, and changing a theme is four and a half times
faster than it was, which is what makes editing one with the whole window following
along possible.

### Fixed
- **Windows 11 was reported as Windows 10**: Microsoft never changed the registry's `ProductName`, so it reads "Windows 10 Pro" on an 11 machine and both the PC Specs page and the About page repeated it. The build number is the only thing that distinguishes them, and it is already read.
- **The About page described a different application**: four of its five facts were string literals. Platform said "Windows 10 / 11 / Linux (64-bit)" on every machine including the Linux ones, Python said 3.12 while the project supports 3.10 and up, and the toolkit row said "Fluent 2 Dark Theme" - written before the 44 themes and the Studio existed. It now reports what is running. "Zero Telemetry: 100% local" went too: opening that page asks GitHub for the contributor list. Nothing about the user is sent, which is the claim worth making, so it makes that one.
- **The contrast engine tries both directions**: it chose to lighten or darken from the background's luminance and gave up if that direction could not reach the ratio. `#3b82f6` sits at 0.22 luminance, just inside "dark", so white could only be lightened - it is already white - and the failing colour was returned unchanged. Text was also corrected against the single background it fared worst on, which is only sound while the correction can move one way; it is now moved to the nearest lightness that clears every background it is drawn on.
- **A duplicate group always keeps a copy**: "Select All" in the duplicate review dialog checked every copy, and confirming recycled all of them - which removes the content itself, since a group only exists because those files are identical. Confirmation is refused while nothing is kept.
- **Duplicate and large-file deletion is validated**: both views called the filesystem helpers directly, so the protected-path rules that guard category cleanup never ran. Discovery no longer offers protected content at all, and every deletion routes through one core helper that validates each path and reports what it refused.
- **Pattern-limited cleanup keeps non-matching files**: a target such as `Prefetch` with `*.pf` deleted whole sub-directories outright, taking unrelated files with them and skipping the per-file safety check. Only matching files are removed, and a directory goes only if processing left it empty.
- **Windows service names cannot alter a command**: start, stop, restart and startup-type changes interpolated the service name into a PowerShell command string. The name is passed through the environment instead, so a name containing a quote is data rather than syntax.
- **Memory actions say what they do**: the standby purge documented one system call and made five; the working-set flush made an undocumented system-wide call, now removed. "Flush all available memory" reported success even when every step failed. The figure shown afterwards is the change in system-wide available memory, labelled as such and no longer clamped at zero.
- **Damaged settings are preserved**: an unreadable `config.json` silently reset to defaults and was then overwritten, taking the user's exclusion list with it. The file is kept as `config.json.corrupt` and the window says so.
- **Cleanup preview totals are complete**: the walk stopped at the 500-item display cap, so a category with 50 000 files reported the size of the first 500.
- **"Find big files" stops skipping game folders**: the skip list was matched as a substring of the whole path, so `Games\MyGame\WindowsNoEditor` was skipped along with `C:\Windows`.
- **"Old files" returns the oldest files**: it returned whichever files the traversal reached first, then sorted those.
- **Scans say when they were cut short**: hitting the file budget silently capped the total, and the partial figure could be cached as if complete.
- **Hardlinks are not counted as reclaimable**: additional names for one file were reported as duplicate copies whose deletion would free nothing.
- **The scan cache and history log are bounded**: neither ever removed an entry.
- **The frozen executable honours arguments**: the packaged launcher ignored `sys.argv`, so every documented command-line option opened the interface instead. It also shipped with no icon and no version metadata.

### Added
- **See every file before it goes**: *Review files…* in the cleanup confirmation lists the exact paths a cleanup would remove, and unticking one leaves it alone. The manifest engine and its per-item selection have existed since 1.0.3 and only the command line could reach them.
- **Crash dumps**: application crash dumps and kernel `MEMORY.DMP` files are now a cleanup category and a command (`crapcleaner crash-dumps`), grouped by the application that wrote them. The analyzer was written and tested but unreachable; a full memory dump is routinely the largest removable file on a Windows system.
- **Changes since last scan**: each storage scan is remembered, so the next one reports which folders grew and by how much - the question people actually arrive with. `crapcleaner storage <path> --compare`, or the new section in the Storage view.
- **On-disk size**: an optional mode measuring what files occupy rather than their length, so totals line up with the free space the OS reports for compressed, sparse, and very small files. `--allocated`, or the checkbox in the Storage view.
- **Scheduled scans**: Settings -> Scan Performance sets one up, or `crapcleaner schedule enable --at 18:00` from the command line. Either registers a Task Scheduler entry or a systemd user timer, and the section reports what the operating system actually has registered rather than what was last asked for. A scheduled run only ever scans. `core/scheduler.py` was dead code; it is now the real thing.
- **Updates that update**: *Check for Updates* now downloads the new release, verifies its SHA-256 against the published checksums, replaces the application, and starts it again. The running version is only replaced after the new one is downloaded and verified, the old binary is kept until the new one starts, and a failed swap restores it. Also available as `crapcleaner update install`.
- **Sub-commands**: `crapcleaner scan`, `clean`, `storage`, `update`, `schedule` and the rest, with per-command help. Every existing flag still works exactly as before.
- **Saved themes are real themes**: *Save to Gallery…* in the Custom Theme Studio writes the current colours to a theme file. It appears in the gallery under *Custom*, and right-clicking offers *Show the theme file* and *Delete*. Editing is done in the file, which reloads as it is saved.
- **A theme is yours unless we shipped it**: provenance is decided by an explicit list of the themes CrapCleaner ships, not by which directory a file sits in or what its own `category` field says. Anything else appears under *Custom* and can be edited, shown, or deleted from the gallery.
- **Themes reload while you edit them**: the application watches both theme directories, so saving a file in an editor restyles the window immediately. Editing a theme no longer means closing and reopening the application repeatedly. A file that cannot be parsed is skipped and the rest keep working; one naming a category that does not exist is filed under a category that does, rather than loading but being unreachable in the gallery.
- **Themes are data**: the 44 palettes moved out of a 2 100-line module into JSON files. A file dropped into `<config dir>/themes` adds a theme with no code change, and an invalid one is skipped with a warning instead of breaking start-up.

### Changed
- **Editing a theme restyles the whole window, not just the preview**: the interface follows the edit a moment after the last change, so a theme is judged on the application rather than on a mockup of it. The preview keeps up in real time while a slider is moving and the window is restyled once, when the movement stops. *Restyle the window as I edit* turns it off.
- **Changing a theme is 4.6x faster**: the stylesheet was set on the `QApplication`, which re-polishes every widget of every top-level at about 1.2ms each; the identical sheet set on the window costs 0.3ms - 243ms against 1115ms for the same 845 widgets. It is not the stylesheet's size, a one-rule sheet cost the same. Every dialog in the application is parented inside the window, so it inherits either way, and a test now fails if an unparented one appears.
- **The Studio keeps up while you drag**: the colour maths ran about 1,200 times per edit on two dozen distinct values and is now cached (palette generation 3.57ms to 0.02ms), the preview restyled each of its mock widgets separately and is now one sheet like the application itself, and a drag redrew once per notch and is now capped at thirty a second with the value it ended on always landing. A full-range drag went from about 4.3 seconds of blocking to 18 milliseconds.
- **The Custom Theme Studio shows the application, not three boxes**: the preview is a working miniature of the window - sidebar, header, figures, a list, badges and buttons - above every palette token with its value. The three tabs it replaces each hid two thirds of the preview behind a click and stretched whichever one was showing into empty space. The page fills the page: a trailing stretch in the settings layout was leaving the bottom half of the view blank whatever the card did.
- **Start from a theme you already have**: any theme can be loaded into the Studio and edited. One saved from the Studio comes back exactly as it was saved, because the settings that produced it are recorded in the file. Anything else - the themes we ship, a file written by hand - has no recipe, so its accent and canvas are taken and the rest generated; the Studio says which of the two it did.
- **Readability, beside the controls**: every colour pair the interface actually draws, rated against WCAG AA, updating as the theme is edited. The soft badge tints are translucent, so they are composited over the card they sit on before being measured - comparing the raw `rgba()` string against its own accent reported about 1:1 for every theme ever made.
- **A Fix button**: where a pair falls short, it sweeps the three sliders and takes the combination nearest to what was set, then says which ones it moved - so the result is still the theme that was being designed, and Reset undoes it. It leaves the accent, canvas and mood alone: those are the design, the sliders are the tuning. Across 663 failing configurations it clears every one.
- **Background Depth is adjustable**: every saved theme carries this value and the Studio had no control for it, so the only way to change it was to edit a theme file by hand.
- **Editing the Studio no longer has to restyle the whole window**: every swatch click and slider release restyled the application and wrote settings to disk. It still does by default, because watching the real interface change is the point, but *Restyle the window as I edit* turns it off.
- **The window opens at the size the dashboard was laid out for**: 1460x1160 rather than 1200x780, which clipped the drive cards and squashed the sidebar footer. It shrinks to fit a smaller screen and is centred on it. The minimum is 1200x660 - not the default, because 1160 pixels of height does not fit a 1080p display once the taskbar is accounted for, and a floor that tall would force the window off the screen on the most common resolution there is.
- **One way to share a theme**: *Copy JSON* and *Import…* have gone from the Custom Theme Studio. A theme is a file now - *Save to Gallery…* writes it, and sharing one means sending it.
- **The Storage view measures the tree once**: the hierarchy, the file-type breakdown and the old-file list each walked the same tree in turn. They now share one traversal - 2.6x faster on a warm 11k-file tree, 3.3x on a larger one - and drilling into a folder is served from what the scan already measured rather than walking it again (290 ms to 0.4 ms).
- **Linux gaming and GPU coverage**: these categories built Windows paths that resolve under `~/.cache` on Linux and matched nothing, so both groups always reported zero. Steam (native, `.steam` and Flatpak), Heroic, Lutris and Bottles are covered, along with the Mesa shader cache, NVIDIA GL and compute caches, and Steam/Proton shader caches.
- **Every built-in theme meets WCAG AA**: the contrast engine was applied to generated custom themes and not to the 44 built-in palettes. Eleven had secondary text below AA on a hovered card, the worst at 1.21:1. Only text colours moved.
- **Start from a theme you already have**: any theme can be loaded into the Studio and edited. One saved from the Studio comes back exactly as it was saved, because the settings that produced it are recorded in the file; anything else has no recipe, so its accent and canvas are taken and the rest generated - and the Studio says which of the two it did rather than implying a copy.
- **Button and badge labels are derived from what they sit on**: the label on a coloured button was `#ffffff` whatever colour the button was, which fails on 37 of the 44 themes we ship and cannot be fixed from the Studio - darkening an accent enough for white to read breaks the accent badge instead. A badge label was the role's own colour on a 15% tint of itself: pale on pale, failing on 26 themes for the accent badge and 39 for the critical one. Both now come from the colour behind them, moving lightness only, so the label keeps its hue and every theme reads.
- **The About page no longer freezes the window**: it fetched the contributor list and every avatar synchronously while the page was being built.
- **A log file, at last**: `crapcleaner.log` in the config directory, `--verbose` for detail and `--log-path` to find it. Failures that used to disappear into a bare `except: pass` now leave a trace.
- **Releases are gated on the version matching the tag**, rebuilt release assets get fresh checksums, and CI runs the built binary rather than only checking that the file exists.
- **A headless Linux session is reported** rather than silently rendering the interface offscreen.

## [1.0.11.1] - 2026-08-19

Storage analysis runs in parallel and streams results as it measures, scan progress reports the category actually running, and Linux app caches cover Flatpak and Snap installs.

### Fixed
- **Scan appeared to hang on a fast category**: every category was reported at queue time, and all 89 are queued within milliseconds, so a long-running directory walk was displayed under the name of whichever fast category happened to be queued in front of it - most visibly "Conda caches", which finishes in under a millisecond even when Conda is installed. Progress is now reported immediately before waiting on each category, so the name shown during a stall is the category doing the work. Categories whose targets do not exist were already skipped without any filesystem walk, and still are.

- **Linux application caches missed for Flatpak and Snap installs** (#7): the Discord, Slack, and Spotify categories only knew the native XDG paths, so a sandboxed install - where the data lives under `~/.var/app/<app-id>/` or `~/snap/<name>/current/` - was scanned as if the app were not installed. All three install layouts are now covered for each app.
- **"Recycle Bin" shown on Linux**: the trash entry lived in the Windows provider, so a Linux install listed "Recycle Bin" under a Windows group with a description citing the Windows API. It now has its own provider and is presented as "Trash" under System on Linux, keeping the `recycle_bin` id so existing settings still apply. Emptying already worked on both platforms.

### Changed
- **Storage analysis is parallel and streams results as it measures**: enumeration fanned out only at the top level, so one oversized subtree - `AppData` is routinely two thirds of a user profile - was measured by a single thread while the rest of the pool sat idle. Every directory is now its own unit of work pulled from a shared queue by 24 workers, which on a cold cache raised throughput from 16k to 52k files/s (3.2x), measured on two interleaved halves of the same tree so both started uncached. Totals are aggregated as results arrive instead of summed at the end, so the view fills in about half a second and keeps growing while the scan runs rather than staying blank until the whole tree is measured. Drilling into a folder stops the live updates, so the view being read is never replaced underneath.
- **A tag push now runs the test suite before anything is published**: CI only triggers on branch pushes, so tagging a release built and published without any test gate - which is how v1.0.11 was first published from a commit whose Linux tests were failing. The release workflow now runs the suite on Windows and Linux first, and the build jobs depend on it.
- **Linux release binaries build on Ubuntu 22.04**: a PyInstaller binary links against the build machine's glibc, so building on ubuntu-latest produced a binary that refuses to start on any older distribution.
- **mypy runs in CI**: it was a project gate enforced only locally, so a type error could land on master with a green tick.
- **Broken Discussions link**: the issue chooser pointed at `PatrickJr/crapcleaner` (missing the "n"), a 404 for anyone who clicked it.
- **Stale workflow_dispatch default**: manually running the release workflow defaulted to rebuilding `v1.0.8`; it now defaults to the tag the run was triggered from.
- **Issue templates cover Linux**: the bug report asks for the distribution, how CrapCleaner was installed, and how the affected application was installed (distro package, Flatpak, Snap, AppImage) - the last being the usual cause of "category not detected". The category request asks for paths per platform and install method.
- **CI hygiene**: superseded runs are cancelled instead of finishing alongside the run that matters, pip downloads are cached, the frozen-build step asserts a binary was actually produced, GitHub Actions are current (no more Node 20 deprecation warnings), and Dependabot keeps them that way.
- **PR checklist**: covers mypy, Linux, and the safety expectations for new cleanup targets.
- **Faster directory traversal**: the duplicate finder, installer scan, large-file scan, AI data scan, and the Python artifact finders each re-checked every directory for being a symlink, which `walk_safe` already guarantees it never yields. Removing that redundant `lstat` per directory cuts roughly a quarter off the traversal time (32,500 directories: 7.4s to 5.6s), with link, junction, and loop protection unchanged.

---

## [1.0.11] - 2026-08-19

Engineering audit implementation: correctness and safety fixes, a modular GUI views package, faster duplicate hashing and storage analysis, wider cleanup coverage, and machine-readable CLI progress.

### Fixed
- **Duplicate cleanup category IDs**: `directx_shader_cache` now has a single owner (Windows provider) and the .NET provider's JetBrains entry became `resharper_caches`, so no two categories share an ID or scan the same path twice. Enforced by tests.
- **Individual file cleanup targets**: a target pointing at a single file (stray `.pyc` files) is now sized, previewed, and deleted correctly through the normal pipeline instead of being silently skipped.
- **Platform-specific categories**: Windows-only targets are no longer registered on Linux and vice versa. This covers the application providers (winget, Chocolatey, Scoop vs apt, dnf, pacman, Flatpak, Snap) and the Windows system provider, so a Linux install no longer lists Prefetch, CBS logs, or Windows TEMP. Emptying the trash stays available on both platforms.
- **Windows drive formatting**: drive letters render one colon (`Drive C:`), Linux mount points are printed unchanged.
- **Storage analyzer traversal**: the analyzer uses the shared reparse-point guard and skips junctions and symlinks instead of resolving through them, so data that lives on another volume is never billed to the scanned drive.
- **Recursive CSV storage export**: a list-rooted storage report now exports every descendant instead of stopping at the top level.
- **Linux storage health**: capacity comes from byte-accurate `lsblk -b` output and free space is correlated through the device's mount point. An unmounted device keeps its real capacity rather than reporting zeros.
- **Cold cleanup preview reported zero**: `crapcleaner --cleanup-preview` runs without a prior scan, so categories that discover their targets through a finder (`__pycache__`, stray `.pyc`, Python tool caches, AI models) previewed as empty while the cleanup would have removed thousands of files. The preview now resolves those finders when no scan data exists.
- **Blank volume label and filesystem on Windows**: PC Specs printed drives with no label or filesystem because `get_drive_info` never queried them. Both now come from `GetVolumeInformationW`, and a drive that cannot be queried reports blank rather than a placeholder.
- **Ruff and mypy**: both pass with zero errors across the package, with no suppressions or broad `Any` casts added.
- **PyInstaller packaging**: stale hidden imports were replaced with modules that actually exist, and `onedir` builds a real folder distribution (`EXE` + `COLLECT`) instead of silently producing a onefile build. Both build scripts pass their mode through and report the matching output path.

### Added
- **Running-browser detection before cleanup**: one process listing identifies every relevant browser; the confirmation dialog, status bar, and CLI warn that locked cache files will be skipped. Browsers are never terminated, and a cleanup that skipped locked files is reported as partial rather than complete.
- **Wider browser coverage**: Thorium on Windows and Linux, Floorp on Linux, alongside the existing Chromium and Firefox derivatives. Only cache directories are targeted.
- **Wider developer cache coverage**: shared `sccache` and Zig compiler caches, project-local `.ruff_cache`, `.mypy_cache`, `.pytest_cache`, and `.tox` folders discovered through the existing single scan-root walk, and the Docker Buildx cache exposed as a confirmed `docker buildx prune` action rather than a file delete.
- **Vendor-neutral GPU telemetry**: AMD and Intel load, temperature, and VRAM through Linux DRM sysfs, NVML retained for NVIDIA, and any Windows display adapter contributing its name and VRAM size. A metric the hardware does not expose is shown as `N/A` instead of a fabricated zero.
- **Wider local AI model discovery**: Jan.ai, ComfyUI, and text-generation-webui model stores in their conventional locations. Models remain inspection-only and are never auto-selected.
- **`--progress-jsonl` streaming CLI progress**: scans and cleanups emit one standalone JSON object per line covering start, per-category progress and results, warnings, errors, cancellation, and completion (including a `partial` flag). Standard output is unchanged without the flag.

### Changed
- **GUI views modularized**: the 9,000-line `gui/views.py` became a `gui/views/` package with one module per major view plus a shared widgets module. Public imports and lazy view creation are unchanged.
- **Centralized subprocess execution**: `run_command` returns a typed `CommandResult` with consistent timeout, working-directory, and environment handling, and every capturing subprocess call site now goes through it, so a failed command can never look like empty-but-successful output.
- **Parallel duplicate hashing**: full SHA-256 hashing runs on a bounded worker pool and consumes results in submission order, keeping grouping deterministic while staying responsive to cancellation.
- **Scan cache invalidation**: continuously rewritten groups (browser caches, Windows Temp) use a short TTL so a stale entry cannot outlive its data, while static categories keep the full TTL.
- **On-demand storage drill-down**: navigating past the analyzed depth measures that folder in a worker and keeps the result, instead of requiring a slower whole-drive pass at a higher depth.

---

## [1.0.10.1] - 2026-08-18

Theme Studio performance optimization, Windows config locking resilience, and release title automation.

### Fixed
- **Theme Studio Slider Performance & Lag**: optimized live theme preview rendering by updating only the actively visible tab (`_update_active_view`) during drag events, reducing per-drag `setStyleSheet` and contrast calculation overhead by over 95%. Bypasses redundant SVG icon and button restyling during active sliding and tunes the application debounce timer to 220ms for fluid 60+ FPS interaction.
- **Windows Config Lock Collision (`PermissionError: [WinError 5]`)**: resolved access denied errors during rapid settings saves by eliminating redundant duplicate saves in custom theme builder and implementing PID/nanosecond unique temporary files, exponential retry backoff, and direct-write fallbacks in `save_settings`.

### Added
- **Automated Descriptive GitHub Release Titles**: enhanced `scripts/extract_changelog.py` and `.github/workflows/release.yml` to automatically extract release headlines from `CHANGELOG.md` and populate descriptive release titles during GitHub Actions publication.

---

## [1.0.10] - 2026-08-18

Custom Theme Studio release: perceptual color theory engine, 6 harmony mood styles, 15 designer presets, magic dice generator, JSON theme import/export, and dedicated Settings sub-navigation tabs.

### Added
- **Custom Theme Studio**: introduces a dedicated workspace inside Settings enabling users to design, fine-tune, and apply personalized themes without manual configuration of dozens of individual hex codes.
- **Perceptual Color Theory Engine (`color_engine.py`)**:
  - Implements hue-dependent brightness bias compensation (`hue_lightness_bias`) and perceptual lightness tuning, ensuring high-luminance hues (amber, yellow, lime) avoid blinding glare while deep blues and violets maintain rich vibrancy.
  - Enforces strict WCAG 2.1 AA/AAA contrast guidelines (minimum 7:1 text contrast and 4.5:1 UI contrast) with automated lightness correction (`ensure_contrast`).
  - Generates complete 27-token palettes mapping chosen signature colors across stratified background levels (`window`, `panel`, `surface`, `surface2`, `elevated`, `border`, `border2`), semantic states (`success`, `warning`, `danger`, `review`, `info`, `selection`), and typography.
- **6 Palette Harmony Mood Styles**:
  - `Cohesive` (default balanced surface tinting with 14% primary saturation)
  - `Vibrant` (high-energy saturated surfaces and neon accents)
  - `Muted` (subdued slate undertones for low-profile visual focus)
  - `OLED Pure` (true `#000000` deep black canvas with stratified dark panels and glowing accent highlights)
  - `Pastel` (soft, airy low-saturation tones)
  - `Minimal` (clean monochromatic neutral greys with single accent focus)
- **15 Curated Designer Color Presets**: one-click curated palettes (*Sapphire Blue*, *Emerald Forest*, *Cyber Violet*, *Sunset Amber*, *Crimson Velvet*, *Rose Gold*, *Hyper Cyan*, *Deep Slate*, *Mint Sage*, *Solar Orange*, *Royal Indigo*, *Cherry Blossom*, *Arctic Frost*, *Matrix Lime*, *Espresso Gold*).
- **Color Harmonies & Magic Dice Generator**:
  - `generate_color_harmonies` computing Analogous ($H \pm 30^\circ$), Complementary ($H + 180^\circ$), Triadic ($H \pm 120^\circ$), and Split-Complementary variations.
  - "Surprise Me (Magic Dice)" rolling harmonious, randomized palettes across curated hues and mood formulas on demand.
- **Theme JSON Export & Import**:
  - Serialization and parsing tools (`export_custom_theme_json`, `import_custom_theme_json`) with clipboard copy and modal import dialog for sharing themes.
- **Interactive Multi-View Live Preview**:
  - Live preview card featuring switchable views: Mockup Overview, Clean-up Queue Table, and 27-Token Palette Matrix with live contrast ratio badge meter (`AAA`, `AA`, `LOW`).
- **Dedicated Sub-Navigation Tabs in Settings**:
  - Clean separation into `Theme Gallery` and `Custom Theme Studio`, providing full viewport height for both browsing 40+ built-in themes and designing custom themes.
  - Added "Custom Studio" shortcut button on the active theme hero banner.

### Fixed
- **Table Column Sorting Recursion Error**: resolved `RecursionError` in PySide6 `NumericItem` during table column sorting by isolating numerical sort values to `Qt.ItemDataRole.UserRole + 99` and handling string fallbacks safely.
- **Mnemonic Accelerator Underscore Artifacts**: escaped ampersands in button labels (`Apply && Save Custom Theme`) and enforced `Qt.TextFormat.PlainText` on labels to prevent unwanted mnemonic accelerator parsing.
- **Live Theme Application on Color Pick**: instant real-time visual application across the entire application upon selecting a color or changing tuning sliders.

---

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
