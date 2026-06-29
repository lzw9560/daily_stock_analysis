# -*- coding: utf-8 -*-
"""
===================================
数据源策略层 - 包初始化 (Lazy)
===================================

本包实现策略模式管理多个数据源，实现：
1. 统一的数据获取接口
2. 自动故障切换
3. 防封禁流控策略

数据源优先级（动态调整）：
【配置了 TUSHARE_TOKEN 时】
1. TushareFetcher (Priority 0) - 🎯 最高优先级（动态提升）
2. EfinanceFetcher (Priority 0) - 同优先级
3. AkshareFetcher (Priority 1) - 来自 akshare 库
4. SinaFetcher (Priority 2) - 新浪财经直连（批量高效）
5. PytdxFetcher (Priority 2) - 来自 pytdx 库（通达信）
6. BaostockFetcher (Priority 3) - 来自 baostock 库
7. TencentFetcher (Priority 3) - 腾讯财经（实时行情补充）
8. YfinanceFetcher (Priority 4) - 来自 yfinance 库

【未配置 TUSHARE_TOKEN 时】
1. EfinanceFetcher (Priority 0) - 最高优先级，来自 efinance 库
2. AkshareFetcher (Priority 1) - 来自 akshare 库
3. SinaFetcher (Priority 2) - 新浪财经直连（批量高效）
4. PytdxFetcher (Priority 2) - 来自 pytdx 库（通达信）
5. TushareFetcher (Priority 2) - 来自 tushare 库（不可用）
6. BaostockFetcher (Priority 3) - 来自 baostock 库
7. TencentFetcher (Priority 3) - 腾讯财经（实时行情补充）
8. YfinanceFetcher (Priority 4) - 来自 yfinance 库
9. LongbridgeFetcher (Priority 5) - 长桥 OpenAPI（美股/港股兜底）

独立数据源（不参与K线故障切换链）:
- IwenCaiFetcher: 问财自然语言选股
- THSHotspotFetcher: 同花顺热点概念

提示：优先级数字越小越优先，同优先级按初始化顺序排列

Imports are lazy — fetcher modules are imported on first attribute access
to keep startup import of the ``data_provider`` package fast.
"""

import importlib

from .base import BaseFetcher, DataFetcherManager

_FETCHER_MODULES = {
    "EfinanceFetcher": ".efinance_fetcher",
    "AkshareFetcher": ".akshare_fetcher",
    "TushareFetcher": ".tushare_fetcher",
    "PytdxFetcher": ".pytdx_fetcher",
    "BaostockFetcher": ".baostock_fetcher",
    "SinaFetcher": ".sina_fetcher",
    "TencentFetcher": ".tencent_fetcher",
    "YfinanceFetcher": ".yfinance_fetcher",
    "LongbridgeFetcher": ".longbridge_fetcher",
    "FinnhubFetcher": ".finnhub_fetcher",
    "AlphaVantageFetcher": ".alphavantage_fetcher",
    "IwenCaiFetcher": ".iwencai_fetcher",
    "create_iwencai_fetcher": ".iwencai_fetcher",
    "THSHotspotFetcher": ".ths_hotspot_fetcher",
    "create_ths_hotspot_fetcher": ".ths_hotspot_fetcher",
}

_FUNCTION_MODULES = {
    "is_us_index_code": ".us_index_mapping",
    "is_us_stock_code": ".us_index_mapping",
    "is_hk_stock_code": ".akshare_fetcher",
    "get_us_index_yf_symbol": ".us_index_mapping",
    "US_INDEX_MAPPING": ".us_index_mapping",
    "fetch_sina_realtime_batch": ".sina_fetcher",
    "fetch_sina_indices": ".sina_fetcher",
    "SinaQuoteRaw": ".sina_fetcher",
    "SinaIndexData": ".sina_fetcher",
}

def __getattr__(name: str):
    return _lazy_import(name)


def __dir__():
    return sorted(__all__)


def _lazy_import(name: str):
    module_name = _FETCHER_MODULES.get(name) or _FUNCTION_MODULES.get(name)
    if module_name:
        module = importlib.import_module(module_name, __package__)
        attr = getattr(module, name)
        globals()[name] = attr
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'BaseFetcher',
    'DataFetcherManager',
    'EfinanceFetcher',
    'AkshareFetcher',
    'TushareFetcher',
    'PytdxFetcher',
    'BaostockFetcher',
    'SinaFetcher',
    'TencentFetcher',
    'YfinanceFetcher',
    'LongbridgeFetcher',
    'FinnhubFetcher',
    'AlphaVantageFetcher',
    'IwenCaiFetcher',
    'create_iwencai_fetcher',
    'THSHotspotFetcher',
    'create_ths_hotspot_fetcher',
    'fetch_sina_realtime_batch',
    'fetch_sina_indices',
    'SinaQuoteRaw',
    'SinaIndexData',
    'is_us_index_code',
    'is_us_stock_code',
    'is_hk_stock_code',
    'get_us_index_yf_symbol',
    'US_INDEX_MAPPING',
]
