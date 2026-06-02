"""
战法与推荐合并综合分析器

每日收盘后将"高胜率战法"与"推荐建仓"进行综合分析，
生成合并推荐标的，并通过飞书推送。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from .recommender import DailyRecommendationResult, PositionRecommendation
    from .dragon_tiger_risk import get_dragon_tiger_risk_factors, DragonTigerInstitutionRisk
    from .win_rate_tracker import WinRateTracker
except ImportError:
    DailyRecommendationResult = object  # type: ignore
    PositionRecommendation = object  # type: ignore
    WinRateTracker = object  # type: ignore


@dataclass
class CombinedRecommendation:
    """合并后的推荐标的"""
    code: str
    name: str
    composite_score: int              # 综合评分（0-100）
    matched_strategies: list[str]     # 匹配的战法名称列表
    strategy_count: int               # 匹配战法数量
    recommendation_score: int         # 推荐引擎评分
    confidence: str                   # 置信度（高/中/低）
    sector: Optional[str]
    reasons: list[str]
    risk_warnings: list[str]
    dragon_tiger_risk: Optional[dict] # 龙虎榜机构风险
    suggested_position_pct: float
    buy_analysis: str
    sell_analysis: str
    risk_level: str                   # low/medium/high/critical
    filter_reason: Optional[str] = None  # 过滤原因（如果被过滤）


@dataclass
class CombinedAnalysisResult:
    """合并分析结果"""
    date: str
    generated_at: str
    total_limit_up: int
    sentiment_phase: str
    sentiment_index: int
    
    # 综合推荐
    high_confidence: list[CombinedRecommendation] = field(default_factory=list)  # 多战法共振
    medium_confidence: list[CombinedRecommendation] = field(default_factory=list)  # 单战法+高评分
    watch_list: list[CombinedRecommendation] = field(default_factory=list)  # 关注列表
    
    # 过滤统计
    gem_filtered: list[dict] = field(default_factory=list)     # 创业板过滤
    risk_filtered: list[dict] = field(default_factory=list)    # 高风险过滤
    
    # 策略状态
    active_strategies: list[str] = field(default_factory=list)
    strategy_suitability: dict[str, int] = field(default_factory=dict)
    
    # 胜率快照
    win_rate: float = 0
    rolling_win_rate: float = 0
    
    # 板块分析
    focus_sectors: list[str] = field(default_factory=list)     # 重点关注板块
    avoid_sectors: list[str] = field(default_factory=list)     # 规避板块


class CombinedAnalyzer:
    """战法与推荐合并综合分析器"""
    
    # 战法定义（与 API 中的保持一致）
    STRATEGIES = {
        "second_board": {
            "name": "二板定龙战法",
            "type": "连板接力",
            "win_rate": 0.70,
            "conditions": [
                "首板封板质量≥70分",
                "二板高开3%以上",
                "前日换手率5%-15%",
                "非一字板接力",
            ],
        },
        "weak_to_strong": {
            "name": "弱转强反包战法",
            "type": "分歧转一致",
            "win_rate": 0.75,
            "conditions": [
                "前日收长上影或高开低走",
                "当日分时弱转强（早盘下跌后回升）",
                "上穿分时均线且站稳",
                "板块仍有热度支撑",
            ],
        },
        "sector_lead": {
            "name": "板块龙头接力战法",
            "type": "龙头战法",
            "win_rate": 0.65,
            "conditions": [
                "板块内最早封板的标的",
                "板块涨停家数≥3只",
                "流通市值30-200亿",
                "板块题材有持续性逻辑",
            ],
        },
        "capital_track": {
            "name": "大基金追踪战法",
            "type": "资金跟随",
            "win_rate": 0.60,
            "conditions": [
                "板块连续3日资金净流入",
                "龙虎榜有机构席位净买入",
                "流通市值>100亿",
                "避开游资主导的小盘标的",
            ],
        },
        "first_board_break": {
            "name": "首板突破战法",
            "type": "低位首板",
            "win_rate": 0.58,
            "conditions": [
                "股价处于历史低位区间",
                "突破60日/120日均线",
                "涨停成交量放大2倍以上",
                "有业绩预增或利好公告支撑",
            ],
        },
    }
    
    def __init__(self, win_tracker: "WinRateTracker | None" = None):
        self.win_tracker = win_tracker or WinRateTracker()
    
    def analyze(
        self,
        recommendation_result: "DailyRecommendationResult",
        seal_amount: float = 1000,
    ) -> CombinedAnalysisResult:
        """
        合并分析战法与推荐结果
        
        Args:
            recommendation_result: 推荐引擎的每日推荐结果
            seal_amount: 默认封单金额（用于风险估算）
        """
        recs = recommendation_result.recommendations
        
        result = CombinedAnalysisResult(
            date=recommendation_result.date,
            generated_at=datetime.now().isoformat(),
            total_limit_up=recommendation_result.total_limit_up,
            sentiment_phase=recommendation_result.sentiment_phase,
            sentiment_index=recommendation_result.sentiment_index,
            win_rate=(
                recommendation_result.win_rate_stats.win_rate
                if recommendation_result.win_rate_stats and getattr(recommendation_result.win_rate_stats, 'total', 0) > 0
                else 0
            ),
            rolling_win_rate=(
                getattr(recommendation_result.win_rate_stats, 'rolling_win_rate10', 0)
                if recommendation_result.win_rate_stats
                else 0
            ),
        )
        
        if not recs:
            logger.info("无推荐标的，跳过合并分析")
            return result
        
        # 获取策略适配度
        result.strategy_suitability = self._get_strategy_suitability(recommendation_result)
        result.active_strategies = [
            s for s, suit in result.strategy_suitability.items() if suit >= 50
        ]
        
        # 对每个推荐标的进行战法匹配
        combined = []
        for rec in recs:
            combined_rec = self._match_and_score(
                rec,
                seal_amount,
                recommendation_result,
            )
            combined.append(combined_rec)
        
        # 按综合评分分类
        for cr in combined:
            if cr.filter_reason:
                if "创业板" in cr.filter_reason:
                    result.gem_filtered.append({
                        "code": cr.code, "name": cr.name,
                        "reason": cr.filter_reason,
                    })
                else:
                    result.risk_filtered.append({
                        "code": cr.code, "name": cr.name,
                        "reason": cr.filter_reason,
                        "composite_score": cr.composite_score,
                    })
                continue
            
            if cr.strategy_count >= 2 and cr.composite_score >= 80:
                result.high_confidence.append(cr)
            elif cr.strategy_count >= 1 and cr.composite_score >= 70:
                result.medium_confidence.append(cr)
            else:
                result.watch_list.append(cr)
        
        # 板块分析
        result.focus_sectors, result.avoid_sectors = self._analyze_sectors(
            combined, recommendation_result
        )
        
        logger.info(
            "合并分析完成: 高置信%d 中置信%d 关注%d 过滤(创业板%d+风险%d) 关注板块%s 规避板块%s",
            len(result.high_confidence), len(result.medium_confidence),
            len(result.watch_list), len(result.gem_filtered), len(result.risk_filtered),
            result.focus_sectors, result.avoid_sectors,
        )
        
        return result
    
    def _match_and_score(
        self,
        rec: "PositionRecommendation",
        seal_amount: float,
        result: "DailyRecommendationResult",
    ) -> CombinedRecommendation:
        """对单个推荐标的进行战法匹配和综合评分"""
        stock = rec.stock
        score = rec.score
        confidence = rec.confidence
        sector = stock.sector if hasattr(stock, 'sector') else None
        reasons = list(rec.reasons)
        risk_warnings = list(rec.risk_warnings)
        
        # 创业板过滤
        if stock.code.startswith(("30", "301")):
            return CombinedRecommendation(
                code=stock.code, name=stock.name if hasattr(stock, 'name') else stock.code,
                composite_score=0, matched_strategies=[], strategy_count=0,
                recommendation_score=score, confidence=confidence,
                sector=sector, reasons=reasons, risk_warnings=risk_warnings,
                dragon_tiger_risk=None, suggested_position_pct=0,
                buy_analysis="", sell_analysis="",
                risk_level="critical",
                filter_reason="创业板标的，按规则自动过滤",
            )
        
        # 战法匹配
        matched = self._check_strategy_match(rec)
        
        # 龙虎榜风险分析
        dt_risk = get_dragon_tiger_risk_factors(
            code=stock.code,
            name=stock.name if hasattr(stock, 'name') else stock.code,
            score=score,
            seal_amount=getattr(stock, 'seal_amount', seal_amount),
        )
        
        # 龙虎榜风险过高 → 加入风险过滤
        if dt_risk.risk_level in ("high", "critical") and score < 85:
            return CombinedRecommendation(
                code=stock.code, name=stock.name if hasattr(stock, 'name') else stock.code,
                composite_score=score, matched_strategies=matched, strategy_count=len(matched),
                recommendation_score=score, confidence=confidence,
                sector=sector, reasons=reasons, risk_warnings=risk_warnings,
                dragon_tiger_risk={
                    "risk_score": dt_risk.risk_score,
                    "risk_level": dt_risk.risk_level,
                    "reasons": dt_risk.risk_reasons,
                    "suggestion": dt_risk.suggestion,
                },
                suggested_position_pct=0,
                buy_analysis="", sell_analysis="",
                risk_level=dt_risk.risk_level,
                filter_reason=f"龙虎榜机构风险{dt_risk.risk_level}: {dt_risk.suggestion}",
            )
        
        # 综合评分：战法匹配 30% + 推荐评分 50% + 机构确认 20%
        strategy_bonus = min(30, len(matched) * 15)
        score_component = min(50, score * 0.5)
        inst_bonus = min(20, max(0, dt_risk.institution_net_buy / 100))
        composite = int(strategy_bonus + score_component + inst_bonus)
        
        # 高胜率游资加分
        if dt_risk.risk_reasons:
            for reason in dt_risk.risk_reasons:
                if "顶级游资" in reason and "跟随价值高" in reason:
                    composite += 5
                    reasons.append(f"龙虎榜: {reason}")
        
        # 龙虎榜风险提示加入
        if dt_risk.risk_level != "low":
            for reason in dt_risk.risk_reasons:
                if reason not in risk_warnings:
                    risk_warnings.append(f"龙虎榜: {reason}")
        
        # 买卖分析
        buy_analysis = self._generate_buy_analysis(score, confidence, matched, rec)
        sell_analysis = self._generate_sell_analysis(rec, dt_risk)
        
        # 风险等级
        if dt_risk.risk_level == "critical" or dt_risk.risk_score >= 60:
            risk_level = "high"
        elif dt_risk.risk_level == "high" or dt_risk.risk_score >= 40:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        return CombinedRecommendation(
            code=stock.code,
            name=stock.name if hasattr(stock, 'name') else stock.code,
            composite_score=composite,
            matched_strategies=matched,
            strategy_count=len(matched),
            recommendation_score=score,
            confidence=confidence,
            sector=sector,
            reasons=reasons,
            risk_warnings=risk_warnings,
            dragon_tiger_risk={
                "risk_score": dt_risk.risk_score,
                "risk_level": dt_risk.risk_level,
                "reasons": dt_risk.risk_reasons,
                "suggestion": dt_risk.suggestion,
            },
            suggested_position_pct=rec.suggested_position_pct,
            buy_analysis=buy_analysis,
            sell_analysis=sell_analysis,
            risk_level=risk_level,
        )
    
    def _check_strategy_match(self, rec: "PositionRecommendation") -> list[str]:
        """检查推荐标的匹配哪些战法"""
        matched = []
        stock = rec.stock
        score = rec.score
        
        # 简化匹配逻辑（基于评分和特征）
        consecutive = getattr(stock, 'consecutive_days', 1)
        sector = getattr(stock, 'sector', '')
        seal_amount = getattr(stock, 'seal_amount', 0)
        seal_strength = getattr(stock, 'seal_strength', None)
        
        # 二板定龙：连板 + 高评分
        if consecutive >= 2 and score >= 70 and seal_amount > 2000:
            matched.append("二板定龙战法")
        
        # 板块龙头：有板块 + 高评分
        if sector and score >= 75:
            matched.append("板块龙头接力战法")
        
        # 首板突破：首板 + 中等以上评分
        if consecutive == 1 and score >= 65:
            matched.append("首板突破战法")
        
        # 资金跟随：高成交 + 高评分
        vol_attr = getattr(stock, 'volume_ratio', None)
        if vol_attr and vol_attr >= 2 and score >= 70:
            matched.append("大基金追踪战法")
        
        # 弱转强判断（基于评分+封板时间）
        seal_time = getattr(stock, 'seal_time', None)
        if score >= 70 and seal_time and "14:" in str(seal_time):
            matched.append("弱转强反包战法")
        
        return matched
    
    def _generate_buy_analysis(
        self, score: int, confidence: str,
        matched: list[str], rec: "PositionRecommendation",
    ) -> str:
        """生成买入分析"""
        parts = []
        if matched:
            if len(matched) >= 2:
                parts.append(f"✅ 多战法共振({'+'.join(matched)})，信号可靠性高")
            else:
                parts.append(f"✅ 匹配{matched[0]}，信号有据可循")
        else:
            parts.append(f"基于评分系统入选(评分{score})，需额外确认")
        
        if confidence == "高":
            parts.append("高置信度，可按建议仓位建仓")
        elif confidence == "中":
            parts.append("中等置信度，建议半仓试探")
        else:
            parts.append("低置信度，轻仓观察为主")
        
        return "；".join(parts)
    
    def _generate_sell_analysis(
        self, rec: "PositionRecommendation",
        dt_risk: "DragonTigerInstitutionRisk",
    ) -> str:
        """生成卖出分析"""
        parts = []
        
        if hasattr(rec.stock, 'seal_strength'):
            ss = rec.stock.seal_strength
            ss_str = str(ss) if ss else ""
            if "BROKEN" in ss_str or "WEAK" in ss_str:
                parts.append("⚠️ 封板质量不佳，次日若低开超2%建议止损")
        
        if dt_risk.risk_level in ("high", "critical"):
            parts.append("⚠️ 龙虎榜机构风险高，次日不创新高即离场")
        
        parts.append("止损线: -3%硬止损, -5%无条件离场")
        parts.append("目标: +5%减半仓, +10%清仓")
        
        return "；".join(parts)
    
    def _get_strategy_suitability(
        self, result: "DailyRecommendationResult"
    ) -> dict[str, int]:
        """根据市场情绪评估各战法适配度"""
        phase = result.sentiment_phase
        sentiment = result.sentiment_index
        
        base = {
            "冰点期": {"first_board_break": 80, "weak_to_strong": 60, "sector_lead": 50},
            "启动期": {"second_board": 85, "first_board_break": 75, "sector_lead": 70},
            "发酵期": {"second_board": 90, "sector_lead": 85, "capital_track": 75},
            "高潮期": {"second_board": 70, "sector_lead": 80, "capital_track": 65},
            "退潮期": {"first_board_break": 50, "capital_track": 40},
            "震荡期": {"weak_to_strong": 70, "first_board_break": 65, "sector_lead": 60},
        }
        
        phase_suits = base.get(phase, base["震荡期"])
        
        # 补充未列出的战法
        result = {
            "second_board": 50,
            "weak_to_strong": 50,
            "sector_lead": 50,
            "capital_track": 50,
            "first_board_break": 50,
        }
        result.update(phase_suits)
        
        return result
    
    def _analyze_sectors(
        self,
        combined: list[CombinedRecommendation],
        result: "DailyRecommendationResult",
    ) -> tuple[list[str], list[str]]:
        """分析板块分布"""
        from collections import Counter
        
        # 汇总所有推荐标的的板块
        sector_scores = {}
        for cr in combined:
            if cr.filter_reason or not cr.sector:
                continue
            sector = cr.sector
            if sector not in sector_scores:
                sector_scores[sector] = {"count": 0, "total_score": 0, "risks": 0}
            sector_scores[sector]["count"] += 1
            sector_scores[sector]["total_score"] += cr.composite_score
            if cr.risk_level in ("high", "critical"):
                sector_scores[sector]["risks"] += 1
        
        focus_sectors = []
        avoid_sectors = []
        
        for sector, data in sector_scores.items():
            avg_score = data["total_score"] / data["count"] if data["count"] > 0 else 0
            risk_ratio = data["risks"] / data["count"] if data["count"] > 0 else 1
            
            if data["count"] >= 2 and avg_score >= 75 and risk_ratio <= 0.3:
                focus_sectors.append(sector)
            elif risk_ratio >= 0.6 or avg_score < 60:
                avoid_sectors.append(sector)
        
        return focus_sectors, avoid_sectors
