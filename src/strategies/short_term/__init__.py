# -*- coding: utf-8 -*-
"""短线战法模块（交易系统升级 Phase 2）

A股特色短线战法集合:
- FirstBoardStrategy: 首板挖掘
- ConsecutiveBoardStrategy: 连板接力
- LowSuckLeaderStrategy: 低吸龙头
- NPatternStrategy: N字反击
"""

from __future__ import annotations

from typing import Optional

from .base_strategy import (
    BaseShortStrategy,
    TradeSignal,
    SignalType,
    EntryMethod,
    StrategyRegistry,
)
from .first_board import FirstBoardStrategy
from .consecutive_board import ConsecutiveBoardStrategy
from .low_suck_leader import LowSuckLeaderStrategy
from .n_pattern import NPatternStrategy


def register_all_strategies():
    """注册所有短线战法到策略注册中心"""
    StrategyRegistry.clear()
    StrategyRegistry.register(FirstBoardStrategy())
    StrategyRegistry.register(ConsecutiveBoardStrategy())
    StrategyRegistry.register(LowSuckLeaderStrategy())
    StrategyRegistry.register(NPatternStrategy())
    return StrategyRegistry.list_all()


def scan_all_strategies(
    market_data: dict,
    *,
    sentiment_phase: str = "unknown",
    sentiment_score: int = 50,
    hot_sectors: "Optional[list[str]]" = None,
) -> list:
    """执行所有策略扫描，返回汇总信号列表"""
    all_signals = []
    for strategy in StrategyRegistry.list_all():
        if not strategy.is_suitable_phase(sentiment_phase):
            continue
        try:
            signals = strategy.scan(
                market_data,
                sentiment_phase=sentiment_phase,
                hot_sectors=hot_sectors,
            )
            # 情绪调整
            adjusted = [
                strategy.adjust_for_sentiment(s, sentiment_phase, sentiment_score)
                for s in signals
            ]
            # 验证
            valid = [s for s in adjusted if strategy.validate(s)]
            all_signals.extend(valid)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"策略 {strategy.display_name} 扫描失败: {e}"
            )
    # 按置信度排序
    all_signals.sort(key=lambda s: s.confidence, reverse=True)
    return all_signals


__all__ = [
    "BaseShortStrategy",
    "TradeSignal",
    "SignalType",
    "EntryMethod",
    "StrategyRegistry",
    "FirstBoardStrategy",
    "ConsecutiveBoardStrategy",
    "LowSuckLeaderStrategy",
    "NPatternStrategy",
    "register_all_strategies",
    "scan_all_strategies",
]
