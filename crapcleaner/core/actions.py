"""External cleanup actions that use official commands or APIs."""

from crapcleaner.models.report import CleanupResult
from crapcleaner.utils.platform import run_command, which

ACTION_REGISTRY: dict[str, dict] = {}


def register_action(name: str, description: str, requires_admin: bool = False):
    def decorator(func):
        ACTION_REGISTRY[name] = {
            "func": func,
            "description": description,
            "requires_admin": requires_admin,
        }
        return func

    return decorator


def describe_action(name: str) -> str | None:
    entry = ACTION_REGISTRY.get(name)
    return entry["description"] if entry else None


def run_action(
    name: str,
    dry_run: bool = False,
    is_admin: bool = False,
    category_name: str = "",
) -> CleanupResult | None:
    entry = ACTION_REGISTRY.get(name)
    if entry is None:
        return CleanupResult(
            category_id=name,
            category_name=category_name or name,
            files_deleted=0,
            space_recovered=0,
            skipped=0,
            errors=[f"Unknown action: {name}"],
            dry_run=dry_run,
        )
    if entry["requires_admin"] and not is_admin:
        return CleanupResult(
            category_id=name,
            category_name=category_name or name,
            files_deleted=0,
            space_recovered=0,
            skipped=0,
            errors=["Requires administrator privileges. Re-run elevated."],
            dry_run=dry_run,
        )
    return entry["func"](dry_run=dry_run, is_admin=is_admin, category_name=category_name)


def _result_for_action(
    category_id: str,
    category_name: str,
    dry_run: bool,
    ok: bool,
    out: str,
    command_label: str,
) -> CleanupResult:
    if dry_run:
        return CleanupResult(
            category_id=category_id,
            category_name=category_name,
            files_deleted=0,
            space_recovered=0,
            skipped=0,
            dry_run=True,
        )
    errors = [] if ok else [f"{command_label} failed: {out.strip()[:500]}"]
    return CleanupResult(
        category_id=category_id,
        category_name=category_name,
        files_deleted=0,
        space_recovered=0,
        skipped=0,
        errors=errors,
        dry_run=False,
    )


@register_action("dism_start_component_cleanup", "DISM /StartComponentCleanup", requires_admin=True)
def _dism_cleanup(
    dry_run: bool = False, is_admin: bool = False, category_name: str = ""
) -> CleanupResult:
    args = [
        "dism.exe",
        "/Online",
        "/Cleanup-Image",
        "/StartComponentCleanup",
        "/NoRestart",
    ]
    if dry_run:
        return CleanupResult(
            category_id="dism_start_component_cleanup",
            category_name=category_name,
            files_deleted=0,
            space_recovered=0,
            skipped=0,
            dry_run=True,
        )
    result = run_command(args, timeout=900.0)
    ok = result["returncode"] == 0
    stdout = str(result.get("stdout", ""))
    stderr = str(result.get("stderr", ""))
    return _result_for_action(
        "dism_start_component_cleanup",
        category_name,
        False,
        ok,
        stdout + stderr,
        " ".join(args),
    )


@register_action("empty_recycle_bin", "Empty Recycle Bin (SHEmptyRecycleBin)")
def _empty_recycle_bin(
    dry_run: bool = False, is_admin: bool = False, category_name: str = ""
) -> CleanupResult:
    from crapcleaner.utils.files import empty_recycle_bin as _empty

    if dry_run:
        return CleanupResult(
            category_id="empty_recycle_bin",
            category_name=category_name,
            files_deleted=0,
            space_recovered=0,
            skipped=0,
            dry_run=True,
        )
    ok = _empty()
    errors = [] if ok else ["Emptying the Recycle Bin failed."]
    return CleanupResult(
        category_id="empty_recycle_bin",
        category_name=category_name,
        files_deleted=0,
        space_recovered=0,
        skipped=0,
        errors=errors,
        dry_run=False,
    )


