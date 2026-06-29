# -*- coding: utf-8 -*-
"""实时数据服务 — 统一实时行情缓存与数据聚合层.

为推荐系统提供高效的实时数据访问，避免重复初始化和请求：
1. 单例 DataFetcherManager（生命周期内复用）
2. 内存缓存（带 TTL 过期）
3. 统一数据聚合（涨停池、板块排行、北向资金、市场统计）
4. 数据新鲜度标记
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    data: Any
    timestamp: float
    ttl: float


class RealTimeDataService:
    """实时数据服务（单例模式）."""

    _instance: Optional["RealTimeDataService"] = None
    _lock = threading.Lock()

    # 缓存 TTL（秒）
    TTL_MARKET_STATS = 30       # 市场统计 30s
    TTL_LIMIT_UP_POOL = 60      # 涨停池 60s
    TTL_SECTOR_RANKINGS = 120   # 板块排行 120s
    TTL_NORTH_BOUND = 300       # 北向资金 5min
    TTL_MARGIN = 600            # 融资融券 10min
    TTL_MONEY_FLOW = 120        # 资金流向 120s
    TTL_CONCEPT_RANKINGS = 120  # 概念排行 120s

    def __new__(cls) -> "RealTimeDataService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._cache: Dict[str, CacheEntry] = {}
        self._cache_lock = threading.Lock()
        self._manager = None
        self._manager_lock = threading.Lock()
        self._ths_fetcher = None
        self._ths_lock = threading.Lock()
        self._data_freshness: Dict[str, datetime] = {}

    @classmethod
    def reset_instance(cls):
        """重置单例（测试用）."""
        with cls._lock:
            cls._instance = None

    def _get_manager(self):
        """获取 DataFetcherManager（懒加载，fail-open）。"""
        if self._manager is not None:
            return self._manager
        with self._manager_lock:
            if self._manager is not None:
                return self._manager
            try:
                from data_provider.base import DataFetcherManager
                self._manager = DataFetcherManager()
                logger.info("DataFetcherManager 初始化成功")
            except Exception as e:
                logger.warning(f"DataFetcherManager 初始化失败: {e}")
                self._manager = None
            return self._manager

    def _get_ths_fetcher(self):
        """获取同花顺数据源（懒加载，fail-open）。"""
        if self._ths_fetcher is not None:
            return self._ths_fetcher
        with self._ths_lock:
            if self._ths_fetcher is not None:
                return self._ths_fetcher
            try:
                from data_provider.ths_hotspot_fetcher import THSHotspotFetcher
                self._ths_fetcher = THSHotspotFetcher()
                logger.info("THSHotspotFetcher 初始化成功")
            except Exception as e:
                logger.warning(f"THSHotspotFetcher 初始化失败: {e}")
                self._ths_fetcher = None
            return self._ths_fetcher

    def _get_cached(self, key: str) -> Optional[Any]:
        """获取缓存数据（检查 TTL）。"""
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry and (time.time() - entry.timestamp) < entry.ttl:
                return entry.data
        return None

    def _set_cache(self, key: str, data: Any, ttl: float):
        """设置缓存数据。"""
        with self._cache_lock:
            self._cache[key] = CacheEntry(data=data, timestamp=time.time(), ttl=ttl)

    def _update_freshness(self, key: str):
        """更新数据新鲜度时间戳。"""
        self._data_freshness[key] = datetime.now()

    def get_freshness(self) -> Dict[str, str]:
        """获取所有数据源的新鲜度信息。"""
        return {
            key: dt.strftime("%Y-%m-%d %H:%M:%S")
            for key, dt in self._data_freshness.items()
        }

    # ── 市场统计 ────────────────────────────────────────────────────────

    def get_market_stats(self) -> Dict[str, Any]:
        """获取实时市场涨跌统计（含缓存）。"""
        cache_key = "market_stats"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        result = {"limit_up_count": 0, "limit_down_count": 0, "advance_count": 0,
                  "decline_count": 0, "flat_count": 0, "total_turnover": 0,
                  "data_source": "none", "is_realtime": False}

        manager = self._get_manager()
        if not manager:
            self._set_cache(cache_key, result, self.TTL_MARKET_STATS)
            return result

        try:
            import efinance as ef
            df = ef.stock.get_realtime_quotes()
            if df is not None and not df.empty:
                result["limit_up_count"] = int((df["涨跌幅"] > 9.5).sum()) if "涨跌幅" in df.columns else 0
                result["limit_down_count"] = int((df["涨跌幅"] < -9.5).sum()) if "涨跌幅" in df.columns else 0
                result["advance_count"] = int((df["涨跌幅"] > 0).sum()) if "涨跌幅" in df.columns else 0
                result["decline_count"] = int((df["涨跌幅"] < 0).sum()) if "涨跌幅" in df.columns else 0
                result["flat_count"] = int((df["涨跌幅"] == 0).sum()) if "涨跌幅" in df.columns else 0
                if "成交额" in df.columns:
                    result["total_turnover"] = round(df["成交额"].sum() / 1e8, 1)
                result["data_source"] = "efinance_realtime"
                result["is_realtime"] = True
                self._update_freshness("market_stats")
        except ImportError:
            logger.debug("efinance 未安装，无法获取实时行情统计")
        except Exception as e:
            logger.warning(f"实时行情统计获取失败: {e}")

        self._set_cache(cache_key, result, self.TTL_MARKET_STATS)
        return result

    # ── 涨停池 ──────────────────────────────────────────────────────────

    def get_limit_up_pool(self, n: int = 20) -> List[Dict[str, Any]]:
        """获取涨停池（含缓存）。"""
        cache_key = f"limit_up_pool_{n}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        result: List[Dict[str, Any]] = []
        manager = self._get_manager()
        if manager:
            try:
                result = manager.get_limit_up_pool(n=n) or []
                self._update_freshness("limit_up_pool")
            except Exception as e:
                logger.warning(f"涨停池获取失败: {e}")

        self._set_cache(cache_key, result, self.TTL_LIMIT_UP_POOL)
        return result

    # ── 板块排行 ────────────────────────────────────────────────────────

    def get_sector_rankings(self, n: int = 5) -> Tuple[List[Dict], List[Dict]]:
        """获取板块涨跌榜（含缓存）。"""
        cache_key = f"sector_rankings_{n}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        result = ([], [])
        manager = self._get_manager()
        if manager:
            try:
                result = manager.get_sector_rankings(n=n)
                self._update_freshness("sector_rankings")
            except Exception as e:
                logger.warning(f"板块排行获取失败: {e}")

        self._set_cache(cache_key, result, self.TTL_SECTOR_RANKINGS)
        return result

    def get_concept_rankings(self, n: int = 5) -> Tuple[List[Dict], List[Dict]]:
        """获取概念板块排行（含缓存）。"""
        cache_key = f"concept_rankings_{n}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        result = ([], [])
        manager = self._get_manager()
        if manager:
            try:
                result = manager.get_concept_rankings(n=n)
                self._update_freshness("concept_rankings")
            except (ConnectionError, TimeoutError, ValueError, TypeError) as e:
                logger.warning(f"概念排行获取失败: {e}")

        self._set_cache(cache_key, result, self.TTL_CONCEPT_RANKINGS)
        return result

    # ── 北向资金 ────────────────────────────────────────────────────────

    def get_north_bound_context(self, top_n: int = 10) -> Dict[str, Any]:
        """获取北向资金上下文（含缓存）。"""
        cache_key = f"north_bound_{top_n}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        result: Dict[str, Any] = {"status": "failed", "today_net_inflow": None}
        manager = self._get_manager()
        if manager:
            try:
                result = manager.get_north_bound_context(top_n=top_n)
                self._update_freshness("north_bound")
            except Exception as e:
                logger.warning(f"北向资金获取失败: {e}")

        self._set_cache(cache_key, result, self.TTL_NORTH_BOUND)
        return result

    # ── 融资融券 ────────────────────────────────────────────────────────

    def get_margin_context(self) -> Dict[str, Any]:
        """获取融资融券上下文（含缓存）。"""
        cache_key = "margin_context"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        result: Dict[str, Any] = {}
        manager = self._get_manager()
        if manager:
            try:
                result = manager.get_margin_context()
                self._update_freshness("margin")
            except Exception as e:
                logger.warning(f"融资融券获取失败: {e}")

        self._set_cache(cache_key, result, self.TTL_MARGIN)
        return result

    # ── 资金流向 ────────────────────────────────────────────────────────

    def get_money_flow(self, top_n: int = 15) -> List[Dict[str, Any]]:
        """获取板块资金流向（含缓存）。

        数据源优先级：
        1. 同花顺 THS
        2. 东方财富 EM（降级）

        返回字段：
        - name: 板块名称
        - amount: 主力净流入(亿) — 兼容旧字段名
        - main_net_inflow: 主力净流入(亿)
        - change_pct: 板块涨跌幅(%)
        - super_large_net: 超大单净流入
        - large_net: 大单净流入
        """
        cache_key = f"money_flow_{top_n}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        result: List[Dict[str, Any]] = []
        used_source = ""

        # 优先同花顺
        ths = self._get_ths_fetcher()
        if ths:
            try:
                raw = ths.get_sector_fund_flow(top_n=top_n)
                if raw:
                    result = [
                        {
                            "name": f.get("name", ""),
                            "amount": round(f.get("main_net_inflow", 0), 1),
                            "main_net_inflow": round(f.get("main_net_inflow", 0), 1),
                            "change_pct": round(f.get("change_pct", 0), 2),
                            "super_large_net": round(f.get("super_large_net", 0), 1),
                            "large_net": round(f.get("large_net", 0), 1),
                        }
                        for f in raw
                    ]
                    used_source = "ths"
                    self._update_freshness("money_flow")
            except Exception as e:
                logger.warning(f"[同花顺] 资金流向获取失败: {e}")

        # 同花顺失败，降级到东方财富
        if not result:
            try:
                result = self._fetch_em_money_flow(top_n=top_n)
                if result:
                    used_source = "eastmoney"
                    self._update_freshness("money_flow")
            except Exception as e:
                logger.warning(f"[东方财富] 资金流向获取失败: {e}")

        if used_source:
            logger.info(f"板块资金流向数据源: {used_source}, 获取 {len(result)} 条")
        else:
            logger.warning("板块资金流向: 所有数据源均失败")

        self._set_cache(cache_key, result, self.TTL_MONEY_FLOW)
        return result

    def _fetch_em_money_flow(self, top_n: int = 15) -> List[Dict[str, Any]]:
        """从东方财富获取板块资金流向（降级方案）。

        使用 push2.eastmoney.com API 获取行业板块资金流向数据。
        fs=m:90+t:2 表示行业板块，按涨跌幅排序。
        """
        import requests as _requests

        url = (
            "http://push2.eastmoney.com/api/qt/clist/get"
            "?cb=&fid=f3&po=1&pz={pz}&pn=1&np=1&fltt=2&invt=2"
            "&fs=m:90+t:2"
            "&fields=f2,f3,f4,f12,f14,f62,f66,f69,f72,f75,f78,f81,f84,f87,f184,f204,f205"
        ).format(pz=top_n)

        try:
            resp = _requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": "http://data.eastmoney.com/",
            })
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", {}).get("diff", [])
            if not items:
                return []

            result = []
            for item in items:
                main_net = float(item.get("f62", 0) or 0)  # 元
                super_large = float(item.get("f66", 0) or 0)  # 元
                large_net = float(item.get("f72", 0) or 0)  # 元

                result.append({
                    "name": str(item.get("f14", "")),
                    "amount": round(main_net / 1e8, 1),        # 转为亿
                    "main_net_inflow": round(main_net / 1e8, 1),  # 转为亿
                    "change_pct": round(float(item.get("f3", 0) or 0), 2),
                    "super_large_net": round(super_large / 1e8, 1),
                    "large_net": round(large_net / 1e8, 1),
                })

            return result
        except Exception as e:
            logger.warning(f"东方财富板块资金流向请求失败: {e}")
            return []

    def get_hot_concepts(self, top_n: int = 15) -> List[Dict[str, Any]]:
        """获取同花顺热点概念（含缓存）。"""
        cache_key = f"hot_concepts_{top_n}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        result: List[Dict[str, Any]] = []
        ths = self._get_ths_fetcher()
        if ths:
            try:
                result = ths.get_hot_concepts(top_n=top_n)
                self._update_freshness("hot_concepts")
            except (ConnectionError, TimeoutError, TypeError) as e:
                logger.warning(f"热点概念获取失败: {e}")

        self._set_cache(cache_key, result, self.TTL_CONCEPT_RANKINGS)
        return result

    # ── 综合市场快照 ────────────────────────────────────────────────────

    def get_market_snapshot(self) -> Dict[str, Any]:
        """获取综合市场快照（一次请求聚合所有实时数据）。"""
        stats = self.get_market_stats()
        limit_up_pool = self.get_limit_up_pool(30)
        sectors, _ = self.get_sector_rankings(5)
        concepts, _ = self.get_concept_rankings(6)
        north_bound = self.get_north_bound_context(5)
        margin = self.get_margin_context()

        return {
            "market_stats": stats,
            "limit_up_pool": limit_up_pool,
            "top_sectors": sectors,
            "top_concepts": concepts,
            "north_bound": north_bound,
            "margin": margin,
            "data_freshness": self.get_freshness(),
            "snapshot_time": datetime.now().isoformat(),
        }
