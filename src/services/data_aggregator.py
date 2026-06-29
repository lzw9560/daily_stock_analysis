# -*- coding: utf-8 -*-
"""
多源数据聚合服务 (Data Aggregator)
====================================

职责:
1. 聚合多个数据源的数据进行交叉验证
2. 为决策分析提供统一数据视图
3. 管理各数据源的可用性状态
4. 按场景智能选择最佳数据源组合

数据源选择策略:
- 行情数据: Efinance(主) → Tencent(实时补充) → AKShare(备份)
- 选股筛选: iWenCai(智能筛选) → AKShare(枚举弥补)
- 热点分析: THS Hotspot(主) → 板块热度(从涨停数据推断)
- 基本面: AKShare Fundamental → Tushare(按需)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DataSourceStatus:
    """数据源状态"""
    name: str
    available: bool = True
    last_success: Optional[float] = None
    last_error: Optional[str] = None
    error_count: int = 0
    total_calls: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return (self.total_calls - self.error_count) / self.total_calls


@dataclass
class AggregatedMarketData:
    """聚合后的市场数据"""
    # 指数行情（多源交叉验证）
    indices: List[Dict[str, Any]] = field(default_factory=list)
    indices_source: str = ""

    # 市场统计
    market_stats: Dict[str, Any] = field(default_factory=dict)
    stats_source: str = ""

    # 实时行情（按需缓存）
    quotes: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # 热点数据
    hot_concepts: List[Dict[str, Any]] = field(default_factory=list)
    fund_flow: List[Dict[str, Any]] = field(default_factory=list)
    market_heat_score: int = 50
    sentiment_signal: str = "neutral"

    # 选股结果
    screening_results: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    # 元信息
    data_sources_used: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class DataAggregator:
    """
    多源数据聚合器

    设计原则:
    - 各数据源独立容错，一个源失败不影响其他
    - 按场景组合数据源，避免冗余请求
    - 交叉验证关键数据，标记数据冲突
    """

    def __init__(self):
        self._source_status: Dict[str, DataSourceStatus] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

        # 延迟加载各 Fetcher
        self._tencent_fetcher = None
        self._iwencai_fetcher = None
        self._ths_hotspot_fetcher = None

    # ========================
    #  Lazy Init
    # ========================

    @property
    def tencent(self):
        if self._tencent_fetcher is None:
            from data_provider.tencent_fetcher import TencentFetcher
            self._tencent_fetcher = TencentFetcher()
        return self._tencent_fetcher

    @property
    def iwencai(self):
        if self._iwencai_fetcher is None:
            from data_provider.iwencai_fetcher import create_iwencai_fetcher
            self._iwencai_fetcher = create_iwencai_fetcher()
        return self._iwencai_fetcher

    @property
    def ths_hotspot(self):
        if self._ths_hotspot_fetcher is None:
            from data_provider.ths_hotspot_fetcher import create_ths_hotspot_fetcher
            self._ths_hotspot_fetcher = create_ths_hotspot_fetcher()
        return self._ths_hotspot_fetcher

    # ========================
    #  场景化数据聚合
    # ========================

    def aggregate_for_seal_plate(
        self,
        sector_names: Optional[List[str]] = None,
        stock_codes: Optional[List[str]] = None,
    ) -> AggregatedMarketData:
        """
        为打板助手聚合决策数据

        数据组合:
        - THS Hotspot: 热点概念 + 资金流向（主）
        - Tencent Finance: 批量实时行情补充
        - iWenCai: 强势股筛选（可选）

        Args:
            sector_names: 关注的板块名称（从涨停数据提取）
            stock_codes: 关注的股票代码（用于实时行情）
        """
        result = AggregatedMarketData()
        sources_used: set[str] = set()

        # 1. 同花顺热点数据
        try:
            hot_analysis = self.ths_hotspot.get_market_hot_analysis()
            result.hot_concepts = hot_analysis.get("hot_concepts", [])
            result.fund_flow = (
                hot_analysis.get("fund_inflow_sectors", []) +
                hot_analysis.get("fund_outflow_sectors", [])
            )
            result.market_heat_score = hot_analysis.get("market_heat_score", 50)
            result.sentiment_signal = hot_analysis.get("sentiment_signal", "neutral")
            sources_used.add("THSHotspotFetcher")
            self.logger.info(
                "[Aggregator] 同花顺热点: heat=%d signal=%s concepts=%d",
                result.market_heat_score,
                result.sentiment_signal,
                len(result.hot_concepts),
            )
        except Exception as e:
            self.logger.warning("[Aggregator] 同花顺热点获取失败: %s", e)
            result.warnings.append("同花顺热点数据不可用")

        # 2. 腾讯财经批量实时行情
        if stock_codes:
            try:
                quotes = self.tencent.get_batch_realtime_quotes(stock_codes)
                for code, quote in quotes.items():
                    result.quotes[code] = quote.to_dict() if hasattr(quote, 'to_dict') else {}
                sources_used.add("TencentFetcher")
                self.logger.info(
                    "[Aggregator] 腾讯财经批量行情: %d/%d",
                    len(result.quotes), len(stock_codes),
                )
            except Exception as e:
                self.logger.warning("[Aggregator] 腾讯财经批量行情失败: %s", e)
                result.warnings.append("腾讯财经批量行情不可用")

        # 3. iWenCai 强势股筛选
        try:
            strong = self.iwencai.get_strong_stocks()
            if strong:
                result.screening_results["strong_stocks"] = strong
                sources_used.add("IwenCaiFetcher")
                self.logger.info("[Aggregator] 问财选股: %d 只强势股", len(strong))
        except Exception as e:
            self.logger.warning("[Aggregator] 问财选股失败: %s", e)

        # 4. 板块热度交叉分析
        if sector_names and result.hot_concepts:
            try:
                intersection = self.ths_hotspot.get_concept_intersection(sector_names)
                result.screening_results["sector_hot_analysis"] = intersection
            except Exception as e:
                self.logger.debug("[Aggregator] 板块交叉分析失败: %s", e)

        result.data_sources_used = sorted(sources_used)
        return result

    def aggregate_for_strategy(
        self,
        strategy_name: str,
        **params,
    ) -> AggregatedMarketData:
        """
        为策略分析聚合数据

        按策略类型组合最佳数据源:
        - 趋势策略: 腾讯K线 + iWenCai动量股
        - 涨停策略: THS热点 + iWenCai连板筛选
        - 放量策略: 腾讯量比 + iWenCai放量股
        """
        result = AggregatedMarketData()
        sources_used: set[str] = set()

        # 根据策略特征决定数据源组合
        if "limit" in strategy_name.lower() or "dragon" in strategy_name.lower():
            # 涨停/龙头策略 → 重点关注热点
            try:
                hot_analysis = self.ths_hotspot.get_market_hot_analysis()
                result.hot_concepts = hot_analysis.get("hot_concepts", [])
                result.market_heat_score = hot_analysis.get("market_heat_score", 50)
                sources_used.add("THSHotspotFetcher")
            except Exception as e:
                logger.warning("热点分析获取失败: %s", e)

            try:
                recent_limit = self.iwencai.get_recent_limit_up(days=2)
                result.screening_results["recent_limit_up"] = recent_limit
                sources_used.add("IwenCaiFetcher")
            except Exception as e:
                logger.warning("近期涨停数据获取失败: %s", e)

        elif "volume" in strategy_name.lower():
            # 放量策略 → 重点关注量比
            try:
                breakout = self.iwencai.get_volume_breakout()
                result.screening_results["volume_breakout"] = breakout
                sources_used.add("IwenCaiFetcher")
            except Exception as e:
                logger.warning("放量突破数据获取失败: %s", e)

        elif "momentum" in strategy_name.lower() or "trend" in strategy_name.lower():
            # 趋势策略 → 动量选股
            try:
                momentum = self.iwencai.get_momentum_stocks(min_change=10, days=10)
                result.screening_results["momentum_stocks"] = momentum
                sources_used.add("IwenCaiFetcher")
            except (ConnectionError, TimeoutError, TypeError) as e:
                logger.warning("动量选股数据获取失败: %s", e)

        result.data_sources_used = sorted(sources_used)
        return result

    # ========================
    #  交叉验证
    # ========================

    def verify_realtime_quote(
        self, stock_code: str, primary_price: float, primary_change_pct: float
    ) -> Optional[Dict[str, Any]]:
        """
        用腾讯财经交叉验证实时价格

        Args:
            stock_code: 股票代码
            primary_price: 主数据源的价格
            primary_change_pct: 主数据源的涨跌幅

        Returns:
            {"match": bool, "tencent_price": float, "deviation_pct": float}
            腾讯不可用时返回 None
        """
        try:
            quote = self.tencent.get_realtime_quote(stock_code)
            if not quote:
                return None

            deviation = abs(quote.price - primary_price) / primary_price * 100

            return {
                "match": deviation < 0.5,
                "tencent_price": quote.price,
                "tencent_change_pct": quote.change_pct,
                "deviation_pct": round(deviation, 3),
            }
        except Exception as e:
            self.logger.debug(f"[Aggregator] 交叉验证失败 {stock_code}: {e}")
            return None

    # ========================
    #  数据源健康检查
    # ========================

    def check_sources_health(self) -> Dict[str, DataSourceStatus]:
        """检查各数据源可用性"""
        health: Dict[str, DataSourceStatus] = {}

        # 腾讯财经
        status = DataSourceStatus(name="TencentFetcher")
        try:
            quote = self.tencent.get_realtime_quote("000001")
            status.available = quote is not None
        except (ConnectionError, TimeoutError) as e:
            logger.warning("TencentFetcher 健康检查失败: %s", e)
            status.available = False
        health["TencentFetcher"] = status

        # iWenCai
        status = DataSourceStatus(name="IwenCaiFetcher")
        try:
            results = self.iwencai.stock_screening("今日涨停", top_n=5)
            status.available = len(results) > 0
        except (ConnectionError, TimeoutError, TypeError) as e:
            logger.warning("IwenCaiFetcher 健康检查失败: %s", e)
            status.available = False
        health["IwenCaiFetcher"] = status

        # THS Hotspot
        status = DataSourceStatus(name="THSHotspotFetcher")
        try:
            concepts = self.ths_hotspot.get_hot_concepts(top_n=5)
            status.available = len(concepts) > 0
        except (ConnectionError, TimeoutError, TypeError) as e:
            logger.warning("THSHotspotFetcher 健康检查失败: %s", e)
            status.available = False
        health["THSHotspotFetcher"] = status

        return health

    def get_health_summary(self) -> Dict[str, Any]:
        """获取数据源健康摘要"""
        health = self.check_sources_health()
        available = sum(1 for s in health.values() if s.available)
        total = len(health)

        return {
            "total_sources": total,
            "available_sources": available,
            "status": "healthy" if available >= total * 0.6 else "degraded",
            "sources": {
                name: {
                    "available": s.available,
                    "success_rate": s.success_rate,
                }
                for name, s in health.items()
            },
        }
