""".NET and Visual Studio ecosystem cleanup categories."""

import glob
import os

from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.utils.files import walk_safe
from crapcleaner.utils.platform import get_appdata, get_local_appdata


def find_vs_ipch_dirs(root: str) -> list[str]:
    found: list[str] = []
    if not root or not os.path.isdir(root):
        return found
    for dirpath, dirnames, _filenames in walk_safe(root):
        try:
            dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
        except OSError:
            continue
        for d in list(dirnames):
            if d.lower().endswith(".ipch"):
                found.append(os.path.join(dirpath, d))
                dirnames.remove(d)
    return found


def _vs_component_cache(root: str, name: str) -> list[CacheTarget]:
    targets = []
    if root and os.path.isdir(root):
        for sub in glob.glob(os.path.join(root, "*")):
            p = os.path.join(sub, name)
            if os.path.isdir(p):
                targets.append(CacheTarget(path=p))
    return targets


def get_categories() -> list[CleanupCategory]:
    local = get_local_appdata()
    appdata = get_appdata()
    user_profile = os.environ.get("USERPROFILE", "")

    nuget_targets = []
    nuget_root = os.path.join(user_profile, ".nuget", "packages")
    if os.path.isdir(nuget_root):
        nuget_targets.append(CacheTarget(path=nuget_root, recurse=False))

    vs_root = os.path.join(local, "Microsoft", "VisualStudio")

    component_model = _vs_component_cache(vs_root, "ComponentModelCache")
    image_cache = _vs_component_cache(vs_root, "ImageCache")

    jetbrains_caches = []
    for base in (os.path.join(local, "JetBrains"), os.path.join(appdata, "JetBrains")):
        if os.path.isdir(base):
            for tool in glob.glob(os.path.join(base, "*")):
                cache = os.path.join(tool, "caches")
                if os.path.isdir(cache):
                    jetbrains_caches.append(CacheTarget(path=cache))

    categories = [
        CleanupCategory(
            id="nuget_cache",
            name="NuGet cache",
            group=".NET",
            description="Global NuGet package cache. Packages are re-downloaded on the next restore; no project files are affected.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="Extracted NuGet packages under .nuget/packages - the assemblies every .NET project on this machine restores from.",
            why_it_grows="Each restore adds every package version a project asks for, and NuGet keeps them all so later restores are offline-fast.",
            why_safe_to_delete="Solutions, project files, and installed SDKs are untouched; only the shared package folder goes. This folder serves every project on the machine, so the next build has to re-download its packages from nuget.org - a machine that is offline or behind a private feed it cannot reach will fail to restore.",
            regeneration_behavior="The next 'dotnet restore' or build repopulates the folder with what those projects need.",
            targets=nuget_targets,
        ),
        CleanupCategory(
            id="dotnet_temp",
            name=".NET temporary files",
            group=".NET",
            description="Temporary build and native compiler artifacts created by the .NET SDK.",
            safety_level=SafetyLevel.SAFE,
            what_it_contains="Scratch files MSBuild writes under your temp folder and the CoreCLR working directory the .NET SDK keeps in Local AppData.",
            why_it_grows="Each build and each SDK tool run leaves intermediate files behind that nothing deletes afterwards.",
            why_safe_to_delete="No project, source, or build output under your solutions is targeted - only the SDK's own scratch space. Files held open by a build that is running right now are skipped rather than forced, so nothing in flight is broken.",
            regeneration_behavior="The next build recreates whatever scratch files it needs.",
            targets=[
                CacheTarget(path=os.path.join(local, "Temp", "MSBuild")),
                CacheTarget(path=os.path.join(local, "Microsoft", "dotnet", "coreclr")),
            ],
        ),
        CleanupCategory(
            id="vs_component_model_cache",
            name="Visual Studio component cache",
            group=".NET",
            description="Visual Studio component model and image caches. Rebuilt on the next IDE start.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="The MEF ComponentModelCache and the ImageCache Visual Studio keeps per installed version, listing its extensions and their icons.",
            why_it_grows="Every Visual Studio version and every extension change writes a fresh composition and icon cache.",
            why_safe_to_delete="Settings, extensions, projects, and solutions are not touched - Visual Studio rebuilds these caches from the extensions that are still installed. Clearing them is the standard fix for extensions that stop loading; the trade-off is one slower IDE start.",
            regeneration_behavior="Visual Studio recomposes the cache the next time it launches, which takes noticeably longer than usual.",
            targets=component_model + image_cache,
        ),
        CleanupCategory(
            id="cpp_intellisense",
            name="C++ IntelliSense caches",
            group=".NET",
            description="C++ IntelliSense .ipch databases. Rebuilt by the IDE when files are opened.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains=".ipch folders holding the precompiled header databases Visual Studio builds so C++ IntelliSense can answer quickly.",
            why_it_grows="Each C++ solution gets its own database, and they are kept after the solution is closed or deleted.",
            why_safe_to_delete="Nothing here is source or build output; the databases are derived from your headers and are rebuilt on demand. The cost is that IntelliSense has to reparse a large C++ solution the first time you open it again, which can take minutes.",
            regeneration_behavior="Visual Studio rebuilds the database in the background when you next open the project.",
            finder=find_vs_ipch_dirs,
            finder_args=(vs_root,),
        ),
        CleanupCategory(
            id="resharper_caches",
            name="JetBrains ReSharper / Rider caches",
            group=".NET",
            description="Caches for JetBrains .NET tools (ReSharper, Rider). Rebuilt on next IDE start.",
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="The 'caches' folders under each JetBrains tool directory - solution indexes, symbol data, and analysis results for ReSharper and Rider.",
            why_it_grows="Each solution you open is indexed and kept, for every installed version of every JetBrains tool.",
            why_safe_to_delete="Licences, settings, and plugins live elsewhere in the JetBrains folders and are not targeted; only the derived indexes go. The cost is a full reindex of each solution the next time you open it, during which navigation and inspections are slower.",
            regeneration_behavior="The IDE reindexes on the next solution open and the caches build back up.",
            targets=jetbrains_caches,
        ),
    ]

    return categories
