"""Filesystem edge cases the scan traversal must survive.

Junction loops, symlink loops, unreadable directories, and cancellation. These are the
cases that turn a scan into a hang, a crash, or - worst - a wrong answer that presents
a user's own files as reclaimable junk.
"""

import os
import shutil
import stat
import subprocess
import threading

import pytest

from crapcleaner.core.size import _Cancelled, compute_dir_size, is_reparse_point
from crapcleaner.utils.platform import is_windows


def _make_junction(link: str, target: str) -> bool:
    """Create a Windows directory junction. Returns False when unavailable."""
    if not is_windows():
        return False
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", link, target], capture_output=True, text=True
    )
    return result.returncode == 0


def _write(path: str, size: int = 128) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"x" * size)


# ---------------------------------------------------------------------------
# Reparse points
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not is_windows(), reason="Windows junctions")
def test_junction_loop_terminates_and_is_not_followed(tmp_path):
    """A junction pointing at its own ancestor must not be traversed.

    S_ISLNK, os.path.islink, and is_dir(follow_symlinks=False) all report a junction as
    an ordinary directory, so without the reparse-tag check the walk recurses until the
    file budget is exhausted.
    """
    base = tmp_path / "base"
    _write(str(base / "real" / "a.tmp"))
    _write(str(base / "real" / "b.tmp"))

    if not _make_junction(str(base / "loop"), str(base)):
        pytest.skip("could not create a junction (needs the privilege)")

    counter = [0]
    total, count, _skipped = compute_dir_size(str(base), max_files=50000, counter=counter)

    # Exactly the two real files, counted once each, and nowhere near the budget.
    assert count == 2
    assert total == 256
    assert counter[0] < 100


@pytest.mark.skipif(not is_windows(), reason="Windows junctions")
def test_junction_pointing_outside_the_root_is_not_counted(tmp_path):
    """A junction escaping the scan root would present unrelated files as junk."""
    outside = tmp_path / "documents"
    _write(str(outside / "important.docx"), size=4096)

    scan_root = tmp_path / "temp"
    _write(str(scan_root / "junk.tmp"), size=10)

    if not _make_junction(str(scan_root / "escape"), str(outside)):
        pytest.skip("could not create a junction (needs the privilege)")

    total, count, _skipped = compute_dir_size(str(scan_root), max_files=50000)
    assert count == 1
    assert total == 10  # the document is not included


@pytest.mark.skipif(is_windows(), reason="POSIX symlinks")
def test_symlink_loop_terminates(tmp_path):
    base = tmp_path / "base"
    _write(str(base / "real" / "a.tmp"))
    os.symlink(str(base), str(base / "loop"), target_is_directory=True)

    counter = [0]
    total, count, _skipped = compute_dir_size(str(base), max_files=50000, counter=counter)
    assert count == 1
    assert counter[0] < 100


def test_is_reparse_point_detects_plain_files(tmp_path):
    plain = tmp_path / "plain.tmp"
    _write(str(plain))
    st = os.stat(str(plain), follow_symlinks=False)
    assert is_reparse_point(st) is False


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_missing_root_returns_zero(tmp_path):
    assert compute_dir_size(str(tmp_path / "nope")) == (0, 0, 0)


def test_file_as_root_returns_zero(tmp_path):
    target = tmp_path / "a.tmp"
    _write(str(target))
    assert compute_dir_size(str(target)) == (0, 0, 0)


def test_unreadable_subdirectory_does_not_abort_the_scan(tmp_path, monkeypatch):
    """One unreadable directory must cost its own contents, not the whole scan."""
    _write(str(tmp_path / "good" / "a.tmp"))
    _write(str(tmp_path / "locked" / "b.tmp"))

    real_scandir = os.scandir

    def selective_scandir(path):
        if str(path).endswith("locked"):
            raise PermissionError("access denied")
        return real_scandir(path)

    monkeypatch.setattr("crapcleaner.core.size.os.scandir", selective_scandir)

    total, count, _skipped = compute_dir_size(str(tmp_path), max_files=50000)
    assert count == 1  # the readable file still counted
    assert total == 128


