"""Tests for the Memory Cleaner reporting and reclamation layer."""

import json

from crapcleaner.system import memory_actions as cleaner_mod
from crapcleaner.system import memory_report as report_mod
from crapcleaner.system.memory_actions import available_actions, get_action, run_action
from crapcleaner.system.memory_report import (
    GpuMemoryStats,
    MemoryReport,
    MemoryStats,
    get_gpu_memory,
    get_memory_report,
    get_memory_stats,
)

MEMINFO = """MemTotal:       16384000 kB
MemFree:         1024000 kB
MemAvailable:    8192000 kB
SwapTotal:       2048000 kB
SwapFree:        1024000 kB
"""


def test_linux_meminfo_parsing(tmp_path):
    path = tmp_path / "meminfo"
    path.write_text(MEMINFO, encoding="utf-8")
    stats = report_mod._linux_memory_stats(str(path))
    assert stats is not None
    assert stats.total_bytes == 16384000 * 1024
    assert stats.available_bytes == 8192000 * 1024
    assert stats.used_bytes == (16384000 - 8192000) * 1024
    assert stats.percent_used == 50.0
    assert stats.swap_supported is True
    assert stats.swap_used_bytes == 1024000 * 1024


def test_linux_meminfo_missing_file_is_not_fatal(tmp_path):
    assert report_mod._linux_memory_stats(str(tmp_path / "nope")) is None


def test_linux_meminfo_without_swap(tmp_path):
    path = tmp_path / "meminfo"
    path.write_text("MemTotal: 1000 kB\nMemAvailable: 500 kB\n", encoding="utf-8")
    stats = report_mod._linux_memory_stats(str(path))
    assert stats is not None
    assert stats.swap_supported is False
    assert stats.swap_total_bytes == 0


def test_get_memory_stats_on_this_platform():
    stats = get_memory_stats()
    assert stats.total_bytes > 0
    assert stats.available_bytes > 0
    assert 0 <= stats.percent_used <= 100
    assert stats.used_bytes + stats.available_bytes == stats.total_bytes


def test_unknown_vram_is_not_reported_as_zero():
    gpu = GpuMemoryStats(name="Test GPU", total_bytes=8 * 1024**3)
    assert gpu.used_bytes == -1
    assert gpu.live_usage_available is False
    assert gpu.percent_used == 0.0
    assert gpu.to_dict()["live_usage_available"] is False


def test_live_vram_percentage():
    gpu = GpuMemoryStats(
        name="Test GPU", total_bytes=8000, used_bytes=2000, free_bytes=6000, source="test"
    )
    assert gpu.live_usage_available is True
    assert gpu.percent_used == 25.0


def test_gpu_detection_without_nvidia_smi(monkeypatch):
    monkeypatch.setattr(report_mod, "_nvidia_smi_path", lambda: None)
    monkeypatch.setattr(report_mod, "_capacity_only_gpus", list)
    monkeypatch.setattr(report_mod, "_amdgpu_sysfs_memory", list)
    assert get_gpu_memory() == []


def test_nvidia_total_capacity_is_preserved_when_live_counters_are_missing(monkeypatch):
    monkeypatch.setattr(
        report_mod,
        "_run_smi",
        lambda args: ["NVIDIA GeForce RTX 3080, 555.12, 10240, N/A, N/A"],
    )
    gpus = report_mod._nvidia_gpu_memory()
    assert len(gpus) == 1
    assert gpus[0].total_bytes == 10240 * 1024 * 1024
    assert gpus[0].live_usage_available is False


def test_vram_consumers_are_suppressed_in_default_report():
    assert report_mod.get_vram_consumers() == []


def test_memory_report_is_json_serialisable(monkeypatch):
    monkeypatch.setattr(report_mod, "get_gpu_memory", lambda: [])
    monkeypatch.setattr(report_mod, "get_vram_consumers", list)
    report = get_memory_report()
    payload = json.dumps(report.to_dict())
    assert "ram" in json.loads(payload)


def test_report_dataclass_defaults():
    report = MemoryReport()
    assert isinstance(report.ram, MemoryStats)
    assert report.gpus == []
    assert report.vram_consumers == []


def test_all_actions_are_platform_gated():
    actions = {a.id: a for a in available_actions(include_unsupported=True)}
    assert set(actions) == {
        "flush_all",
        "process_working_sets",
        "working_set",
        "standby_list",
        "fs_cache",
        "vram_report",
    }
    assert actions["standby_list"].supported is cleaner_mod.is_windows()
    assert actions["fs_cache"].supported is cleaner_mod.is_linux()
    for action in actions.values():
        if not action.supported:
            assert action.unsupported_reason
    assert actions["working_set"].requires_admin is False
    assert actions["process_working_sets"].requires_admin is False
    assert actions["flush_all"].requires_admin is False


