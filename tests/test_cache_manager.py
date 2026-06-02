# -*- coding: utf-8 -*-
"""测试本地缓存管理器"""

import time
import pytest
from src.services.cache_manager import (
    CacheManager, MemCache, DiskCache, get_cache, cached,
)


class TestMemCache:
    """内存缓存测试"""

    def test_set_and_get(self):
        cache = MemCache(max_entries=100)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key(self):
        cache = MemCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        cache = MemCache(max_entries=100)
        cache.set("key1", "value1", ttl=0.01)  # 10ms TTL
        time.sleep(0.02)
        assert cache.get("key1", ttl=0.01) is None

    def test_lru_eviction(self):
        cache = MemCache(max_entries=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # 应淘汰 'a'
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_lru_reorder_on_access(self):
        cache = MemCache(max_entries=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")  # 访问 'a'，移到末尾
        cache.set("d", 4)  # 应淘汰 'b'
        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_delete(self):
        cache = MemCache()
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear(self):
        cache = MemCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert len(cache) == 0


class TestDiskCache:
    """磁盘缓存测试"""

    def test_set_and_get(self, tmp_path):
        db_path = str(tmp_path / "test_cache.db")
        cache = DiskCache(db_path)
        cache.set("key1", {"data": [1, 2, 3]})
        result = cache.get("key1")
        assert result == {"data": [1, 2, 3]}

    def test_get_missing(self, tmp_path):
        cache = DiskCache(str(tmp_path / "test_cache.db"))
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self, tmp_path):
        cache = DiskCache(str(tmp_path / "test_cache.db"))
        cache.set("key1", "value", ttl=0.01)
        time.sleep(0.02)
        assert cache.get("key1") is None

    def test_overwrite(self, tmp_path):
        cache = DiskCache(str(tmp_path / "test_cache.db"))
        cache.set("key1", "old")
        cache.set("key1", "new")
        assert cache.get("key1") == "new"

    def test_cleanup_expired(self, tmp_path):
        cache = DiskCache(str(tmp_path / "test_cache.db"))
        cache.set("key1", "val1", ttl=0.01)
        cache.set("key2", "val2", ttl=3600)
        time.sleep(0.02)
        cleaned = cache.cleanup_expired()
        assert cleaned >= 1
        assert cache.get("key1") is None
        assert cache.get("key2") == "val2"


class TestCacheManager:
    """两级缓存管理器测试"""

    @pytest.fixture(autouse=True)
    def _clean_cache(self):
        """每个测试前清理缓存状态"""
        cache = get_cache()
        cache._mem.clear()
        yield
        cache._mem.clear()

    def test_singleton(self):
        c1 = get_cache()
        c2 = get_cache()
        assert c1 is c2

    def test_get_or_set_cache_hit(self):
        cache = get_cache()
        # 使用唯一的key避免跨测试污染
        import uuid
        uid = str(uuid.uuid4())
        cache.set("test", uid, "h", value="cached_value", ttl=60)
        call_count = [0]

        def factory():
            call_count[0] += 1
            return "new_value"

        result = cache.get_or_set("test", uid, "h", factory=factory)
        assert result == "cached_value"
        assert call_count[0] == 0

    def test_get_or_set_cache_miss(self):
        cache = get_cache()
        import uuid
        uid = str(uuid.uuid4())
        call_count = [0]

        def factory():
            call_count[0] += 1
            return "computed_value"

        result = cache.get_or_set("test", uid, "m", factory=factory, ttl=60)
        assert result == "computed_value"
        assert call_count[0] == 1

    def test_namespace_isolation(self):
        cache = get_cache()
        import uuid
        uid = str(uuid.uuid4())
        cache.set("ns_a", uid, value="val_a")
        cache.set("ns_b", uid, value="val_b")
        assert cache.get("ns_a", uid) == "val_a"
        assert cache.get("ns_b", uid) == "val_b"

    def test_invalidate(self):
        cache = get_cache()
        import uuid
        uid = str(uuid.uuid4())
        cache.set("test", uid, value="value1")
        cache.invalidate("test", uid)
        assert cache.get("test", uid) is None

    def test_stats_tracking(self):
        from src.services.cache_manager import CacheManager as CM
        # 创建完全独立的实例
        old_instance = CM._instance
        CM._instance = None
        try:
            cache = CM(mem_max_entries=100, disk_enabled=False)
            cache.set("stats_test", "s1", value="v")
            cache.get("stats_test", "s1")  # hit
            cache.get("stats_test", "s2")  # miss
            stats = cache.stats
            assert stats.hits == 1
            assert stats.misses == 1
            assert stats.sets == 1
        finally:
            CM._instance = old_instance

    def test_get_stats_dict(self):
        cache = get_cache()
        stats = cache.get_stats_dict()
        assert "hit_rate" in stats
        assert "mem_entries" in stats

    def test_cached_decorator(self):
        # 使用独立实例避免磁盘缓存污染
        from src.services.cache_manager import CacheManager as CM
        old_instance = CM._instance
        CM._instance = None
        try:
            cache = CM(mem_max_entries=100, disk_enabled=False)

            call_count = [0]

            @cached("test_decorator", ttl=60)
            def compute(x):
                call_count[0] += 1
                return x * 2

            r1 = compute(5)
            assert r1 == 10
            assert call_count[0] == 1
            r2 = compute(5)
            assert r2 == 10  # 缓存命中
            assert call_count[0] == 1  # 未再调用
        finally:
            CM._instance = old_instance


class TestCacheIntegration:
    """缓存与磁盘集成测试"""

    def test_mem_fallback_to_disk(self, tmp_path):
        """L1 miss → L2 hit → 回填L1"""
        db_path = str(tmp_path / "cache.db")
        cache = CacheManager(disk_enabled=True, db_path=db_path)
        cache.set("test", "key", value="disk_value", ttl=60)

        # 清除内存缓存模拟L1 miss
        cache._mem.clear()

        result = cache.get("test", "key")
        assert result == "disk_value"
        # 回填到内存
        assert cache._mem.get(cache._build_key("test", "key")) is not None