def test_vanishing_file_is_skipped_not_fatal(tmp_path, monkeypatch):
    """A file deleted between enumeration and stat is normal in a temp directory."""
    _write(str(tmp_path / "a.tmp"))
    _write(str(tmp_path / "b.tmp"))

    original = os.DirEntry.stat

    def flaky_stat(self, *args, **kwargs):
        if self.name == "a.tmp":
            raise FileNotFoundError("vanished")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(os.DirEntry, "stat", flaky_stat, raising=False)

    total, count, skipped = compute_dir_size(str(tmp_path), max_files=50000)
    assert count == 1
    assert skipped >= 1


def test_file_budget_is_respected(tmp_path):
    for i in range(200):
        _write(str(tmp_path / "dir" / f"f{i}.tmp"), size=1)
    counter = [0]
    compute_dir_size(str(tmp_path), max_files=50, counter=counter)
    # It stops promptly rather than walking everything.
    assert counter[0] <= 60


def test_cancellation_stops_the_walk(tmp_path):
    for i in range(500):
        _write(str(tmp_path / "dir" / f"f{i}.tmp"), size=1)

    stop = threading.Event()
    stop.set()

    with pytest.raises(_Cancelled):
        compute_dir_size(str(tmp_path), max_files=50000, stop_event=stop)


def test_protected_directory_is_not_descended(tmp_path):
    """Nothing inside a .git directory is ever a cleanup candidate."""
    _write(str(tmp_path / "proj" / ".git" / "objects" / "abc"))
    _write(str(tmp_path / "proj" / "build.tmp"))

    total, count, _skipped = compute_dir_size(str(tmp_path), max_files=50000)
    assert count == 1
    assert total == 128


# ---------------------------------------------------------------------------
# Deletion must not escape through a link
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not is_windows(), reason="Windows junctions")
def test_deletion_does_not_follow_a_junction_out_of_the_target(tmp_path):
    """The worst outcome of following a junction: deleting someone's documents.

    A cleanup target containing a junction to an unrelated folder must delete the
    junction itself, never the files it points at.
    """
    from crapcleaner.utils.files import walk_safe

    documents = tmp_path / "documents"
    _write(str(documents / "thesis.docx"), size=4096)

    target = tmp_path / "cache"
    _write(str(target / "junk.tmp"), size=10)

    if not _make_junction(str(target / "escape"), str(documents)):
        pytest.skip("could not create a junction (needs the privilege)")

    walked = [
        os.path.join(root, name) for root, _dirs, files in walk_safe(str(target)) for name in files
    ]

    assert any(p.endswith("junk.tmp") for p in walked)
    assert not any("thesis.docx" in p for p in walked), "walk escaped through the junction"
    # The junction is offered as a deletable entry itself, so the link goes but its
    # target survives.
    assert any(p.endswith("escape") for p in walked)
    assert (documents / "thesis.docx").exists()


def test_walk_safe_matches_os_walk_on_an_ordinary_tree(tmp_path):
    """Without links present, the safe walker must see exactly what os.walk sees."""
    from crapcleaner.utils.files import walk_safe

    for i in range(3):
        _write(str(tmp_path / f"d{i}" / "nested" / f"f{i}.tmp"))
    _write(str(tmp_path / "root.tmp"))

    def collect(walker):
        return sorted(
            os.path.relpath(os.path.join(root, name), str(tmp_path))
            for root, _dirs, files in walker
            for name in files
        )

    assert collect(walk_safe(str(tmp_path))) == collect(os.walk(str(tmp_path)))
    assert collect(walk_safe(str(tmp_path), topdown=False)) == collect(
        os.walk(str(tmp_path), topdown=False)
    )
