# -*- coding: utf-8 -*-
"""
===================================
API v1 Endpoints 模块初始化
===================================

职责：
1. 声明所有 endpoint 路由模块
"""

from api.v1.endpoints import (
    health,
    analysis,
    history,
    stocks,
    backtest,
    system_config,
    auth,
    agent,
    usage,
    portfolio,
    seal_plate,
    position_monitor,
    alerts,
    alphasift,
    comprehensive_recommend,
    recommendation_tracking,
    screening,
    deep_analysis,
    strategy_optimizer,
)
__all__ = [
    "health",
    "analysis",
    "history",
    "stocks",
    "backtest",
    "system_config",
    "auth",
    "agent",
    "usage",
    "portfolio",
    "seal_plate",
    "position_monitor",
    "alerts",
    "alphasift",
    "comprehensive_recommend",
    "recommendation_tracking",
    "screening",
    "deep_analysis",
    "strategy_optimizer",
]
