"""Tests for the scan result cache."""

import json
import time

from crapcleaner.core.cache import ScanCache


def _tree(path, spec):
    for rel, data in spec.items():
        full = path / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)


class TestScanCache:
    def test_dir_roundtrip(self, tmp_path):
        cache = ScanCache(ttl=600, path=str(tmp_path / "cache.json"))
        _tree(tmp_path / "t", {"a.txt": b"x" * 100})
        cache.put_dir(str(tmp_path / "t"), (), True, False, 200000, 100, 1, 0)
        assert cache.get_dir(str(tmp_path / "t")) == (100, 1, 0)

    def test_dir_ttl_expired(self, tmp_path):
        cache = ScanCache(ttl=1, path=str(tmp_path / "cache.json"))
        _tree(tmp_path / "t", {"a.txt": b"x" * 100})
        cache.put_dir(str(tmp_path / "t"), (), True, False, 200000, 100, 1, 0)
        time.sleep(1.1)
        assert cache.get_dir(str(tmp_path / "t")) is None

    def test_dir_invalidated_by_new_file(self, tmp_path):
        cache = ScanCache(ttl=600, path=str(tmp_path / "cache.json"))
        d = tmp_path / "t"
        _tree(d, {"a.txt": b"x" * 100})
        cache.put_dir(str(d), (), True, False, 200000, 100, 1, 0)
        time.sleep(0.02)
        (d / "b.txt").write_bytes(b"y" * 200)
        assert cache.get_dir(str(d)) is None

    def test_dir_missing_path_not_cached(self, tmp_path):
        cache = ScanCache(ttl=600, path=str(tmp_path / "cache.json"))
        cache.put_dir(str(tmp_path / "nope"), (), True, False, 200000, 0, 0, 0)
        assert cache.get_dir(str(tmp_path / "nope")) is None

    def test_disabled_when_ttl_zero(self, tmp_path):
        cache = ScanCache(ttl=0, path=str(tmp_path / "cache.json"))
        _tree(tmp_path / "t", {"a.txt": b"x" * 100})
        cache.put_dir(str(tmp_path / "t"), (), True, False, 200000, 100, 1, 0)
        assert cache.get_dir(str(tmp_path / "t")) is None

    def test_finder_uncached_when_root_missing(self, tmp_path):
        cache = ScanCache(ttl=600, path=str(tmp_path / "cache.json"))
        cache.put_finder("finder", ([str(tmp_path / "root")],), ["a", "b"])
        assert cache.get_finder("finder", ([str(tmp_path / "root")],)) is None

    def test_finder_cached_when_root_stable(self, tmp_path):
        cache = ScanCache(ttl=600, path=str(tmp_path / "cache.json"))
        root = tmp_path / "root"
        root.mkdir()
        cache.put_finder("finder", ([str(root)],), [str(root / "x")])
        assert cache.get_finder("finder", ([str(root)],)) == [str(root / "x")]

    def test_finder_invalidated_by_root_change(self, tmp_path):
        cache = ScanCache(ttl=600, path=str(tmp_path / "cache.json"))
        root = tmp_path / "root"
        root.mkdir()
        cache.put_finder("finder", ([str(root)],), [str(root / "x")])
        time.sleep(0.02)
        (root / "new").mkdir()
        assert cache.get_finder("finder", ([str(root)],)) is None

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "cache.json")
        cache = ScanCache(ttl=600, path=path)
        _tree(tmp_path / "t", {"a.txt": b"x" * 100})
        cache.put_dir(str(tmp_path / "t"), (), True, False, 200000, 100, 1, 0)
        cache.save()
        cache2 = ScanCache(ttl=600, path=path)
        assert cache2.get_dir(str(tmp_path / "t")) == (100, 1, 0)

    def test_clear_wipes_and_file(self, tmp_path):
        path = str(tmp_path / "cache.json")
        cache = ScanCache(ttl=600, path=path)
        _tree(tmp_path / "t", {"a.txt": b"x" * 100})
        cache.put_dir(str(tmp_path / "t"), (), True, False, 200000, 100, 1, 0)
        cache.save()
        cache.clear()
        assert cache.get_dir(str(tmp_path / "t")) is None


def test_scan_category_uses_cache(tmp_path):
    from crapcleaner.core.scanner import scan_category
    from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel

    _tree(tmp_path / "t", {"a.txt": b"x" * 100})
    cat = CleanupCategory(
        id="c",
        name="C",
        description="d",
        safety_level=SafetyLevel.SAFE,
        targets=[CacheTarget(path=str(tmp_path / "t"))],
    )
    cache = ScanCache(ttl=600, path=str(tmp_path / "cache.json"))
    r1 = scan_category(cat, cache=cache)
    assert r1.size == 100
    hits_before = cache.stats[0]
    r2 = scan_category(cat, cache=cache)
    assert r2.size == 100
    assert cache.stats[0] == hits_before + 1


class TestExpiredCacheFile:
    """BUG-04: a cache that pruned to nothing was left on disk and reparsed forever."""

    def _write_file(self, path, cached_at):
        path.write_text(
            json.dumps(
                {
                    "entries": {
                        key: {"total": 1, "count": 1, "skipped": 0, "cached_at": at}
                        for key, at in cached_at.items()
                    }
                }
            ),
            encoding="utf-8",
        )

    def test_a_fully_expired_cache_is_removed(self, tmp_path):
        path = tmp_path / "cache.json"
        self._write_file(path, {"stale": time.time() - 100_000})

        ScanCache(ttl=300, path=str(path)).save()

        assert not path.exists()

    def test_a_partly_expired_cache_keeps_only_the_fresh_entries(self, tmp_path):
        path = tmp_path / "cache.json"
        self._write_file(path, {"stale": time.time() - 100_000, "fresh": time.time()})

        ScanCache(ttl=300, path=str(path)).save()

        assert set(json.loads(path.read_text(encoding="utf-8"))["entries"]) == {"fresh"}
