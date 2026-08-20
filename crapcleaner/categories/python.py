"""Python ecosystem cleanup categories."""

import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.utils.files import walk_safe
from crapcleaner.utils.platform import get_local_appdata, list_drives

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

# Lowercased once; the skip check runs for every directory visited.
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
            # walk_safe already excludes symlinks and junctions.
            dirnames[:] = [d for d in dirnames if d in TOOL_CACHE_DIRS or not _is_skipped_dir(d)]
            yield dirpath, dirnames, filenames
    except OSError:
        return


#: Per-project tool caches, each rebuilt from the project's own sources on next run.
TOOL_CACHE_DIRS = frozenset({".ruff_cache", ".mypy_cache", ".pytest_cache", ".tox"})

_ARTIFACT_KINDS = 5


@lru_cache(maxsize=8)
def _python_artifacts(roots: tuple, max_dirs: int = 50000) -> tuple:
    """Walk every root once and collect every Python artifact type.

    One walk shared by all finder categories; a per-category walk re-traversed the
    whole tree once per category on a full-drive scan.
    """
    results: dict[str, tuple[list[str], ...]] = {
        root: tuple([] for _ in range(_ARTIFACT_KINDS)) for root in roots
    }

    def _scan(root: str):
        pycache: list[str] = []
        pyc_files: list[str] = []
        egg_info: list[str] = []
        build_dirs: list[str] = []
        tool_caches: list[str] = []
        for dirpath, dirnames, filenames in _walk_one(root, max_dirs):
            keep = []
            for d in dirnames:
                if d == "__pycache__":
                    pycache.append(os.path.join(dirpath, "__pycache__"))
                    continue
                if d in TOOL_CACHE_DIRS:
                    tool_caches.append(os.path.join(dirpath, d))
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
        results[root] = (pycache, pyc_files, egg_info, build_dirs, tool_caches)

    if len(roots) > 1:
        with ThreadPoolExecutor(max_workers=min(4, len(roots))) as pool:
            list(pool.map(_scan, roots))
    else:
        for root in roots:
            _scan(root)

    merged: tuple[list[str], ...] = tuple([] for _ in range(_ARTIFACT_KINDS))
    for root in roots:
        for i in range(_ARTIFACT_KINDS):
            merged[i].extend(results[root][i])
    return merged


def find_pycache_dirs(roots: list[str], max_dirs: int = 50000) -> list[str]:
    return _python_artifacts(tuple(roots or []), max_dirs)[0]


def find_pyc_files(roots: list[str], max_dirs: int = 50000) -> list[str]:
    return _python_artifacts(tuple(roots or []), max_dirs)[1]


def find_egg_info_dirs(roots: list[str], max_dirs: int = 50000) -> list[str]:
    return _python_artifacts(tuple(roots or []), max_dirs)[2]


def find_build_dirs(roots: list[str], max_dirs: int = 50000) -> list[str]:
    return _python_artifacts(tuple(roots or []), max_dirs)[3]


