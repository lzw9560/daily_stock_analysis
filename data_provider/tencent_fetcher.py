# -*- coding: utf-8 -*-
"""
腾讯财经数据源 (Tencent Finance Fetcher)
========================================

优势:
- 公开免费、调用简单、响应快
- 零鉴权，HTTP 直接调用
- 支持 A股/港股 实时行情 + K线

短板:
- 无官方文档，接口可能变动
- 功能单一，无新闻/公告

适用场景:
- 临时拉取、轻量监控
- 作为其他数据源的实时行情补充
- 批量实时行情查询

API 说明:
- 实时行情: http://qt.gtimg.cn/q=sh600519,sz000001
- K线数据:   http://web.ifzq.gtimg.cn/appstock/app/fqkline/get
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import pandas as pd
import requests

from .base import (
    BaseFetcher, DataFetchError, STANDARD_COLUMNS,
    normalize_stock_code,
)
from .realtime_types import UnifiedRealtimeQuote

logger = logging.getLogger(__name__)

# 腾讯行情接口前缀映射
_TENCENT_PREFIX_MAP: Dict[str, str] = {
    "60": "sh",  # 上海主板
    "68": "sh",  # 科创板
    "00": "sz",  # 深圳主板
    "30": "sz",  # 创业板
    "15": "sz",  # 深圳 ETF
    "16": "sz",  # 深圳 LOF
    "51": "sh",  # 上海 ETF
    "58": "sh",  # 上海 ETF
    "56": "sh",  # 上海 ETF
    "52": "sh",  # 上海 ETF
}

# 腾讯行情字段索引（~ 分隔）
# 参考: https://blog.csdn.net/qq_38929220/article/details/79881855
_TENCENT_QUOTE_FIELDS = {
    "name": 1,         # 股票名称
    "code": 2,         # 股票代码
    "price": 3,        # 当前价格
    "pre_close": 4,    # 昨收价
    "open": 5,         # 今开
    "volume": 6,       # 成交量(手)
    "bid1_vol": 7,     # 买一量
    "bid1_price": 9,   # 买一价
    "ask1_vol": 19,    # 卖一量
    "ask1_price": 21,  # 卖一价
    "high": 33,        # 最高
    "low": 34,         # 最低
    "amount": 37,      # 成交额(万)
    "turnover_rate": 38,  # 换手率(%)
    "pe_ratio": 39,    # PE
    "high52": 40,      # 52周高
    "low52": 41,       # 52周低
    "amplitude": 43,   # 振幅(%)
    "circ_mv": 44,     # 流通市值(亿)
    "total_mv": 45,    # 总市值(亿)
    "pb_ratio": 46,    # PB
    "limit_up": 47,    # 涨停价
    "limit_down": 48,  # 跌停价
    "volume_ratio": 50,  # 量比
    "change_pct": 32,  # 涨跌幅(%)
}


def _get_tencent_code(stock_code: str) -> str:
    """将股票代码转为腾讯行情前缀格式，如 sh600519"""
    code = normalize_stock_code(stock_code)
    prefix = _TENCENT_PREFIX_MAP.get(code[:2], "sz")
    return f"{prefix}{code}"


def _tencent_codes_to_market_codes(codes: List[str]) -> str:
    """批量转为腾讯查询格式，逗号分隔"""
    return ",".join(_get_tencent_code(c) for c in codes)


def _parse_tencent_realtime_response(text: str) -> Dict[str, Dict[str, Any]]:
    """
    解析腾讯实时行情响应

    格式: v_sh600519="1~贵州茅台~600519~1850.00~..."
    返回: {code: {field: value}}
    """
    result: Dict[str, Dict[str, Any]] = {}
    # 匹配 v_xxx="..." 格式
    pattern = re.compile(r'v_(\w+)="([^"]*)"')
    for match in pattern.finditer(text):
        tencent_code = match.group(1)
        raw_data = match.group(2)
        fields = raw_data.split("~")

        # 提取纯代码
        code = re.sub(r'^(sh|sz)', '', tencent_code)
        if not code:
            continue

        parsed: Dict[str, Any] = {}
        for name, idx in _TENCENT_QUOTE_FIELDS.items():
            try:
                val = fields[idx] if idx < len(fields) else ""
                if name in ("name", "code"):
                    parsed[name] = val
                else:
                    parsed[name] = float(val) if val else 0.0
            except (ValueError, IndexError):
                parsed[name] = 0.0 if name not in ("name", "code") else ""

        result[code] = parsed

    return result


class TencentFetcher(BaseFetcher):
    """腾讯财经数据源"""

    name = "TencentFetcher"
    priority = 3  # 轻量补充源，优先级在主流数据源之后

    QUOTE_URL = "http://qt.gtimg.cn/q={codes}"
    KLINE_URL = (
        "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        "?param={code},day,{start},{end},{limit},qfq"
    )
    REQUEST_TIMEOUT = 10

    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
        })

    # ========================
    #  日线K线数据
    # ========================

    def _fetch_raw_data(
        self, stock_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """从腾讯财经获取日线K线"""
        tcode = _get_tencent_code(stock_code)
        url = self.KLINE_URL.format(
            code=tcode,
            start=start_date.replace("-", ""),
            end=end_date.replace("-", ""),
            limit=500,
        )

        try:
            resp = self._session.get(url, timeout=self.REQUEST_TIMEOUT)
            resp.encoding = "utf-8"
            data = resp.json()
        except Exception as e:
            raise DataFetchError(f"腾讯财经K线请求失败: {e}")

        # 解析K线数据
        stock_data = data.get("data", {}).get(tcode)
        if not stock_data:
            raise DataFetchError(f"腾讯财经未返回 {stock_code} 的K线数据")

        # qfqday 前复权, day 不复权
        kline_list = stock_data.get("qfqday") or stock_data.get("day") or []
        if not kline_list:
            raise DataFetchError(f"腾讯财经 {stock_code} K线为空")

        df = pd.DataFrame(kline_list)
        return df

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """标准化K线列名"""
        col_map = {
            "0": "date",
            "1": "open",
            "2": "close",
            "3": "high",
            "4": "low",
            "5": "volume",
        }

        normalized = pd.DataFrame()
        for raw_col, std_col in col_map.items():
            if raw_col in df.columns:
                normalized[std_col] = pd.to_numeric(df[raw_col], errors="coerce")

        # 计算涨跌幅
        if "close" in normalized.columns:
            normalized["pct_chg"] = normalized["close"].pct_change() * 100
            normalized["pct_chg"] = normalized["pct_chg"].round(2)
        else:
            normalized["pct_chg"] = 0.0

        # 成交额估算 = 成交量 * 收盘价 / 10000 (万)
        if "volume" in normalized.columns and "close" in normalized.columns:
            normalized["amount"] = (
                normalized["volume"] * normalized["close"] / 10000
            ).round(2)
        else:
            normalized["amount"] = 0.0

        # 成交量单位：手 → 保持原样
        return normalized[STANDARD_COLUMNS]

    # ========================
    #  实时行情
    # ========================

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """获取单只股票实时行情"""
        try:
            tcode = _get_tencent_code(stock_code)
            url = self.QUOTE_URL.format(codes=tcode)
            resp = self._session.get(url, timeout=self.REQUEST_TIMEOUT)
            resp.encoding = "gbk"
            parsed = _parse_tencent_realtime_response(resp.text)
            raw = parsed.get(normalize_stock_code(stock_code))
            if not raw:
                return None
            return self._build_quote(raw)
        except Exception as e:
            logger.debug(f"[Tencent] 实时行情获取失败 {stock_code}: {e}")
            return None

    def get_batch_realtime_quotes(
        self, stock_codes: List[str]
    ) -> Dict[str, UnifiedRealtimeQuote]:
        """批量获取实时行情（腾讯支持一次查询最多约 50-80 只）"""
        result: Dict[str, UnifiedRealtimeQuote] = {}
        batch_size = 50  # 分批查询避免 URL 过长

        for i in range(0, len(stock_codes), batch_size):
            batch = stock_codes[i : i + batch_size]
            try:
                tcodes = _tencent_codes_to_market_codes(batch)
                url = self.QUOTE_URL.format(codes=tcodes)
                resp = self._session.get(url, timeout=self.REQUEST_TIMEOUT)
                resp.encoding = "gbk"
                parsed = _parse_tencent_realtime_response(resp.text)

                for code, raw in parsed.items():
                    quote = self._build_quote(raw)
                    if quote:
                        result[code] = quote

                self.random_sleep(0.3, 0.8)
            except Exception as e:
                logger.warning(f"[Tencent] 批量行情获取失败 batch={i}: {e}")
                continue

        return result

    def _build_quote(self, raw: Dict[str, Any]) -> Optional[UnifiedRealtimeQuote]:
        """构建统一实时行情对象"""
        try:
            price = raw.get("price", 0)
            if not price or price <= 0:
                return None

            return UnifiedRealtimeQuote(
                code=raw.get("code", ""),
                name=raw.get("name", ""),
                price=price,
                change_pct=raw.get("change_pct", 0),
                change_amount=price - raw.get("pre_close", price),
                open_price=raw.get("open", 0),
                high=raw.get("high", 0),
                low=raw.get("low", 0),
                pre_close=raw.get("pre_close", 0),
                volume=raw.get("volume", 0),
                amount=raw.get("amount", 0),
                volume_ratio=raw.get("volume_ratio", None),
                turnover_rate=raw.get("turnover_rate", None),
                amplitude=raw.get("amplitude", None),
                pe_ratio=raw.get("pe_ratio", None),
                pb_ratio=raw.get("pb_ratio", None),
                total_mv=raw.get("total_mv", None),
                circ_mv=raw.get("circ_mv", None),
            )
        except Exception as e:
            logger.debug(f"[Tencent] 构建行情对象失败: {e}")
            return None

    # ========================
    #  市场统计
    # ========================

    def get_market_stats(self) -> Optional[Dict[str, Any]]:
        """获取市场涨跌统计"""
        return None  # 腾讯接口不直接提供此服务

    def get_main_indices(self, region: str = "cn") -> Optional[List[Dict[str, Any]]]:
        """获取主要指数行情"""
        if region != "cn":
            return None

        index_map = {
            "sh000001": "上证指数",
            "sz399001": "深证成指",
            "sz399006": "创业板指",
            "sh000688": "科创50",
        }

        codes = list(index_map.keys())
        try:
            tcodes = ",".join(codes)
            url = self.QUOTE_URL.format(codes=tcodes)
            resp = self._session.get(url, timeout=self.REQUEST_TIMEOUT)
            resp.encoding = "gbk"
            parsed = _parse_tencent_realtime_response(resp.text)

            indices: List[Dict[str, Any]] = []
            for tcode, raw in parsed.items():
                price = raw.get("price", 0)
                pre_close = raw.get("pre_close", 0)
                change_pct = raw.get("change_pct", 0)
                name = index_map.get(tcode, raw.get("name", tcode))
                indices.append({
                    "code": tcode,
                    "name": name,
                    "current": price,
                    "change": round(price - pre_close, 2),
                    "change_pct": change_pct,
                    "volume": raw.get("volume", 0),
                    "amount": raw.get("amount", 0),
                })

            return indices
        except Exception as e:
            logger.warning(f"[Tencent] 指数行情获取失败: {e}")
            return None

    def get_stock_name(self, stock_code: str) -> Optional[str]:
        """获取股票名称"""
        quote = self.get_realtime_quote(stock_code)
        if quote and quote.name:
            return quote.name
        return None
