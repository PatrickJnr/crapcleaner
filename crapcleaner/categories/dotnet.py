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
            targets=nuget_targets,
        ),
        CleanupCategory(
            id="dotnet_temp",
            name=".NET temporary files",
            group=".NET",
            description="Temporary build and native compiler artifacts created by the .NET SDK.",
            safety_level=SafetyLevel.SAFE,
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
            targets=component_model + image_cache,
        ),
        CleanupCategory(
            id="cpp_intellisense",
            name="C++ IntelliSense caches",
            group=".NET",
            description="C++ IntelliSense .ipch databases. Rebuilt by the IDE when files are opened.",
            safety_level=SafetyLevel.LOW_RISK,
            finder=find_vs_ipch_dirs,
            finder_args=(vs_root,),
        ),
        CleanupCategory(
            id="resharper_caches",
            name="JetBrains ReSharper / Rider caches",
            group=".NET",
            description="Caches for JetBrains .NET tools (ReSharper, Rider). Rebuilt on next IDE start.",
            safety_level=SafetyLevel.LOW_RISK,
            targets=jetbrains_caches,
        ),
    ]

    return categories