def test_available_actions_hides_other_platforms_actions():
    """A kernel interface this system does not have is not worth showing at all."""
    offered = {a.id for a in available_actions()}
    assert all(a.supported for a in available_actions())

    if cleaner_mod.is_windows():
        assert "standby_list" in offered
        assert "fs_cache" not in offered
    elif cleaner_mod.is_linux():
        assert "fs_cache" in offered
        assert "standby_list" not in offered

    # Actions every platform can perform are always offered.
    assert {"flush_all", "process_working_sets", "working_set", "vram_report"} <= offered


def test_unsupported_action_ids_still_explain_themselves():
    """Hiding an action must not degrade its error into 'unknown action'."""
    from crapcleaner.system.memory_actions import get_action

    other_platform_id = "fs_cache" if cleaner_mod.is_windows() else "standby_list"
    action = get_action(other_platform_id)
    assert action is not None
    assert action.supported is False

    result = run_action(other_platform_id)
    assert result.success is False
    assert result.message == action.unsupported_reason


def test_action_effect_text_names_only_this_platforms_mechanism():
    effects = " ".join(a.effect for a in available_actions())
    descriptions = " ".join(a.description for a in available_actions())
    text = f"{effects} {descriptions}"

    if cleaner_mod.is_windows():
        assert "EmptyWorkingSet" in text
        assert "malloc_trim" not in text
        assert "drop_caches" not in text
    elif cleaner_mod.is_linux():
        assert "malloc_trim" in text
        assert "EmptyWorkingSet" not in text
        assert "SetProcessWorkingSetSize" not in text


def test_process_working_sets_action(monkeypatch):
    monkeypatch.setattr(
        cleaner_mod,
        "_trim_process_working_sets",
        lambda: (True, "Flushed working sets for 10 processes."),
    )
    result = run_action("process_working_sets")
    assert result.success is True
    assert "Flushed working sets" in result.message


def test_flush_all_action(monkeypatch):
    monkeypatch.setattr(cleaner_mod, "_flush_all", lambda: (True, "Memory flush completed."))
    result = run_action("flush_all")
    assert result.success is True
    assert "Memory flush completed" in result.message


def test_unknown_action_is_reported():
    result = run_action("does-not-exist")
    assert result.success is False
    assert "Unknown action" in result.message
    assert get_action("does-not-exist") is None


def test_dry_run_changes_nothing(monkeypatch):
    called = []
    monkeypatch.setattr(cleaner_mod, "_trim_working_set", lambda: called.append(1) or (True, "x"))
    result = run_action("working_set", dry_run=True)
    assert result.success is True
    assert result.dry_run is True
    assert called == []
    assert result.available_delta_bytes == 0
    assert "Dry run" in result.message


def test_unsupported_action_explains_itself(monkeypatch):
    target = "fs_cache" if cleaner_mod.is_windows() else "standby_list"
    result = run_action(target)
    assert result.success is False
    assert result.message


def test_admin_gated_action_is_refused_without_privileges(monkeypatch):
    monkeypatch.setattr(cleaner_mod, "is_admin", lambda: False)
    monkeypatch.setattr(cleaner_mod, "is_windows", lambda: True)
    monkeypatch.setattr(cleaner_mod, "is_linux", lambda: False)
    result = run_action("standby_list")
    assert result.success is False
    assert "elevated privileges" in result.message


def test_working_set_action_reports_before_and_after(monkeypatch):
    monkeypatch.setattr(cleaner_mod, "_trim_working_set", lambda: (True, "Trimmed."))
    monkeypatch.setattr(
        cleaner_mod,
        "get_memory_stats",
        lambda: MemoryStats(total_bytes=100, available_bytes=40, used_bytes=60),
    )
    result = run_action("working_set")
    assert result.success is True
    assert result.before.total_bytes == 100
    assert result.after.total_bytes == 100
    assert result.available_delta_bytes == 0


def test_vram_action_is_read_only(monkeypatch):
    monkeypatch.setattr(
        cleaner_mod,
        "get_gpu_memory",
        lambda: [
            GpuMemoryStats(
                name="Test GPU", total_bytes=8000, used_bytes=4000, free_bytes=4000, source="test"
            )
        ],
    )
    result = run_action("vram_report")
    assert result.success is True
    assert result.measurable is False
    assert result.available_delta_bytes == 0
    assert "50.0%" in result.message


def test_vram_action_without_live_counters(monkeypatch):
    monkeypatch.setattr(cleaner_mod, "get_gpu_memory", list)
    result = run_action("vram_report")
    assert result.success is True
    assert "No graphics adapter" in result.message


