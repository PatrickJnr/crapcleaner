"""Windows system cleanup categories."""

import os

from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.utils.platform import (
    get_local_appdata,
    get_program_data,
    get_windows_dir,
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
            description="Temporary files from the current user's TEMP folder. Almost always safe to remove; programs recreate them as needed.",
            safety_level=SafetyLevel.SAFE,
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
            description="User-mode crash dumps written by Windows Error Reporting to %LOCALAPPDATA%\\CrashDumps. Safe to remove.",
            safety_level=SafetyLevel.SAFE,
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
            targets=[CacheTarget(path=os.path.join(windir, "Minidump"))],
        )
    )

    categories.append(
        CleanupCategory(
            id="windows_cryptnet_cache",
            name="Cryptnet SSL / TLS Certificate Cache",
            group="Windows",
            description="Cached SSL certificates and revocation lists. Re-fetched from certificate authorities on demand.",
            safety_level=SafetyLevel.SAFE,
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
                targets=previous_installs,
            )
        )

    categories.append(
        CleanupCategory(
            id="recycle_bin",
            name="Recycle Bin",
            group="Windows",
            description="Empties the Recycle Bin using the official Windows API. Permanently deletes its contents - requires explicit confirmation.",
            safety_level=SafetyLevel.REVIEW,
            action="empty_recycle_bin",
            targets=[],
        )
    )

    return categories
