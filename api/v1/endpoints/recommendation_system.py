# -*- coding: utf-8 -*-
"""
推荐系统页面 API 端点.

为10个推荐页面分别提供独立的数据端点，数据来源于
StockDaily 表 + 实时计算指标。
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter

from api.v1.schemas.recommendation_system import (
    MarketTrendResponse,
    DailyReviewResponse,
    CapitalFlowResponse,
    ShortTermTargetsResponse,
    MidLongTermResponse,
    RiskControlResponse,
    ThemeMiningResponse,
    LimitUpLadderResponse,
    MultiFactorBacktestResponse,
    PositionAdviceResponse,
    IndexItem, TrendSeries,
    DailyStats, LhbItem, SectorLeader,
    MoneyFlowItem, NorthBoundItem, SectorRotationItem,
    ShortTermTarget,
    MidLongTermPosition, StrategyType,
    SectorRisk, PositionRiskItem,
    ThemeItem,
    LadderItem, EmotionCycle, EmotionHistoryItem,
    FactorItem, NavItem,
    PortfolioItem,
    BlockTradeItem, BlockTradeSummary,
)
from src.services.recommendation_system_service import RecommendationSystemService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["推荐系统"])


# ── 1. 大盘走势 ──────────────────────────────────────────────────────────────


@router.get("/market-trend", response_model=MarketTrendResponse)
def get_market_trend() -> Dict[str, Any]:
    """大盘走势 — 指数行情、均线趋势、涨跌统计、成交额."""
    service = RecommendationSystemService()
    result = service.get_market_trend()

    return MarketTrendResponse(
        trade_date=result["trade_date"],
        indices=[IndexItem(**i) for i in result["indices"]],
        trend=TrendSeries(**result["trend"]),
        up_count=result["up_count"],
        down_count=result["down_count"],
        total_amount=result["total_amount"],
        limit_up_count=result["limit_up_count"],
        limit_down_count=result.get("limit_down_count", 0),
        data_source=result.get("data_source", "db"),
        is_realtime=result.get("is_realtime", False),
        data_available=result.get("data_available", True),
    ).model_dump()


# ── 2. 每日复盘 ──────────────────────────────────────────────────────────────


@router.get("/daily-review", response_model=DailyReviewResponse)
def get_daily_review() -> Dict[str, Any]:
    """每日复盘 — 涨跌家数统计、龙虎榜、领涨板块."""
    service = RecommendationSystemService()
    result = service.get_daily_review()

    block_trade = result.get("block_trade")
    bt_obj = None
    if block_trade:
        bt_obj = BlockTradeSummary(
            today_count=block_trade.get("today_count", 0),
            total_amount=block_trade.get("total_amount"),
            top_premium=[BlockTradeItem(**p) for p in block_trade.get("top_premium", [])],
            top_discount=[BlockTradeItem(**d) for d in block_trade.get("top_discount", [])],
        )
    return DailyReviewResponse(
        trade_date=result["trade_date"],
        stats=DailyStats(**result["stats"]),
        lhb_top=[LhbItem(**l) for l in result["lhb_top"]],
        block_trade=bt_obj,
        sector_leaders=[SectorLeader(**s) for s in result["sector_leaders"]],
        data_source=result.get("data_source", "db"),
        is_realtime=result.get("is_realtime", False),
        data_available=result.get("data_available", True),
    ).model_dump()


# ── 3. 资金与板块热点 ────────────────────────────────────────────────────────


@router.get("/capital-flow", response_model=CapitalFlowResponse)
def get_capital_flow() -> Dict[str, Any]:
    """资金与板块热点 — 板块资金流向、北向资金、板块轮动."""
    service = RecommendationSystemService()
    result = service.get_capital_flow()

    return CapitalFlowResponse(
        trade_date=result["trade_date"],
        money_flow=[MoneyFlowItem(**m) for m in result["money_flow"]],
        north_bound=[NorthBoundItem(**n) for n in result["north_bound"]],
        sector_rotation=[SectorRotationItem(**s) for s in result["sector_rotation"]],
        total_inflow=result["total_inflow"],
        total_outflow=result["total_outflow"],
        today_north_bound=result["today_north_bound"],
        total_amount=result["total_amount"],
        data_available=result.get("data_available", True),
    ).model_dump()


# ── 4. 短线打板标的 ──────────────────────────────────────────────────────────


@router.get("/short-term", response_model=ShortTermTargetsResponse)
def get_short_term_targets() -> Dict[str, Any]:
    """短线打板标的 — 封板强度、溢价率与短线爆发力评估."""
    service = RecommendationSystemService()
    result = service.get_short_term_targets()

    return ShortTermTargetsResponse(
        trade_date=result["trade_date"],
        targets=[ShortTermTarget(**t) for t in result["targets"]],
        limit_up_count=result["limit_up_count"],
        data_available=result.get("data_available", True),
    ).model_dump()


# ── 5. 中长线波段建仓 ────────────────────────────────────────────────────────


@router.get("/mid-long-term", response_model=MidLongTermResponse)
def get_mid_long_term() -> Dict[str, Any]:
    """中长线波段建仓 — 趋势确认、估值分位与中线持仓逻辑."""
    service = RecommendationSystemService()
    result = service.get_mid_long_term()

    return MidLongTermResponse(
        trade_date=result["trade_date"],
        positions=[MidLongTermPosition(**p) for p in result["positions"]],
        strategies=[StrategyType(**s) for s in result["strategies"]],
    ).model_dump()


# ── 6. 风控与仓位管理 ────────────────────────────────────────────────────────


@router.get("/risk-control", response_model=RiskControlResponse)
def get_risk_control() -> Dict[str, Any]:
    """风控与仓位管理 — 个股止损止盈、动态仓位控制及系统性风险预警."""
    service = RecommendationSystemService()
    result = service.get_risk_control()

    return RiskControlResponse(
        trade_date=result["trade_date"],
        vix=result["vix"],
        margin_balance=result["margin_balance"],
        margin_change=result.get("margin_change"),
        forced_liquidation=result["forced_liquidation"],
        sector_risk=SectorRisk(**result["sector_risk"]),
        position_risks=[PositionRiskItem(**p) for p in result["position_risks"]],
        total_weight=result["total_weight"],
    ).model_dump()


# ── 7. 题材挖掘与龙头定性 ────────────────────────────────────────────────────


@router.get("/theme-mining", response_model=ThemeMiningResponse)
def get_theme_mining() -> Dict[str, Any]:
    """题材挖掘与龙头定性 — 题材溯源、热点轮动剖析与龙头股生命力评估."""
    service = RecommendationSystemService()
    result = service.get_theme_mining()

    return ThemeMiningResponse(
        trade_date=result["trade_date"],
        themes=[ThemeItem(**t) for t in result["themes"]],
        active_themes=result["active_themes"],
        total_followers=result["total_followers"],
        main_theme=result["main_theme"],
        hottest_leader=result["hottest_leader"],
        data_available=result.get("data_available", True),
    ).model_dump()


# ── 8. 连板梯队与情绪周期 ────────────────────────────────────────────────────


@router.get("/limit-up-ladder", response_model=LimitUpLadderResponse)
def get_limit_up_ladder() -> Dict[str, Any]:
    """连板梯队与情绪周期 — 打板高度监控、涨停溢价及市场情绪指标."""
    service = RecommendationSystemService()
    result = service.get_limit_up_ladder()

    emotion = result["emotion"]
    return LimitUpLadderResponse(
        trade_date=result["trade_date"],
        ladder=[LadderItem(**l) for l in result["ladder"]],
        emotion=EmotionCycle(
            phase=emotion["phase"],
            phase_desc=emotion["phase_desc"],
            sentiment_index=emotion["sentiment_index"],
            limit_up_ratio=emotion["limit_up_ratio"],
            yesterday_premium=emotion["yesterday_premium"],
            next_day_red_rate=emotion["next_day_red_rate"],
            history=[EmotionHistoryItem(**h) for h in emotion["history"]],
        ),
        total_limit_up=result["total_limit_up"],
        data_available=result.get("data_available", True),
    ).model_dump()


# ── 9. 多因子策略回测 ────────────────────────────────────────────────────────


@router.get("/multi-factor-backtest", response_model=MultiFactorBacktestResponse)
def get_multi_factor_backtest() -> Dict[str, Any]:
    """多因子策略回测 — Alpha因子IC/IR表现及策略净值曲线展示."""
    service = RecommendationSystemService()
    result = service.get_multi_factor_backtest()

    return MultiFactorBacktestResponse(
        trade_date=result.get("trade_date", ""),
        factors=[FactorItem(**f) for f in result["factors"]],
        nav_curve=[NavItem(**n) for n in result["nav_curve"]],
    ).model_dump()


# ── 10. 持仓建议 ─────────────────────────────────────────────────────────────


@router.get("/position-advice", response_model=PositionAdviceResponse)
def get_position_advice() -> Dict[str, Any]:
    """持仓建议 — 持仓优化操作、调仓信号、仓位再平衡与止盈止损."""
    service = RecommendationSystemService()
    result = service.get_position_advice()

    return PositionAdviceResponse(
        trade_date=result["trade_date"],
        portfolio=[PortfolioItem(**p) for p in result["portfolio"]],
        total_weight=result.get("total_weight", 0),
        market_sentiment_phase=result.get("market_sentiment_phase", "未知"),
        suggested_total_position=result.get("suggested_total_position", "30-50%"),
    ).model_dump()
