"""Python ecosystem cleanup categories."""

import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.utils.platform import get_local_appdata, list_drives
from crapcleaner.utils.files import walk_safe

SKIP_DIRS = {
    "AppData",
    "$Recycle.Bin",
    "System Volume Information",
    "Windows",
    "Program Files",
    "Program Files (x86)",
    "node_modules",
    ".git",
    ".venv",
    "venv",
    ".cache",
    "Cache",
    "caches",
    "pkg",
    "package",
    "site-packages",
}

# Lowercased once so the per-directory skip check is a single frozenset
# membership test instead of rebuilding the set for every visited directory.
_SKIP_LOWER = frozenset(s.lower() for s in SKIP_DIRS)


def _is_skipped_dir(name: str) -> bool:
    if name.startswith("."):
        return True
    return name.lower() in _SKIP_LOWER


def _walk_one(root: str, max_dirs: int):
    """Single os.walk over one root; yields (dirpath, dirnames, filenames)."""
    try:
        walker = walk_safe(root, topdown=True)
        visited = 0
        for dirpath, dirnames, filenames in walker:
            if visited > max_dirs:
                break
            visited += 1
            dirnames[:] = [
                d
                for d in dirnames
                if not _is_skipped_dir(d) and not os.path.islink(os.path.join(dirpath, d))
            ]
            yield dirpath, dirnames, filenames
    except OSError:
        return


@lru_cache(maxsize=8)
def _python_artifacts(roots: tuple, max_dirs: int = 50000) -> tuple:
    """Walk every root once and collect all four Python artifact types.

    The four finder categories previously walked the same roots independently,
    so a full-drive scan re-traversed the tree up to four times. This merges
    those traversals into a single walk (parallelized across roots) and caches
    the result per (roots, max_dirs) for the duration of a scan.
    """
    results: dict[str, tuple[list[str], list[str], list[str], list[str]]] = {
        root: ([], [], [], []) for root in roots
    }

    def _scan(root: str):
        pycache: list[str] = []
        pyc_files: list[str] = []
        egg_info: list[str] = []
        build_dirs: list[str] = []
        for dirpath, dirnames, filenames in _walk_one(root, max_dirs):
            keep = []
            for d in dirnames:
                if d == "__pycache__":
                    pycache.append(os.path.join(dirpath, "__pycache__"))
                    continue
                if _is_skipped_dir(d):
                    continue
                keep.append(d)
            dirnames[:] = keep

            for name in filenames:
                if name.endswith(".pyc") and not name.startswith("__pycache__"):
                    pyc_files.append(os.path.join(dirpath, name))

            for d in list(dirnames):
                if d.endswith(".egg-info"):
                    egg_info.append(os.path.join(dirpath, d))
                    dirnames.remove(d)
                elif d == "build" and _looks_like_python_build(dirpath, d):
                    build_dirs.append(os.path.join(dirpath, d))
                    dirnames.remove(d)
        results[root] = (pycache, pyc_files, egg_info, build_dirs)

    if len(roots) > 1:
        with ThreadPoolExecutor(max_workers=min(4, len(roots))) as pool:
            list(pool.map(_scan, roots))
    else:
        for root in roots:
            _scan(root)

    merged: tuple[list[str], list[str], list[str], list[str]] = ([], [], [], [])
    for root in roots:
        for i in range(4):
            merged[i].extend(results[root][i])
    return tuple(merged)


def find_pycache_dirs(roots: list[str], max_dirs: int = 50000) -> list[str]:
    return _python_artifacts(tuple(roots or []), max_dirs)[0]


def find_pyc_files(roots: list[str], max_dirs: int = 50000) -> list[str]:
    return _python_artifacts(tuple(roots or []), max_dirs)[1]


def find_egg_info_dirs(roots: list[str], max_dirs: int = 50000) -> list[str]:
    return _python_artifacts(tuple(roots or []), max_dirs)[2]


def find_build_dirs(roots: list[str], max_dirs: int = 50000) -> list[str]:
    return _python_artifacts(tuple(roots or []), max_dirs)[3]


def _looks_like_python_build(parent: str, build_name: str) -> bool:
    marker = os.path.join(parent, "pyproject.toml")
    if os.path.exists(marker):
        return True
    marker = os.path.join(parent, "setup.py")
    if os.path.exists(marker):
        return True
    marker = os.path.join(parent, "setup.cfg")
    if os.path.exists(marker):
        return True
    try:
        for entry in os.listdir(parent):
            if entry.endswith(".egg-info"):
                return True
    except OSError:
        return False
    return False


