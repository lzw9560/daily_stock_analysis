# -*- coding: utf-8 -*-
"""
========================================
新浪财经实时行情数据源 (Sina Finance Fetcher)
========================================

数据来源：新浪财经实时行情接口 (hq.sinajs.cn)

特性：
- 完全免费，零鉴权，HTTP GET 直连
- 支持 A股（沪深北）/港股/ETF 实时行情
- 支持批量查询（单次最多约 400 只）
- 支持主要指数（上证、深证、创业板、科创50 等）
- 支持涨跌统计（上涨/下跌/平盘/涨停/跌停家数）

短板：
- 无官方文档，字段通过社区反推
- 仅实时盘中数据，无历史日线（需用其他源）
- 偶尔返回空数据，需结合重试 + 熔断

适用场景：
- 盘中实时行情监控
- 批量个股快照
- 指数研判、涨跌统计
- 作为其他数据源的实时补充

字段说明（新浪行情接口）：
  0: name         股票名称
  1: open         今开盘
  2: pre_close    昨收盘
  3: price        当前价
  4: high         最高价
  5: low          最低价
  6: bid1         竞买价(买一)
  7: ask1         竞卖价(卖一)
  8: volume       成交股数（股）
  9: amount       成交金额（元）
 10: bid1_vol     买一量
 11: bid1_price   买一价
 12: bid2_vol     买二量
 13: bid2_price   买二价
 14: bid3_vol     买三量
 15: bid3_price   买三价
 16: bid4_vol     买四量
 17: bid4_price   买四价
 18: bid5_vol     买五量
 19: bid5_price   买五价
 20: ask1_vol     卖一量
 21: ask1_price   卖一价
 22: ask2_vol     卖二量
 23: ask2_price   卖二价
 24: ask3_vol     卖三量
 25: ask3_price   卖三价
 26: ask4_vol     卖四量
 27: ask4_price   卖四价
 28: ask5_vol     卖五量
 29: ask5_price   卖五价
 30: date         日期
 31: time         时间
 32: status       状态(00=正常,01=停牌)
"""

from __future__ import annotations

import logging
import re
import time
import random
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple
from collections import OrderedDict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import (
    BaseFetcher, DataFetchError, RateLimitError,
    normalize_stock_code,
)
from .realtime_types import (
    UnifiedRealtimeQuote, RealtimeSource,
    get_realtime_circuit_breaker,
    safe_float, safe_int,
)

logger = logging.getLogger(__name__)

# ============================================================
# 常量定义
# ============================================================

# 新浪行情接口
_SINA_REALTIME_URL = "http://hq.sinajs.cn/list={codes}"

# 新浪涨跌统计接口（东方财富格式，新浪也支持）
_SINA_EM_MARKET_URL = (
    "http://push2.eastmoney.com/api/qt/clist/get"
    "?fid=f3&po=1&pz={pz}&pn={pn}&np=1&fltt=2&invt=2"
    "&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
    "&fields=f2,f3,f12"
)

# 新浪对大指数也使用 hq.sinajs.cn
_SINA_INDEX_URL = "http://hq.sinajs.cn/list={codes}"

# 请求配置
_REQUEST_TIMEOUT = 10          # 单次请求超时（秒）
_BATCH_SIZE = 80               # 单次批量查询上限
_RETRY_TOTAL = 3               # 最大重试次数
_RETRY_BACKOFF_FACTOR = 0.5    # 重试退避因子
_MIN_DELAY_BETWEEN_CALLS = 0.1  # 最小请求间隔（秒）

# 新浪代码前缀映射
_SINA_MARKET_PREFIX: Dict[str, str] = {
    "60": "sh",   # 沪市主板
    "68": "sh",   # 科创板
    "51": "sh",   # 沪市 ETF
    "56": "sh",   # 沪市 ETF
    "58": "sh",   # 沪市 ETF
    "90": "sh",   # 沪市 B 股
    "00": "sz",   # 深市主板
    "30": "sz",   # 创业板
    "15": "sz",   # 深市 ETF
    "16": "sz",   # 深市 LOF
    "20": "sz",   # 深市 B 股
    "40": "bj",   # 北交所
    "43": "bj",   # 北交所
    "83": "bj",   # 北交所
    "87": "bj",   # 北交所
    "88": "bj",   # 北交所
    "92": "bj",   # 北交所(新版)
}

