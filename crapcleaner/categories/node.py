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
            action="pnpm_store_prune",
        ),
    ]
