# -*- coding: utf-8 -*-
"""
AkShare fundamental adapter (fail-open).

This adapter intentionally uses capability probing against multiple AkShare
endpoint candidates. It should never raise to caller; partial data is allowed.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

_DIVIDEND_KEYWORD_MAP: Dict[str, List[str]] = {
    "per_share": [
        "每股派息",
        "每股现金红利",
        "每股分红",
        "每股派现",
        "派现(元/股)",
        "派息(元/股)",
        "税前派息(元/股)",
        "现金分红(税前)",
    ],
    "plan_text": [
        "分配方案",
        "分红方案",
        "实施方案",
        "派息方案",
        "方案",
        "预案",
        "方案说明",
    ],
    "ex_dividend_date": ["除权除息日", "除息日", "除权日", "除权除息", "除息日期"],
    "record_date": ["股权登记日", "登记日"],
    "announce_date": ["公告日期", "公告日", "实施公告日", "预案公告日"],
    "report_date": ["报告期", "报告日期", "截止日期", "统计截止日期"],
}


def _safe_float(value: Any) -> Optional[float]:
    """Best-effort float conversion."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    s = str(value).strip().replace(",", "").replace("%", "")
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        parsed = pd.to_datetime(value)
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    try:
        return parsed.to_pydatetime()
    except Exception:
        return None


def _normalize_code(raw: Any) -> str:
    s = _safe_str(raw).upper()
    if "." in s:
        s = s.split(".", 1)[0]
    s = re.sub(r"^(SH|SZ|BJ)", "", s)
    return s


def _pick_by_keywords(row: pd.Series, keywords: List[str]) -> Optional[Any]:
    """
    Return first non-empty row value whose column name contains any keyword.
    """
    for col in row.index:
        col_s = str(col)
        if any(k in col_s for k in keywords):
            val = row.get(col)
            if val is not None and str(val).strip() not in ("", "-", "nan", "None"):
                return val
    return None


def _parse_dividend_plan_to_per_share(plan_text: str) -> Optional[float]:
    """Parse per-share cash dividend from Chinese plan text."""
    text = _safe_str(plan_text)
    if not text:
        return None

    for pattern in (
        r"(?:每)?\s*10\s*股?\s*派(?:发)?\s*([0-9]+(?:\.[0-9]+)?)\s*元",
        r"10\s*派\s*([0-9]+(?:\.[0-9]+)?)\s*元",
    ):
        match = re.search(pattern, text)
        if match:
            parsed = _safe_float(match.group(1))
            if parsed is not None and parsed > 0:
                return parsed / 10.0

    match_per_share = re.search(r"每\s*股\s*派(?:发)?\s*([0-9]+(?:\.[0-9]+)?)\s*元", text)
    if match_per_share:
        parsed = _safe_float(match_per_share.group(1))
        if parsed is not None and parsed > 0:
            return parsed
    return None


def _extract_cash_dividend_per_share(row: pd.Series) -> Optional[float]:
    """Extract pre-tax cash dividend per share from a row."""
    plan_text = _safe_str(_pick_by_keywords(row, _DIVIDEND_KEYWORD_MAP["plan_text"]))
    # Keep pre-tax semantics; skip explicit after-tax plans unless pre-tax marker exists.
    if "税后" in plan_text and "税前" not in plan_text and "含税" not in plan_text:
        return None

    direct = _safe_float(_pick_by_keywords(row, _DIVIDEND_KEYWORD_MAP["per_share"]))
    if direct is not None and direct > 0:
        return direct
    return _parse_dividend_plan_to_per_share(plan_text)


