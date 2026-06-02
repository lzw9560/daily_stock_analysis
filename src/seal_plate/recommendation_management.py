"""
推荐建仓管理模块
提供：推荐记录查询、每日胜率回溯、历史胜率按日期查询
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from .recommendation_log import RecommendationLog, RecommendationItem, RecommendationLogStore
from .win_rate_tracker import WinRateTracker, WinRateStats

logger = logging.getLogger(__name__)


@dataclass
class DailyWinRateRecord:
    """单日胜率回溯记录"""
    date: str
    label: str = ""
    total_count: int = 0
    settled_count: int = 0
    won_count: int = 0
    lost_count: int = 0
    pending_count: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    max_return: float = 0.0
    min_return: float = 0.0
    sentiment_phase: str = ""
    sentiment_index: float = 50.0
    recommendations: list[dict] = field(default_factory=list)


@dataclass
class RecommendationRecord:
    """推荐建仓详细记录"""
    date: str
    label: str = ""
    generated_at: str = ""
    code: str = ""
    name: str = ""
    score: int = 0
    change_pct: float = 0.0
    seal_time: Optional[str] = None
    sector: Optional[str] = None
    seal_amount: float = 0.0
    reasons: list[str] = field(default_factory=list)
    outcome: Optional[str] = None
    actual_return_pct: Optional[float] = None
    won: Optional[bool] = None
    review_note: Optional[str] = None
    sentiment_phase: str = ""
    sentiment_index: float = 50.0


@dataclass
class WinRateBacktestResult:
    """胜率回溯结果"""
    daily_records: list[DailyWinRateRecord] = field(default_factory=list)
    overall_win_rate: float = 0.0
    total_recommendations: int = 0
    total_settled: int = 0
    total_won: int = 0
    avg_return: float = 0.0
    best_day: Optional[DailyWinRateRecord] = None
    worst_day: Optional[DailyWinRateRecord] = None


class RecommendationManager:
    """推荐建仓管理器

    核心功能：
    1. 推荐建仓记录 - 详细记录每次推荐的时间、标的代码及推荐价格
    2. 每日胜率回溯 - 自动统计并回溯每日推荐标的的涨跌胜率
    3. 历史胜率查询 - 支持选择特定日期查看过往推荐标的的阶段性胜率
    """

    def __init__(self, store: Optional[RecommendationLogStore] = None):
        self.store = store or RecommendationLogStore()
        self.win_tracker = WinRateTracker(self.store)

    # ========================
    #  1. 推荐建仓记录
    # ========================

    def get_all_recommendations(
        self,
        limit: int = 90,
        offset: int = 0,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[RecommendationRecord]:
        """获取所有推荐建仓记录（支持日期范围筛选和分页）

        Args:
            limit: 最大返回条数
            offset: 偏移量
            date_from: 起始日期 YYYYMMDD
            date_to: 结束日期 YYYYMMDD
        """
        logs = self.store.load_all(limit=200)  # 加载足够多用于筛选
        records: list[RecommendationRecord] = []

        for log in logs:
            # 日期范围过滤
            if date_from and log.date < date_from:
                continue
            if date_to and log.date > date_to:
                continue

            for r in log.recommendations:
                records.append(RecommendationRecord(
                    date=log.date,
                    label=self._make_label(log.date),
                    generated_at=log.generated_at,
                    code=r.code,
                    name=r.name,
                    score=r.score,
                    change_pct=r.change_pct,
                    seal_time=r.seal_time,
                    sector=r.sector,
                    seal_amount=getattr(r, 'seal_amount', 0.0),
                    reasons=r.reasons,
                    outcome=r.outcome,
                    actual_return_pct=r.actual_return_pct,
                    won=r.won,
                    review_note=r.review_note,
                    sentiment_phase=log.sentiment_phase,
                    sentiment_index=log.sentiment_index,
                ))

        # 按日期倒序，同一日期内按评分倒序
        records.sort(key=lambda x: (-int(x.date), -x.score))

        return records[offset:offset + limit]

    def get_recommendation_count(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> int:
        """获取推荐总数"""
        logs = self.store.load_all(limit=200)
        count = 0
        for log in logs:
            if date_from and log.date < date_from:
                continue
            if date_to and log.date > date_to:
                continue
            count += len(log.recommendations)
        return count

    # ========================
    #  2. 每日胜率回溯
    # ========================

    def compute_daily_win_rate_backtest(
        self,
        days: int = 30,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> WinRateBacktestResult:
        """计算每日胜率回溯

        对指定日期范围内的每一天，自动统计推荐标的的涨跌胜率。
        提供历史胜率数据评估。

        Args:
            days: 回溯天数（当未指定 date_from/date_to 时使用）
            date_from: 起始日期
            date_to: 结束日期
        """
        logs = self.store.load_all(limit=200)

        # 日期范围确定
        if not date_from and not date_to:
            # 默认最近N天
            date_to = datetime.now().strftime("%Y%m%d")
            date_from = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        # 按日期分组
        daily_map: dict[str, RecommendationLog] = {}
        for log in logs:
            if date_from and log.date < date_from:
                continue
            if date_to and log.date > date_to:
                continue
            daily_map[log.date] = log

        daily_records: list[DailyWinRateRecord] = []
        total_settled = 0
        total_won = 0
        total_returns: list[float] = []

        for date_str in sorted(daily_map.keys()):
            log = daily_map[date_str]
            record = self._compute_single_day(log)
            daily_records.append(record)

            total_settled += record.settled_count
            total_won += record.won_count
            if record.avg_return != 0:
                for r in log.recommendations:
                    if r.actual_return_pct is not None:
                        total_returns.append(r.actual_return_pct)

        daily_records.sort(key=lambda x: x.date, reverse=True)

        # 最佳/最差日
        settled_days = [d for d in daily_records if d.settled_count > 0]
        best_day = max(settled_days, key=lambda d: d.win_rate, default=None)
        worst_day = min(settled_days, key=lambda d: d.win_rate, default=None)

        return WinRateBacktestResult(
            daily_records=daily_records,
            overall_win_rate=round(total_won / total_settled * 100, 1) if total_settled else 0.0,
            total_recommendations=sum(d.total_count for d in daily_records),
            total_settled=total_settled,
            total_won=total_won,
            avg_return=round(sum(total_returns) / len(total_returns), 2) if total_returns else 0.0,
            best_day=best_day,
            worst_day=worst_day,
        )

    # ========================
    #  3. 历史胜率查询
    # ========================

    def query_historical_win_rate(
        self,
        target_date: str,
        lookback_days: int = 5,
    ) -> dict:
        """查询特定日期的阶段性胜率表现

        查看指定日期当天的推荐标的，及其后续表现。
        同时展示前后 N 天的胜率趋势。

        Args:
            target_date: 目标日期 YYYYMMDD
            lookback_days: 前后对比天数
        """
        target_log = self.store.load(target_date)

        # 当日推荐详情
        target_detail = None
        if target_log:
            settled = sum(1 for r in target_log.recommendations if r.outcome is not None)
            won = sum(1 for r in target_log.recommendations if r.won)
            target_detail = {
                "date": target_log.date,
                "label": self._make_label(target_log.date),
                "total_count": len(target_log.recommendations),
                "settled_count": settled,
                "won_count": won,
                "lost_count": settled - won,
                "pending_count": len(target_log.recommendations) - settled,
                "win_rate": round(won / settled * 100, 1) if settled else 0.0,
                "sentiment_phase": target_log.sentiment_phase,
                "sentiment_index": target_log.sentiment_index,
                "recommendations": [
                    {
                        "code": r.code,
                        "name": r.name,
                        "score": r.score,
                        "change_pct": r.change_pct,
                        "seal_time": r.seal_time,
                        "sector": r.sector,
                        "reasons": r.reasons,
                        "outcome": r.outcome,
                        "actual_return_pct": r.actual_return_pct,
                        "won": r.won,
                        "review_note": r.review_note,
                    }
                    for r in target_log.recommendations
                ],
            }

        # 前后 N 天趋势
        date_from = (datetime.strptime(target_date, "%Y%m%d") - timedelta(days=lookback_days)).strftime("%Y%m%d")
        date_to = (datetime.strptime(target_date, "%Y%m%d") + timedelta(days=lookback_days)).strftime("%Y%m%d")

        trend = []
        all_logs = self.store.load_all(limit=200)
        for log in all_logs:
            if date_from <= log.date <= date_to:
                settled = sum(1 for r in log.recommendations if r.outcome is not None)
                won = sum(1 for r in log.recommendations if r.won)
                trend.append({
                    "date": log.date,
                    "label": self._make_label(log.date),
                    "count": len(log.recommendations),
                    "settled": settled,
                    "won": won,
                    "win_rate": round(won / settled * 100, 1) if settled else 0.0,
                    "is_target": log.date == target_date,
                })

        trend.sort(key=lambda x: x["date"])

        # 整体胜率
        stats = self.win_tracker.compute_stats(all_logs)

        return {
            "target_date": target_date,
            "target_detail": target_detail,
            "trend": trend,
            "lookback_days": lookback_days,
            "overall_stats": {
                "total_recommendations": stats.total_recommendations,
                "settled": stats.settled,
                "won": stats.won,
                "lost": stats.lost,
                "pending": stats.pending,
                "win_rate": stats.win_rate,
                "avg_return": stats.avg_return,
                "rolling_win_rate_10": stats.rolling_win_rate_10,
                "trend": stats.trend,
            },
        }

    def get_available_dates(self) -> list[dict]:
        """获取有推荐记录的所有日期列表（供日期选择器使用）"""
        logs = self.store.load_all(limit=200)
        dates = []
        for log in logs:
            settled = sum(1 for r in log.recommendations if r.outcome is not None)
            won = sum(1 for r in log.recommendations if r.won)
            dates.append({
                "date": log.date,
                "label": self._make_label(log.date),
                "count": len(log.recommendations),
                "settled": settled,
                "won": won,
                "win_rate": round(won / settled * 100, 1) if settled else None,
                "sentiment_phase": log.sentiment_phase,
            })
        dates.sort(key=lambda x: x["date"], reverse=True)
        return dates

    # ========================
    #  内部方法
    # ========================

    def _compute_single_day(self, log: RecommendationLog) -> DailyWinRateRecord:
        """计算单日胜率"""
        settled = 0
        won = 0
        lost = 0
        pending = 0
        returns: list[float] = []

        recs = []
        for r in log.recommendations:
            if r.outcome is None:
                pending += 1
            else:
                settled += 1
                ret = r.actual_return_pct or 0
                returns.append(ret)
                if r.won:
                    won += 1
                else:
                    lost += 1

            recs.append({
                "code": r.code,
                "name": r.name,
                "score": r.score,
                "change_pct": r.change_pct,
                "seal_time": r.seal_time,
                "sector": r.sector,
                "reasons": r.reasons,
                "outcome": r.outcome,
                "actual_return_pct": r.actual_return_pct,
                "won": r.won,
                "review_note": r.review_note,
            })

        return DailyWinRateRecord(
            date=log.date,
            label=self._make_label(log.date),
            total_count=len(log.recommendations),
            settled_count=settled,
            won_count=won,
            lost_count=lost,
            pending_count=pending,
            win_rate=round(won / settled * 100, 1) if settled else 0.0,
            avg_return=round(sum(returns) / len(returns), 2) if returns else 0.0,
            max_return=round(max(returns), 2) if returns else 0.0,
            min_return=round(min(returns), 2) if returns else 0.0,
            sentiment_phase=log.sentiment_phase,
            sentiment_index=log.sentiment_index,
            recommendations=recs,
        )

    @staticmethod
    def _make_label(date_str: str) -> str:
        """生成日期标签"""
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
            weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            return f"{dt.strftime('%Y-%m-%d')} {weekdays[dt.weekday()]}"
        except ValueError:
            return date_str