def find_tool_cache_dirs(roots: list[str], max_dirs: int = 50000) -> list[str]:
    return _python_artifacts(tuple(roots or []), max_dirs)[4]


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
            what_it_contains="Wheels and source archives pip downloaded from PyPI, plus the wheels pip built locally from source distributions.",
            why_it_grows="pip keeps a copy of everything it fetches so repeat installs skip the download, and it never expires old versions.",
            why_safe_to_delete="Installed packages and virtual environments are not touched - only pip's download copies. The next install fetches from the network again, and any package that has no wheel is recompiled from source, so an offline machine cannot reinstall what it has forgotten.",
            regeneration_behavior="The cache refills as you install; the first install of each package is slower.",
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
            what_it_contains="Wheels, source distributions, and the built-wheel and resolution metadata uv stores between runs.",
            why_it_grows="uv caches every distribution it resolves so later installs are near-instant, keeping each version it has seen.",
            why_safe_to_delete="Existing environments keep working: uv links packages into them, so removing the cached copy does not remove the installed files. New installs and resolutions have to reach the network again instead of being served locally.",
            regeneration_behavior="uv refills the cache on the next sync, resolve, or install.",
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
            what_it_contains="Poetry's downloaded wheels and sdists and its cached package metadata.",
            why_it_grows="Every project Poetry manages adds its downloads.",
            why_safe_to_delete="Project files, pyproject.toml and lock files are untouched, and cached downloads are re-fetched from PyPI. Poetry keeps project virtual environments under the same cache root, and virtualenvs is deliberately not targeted, so no project environment is destroyed.",
            regeneration_behavior="Poetry re-downloads packages on the next install; existing environments keep working.",
            targets=[
                CacheTarget(path=os.path.join(local, "pypoetry", "Cache", "cache")),
                CacheTarget(path=os.path.join(local, "pypoetry", "Cache", "artifacts")),
            ],
        )
    )

    categories.append(
        CleanupCategory(
            id="conda_cache",
            name="Conda caches",
            group="Python",
            description="Package download cache managed by Conda/Mamba. Only the download cache is targeted - installed environments are left untouched.",
            safety_level=SafetyLevel.SAFE,
            what_it_contains="The channel index (repodata) and notice caches conda and mamba keep, under .conda/pkgs/cache and .cache/conda.",
            why_it_grows="Every channel conda queries leaves a copy of its index, and each refresh writes another.",
            why_safe_to_delete="Environments and the extracted packages in the pkgs directory are not targeted, so nothing you have installed stops working. This cache is shared by every environment on the machine rather than one project, so the next install, update, or search in any of them re-downloads channel data before it can solve.",
            regeneration_behavior="conda re-fetches channel index data on the next command that needs it; that first command is noticeably slower.",
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
            what_it_contains="__pycache__ folders inside the projects under your scan roots, holding the .pyc bytecode Python compiled from the .py files beside them.",
            why_it_grows="Python writes bytecode for every module it imports, once per interpreter version, and leaves it behind when the source is moved or deleted.",
            why_safe_to_delete="Only compiled bytecode is removed; the .py sources it was generated from stay exactly where they are, and the scan skips virtual environments and site-packages so installed libraries are not disturbed. Python recompiles a module the first time it is imported again.",
            regeneration_behavior="The first import after cleaning is marginally slower while Python rewrites the bytecode.",
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
            what_it_contains="Loose .pyc bytecode files sitting next to source instead of in a __pycache__ folder, the layout Python 2 and older tooling used.",
            why_it_grows="They are written beside the module and left behind when the .py file is renamed, moved, or deleted.",
            why_safe_to_delete="No .py file is ever removed, and any .pyc with its source still beside it is rebuilt on the next import. The exception worth checking: a folder that ships .pyc files with no .py at all is a sourceless deployment, and removing those does delete the only copy of that code.",
            regeneration_behavior="Python recreates bytecode on import, in __pycache__ rather than beside the source.",
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
            what_it_contains=".egg-info folders setuptools generates beside a project's setup.py or pyproject.toml, listing its name, version, and entry points.",
            why_it_grows="Every build or editable install regenerates one, and they stay in the project tree afterwards.",
            why_safe_to_delete="Only generated packaging metadata is removed; setup.py, pyproject.toml, and the package source are untouched, and the folder is rebuilt by the next build. One case is not free: a project installed in editable mode by older setuptools resolves its metadata and entry points through this folder, so re-run 'pip install -e .' for those projects.",
            regeneration_behavior="Recreated the next time the project is built or installed.",
            finder=find_egg_info_dirs,
            finder_args=(scan_roots,),
        )
    )

    categories.append(
        CleanupCategory(
            id="python_tool_caches",
            name="Python tool caches (.ruff_cache, .mypy_cache, .pytest_cache, .tox)",
            group="Python",
            description=(
                "Per-project caches written by Ruff, mypy, pytest and tox inside the "
                "projects under your scan roots. Rebuilt from the project's own sources "
                "on the next run; .tox environments take longest to recreate."
            ),
            safety_level=SafetyLevel.LOW_RISK,
            what_it_contains="Lint results, type-check results, test caches and tox virtualenvs.",
            why_it_grows="Every project keeps its own copy, and each tool run adds to it.",
            why_safe_to_delete="No source code or configuration lives in these folders.",
            regeneration_behavior="Recreated the next time the tool runs in that project.",
            reversible=True,
            finder=find_tool_cache_dirs,
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
            what_it_contains="The 'build' directory of Python packaging projects - the staged copies of your modules and the intermediate object files from compiled extensions.",
            why_it_grows="Each wheel or sdist build stages another copy there and nothing clears it between builds.",
            why_safe_to_delete="Everything inside is generated from the project's own sources, which are not touched, and nothing imports from it at runtime. Only a folder named 'build' next to a pyproject.toml, setup.py, setup.cfg, or .egg-info is offered, but if a project of yours keeps hand-written files in a folder by that name, review the list before cleaning.",
            regeneration_behavior="The next build recreates it, recompiling C extensions from scratch instead of reusing the previous objects.",
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
    merged = list(roots)
    for drive in list_drives():
        if drive not in merged:
            merged.append(drive)
    return merged
