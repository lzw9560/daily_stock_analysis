# -*- coding: utf-8 -*-
"""
===================================
API v1 路由聚合
===================================

职责：
1. 聚合 v1 版本的所有 endpoint 路由
2. 统一添加 /api/v1 前缀
"""

from fastapi import APIRouter

from api.v1.endpoints import alerts, analysis, auth, health, history, stocks, backtest, system_config, agent, usage, portfolio, seal_plate, position_monitor, alphasift, comprehensive_recommend, recommendation_tracking, screening, deep_analysis, strategy_optimizer

# 创建 v1 版本主路由
router = APIRouter(prefix="/api/v1")

router.include_router(
    health.router,
    tags=["Health"]
)

router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Auth"]
)

router.include_router(
    agent.router,
    prefix="/agent",
    tags=["Agent"]
)

router.include_router(
    analysis.router,
    prefix="/analysis",
    tags=["Analysis"]
)

router.include_router(
    history.router,
    prefix="/history",
    tags=["History"]
)

router.include_router(
    stocks.router,
    prefix="/stocks",
    tags=["Stocks"]
)

router.include_router(
    backtest.router,
    prefix="/backtest",
    tags=["Backtest"]
)

router.include_router(
    system_config.router,
    prefix="/system",
    tags=["SystemConfig"]
)

router.include_router(
    usage.router,
    prefix="/usage",
    tags=["Usage"]
)

router.include_router(
    portfolio.router,
    prefix="/portfolio",
    tags=["Portfolio"]
)

router.include_router(
    seal_plate.router,
    prefix="/seal-plate",
    tags=["SealPlate"]
)

router.include_router(
    position_monitor.router,
    tags=["PositionMonitor"]
)

router.include_router(
    alerts.router,
    prefix="/alerts",
    tags=["Alerts"]
)

router.include_router(
    alphasift.router,
    prefix="/alphasift",
    tags=["AlphaSift"]
)

router.include_router(
    comprehensive_recommend.router,
    prefix="/comprehensive",
    tags=["Comprehensive"]
)

router.include_router(
    screening.router,
    prefix="/screening",
    tags=["Screening"]
)

router.include_router(
    deep_analysis.router,
    prefix="/deep-analysis",
    tags=["DeepAnalysis"]
)

router.include_router(
    recommendation_tracking.router,
    prefix="/recommendation-tracking",
    tags=["RecommendationTracking"]
)

router.include_router(
    strategy_optimizer.router,
    prefix="/strategy-optimizer",
    tags=["StrategyOptimizer"]
)