@register_action("docker_system_prune", "docker system prune -af")
def _docker_system_prune(
    dry_run: bool = False, is_admin: bool = False, category_name: str = ""
) -> CleanupResult:
    if which("docker") is None:
        return CleanupResult(
            category_id="docker_system_prune",
            category_name=category_name,
            files_deleted=0,
            space_recovered=0,
            skipped=0,
            errors=["Docker CLI not found."],
            dry_run=dry_run,
        )
    args = ["docker", "system", "prune", "-af"]
    if dry_run:
        return CleanupResult(
            category_id="docker_system_prune",
            category_name=category_name,
            files_deleted=0,
            space_recovered=0,
            skipped=0,
            dry_run=True,
        )
    result = run_command(args, timeout=600.0)
    ok = result["returncode"] == 0
    stdout = str(result.get("stdout", ""))
    stderr = str(result.get("stderr", ""))
    return _result_for_action(
        "docker_system_prune",
        category_name,
        False,
        ok,
        stdout + stderr,
        " ".join(args),
    )


@register_action("docker_builder_prune", "docker builder prune -af")
def _docker_builder_prune(
    dry_run: bool = False, is_admin: bool = False, category_name: str = ""
) -> CleanupResult:
    if which("docker") is None:
        return CleanupResult(
            category_id="docker_builder_prune",
            category_name=category_name,
            files_deleted=0,
            space_recovered=0,
            skipped=0,
            errors=["Docker CLI not found."],
            dry_run=dry_run,
        )
    args = ["docker", "builder", "prune", "-af"]
    if dry_run:
        return CleanupResult(
            category_id="docker_builder_prune",
            category_name=category_name,
            files_deleted=0,
            space_recovered=0,
            skipped=0,
            dry_run=True,
        )
    result = run_command(args, timeout=600.0)
    ok = result["returncode"] == 0
    stdout = str(result.get("stdout", ""))
    stderr = str(result.get("stderr", ""))
    return _result_for_action(
        "docker_builder_prune",
        category_name,
        False,
        ok,
        stdout + stderr,
        " ".join(args),
    )


@register_action("docker_buildx_prune", "docker buildx prune -af")
def _docker_buildx_prune(
    dry_run: bool = False, is_admin: bool = False, category_name: str = ""
) -> CleanupResult:
    if which("docker") is None:
        return CleanupResult(
            category_id="docker_buildx_prune",
            category_name=category_name,
            files_deleted=0,
            space_recovered=0,
            skipped=0,
            errors=["Docker CLI not found."],
            dry_run=dry_run,
        )
    args = ["docker", "buildx", "prune", "-af"]
    if dry_run:
        return CleanupResult(
            category_id="docker_buildx_prune",
            category_name=category_name,
            files_deleted=0,
            space_recovered=0,
            skipped=0,
            dry_run=True,
        )
    result = run_command(args, timeout=600.0)
    return _result_for_action(
        "docker_buildx_prune",
        category_name,
        False,
        result.ok,
        result.stdout + result.stderr,
        " ".join(args),
    )


@register_action("pnpm_store_prune", "pnpm store prune")
def _pnpm_store_prune(
    dry_run: bool = False, is_admin: bool = False, category_name: str = ""
) -> CleanupResult:
    if which("pnpm") is None:
        return CleanupResult(
            category_id="pnpm_store_prune",
            category_name=category_name,
            files_deleted=0,
            space_recovered=0,
            skipped=0,
            errors=["pnpm not found in PATH."],
            dry_run=dry_run,
        )
    args = ["pnpm", "store", "prune"]
    if dry_run:
        return CleanupResult(
            category_id="pnpm_store_prune",
            category_name=category_name,
            files_deleted=0,
            space_recovered=0,
            skipped=0,
            dry_run=True,
        )
    result = run_command(args, timeout=600.0)
    ok = result["returncode"] == 0
    stdout = str(result.get("stdout", ""))
    stderr = str(result.get("stderr", ""))
    return _result_for_action(
        "pnpm_store_prune",
        category_name,
        False,
        ok,
        stdout + stderr,
        " ".join(args),
    )


def available_actions() -> list[str]:
    return sorted(ACTION_REGISTRY)
