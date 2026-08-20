"""Large file scanner: progress reporting and per-directory guard cost."""

import crapcleaner.core.protected_paths as protected_paths
from crapcleaner.analysis.large_files import scan_large_files


class TestProgressReporting:
    """The callback sat in the directory loop, where `visited % 2000` almost never hit."""

    def test_progress_is_reported_while_a_directory_is_still_being_read(self, tmp_path):
        for i in range(2100):
            (tmp_path / f"f{i}.bin").write_bytes(b"x")
        seen = []

        scan_large_files(str(tmp_path), threshold_bytes=1, progress_cb=seen.append)

        assert seen == [2000]


class TestGuardCost:
    def test_a_scan_resolves_only_its_root(self, tmp_path, monkeypatch):
        for name in ("a", "a/b", "a/b/c"):
            (tmp_path / name).mkdir()
        (tmp_path / "a" / "b" / "c" / "big.bin").write_bytes(b"x" * 100)
        calls = []
        real_norm = protected_paths._norm
        monkeypatch.setattr(
            protected_paths,
            "_norm",
            lambda path: (calls.append(path), real_norm(path))[1],
        )

        results = scan_large_files(str(tmp_path), threshold_bytes=10)

        assert len(results) == 1
        assert len(calls) == 1
