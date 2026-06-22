# -*- coding: utf-8 -*-
"""
同花顺热点数据源 (THS Hotspot Fetcher)
========================================

优势:
- 零鉴权、实时热点数据
- 热点概念/板块资金流向一目了然

短板:
- 接口不稳定、无历史数据
- 依赖同花顺服务可用性

适用场景:
- 短线热点监控
- 情绪周期判断
- 打板助手题材热度分析

数据来源:
- 同花顺概念板块: http://data.10jqka.com.cn/
- 同花顺资金流向: http://data.10jqka.com.cn/funds/
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional, List, Dict, Any

import requests

logger = logging.getLogger(__name__)

# 同花顺热点 API 端点
_THS_CONCEPT_URL = (
    "http://data.10jqka.com.cn/dataapi/block/themeIndex"
    "?type=0&page=1&perpage=30"
)
_THS_CONCEPT_DETAIL_URL = (
    "http://data.10jqka.com.cn/dataapi/block/blockDetail"
    "?code={code}&type=0&page=1&perpage=50"
)
_THS_FUND_FLOW_URL = (
    "http://data.10jqka.com.cn/dataapi/fundflow/industryRank"
    "?type=0&page=1&perpage=20"
)
# 备用：概念板块排行
_THS_CONCEPT_RANK_URL = (
    "http://q.10jqka.com.cn/gn/detail/code/{code}/"
)


class THSHotspotFetcher:
    """同花顺热点数据获取器

    独立工具类，提供热点概念、板块资金流向、题材热度等数据。
    特别适用于打板助手中的情绪周期判断和板块热度分析。
    """

    name = "THSHotspotFetcher"
    REQUEST_TIMEOUT = 10

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "http://data.10jqka.com.cn/",
        })
        self.logger = logging.getLogger(self.__class__.__name__)

    # ========================
    #  热点概念
    # ========================

    def get_hot_concepts(self, top_n: int = 20) -> List[Dict[str, Any]]:
        """
        获取当日热点概念板块

        Returns:
            概念列表，每项包含:
            - code: 概念代码
            - name: 概念名称
            - change_pct: 涨跌幅(%)
            - up_count / down_count: 上涨/下跌家数
            - leading_stock: 领涨股
            - leading_stock_change: 领涨股涨幅
            - fund_flow: 主力净流入(亿)
            - heat_score: 热度评分(0-100)
        """
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                resp = self._session.get(_THS_CONCEPT_URL, timeout=self.REQUEST_TIMEOUT)
                # 检测HTML响应（反爬/错误页）
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" in content_type.lower():
                    self.logger.warning("同花顺概念接口返回HTML而非JSON (attempt %d/%d)", attempt + 1, max_retries + 1)
                    if attempt < max_retries:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    return []
                data = resp.json()
            except Exception as e:
                self.logger.warning("同花顺概念请求失败 (attempt %d/%d): %s", attempt + 1, max_retries + 1, e)
                if attempt < max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return []

        concepts = self._parse_concepts(data)
        return concepts[:top_n]

    def get_concept_detail(self, concept_code: str) -> List[Dict[str, Any]]:
        """获取概念板块成分股"""
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                url = _THS_CONCEPT_DETAIL_URL.format(code=concept_code)
                resp = self._session.get(url, timeout=self.REQUEST_TIMEOUT)
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" in content_type.lower():
                    self.logger.warning("同花顺概念详情返回HTML (attempt %d/%d)", attempt + 1, max_retries + 1)
                    if attempt < max_retries:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    return []
                data = resp.json()
                return self._parse_concept_stocks(data)
            except Exception as e:
                self.logger.warning("同花顺概念详情请求失败 (attempt %d/%d): %s", attempt + 1, max_retries + 1, e)
                if attempt < max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return []

    # ========================
    #  资金流向
    # ========================

    def get_sector_fund_flow(self, top_n: int = 15) -> List[Dict[str, Any]]:
        """
        获取行业板块资金流向排行

        Returns:
            板块资金流向列表
            - name: 板块名称
            - main_net_inflow: 主力净流入(亿)
            - super_large_net: 超大单净流入
            - change_pct: 板块涨跌幅
        """
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                resp = self._session.get(_THS_FUND_FLOW_URL, timeout=self.REQUEST_TIMEOUT)
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" in content_type.lower():
                    self.logger.warning("同花顺资金流向返回HTML (attempt %d/%d)", attempt + 1, max_retries + 1)
                    if attempt < max_retries:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    return []
                data = resp.json()
                return self._parse_fund_flow(data)[:top_n]
            except Exception as e:
                self.logger.warning("同花顺资金流向请求失败 (attempt %d/%d): %s", attempt + 1, max_retries + 1, e)
                if attempt < max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return []

    # ========================
    #  综合分析
    # ========================

    def get_market_hot_analysis(self) -> Dict[str, Any]:
        """
        市场热度综合分析

        结合概念热度 + 资金流向，给出当日市场的综合研判。
        用于打板助手的情绪周期分析。

        Returns:
            {
                "hot_concepts": [...],      # 热点概念 TOP10
                "fund_inflow_sectors": [...],  # 资金流入板块
                "fund_outflow_sectors": [...],  # 资金流出板块
                "market_heat_score": int,     # 市场热度评分 0-100
                "market_focus": str,          # 市场焦点描述
                "sentiment_signal": str,      # 情绪信号: bullish/bearish/neutral
                "suggested_sectors": [...],   # 建议关注板块
            }
        """
        concepts = self.get_hot_concepts(15)
        fund_flow = self.get_sector_fund_flow(15)

        # 计算热度评分
        heat_score = self._calculate_heat_score(concepts, fund_flow)

        # 区分流入/流出
        inflow_sectors = [f for f in fund_flow if f.get("main_net_inflow", 0) > 0]
        outflow_sectors = [f for f in fund_flow if f.get("main_net_inflow", 0) < 0]

        # 情绪信号
        if heat_score >= 70:
            sentiment_signal = "bullish"
        elif heat_score >= 40:
            sentiment_signal = "neutral"
        else:
            sentiment_signal = "bearish"

        # 市场焦点
        if concepts:
            top3_names = ", ".join(c["name"] for c in concepts[:3])
            market_focus = f"资金聚焦{top3_names}"
        else:
            market_focus = "热点分散，无明确主线"

        # 建议关注（资金流入 + 涨幅靠前的板块交集）
        hot_names = {c["name"] for c in concepts[:10]}
        suggested = [
            f for f in inflow_sectors[:5]
            if f.get("name") in hot_names
        ]

        return {
            "hot_concepts": [
                {
                    "name": c["name"],
                    "change_pct": c.get("change_pct", 0),
                    "leading_stock": c.get("leading_stock", ""),
                    "heat_score": c.get("heat_score", 0),
                }
                for c in concepts[:10]
            ],
            "fund_inflow_sectors": [
                {"name": f["name"], "net_inflow": f.get("main_net_inflow", 0)}
                for f in inflow_sectors[:5]
            ],
            "fund_outflow_sectors": [
                {"name": f["name"], "net_outflow": abs(f.get("main_net_inflow", 0))}
                for f in outflow_sectors[:5]
            ],
            "market_heat_score": heat_score,
            "market_focus": market_focus,
            "sentiment_signal": sentiment_signal,
            "suggested_sectors": suggested,
        }

    def get_concept_intersection(
        self, stock_sectors: List[str]
    ) -> Dict[str, List[str]]:
        """
        判断股票的板块是否属于当日热点

        Args:
            stock_sectors: 股票的板块列表

        Returns:
            {"hot": [...], "warm": [...], "cold": [...]}
        """
        concepts = self.get_hot_concepts(20)
        hot_names_top5 = {c["name"] for c in concepts[:5]}
        hot_names_top15 = {c["name"] for c in concepts[:15]}

        result = {"hot": [], "warm": [], "cold": []}
        for sector in stock_sectors:
            if sector in hot_names_top5:
                result["hot"].append(sector)
            elif sector in hot_names_top15:
                result["warm"].append(sector)
            else:
                result["cold"].append(sector)

        return result

    # ========================
    #  内部方法
    # ========================

    def _parse_concepts(self, data: Any) -> List[Dict[str, Any]]:
        """解析热点概念列表"""
        concepts: List[Dict[str, Any]] = []
        try:
            items = data.get("data", {}).get("list", [])
            if not items:
                items = data.get("list", [])
            if not items and isinstance(data, list):
                items = data

            for item in items:
                concepts.append({
                    "code": str(item.get("code", item.get("concept_code", ""))),
                    "name": str(item.get("name", item.get("concept_name", ""))),
                    "change_pct": float(item.get("change", item.get("change_pct", 0)) or 0),
                    "up_count": int(item.get("up_count", 0) or 0),
                    "down_count": int(item.get("down_count", 0) or 0),
                    "leading_stock": str(item.get("leading", item.get("leading_stock", ""))),
                    "leading_stock_change": float(item.get("leading_change", 0) or 0),
                    "fund_flow": float(item.get("main_net_inflow", item.get("fund_flow", 0)) or 0),
                    "heat_score": self._estimate_heat(item),
                })
        except Exception as e:
            self.logger.debug("解析概念列表失败: %s", e)

        return concepts

    def _parse_concept_stocks(self, data: Any) -> List[Dict[str, Any]]:
        """解析概念板块成分股"""
        stocks: List[Dict[str, Any]] = []
        try:
            items = data.get("data", {}).get("list", [])
            if not items:
                items = data.get("list", [])

            for item in items:
                stocks.append({
                    "code": str(item.get("code", "")),
                    "name": str(item.get("name", "")),
                    "price": float(item.get("price", 0) or 0),
                    "change_pct": float(item.get("change", item.get("change_pct", 0)) or 0),
                })
        except Exception as e:
            self.logger.debug("解析概念成分股失败: %s", e)

        return stocks

    def _parse_fund_flow(self, data: Any) -> List[Dict[str, Any]]:
        """解析资金流向数据"""
        flow_list: List[Dict[str, Any]] = []
        try:
            items = data.get("data", {}).get("list", [])
            if not items:
                items = data.get("list", [])

            for item in items:
                flow_list.append({
                    "name": str(item.get("name", item.get("sector_name", ""))),
                    "code": str(item.get("code", "")),
                    "change_pct": float(item.get("change", item.get("change_pct", 0)) or 0),
                    "main_net_inflow": float(item.get("main_net", item.get("main_net_inflow", 0)) or 0),
                    "super_large_net": float(item.get("super_large", item.get("super_large_net", 0)) or 0),
                    "large_net": float(item.get("large", item.get("large_net", 0)) or 0),
                })
        except Exception as e:
            self.logger.debug("解析资金流向失败: %s", e)

        return flow_list

    @staticmethod
    def _estimate_heat(item: Dict[str, Any]) -> int:
        """估算板块热度评分"""
        score = 50
        try:
            change = abs(float(item.get("change", item.get("change_pct", 0)) or 0))
            up_count = int(item.get("up_count", 0) or 0)
            total = up_count + int(item.get("down_count", 0) or 0)

            score += min(change * 2, 30)  # 涨幅贡献
            if total > 0:
                ratio = up_count / total
                score += int(ratio * 20)  # 涨跌比贡献
        except Exception:
            pass

        return min(100, max(0, score))

    @staticmethod
    def _calculate_heat_score(
        concepts: List[Dict],
        fund_flow: List[Dict],
    ) -> int:
        """计算综合市场热度评分"""
        if not concepts:
            return 30

        score = 50

        # 概念平均涨幅
        avg_change = sum(c.get("change_pct", 0) for c in concepts[:10]) / max(
            len(concepts[:10]), 1
        )
        score += min(avg_change * 2, 20)

        # 资金流入板块占比
        if fund_flow:
            inflow_ratio = sum(
                1 for f in fund_flow[:10] if f.get("main_net_inflow", 0) > 0
            ) / max(len(fund_flow[:10]), 1)
            score += int(inflow_ratio * 20)

        # 领涨股涨幅
        if concepts:
            top_lead = max(
                (c.get("leading_stock_change", 0) for c in concepts[:5]),
                default=0,
            )
            score += min(top_lead, 10)

        return min(100, max(0, int(score)))


def create_ths_hotspot_fetcher() -> THSHotspotFetcher:
    """工厂方法"""
    return THSHotspotFetcher()
