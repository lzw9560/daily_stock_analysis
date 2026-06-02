# -*- coding: utf-8 -*-
"""
问财选股数据源 (iWenCai Fetcher)
================================

优势:
- 自然语言搜索、选股能力强
- 同花顺旗下产品，数据覆盖面广

短板:
- 需 API Key、调用频率受限
- 非官方公开 API，稳定性有波动

适用场景:
- 快速选股、策略验证
- 条件筛选（如"最近连续涨停"、"放量突破平台"）
- 作为推荐引擎的候选池补充

API 使用:
- 默认通过网页端接口调用（无需 Key 的临时方案）
- 可选配置 IWENCAI_API_KEY 使用高级接口
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional, List, Dict, Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# 问财网页端接口
_IWENCAI_SEARCH_URL = "http://www.iwencai.com/stockpick/search"
_IWENCAI_UNIFIED_URL = "http://www.iwencai.com/unifiedwap/unified-wap/result/get-stock-pick"


class IwenCaiFetcher:
    """问财选股数据获取器

    设计为独立工具类而非 BaseFetcher 子类，
    因为其能力偏向于选股筛选而非K线数据获取。
    """

    name = "IwenCaiFetcher"
    REQUEST_TIMEOUT = 15

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self.logger = logging.getLogger(self.__class__.__name__)

    def stock_screening(
        self,
        query: str,
        top_n: int = 20,
        **extra_filters,
    ) -> List[Dict[str, Any]]:
        """
        自然语言选股

        Args:
            query: 选股条件，如:
                   - "今日涨停"
                   - "连续2天涨停"
                   - "放量突破20日均线"
                   - "MACD金叉且成交量放大"
                   - "市盈率低于20且净利润增长"
                   - "最近5日主力资金净流入"
            top_n: 返回前N条结果
            extra_filters: 额外筛选条件

        Returns:
            符合条件的股票列表，每只包含:
            - code: 股票代码
            - name: 股票名称
            - price: 最新价
            - change_pct: 涨跌幅
            - 以及查询对应的指标字段
        """
        try:
            results = self._search_unified(query, top_n)
            return results
        except Exception as e:
            self.logger.warning("问财选股失败(query=%s): %s", query, e)
            return []

    def get_recent_limit_up(self, days: int = 3) -> List[Dict[str, Any]]:
        """获取近期连续涨停的股票"""
        results = self.stock_screening(f"连续{days}天涨停", top_n=30)
        return [r for r in results if r.get("code")]

    def get_volume_breakout(self, min_volume_ratio: float = 2.0) -> List[Dict[str, Any]]:
        """获取放量突破的股票"""
        results = self.stock_screening(
            f"量比大于{min_volume_ratio}且涨幅大于3%", top_n=30
        )
        return [r for r in results if r.get("code")]

    def get_strong_stocks(self) -> List[Dict[str, Any]]:
        """获取强势股（涨幅>5%且量比>1.5）"""
        results = self.stock_screening(
            "涨幅大于5%且量比大于1.5且换手率大于3%", top_n=30
        )
        return [r for r in results if r.get("code")]

    def get_hot_sector_stocks(self, sector_name: str) -> List[Dict[str, Any]]:
        """获取热点板块的股票"""
        results = self.stock_screening(
            f"{sector_name}板块且涨幅大于2%", top_n=20
        )
        return [r for r in results if r.get("code")]

    def get_momentum_stocks(
        self, min_change: float = 5.0, days: int = 5
    ) -> List[Dict[str, Any]]:
        """获取动量股（近期持续上涨）"""
        results = self.stock_screening(
            f"{days}日涨幅大于{min_change}%且今日涨幅大于0", top_n=25
        )
        return [r for r in results if r.get("code")]

    def get_market_sentiment_stocks(self) -> List[Dict[str, Any]]:
        """
        获取市场情绪相关指标

        适合与打板助手配合使用，判断市场热度
        """
        queries = [
            ("limit_up_count", "今日涨停家数"),
            ("limit_down_count", "今日跌停家数"),
            ("market_strong", "涨幅大于7%的股票数量"),
            ("market_weak", "跌幅大于7%的股票数量"),
        ]
        sentiment: Dict[str, Any] = {}
        for key, query in queries:
            try:
                results = self.stock_screening(query, top_n=300)
                sentiment[key] = len(results)
            except Exception:
                sentiment[key] = 0

        return sentiment

    # ========================
    #  内部方法
    # ========================

    def _search_unified(self, query: str, top_n: int) -> List[Dict[str, Any]]:
        """通过统一接口搜索"""
        params = {
            "query": query,
            "perpage": min(top_n, 50),
            "page": 1,
        }

        try:
            resp = self._session.get(
                _IWENCAI_UNIFIED_URL,
                params=params,
                timeout=self.REQUEST_TIMEOUT,
            )
            data = resp.json()
            return self._parse_response(data)
        except requests.Timeout:
            self.logger.warning("问财接口超时: %s", query)
            return []
        except Exception as e:
            self.logger.debug("问财接口异常: %s", e)
            return []

    def _parse_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析问财响应"""
        results: List[Dict[str, Any]] = []

        try:
            # 尝试多种响应格式
            answer = data.get("data", {}).get("answer", [])
            if not answer:
                answer = data.get("answer", [])

            if isinstance(answer, list):
                for item in answer:
                    if isinstance(item, str):
                        # 可能是 HTML 片段，提取股票代码
                        codes = re.findall(r'(\d{6})', item)
                        for code in codes:
                            results.append({"code": code, "name": ""})
                    elif isinstance(item, dict):
                        code = str(item.get("code", item.get("stock_code", "")))
                        name = str(item.get("name", item.get("stock_name", "")))
                        if code:
                            results.append({
                                "code": code,
                                "name": name,
                                **{k: v for k, v in item.items()
                                   if k not in ("code", "name", "stock_code", "stock_name")},
                            })

        except Exception as e:
            self.logger.debug("解析问财响应失败: %s", e)

        return results


def create_iwencai_fetcher() -> IwenCaiFetcher:
    """工厂方法：创建问财实例（读取配置中的 API Key）"""
    try:
        from src.config import get_config
        config = get_config()
        api_key = getattr(config, "iwencai_api_key", None) or None
    except Exception:
        api_key = None

    return IwenCaiFetcher(api_key=api_key)