def _filter_rows_by_code(df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    code_cols = [c for c in df.columns if any(k in str(c) for k in ("代码", "股票代码", "证券代码", "symbol", "ts_code"))]
    if not code_cols:
        return df

    target = _normalize_code(stock_code)
    for col in code_cols:
        try:
            series = df[col].astype(str).map(_normalize_code)
            filtered = df[series == target]
            if not filtered.empty:
                return filtered
        except Exception:
            continue
    return pd.DataFrame()


def _normalize_report_date(value: Any) -> Optional[str]:
    parsed = _safe_datetime(value)
    return parsed.date().isoformat() if parsed else None


def _build_dividend_payload(
    dividend_df: pd.DataFrame,
    stock_code: str,
    max_events: int = 5,
) -> Dict[str, Any]:
    work_df = _filter_rows_by_code(dividend_df, stock_code)
    if work_df.empty:
        return {}

    now_date = datetime.now().date()
    ttm_start_date = now_date - timedelta(days=365)
    dedupe_keys = set()
    events: List[Dict[str, Any]] = []

    for _, row in work_df.iterrows():
        if not isinstance(row, pd.Series):
            continue
        ex_dt = _safe_datetime(_pick_by_keywords(row, _DIVIDEND_KEYWORD_MAP["ex_dividend_date"]))
        record_dt = _safe_datetime(_pick_by_keywords(row, _DIVIDEND_KEYWORD_MAP["record_date"]))
        announce_dt = _safe_datetime(_pick_by_keywords(row, _DIVIDEND_KEYWORD_MAP["announce_date"]))
        event_dt = ex_dt or record_dt or announce_dt
        if event_dt is None:
            continue
        event_date = event_dt.date()
        if event_date > now_date:
            continue

        per_share = _extract_cash_dividend_per_share(row)
        if per_share is None or per_share <= 0:
            continue

        dedupe_key = (event_date.isoformat(), round(per_share, 6))
        if dedupe_key in dedupe_keys:
            continue
        dedupe_keys.add(dedupe_key)

        events.append(
            {
                "event_date": event_date.isoformat(),
                "ex_dividend_date": ex_dt.date().isoformat() if ex_dt else None,
                "record_date": record_dt.date().isoformat() if record_dt else None,
                "announcement_date": announce_dt.date().isoformat() if announce_dt else None,
                "cash_dividend_per_share": round(per_share, 6),
                "is_pre_tax": True,
            }
        )

    if not events:
        return {}

    events.sort(key=lambda item: item.get("event_date") or "", reverse=True)
    ttm_events: List[Dict[str, Any]] = []
    for item in events:
        event_dt = _safe_datetime(item.get("event_date"))
        if event_dt is None:
            continue
        event_date = event_dt.date()
        if ttm_start_date <= event_date <= now_date:
            ttm_events.append(item)

    return {
        "events": events[:max(1, max_events)],
        "ttm_event_count": len(ttm_events),
        "ttm_cash_dividend_per_share": (
            round(sum(float(item.get("cash_dividend_per_share") or 0.0) for item in ttm_events), 6)
            if ttm_events else None
        ),
        "coverage": "cash_dividend_pre_tax",
        "as_of": now_date.isoformat(),
    }


def _extract_latest_row(df: pd.DataFrame, stock_code: str) -> Optional[pd.Series]:
    """
    Select the most relevant row for the given stock.
    """
    if df is None or df.empty:
        return None

    code_cols = [c for c in df.columns if any(k in str(c) for k in ("代码", "股票代码", "证券代码", "ts_code", "symbol"))]
    target = _normalize_code(stock_code)
    if code_cols:
        for col in code_cols:
            try:
                series = df[col].astype(str).map(_normalize_code)
                matched = df[series == target]
                if not matched.empty:
                    return matched.iloc[0]
            except Exception:
                continue
        return None

    # Fallback: use latest row
    return df.iloc[0]


class AkshareFundamentalAdapter:
    """AkShare adapter for fundamentals, capital flow and dragon-tiger signals."""

    def _call_df_candidates(
        self,
        candidates: List[Tuple[str, Dict[str, Any]]],
    ) -> Tuple[Optional[pd.DataFrame], Optional[str], List[str]]:
        errors: List[str] = []
        try:
            import akshare as ak
        except Exception as exc:
            return None, None, [f"import_akshare:{type(exc).__name__}"]

        for func_name, kwargs in candidates:
            fn = getattr(ak, func_name, None)
            if fn is None:
                continue
            try:
                df = fn(**kwargs)
                if isinstance(df, pd.Series):
                    df = df.to_frame().T
                if isinstance(df, pd.DataFrame) and not df.empty:
                    return df, func_name, errors
            except Exception as exc:
                errors.append(f"{func_name}:{type(exc).__name__}")
                continue
        return None, None, errors

    def get_fundamental_bundle(self, stock_code: str) -> Dict[str, Any]:
        """
        Return normalized fundamental blocks from AkShare with partial tolerance.
        """
        result: Dict[str, Any] = {
            "status": "not_supported",
            "growth": {},
            "earnings": {},
            "institution": {},
            "source_chain": [],
            "errors": [],
        }

        # Financial indicators
        fin_df, fin_source, fin_errors = self._call_df_candidates([
            ("stock_financial_abstract", {"symbol": stock_code}),
            ("stock_financial_analysis_indicator", {"symbol": stock_code}),
            ("stock_financial_analysis_indicator", {}),
        ])
        result["errors"].extend(fin_errors)
        if fin_df is not None:
            row = _extract_latest_row(fin_df, stock_code)
            if row is not None:
                revenue_yoy = _safe_float(_pick_by_keywords(row, ["营业收入同比", "营收同比", "收入同比", "同比增长"]))
                profit_yoy = _safe_float(_pick_by_keywords(row, ["净利润同比", "净利同比", "归母净利润同比"]))
                roe = _safe_float(_pick_by_keywords(row, ["净资产收益率", "ROE", "净资产收益"]))
                gross_margin = _safe_float(_pick_by_keywords(row, ["毛利率"]))
                report_date = _normalize_report_date(_pick_by_keywords(row, _DIVIDEND_KEYWORD_MAP["report_date"]))
                revenue = _safe_float(_pick_by_keywords(row, ["营业总收入", "营业收入", "营收"]))
                net_profit_parent = _safe_float(_pick_by_keywords(row, ["归母净利润", "母公司股东净利润", "净利润"]))
                operating_cash_flow = _safe_float(
                    _pick_by_keywords(row, ["经营活动产生的现金流量净额", "经营现金流", "经营活动现金流"])
                )
                result["growth"] = {
                    "revenue_yoy": revenue_yoy,
                    "net_profit_yoy": profit_yoy,
                    "roe": roe,
                    "gross_margin": gross_margin,
                }
                financial_report_payload = {
                    "report_date": report_date,
                    "revenue": revenue,
                    "net_profit_parent": net_profit_parent,
                    "operating_cash_flow": operating_cash_flow,
                    "roe": roe,
                }
                if any(v is not None for v in financial_report_payload.values()):
                    result["earnings"]["financial_report"] = financial_report_payload
                result["source_chain"].append(f"growth:{fin_source}")

        # Earnings forecast
        forecast_df, forecast_source, forecast_errors = self._call_df_candidates([
            ("stock_yjyg_em", {"symbol": stock_code}),
            ("stock_yjyg_em", {}),
            ("stock_yjbb_em", {"symbol": stock_code}),
            ("stock_yjbb_em", {}),
        ])
        result["errors"].extend(forecast_errors)
        if forecast_df is not None:
            row = _extract_latest_row(forecast_df, stock_code)
            if row is not None:
                result["earnings"]["forecast_summary"] = _safe_str(
                    _pick_by_keywords(row, ["预告", "业绩变动", "内容", "摘要", "公告"])
                )[:200]
                result["source_chain"].append(f"earnings_forecast:{forecast_source}")

        # Earnings quick report
        quick_df, quick_source, quick_errors = self._call_df_candidates([
            ("stock_yjkb_em", {"symbol": stock_code}),
            ("stock_yjkb_em", {}),
        ])
        result["errors"].extend(quick_errors)
        if quick_df is not None:
            row = _extract_latest_row(quick_df, stock_code)
            if row is not None:
                result["earnings"]["quick_report_summary"] = _safe_str(
                    _pick_by_keywords(row, ["快报", "摘要", "公告", "说明"])
                )[:200]
                result["source_chain"].append(f"earnings_quick:{quick_source}")

        # Dividend details (cash dividend, pre-tax)
        dividend_df, dividend_source, dividend_errors = self._call_df_candidates([
            ("stock_fhps_detail_em", {"symbol": stock_code}),
            ("stock_history_dividend_detail", {"symbol": stock_code, "indicator": "分红", "date": ""}),
            ("stock_dividend_cninfo", {"symbol": stock_code}),
        ])
        result["errors"].extend(dividend_errors)
        if dividend_df is not None:
            dividend_payload = _build_dividend_payload(dividend_df, stock_code, max_events=5)
            if dividend_payload:
                result["earnings"]["dividend"] = dividend_payload
                result["source_chain"].append(f"dividend:{dividend_source}")

        # Institution / top shareholders
        inst_df, inst_source, inst_errors = self._call_df_candidates([
            ("stock_institute_hold", {}),
            ("stock_institute_recommend", {}),
        ])
        result["errors"].extend(inst_errors)
        if inst_df is not None:
            row = _extract_latest_row(inst_df, stock_code)
            if row is not None:
                inst_change = _safe_float(_pick_by_keywords(row, ["增减", "变化", "变动", "持股变化"]))
                result["institution"]["institution_holding_change"] = inst_change
                result["source_chain"].append(f"institution:{inst_source}")

        top10_df, top10_source, top10_errors = self._call_df_candidates([
            ("stock_gdfx_top_10_em", {"symbol": stock_code}),
            ("stock_gdfx_top_10_em", {}),
            ("stock_zh_a_gdhs_detail_em", {"symbol": stock_code}),
            ("stock_zh_a_gdhs_detail_em", {}),
        ])
        result["errors"].extend(top10_errors)
        if top10_df is not None:
            row = _extract_latest_row(top10_df, stock_code)
            if row is not None:
                holder_change = _safe_float(_pick_by_keywords(row, ["增减", "变化", "持股变化", "变动"]))
                result["institution"]["top10_holder_change"] = holder_change
                result["source_chain"].append(f"top10:{top10_source}")

        has_content = bool(result["growth"] or result["earnings"] or result["institution"])
        result["status"] = "partial" if has_content else "not_supported"
        return result

    def get_capital_flow(self, stock_code: str, top_n: int = 5) -> Dict[str, Any]:
        """
        Return stock + sector capital flow.
        """
        result: Dict[str, Any] = {
            "status": "not_supported",
            "stock_flow": {},
            "sector_rankings": {"top": [], "bottom": []},
            "source_chain": [],
            "errors": [],
        }

        stock_df, stock_source, stock_errors = self._call_df_candidates([
            ("stock_individual_fund_flow", {"stock": stock_code}),
            ("stock_individual_fund_flow", {"symbol": stock_code}),
            ("stock_individual_fund_flow", {}),
            ("stock_main_fund_flow", {"symbol": stock_code}),
            ("stock_main_fund_flow", {}),
        ])
        result["errors"].extend(stock_errors)
        if stock_df is not None:
            row = _extract_latest_row(stock_df, stock_code)
            if row is not None:
                net_inflow = _safe_float(_pick_by_keywords(row, ["主力净流入", "净流入", "净额"]))
                inflow_5d = _safe_float(_pick_by_keywords(row, ["5日", "五日"]))
                inflow_10d = _safe_float(_pick_by_keywords(row, ["10日", "十日"]))
                result["stock_flow"] = {
                    "main_net_inflow": net_inflow,
                    "inflow_5d": inflow_5d,
                    "inflow_10d": inflow_10d,
                }
                result["source_chain"].append(f"capital_stock:{stock_source}")

        sector_df, sector_source, sector_errors = self._call_df_candidates([
            ("stock_sector_fund_flow_rank", {}),
            ("stock_sector_fund_flow_summary", {}),
        ])
        result["errors"].extend(sector_errors)
        if sector_df is not None:
            name_col = next((c for c in sector_df.columns if any(k in str(c) for k in ("板块", "行业", "名称", "name"))), None)
            flow_col = next((c for c in sector_df.columns if any(k in str(c) for k in ("净流入", "主力", "flow", "净额"))), None)
            if name_col and flow_col:
                work_df = sector_df[[name_col, flow_col]].copy()
                work_df[flow_col] = pd.to_numeric(work_df[flow_col], errors="coerce")
                work_df = work_df.dropna(subset=[flow_col])
                top_df = work_df.nlargest(top_n, flow_col)
                bottom_df = work_df.nsmallest(top_n, flow_col)
                result["sector_rankings"] = {
                    "top": [{"name": _safe_str(r[name_col]), "net_inflow": float(r[flow_col])} for _, r in top_df.iterrows()],
                    "bottom": [{"name": _safe_str(r[name_col]), "net_inflow": float(r[flow_col])} for _, r in bottom_df.iterrows()],
                }
                result["source_chain"].append(f"capital_sector:{sector_source}")

        has_content = bool(result["stock_flow"] or result["sector_rankings"]["top"] or result["sector_rankings"]["bottom"])
        result["status"] = "partial" if has_content else "not_supported"
        return result

    def get_dragon_tiger_flag(self, stock_code: str, lookback_days: int = 20) -> Dict[str, Any]:
        """
        Return dragon-tiger signal in lookback window.
        """
        result: Dict[str, Any] = {
            "status": "not_supported",
            "is_on_list": False,
            "recent_count": 0,
            "latest_date": None,
            "source_chain": [],
            "errors": [],
        }

        df, source, errors = self._call_df_candidates([
            ("stock_lhb_stock_statistic_em", {}),
            ("stock_lhb_detail_em", {}),
            ("stock_lhb_jgmmtj_em", {}),
        ])
        result["errors"].extend(errors)
        if df is None:
            return result

        # Try code filter
        code_cols = [c for c in df.columns if any(k in str(c) for k in ("代码", "股票代码", "证券代码"))]
        target = _normalize_code(stock_code)
        matched = pd.DataFrame()
        for col in code_cols:
            try:
                series = df[col].astype(str).map(_normalize_code)
                cur = df[series == target]
                if not cur.empty:
                    matched = cur
                    break
            except Exception:
                continue
        if matched.empty:
            result["source_chain"].append(f"dragon_tiger:{source}")
            result["status"] = "ok" if code_cols else "partial"
            return result

        date_col = next((c for c in matched.columns if any(k in str(c) for k in ("日期", "上榜", "交易日", "time"))), None)
        parsed_dates: List[datetime] = []
        if date_col is not None:
            for val in matched[date_col].astype(str).tolist():
                try:
                    parsed_dates.append(pd.to_datetime(val).to_pydatetime())
                except Exception:
                    continue
        now = datetime.now()
        start = now - timedelta(days=max(1, lookback_days))
        recent_dates = [d for d in parsed_dates if start <= d <= now]

        result["is_on_list"] = bool(recent_dates)
        result["recent_count"] = len(recent_dates) if recent_dates else int(len(matched))
        result["latest_date"] = max(recent_dates).date().isoformat() if recent_dates else (
            max(parsed_dates).date().isoformat() if parsed_dates else None
        )
        result["status"] = "ok"
        result["source_chain"].append(f"dragon_tiger:{source}")
        return result

    # ── 北向资金 ────────────────────────────────────────────────────────

    def get_north_bound_flow(self, top_n: int = 10) -> Dict[str, Any]:
        """
        北向资金汇总：沪股通+深股通当日净流入，以及个股北向持仓变化。

        替代方案：ak.stock_hsgt_north_net_flow_in_em()（日级别汇总）
                + ak.stock_hsgt_individual_north_net_flow_in_em()（个股级别）
        若北向接口不可用，降级到融资融券余额变化。
        """
        result: Dict[str, Any] = {
            "status": "not_supported",
            "today_net_inflow": None,
            "sh_net": None,
            "sz_net": None,
            "top_inflow_stocks": [],
            "top_outflow_stocks": [],
            "source_chain": [],
            "errors": [],
        }

        # 北向汇总（沪股通+深股通）
        agg_df, agg_source, agg_errors = self._call_df_candidates([
            ("stock_hsgt_north_net_flow_in_em", {"symbol": "北上"}),
            ("stock_hsgt_north_net_flow_in_em", {}),
            ("stock_hsgt_north_flow_in_sina", {}),
        ])
        result["errors"].extend(agg_errors)

        if agg_df is not None and not agg_df.empty:
            agg_row = agg_df.iloc[-1] if len(agg_df) > 1 else agg_df.iloc[0]
            sh_cols = [c for c in agg_df.columns if any(k in str(c) for k in ("沪股通", "沪", "shanghai"))]
            sz_cols = [c for c in agg_df.columns if any(k in str(c) for k in ("深股通", "深", "shenzhen"))]
            net_cols = [c for c in agg_df.columns if any(k in str(c) for k in ("净流入", "净额", "net"))]
            date_cols = [c for c in agg_df.columns if any(k in str(c) for k in ("日期", "date", "时间"))]

            sh_net = _safe_float(agg_row[sh_cols[0]]) if sh_cols else None
            sz_net = _safe_float(agg_row[sz_cols[0]]) if sz_cols else None
            total_net = _safe_float(agg_row[net_cols[0]]) if net_cols else None

            if total_net is None and sh_net is not None and sz_net is not None:
                total_net = round(sh_net + sz_net, 2)

            trade_date = _safe_str(agg_row[date_cols[0]]) if date_cols else None
            result["today_net_inflow"] = total_net
            result["sh_net"] = sh_net
            result["sz_net"] = sz_net
            result["trade_date"] = trade_date
            result["source_chain"].append(f"north_bound_agg:{agg_source}")

        # 个股北向流入排行
        ind_df, ind_source, ind_errors = self._call_df_candidates([
            ("stock_hsgt_individual_north_net_flow_in_em", {"symbol": "沪股通"}),
            ("stock_hsgt_individual_north_net_flow_in_em", {"symbol": "深股通"}),
            ("stock_hsgt_individual_north_net_flow_in_em", {}),
        ])
        result["errors"].extend(ind_errors)

        if ind_df is not None and not ind_df.empty:
            name_col = next((c for c in ind_df.columns if any(k in str(c) for k in ("名称", "name", "股票"))), None)
            code_col = next((c for c in ind_df.columns if any(k in str(c) for k in ("代码", "code", "symbol"))), None)
            flow_col = next((c for c in ind_df.columns if any(k in str(c) for k in ("净流入", "净额", "net", "流入"))), None)

            if flow_col and name_col:
                ind_df[flow_col] = pd.to_numeric(ind_df[flow_col], errors="coerce")
                ind_df = ind_df.dropna(subset=[flow_col])
                top_flow = ind_df.nlargest(top_n, flow_col)
                bottom_flow = ind_df.nsmallest(top_n, flow_col)

                result["top_inflow_stocks"] = [
                    {
                        "name": _safe_str(r[name_col]),
                        "code": _safe_str(r[code_col]) if code_col else "",
                        "net_inflow": float(r[flow_col]) / 1e8,
                    }
                    for _, r in top_flow.iterrows()
                ]
                result["top_outflow_stocks"] = [
                    {
                        "name": _safe_str(r[name_col]),
                        "code": _safe_str(r[code_col]) if code_col else "",
                        "net_inflow": float(r[flow_col]) / 1e8,
                    }
                    for _, r in bottom_flow.iterrows()
                ]
                result["source_chain"].append(f"north_bound_ind:{ind_source}")

        has_content = result["today_net_inflow"] is not None or bool(
            result["top_inflow_stocks"] or result["top_outflow_stocks"]
        )
        result["status"] = "partial" if has_content else "not_supported"
        return result

    # ── 融资融券余额 ────────────────────────────────────────────────────

    def get_margin_balance(self) -> Dict[str, Any]:
        """
        融资融券余额变化（替代北向实时数据）。

        数据源：ak.stock_margin_detail_sse()（沪市）
              + ak.stock_margin_ratio_pa_em()（融资融券余额）
        """
        result: Dict[str, Any] = {
            "status": "not_supported",
            "margin_balance": None,
            "margin_change": None,
            "short_balance": None,
            "short_change": None,
            "source_chain": [],
            "errors": [],
        }

        df, source, errors = self._call_df_candidates([
            ("stock_margin_detail_sse", {}),
            ("stock_margin_ratio_pa_em", {}),
            ("stock_margin_sse", {}),
        ])
        result["errors"].extend(errors)

        if df is not None and not df.empty:
            row = df.iloc[-1] if len(df) > 1 else df.iloc[0]

            margin_cols = [c for c in df.columns if any(k in str(c) for k in ("融资余额", "融资", "margin"))]
            margin_chg_cols = [c for c in df.columns if any(k in str(c) for k in ("融资变化", "融资买入", "变化"))]
            short_cols = [c for c in df.columns if any(k in str(c) for k in ("融券", "short"))]

            margin_bal = _safe_float(row[margin_cols[0]]) if margin_cols else None
            margin_chg = _safe_float(row[margin_chg_cols[0]]) if margin_chg_cols else None
            short_bal = _safe_float(row[short_cols[0]]) if short_cols else None

            result["margin_balance"] = round(margin_bal / 1e8, 2) if margin_bal else None
            result["margin_change"] = round(margin_chg / 1e8, 2) if margin_chg else None
            result["short_balance"] = round(short_bal / 1e8, 2) if short_bal else None
            result["source_chain"].append(f"margin:{source}")
            result["status"] = "ok" if result["margin_balance"] else "partial"

        return result

    # ── 大宗交易统计 ────────────────────────────────────────────────────

    def get_block_trade_stats(self, top_n: int = 10) -> Dict[str, Any]:
        """
        大宗交易统计（替代/补充龙虎榜）。

        数据源：ak.stock_dzjy_mrmx()（大宗交易明细）
              + ak.stock_dzjy_mrtj()（大宗交易统计）
        """
        result: Dict[str, Any] = {
            "status": "not_supported",
            "today_count": 0,
            "total_amount": None,
            "top_premium": [],
            "top_discount": [],
            "source_chain": [],
            "errors": [],
        }

        # 大宗交易统计（汇总）
        stat_df, stat_source, stat_errors = self._call_df_candidates([
            ("stock_dzjy_mrtj", {}),
        ])
        result["errors"].extend(stat_errors)

        if stat_df is not None and not stat_df.empty:
            row = stat_df.iloc[0] if not stat_df.empty else None
            if row is not None:
                count_cols = [c for c in stat_df.columns if any(k in str(c) for k in ("笔数", "成交笔数", "count"))]
                amt_cols = [c for c in stat_df.columns if any(k in str(c) for k in ("成交额", "金额", "amount"))]

                result["today_count"] = int(_safe_float(row[count_cols[0]]) or 0) if count_cols else 0
                result["total_amount"] = round((_safe_float(row[amt_cols[0]]) or 0) / 1e8, 2) if amt_cols else None
                result["source_chain"].append(f"block_trade_stat:{stat_source}")

        # 大宗交易明细（用于提取折溢价排行）
        detail_df, detail_source, detail_errors = self._call_df_candidates([
            ("stock_dzjy_mrmx", {"symbol": ""}),
            ("stock_dzjy_mrmx", {}),
        ])
        result["errors"].extend(detail_errors)

        if detail_df is not None and not detail_df.empty:
            name_col = next((c for c in detail_df.columns if any(k in str(c) for k in ("名称", "name", "证券"))), None)
            code_col = next((c for c in detail_df.columns if any(k in str(c) for k in ("代码", "code"))), None)
            premium_col = next((c for c in detail_df.columns if any(k in str(c) for k in ("溢价", "折价", "premium", "rate"))), None)
            amt_col = next((c for c in detail_df.columns if any(k in str(c) for k in ("成交额", "金额", "amount", "交易额"))), None)

            if premium_col:
                detail_df[premium_col] = pd.to_numeric(detail_df[premium_col], errors="coerce")
                detail_df = detail_df.dropna(subset=[premium_col])

                top_premium = detail_df.nlargest(top_n, premium_col)
                top_discount = detail_df.nsmallest(top_n, premium_col)

                result["top_premium"] = [
                    {
                        "name": _safe_str(r[name_col]) if name_col else "",
                        "code": _safe_str(r[code_col]) if code_col else "",
                        "premium_rate": round(float(r[premium_col]), 2),
                        "amount": round(float(r[amt_col]) / 1e8, 2) if amt_col and _safe_float(r[amt_col]) else None,
                    }
                    for _, r in top_premium.iterrows()
                ]
                result["top_discount"] = [
                    {
                        "name": _safe_str(r[name_col]) if name_col else "",
                        "code": _safe_str(r[code_col]) if code_col else "",
                        "premium_rate": round(float(r[premium_col]), 2),
                        "amount": round(float(r[amt_col]) / 1e8, 2) if amt_col and _safe_float(r[amt_col]) else None,
                    }
                    for _, r in top_discount.iterrows()
                ]
                result["source_chain"].append(f"block_trade_detail:{detail_source}")

        has_content = result["today_count"] > 0 or bool(result["top_premium"] or result["top_discount"])
        result["status"] = "partial" if has_content else "not_supported"
        return result

    # ── 机构调研动向 ────────────────────────────────────────────────────

    def get_institution_research(self, top_n: int = 10) -> Dict[str, Any]:
        """
        机构调研动向统计。

        数据源：ak.stock_jgdy_tj_em()（机构调研统计）
        可作为龙虎榜的补充信号：机构密集调研往往先于股价变动。
        """
        result: Dict[str, Any] = {
            "status": "not_supported",
            "top_research_stocks": [],
            "total_research_count": 0,
            "source_chain": [],
            "errors": [],
        }

        df, source, errors = self._call_df_candidates([
            ("stock_jgdy_tj_em", {}),
            ("stock_jgdx_tj_em", {}),
            ("stock_jgcc_em", {}),
        ])
        result["errors"].extend(errors)

        if df is not None and not df.empty:
            name_col = next((c for c in df.columns if any(k in str(c) for k in ("名称", "name", "股票"))), None)
            code_col = next((c for c in df.columns if any(k in str(c) for k in ("代码", "code", "symbol"))), None)
            count_col = next((c for c in df.columns if any(k in str(c) for k in ("调研", "家数", "机构", "count", "次数"))), None)
            date_col = next((c for c in df.columns if any(k in str(c) for k in ("日期", "date", "调研日期", "时间"))), None)

            if name_col:
                sort_col = count_col or name_col
                try:
                    if count_col:
                        df[count_col] = pd.to_numeric(df[count_col], errors="coerce")
                    df_sorted = df.sort_values(by=sort_col, ascending=False, na_position="last")
                except Exception:
                    df_sorted = df

                result["total_research_count"] = len(df)
                result["top_research_stocks"] = [
                    {
                        "name": _safe_str(r[name_col]),
                        "code": _safe_str(r[code_col]) if code_col else "",
                        "research_count": int(_safe_float(r[count_col]) or 0) if count_col and _safe_float(r[count_col]) else 1,
                        "latest_date": _safe_str(r[date_col]) if date_col else None,
                    }
                    for _, r in df_sorted.head(top_n).iterrows()
                ]
                result["source_chain"].append(f"institution_research:{source}")
                result["status"] = "partial" if result["top_research_stocks"] else "not_supported"

        return result

    # ── 龙虎榜明细扩展 ──────────────────────────────────────────────────

    def get_dragon_tiger_detail(self, top_n: int = 10) -> Dict[str, Any]:
        """
        龙虎榜明细：每日上榜个股及席位买卖详情。

        数据源：ak.stock_lhb_detail_em()（龙虎榜明细）
              + ak.stock_lhb_jgmmtj_em()（机构买卖统计）
        比 get_dragon_tiger_flag 更丰富，提取席位、买卖金额、机构净买等。
        """
        result: Dict[str, Any] = {
            "status": "not_supported",
            "list_date": None,
            "entries": [],
            "source_chain": [],
            "errors": [],
        }

        # 龙虎榜明细
        detail_df, detail_source, detail_errors = self._call_df_candidates([
            ("stock_lhb_detail_em", {}),
        ])
        result["errors"].extend(detail_errors)

        if detail_df is not None and not detail_df.empty:
            name_col = next((c for c in detail_df.columns if any(k in str(c) for k in ("名称", "name", "股票"))), None)
            code_col = next((c for c in detail_df.columns if any(k in str(c) for k in ("代码", "code"))), None)
            chg_col = next((c for c in detail_df.columns if any(k in str(c) for k in ("涨幅", "涨跌", "change", "pct"))), None)
            buy_col = next((c for c in detail_df.columns if any(k in str(c) for k in ("买入", "buy"))), None)
            sell_col = next((c for c in detail_df.columns if any(k in str(c) for k in ("卖出", "sell"))), None)
            net_col = next((c for c in detail_df.columns if any(k in str(c) for k in ("净买", "净额", "net"))), None)
            date_col = next((c for c in detail_df.columns if any(k in str(c) for k in ("日期", "date", "上榜日期"))), None)
            reason_col = next((c for c in detail_df.columns if any(k in str(c) for k in ("原因", "理由", "reason"))), None)

            trade_dates: List[str] = []
            if date_col:
                for v in detail_df[date_col].astype(str):
                    d = _safe_str(v)
                    if d:
                        trade_dates.append(d)

            if trade_dates:
                from collections import Counter
                date_counter = Counter(trade_dates)
                if date_counter:
                    result["list_date"] = date_counter.most_common(1)[0][0]

            entries = []
            for _, r in detail_df.head(top_n).iterrows():
                entry: Dict[str, Any] = {
                    "name": _safe_str(r[name_col]) if name_col else "",
                    "code": _safe_str(r[code_col]) if code_col else "",
                    "change_pct": round(_safe_float(r[chg_col]) or 0, 2) if chg_col else None,
                    "buy_amount": round((_safe_float(r[buy_col]) or 0) / 1e8, 2) if buy_col else None,
                    "sell_amount": round((_safe_float(r[sell_col]) or 0) / 1e8, 2) if sell_col else None,
                    "net_amount": round((_safe_float(r[net_col]) or 0) / 1e8, 2) if net_col else None,
                    "reason": _safe_str(r[reason_col]) if reason_col else "",
                }
                if entry.get("name") or entry.get("code"):
                    entries.append(entry)

            result["entries"] = entries
            result["source_chain"].append(f"dragon_tiger_detail:{detail_source}")

        # 机构买卖统计（补充机构席位视角）
        inst_df, inst_source, inst_errors = self._call_df_candidates([
            ("stock_lhb_jgmmtj_em", {}),
        ])
        result["errors"].extend(inst_errors)

        if inst_df is not None and not inst_df.empty:
            name_col = next((c for c in inst_df.columns if any(k in str(c) for k in ("名称", "name", "股票"))), None)
            code_col = next((c for c in inst_df.columns if any(k in str(c) for k in ("代码", "code"))), None)
            inst_buy = next((c for c in inst_df.columns if any(k in str(c) for k in ("机构买入", "机构净买"))), None)
            inst_sell = next((c for c in inst_df.columns if any(k in str(c) for k in ("机构卖出"))), None)

            inst_entries = []
            for _, r in inst_df.head(top_n).iterrows():
                ib = _safe_float(r[inst_buy]) if inst_buy else None
                isell = _safe_float(r[inst_sell]) if inst_sell else None
                inst_entries.append({
                    "name": _safe_str(r[name_col]) if name_col else "",
                    "code": _safe_str(r[code_col]) if code_col else "",
                    "inst_buy": round(ib / 1e8, 2) if ib else None,
                    "inst_sell": round(isell / 1e8, 2) if isell else None,
                    "inst_net": round((ib or 0) - (isell or 0), 2) if ib or isell else None,
                })

            if inst_entries:
                result["inst_entries"] = inst_entries
                result["source_chain"].append(f"dragon_tiger_inst:{inst_source}")

        has_content = bool(result["entries"]) or bool(result.get("inst_entries"))
        result["status"] = "partial" if has_content else "not_supported"
        return result
