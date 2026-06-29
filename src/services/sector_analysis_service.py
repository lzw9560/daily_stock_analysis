# -*- coding: utf-8 -*-
"""板块联动分析服务 — 识别主线板块、板块内选股、板块轮动.

核心功能：
1. 板块强度打分（涨停数 + 资金流入 + 涨幅 + 个股联动）
2. 主线识别（连续2日以上的资金聚集板块）
3. 轮动检测（资金从高位板块流向低位板块的信号）
4. 板块内选股（在强势板块内筛选个股）
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SectorAnalysisService:
    """板块联动分析服务."""

    def __init__(self):
        pass

    def analyze_sector_strength(
        self,
        sector_data: List[Dict[str, Any]],
        limit_up_data: List[Dict[str, Any]],
        capital_flow_data: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """分析板块强度.

        Args:
            sector_data: 板块数据 [{sector, change_pct, volume, ...}]
            limit_up_data: 涨停数据 [{code, sector, seal_time, ...}]
            capital_flow_data: 资金流向数据 [{sector, net_inflow, ...}]

        Returns:
            板块强度排行榜 [{sector, score, rank, ...}]
        """
        sector_scores = {}

        # 1. 涨停数得分（权重40%）
        limit_up_counts = defaultdict(int)
        for stock in limit_up_data:
            sector = stock.get("sector") or stock.get("sectors") or "unknown"
            limit_up_counts[sector] += 1

        max_limit_up = max(limit_up_counts.values()) if limit_up_counts else 1
        for sector, count in limit_up_counts.items():
            sector_scores[sector] = sector_scores.get(sector, 0) + (count / max_limit_up) * 40

        # 2. 资金流入得分（权重30%）
        inflows = {d.get("sector", ""): d.get("net_inflow", 0) for d in capital_flow_data}
        max_inflow = max(abs(v) for v in inflows.values()) if inflows else 1
        for sector, inflow in inflows.items():
            if sector and sector != "unknown":
                sector_scores[sector] = sector_scores.get(sector, 0) + (inflow / max_inflow) * 30 if inflow > 0 else 0

        # 3. 板块涨幅得分（权重20%）
        for s in sector_data:
            sector = s.get("sector") or s.get("name") or ""
            change = s.get("change_pct", 0)
            if sector and sector != "unknown":
                sector_scores[sector] = sector_scores.get(sector, 0) + max(0, change) * 2

        # 4. 个股联动得分（权重10%）
        sector_stock_counts = defaultdict(int)
        for s in sector_data:
            sector = s.get("sector") or s.get("name") or ""
            if sector and sector != "unknown":
                sector_stock_counts[sector] += 1
        max_stocks = max(sector_stock_counts.values()) if sector_stock_counts else 1
        for sector, count in sector_stock_counts.items():
            sector_scores[sector] = sector_scores.get(sector, 0) + (count / max_stocks) * 10

        # 排序
        ranked = sorted(
            sector_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return [
            {
                "sector": sector,
                "score": round(score, 1),
                "rank": i + 1,
            }
            for i, (sector, score) in enumerate(ranked)
        ]

    def identify_main_line(
        self,
        daily_sector_scores: List[List[Dict[str, Any]]],
        min_days: int = 2,
    ) -> List[Dict[str, Any]]:
        """识别主线板块（连续N日资金聚集）.

        Args:
            daily_sector_scores: 每日板块得分列表 [[{sector, score}, ...], ...]
            min_days: 最少连续天数

        Returns:
            [{sector, days_consecutive, avg_score, trend}, ...]
        """
        sector_history = defaultdict(list)

        for day_scores in daily_sector_scores:
            for item in day_scores:
                sector = item.get("sector", "")
                score = item.get("score", 0)
                if sector:
                    sector_history[sector].append(score)

        main_lines = []
        for sector, scores in sector_history.items():
            consecutive = 0
            max_consecutive = 0
            for s in scores:
                if s > 50:  # 得分>50视为资金聚集
                    consecutive += 1
                    max_consecutive = max(max_consecutive, consecutive)
                else:
                    consecutive = 0

            if max_consecutive >= min_days:
                avg_score = sum(scores[-max_consecutive:]) / len(scores[-max_consecutive:])
                if len(scores) >= 3:
                    trend = "rising" if scores[-1] > scores[-3] else "stable"
                else:
                    trend = "rising" if scores[-1] > scores[0] else "stable"

                main_lines.append({
                    "sector": sector,
                    "days_consecutive": max_consecutive,
                    "avg_score": round(avg_score, 1),
                    "trend": trend,
                    "recent_scores": scores[-5:],
                })

        main_lines.sort(key=lambda x: x["days_consecutive"], reverse=True)
        return main_lines

    def detect_rotation(
        self,
        current_scores: List[Dict[str, Any]],
        previous_scores: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """检测板块轮动信号.

        资金从高位板块流向低位板块 = 轮动信号

        Returns:
            [{from_sector, to_sector, signal_type, strength}, ...]
        """
        prev_map = {s["sector"]: s["score"] for s in previous_scores}
        curr_map = {s["sector"]: s["score"] for s in current_scores}

        rotations = []

        # 资金流出板块（得分下降）
        flowing_out = []
        for sector, prev_score in prev_map.items():
            curr_score = curr_map.get(sector, 0)
            if prev_score > 60 and curr_score < prev_score * 0.7:
                flowing_out.append((sector, prev_score - curr_score))

        # 资金流入板块（得分上升）
        flowing_in = []
        for sector, curr_score in curr_map.items():
            prev_score = prev_map.get(sector, 0)
            if curr_score > 50 and curr_score > prev_score * 1.3:
                flowing_in.append((sector, curr_score - prev_score))

        # 配对轮动信号
        for out_sector, out_strength in sorted(flowing_out, key=lambda x: x[1], reverse=True)[:3]:
            for in_sector, in_strength in sorted(flowing_in, key=lambda x: x[1], reverse=True)[:3]:
                if out_sector != in_sector:
                    rotations.append({
                        "from_sector": out_sector,
                        "to_sector": in_sector,
                        "out_strength": round(out_strength, 1),
                        "in_strength": round(in_strength, 1),
                        "signal_type": "rotation",
                        "confidence": min((out_strength + in_strength) / 200, 1.0),
                    })

        return rotations[:9]

    def screen_within_sector(
        self,
        sector: str,
        stocks: List[Dict[str, Any]],
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """板块内选股.

        Args:
            sector: 目标板块
            stocks: 股票列表 [{code, name, change_pct, volume_ratio, ...}]
            limit: 返回数量

        Returns:
            按综合得分排序的股票列表
        """
        sector_stocks = [s for s in stocks if sector in (s.get("sectors") or "")]

        if not sector_stocks:
            return []

        # 简单综合打分
        scored = []
        for s in sector_stocks:
            change = s.get("change_pct", 0)
            vol_ratio = s.get("volume_ratio", 1)
            score = change * 2 + (vol_ratio - 1) * 10
            scored.append({
                **s,
                "score": round(score, 1),
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]