# 主要指数代码映射
_INDEX_CODES: Dict[str, str] = OrderedDict({
    "sh000001":  "上证指数",
    "sh000688":  "科创50",
    "sz399001":  "深证成指",
    "sz399006":  "创业板指",
    "sz399005":  "中小100",
    "sh000016":  "上证50",
    "sh000300":  "沪深300",
    "sh000905":  "中证500",
    "sz399303":  "国证2000",
    "sh000852":  "中证1000",
})

# 港股前缀
_HK_PREFIX = "rt_hk"


# ============================================================
# 异常定义
# ============================================================

class SinaFetchError(DataFetchError):
    """新浪数据获取异常"""
    pass


class SinaParseError(DataFetchError):
    """新浪数据解析异常"""
    pass


# ============================================================
# 数据结构定义
# ============================================================

@dataclass
class SinaQuoteRaw:
    """
    新浪实时行情原始解析结果

    包含新浪接口返回的全部可解析字段，供下游模块灵活使用。
    字段顺序与 _SINA_FIELD_MAP 定义一致。
    """
    code: str                          # 股票代码
    name: str = ""                     # 股票名称
    open_price: float = 0.0            # 今开盘
    pre_close: float = 0.0             # 昨收盘
    price: float = 0.0                 # 当前价
    high: float = 0.0                  # 最高价
    low: float = 0.0                   # 最低价
    bid1: float = 0.0                  # 买一价
    ask1: float = 0.0                  # 卖一价
    volume: int = 0                    # 成交量（股）
    amount: float = 0.0                # 成交金额（元）
    bid_volumes: List[int] = field(default_factory=list)    # 买1-5量
    bid_prices: List[float] = field(default_factory=list)    # 买1-5价
    ask_volumes: List[int] = field(default_factory=list)     # 卖1-5量
    ask_prices: List[float] = field(default_factory=list)    # 卖1-5价
    trade_date: str = ""               # 交易日期 YYYY-MM-DD
    trade_time: str = ""               # 交易时间 HH:MM:SS
    status: str = ""                   # 状态码(00=正常,01=停牌)

    def to_dict(self) -> Dict[str, Any]:
        """转为普通字典"""
        return asdict(self)

    def is_suspended(self) -> bool:
        """是否停牌"""
        return self.status == "01" or self.price <= 0

    def is_valid(self) -> bool:
        """数据是否有效"""
        return bool(self.code) and self.price > 0 and self.name != ""


@dataclass
class SinaIndexData:
    """
    新浪指数行情数据
    """
    code: str                          # 指数代码
    name: str = ""                     # 指数名称
    price: float = 0.0                 # 当前点位
    change: float = 0.0                # 涨跌点位
    change_pct: float = 0.0            # 涨跌幅(%)
    volume: int = 0                    # 成交量
    amount: float = 0.0                # 成交金额

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# 工具函数
# ============================================================

def _to_sina_symbol(stock_code: str) -> str:
    """将股票代码转换为新浪行情符号，如 sh600519, sz000001"""
    code = normalize_stock_code(stock_code)
    prefix = _SINA_MARKET_PREFIX.get(code[:2], "sz")
    return f"{prefix}{code}"


def _to_sina_hk_symbol(stock_code: str) -> str:
    """将港股代码转换为新浪行情符号"""
    code = stock_code.strip().upper()
    if code.startswith("HK"):
        code = code[2:]
    code = code.zfill(5)
    return f"{_HK_PREFIX}{code}"


def _batch_to_sina_symbols(stock_codes: List[str]) -> str:
    """批量转换为逗号分隔的新浪符号"""
    return ",".join(_to_sina_symbol(c) for c in stock_codes)