def test_cli_memory_json(capsys):
    from crapcleaner.cli import run

    assert run(["--memory", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ram"]["total_bytes"] > 0
    assert "gpus" in payload


def test_cli_memory_action_list(capsys):
    from crapcleaner.cli import run

    assert run(["--memory-clean", "list"]) == 0
    out = capsys.readouterr().out
    assert "working_set" in out
    assert "vram_report" in out


def test_cli_memory_clean_defaults_to_dry_run(capsys):
    from crapcleaner.cli import run

    assert run(["--memory-clean", "working_set"]) == 0
    out = capsys.readouterr().out
    assert "Dry run" in out
    assert "--execute" in out


def test_cached_memory_and_pressure_from_meminfo(tmp_path):
    path = tmp_path / "meminfo"
    path.write_text(
        MEMINFO + "Cached:          2048000 kB\nSReclaimable:     512000 kB\n", encoding="utf-8"
    )
    stats = report_mod._linux_memory_stats(str(path))
    assert stats.cached_known is True
    assert stats.cached_bytes == (2048000 + 512000) * 1024
    assert stats.pressure == "moderate"


def test_cached_memory_unknown_is_not_zero(tmp_path):
    path = tmp_path / "meminfo"
    path.write_text("MemTotal: 1000 kB\nMemAvailable: 900 kB\n", encoding="utf-8")
    stats = report_mod._linux_memory_stats(str(path))
    assert stats.cached_known is False
    assert stats.cached_bytes == -1
    assert stats.to_dict()["cached_known"] is False


def test_pressure_labels():
    assert MemoryStats(total_bytes=100, percent_used=10.0).pressure == "low"
    assert MemoryStats(total_bytes=100, percent_used=60.0).pressure == "moderate"
    assert MemoryStats(total_bytes=100, percent_used=80.0).pressure == "high"
    assert MemoryStats(total_bytes=100, percent_used=95.0).pressure == "critical"
    assert MemoryStats().pressure == "unknown"


def test_cli_memory_report_mentions_cached_and_pressure(capsys):
    from crapcleaner.cli import run

    assert run(["--memory"]) == 0
    out = capsys.readouterr().out
    assert "Cached/Standby" in out
    assert "Memory pressure" in out


def test_committed_memory_from_meminfo(tmp_path):
    path = tmp_path / "meminfo"
    path.write_text(
        MEMINFO + "Committed_AS:    4096000 kB\nCommitLimit:     9216000 kB\n", encoding="utf-8"
    )
    stats = report_mod._linux_memory_stats(str(path))
    assert stats.commit_bytes == 4096000 * 1024
    assert stats.commit_limit_bytes == 9216000 * 1024


def test_privilege_status_on_non_windows(monkeypatch):
    monkeypatch.setattr(cleaner_mod, "is_windows", lambda: False)
    status = cleaner_mod.enable_privilege("SeProfileSingleProcessPrivilege")
    assert status.enabled is False
    assert status.stage == "platform"
    assert "Windows" in status.message


def test_privilege_status_reports_elevation_and_code():
    status = cleaner_mod.enable_privilege("SeProfileSingleProcessPrivilege")
    assert status.name == "SeProfileSingleProcessPrivilege"
    assert isinstance(status.elevated, bool)
    assert isinstance(status.error_code, int)
    assert status.message
    assert status.to_dict()["stage"] == status.stage
    if cleaner_mod.is_windows() and not status.enabled:
        assert status.stage in {
            "not_in_token",
            "OpenProcessToken",
            "LookupPrivilegeValue",
            "AdjustTokenPrivileges",
        }


def test_privilege_message_does_not_blame_elevation_when_elevated(monkeypatch):
    monkeypatch.setattr(cleaner_mod, "is_admin", lambda: True)
    monkeypatch.setattr(cleaner_mod, "is_windows", lambda: False)
    status = cleaner_mod.enable_privilege("SeProfileSingleProcessPrivilege")
    assert "Run as administrator" not in status.message


def test_standby_purge_reports_privilege_failure(monkeypatch):
    from crapcleaner.system.memory_actions import PrivilegeStatus

    monkeypatch.setattr(cleaner_mod, "is_windows", lambda: True)
    monkeypatch.setattr(cleaner_mod, "is_linux", lambda: False)
    monkeypatch.setattr(cleaner_mod, "is_admin", lambda: True)
    monkeypatch.setattr(
        cleaner_mod,
        "enable_privilege",
        lambda name: PrivilegeStatus(
            name=name,
            elevated=True,
            error_code=1300,
            stage="not_in_token",
            message="SeProfileSingleProcessPrivilege is not held by this process token",
        ),
    )
    result = run_action("standby_list")
    assert result.success is False
    assert "not held by this process token" in result.message
    assert "Run as administrator" not in result.message
