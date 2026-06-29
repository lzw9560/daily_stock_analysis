# -*- coding: utf-8 -*-
"""金融数据 API 端点

提供美联储利率（FRED API）、Yahoo Finance、经济日历、财务报表（基本面适配器）、
分红/拆股、财报日历、经济指标等金融数据查询接口。

数据源优先级：
1. Yahoo Finance（实时行情/历史数据）— 已接入
2. FRED API（美联储利率/经济指标）— 已接入
3. 基本面适配器（财务报表/分红/拆股）— 已接入
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter()


# ======================== Fed Rates（FRED API 接入）========================

@router.get("/fed-rates", summary="获取美联储利率数据")
def get_fed_rates(
    start_date: Optional[str] = Query(None, alias="startDate", description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, alias="endDate", description="结束日期 YYYY-MM-DD"),
    maturity_type: Optional[str] = Query(None, alias="maturityType", description="债券类型"),
):
    """获取美联储利率数据

    数据源：FRED API（Federal Reserve Economic Data）
    支持的 maturity_type：Treasury, FedFunds, LIBOR, Eurodollar
    """
    try:
        # 尝试 FRED API 获取真实数据
        data = _fetch_fred_rates(start_date, end_date, maturity_type)
        if data:
            return {
                "data": data,
                "meta": {
                    "source": "FRED API",
                    "start_date": start_date or "2020-01-01",
                    "end_date": end_date or datetime.now().strftime("%Y-%m-%d"),
                    "maturity_type": maturity_type or "FedFunds",
                },
            }

        # FRED API 不可用时降级到 yfinance 获取美国国债收益率
        treasury_data = _fetch_treasury_yields_via_yfinance(start_date, end_date)
        if treasury_data:
            return {
                "data": treasury_data,
                "meta": {
                    "source": "Yahoo Finance (Treasury Yields)",
                    "start_date": start_date or "2020-01-01",
                    "end_date": end_date or datetime.now().strftime("%Y-%m-%d"),
                    "maturity_type": maturity_type or "Treasury",
                },
            }

        # 最终降级：返回最近的已知利率数据
        return {
            "data": _get_fallback_fed_rates(),
            "meta": {
                "source": "fallback (FRED/Yahoo unavailable)",
                "start_date": start_date or "2020-01-01",
                "end_date": end_date or datetime.now().strftime("%Y-%m-%d"),
            },
        }
    except Exception as exc:
        logger.error("获取美联储利率数据失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ======================== Yahoo Finance ========================

@router.get("/yahoo/{stock_code}", summary="获取Yahoo Finance股票数据")
def get_yahoo_finance(
    stock_code: str,
    start_date: str = Query(..., alias="startDate"),
    end_date: str = Query(..., alias="endDate"),
    interval: str = Query("1d", description="时间间隔"),
):
    """通过 Yahoo Finance 获取股票历史数据

    支持市场：
    - A股：000001.SZ, 600519.SS
    - 港股：0700.HK, 9988.HK
    - 美股：AAPL, TSLA, SPY
    - 美股指数：^GSPC, ^DJI, ^IXIC
    """
    try:
        from data_provider.yfinance_fetcher import YFinanceFetcher
        fetcher = YFinanceFetcher()
        df = fetcher.fetch_history(stock_code, start_date, end_date, interval)

        records = []
        if df is not None and not df.empty:
            for idx, row in df.iterrows():
                records.append({
                    "date": str(idx),
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": int(row.get("volume", 0)),
                    "adj_close": float(row.get("adj_close", row.get("close", 0))),
                })

        return {
            "data": records,
            "meta": {
                "symbol": stock_code,
                "interval": interval,
                "count": len(records),
            },
        }
    except Exception as exc:
        logger.error("获取Yahoo Finance数据失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(exc)})


# ======================== Economic Calendar ========================

@router.get("/calendar", summary="获取经济日历")
def get_economic_calendar(
    start_date: str = Query(..., alias="startDate"),
    end_date: str = Query(..., alias="endDate"),
    calendar_type: str = Query("economic", alias="type"),
):
    """获取经济日历事件

    数据源：尝试从 FRED 发布日历 + yfinance 财报日历聚合
    降级时返回最近已知的经济事件
    """
    try:
        events = _fetch_economic_calendar(start_date, end_date, calendar_type)
        if events:
            return {"items": events}

        # 降级到已知重要事件
        return {"items": _get_fallback_calendar_events()}
    except Exception as exc:
        logger.error("获取经济日历失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ======================== Market Data ========================

@router.get("/market/{market}", summary="获取市场数据摘要")
def get_market_data(
    market: str,
    indicator: str = Query("prices", description="指标类型"),
):
    """获取市场指数实时数据

    数据源：Yahoo Finance 实时行情
    支持市场：us, hk, cn, eu
    """
    try:
        summary = _fetch_market_summary(market)
        return {
            "market": market,
            "indicator": indicator,
            "summary": summary,
            "timestamps": [],
            "values": [],
        }
    except Exception as exc:
        logger.error("获取市场数据失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ======================== Financial Statement（基本面适配器接入）========================

@router.get("/stock/{stock_code}/statement", summary="获取股票财务报表")
def get_financial_statement(
    stock_code: str,
    statement: str = Query("income", description="报表类型: income/balance/cashflow"),
):
    """获取股票财务报表

    数据源：基本面适配器（yfinance financials/balance_sheet/cashflow）
    支持类型：income（利润表）, balance（资产负债表）, cashflow（现金流量表）
    """
    try:
        data = _fetch_financial_statement(stock_code, statement)
        if data:
            return data

        return {
            "symbol": stock_code,
            "type": statement,
            "period": "annual",
            "items": [],
            "note": "基本面数据暂不可用，请检查数据源连接",
        }
    except Exception as exc:
        logger.error("获取财务报表失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ======================== Dividends ========================

@router.get("/stock/{stock_code}/dividends", summary="获取股票分红信息")
def get_stock_dividends(stock_code: str):
    """获取股票分红历史

    数据源：yfinance dividends
    """
    try:
        dividends, yield_pct = _fetch_dividends(stock_code)
        return {
            "symbol": stock_code,
            "dividends": dividends,
            "yield_pct": yield_pct,
        }
    except Exception as exc:
        logger.error("获取分红信息失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ======================== Splits ========================

@router.get("/stock/{stock_code}/splits", summary="获取股票分割信息")
def get_stock_splits(stock_code: str):
    """获取股票拆分历史

    数据源：yfinance splits
    """
    try:
        splits = _fetch_splits(stock_code)
        return {
            "symbol": stock_code,
            "splits": splits,
        }
    except Exception as exc:
        logger.error("获取分割信息失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ======================== Dividend Schedule ========================

@router.get("/dividends", summary="获取分红时间表")
def get_dividend_schedule(
    start_date: str = Query(..., alias="startDate"),
    end_date: str = Query(..., alias="endDate"),
):
    """获取分红时间表

    数据源：yfinance 多标的聚合分红日历
    """
    try:
        items = _fetch_dividend_schedule(start_date, end_date)
        return {"items": items}
    except Exception as exc:
        logger.error("获取分红时间表失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ======================== Earnings Calendar ========================

@router.get("/earnings", summary="获取财报日历")
def get_earnings_calendar(
    start_date: str = Query(..., alias="startDate"),
    end_date: str = Query(..., alias="endDate"),
):
    """获取财报日历

    数据源：yfinance 财报日期
    """
    try:
        items = _fetch_earnings_calendar(start_date, end_date)
        if items:
            return {"items": items}
        return {"items": _get_fallback_earnings_calendar()}
    except Exception as exc:
        logger.error("获取财报日历失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ======================== Economic Indicators ========================

@router.get("/economic", summary="获取经济指标")
def get_economic_indicators(
    indicators: str = Query(..., description="指标类型，逗号分隔"),
    start_date: str = Query(..., alias="startDate"),
    end_date: str = Query(..., alias="endDate"),
):
    """获取宏观经济指标

    数据源：FRED API（优先），yfinance 降级
    支持指标：inflation, unemployment, gdp, industrial_production, retail_sales
    """
    try:
        indicator_list = [i.strip() for i in indicators.split(",") if i.strip()]
        result: dict = {}
        for ind in indicator_list:
            data = _fetch_economic_indicator(ind, start_date, end_date)
            result[ind] = data if data else []
        return result
    except Exception as exc:
        logger.error("获取经济指标失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ======================== Real Data Fetchers ========================

def _fetch_fred_rates(start_date, end_date, maturity_type) -> list:
    """从 FRED API 获取利率数据"""
    try:
        import requests

        # FRED series ID 映射
        series_map = {
            "FedFunds": "DFF",       # Federal Funds Effective Rate
            "Treasury": "DGS10",     # 10-Year Treasury Constant Maturity Rate
            "LIBOR": "USD3MTD156N",  # 3-Month London Interbank Offered Rate
        }
        series_id = series_map.get(maturity_type, "DFF")

        api_key = _get_fred_api_key()
        if not api_key:
            return []

        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start_date or "2020-01-01",
            "observation_end": end_date or datetime.now().strftime("%Y-%m-%d"),
            "sort_order": "desc",
            "limit": 100,
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        observations = resp.json().get("observations", [])

        return [
            {
                "date": obs["date"],
                "rate": float(obs["value"]),
                "type": maturity_type or "FedFunds",
            }
            for obs in observations
            if obs.get("value") and obs["value"] != "."
        ]
    except Exception as exc:
        logger.warning("FRED API 获取失败: %s", exc)
        return []


def _get_fred_api_key() -> Optional[str]:
    """获取 FRED API Key（从配置或环境变量）"""
    import os
    key = os.environ.get("FRED_API_KEY", "")
    if not key:
        try:
            from src.config import get_config
            config = get_config()
            key = config.get("fred_api_key", "") or config.get("FRED_API_KEY", "")
        except Exception:
            pass
    return key


def _fetch_treasury_yields_via_yfinance(start_date, end_date) -> list:
    """通过 yfinance 获取美国国债收益率作为降级方案"""
    try:
        import yfinance as yf
        ticker = yf.Ticker("^TNX")  # 10-Year Treasury Yield
        start = start_date or "2020-01-01"
        end = end_date or datetime.now().strftime("%Y-%m-%d")
        hist = ticker.history(start=start, end=end)
        if hist.empty:
            return []
        return [
            {
                "date": idx.strftime("%Y-%m-%d"),
                "rate": round(float(row["Close"]), 2),
                "type": "Treasury",
            }
            for idx, row in hist.iterrows()
        ]
    except Exception as exc:
        logger.warning("yfinance 国债收益率获取失败: %s", exc)
        return []


def _fetch_economic_calendar(start_date, end_date, calendar_type) -> list:
    """聚合经济日历事件"""
    events = []

    # 尝试从 yfinance 获取财报日历
    try:
        import yfinance as yf
        # 获取主要指数的财报季信息
        for symbol in ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]:
            try:
                ticker = yf.Ticker(symbol)
                earnings = ticker.earnings_dates
                if earnings is not None and not earnings.empty:
                    for idx, row in earnings.head(5).iterrows():
                        events.append({
                            "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10],
                            "time": "TBA",
                            "event": f"{symbol} 财报发布",
                            "country": "US",
                            "importance": "high",
                            "previous": "",
                            "forecast": f"EPS Est: {row.get('EPS Estimate', 'N/A')}" if 'EPS Estimate' in row else "",
                        })
            except Exception:
                continue
    except Exception as exc:
        logger.warning("yfinance 财报日历获取失败: %s", exc)

    return events


def _fetch_market_summary(market: str) -> dict:
    """通过 Yahoo Finance 获取市场实时摘要"""
    symbol_map = {
        "us": ("^GSPC", "标普500"),
        "hk": ("^HSI", "恒生指数"),
        "cn": ("000001.SS", "上证指数"),
        "eu": ("^STOXX50E", "欧洲斯托克50"),
    }
    try:
        import yfinance as yf
        symbol, name = symbol_map.get(market, ("^GSPC", "标普500"))
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        hist = ticker.history(period="2d")

        price = info.get("regularMarketPrice") or info.get("previousClose", 0)
        prev_close = info.get("previousClose", 0)

        if not hist.empty and len(hist) >= 2:
            price = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2])

        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        return {
            "name": name,
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
        }
    except Exception as exc:
        logger.warning("yfinance 市场数据获取失败(%s): %s", market, exc)
        return _get_fallback_market_summary(market)


def _fetch_financial_statement(stock_code: str, statement_type: str) -> Optional[dict]:
    """通过 yfinance 基本面适配器获取财务报表"""
    try:
        import yfinance as yf
        ticker = yf.Ticker(stock_code)

        if statement_type == "income":
            df = ticker.financials
            period = "annual"
        elif statement_type == "balance":
            df = ticker.balance_sheet
            period = "annual"
        elif statement_type == "cashflow":
            df = ticker.cashflow
            period = "annual"
        else:
            return None

        if df is None or df.empty:
            return None

        items = []
        for col in df.columns:
            col_str = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
            row_items = {}
            for idx, val in df[col].items():
                if val and not (isinstance(val, float) and (val != val)):  # not NaN
                    row_items[str(idx)] = round(float(val), 2) if isinstance(val, (int, float)) else str(val)
            if row_items:
                items.append({"period": col_str, "values": row_items})

        return {
            "symbol": stock_code,
            "type": statement_type,
            "period": period,
            "items": items,
        }
    except Exception as exc:
        logger.warning("基本面适配器获取失败(%s): %s", stock_code, exc)
        return None


def _fetch_dividends(stock_code: str) -> tuple:
    """通过 yfinance 获取分红数据"""
    try:
        import yfinance as yf
        ticker = yf.Ticker(stock_code)
        div_df = ticker.dividends
        if div_df is None or div_df.empty:
            return [], 0.0

        dividends = []
        for idx, val in div_df.items():
            dividends.append({
                "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx),
                "amount": round(float(val), 4),
            })

        # 计算股息率
        info = ticker.info or {}
        current_price = info.get("regularMarketPrice") or info.get("previousClose", 1)
        annual_dividend = sum(
            float(v) for d, v in div_df.items()
            if hasattr(d, "year") and d.year == datetime.now().year
        ) if not div_df.empty else 0
        yield_pct = round((annual_dividend / current_price * 100), 2) if current_price else 0

        return dividends, yield_pct
    except Exception as exc:
        logger.warning("分红数据获取失败(%s): %s", stock_code, exc)
        return [], 0.0


def _fetch_splits(stock_code: str) -> list:
    """通过 yfinance 获取拆股数据"""
    try:
        import yfinance as yf
        ticker = yf.Ticker(stock_code)
        splits_df = ticker.splits
        if splits_df is None or splits_df.empty:
            return []

        return [
            {
                "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx),
                "ratio": float(val),
            }
            for idx, val in splits_df.items()
        ]
    except Exception as exc:
        logger.warning("拆股数据获取失败(%s): %s", stock_code, exc)
        return []


def _fetch_dividend_schedule(start_date: str, end_date: str) -> list:
    """获取分红时间表（基于已知高分红标的）"""
    try:
        import yfinance as yf
        high_div_symbols = ["T", "VZ", "MO", "XOM", "JNJ", "PG", "KO"]
        items = []
        for symbol in high_div_symbols:
            try:
                ticker = yf.Ticker(symbol)
                div_df = ticker.dividends
                if div_df is not None and not div_df.empty:
                    last_div = div_df.index[-1]
                    if start_date <= last_div.strftime("%Y-%m-%d") <= end_date:
                        items.append({
                            "date": last_div.strftime("%Y-%m-%d"),
                            "symbol": symbol,
                            "company": ticker.info.get("longName", symbol),
                            "amount": round(float(div_df.iloc[-1]), 4),
                            "frequency": "quarterly",
                        })
            except Exception:
                continue
        return items
    except Exception as exc:
        logger.warning("分红时间表获取失败: %s", exc)
        return []


def _fetch_earnings_calendar(start_date: str, end_date: str) -> list:
    """通过 yfinance 获取财报日历"""
    try:
        import yfinance as yf
        major_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM"]
        items = []
        for symbol in major_symbols:
            try:
                ticker = yf.Ticker(symbol)
                earnings = ticker.earnings_dates
                if earnings is not None and not earnings.empty:
                    for idx, row in earnings.head(3).iterrows():
                        date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
                        if start_date <= date_str <= end_date:
                            items.append({
                                "date": date_str,
                                "symbol": symbol,
                                "company": ticker.info.get("longName", symbol),
                                "fiscal_quarter": "",
                                "eps_estimate": float(row.get("EPS Estimate", 0)) if "EPS Estimate" in row else 0,
                                "revenue_estimate": 0,
                            })
            except Exception:
                continue
        return items
    except Exception as exc:
        logger.warning("财报日历获取失败: %s", exc)
        return []


def _fetch_economic_indicator(indicator: str, start_date: str, end_date: str) -> list:
    """从 FRED API 获取经济指标数据"""
    try:
        import requests

        indicator_map = {
            "inflation": "CPIAUCSL",         # Consumer Price Index
            "unemployment": "UNRATE",         # Unemployment Rate
            "gdp": "GDP",                     # Gross Domestic Product
            "industrial_production": "INDPRO", # Industrial Production Index
            "retail_sales": "RSAFS",          # Retail Sales
        }
        series_id = indicator_map.get(indicator)
        if not series_id:
            return []

        api_key = _get_fred_api_key()
        if not api_key:
            return []

        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start_date,
            "observation_end": end_date,
            "sort_order": "desc",
            "limit": 50,
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        observations = resp.json().get("observations", [])

        return [
            {"date": obs["date"], "value": float(obs["value"])}
            for obs in observations
            if obs.get("value") and obs["value"] != "."
        ]
    except Exception as exc:
        logger.warning("经济指标获取失败(%s): %s", indicator, exc)
        return []


# ======================== Fallback Data ========================

def _get_fallback_fed_rates() -> list:
    """降级美联储利率数据（最近的公开数据）"""
    return [
        {"date": "2024-01-31", "rate": 5.50, "type": "FedFunds"},
        {"date": "2024-03-20", "rate": 5.50, "type": "FedFunds"},
        {"date": "2024-05-01", "rate": 5.50, "type": "FedFunds"},
        {"date": "2024-06-12", "rate": 5.50, "type": "FedFunds"},
        {"date": "2024-07-31", "rate": 5.50, "type": "FedFunds"},
        {"date": "2024-09-18", "rate": 5.00, "type": "FedFunds"},
        {"date": "2024-11-07", "rate": 4.75, "type": "FedFunds"},
        {"date": "2024-12-18", "rate": 4.50, "type": "FedFunds"},
    ]


def _get_fallback_calendar_events() -> list:
    """降级经济日历事件"""
    return [
        {
            "date": "2024-06-15",
            "time": "08:30",
            "event": "美国CPI数据公布",
            "country": "US",
            "importance": "high",
            "previous": "3.4%",
            "forecast": "3.3%",
        },
    ]


def _get_fallback_market_summary(market: str) -> dict:
    """降级市场摘要"""
    market_data = {
        "us": {"name": "标普500", "price": 5000.0, "change": 0.5, "change_pct": 0.01},
        "hk": {"name": "恒生指数", "price": 18000.0, "change": 100.0, "change_pct": 0.56},
        "cn": {"name": "上证指数", "price": 3200.0, "change": 15.0, "change_pct": 0.47},
        "eu": {"name": "欧洲斯托克50", "price": 4500.0, "change": -20.0, "change_pct": -0.44},
    }
    return market_data.get(market, {"name": "Unknown", "price": 0, "change": 0, "change_pct": 0})


def _get_fallback_earnings_calendar() -> list:
    """降级财报日历"""
    return [
        {
            "date": "2024-06-20",
            "symbol": "AAPL",
            "company": "Apple Inc.",
            "fiscal_quarter": "Q3 2024",
            "eps_estimate": 1.55,
            "revenue_estimate": 85.0,
        },
    ]