def _parse_sina_single(symbol: str, raw_text: str) -> Optional[SinaQuoteRaw]:
    """
    解析单条新浪实时行情

    输入格式：
      var hq_str_sh600519="贵州茅台,1850.00,1840.00,1845.50,...";

    返回：
      SinaQuoteRaw 或 None（解析失败时）
    """
    try:
        # 分割字段
        fields = raw_text.split(",")
        if len(fields) < 33:
            logger.debug(f"[Sina] 字段不足 {len(fields)} < 33: {symbol}")
            return None

        code = re.sub(r'^(sh|sz|bj)', '', symbol, flags=re.IGNORECASE)

        # 构建盘口五档
        bid_volumes = []
        bid_prices = []
        ask_volumes = []
        ask_prices = []

        for i in range(5):
            bid_volumes.append(safe_int(fields[10 + i * 2], 0))
            bid_prices.append(safe_float(fields[11 + i * 2], 0.0))
            ask_volumes.append(safe_int(fields[20 + i * 2], 0))
            ask_prices.append(safe_float(fields[21 + i * 2], 0.0))

        return SinaQuoteRaw(
            code=code,
            name=fields[0].strip(),
            open_price=safe_float(fields[1], 0.0),
            pre_close=safe_float(fields[2], 0.0),
            price=safe_float(fields[3], 0.0),
            high=safe_float(fields[4], 0.0),
            low=safe_float(fields[5], 0.0),
            bid1=safe_float(fields[6], 0.0),
            ask1=safe_float(fields[7], 0.0),
            volume=safe_int(fields[8], 0),
            amount=safe_float(fields[9], 0.0),
            bid_volumes=bid_volumes,
            bid_prices=bid_prices,
            ask_volumes=ask_volumes,
            ask_prices=ask_prices,
            trade_date=fields[30].strip() if len(fields) > 30 else "",
            trade_time=fields[31].strip() if len(fields) > 31 else "",
            status=fields[32].strip() if len(fields) > 32 else "",
        )
    except Exception as e:
        logger.debug(f"[Sina] 解析异常 {symbol}: {e}")
        return None


def _parse_sina_batch(response_text: str) -> Dict[str, SinaQuoteRaw]:
    """
    解析新浪批量行情响应

    输入示例：
      var hq_str_sh600519="贵州茅台,1850.00,...";
      var hq_str_sz000001="平安银行,12.50,...";

    返回：
      {code: SinaQuoteRaw}
    """
    result: Dict[str, SinaQuoteRaw] = {}

    # 匹配 var hq_str_XXX="...";
    pattern = re.compile(r'var hq_str_(\w+)="([^"]*)"')
    for match in pattern.finditer(response_text):
        symbol = match.group(1)
        raw_data = match.group(2)
        parsed = _parse_sina_single(symbol, raw_data)
        if parsed and parsed.is_valid():
            result[parsed.code] = parsed

    return result


def _parse_sina_index_batch(response_text: str) -> Dict[str, SinaIndexData]:
    """解析新浪指数行情响应"""
    result: Dict[str, SinaIndexData] = {}

    pattern = re.compile(r'var hq_str_(\w+)="([^"]*)"')
    for match in pattern.finditer(response_text):
        symbol = match.group(1)
        raw_data = match.group(2)
        fields = raw_data.split(",")

        if len(fields) < 5:
            continue

        try:
            price = safe_float(fields[3], 0.0)
            pre_close = safe_float(fields[2], 0.0)
            change = round(price - pre_close, 2) if pre_close > 0 else 0.0
            change_pct = round(change / pre_close * 100, 2) if pre_close > 0 else 0.0

            name = _INDEX_CODES.get(symbol, fields[0].strip())
            result[symbol] = SinaIndexData(
                code=symbol,
                name=name,
                price=price,
                change=change,
                change_pct=change_pct,
                volume=safe_int(fields[8], 0),
                amount=safe_float(fields[9], 0.0),
            )
        except Exception:
            continue

    return result


# ============================================================
# 新浪直连 Fetcher
# ============================================================

