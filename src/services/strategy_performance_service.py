# -*- coding: utf-8 -*-
"""策略胜率分析服务 — 按战法/信号类型/板块/情绪阶段分类统计胜率.

核心功能：
1. 按战法分类统计胜率、盈亏比、最大回撤
2. 按信号类型统计
3. 按板块统计
4. 按情绪阶段统计
5. 策略对比分析
6. 胜率趋势分析（滚动窗口）
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.repositories.recommendation_tracking_repo import RecommendationTrackingRepository

logger = logging.getLogger(__name__)


class StrategyPerformanceService:
    """策略胜率分析服务."""

    def __init__(self, repo: Optional[RecommendationTrackingRepository] = None):
        self.repo = repo or RecommendationTrackingRepository()

    def get_strategy_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_samples: int = 5,
    ) -> Dict[str, Any]:
        """获取策略分类统计.

        Args:
            start_date: 起始日期
            end_date: 结束日期
            min_samples: 最小样本数（低于此数的策略不显示）

        Returns:
            {
                "by_strategy": {...},
                "by_signal_type": {...},
                "by_sectors": {...},
                "by_sentiment": {...},
                "by_entry_method": {...},
                "by_time_horizon": {...},
            }
        """
        all_records = self.repo.list_records(
            start_date=start_date,
            end_date=end_date,
            limit=10000,
            page=1,
        )["items"]

        closed = [r for r in all_records if r["status"] == "closed"]

        result = {
            "by_strategy": self._compute_category_stats(closed, "strategy_pattern", min_samples),
            "by_signal_type": self._compute_category_stats(closed, "signal_type", min_samples),
            "by_sectors": self._compute_sector_stats(closed, min_samples),
            "by_sentiment": self._compute_category_stats(closed, "sentiment_phase", min_samples),
            "by_entry_method": self._compute_category_stats(closed, "entry_method", min_samples),
            "by_time_horizon": self._compute_category_stats(closed, "time_horizon", min_samples),
            "total_closed": len(closed),
        }

        return result

    def _compute_category_stats(
        self,
        records: List[Dict[str, Any]],
        field: str,
        min_samples: int,
    ) -> Dict[str, Any]:
        """按某个分类字段统计."""
        categories: Dict[str, List[Dict]] = defaultdict(list)

        for r in records:
            cat = (r.get(field) or "unknown").strip() or "unknown"
            if cat and cat != "unknown":
                categories[cat].append(r)

        result = {}
        for cat, items in categories.items():
            if len(items) < min_samples:
                continue

            wins = sum(1 for i in items if (i.get("profit_loss_pct") or 0) > 0)
            losses = sum(1 for i in items if (i.get("profit_loss_pct") or 0) <= 0)
            total_pl = sum(i.get("profit_loss_pct") or 0 for i in items)
            win_pl = sum(i.get("profit_loss_pct") or 0 for i in items if (i.get("profit_loss_pct") or 0) > 0)
            loss_pl = sum(abs(i.get("profit_loss_pct") or 0) for i in items if (i.get("profit_loss_pct") or 0) <= 0)

            pl_pcts = [i.get("profit_loss_pct") or 0 for i in items]
            max_dd = min(pl_pcts) if pl_pcts else 0

            result[cat] = {
                "total": len(items),
                "wins": wins,
                "losses": losses,
                "win_rate": round(wins / len(items) * 100, 1),
                "avg_pl_pct": round(total_pl / len(items), 2),
                "avg_win_pct": round(win_pl / wins, 2) if wins > 0 else 0,
                "avg_loss_pct": round(-loss_pl / losses, 2) if losses > 0 else 0,
                "profit_factor": round(win_pl / loss_pl, 2) if loss_pl > 0 else 999,
                "max_drawdown": round(max_dd, 2),
                "total_pl_pct": round(total_pl, 2),
            }

        # 按胜率排序
        return dict(sorted(result.items(), key=lambda x: x[1]["win_rate"], reverse=True))

    def _compute_sector_stats(
        self,
        records: List[Dict[str, Any]],
        min_samples: int,
    ) -> Dict[str, Any]:
        """按板块统计（解析逗号分隔的sectors字段）."""
        sector_records: Dict[str, List[Dict]] = defaultdict(list)

        for r in records:
            sectors_str = r.get("sectors") or ""
            if not sectors_str:
                continue
            sectors = [s.strip() for s in sectors_str.split(",") if s.strip()]
            for sector in sectors:
                sector_records[sector].append(r)

        result = {}
        for sector, items in sector_records.items():
            if len(items) < min_samples:
                continue

            wins = sum(1 for i in items if (i.get("profit_loss_pct") or 0) > 0)
            losses = sum(1 for i in items if (i.get("profit_loss_pct") or 0) <= 0)
            total_pl = sum(i.get("profit_loss_pct") or 0 for i in items)

            result[sector] = {
                "total": len(items),
                "wins": wins,
                "losses": losses,
                "win_rate": round(wins / len(items) * 100, 1),
                "avg_pl_pct": round(total_pl / len(items), 2),
                "total_pl_pct": round(total_pl, 2),
            }

        return dict(sorted(result.items(), key=lambda x: x[1]["win_rate"], reverse=True))

    def get_strategy_comparison(
        self,
        strategies: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """策略对比分析.

        Args:
            strategies: 要对比的策略列表
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            对比结果，包含胜率、盈亏比、样本数等
        """
        all_records = self.repo.list_records(
            start_date=start_date,
            end_date=end_date,
            limit=10000,
            page=1,
        )["items"]

        closed = [r for r in all_records if r["status"] == "closed"]

        comparison = {}
        for strategy in strategies:
            items = [r for r in closed if (r.get("strategy_pattern") or "").strip() == strategy]
            if not items:
                continue

            wins = sum(1 for i in items if (i.get("profit_loss_pct") or 0) > 0)
            losses = sum(1 for i in items if (i.get("profit_loss_pct") or 0) <= 0)
            total_pl = sum(i.get("profit_loss_pct") or 0 for i in items)
            win_pl = sum(i.get("profit_loss_pct") or 0 for i in items if (i.get("profit_loss_pct") or 0) > 0)
            loss_pl = sum(abs(i.get("profit_loss_pct") or 0) for i in items if (i.get("profit_loss_pct") or 0) <= 0)

            comparison[strategy] = {
                "total": len(items),
                "win_rate": round(wins / len(items) * 100, 1),
                "profit_factor": round(win_pl / loss_pl, 2) if loss_pl > 0 else 999,
                "avg_pl_pct": round(total_pl / len(items), 2),
                "total_pl_pct": round(total_pl, 2),
            }

        return comparison

    def get_rolling_win_rate(
        self,
        days: int = 30,
        window: int = 10,
    ) -> List[Dict[str, Any]]:
        """滚动窗口胜率趋势.

        Args:
            days: 回溯天数
            window: 窗口大小（交易次数）

        Returns:
            [{date, win_rate, total, window}, ...]
        """
        all_records = self.repo.list_records(
            start_date=(date.today() - timedelta(days=days)).isoformat(),
            end_date=date.today().isoformat(),
            limit=10000,
            page=1,
        )["items"]

        closed = sorted(
            [r for r in all_records if r["status"] == "closed"],
            key=lambda x: x.get("close_date") or x.get("created_at") or "",
        )

        if not closed:
            return []

        result = []
        for i in range(window, len(closed) + 1):
            window_items = closed[i - window:i]
            wins = sum(1 for r in window_items if (r.get("profit_loss_pct") or 0) > 0)
            result.append({
                "index": i,
                "win_rate": round(wins / window * 100, 1),
                "total": window,
                "wins": wins,
            })

        return result

    def get_top_performing_strategies(
        self,
        limit: int = 10,
        min_samples: int = 5,
    ) -> List[Dict[str, Any]]:
        """获取表现最好的策略排名.

        Args:
            limit: 返回数量
            min_samples: 最小样本数

        Returns:
            [{strategy, win_rate, profit_factor, total, ...}, ...]
        """
        stats = self.get_strategy_stats(min_samples=min_samples)
        by_strategy = stats.get("by_strategy", {})

        ranked = []
        for strategy, data in by_strategy.items():
            ranked.append({
                "strategy": strategy,
                "win_rate": data["win_rate"],
                "profit_factor": data["profit_factor"],
                "total": data["total"],
                "avg_pl_pct": data["avg_pl_pct"],
                "total_pl_pct": data["total_pl_pct"],
                "max_drawdown": data["max_drawdown"],
            })

        # 综合评分：胜率 * 0.4 + 盈亏比 * 20 * 0.3 + (1-回撤/100) * 10 * 0.3
        for item in ranked:
            item["composite_score"] = round(
                item["win_rate"] * 0.4 +
                min(item["profit_factor"], 5) * 20 * 0.3 +
                max(0, (1 - abs(item["max_drawdown"]) / 100) * 10) * 0.3,
                2,
            )

        ranked.sort(key=lambda x: x["composite_score"], reverse=True)
        return ranked[:limit]
