"""Node.js ecosystem cleanup categories."""

import os

from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel
from crapcleaner.utils.platform import get_local_appdata


def get_categories() -> list[CleanupCategory]:
    local = get_local_appdata()

    return [
        CleanupCategory(
            id="npm_cache",
            name="npm cache",
            group="Node.js",
            description="Package cache used by npm (npm-cache). Re-downloaded on demand. Never touches node_modules, project sources, or lock files.",
            safety_level=SafetyLevel.SAFE,
            what_it_contains="Package tarballs npm has downloaded from the registry, with the integrity metadata of its _cacache store.",
            why_it_grows="npm adds every version of every package it fetches and never expires the old ones.",
            why_safe_to_delete="node_modules, lock files, and project sources are not touched - only the download copies. The next install fetches those packages from the registry again, so it needs a network connection and takes longer than a cached install.",
            regeneration_behavior="The cache refills as you install; the first install of each package is slower.",
            targets=[
                CacheTarget(path=os.path.join(local, "npm-cache")),
                CacheTarget(path=os.path.join(local, "npm", "cache")),
            ],
        ),
        CleanupCategory(
            id="yarn_cache",
            name="Yarn cache",
            group="Node.js",
            description="Global package cache used by Yarn classic and Yarn Berry. Re-downloaded on demand.",
            safety_level=SafetyLevel.SAFE,
            what_it_contains="Package archives Yarn keeps in its global cache folder for Yarn classic and Yarn Berry.",
            why_it_grows="Every package version any project installs is added to the shared cache and kept indefinitely.",
            why_safe_to_delete="node_modules, lock files, and project sources stay as they are; only the global download cache goes. Yarn re-downloads from the registry on the next install, so that install needs the network, and a project that vendors its own packages in .yarn/cache is unaffected.",
            regeneration_behavior="Yarn refills the cache as projects install packages again.",
            targets=[
                CacheTarget(path=os.path.join(local, "Yarn", "Cache")),
                CacheTarget(path=os.path.join(local, "yarn", "Cache")),
            ],
        ),
        CleanupCategory(
            id="pnpm_store",
            name="pnpm store (prune)",
            group="Node.js",
            description="Runs 'pnpm store prune' to remove only unreferenced packages from the pnpm content-addressable store. Safe: packages still used by projects are kept.",
            safety_level=SafetyLevel.REVIEW,
            what_it_contains="pnpm's global content-addressable store, which holds one copy of each package version and hard-links it into every project's node_modules.",
            why_it_grows="Packages stay in the store after the projects that used them are updated or deleted, so old versions build up.",
            why_safe_to_delete="This runs 'pnpm store prune' rather than deleting the folder: packages a project still references are kept and existing node_modules keep working. The store is shared by every project on the machine, so any version dropped here is re-downloaded from the registry the next time any project asks for it.",
            regeneration_behavior="Installs continue to work; the store refills as new packages are fetched.",
            action="pnpm_store_prune",
        ),
    ]