class SinaFetcher(BaseFetcher):
    """
    新浪财经实时行情数据源

    提供：
    - get_realtime_quote(code)          单只个股实时行情
    - get_batch_realtime_quotes(codes)  批量个股实时行情
    - get_main_indices()                主要指数行情
    - get_market_stats()                全市场涨跌统计（通过东方财富）
    - get_limit_up_pool()               涨停池（通过东方财富）
    - get_stock_name(code)              股票名称查询
    """

    name = "SinaFetcher"
    priority = 2  # 略低于 efinance/akshare，但高于 tencent

    def __init__(self):
        super().__init__()
        self._session = self._build_session()
        self._last_call_time: float = 0.0

    def _build_session(self) -> requests.Session:
        """构建带重试的 Requests Session"""
        session = requests.Session()

        # 重试适配器
        retry_strategy = Retry(
            total=_RETRY_TOTAL,
            backoff_factor=_RETRY_BACKOFF_FACTOR,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20,
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # 请求头
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Referer": "https://finance.sina.com.cn/",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        return session

    def _rate_limit(self):
        """请求限频：确保两次请求间隔 >= self._min_delay"""
        elapsed = time.time() - self._last_call_time
        if elapsed < _MIN_DELAY_BETWEEN_CALLS:
            time.sleep(_MIN_DELAY_BETWEEN_CALLS - elapsed)
        self._last_call_time = time.time()

    def random_sleep(self, min_s: float = 0.1, max_s: float = 0.5):
        """随机休眠，降低频率特征"""
        time.sleep(random.uniform(min_s, max_s))

    # ============================
    #  日线数据（新浪不直接支持，返回空/委托给其他源）
    # ============================

    def _fetch_raw_data(
        self, stock_code: str, start_date: str, end_date: str
    ) -> "pd.DataFrame":
        """新浪接口不提供历史日线，此方法由 DataFetcherManager 的故障切换链自动跳过"""
        raise DataFetchError("[Sina] 不支持历史日线数据，请使用其他数据源")

    def _normalize_data(self, df: "pd.DataFrame", stock_code: str) -> "pd.DataFrame":
        raise NotImplementedError

    # ============================
    #  实时行情
    # ============================

    def _fetch_realtime_raw(self, codes: List[str]) -> str:
        """
        发送批量行情请求，返回原始响应文本

        Args:
            codes: 新浪格式符号列表，如 ['sh600519', 'sz000001']

        Returns:
            原始响应文本

        Raises:
            SinaFetchError: 网络请求失败时
        """
        self._rate_limit()

        symbols = ",".join(codes)
        url = _SINA_REALTIME_URL.format(codes=symbols)

        try:
            resp = self._session.get(url, timeout=_REQUEST_TIMEOUT)
            resp.encoding = "gbk"
            if resp.status_code != 200:
                raise SinaFetchError(
                    f"新浪行情请求失败 HTTP {resp.status_code}: {symbols[:50]}..."
                )

            text = resp.text
            if not text or len(text) < 20:
                raise SinaFetchError(f"新浪行情返回空数据: {symbols[:50]}...")

            return text
        except requests.exceptions.Timeout:
            raise SinaFetchError(f"新浪行情请求超时 ({_REQUEST_TIMEOUT}s): {symbols[:50]}...")
        except requests.exceptions.ConnectionError as e:
            raise SinaFetchError(f"新浪行情连接失败: {e}")
        except requests.exceptions.RequestException as e:
            raise SinaFetchError(f"新浪行情请求异常: {e}")

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        获取单只股票实时行情

        Args:
            stock_code: 股票代码，如 '600519', '000001'

        Returns:
            UnifiedRealtimeQuote 或 None
        """
        breaker = get_realtime_circuit_breaker()
        if not breaker.is_available("sina"):
            logger.debug("[Sina] 熔断器阻止请求")
            return None

        try:
            symbol = _to_sina_symbol(stock_code)
            text = self._fetch_realtime_raw([symbol])
            parsed = _parse_sina_batch(text)
            raw = parsed.get(normalize_stock_code(stock_code))

            if raw is None:
                breaker.record_inconclusive("sina")
                return None

            breaker.record_success("sina")
            return _sina_raw_to_unified(raw)

        except SinaFetchError as e:
            breaker.record_failure("sina", str(e))
            logger.warning(f"[Sina] 实时行情失败 {stock_code}: {e}")
            return None
        except Exception as e:
            breaker.record_failure("sina", str(e))
            logger.warning(f"[Sina] 实时行情异常 {stock_code}: {e}")
            return None

    def get_batch_realtime_quotes(
        self, stock_codes: List[str]
    ) -> Dict[str, UnifiedRealtimeQuote]:
        """
        批量获取实时行情

        分批请求（每批 _BATCH_SIZE 只），自动合并结果。

        Args:
            stock_codes: 股票代码列表

        Returns:
            {code: UnifiedRealtimeQuote}
        """
        result: Dict[str, UnifiedRealtimeQuote] = {}
        breaker = get_realtime_circuit_breaker()

        if not breaker.is_available("sina"):
            return result

        for i in range(0, len(stock_codes), _BATCH_SIZE):
            batch = stock_codes[i: i + _BATCH_SIZE]
            try:
                symbols = [_to_sina_symbol(c) for c in batch]
                text = self._fetch_realtime_raw(symbols)
                parsed = _parse_sina_batch(text)

                for code, raw in parsed.items():
                    quote = _sina_raw_to_unified(raw)
                    if quote:
                        result[code] = quote

                breaker.record_success("sina")
                self.random_sleep(0.05, 0.2)

            except SinaFetchError as e:
                breaker.record_failure("sina", str(e))
                logger.warning(f"[Sina] 批量行情第 {i} 批失败: {e}")
                continue
            except Exception as e:
                breaker.record_failure("sina", str(e))
                logger.warning(f"[Sina] 批量行情第 {i} 批异常: {e}")
                continue

        return result

    # ============================
    #  指数行情
    # ============================

    def get_main_indices(self, region: str = "cn") -> Optional[List[Dict[str, Any]]]:
        """
        获取主要指数实时行情

        Args:
            region: 市场区域，'cn'=A股

        Returns:
            指数列表，每项含 code, name, current, change, change_pct
        """
        if region != "cn":
            return None

        try:
            index_symbols = list(_INDEX_CODES.keys())
            self._rate_limit()

            url = _SINA_INDEX_URL.format(codes=",".join(index_symbols))
            resp = self._session.get(url, timeout=_REQUEST_TIMEOUT)
            resp.encoding = "gbk"

            if resp.status_code != 200:
                logger.warning(f"[Sina] 指数行情请求失败 HTTP {resp.status_code}")
                return None

            parsed = _parse_sina_index_batch(resp.text)
            if not parsed:
                return None

            # 按 _INDEX_CODES 顺序输出
            indices: List[Dict[str, Any]] = []
            for code, name in _INDEX_CODES.items():
                idx = parsed.get(code)
                if idx:
                    indices.append({
                        "code": code,
                        "name": name,
                        "current": idx.price,
                        "change": idx.change,
                        "change_pct": idx.change_pct,
                        "volume": idx.volume,
                        "amount": idx.amount,
                    })

            return indices if indices else None

        except Exception as e:
            logger.warning(f"[Sina] 指数行情获取失败: {e}")
            return None

    # ============================
    #  股票名称查询
    # ============================

    def get_stock_name(self, stock_code: str) -> Optional[str]:
        """通过实时行情获取股票名称"""
        quote = self.get_realtime_quote(stock_code)
        if quote and quote.name:
            return quote.name
        return None

    # ============================
    #  港股行情
    # ============================

    def get_hk_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        """
        获取港股实时行情（通过新浪港股接口）

        Args:
            stock_code: 港股代码，如 'HK00700' 或 '00700'

        Returns:
            UnifiedRealtimeQuote 或 None
        """
        try:
            symbol = _to_sina_hk_symbol(stock_code)
            self._rate_limit()

            url = _SINA_REALTIME_URL.format(codes=symbol)
            resp = self._session.get(url, timeout=_REQUEST_TIMEOUT)
            resp.encoding = "gbk"

            if resp.status_code != 200:
                return None

            # 港股返回格式略有不同：var hq_str_rt_hk00700="..."
            parsed = _parse_sina_batch(resp.text)
            # 港股代码处理
            pure_code = stock_code.strip().upper().replace("HK", "").zfill(5)
            raw = parsed.get(pure_code)

            if raw and raw.is_valid():
                return _sina_raw_to_unified(raw, source=RealtimeSource.SINA)

            return None
        except Exception as e:
            logger.debug(f"[Sina] 港股行情失败 {stock_code}: {e}")
            return None


# ============================================================
# 转换函数：SinaQuoteRaw → UnifiedRealtimeQuote
# ============================================================

def _sina_raw_to_unified(
    raw: SinaQuoteRaw,
    source: RealtimeSource = RealtimeSource.SINA,
) -> Optional[UnifiedRealtimeQuote]:
    """将 SinaQuoteRaw 转换为统一行情结构"""
    try:
        if not raw.is_valid():
            return None

        price = raw.price
        pre_close = raw.pre_close

        # 计算涨跌幅
        if pre_close > 0:
            change_pct = round((price - pre_close) / pre_close * 100, 2)
            change_amount = round(price - pre_close, 2)
        else:
            change_pct = 0.0
            change_amount = 0.0

        # 计算振幅
        if pre_close > 0 and raw.high > 0 and raw.low > 0:
            amplitude = round((raw.high - raw.low) / pre_close * 100, 2)
        else:
            amplitude = None

        return UnifiedRealtimeQuote(
            code=raw.code,
            name=raw.name,
            source=source,
            price=price,
            change_pct=change_pct,
            change_amount=change_amount,
            volume=raw.volume,
            amount=raw.amount,
            open_price=raw.open_price or None,
            high=raw.high or None,
            low=raw.low or None,
            pre_close=pre_close or None,
            amplitude=amplitude,
        )
    except Exception as e:
        logger.debug(f"[Sina] 转换 UnifiedRealtimeQuote 失败: {e}")
        return None


# ============================================================
# 独立工具函数（可直接导入使用，无需实例化 Fetcher）
# ============================================================

def fetch_sina_realtime_batch(
    codes: List[str],
    timeout: int = _REQUEST_TIMEOUT,
) -> Dict[str, UnifiedRealtimeQuote]:
    """
    独立批量获取新浪实时行情（无状态，不需要 Fetcher 实例）

    适合临时调用/脚本场景，不依赖熔断器。

    Args:
        codes: 股票代码列表
        timeout: 请求超时秒数

    Returns:
        {code: UnifiedRealtimeQuote}

    Example:
        >>> quotes = fetch_sina_realtime_batch(["600519", "000001"])
        >>> for code, q in quotes.items():
        ...     print(f"{code} {q.name}: {q.price} ({q.change_pct:+.2f}%)")
    """
    result: Dict[str, UnifiedRealtimeQuote] = {}
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/126.0.0.0"
        ),
        "Referer": "https://finance.sina.com.cn/",
    })

    for i in range(0, len(codes), _BATCH_SIZE):
        batch = codes[i : i + _BATCH_SIZE]
        symbols = ",".join(_to_sina_symbol(c) for c in batch)

        try:
            url = _SINA_REALTIME_URL.format(codes=symbols)
            resp = session.get(url, timeout=timeout)
            resp.encoding = "gbk"

            if resp.status_code != 200:
                continue

            parsed = _parse_sina_batch(resp.text)
            for code, raw in parsed.items():
                quote = _sina_raw_to_unified(raw)
                if quote:
                    result[code] = quote

            time.sleep(_MIN_DELAY_BETWEEN_CALLS)

        except Exception as e:
            logger.warning(f"fetch_sina_realtime_batch 第{i}批失败: {e}")
            continue

    session.close()
    return result


def fetch_sina_indices() -> Dict[str, SinaIndexData]:
    """
    独立获取主要指数行情

    Returns:
        {code: SinaIndexData}

    Example:
        >>> indices = fetch_sina_indices()
        >>> sh = indices.get("sh000001")
        >>> if sh:
        ...     print(f"上证指数: {sh.price} ({sh.change_pct:+.2f}%)")
    """
    try:
        symbols = ",".join(_INDEX_CODES.keys())
        url = _SINA_INDEX_URL.format(codes=symbols)

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 Chrome/126.0.0.0",
            "Referer": "https://finance.sina.com.cn/",
        })
        resp = session.get(url, timeout=_REQUEST_TIMEOUT)
        resp.encoding = "gbk"
        session.close()

        if resp.status_code != 200:
            return {}

        return _parse_sina_index_batch(resp.text)
    except Exception as e:
        logger.warning(f"fetch_sina_indices 失败: {e}")
        return {}
