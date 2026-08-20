"""Every worker must be interruptible, and stopping one must not freeze the window."""

import inspect
import os
import time

import pytest
from PySide6.QtCore import QThread

from crapcleaner.gui import workers


def _worker_classes():
    found = {}
    for obj in vars(workers).values():
        if inspect.isclass(obj) and issubclass(obj, QThread) and obj.__module__ == workers.__name__:
            found[obj.__name__] = obj
    return list(found.values())


def test_the_module_still_defines_the_workers_we_think_it_does():
    assert len(_worker_classes()) > 20


@pytest.mark.parametrize("cls", _worker_classes(), ids=lambda c: c.__name__)
def test_every_worker_can_be_asked_to_stop(cls):
    assert callable(getattr(cls, "request_stop", None))


def test_stopping_a_worker_asks_first_and_returns_promptly(qt_app):
    class Sleeper(workers._Worker):
        def run(self):
            self._stop.wait(10)

    worker = Sleeper()
    worker.start()
    while not worker.isRunning():
        time.sleep(0.01)

    started = time.monotonic()
    workers.stop_worker(worker)
    elapsed = time.monotonic() - started

    assert worker.stop_requested
    assert elapsed < 1.0, "stop_worker blocked the GUI thread"
    assert worker.wait(2000)


def test_a_stopped_worker_drops_its_result(qt_app):
    class Late(workers._Worker):
        done = workers.Signal(str)

        def run(self):
            self._emit(self.done, "late")

    worker = Late()
    seen = []
    worker.done.connect(seen.append)
    worker.request_stop()
    worker.run()

    assert seen == []


def test_delete_worker_stops_between_paths(qt_app, tmp_path):
    paths = []
    for name in ("a.bin", "b.bin", "c.bin"):
        target = tmp_path / name
        target.write_bytes(b"x")
        paths.append(str(target))

    worker = workers.DeleteWorker(paths, use_recycle_bin=False)
    worker.progress.connect(lambda *_: worker.request_stop())
    outcomes = []
    worker.done.connect(outcomes.append)
    worker.run()

    assert len(outcomes[0]) == 1
    assert os.path.exists(paths[2])


def test_diagnostics_worker_reports_the_written_path(qt_app, tmp_path, monkeypatch):
    from crapcleaner.system import diagnostics

    destination = str(tmp_path / "bundle.txt")
    monkeypatch.setattr(diagnostics, "write_diagnostics_bundle", lambda dest: dest)

    worker = workers.DiagnosticsWorker(destination)
    seen = []
    worker.done.connect(seen.append)
    worker.run()

    assert seen == [destination]


def test_the_snapshot_comparison_is_told_which_size_mode_the_scan_used():
    source = inspect.getsource(workers.StorageAnalysisWorker.run)

    assert "compare(self._path, sizes, size_mode=self._size_mode)" in source
