# -*- coding: utf-8 -*-
"""
本地缓存管理器 (Cache Manager)
==============================

职责:
1. 缓存已解析的历史行情数据，避免重复请求数据源
2. 缓存策略规则匹配结果，避免重复计算
3. 支持 TTL 过期 + LRU 淘汰策略
4. 线程安全，支持内存 + 磁盘双级缓存

缓存层级:
- L1 (内存): 热数据，dict + OrderedDict 实现 LRU
- L2 (磁盘): 冷数据，SQLite 持久化

使用示例:
    cache = CacheManager()
    cache.set("key", data, ttl=600)
    data = cache.get("key")
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
import sqlite3
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """缓存统计信息"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    sets: int = 0
    mem_size: int = 0
    disk_size: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total * 100, 1) if total > 0 else 0.0


class MemCache:
    """L1 内存缓存 (LRU + TTL)"""

    def __init__(self, max_entries: int = 2000):
        self._max_entries = max_entries
        self._store: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str, ttl: float = 0) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expiry = entry
            if ttl > 0 and time.time() > expiry:
                del self._store[key]
                return None
            # LRU: 移到最后
            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: float = 0):
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            elif len(self._store) >= self._max_entries:
                # 淘汰最久未用的
                self._store.popitem(last=False)
            expiry = time.time() + ttl if ttl > 0 else float('inf')
            self._store[key] = (value, expiry)

    def delete(self, key: str):
        with self._lock:
            self._store.pop(key, None)

    def clear(self):
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


class DiskCache:
    """L2 磁盘缓存 (SQLite)"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(
                Path(__file__).parent.parent.parent / "data" / "cache.db"
            )
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path, timeout=10)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_entries (
                key TEXT PRIMARY KEY,
                value BLOB NOT NULL,
                created_at REAL NOT NULL,
                ttl REAL NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_ttl
            ON cache_entries(created_at, ttl)
        """)
        conn.commit()

    def get(self, key: str) -> Optional[Any]:
        try:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT value, created_at, ttl FROM cache_entries WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            value_blob, created_at, ttl = row
            if ttl > 0 and time.time() - created_at > ttl:
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                conn.commit()
                return None
            return pickle.loads(value_blob)
        except Exception as e:
            logger.debug("磁盘缓存读取失败 (%s): %s", key, e)
            return None

    def set(self, key: str, value: Any, ttl: float = 0):
        try:
            conn = self._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO cache_entries VALUES (?, ?, ?, ?)",
                (key, pickle.dumps(value), time.time(), ttl),
            )
            conn.commit()
        except Exception as e:
            logger.debug("磁盘缓存写入失败 (%s): %s", key, e)

    def delete(self, key: str):
        try:
            conn = self._get_conn()
            conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            conn.commit()
        except Exception as e:
            logger.debug("磁盘缓存删除失败 (%s): %s", key, e)

    def cleanup_expired(self) -> int:
        """清理过期条目，返回清理数量"""
        try:
            conn = self._get_conn()
            cursor = conn.execute(
                "DELETE FROM cache_entries WHERE ttl > 0 AND ? - created_at > ttl",
                (time.time(),),
            )
            conn.commit()
            return cursor.rowcount
        except Exception:
            return 0

    @property
    def size(self) -> int:
        try:
            conn = self._get_conn()
            row = conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()
            return row[0] if row else 0
        except Exception:
            return 0


