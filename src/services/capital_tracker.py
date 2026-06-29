# -*- coding: utf-8 -*-
"""多维资金画像服务 — 北向资金替代方案.

替代逻辑：
北向资金（外资） + 融资余额（杠杆资金） + 主力净流入（大资金）
= 三维资金面画像，比单一北向指标更立体。

数据源：
1. 主力资金净流入 — 东方财富（efinance 已支持）
2. 融资融券余额 — 上交所/深交所（akshare 支持）
3. 大宗交易 — 东方财富（akshare 支持）
4. 北向资金汇总（备用） — efinance / akshare
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class CapitalTracker:
    """多维资金画像追踪器."""

    def __init__(self):
        pass

    def get_capital_profile(
        self,
        date_str: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取多维资金画像.

        Returns:
            {
                "date": "...",
                "main_force": {...},     # 主力资金
                "margin": {...},          # 融资融券
                "block_trade": {...},     # 大宗交易
                "north_bound": {...},     # 北向资金（备用）
                "composite_score": ...,   # 综合资金评分
            }
        """
        if not date_str:
            date_str = date.today().isoformat()

        result = {"date": date_str}

        # 1. 主力资金净流入（最可靠的数据源）
        result["main_force"] = self._get_main_force_flow(date_str)

        # 2. 融资融券余额
        result["margin"] = self._get_margin_data(date_str)

        # 3. 大宗交易
        result["block_trade"] = self._get_block_trade(date_str)

        # 4. 北向资金（备用）
        result["north_bound"] = self._get_north_bound_backup(date_str)

        # 5. 综合评分
        result["composite_score"] = self._compute_composite_score(result)

        return result

    def _get_main_force_flow(self, date_str: str) -> Dict[str, Any]:
        """获取主力资金净流入（东方财富）.

        通过 efinance 或 akshare 获取板块/个股主力资金流向.
        """
        try:
            # 尝试使用 efinance（更快更稳定）
            from data_provider.efinance_fetcher import EfinanceFetcher
            fetcher = EfinanceFetcher()
            # 获取板块资金流向
            sector_flows = fetcher.get_sector_capital_flow(date_str) if hasattr(fetcher, "get_sector_capital_flow") else []
            if sector_flows:
                top_inflow = sorted(sector_flows, key=lambda x: x.get("net_inflow", 0), reverse=True)[:5]
                top_outflow = sorted(sector_flows, key=lambda x: x.get("net_inflow", 0))[:5]
                total_inflow = sum(s.get("net_inflow", 0) for s in top_inflow)
                total_outflow = sum(abs(s.get("net_inflow", 0)) for s in top_outflow)
                return {
                    "status": "success",
                    "total_net_inflow": round(total_inflow - total_outflow, 1),
                    "top_inflow_sectors": [{"name": s.get("name", ""), "net_inflow": round(s.get("net_inflow", 0), 1)} for s in top_inflow],
                    "top_outflow_sectors": [{"name": s.get("name", ""), "net_inflow": round(s.get("net_inflow", 0), 1)} for s in top_outflow],
                }
        except Exception as e:
            logger.debug("主力资金获取失败: %s", e)

        return {"status": "unavailable", "total_net_inflow": 0, "note": "主力资金数据不可用"}

    def _get_margin_data(self, date_str: str) -> Dict[str, Any]:
        """获取融资融券余额（上交所/深交所）.

        融资余额变化 = 杠杆资金动向.
        """
        try:
            import akshare as ak
            # 沪深两市融资融券余额
            margin_detail = ak.stock_margin_details_em(symbol="沪A")
            if not margin_detail.empty:
                latest = margin_detail.iloc[-1]
                return {
                    "status": "success",
                    "balance": float(latest.get("rzye", 0)) / 1e8,  # 亿
                    "change": float(latest.get("rzlke", 0)),
                    "date": date_str,
                }
        except Exception as e:
            logger.debug("融资融券获取失败: %s", e)

        return {"status": "unavailable", "balance": 0, "change": 0}

    def _get_block_trade(self, date_str: str) -> Dict[str, Any]:
        """获取大宗交易数据.

        大宗交易 = 机构/大户调仓信号.
        """
        try:
            import akshare as ak
            # 当日大宗交易
            block_df = ak.stock_dzjy_mrmx(date=date_str.replace("-", ""))
            if not block_df.empty:
                total_amount = block_df.get("成交金额", block_df.get("amount", pd.Series([0]))).sum()
                return {
                    "status": "success",
                    "deal_count": len(block_df),
                    "total_amount": round(total_amount / 1e8, 1),
                }
        except Exception as e:
            logger.debug("大宗交易获取失败: %s", e)

        return {"status": "unavailable", "deal_count": 0, "total_amount": 0}

    def _get_north_bound_backup(self, date_str: str) -> Dict[str, Any]:
        """北向资金（备用数据源）.

        优先使用 efinance，降级到 akshare.
        """
        # 尝试 efinance
        try:
            from data_provider.efinance_fetcher import EfinanceFetcher
            fetcher = EfinanceFetcher()
            if hasattr(fetcher, "get_north_flow"):
                nf = fetcher.get_north_flow(date_str)
                if nf:
                    return {"status": "success", **nf}
        except Exception as e:
            logger.debug("efinance 北向获取失败: %s", e)

        # 降级到 akshare
        try:
            import akshare as ak
            hsgt = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
            if not hsgt.empty:
                latest = hsgt.iloc[-1]
                return {
                    "status": "success",
                    "net_flow": float(latest) if isinstance(latest, (int, float)) else 0,
                    "date": date_str,
                }
        except Exception as e:
            logger.debug("akshare 北向获取失败: %s", e)

        return {"status": "unavailable", "net_flow": 0}

    def _compute_composite_score(self, profile: Dict[str, Any]) -> float:
        """综合资金评分（0-100）.

        权重：
        - 主力资金净流入：40%
        - 融资余额变化：30%
        - 大宗交易活跃度：15%
        - 北向资金：15%
        """
        score = 0

        # 主力资金（-100到+100映射到0-40分）
        mf = profile.get("main_force", {})
        if mf.get("status") == "success":
            net = mf.get("total_net_inflow", 0)
            score += min(40, max(0, 20 + net / 10))

        # 融资余额变化（-100到+100映射到0-30分）
        mg = profile.get("margin", {})
        if mg.get("status") == "success":
            change = mg.get("change", 0)
            score += min(30, max(0, 15 + change / 2))

        # 大宗交易活跃度（0-15分）
        bt = profile.get("block_trade", {})
        if bt.get("status") == "success":
            amount = bt.get("total_amount", 0)
            score += min(15, amount / 10)

        # 北向资金（0-15分）
        nb = profile.get("north_bound", {})
        if nb.get("status") == "success":
            flow = nb.get("net_flow", 0)
            score += min(15, max(0, 7.5 + flow / 5))

        return round(min(100, max(0, score)), 1)