def get_categories(
    scan_roots: list[str] | None = None,
    include_all_drives: bool = False,
) -> list[CleanupCategory]:
    local = get_local_appdata()
    user_profile = os.environ.get("USERPROFILE", "")
    scan_roots = _merge_scan_roots(scan_roots or [])
    if include_all_drives:
        scan_roots = _merge_all_drives(scan_roots)

    categories = []

    categories.append(
        CleanupCategory(
            id="pip_cache",
            name="pip cache",
            group="Python",
            description="Downloaded package wheels cached by pip. Re-downloaded when needed; frees space and speeds nothing until you install again.",
            safety_level=SafetyLevel.SAFE,
            targets=[CacheTarget(path=os.path.join(local, "pip", "cache"))],
        )
    )

    categories.append(
        CleanupCategory(
            id="uv_cache",
            name="uv cache",
            group="Python",
            description="Package cache maintained by uv (the fast Python package manager). Re-downloaded on demand.",
            safety_level=SafetyLevel.SAFE,
            targets=[CacheTarget(path=os.path.join(local, "uv", "cache"))],
        )
    )

    categories.append(
        CleanupCategory(
            id="poetry_cache",
            name="Poetry cache",
            group="Python",
            description="Wheel cache used by Poetry. Re-downloaded on demand.",
            safety_level=SafetyLevel.SAFE,
            targets=[CacheTarget(path=os.path.join(local, "pypoetry", "Cache"))],
        )
    )

    categories.append(
        CleanupCategory(
            id="conda_cache",
            name="Conda caches",
            group="Python",
            description="Package download cache managed by Conda/Mamba. Only the download cache is targeted - installed environments are left untouched.",
            safety_level=SafetyLevel.SAFE,
            targets=[
                CacheTarget(path=os.path.join(user_profile, ".conda", "pkgs", "cache")),
                CacheTarget(path=os.path.join(user_profile, ".cache", "conda")),
            ],
        )
    )

    categories.append(
        CleanupCategory(
            id="pycache_dirs",
            name="__pycache__ directories",
            group="Python",
            description="Compiled bytecode folders created by Python. Recreated automatically; never contains source code.",
            safety_level=SafetyLevel.SAFE,
            finder=find_pycache_dirs,
            finder_args=(scan_roots,),
        )
    )

    categories.append(
        CleanupCategory(
            id="pyc_files",
            name=".pyc files",
            group="Python",
            description="Orphaned compiled Python files outside __pycache__ folders. Regenerated by Python as needed.",
            safety_level=SafetyLevel.SAFE,
            finder=find_pyc_files,
            finder_args=(scan_roots,),
        )
    )

    categories.append(
        CleanupCategory(
            id="python_egg_info",
            name="Python build leftovers (.egg-info)",
            group="Python",
            description="Metadata folders left behind by older Python packaging tooling. Safe to remove; regenerated on build.",
            safety_level=SafetyLevel.REVIEW,
            finder=find_egg_info_dirs,
            finder_args=(scan_roots,),
        )
    )

    categories.append(
        CleanupCategory(
            id="python_build_dirs",
            name="Python build caches",
            group="Python",
            description="'build' output directories from Python packaging projects (detected via pyproject.toml / setup.py presence). Regenerated on the next build.",
            safety_level=SafetyLevel.REVIEW,
            finder=find_build_dirs,
            finder_args=(scan_roots,),
        )
    )

    return categories


def _default_scan_roots() -> list[str]:
    roots = []
    user_profile = os.environ.get("USERPROFILE", "")
    if user_profile:
        roots.append(user_profile)
    roots.extend(
        [
            os.environ.get("OneDrive", ""),
            os.environ.get("OneDriveConsumer", ""),
        ]
    )
    return [r for r in roots if r]


def _merge_scan_roots(configured: list[str]) -> list[str]:
    merged = list(configured)
    for root in _default_scan_roots():
        if root not in merged:
            merged.append(root)
    return merged


def _merge_all_drives(roots: list[str]) -> list[str]:
    """Append every drive root so the finders search all drives."""
    merged = list(roots)
    for drive in list_drives():
        if drive not in merged:
            merged.append(drive)
    return merged