class CacheManager:
    """
    两级缓存管理器

    缓存命名空间:
    - history:    历史K线数据 (TTL=3600, 交易时段内不过期)
    - strategy:   策略匹配结果 (TTL=300)
    - fundamental:基本面数据 (TTL=86400)
    - news:       新闻资讯 (TTL=1800)
    - analysis:   分析计算结果 (TTL=600)
    """

    # 各命名空间默认TTL（秒）
    DEFAULT_TTLS = {
        "history": 3600,      # 1小时
        "strategy": 300,      # 5分钟
        "fundamental": 86400,  # 24小时
        "news": 1800,         # 30分钟
        "analysis": 600,      # 10分钟
        "quote": 10,          # 10秒（实时行情）
    }

    _instance: Optional["CacheManager"] = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        mem_max_entries: int = 2000,
        disk_enabled: bool = True,
        db_path: Optional[str] = None,
    ):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self._mem = MemCache(max_entries=mem_max_entries)
        self._disk_enabled = disk_enabled
        self._disk = DiskCache(db_path) if disk_enabled else None
        self._stats = CacheStats()
        self._stats_lock = threading.Lock()

        logger.info(
            "缓存管理器初始化: 内存=%d条, 磁盘=%s",
            mem_max_entries, "启用" if disk_enabled else "禁用",
        )

    # ============================================================
    #  核心API
    # ============================================================

    def _build_key(self, namespace: str, *parts: str) -> str:
        """构建缓存键"""
        raw = f"{namespace}:{'|'.join(parts)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(
        self,
        namespace: str,
        *key_parts: str,
        default_ttl: Optional[float] = None,
    ) -> Optional[Any]:
        """获取缓存值"""
        key = self._build_key(namespace, *key_parts)
        ttl = default_ttl or self.DEFAULT_TTLS.get(namespace, 600)

        # L1: 内存
        value = self._mem.get(key, ttl)
        if value is not None:
            with self._stats_lock:
                self._stats.hits += 1
            return value

        # L2: 磁盘
        if self._disk_enabled and self._disk:
            value = self._disk.get(key)
            if value is not None:
                # 回填到内存
                self._mem.set(key, value, ttl)
                with self._stats_lock:
                    self._stats.hits += 1
                return value

        with self._stats_lock:
            self._stats.misses += 1
        return None

    def set(
        self,
        namespace: str,
        *key_parts: str,
        value: Any,
        ttl: Optional[float] = None,
    ):
        """设置缓存值"""
        key = self._build_key(namespace, *key_parts)
        effective_ttl = ttl if ttl is not None else self.DEFAULT_TTLS.get(namespace, 600)

        self._mem.set(key, value, effective_ttl)
        if self._disk_enabled and self._disk:
            self._disk.set(key, value, effective_ttl)

        with self._stats_lock:
            self._stats.sets += 1

    def get_or_set(
        self,
        namespace: str,
        *key_parts: str,
        factory: Callable[[], Any],
        ttl: Optional[float] = None,
    ) -> Any:
        """获取缓存，如果不存在则调用 factory 生成并缓存"""
        cached = self.get(namespace, *key_parts, default_ttl=ttl)
        if cached is not None:
            return cached
        value = factory()
        if value is not None:
            self.set(namespace, *key_parts, value=value, ttl=ttl)
        return value

    def invalidate(self, namespace: str, *key_parts: str):
        """使缓存失效"""
        key = self._build_key(namespace, *key_parts)
        self._mem.delete(key)
        if self._disk_enabled and self._disk:
            self._disk.delete(key)

    def invalidate_namespace(self, namespace: str):
        """使整个命名空间失效（仅内存层，磁盘通过TTL自然过期）"""
        self._mem.clear()
        # 磁盘层通过cleanup_expired清理
        if self._disk_enabled and self._disk:
            self._disk.cleanup_expired()

    def cleanup(self) -> int:
        """清理过期缓存"""
        count = 0
        if self._disk_enabled and self._disk:
            count = self._disk.cleanup_expired()
        return count

    @property
    def stats(self) -> CacheStats:
        with self._stats_lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                sets=self._stats.sets,
                mem_size=len(self._mem),
                disk_size=self._disk.size if self._disk else 0,
            )

    def get_stats_dict(self) -> Dict[str, Any]:
        s = self.stats
        return {
            "hits": s.hits,
            "misses": s.misses,
            "hit_rate": s.hit_rate,
            "evictions": s.evictions,
            "sets": s.sets,
            "mem_entries": s.mem_size,
            "disk_entries": s.disk_size,
        }


# ============================================================
#  便捷函数
# ============================================================

def get_cache() -> CacheManager:
    """获取缓存管理器单例"""
    return CacheManager()


def cached(
    namespace: str,
    ttl: Optional[float] = None,
    key_func: Optional[Callable[..., str]] = None,
):
    """装饰器：自动缓存函数返回值

    Usage:
        @cached("history", ttl=3600)
        def get_daily_kline(code: str, date: str) -> dict:
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_cache()
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # 默认：函数名 + 参数
                key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            return cache.get_or_set(
                namespace, key,
                factory=lambda: func(*args, **kwargs),
                ttl=ttl,
            )
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
