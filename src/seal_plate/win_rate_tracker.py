"""
打板助手胜率追踪 + 策略自适应优化
基于历史推荐复盘数据，计算胜率并自动调整推荐策略
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .recommendation_log import RecommendationLog, RecommendationItem, RecommendationLogStore

logger = logging.getLogger(__name__)


@dataclass
class WinRateStats:
    """胜率统计"""
    total_recommendations: int = 0
    settled: int = 0              # 已结算
    won: int = 0                  # 盈利
    lost: int = 0                 # 亏损
    pending: int = 0              # 待结算

    avg_return: float = 0.0       # 平均收益率
    max_return: float = 0.0       # 最高收益
    min_return: float = float("-inf")

    # 按维度拆分
    by_sector: dict[str, dict] = field(default_factory=dict)    # sector → {won, total, rate}
    by_score_range: dict[str, dict] = field(default_factory=dict)  # "70-79"/"80-89"/"90-100"

    # 趋势
    rolling_win_rate_10: float = 0.0  # 近10笔胜率
    trend: str = "stable"             # improving / stable / declining

    # 策略调整建议
    strategy_adjustments: list[str] = field(default_factory=list)
    adjustment_reasons: list[str] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        if self.settled == 0:
            return 0.0
        return round(self.won / self.settled * 100, 1)


class WinRateTracker:
    """胜率追踪器"""

    def __init__(self, store: Optional[RecommendationLogStore] = None):
        self.store = store or RecommendationLogStore()

    def compute_stats(self, logs: Optional[list[RecommendationLog]] = None) -> WinRateStats:
        """计算整体胜率统计"""
        if logs is None:
            logs = self.store.load_all(limit=60)

        stats = WinRateStats()
        all_items: list[RecommendationItem] = []

        # 按板块 / 评分区间
        by_sector_total: dict[str, int] = defaultdict(int)
        by_sector_won: dict[str, int] = defaultdict(int)
        by_score_won: dict[str, list[bool]] = defaultdict(list)

        returns: list[float] = []

        for log in logs:
            for r in log.recommendations:
                all_items.append(r)
                stats.total_recommendations += 1

                if r.outcome is None:
                    stats.pending += 1
                    continue

                stats.settled += 1
                ret = r.actual_return_pct or 0

                if r.won:
                    stats.won += 1
                else:
                    stats.lost += 1

                returns.append(ret)

                # 板块统计
                sector = r.sector or "未分类"
                by_sector_total[sector] += 1
                if r.won:
                    by_sector_won[sector] += 1

                # 评分区间
                if r.score >= 90:
                    bucket = "90-100"
                elif r.score >= 80:
                    bucket = "80-89"
                elif r.score >= 70:
                    bucket = "70-79"
                else:
                    bucket = "<70"
                by_score_won[bucket].append(r.won)

        # 结算统计（按时间倒序，取最近）
        if returns:
            stats.avg_return = round(sum(returns) / len(returns), 2)
            stats.max_return = round(max(returns), 2)
            stats.min_return = round(min(returns), 2)

        # 板块胜率
        for sector, total in by_sector_total.items():
            won = by_sector_won.get(sector, 0)
            stats.by_sector[sector] = {
                "won": won, "total": total,
                "rate": round(won / total * 100, 1) if total else 0,
            }

        # 评分区间胜率
        for bucket, results in by_score_won.items():
            total = len(results)
            won = sum(results)
            stats.by_score_range[bucket] = {
                "won": won, "total": total,
                "rate": round(won / total * 100, 1) if total else 0,
            }

        # 近10笔滚动胜率
        recent = [r for r in all_items if r.outcome is not None][-10:]
        if recent:
            stats.rolling_win_rate_10 = round(
                sum(1 for r in recent if r.won) / len(recent) * 100, 1
            )

        # 趋势判定：比较前10笔 vs 后10笔
        all_settled = [r for r in all_items if r.outcome is not None]
        if len(all_settled) >= 20:
            first_half = all_settled[:10]
            second_half = all_settled[-10:]
            wr_first = sum(1 for r in first_half if r.won) / len(first_half)
            wr_second = sum(1 for r in second_half if r.won) / len(second_half)
            diff = wr_second - wr_first
            if diff > 0.1:
                stats.trend = "improving"
            elif diff < -0.1:
                stats.trend = "declining"
            else:
                stats.trend = "stable"

        # 生成策略调整建议
        stats.strategy_adjustments, stats.adjustment_reasons = self._generate_adjustments(stats)

        return stats

    def _generate_adjustments(self, stats: WinRateStats) -> tuple[list[str], list[str]]:
        """基于胜率数据生成策略调整建议"""
        adjustments: list[str] = []
        reasons: list[str] = []

        overall_wr = stats.win_rate

        # 整体胜率评估
        if overall_wr < 40:
            adjustments.append("⚠️ 整体胜率偏低(<40%)，建议降低仓位，提高评分门槛至80+")
            reasons.append(f"整体胜率仅{overall_wr}%，样本{stats.settled}笔")
        elif overall_wr >= 60:
            adjustments.append("✅ 整体胜率良好(≥60%)，保持当前策略")
            reasons.append(f"整体胜率{overall_wr}%")

        # 近10笔趋势
        if stats.rolling_win_rate_10 < 30 and stats.settled >= 10:
            adjustments.append("📉 近10笔胜率降至30%以下，建议暂缓建仓，等待情绪修复")
            reasons.append(f"近10笔胜率仅{stats.rolling_win_rate_10}%")

        if stats.trend == "declining":
            adjustments.append("📉 胜率呈下降趋势，建议缩减仓位至30%以下")
            reasons.append("前10笔与后10笔对比，胜率明显下滑")
        elif stats.trend == "improving":
            adjustments.append("📈 胜率呈上升趋势，可适当加大仓位")
            reasons.append("胜率持续改善中")

        # 板块维度：降低低胜率板块权重
        low_sectors = [
            (s, d) for s, d in stats.by_sector.items()
            if d["total"] >= 3 and d["rate"] < 40
        ]
        high_sectors = [
            (s, d) for s, d in stats.by_sector.items()
            if d["total"] >= 3 and d["rate"] >= 60
        ]

        if low_sectors:
            names = ", ".join(f"{s}({d['rate']:.0f}%)" for s, d in low_sectors[:3])
            adjustments.append(f"⛔ 回避低胜率板块: {names}")
            reasons.append("这些板块历史胜率<40%，建议减少参与")

        if high_sectors:
            names = ", ".join(f"{s}({d['rate']:.0f}%)" for s, d in high_sectors[:3])
            adjustments.append(f"🎯 重点关注高胜率板块: {names}")
            reasons.append("这些板块历史胜率≥60%，可积极参与")

        # 评分区间建议
        best_range = None
        best_rate = 0
        for bucket, d in stats.by_score_range.items():
            if d["total"] >= 3 and d["rate"] > best_rate:
                best_rate = d["rate"]
                best_range = bucket

        if best_range:
            adjustments.append(f"⭐ 历史最佳评分区间: {best_range}(胜率{best_rate:.0f}%)，优先进场")
            reasons.append(f"评分{bucket}区间胜率最高")

        return adjustments, reasons
