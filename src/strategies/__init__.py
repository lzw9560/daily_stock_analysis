# -*- coding: utf-8 -*-
"""短线交易策略注册中心（交易系统升级 Phase 2）

策略按类别组织:
- short_term/: A股特色短线战法（首板/连板/低吸/N字等）
- sector_rotation: 板块联动与主线识别
"""

from .short_term import (
    BaseShortStrategy,
    TradeSignal,
    StrategyRegistry,
    FirstBoardStrategy,
    ConsecutiveBoardStrategy,
    LowSuckLeaderStrategy,
    NPatternStrategy,
    register_all_strategies,
    scan_all_strategies,
)

from .sector_rotation import (
    SectorAnalyzer,
    SectorRank,
    SectorStrength,
    SectorFlow,
    HotTheme,
    RotationStep,
)

__all__ = [
    # Strategy framework
    "BaseShortStrategy",
    "TradeSignal",
    "StrategyRegistry",
    # Core strategies
    "FirstBoardStrategy",
    "ConsecutiveBoardStrategy",
    "LowSuckLeaderStrategy",
    "NPatternStrategy",
    # Registry helpers
    "register_all_strategies",
    "scan_all_strategies",
    # Sector analysis
    "SectorAnalyzer",
    "SectorRank",
    "SectorStrength",
    "SectorFlow",
    "HotTheme",
    "RotationStep",
]
