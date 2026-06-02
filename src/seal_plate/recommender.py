"""
打板助手推荐引擎
基于评分引擎 + 情绪周期 + 历史胜率，生成建仓推荐
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .models import SealPlateReport, SealPlateStock
from .recommendation_log import RecommendationItem, RecommendationLog, RecommendationLogStore
from .win_rate_tracker import WinRateTracker, WinRateStats

logger = logging.getLogger(__name__)


@dataclass
class PositionRecommendation:
    """建仓推荐结果"""
    stock: SealPlateStock
    score: int
    rank: int
    confidence: str            # 高 / 中 / 低
    reasons: list[str] = field(default_factory=list)
    risk_warnings: list[str] = field(default_factory=list)
    suggested_position_pct: float = 0.0  # 建议仓位比例


@dataclass
class DailyRecommendationResult:
    """每日推荐结果"""
    date: str
    label: str                                # 日期标签 "2026-05-25 周一"
    sentiment_index: float
    sentiment_phase: str
    total_limit_up: int
    recommendations: list[PositionRecommendation] = field(default_factory=list)
    win_rate_stats: Optional[WinRateStats] = None
    strategy_notes: list[str] = field(default_factory=list)


class RecommendationEngine:
    """建仓推荐引擎

    支持多数据源增强:
    - 基础候选: 打板评分（AKShare/东方财富）
    - 问财补充: 强势股筛选（iWenCai）
    - 热点验证: 板块热度交叉分析（THS Hotspot）
    """

    MAX_RECOMMENDATIONS = 5     # 每日最多推荐数
    HIGH_CONFIDENCE_SCORE = 80  # 高置信度评分线
    MID_CONFIDENCE_SCORE = 70   # 中置信度评分线

    def __init__(self, log_store: Optional[RecommendationLogStore] = None):
        self.log_store = log_store or RecommendationLogStore()
        self.win_tracker = WinRateTracker(self.log_store)
        self._iwencai_fetcher = None

    @property
    def iwencai(self):
        if self._iwencai_fetcher is None:
            from data_provider.iwencai_fetcher import create_iwencai_fetcher
            self._iwencai_fetcher = create_iwencai_fetcher()
        return self._iwencai_fetcher

    def generate_recommendations(
        self,
        report: SealPlateReport,
        date_label: str = "",
        iwencai_candidates: Optional[List[Dict]] = None,
        fund_analysis: Optional[dict] = None,
    ) -> DailyRecommendationResult:
        """
        基于分析报告生成建仓推荐

        Args:
            report: 打板分析报告
            date_label: 日期标签（如 "2026-05-25 周一"）
            iwencai_candidates: 问财选股候选（可选增强）
            fund_analysis: 资金流向分析结果（可选增强）
        """
        # 1. 收集候选标的（强势 + 关注），剔除创业板
        candidates = list(report.strong_stocks)
        for s in report.watch_stocks:
            if s.score >= 65:
                candidates.append(s)

        # 过滤创业板标的（30xxx）
        gem_filtered = [s for s in candidates if s.code.startswith(("30", "301"))]
        if gem_filtered:
            gem_names = [f"{s.name}({s.code})" for s in gem_filtered]
            logger.info("已过滤创业板标的(%d只): %s", len(gem_filtered), gem_names)
        candidates = [s for s in candidates if not s.code.startswith(("30", "301"))]

        # 问财强势股补充（与打板池交叉验证）
        if iwencai_candidates:
            self._cross_validate_with_iwencai(candidates, iwencai_candidates)

        if not candidates:
            return DailyRecommendationResult(
                date=report.date,
                label=date_label or report.date,
                sentiment_index=report.sentiment_index,
                sentiment_phase=report.sentiment_phase,
                total_limit_up=report.total_limit_up,
            )

        # 2. 对候选评分排序
        candidates.sort(key=lambda s: (
            -s.score,
            s.seal_time or "99:99:99",  # 封板早的优先
            -s.seal_amount,
        ))

        # 3. 加载历史胜率用于策略调整
        history_logs = self.log_store.load_all(limit=60)
        win_stats = self.win_tracker.compute_stats(history_logs)

        # 4. 获取高/低胜率板块
        high_win_sectors = {
            s for s, d in win_stats.by_sector.items()
            if d["total"] >= 3 and d["rate"] >= 60
        }
        low_win_sectors = {
            s for s, d in win_stats.by_sector.items()
            if d["total"] >= 3 and d["rate"] < 40
        }

        # 4.5 资金流向增强：标记资金流入/流出板块
        fund_inflow_sectors: set[str] = set()
        fund_outflow_sectors: set[str] = set()
        if fund_analysis:
            for s in fund_analysis.get("hot_sectors_inflow", []):
                fund_inflow_sectors.add(s.get("name", ""))
            for s in fund_analysis.get("hot_sectors_outflow", []):
                fund_outflow_sectors.add(s.get("name", ""))

        # 5. 生成推荐
        recommendations: list[PositionRecommendation] = []
        seen_sectors: dict[str, int] = {}

        for rank, stock in enumerate(candidates[:15], 1):
            if len(recommendations) >= self.MAX_RECOMMENDATIONS:
                break

            # 同板块最多推2只
            sector = stock.sector or ""
            if sector and seen_sectors.get(sector, 0) >= 2:
                continue
            seen_sectors[sector] = seen_sectors.get(sector, 0) + 1

            # 生成推荐理由（含资金流向）
            reasons = self._build_reasons(stock, report)
            # 资金流向增强
            if sector in fund_inflow_sectors:
                reasons.append(f"💰 {sector}板块资金净流入，主力看好")
            if sector in fund_outflow_sectors:
                reasons.append(f"⚠️ {sector}板块资金净流出，谨慎参与")
            risk_warnings = self._build_risk_warnings(stock, report, low_win_sectors)

            # 置信度
            if stock.score >= self.HIGH_CONFIDENCE_SCORE:
                confidence = "高"
            elif stock.score >= self.MID_CONFIDENCE_SCORE:
                confidence = "中"
            else:
                confidence = "低"

            # 低胜率板块降级
            if sector in low_win_sectors and confidence != "低":
                confidence = "低"
                reasons.append(f"⚠️ {sector}板块历史胜率偏低，降为低置信度")

            # 高胜率板块升级
            if sector in high_win_sectors and stock.score >= 65 and confidence == "中":
                confidence = "高"
                reasons.append(f"🔥 {sector}板块历史胜率高，升级为高置信度")

            # 建议仓位（基于情绪周期 + 置信度）
            base_pct = {
                "冰点期": 5, "启动期": 10, "发酵期": 20,
                "高潮期": 10, "退潮期": 0,
            }.get(report.sentiment_phase, 10)

            conf_mult = {"高": 1.0, "中": 0.6, "低": 0.3}
            suggested_pct = base_pct * conf_mult.get(confidence, 0.5)

            recommendations.append(PositionRecommendation(
                stock=stock,
                score=stock.score,
                rank=rank,
                confidence=confidence,
                reasons=reasons,
                risk_warnings=risk_warnings,
                suggested_position_pct=round(suggested_pct, 1),
            ))

        # 6. 策略调整说明
        strategy_notes = win_stats.strategy_adjustments if recommendations else []

        return DailyRecommendationResult(
            date=report.date,
            label=date_label or report.date,
            sentiment_index=report.sentiment_index,
            sentiment_phase=report.sentiment_phase,
            total_limit_up=report.total_limit_up,
            recommendations=recommendations,
            win_rate_stats=win_stats,
            strategy_notes=strategy_notes,
        )

    # ========================
    #  问财交叉验证
    # ========================

    def _cross_validate_with_iwencai(
        self,
        candidates: list[SealPlateStock],
        iwencai_results: List[Dict],
    ) -> None:
        """
        用问财选股结果交叉验证打板候选池

        策略:
        - 同时出现在打板池和问财结果的 → 加分（多源确认）
        - 仅出现在打板池的 → 标记为"仅打板池"
        - 问财中表现优秀但不在打板池的 → 标记为潜在标的（但不强制加入）
        """
        iwencai_codes = {
            str(r.get("code", "")).zfill(6)
            for r in iwencai_results
            if r.get("code")
        }

        confirmed = 0
        for stock in candidates:
            if stock.code in iwencai_codes:
                stock.score = min(100, stock.score + 3)  # 多源确认加分
                confirmed += 1

        if confirmed:
            logger.info(
                "问财交叉验证: %d/%d 只标的多源确认，已加分",
                confirmed, len(candidates),
            )

    def save_recommendations(self, result: DailyRecommendationResult) -> None:
        """保存推荐记录到日志"""
        log = RecommendationLog(
            date=result.date,
            generated_at=datetime.now().isoformat(),
            sentiment_index=result.sentiment_index,
            sentiment_phase=result.sentiment_phase,
            total_limit_up=result.total_limit_up,
            recommendations=[
                RecommendationItem(
                    code=r.stock.code,
                    name=r.stock.name,
                    score=r.score,
                    change_pct=r.stock.change_pct,
                    seal_time=r.stock.seal_time,
                    sector=r.stock.sector,
                    reasons=r.reasons,
                )
                for r in result.recommendations
            ],
        )
        self.log_store.save(log)
        logger.info(
            "推荐已保存: %s, %d只标的",
            result.date, len(result.recommendations)
        )

    # ========================
    #  理由生成
    # ========================

    def _build_reasons(
        self, stock: SealPlateStock, report: SealPlateReport
    ) -> list[str]:
        """生成推荐理由"""
        reasons: list[str] = []

        # 评分
        if stock.score >= 85:
            reasons.append(f"⭐⭐ 极佳评分({stock.score}分)，多维度表现优异")
        elif stock.score >= 75:
            reasons.append(f"⭐ 良好评分({stock.score}分)，值得关注")
        elif stock.score >= 60:
            reasons.append(f"评分{stock.score}分，基本合格")

        # 封板时间
        if stock.is_morning_seal:
            reasons.append(f"🕐 早盘{stock.seal_time}封板，主力坚决")

        # 封板强度
        if stock.open_count == 0:
            reasons.append("🔒 零开板，封板牢固")
        elif stock.open_count == 1:
            reasons.append("🔓 开板1次回封，弱转强信号")

        # 换手率
        if 5 <= stock.turnover_rate <= 15:
            reasons.append(f"📊 换手率{stock.turnover_rate:.1f}%健康，筹码充分换手")

        # 板块地位
        is_leader = any(l.code == stock.code for l in report.leader_stocks)
        if is_leader:
            reasons.append(f"👑 {stock.sector or '板块'}龙头，辨识度高")

        # 首板/连板
        if stock.consecutive_days <= 1:
            reasons.append("🌱 首板，低位启动空间大")
        elif stock.consecutive_days == 2:
            reasons.append("📈 二板，确认强势")

        # 热点题材
        hot_sectors = [s for s, c in report.sector_hot[:5]]
        if stock.sector and stock.sector in hot_sectors:
            reasons.append(f"🔥 属于当日热点题材({stock.sector})")

        # 八项标准
        if stock.eight_standard_pass >= 7:
            reasons.append(f"✅ 八项标准通过{stock.eight_standard_pass}/8，质量过硬")

        return reasons

    def _build_risk_warnings(
        self, stock: SealPlateStock, report: SealPlateReport,
        low_win_sectors: set[str]
    ) -> list[str]:
        """生成风险警告"""
        warnings: list[str] = []

        if stock.turnover_rate > 25:
            warnings.append(f"换手率{stock.turnover_rate:.1f}%偏高，筹码不稳定")

        if stock.open_count >= 3:
            warnings.append(f"开板{stock.open_count}次，封板分歧大")

        if stock.consecutive_days >= 4:
            warnings.append(f"{stock.consecutive_days}连板高位风险，博弈难度大")

        if stock.seal_amount < 500:
            warnings.append(f"封单仅{stock.seal_amount:.0f}万，资金信心不足")

        sector = stock.sector or ""
        if sector in low_win_sectors:
            warnings.append(f"板块({sector})历史胜率偏低")

        if report.sentiment_phase in ("退潮期", "高潮期"):
            warnings.append(f"当前情绪{report.sentiment_phase}，注意节奏")

        if report.total_limit_up > 150:
            warnings.append("涨停家数过多，警惕一致性和高潮风险")

        # 封板时间过晚
        if stock.seal_time and not stock.is_morning_seal:
            warnings.append(f"封板时间{stock.seal_time}较晚，次日溢价不确定")

        return warnings
