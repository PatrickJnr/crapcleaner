"""Tests for the shareable diagnostics bundle (FEAT-07)."""

import os

from crapcleaner.system import diagnostics


def test_redaction_reduces_every_path_to_its_root():
    text = (
        "opened C:\\Users\\Someone\\AppData\\Local\\Temp\\secret-project.log\n"
        "and /home/someone/.config/crapcleaner/notes.txt\n"
        "and D:/Games/Steam/userdata\n"
    )
    redacted = diagnostics._redact(text)
    assert "Someone" not in redacted
    assert "someone" not in redacted
    assert "secret-project" not in redacted
    assert "Steam" not in redacted
    assert "C:\\" in redacted and "D:\\" in redacted and "/" in redacted


def test_bundle_carries_the_sections_a_bug_report_needs(tmp_path, monkeypatch):
    log = tmp_path / "crapcleaner.log"
    log.write_text(
        "\n".join(
            f"2026-08-20 00:00:0{i % 10} WARNING crapcleaner.core: line {i}" for i in range(500)
        )
        + "\n2026-08-20 00:01:00 ERROR crapcleaner.core: could not delete C:\\Users\\Bob\\thing.dat\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(diagnostics, "log_path", lambda: str(log))

    destination = str(tmp_path / "out" / "bundle.txt")
    assert diagnostics.write_diagnostics_bundle(destination) == destination
    assert os.path.isfile(destination)

    text = open(destination, encoding="utf-8").read()
    for heading in ("=== CrapCleaner Diagnostics ===", "Version:", "Python:", "Admin:"):
        assert heading in text
    assert "--- Capabilities ---" in text
    assert "--- Drives ---" in text
    assert "Categories:" in text and "Exclusions:" in text

    tail = text.split(f"--- Log (last {diagnostics.LOG_TAIL_LINES} lines) ---")[1]
    assert "line 499" in tail
    assert "line 200" not in tail
    assert "Bob" not in tail and "thing.dat" not in tail


def test_bundle_survives_a_missing_log(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostics, "log_path", lambda: str(tmp_path / "absent.log"))
    assert "log unavailable" in diagnostics.build_diagnostics_text()
