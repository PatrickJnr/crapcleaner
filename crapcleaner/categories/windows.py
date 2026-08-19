"""Windows system cleanup categories."""

import os

from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.utils.platform import (
    get_local_appdata,
    get_program_data,
    get_windows_dir,
    is_windows,
)


def get_categories() -> list[CleanupCategory]:
    local = get_local_appdata()
    windir = get_windows_dir()
    temp = os.environ.get("TEMP", os.path.join(local, "Temp"))

    categories = []

    categories.append(
        CleanupCategory(
            id="windows_user_temp",
            name="User TEMP",
            group="Windows",
            description="Temporary files created by user applications in the user TEMP folder.",
            safety_level=SafetyLevel.SAFE,
            what_it_contains="Unpacked archives, temporary caches, and working files left by closed applications.",
            why_it_grows="Applications frequently create temporary files during install or runtime without deleting them.",
            why_safe_to_delete="Active files in use by running processes are automatically skipped; inactive temporary files can be safely removed.",
            regeneration_behavior="Applications will recreate required scratch files on demand.",
            reversible=True,
            targets=[CacheTarget(path=temp)],
        )
    )

    categories.append(
        CleanupCategory(
            id="windows_temp",
            name="Windows TEMP",
            group="Windows",
            description="System-wide temporary files under C:\\Windows\\Temp. Requires administrator privileges to remove fully.",
            safety_level=SafetyLevel.SAFE,
            requires_admin=True,
            what_it_contains="System-level installers, Windows Service temporary scratch files, and setup payloads.",
            why_it_grows="Windows services and installers accumulate temp files over time.",
            why_safe_to_delete="Files not in use by system processes can be safely reclaimed.",
            regeneration_behavior="Services generate new scratch files when needed.",
            reversible=True,
            targets=[CacheTarget(path=os.path.join(windir, "Temp"))],
        )
    )

    categories.append(
        CleanupCategory(
            id="windows_error_reports",
            name="Windows Error Reporting",
            group="Windows",
            description="WER report queue and archives (application crash reports sent to Microsoft). Safe to remove.",
            safety_level=SafetyLevel.SAFE,
            what_it_contains="Historical diagnostic crash logs and report queues for Windows Error Reporting.",
            why_it_grows="Every application crash or hang generates a diagnostic report package.",
            why_safe_to_delete="Historical reports that have been sent or archived have no runtime dependencies.",
            regeneration_behavior="New reports are recorded only when new application faults occur.",
            reversible=True,
            targets=[
                CacheTarget(
                    path=os.path.join(
                        get_program_data(), "Microsoft", "Windows", "WER", "ReportQueue"
                    )
                ),
                CacheTarget(
                    path=os.path.join(
                        get_program_data(),
                        "Microsoft",
                        "Windows",
                        "WER",
                        "ReportArchive",
                    )
                ),
                CacheTarget(path=os.path.join(local, "Microsoft", "Windows", "WER")),
            ],
        )
    )

    categories.append(
        CleanupCategory(
            id="windows_crash_dumps",
            name="Crash dumps",
            group="Windows",
            description="User-mode crash dumps written by Windows Error Reporting to %LOCALAPPDATA%\\CrashDumps.",
            safety_level=SafetyLevel.SAFE,
            what_it_contains="Memory dumps (.dmp) created when user applications crash.",
            why_it_grows="Unstable or crashing desktop programs write 50 MB - 2 GB memory dump files per crash.",
            why_safe_to_delete="Crash dumps are purely diagnostic and are not required for program execution.",
            regeneration_behavior="No regeneration unless an application crashes again.",
            reversible=True,
            targets=[CacheTarget(path=os.path.join(local, "CrashDumps"))],
        )
    )

    categories.append(
        CleanupCategory(
            id="windows_minidumps",
            name="Minidumps",
            group="Windows",
            description="Kernel minidump files in C:\\Windows\\Minidump. Requires administrator privileges. Safe to remove.",
            safety_level=SafetyLevel.SAFE,
            requires_admin=True,
            what_it_contains="Blue Screen of Death (BSOD) kernel crash dump headers.",
            why_it_grows="Created by the Windows kernel upon system stop errors.",
            why_safe_to_delete="Historical BSOD records are useful for debugging past crashes but do not affect system stability.",
            regeneration_behavior="Created only if another kernel crash occurs.",
            reversible=True,
            targets=[CacheTarget(path=os.path.join(windir, "Minidump"))],
        )
    )

    categories.append(
        CleanupCategory(
            id="windows_cbs_logs",
            name="Windows CBS Servicing Logs",
            group="Windows",
            description="Component-Based Servicing (CBS) logs and persistent servicing records in C:\\Windows\\Logs\\CBS.",
            safety_level=SafetyLevel.LOW_RISK,
            requires_admin=True,
            what_it_contains="Archived Component-Based Servicing logs and Dism logs.",
            why_it_grows="Windows Update and DISM maintenance append detailed servicing records that can grow to several gigabytes.",
            why_safe_to_delete="Old logs can be safely removed; the CBS service will continue logging new events.",
            regeneration_behavior="Windows creates new log files on the next servicing operation.",
            reversible=True,
            targets=[
                CacheTarget(
                    path=os.path.join(windir, "Logs", "CBS"),
                    patterns=("*.log", "*.cab"),
                )
            ],
        )
    )

    categories.append(
        CleanupCategory(
            id="windows_cryptnet_cache",
            name="Cryptnet SSL / TLS Certificate Cache",
            group="Windows",
            description="Cached SSL certificates and revocation lists. Re-fetched from certificate authorities on demand.",
            safety_level=SafetyLevel.SAFE,
            what_it_contains="Cached public certificates, CRLs (Certificate Revocation Lists), and authority metadata.",
            why_it_grows="Browsing websites and verifying signed binaries caches certificate validation chains.",
            why_safe_to_delete="Windows automatically queries certificate authorities to fetch fresh revocation lists as needed.",
            regeneration_behavior="Re-downloaded seamlessly in the background during HTTPS requests.",
            reversible=True,
            targets=[
                CacheTarget(path=os.path.join(local, "Microsoft", "Windows", "INetCache", "IE")),
                CacheTarget(
                    path=os.path.join(local, "Microsoft", "Windows", "INetCache", "Low", "IE")
                ),
                CacheTarget(
                    path=os.path.join(local, "Microsoft", "Windows", "CryptnetUrlCache", "Content")
                ),
                CacheTarget(
                    path=os.path.join(local, "Microsoft", "Windows", "CryptnetUrlCache", "MetaData")
                ),
            ],
        )
    )

    categories.append(
        CleanupCategory(
            id="windows_font_cache",
            name="Windows Font Cache",
            group="Windows",
            description="Cached font metadata and rasterized glyph caches. Rebuilt by the Windows Font Cache Service.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="Rasterized font glyph caches and font table indexes.",
            why_it_grows="Installed fonts and specialized glyphs are cached for fast UI rendering.",
            why_safe_to_delete="Rebuilt automatically by the Windows Font Cache Service.",
            regeneration_behavior="Windows regenerates font caches on application launch.",
            reversible=True,
            targets=[
                CacheTarget(path=os.path.join(local, "FontCache")),
                CacheTarget(path=os.path.join(local, "Microsoft", "Windows", "FontCache")),
            ],
        )
    )

    categories.append(
        CleanupCategory(
            id="delivery_optimization",
            name="Delivery Optimization cache",
            group="Windows",
            description="Peer-to-peer update cache used by Windows Update Delivery Optimization. Rebuilt on demand. Requires administrator privileges.",
            safety_level=SafetyLevel.LOW_RISK,
            requires_admin=True,
            what_it_contains="Cached Windows Update payloads shared between local network machines.",
            why_it_grows="Windows caches completed updates to seed other local PCs.",
            why_safe_to_delete="Deleting the cache frees disk space; updates are already installed.",
            regeneration_behavior="New payloads are cached during subsequent Windows Updates.",
            reversible=True,
            targets=[
                CacheTarget(
                    path=os.path.join(windir, "SoftwareDistribution", "DeliveryOptimization")
                ),
                CacheTarget(
                    path=os.path.join(
                        windir,
                        "ServiceProfiles",
                        "NetworkService",
                        "AppData",
                        "Local",
                        "Microsoft",
                        "Windows",
                        "DeliveryOptimization",
                        "Cache",
                    )
                ),
            ],
        )
    )

    categories.append(
        CleanupCategory(
            id="thumbnail_cache",
            name="Thumbnail cache",
            group="Windows",
            description="Explorer thumbnail and icon cache databases. Rebuilt automatically; some files may be in use and will be skipped.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="Cached thumbnail previews for images, videos, and icons in File Explorer (thumbcache_*.db).",
            why_it_grows="Browsing media folders causes Explorer to generate persistent preview thumbnails.",
            why_safe_to_delete="Does not delete any user images or videos. Windows will regenerate thumbnails on demand.",
            regeneration_behavior="Explorer will re-render thumbnails when you open folders.",
            reversible=True,
            targets=[
                CacheTarget(
                    path=os.path.join(local, "Microsoft", "Windows", "Explorer"),
                    patterns=("thumbcache_*.db", "iconcache_*.db"),
                ),
            ],
        )
    )

    categories.append(
        CleanupCategory(
            id="directx_shader_cache",
            name="DirectX shader cache",
            group="Windows",
            description="Compiled DirectX shader cache. Games and apps recompile shaders on next launch (may cause a temporary stutter).",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="Precompiled GPU shaders from DirectX games and applications.",
            why_it_grows="Games compile shaders to disk to prevent runtime stutter.",
            why_safe_to_delete="Clearing old shaders reclaims space from uninstalled games; active games recompile on launch.",
            regeneration_behavior="Games and DirectX runtimes recompile shaders as needed.",
            reversible=True,
            targets=[
                CacheTarget(path=os.path.join(local, "D3DSCache")),
                CacheTarget(path=os.path.join(local, "Microsoft", "DirectXShaderCache")),
            ],
        )
    )

    categories.append(
        CleanupCategory(
            id="windows_update_cleanup",
            name="Windows Update cleanup",
            group="Windows",
            description="Runs DISM /StartComponentCleanup to remove superseded Windows Update components. Requires administrator privileges.",
            safety_level=SafetyLevel.LOW_RISK,
            requires_admin=True,
            action="dism_start_component_cleanup",
            what_it_contains="Superseded Windows Update components in the WinSxS component store.",
            why_it_grows="Windows keeps previous versions of updated system DLLs for uninstallation rollback.",
            why_safe_to_delete="Uses Microsoft's official DISM servicing tool to safely discard obsolete package versions.",
            regeneration_behavior="Current update components are preserved; only obsolete versions are pruned.",
            reversible=False,
        )
    )

    categories.append(
        CleanupCategory(
            id="windows_update_downloads",
            name="Old Windows Update downloads",
            group="Windows",
            description="Downloaded Windows Update payloads in SoftwareDistribution\\Download. Windows re-downloads as needed. Requires administrator privileges.",
            safety_level=SafetyLevel.LOW_RISK,
            requires_admin=True,
            what_it_contains="Downloaded update installation binaries and staging files.",
            why_it_grows="Windows Update stores downloaded update packages in the Download folder during servicing.",
            why_safe_to_delete="After updates are applied, old downloaded installation packages can be safely purged.",
            regeneration_behavior="Windows re-downloads fresh update packages on the next update check.",
            reversible=True,
            targets=[CacheTarget(path=os.path.join(windir, "SoftwareDistribution", "Download"))],
        )
    )

    categories.append(
        CleanupCategory(
            id="windows_upgrade_logs",
            name="Windows upgrade logs",
            group="Windows",
            description="Setup log files from Windows upgrades and servicing (Panther). Requires administrator privileges.",
            safety_level=SafetyLevel.LOW_RISK,
            requires_admin=True,
            what_it_contains="Diagnostic logs from previous Windows feature upgrades and installations.",
            why_it_grows="Windows setup logs every step during OS upgrades into the Panther directory.",
            why_safe_to_delete="Historical upgrade logs have no operational effect on running systems.",
            regeneration_behavior="New logs created only during future Windows setup operations.",
            reversible=True,
            targets=[CacheTarget(path=os.path.join(windir, "Panther"))],
        )
    )

    categories.append(
        CleanupCategory(
            id="windows_prefetch",
            name="Windows Prefetch data",
            group="Windows",
            description="Application prefetch data in C:\\Windows\\Prefetch. Windows regenerates prefetch traces over time. Requires administrator privileges.",
            safety_level=SafetyLevel.REVIEW,
            requires_admin=True,
            what_it_contains="Prefetch execution traces (*.pf) used by Windows to optimize initial application launch.",
            why_it_grows="Windows logs initial disk read patterns for every launched executable.",
            why_safe_to_delete="Clears prefetch traces for uninstalled applications; active programs regenerate traces over time.",
            regeneration_behavior="Windows rebuilds prefetch files automatically during program execution.",
            reversible=True,
            targets=[CacheTarget(path=os.path.join(windir, "Prefetch"), patterns=("*.pf",))],
        )
    )

    previous_installs = []
    for candidate in (
        os.path.join("C:", "Windows.old"),
        os.path.join("C:", "$WINDOWS.~BT"),
        os.path.join("C:", "$WINDOWS.~WS"),
        os.path.join("C:", "ESD"),
    ):
        if os.path.exists(candidate):
            previous_installs.append(CacheTarget(path=candidate))

    if previous_installs:
        categories.append(
            CleanupCategory(
                id="previous_windows_install",
                name="Previous Windows installation",
                group="Windows",
                description="Leftover files from a previous Windows installation (Windows.old / upgrade folders). Can free tens of gigabytes. NEVER deleted automatically; requires explicit confirmation and administrator privileges.",
                safety_level=SafetyLevel.REVIEW,
                requires_admin=True,
                what_it_contains="Backup of previous OS installation files allowing rollback to earlier Windows versions.",
                why_it_grows="Major Windows version upgrades preserve the previous operating system in Windows.old.",
                why_safe_to_delete="Safe to remove if you are satisfied with the current Windows version and do not intend to roll back.",
                regeneration_behavior="Cannot be recovered once removed.",
                reversible=False,
                targets=previous_installs,
            )
        )

    if not is_windows():
        return []

    return categories
