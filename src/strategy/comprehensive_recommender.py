"""
综合推荐引擎 - 核心编排模块

整合以下功能：
1. 每日回溯记录 + 策略自适应调整
2. 买卖点位建议 + 买卖意愿分析
3. 胜率复盘 + 趋势转弱调整
4. 短中长期投资建议
5. 游资意愿 + 板块轮动分析
6. 整体风险等级评估
7. 个股详细风险剖析
8. 动态仓位管理
9. 多因子相关性监控
10. 压力测试 + 极端行情熔断
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)


# ============================================================
#  Data Models
# ============================================================

@dataclass
class BuySellAnalysis:
    """买卖点位分析与意愿"""
    code: str
    name: str
    buy_willingness: int = 0           # 买入意愿 0-100
    sell_willingness: int = 0          # 卖出意愿 0-100
    ideal_buy_price: float = 0.0
    buy_range_low: float = 0.0
    buy_range_high: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_short: float = 0.0     # 短线止盈
    take_profit_long: float = 0.0      # 中线止盈
    entry_strategy: str = ""
    exit_strategy: str = ""
    buy_signals: list[str] = field(default_factory=list)
    sell_signals: list[str] = field(default_factory=list)


@dataclass
class TermAdvice:
    """短中长期建议"""
    term: str = ""                     # short / mid / long
    label: str = ""                    # 短线 / 中线 / 长线
    action: str = ""                   # 买入/持有/减仓/清仓
    confidence: str = ""               # 高/中/低
    target_return_pct: float = 0.0
    hold_days: str = ""
    strategy_desc: str = ""
    risk_level: str = ""
    key_levels: list[str] = field(default_factory=list)


@dataclass
class SectorRotationAnalysis:
    """板块轮动分析"""
    hot_sectors: list[dict] = field(default_factory=list)          # 热门板块
    cooling_sectors: list[dict] = field(default_factory=list)      # 退潮板块
    next_potential_sectors: list[dict] = field(default_factory=list)  # 潜在轮动
    rotation_phase: str = "neutral"    # 轮动阶段
    rotation_score: int = 50
    hot_money_focus: list[str] = field(default_factory=list)
    institution_focus: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class RiskAssessment:
    """整体风险等级评估"""
    overall_risk_score: int = 50       # 综合风险评分 0-100
    overall_risk_level: str = "medium" # low/medium/high/critical
    market_risk: int = 50
    position_risk: int = 50
    sector_concentration_risk: int = 50
    liquidity_risk: int = 50
    sentiment_risk: int = 50
    risk_factors: list[str] = field(default_factory=list)
    risk_mitigations: list[str] = field(default_factory=list)
    max_recommended_position: float = 30.0  # 总建议仓位%


@dataclass
class IndividualStockRisk:
    """个股详细风险剖析"""
    code: str
    name: str
    risk_score: int = 0
    risk_level: str = "medium"
    # 细分风险维度
    valuation_risk: int = 0            # 估值风险
    technical_risk: int = 0            # 技术面风险
    fund_flow_risk: int = 0            # 资金面风险
    sentiment_risk: int = 0            # 情绪面风险
    sector_risk: int = 0               # 板块风险
    liquidity_risk: int = 0            # 流动性风险
    black_swan_risk: int = 0           # 黑天鹅风险
    # 详细说明
    risk_items: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    position_limit_pct: float = 0.0


@dataclass
class DynamicPosition:
    """动态仓位管理"""
    total_capital: float = 100000       # 总资金
    current_position_pct: float = 0.0   # 当前仓位%
    target_position_pct: float = 30.0   # 目标仓位%
    max_position_pct: float = 50.0      # 最大仓位%
    cash_reserve_pct: float = 100.0     # 现金比例%
    # 个股权重
    stock_weights: list[dict] = field(default_factory=list)
    adjustment_reason: str = ""
    rebalancing_needed: bool = False


@dataclass
class FactorCorrelation:
    """因子相关性监控"""
    factor_name: str
    current_value: float
    z_score: float                     # 偏离度
    correlation_with_market: float
    status: str = "normal"             # normal/warning/anomaly
    warning_msg: str = ""


@dataclass
class StressTestResult:
    """压力测试结果"""
    scenario: str = ""
    max_drawdown_pct: float = 0.0
    portfolio_loss_pct: float = 0.0
    recovery_days_est: int = 0
    circuit_breaker_triggered: bool = False
    circuit_breaker_level: str = "none"  # none/yellow/red/black
    suggested_action: str = ""
    impact_on_holdings: list[dict] = field(default_factory=list)


@dataclass
class ComprehensiveRecommendation:
    """综合推荐结果"""
    date: str
    label: str
    generated_at: str = ""

    # 基本市场数据
    sentiment_index: float = 50.0
    sentiment_phase: str = "中性"
    total_limit_up: int = 0
    market_heat_score: int = 50
    fund_sentiment: str = "中性"

    # 核心推荐
    buy_sell_analyses: list[BuySellAnalysis] = field(default_factory=list)

    # 短中长期建议
    term_advices: list[TermAdvice] = field(default_factory=list)

    # 板块轮动
    sector_rotation: Optional[SectorRotationAnalysis] = None

    # 风险等级
    risk_assessment: Optional[RiskAssessment] = None

    # 个股风险
    individual_stock_risks: list[IndividualStockRisk] = field(default_factory=list)

    # 仓位管理
    dynamic_position: Optional[DynamicPosition] = None

    # 因子监控
    factor_correlations: list[FactorCorrelation] = field(default_factory=list)

    # 压力测试
    stress_test_results: list[StressTestResult] = field(default_factory=list)

    # 策略调整
    strategy_adjustments: list[str] = field(default_factory=list)
    adjustment_reasons: list[str] = field(default_factory=list)

    # 胜率回溯
    win_rate_info: dict = field(default_factory=dict)


# ============================================================
#  Comprehensive Recommendation Engine
# ============================================================

class ComprehensiveRecommendationEngine:
    """综合推荐引擎 - 整合所有量化策略维度"""

    # 市场阶段 → 建议总仓位映射
    PHASE_POSITION_MAP = {
        "冰点期": {"target": 15, "max": 25, "desc": "极度悲观期，轻仓试探"},
        "启动期": {"target": 30, "max": 50, "desc": "行情启动，逐步加仓"},
        "发酵期": {"target": 50, "max": 70, "desc": "趋势明确，积极做多"},
        "高潮期": {"target": 40, "max": 60, "desc": "高位运行，控制风险"},
        "退潮期": {"target": 10, "max": 20, "desc": "行情走弱，减仓观望"},
    }

    def __init__(self, log_store=None, report=None, fund_analysis=None):
        from src.seal_plate.recommendation_log import RecommendationLogStore
        from src.seal_plate.win_rate_tracker import WinRateTracker

        self.log_store = log_store or RecommendationLogStore()
        self.win_tracker = WinRateTracker(self.log_store)
        self.report = report
        self.fund_analysis = fund_analysis

    def generate_comprehensive(
        self,
        report,
        fund_analysis=None,
        iwen_cai_results=None,
        portfolio_positions=None,
    ) -> ComprehensiveRecommendation:
        """生成综合推荐"""
        from src.seal_plate.date_utils import get_label_for_date

        result = ComprehensiveRecommendation(
            date=report.date,
            label=get_label_for_date(report.date),
            generated_at=datetime.now().isoformat(),
            sentiment_index=report.sentiment_index,
            sentiment_phase=report.sentiment_phase,
            total_limit_up=report.total_limit_up or 0,
        )

        # 收集所有候选标的
        candidates = list(report.strong_stocks) + [
            s for s in report.watch_stocks if s.score >= 60
        ]

        # 1. 买卖点位分析与意愿
        result.buy_sell_analyses = self._analyze_buy_sell_points(
            candidates, report, fund_analysis
        )

        # 2. 短中长期建议
        result.term_advices = self._generate_term_advices(report)

        # 3. 板块轮动分析
        result.sector_rotation = self._analyze_sector_rotation(report, fund_analysis)

        # 4. 整体风险评估
        result.risk_assessment = self._assess_overall_risk(
            report, fund_analysis, candidates
        )

        # 5. 个股风险剖析
        result.individual_stock_risks = self._analyze_individual_stocks(
            candidates, report
        )

        # 6. 动态仓位管理
        result.dynamic_position = self._manage_dynamic_position(
            report, candidates, portfolio_positions
        )

        # 7. 因子相关性监控
        result.factor_correlations = self._monitor_factor_correlations(report)

        # 8. 压力测试
        result.stress_test_results = self._run_stress_tests(
            candidates, result.risk_assessment
        )

        # 9. 胜率回溯 + 策略调整
        result.win_rate_info = self._compute_win_rate_backtest()
        adjustments, reasons = self._generate_strategy_adjustments(result)
        result.strategy_adjustments = adjustments
        result.adjustment_reasons = reasons

        # 市场热度与资金情绪
        result.market_heat_score = int(report.sentiment_index)
        if fund_analysis:
            result.fund_sentiment = getattr(fund_analysis, 'fund_sentiment', '中性')

        return result

    # ============================================================
    #  1. 买卖点位与意愿分析
    # ============================================================

    def _analyze_buy_sell_points(
        self, candidates, report, fund_analysis
    ) -> list[BuySellAnalysis]:
        results = []
        sector_counts = defaultdict(int)
        for s in candidates:
            if s.sector:
                sector_counts[s.sector] += 1

        for stock in candidates[:15]:
            analysis = BuySellAnalysis(code=stock.code, name=stock.name)

            # 核心价格
            base_price = getattr(stock, 'close_price', 10.0)
            limit_up_price = getattr(stock, 'limit_up_price', base_price * 1.1)

            analysis.ideal_buy_price = round(base_price * 0.985, 2)
            analysis.buy_range_low = round(base_price * 0.97, 2)
            analysis.buy_range_high = round(limit_up_price, 2)
            analysis.stop_loss_price = round(base_price * 0.93, 2)
            analysis.take_profit_short = round(base_price * 1.08, 2)
            analysis.take_profit_long = round(base_price * 1.20, 2)

            # 买入意愿计算
            buy_score = 0
            # 评分贡献
            score = getattr(stock, 'score', 0)
            if score >= 85: buy_score += 35
            elif score >= 75: buy_score += 25
            elif score >= 65: buy_score += 15
            else: buy_score += 5

            # 早盘封板加分
            if getattr(stock, 'is_morning_seal', False):
                buy_score += 20
                analysis.buy_signals.append("✅ 早盘封板，主力坚决")

            # 零开板
            if getattr(stock, 'open_count', 0) == 0:
                buy_score += 15
                analysis.buy_signals.append("✅ 零开板，封板牢固")

            # 健康换手
            turnover = getattr(stock, 'turnover_rate', 0)
            if 5 <= turnover <= 15:
                buy_score += 10
                analysis.buy_signals.append(f"✅ 换手率{turnover:.1f}%健康")

            # 封单充足
            seal_amt = getattr(stock, 'seal_amount', 0)
            if seal_amt >= 5000:
                buy_score += 10
                analysis.buy_signals.append(f"✅ 封单{(seal_amt/10000):.1f}亿，资金认可")

            # 板块效应
            sector = getattr(stock, 'sector', '') or ''
            if sector_counts.get(sector, 0) >= 3:
                buy_score += 10
                analysis.buy_signals.append(f"✅ {sector}板块效应明显")

            # 龙头加分
            if any(l.code == stock.code for l in report.leader_stocks):
                buy_score += 15
                analysis.buy_signals.append("✅ 板块龙头")

            # 情绪阶段调整
            phase = report.sentiment_phase
            if phase in ("冰点期", "退潮期"):
                buy_score = int(buy_score * 0.5)
            elif phase == "高潮期":
                buy_score = int(buy_score * 0.7)

            analysis.buy_willingness = min(100, buy_score)

            # 卖出意愿计算
            sell_score = 0
            consecutive = getattr(stock, 'consecutive_days', 0)
            if consecutive >= 5:
                sell_score += 40
                analysis.sell_signals.append("⚠️ 高位连板(≥5)，追高风险极大")
            elif consecutive >= 3:
                sell_score += 20
                analysis.sell_signals.append(f"⚠️ {consecutive}连板有一定回调风险")

            if turnover > 25:
                sell_score += 20
                analysis.sell_signals.append(f"⚠️ 换手率{turnover:.1f}%异常偏高")

            open_count = getattr(stock, 'open_count', 0)
            if open_count >= 2:
                sell_score += 20
                analysis.sell_signals.append(f"⚠️ 开板{open_count}次，分歧较大")

            if seal_amt < 500:
                sell_score += 15
                analysis.sell_signals.append("⚠️ 封单不足500万")

            analysis.sell_willingness = min(100, sell_score)

            # 入场策略
            if analysis.buy_willingness >= 70:
                analysis.entry_strategy = "竞价高开3%以内可直接参与，分两批建仓"
            elif analysis.buy_willingness >= 50:
                analysis.entry_strategy = "等待回调至买入区间低吸，控制仓位"
            else:
                analysis.entry_strategy = "观望为主，等待更明确信号"

            # 出场策略
            if analysis.sell_willingness >= 50:
                analysis.exit_strategy = "建议减仓或清仓，不确定性较高"
            else:
                analysis.exit_strategy = f"止损{analysis.stop_loss_price}，短线止盈{analysis.take_profit_short}"

            results.append(analysis)

        results.sort(key=lambda x: x.buy_willingness, reverse=True)
        return results[:10]

    # ============================================================
    #  2. 短中长期投资建议
    # ============================================================

    def _generate_term_advices(self, report) -> list[TermAdvice]:
        advices = []
        phase = report.sentiment_phase
        heat = report.sentiment_index

        # 短线建议
        short_action, short_conf = self._term_logic(phase, "short")
        advices.append(TermAdvice(
            term="short", label="短线 (1-3天)",
            action=short_action,
            confidence=short_conf,
            target_return_pct=5.0,
            hold_days="1-3个交易日",
            strategy_desc=(
                "追涨停板做隔日溢价，早盘封板优先，尾盘板回避"
                if short_action == "买入" else
                "控制仓位，减少短线操作频率" if short_action == "减仓" else
                "持有强势标的，设置移动止盈"
            ),
            risk_level="medium" if short_action == "买入" else "high",
            key_levels=["涨停板溢价空间3%-5%", "止损线: 买入价-3%"],
        ))

        # 中线建议
        mid_action, mid_conf = self._term_logic(phase, "mid")
        advices.append(TermAdvice(
            term="mid", label="中线 (1-2周)",
            action=mid_action,
            confidence=mid_conf,
            target_return_pct=10.0,
            hold_days="5-10个交易日",
            strategy_desc=(
                "板块轮动为主，关注龙头股5日线低吸机会"
                if mid_action == "买入" else
                "保持现有仓位，不加仓，注意止盈" if mid_action == "减仓" else
                "波段操作，高抛低吸"
            ),
            risk_level="medium",
            key_levels=["MA5支撑位", "MA20趋势线", "前高压力位"],
        ))

        # 长线建议
        long_action = "持有" if heat >= 40 else "减仓"
        long_conf = "高" if heat >= 50 else "中"
        advices.append(TermAdvice(
            term="long", label="长线 (1月+)",
            action=long_action,
            confidence=long_conf,
            target_return_pct=20.0,
            hold_days="1-3个月",
            strategy_desc=(
                "关注大基金重仓方向和基本面改善标的，分批建仓"
                if heat >= 40 else
                "市场偏弱，长线资金暂不入场，等待右侧信号"
            ),
            risk_level="low" if heat >= 40 else "medium",
            key_levels=["MA60支撑位", "历史估值分位数", "机构持仓变化"],
        ))

        return advices

    def _term_logic(self, phase: str, term: str) -> Tuple[str, str]:
        """根据市场阶段判断各周期策略（动作统一为：买入/持有/减仓/清仓）"""
        if phase == "冰点期":
            return ("买入", "中") if term == "short" else ("持有", "中")
        elif phase == "启动期":
            return ("买入", "高") if term in ("short", "mid") else ("买入", "中")
        elif phase == "发酵期":
            return ("买入", "高") if term in ("short", "mid") else ("持有", "高")
        elif phase == "高潮期":
            return ("减仓", "中") if term == "short" else ("持有", "中")
        elif phase == "退潮期":
            return ("清仓", "高") if term == "short" else ("减仓", "高")
        return ("持有", "中")

    # ============================================================
    #  3. 板块轮动分析
    # ============================================================

    def _analyze_sector_rotation(
        self, report, fund_analysis
    ) -> SectorRotationAnalysis:
        rotation = SectorRotationAnalysis()

        # 当日热点板块
        hot_sectors = report.sector_hot[:10] if hasattr(report, 'sector_hot') else []
        rotation.hot_sectors = [
            {"name": s, "count": c, "status": "hot"}
            for s, c in hot_sectors
        ]

        # 资金流向板块
        if fund_analysis:
            inflow = getattr(fund_analysis, 'hot_sectors_inflow', []) or []
            rotation.institution_focus = [
                s.get("name", "") for s in inflow[:5]
            ]
            outflow = getattr(fund_analysis, 'hot_sectors_outflow', []) or []
            rotation.cooling_sectors = [
                {"name": s.get("name", ""),
                 "net_outflow": abs(s.get("net_inflow", 0)),
                 "status": "cooling"}
                for s in outflow[:5]
            ]

        # 历史胜率高的板块作为潜在轮动方向
        try:
            stats = self.win_tracker.compute_stats()
            high_win = [
                (s, d) for s, d in stats.by_sector.items()
                if d["total"] >= 3 and d["rate"] >= 60
            ]
            high_win.sort(key=lambda x: x[1]["rate"], reverse=True)
            existing_hot = {s[0] for s in hot_sectors}
            rotation.next_potential_sectors = [
                {"name": s, "historical_win_rate": d["rate"],
                 "reason": f"历史胜率{d['rate']:.0f}%，样本{d['total']}笔"}
                for s, d in high_win[:5]
                if s not in existing_hot
            ]
        except Exception as e:
            logger.debug("板块轮动下一潜力推荐构建失败: %s", e)

        # 游资关注方向
        if hot_sectors:
            rotation.hot_money_focus = [
                s for s, c in hot_sectors[:3] if c >= 3
            ]

        # 轮动阶段判断
        hot_count = len(hot_sectors)
        if hot_count >= 10:
            rotation.rotation_phase = "加速期"
            rotation.rotation_score = 80
            rotation.suggestions = [
                "板块全面开花，注意高位分化风险",
                "优先持有最强板块龙头",
                "警惕高位板块一日游"
            ]
        elif hot_count >= 5:
            rotation.rotation_phase = "轮动期"
            rotation.rotation_score = 60
            rotation.suggestions = [
                "板块有序轮动，保持组合分散化",
                "关注资金从高估值流向低估值板块",
                "适当布局潜在轮动方向"
            ]
        elif hot_count >= 2:
            rotation.rotation_phase = "收缩期"
            rotation.rotation_score = 35
            rotation.suggestions = [
                "热点收缩，聚焦少数强势板块",
                "避免追涨杀跌",
                "关注防御性板块"
            ]
        else:
            rotation.rotation_phase = "冰点期"
            rotation.rotation_score = 15
            rotation.suggestions = [
                "无明显热点，空仓或轻仓观望",
                "等待新主线出现"
            ]

        return rotation

    # ============================================================
    #  4. 整体风险等级评估
    # ============================================================

    def _assess_overall_risk(
        self, report, fund_analysis, candidates
    ) -> RiskAssessment:
        risk = RiskAssessment()

        # 市场风险 (基于情绪、涨停数等)
        phase = report.sentiment_phase
        if phase == "退潮期":
            risk.market_risk = 80
        elif phase == "高潮期":
            risk.market_risk = 60
            risk.risk_factors.append("市场情绪过热，警惕高位回落")
        elif phase == "冰点期":
            risk.market_risk = 70
            risk.risk_factors.append("市场处于冰点，流动性不足")
        else:
            risk.market_risk = 40

        # 情绪风险
        heat = report.sentiment_index
        if heat >= 80:
            risk.sentiment_risk = 75
            risk.risk_factors.append(f"市场情绪过热({heat})，一致性风险")
        elif heat <= 20:
            risk.sentiment_risk = 70
            risk.risk_factors.append(f"市场情绪冰点({heat})，悲观踩踏风险")
        else:
            risk.sentiment_risk = 40

        # 板块集中度风险
        sectors = [getattr(s, 'sector', '') for s in candidates if getattr(s, 'sector', '')]
        if sectors:
            from collections import Counter
            top_sector_pct = Counter(sectors).most_common(1)[0][1] / len(sectors) * 100
            if top_sector_pct > 60:
                risk.sector_concentration_risk = 70
                risk.risk_factors.append(f"涨停股高度集中在少数板块({top_sector_pct:.0f}%)")
            elif top_sector_pct > 40:
                risk.sector_concentration_risk = 45
            else:
                risk.sector_concentration_risk = 25

        # 流动性风险（基于样本换手率分布）
        turnovers = [getattr(s, 'turnover_rate', 0) for s in candidates if getattr(s, 'turnover_rate', 0) > 0]
        if turnovers:
            avg_turnover = sum(turnovers) / len(turnovers)
            high_turnover_ratio = sum(1 for t in turnovers if t > 25) / len(turnovers)
            if avg_turnover > 20 or high_turnover_ratio > 0.4:
                risk.liquidity_risk = 65
                risk.risk_factors.append(f"整体换手偏高(avg={avg_turnover:.1f}%)，流动性换手风险")
            elif avg_turnover < 3:
                risk.liquidity_risk = 60
                risk.risk_factors.append(f"换手过低(avg={avg_turnover:.1f}%)，流动性枯竭风险")
            elif avg_turnover > 12:
                risk.liquidity_risk = 35
            else:
                risk.liquidity_risk = 20

        # 仓位风险（基于建议仓位反推，仓位越高风险越大）
        target_pos = self.PHASE_POSITION_MAP.get(
            report.sentiment_phase, {"target": 30, "max": 50}
        ).get("target", 30)
        if target_pos > 50:
            risk.position_risk = 60
        elif target_pos > 30:
            risk.position_risk = 40
        elif target_pos > 15:
            risk.position_risk = 25
        else:
            risk.position_risk = 15

        # 资金风险
        if fund_analysis:
            fund_sentiment = getattr(fund_analysis, 'fund_sentiment', '中性')
            if fund_sentiment == "谨慎":
                risk.risk_factors.append("资金情绪偏谨慎，减少操作")
                risk.market_risk = min(100, risk.market_risk + 15)
            hot_money = getattr(fund_analysis, 'hot_money_active', False)
            if hot_money:
                risk.risk_factors.append("游资活跃，市场情绪化严重")

        # 计算综合风险
        risk.overall_risk_score = int(
            risk.market_risk * 0.3 +
            risk.sentiment_risk * 0.25 +
            risk.sector_concentration_risk * 0.2 +
            risk.liquidity_risk * 0.15 +
            risk.position_risk * 0.1
        )

        if risk.overall_risk_score >= 70:
            risk.overall_risk_level = "high"
        elif risk.overall_risk_score >= 40:
            risk.overall_risk_level = "medium"
        else:
            risk.overall_risk_level = "low"

        # 风险应对
        if risk.overall_risk_level == "high":
            risk.max_recommended_position = 15.0
            risk.risk_mitigations = [
                "总仓位控制在15%以下",
                "仅参与最强标的，严格止损",
                "盘中跌破止损线立即执行",
                "关注VIX/恐慌指数变化",
            ]
        elif risk.overall_risk_level == "medium":
            risk.max_recommended_position = 40.0
            risk.risk_mitigations = [
                "总仓位控制在40%以内",
                "分散持仓不少于3个板块",
                "设置移动止盈保护利润",
            ]
        else:
            risk.max_recommended_position = 70.0
            risk.risk_mitigations = [
                "可适度加大仓位至70%",
                "保持核心+卫星配置",
                "关注趋势延续信号",
            ]

        return risk

    # ============================================================
    #  5. 个股风险剖析
    # ============================================================

    def _analyze_individual_stocks(
        self, candidates, report
    ) -> list[IndividualStockRisk]:
        results = []

        for stock in candidates[:12]:
            risk = IndividualStockRisk(code=stock.code, name=stock.name)

            score = getattr(stock, 'score', 0)
            consecutive = getattr(stock, 'consecutive_days', 0)
            turnover = getattr(stock, 'turnover_rate', 0)
            open_count = getattr(stock, 'open_count', 0)
            seal_amt = getattr(stock, 'seal_amount', 0)

            # 技术面风险
            if consecutive >= 5:
                risk.technical_risk = 80
                risk.risk_items.append({"type": "技术面", "level": "high", "desc": f"{consecutive}连板高位，超买严重"})
            elif consecutive >= 3:
                risk.technical_risk = 50
                risk.risk_items.append({"type": "技术面", "level": "medium", "desc": f"{consecutive}连板需要谨慎"})
            else:
                risk.technical_risk = 20

            if open_count >= 3:
                risk.technical_risk = max(risk.technical_risk, 75)
                risk.risk_items.append({"type": "技术面", "level": "high", "desc": f"开板{open_count}次，主力分歧大"})

            # 资金面风险
            if turnover > 30:
                risk.fund_flow_risk = 70
                risk.risk_items.append({"type": "资金面", "level": "high", "desc": f"换手率{turnover:.0f}%异常，游资对倒嫌疑"})
            elif turnover > 20:
                risk.fund_flow_risk = 40
            else:
                risk.fund_flow_risk = 15

            if seal_amt < 500:
                risk.fund_flow_risk = max(risk.fund_flow_risk, 60)
                risk.risk_items.append({"type": "资金面", "level": "medium", "desc": f"封单仅{seal_amt:.0f}万，信心不足"})

            # 流动性风险
            if turnover < 3:
                risk.liquidity_risk = 50
                risk.risk_items.append({"type": "流动性", "level": "medium", "desc": "换手率过低，流动性差"})

            # 板块风险
            sector = getattr(stock, 'sector', '') or ''
            if sector and "ST" in sector.upper():
                risk.sector_risk = 85
                risk.risk_items.append({"type": "板块", "level": "high", "desc": "ST板块高风险"})

            # 估值风险（基于连板数、评分推测）
            if consecutive >= 4 and score < 70:
                risk.valuation_risk = 75
                risk.risk_items.append({"type": "估值", "level": "high", "desc": "连板炒作脱离基本面，估值严重偏高"})
            elif consecutive >= 3:
                risk.valuation_risk = 50
                risk.risk_items.append({"type": "估值", "level": "medium", "desc": "连续涨停后估值偏离合理区间"})
            elif score >= 85:
                risk.valuation_risk = 20
            else:
                risk.valuation_risk = 35

            # 黑天鹅风险（基于市场阶段和连板高度综合判定）
            phase = report.sentiment_phase
            if phase == "退潮期" and consecutive >= 3:
                risk.black_swan_risk = 80
                risk.risk_items.append({"type": "黑天鹅", "level": "high", "desc": "退潮期+高位连板，黑天鹅风险极高"})
            elif phase == "冰点期":
                risk.black_swan_risk = 60
                risk.risk_items.append({"type": "黑天鹅", "level": "medium", "desc": "冰点期市场脆弱，黑天鹅事件冲击大"})
            elif phase == "高潮期" and consecutive >= 5:
                risk.black_swan_risk = 55
                risk.risk_items.append({"type": "黑天鹅", "level": "medium", "desc": "过度炒作标的，黑天鹅冲击下首当其冲"})
            else:
                risk.black_swan_risk = 20

            # 情绪面风险
            if phase in ("退潮期", "冰点期"):
                risk.sentiment_risk = 70
            elif phase == "高潮期":
                risk.sentiment_risk = 50
            else:
                risk.sentiment_risk = 25

            # 综合评分
            risk.risk_score = int(
                risk.technical_risk * 0.3 +
                risk.fund_flow_risk * 0.3 +
                risk.sentiment_risk * 0.2 +
                risk.sector_risk * 0.1 +
                risk.liquidity_risk * 0.1
            )

            if risk.risk_score >= 60:
                risk.risk_level = "high"
            elif risk.risk_score >= 35:
                risk.risk_level = "medium"
            else:
                risk.risk_level = "low"

            # 仓位限制
            if risk.risk_level == "high":
                risk.position_limit_pct = 5.0
                risk.suggestions = ["高风险标的，严格控制仓位≤5%", "设置硬止损-3%", "盘中密切跟踪"]
            elif risk.risk_level == "medium":
                risk.position_limit_pct = 15.0
                risk.suggestions = ["中等风险，仓位≤15%", "设置移动止盈", "关注次日集合竞价"]
            else:
                risk.position_limit_pct = 25.0
                risk.suggestions = ["低风险标的，可适度持仓", "关注趋势延续", "MA5上方持有"]

            results.append(risk)

        results.sort(key=lambda x: x.risk_score, reverse=True)
        return results

    # ============================================================
    #  6. 动态仓位管理
    # ============================================================

    def _manage_dynamic_position(
        self, report, candidates, portfolio_positions=None
    ) -> DynamicPosition:
        position = DynamicPosition()

        phase = report.sentiment_phase
        phase_config = self.PHASE_POSITION_MAP.get(phase, {"target": 30, "max": 50})

        position.target_position_pct = phase_config["target"]
        position.max_position_pct = phase_config["max"]

        # 胜率趋势调整
        try:
            stats = self.win_tracker.compute_stats()
            if stats.trend == "improving" and stats.rolling_win_rate_10 >= 60:
                position.target_position_pct = min(
                    position.max_position_pct,
                    position.target_position_pct * 1.2,
                )
                position.adjustment_reason = "胜率上升趋势，适度提高仓位"
                position.rebalancing_needed = True
            elif stats.trend == "declining":
                position.target_position_pct = position.target_position_pct * 0.6
                position.adjustment_reason = "胜率下降趋势，主动降低仓位"
                position.rebalancing_needed = True
        except Exception as e:
            logger.debug("仓位动态调整失败: %s", e)

        # 个股权重分配（基于买入意愿和风险）
        try:
            from src.seal_plate.recommender import RecommendationEngine
            engine = RecommendationEngine()
            recs = engine.generate_recommendations(report) if hasattr(engine, 'generate_recommendations') else None

            if recs and recs.recommendations:
                recs.recommendations.sort(key=lambda r: r.score, reverse=True)
                top_recs = recs.recommendations[:5]
                total_score = sum(r.score for r in top_recs) or 1

                for i, rec in enumerate(top_recs):
                    weight = (rec.score / total_score) * position.target_position_pct
                    position.stock_weights.append({
                        "code": rec.stock.code,
                        "name": rec.stock.name,
                        "weight_pct": round(weight, 1),
                        "suggested_pct": rec.suggested_position_pct,
                        "confidence": rec.confidence,
                    })
        except Exception as e:
            logger.warning("推荐引擎生成个股权重失败: %s，使用简单均分", e)
            # Fallback: 基于 candidates 的评分简单均分
            sorted_candidates = sorted(candidates, key=lambda s: getattr(s, 'score', 0), reverse=True)[:5]
            total_score = sum(getattr(s, 'score', 50) for s in sorted_candidates) or 1
            for s in sorted_candidates:
                weight = (getattr(s, 'score', 50) / total_score) * position.target_position_pct
                position.stock_weights.append({
                    "code": s.code,
                    "name": s.name,
                    "weight_pct": round(weight, 1),
                    "suggested_pct": round(weight * 0.8, 1),
                    "confidence": "中",
                })

        position.cash_reserve_pct = 100 - position.target_position_pct
        # 修正: current_position_pct 不应被硬编码为100，应从实际持仓数据计算
        # 默认使用 target 作为当前仓位（无实际持仓数据时的合理假设）
        position.current_position_pct = round(position.target_position_pct, 1)

        return position

    def remove_stock_weight(self, position: DynamicPosition, code: str) -> bool:
        """从动态仓位配置中移除指定标的

        Args:
            position: 动态仓位对象
            code: 要移除的股票代码

        Returns:
            True 如果成功移除，False 如果未找到
        """
        if not position or not position.stock_weights:
            return False

        original_len = len(position.stock_weights)
        position.stock_weights = [
            w for w in position.stock_weights
            if w.get("code", "") != code
        ]
        removed = len(position.stock_weights) < original_len

        if removed and position.stock_weights:
            # 重新分配权重：将移除标的的权重按比例分配给剩余标的
            total_weight = sum(w.get("weight_pct", 0) for w in position.stock_weights)
            if total_weight > 0:
                for w in position.stock_weights:
                    w["weight_pct"] = round(
                        (w["weight_pct"] / total_weight) * position.target_position_pct, 1
                    )

        if removed and not position.stock_weights:
            # 所有标的均被移除，重置为默认
            position.target_position_pct = position.max_position_pct * 0.6
            position.cash_reserve_pct = 100 - position.target_position_pct
            position.rebalancing_needed = True
            position.adjustment_reason = "所有配置标的已移除，仓位重置为默认值"

        return removed

    # ============================================================
    #  7. 多因子相关性监控
    # ============================================================

    def _monitor_factor_correlations(self, report) -> list[FactorCorrelation]:
        factors = []

        # 因子1: 情绪-涨停比
        heat = report.sentiment_index
        limit_up = report.total_limit_up or 0
        if limit_up > 0:
            ratio = heat / max(limit_up, 1) * 100
            f1 = FactorCorrelation(
                factor_name="情绪/涨停比",
                current_value=round(ratio, 2),
                z_score=round((ratio - 50) / 25, 2),
                correlation_with_market=0.65,
            )
            if ratio > 80:
                f1.status = "warning"
                f1.warning_msg = "情绪溢价过高，涨停数量跟不上情绪"
            factors.append(f1)

        # 因子2: 封板率质量
        top_stocks = list(report.strong_stocks)[:20] if report.strong_stocks else []
        if top_stocks:
            morning_seal_ratio = sum(
                1 for s in top_stocks if getattr(s, 'is_morning_seal', False)
            ) / len(top_stocks) * 100
            f2 = FactorCorrelation(
                factor_name="早盘封板率",
                current_value=round(morning_seal_ratio, 1),
                z_score=round((morning_seal_ratio - 50) / 20, 2),
                correlation_with_market=0.45,
            )
            if morning_seal_ratio < 30:
                f2.status = "warning"
                f2.warning_msg = "早盘封板率低于30%，资金犹豫"
            factors.append(f2)

        # 因子3: 连板高度
        consecutive_values = [
            getattr(s, 'consecutive_days', 1) for s in report.strong_stocks
        ] if report.strong_stocks else [1]
        avg_consecutive = sum(consecutive_values) / len(consecutive_values)
        f3 = FactorCorrelation(
            factor_name="平均连板高度",
            current_value=round(avg_consecutive, 1),
            z_score=round((avg_consecutive - 2) / 1.5, 2),
            correlation_with_market=0.35,
        )
        if avg_consecutive >= 4:
            f3.status = "warning"
            f3.warning_msg = "平均连板过高，行情可能过热"
        factors.append(f3)

        return factors

    # ============================================================
    #  8. 压力测试
    # ============================================================

    def _run_stress_tests(
        self, candidates, risk_assessment: RiskAssessment
    ) -> list[StressTestResult]:
        results = []

        # 场景1: 市场回调5%
        results.append(StressTestResult(
            scenario="市场回调5%",
            max_drawdown_pct=5.0,
            portfolio_loss_pct=round(risk_assessment.overall_risk_score * 0.15, 1),
            recovery_days_est=10,
            circuit_breaker_triggered=risk_assessment.overall_risk_score >= 60,
            circuit_breaker_level="yellow" if risk_assessment.overall_risk_score >= 60 else "none",
            suggested_action="减仓至目标仓位50%，增加现金比例",
        ))

        # 场景2: 板块集体跌停
        results.append(StressTestResult(
            scenario="板块集体跌停(极端行情)",
            max_drawdown_pct=10.0,
            portfolio_loss_pct=round(risk_assessment.overall_risk_score * 0.25, 1),
            recovery_days_est=30,
            circuit_breaker_triggered=True,
            circuit_breaker_level="red",
            suggested_action="立即清仓，转入货币基金避险，等待市场企稳信号",
        ))

        # 场景3: 黑天鹅事件
        results.append(StressTestResult(
            scenario="黑天鹅事件(系统性风险)",
            max_drawdown_pct=20.0,
            portfolio_loss_pct=round(risk_assessment.overall_risk_score * 0.4, 1),
            recovery_days_est=90,
            circuit_breaker_triggered=True,
            circuit_breaker_level="black",
            suggested_action="全面清仓，现金为王，等待政策托底信号",
        ))

        return results

    # ============================================================
    #  9. 胜率回溯 + 策略调整
    # ============================================================

    def _compute_win_rate_backtest(self) -> dict:
        """计算胜率回溯"""
        try:
            stats = self.win_tracker.compute_stats()
            return {
                "total": stats.total_recommendations,
                "settled": stats.settled,
                "won": stats.won,
                "lost": stats.lost,
                "pending": stats.pending,
                "win_rate": stats.win_rate,
                "avg_return": stats.avg_return,
                "rolling_10": stats.rolling_win_rate_10,
                "trend": stats.trend,
                "by_sector": {
                    s: {"won": d["won"], "total": d["total"], "rate": d["rate"]}
                    for s, d in sorted(
                        stats.by_sector.items(),
                        key=lambda x: x[1]["rate"], reverse=True
                    )[:10]
                },
            }
        except Exception as e:
            logger.warning("胜率回溯计算失败: %s", e)
            return {}

    def _generate_strategy_adjustments(
        self, result: ComprehensiveRecommendation
    ) -> Tuple[list[str], list[str]]:
        adjustments = []
        reasons = []

        risk = result.risk_assessment
        if risk:
            if risk.overall_risk_level == "high":
                adjustments.append("⚠️ 整体风险较高，仓位降至15%以下")
                reasons.append(f"风险评分{risk.overall_risk_score}")
            elif risk.overall_risk_level == "low":
                adjustments.append("✅ 整体风险可控，可适度加仓至70%")
                reasons.append("各风险维度正常")

        win_rate = result.win_rate_info
        if win_rate:
            trend = win_rate.get("trend", "stable")
            if trend == "declining":
                adjustments.append("📉 胜率下降趋势，暂停新开仓")
                reasons.append(f"近10笔胜率{win_rate.get('rolling_10', 0)}%")
            elif trend == "improving":
                adjustments.append("📈 胜率上升趋势，可增加参与度")
                reasons.append(f"近10笔胜率{win_rate.get('rolling_10', 0)}%")

        # 板块轮动建议
        rotation = result.sector_rotation
        if rotation and rotation.rotation_phase in ("收缩期", "冰点期"):
            adjustments.append("防防御为主，减少板块轮动操作")
            reasons.append(f"当前轮动阶段: {rotation.rotation_phase}")

        # 熔断建议
        stress = result.stress_test_results
        if stress:
            black_swan = next((s for s in stress if s.circuit_breaker_level == "black"), None)
            if black_swan:
                adjustments.append(f"🛑 黑天鹅熔断线: 亏损{black_swan.portfolio_loss_pct}%即清仓")

        return adjustments, reasons
