# -*- coding: utf-8 -*-
"""
盘中监控策略定义

策略类型：
1. price_breakout    — 价格突破（上穿/下穿关键价位）
2. change_threshold  — 涨跌幅阈值告警
3. volume_surge      — 量比异动（放量/缩量）
4. ma_cross          — 均线交叉（暂用价格近似，实际需K线数据）
5. amplitude_alert   — 振幅异常告警
6. turnover_alert    — 换手率异常告警
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SignalType(str, Enum):
    """信号类型"""
    BUY = "buy"         # 买入信号
    SELL = "sell"       # 卖出信号
    ALERT = "alert"     # 关注信号
    WARNING = "warning" # 风险预警


class StrategyType(str, Enum):
    """策略类型枚举"""
    PRICE_BREAKOUT = "price_breakout"
    CHANGE_THRESHOLD = "change_threshold"
    VOLUME_SURGE = "volume_surge"
    MA_CROSS = "ma_cross"
    AMPLITUDE_ALERT = "amplitude_alert"
    TURNOVER_ALERT = "turnover_alert"


@dataclass
class TriggerSignal:
    """触发信号"""
    code: str
    name: str
    signal_type: SignalType
    strategy_type: StrategyType
    current_price: float
    change_pct: float
    trigger_value: float            # 触发时的指标值
    threshold: float                # 触发阈值
    message: str                    # 信号描述
    timestamp: datetime = field(default_factory=datetime.now)
    extra: Dict[str, Any] = field(default_factory=dict)  # 额外上下文


@dataclass
class StrategyConfig:
    """单条策略配置"""
    strategy_type: StrategyType
    signal_type: SignalType
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)
    # 冷却时间（秒），同一标的同一策略触发后冷却期内不再重复告警
    cooldown_seconds: int = 300


class BaseStrategy:
    """策略基类"""

    strategy_type: StrategyType

    def __init__(self, config: StrategyConfig):
        self.config = config
        self._last_trigger: Dict[str, float] = {}  # {code: timestamp}

    def check_cooldown(self, code: str) -> bool:
        """检查冷却期，返回 True 表示在冷却中"""
        last = self._last_trigger.get(code)
        if last is None:
            return False
        elapsed = time.time() - last
        return elapsed < self.config.cooldown_seconds

    def mark_triggered(self, code: str):
        """标记已触发"""
        self._last_trigger[code] = time.time()

    def evaluate(
        self, code: str, name: str, quote: Dict[str, Any]
    ) -> Optional[TriggerSignal]:
        """评估是否触发，子类实现"""
        raise NotImplementedError

    def evaluate_with_cooldown(
        self, code: str, name: str, quote: Dict[str, Any]
    ) -> Optional[TriggerSignal]:
        """带冷却检查的评估，在冷却期内返回 None"""
        if self.check_cooldown(code):
            return None
        signal = self.evaluate(code, name, quote)
        if signal:
            self.mark_triggered(code)
        return signal


# ============================================================
#  策略实现
# ============================================================

class ChangeThresholdStrategy(BaseStrategy):
    """涨跌幅阈值告警"""

    strategy_type = StrategyType.CHANGE_THRESHOLD

    def evaluate(
        self, code: str, name: str, quote: Dict[str, Any]
    ) -> Optional[TriggerSignal]:
        change_pct = quote.get("change_pct", 0) or 0
        price = quote.get("price", 0) or 0

        if abs(change_pct) <= self.config.params.get("threshold", 5):
            return None

        signal_type = SignalType.BUY if change_pct > 0 else SignalType.SELL
        direction = "上涨" if change_pct > 0 else "下跌"

        return TriggerSignal(
            code=code,
            name=name,
            signal_type=signal_type,
            strategy_type=self.strategy_type,
            current_price=price,
            change_pct=change_pct,
            trigger_value=change_pct,
            threshold=self.config.params.get("threshold", 5),
            message=f"涨跌幅阈值触发：{direction}{abs(change_pct):.2f}%",
            extra={"direction": direction},
        )


class VolumeSurgeStrategy(BaseStrategy):
    """量比异动告警"""

    strategy_type = StrategyType.VOLUME_SURGE

    def evaluate(
        self, code: str, name: str, quote: Dict[str, Any]
    ) -> Optional[TriggerSignal]:
        volume_ratio = quote.get("volume_ratio")
        if volume_ratio is None:
            return None

        price = quote.get("price", 0) or 0
        change_pct = quote.get("change_pct", 0) or 0

        # 放量上涨/下跌
        if volume_ratio > self.config.params.get("surge_threshold", 2.0):
            signal_type = SignalType.BUY if change_pct > 0 else SignalType.WARNING
            return TriggerSignal(
                code=code, name=name, signal_type=signal_type,
                strategy_type=self.strategy_type,
                current_price=price, change_pct=change_pct,
                trigger_value=volume_ratio,
                threshold=self.config.params.get("surge_threshold", 2.0),
                message=f"量比异动：量比{volume_ratio:.1f}，{'放量上涨' if change_pct > 0 else '放量下跌'}",
                extra={"volume_ratio": volume_ratio},
            )

        # 缩量
        if volume_ratio < self.config.params.get("shrink_threshold", 0.5):
            return TriggerSignal(
                code=code, name=name, signal_type=SignalType.ALERT,
                strategy_type=self.strategy_type,
                current_price=price, change_pct=change_pct,
                trigger_value=volume_ratio,
                threshold=self.config.params.get("shrink_threshold", 0.5),
                message=f"量比萎缩：量比{volume_ratio:.2f}，关注地量信号",
                extra={"volume_ratio": volume_ratio},
            )

        return None


class AmplitudeAlertStrategy(BaseStrategy):
    """振幅异常告警"""

    strategy_type = StrategyType.AMPLITUDE_ALERT

    def evaluate(
        self, code: str, name: str, quote: Dict[str, Any]
    ) -> Optional[TriggerSignal]:
        amplitude = quote.get("amplitude")
        if amplitude is None:
            return None

        threshold = self.config.params.get("threshold", 8.0)
        if amplitude <= threshold:
            return None

        price = quote.get("price", 0) or 0
        change_pct = quote.get("change_pct", 0) or 0

        return TriggerSignal(
            code=code, name=name,
            signal_type=SignalType.ALERT,
            strategy_type=self.strategy_type,
            current_price=price, change_pct=change_pct,
            trigger_value=amplitude, threshold=threshold,
            message=f"振幅异常：振幅{amplitude:.1f}%，盘中波动剧烈",
            extra={"amplitude": amplitude},
        )


class TurnoverAlertStrategy(BaseStrategy):
    """换手率异常告警"""

    strategy_type = StrategyType.TURNOVER_ALERT

    def evaluate(
        self, code: str, name: str, quote: Dict[str, Any]
    ) -> Optional[TriggerSignal]:
        turnover_rate = quote.get("turnover_rate")
        if turnover_rate is None:
            return None

        threshold = self.config.params.get("threshold", 10.0)
        if turnover_rate <= threshold:
            return None

        price = quote.get("price", 0) or 0
        change_pct = quote.get("change_pct", 0) or 0

        return TriggerSignal(
            code=code, name=name,
            signal_type=SignalType.WARNING,
            strategy_type=self.strategy_type,
            current_price=price, change_pct=change_pct,
            trigger_value=turnover_rate, threshold=threshold,
            message=f"换手率异常：换手率{turnover_rate:.1f}%，交投极度活跃",
            extra={"turnover_rate": turnover_rate},
        )


# ============================================================
#  策略工厂
# ============================================================

STRATEGY_REGISTRY: Dict[StrategyType, type] = {
    StrategyType.CHANGE_THRESHOLD: ChangeThresholdStrategy,
    StrategyType.VOLUME_SURGE: VolumeSurgeStrategy,
    StrategyType.AMPLITUDE_ALERT: AmplitudeAlertStrategy,
    StrategyType.TURNOVER_ALERT: TurnoverAlertStrategy,
}


def create_strategies(strategy_configs: List[Dict[str, Any]]) -> List[BaseStrategy]:
    """从配置列表创建策略实例"""
    strategies = []
    for cfg_dict in strategy_configs:
        stype_str = cfg_dict.get("strategy_type", "")
        try:
            stype = StrategyType(stype_str)
        except ValueError:
            logger.warning("未知策略类型: %s，跳过", stype_str)
            continue

        cls = STRATEGY_REGISTRY.get(stype)
        if cls is None:
            logger.warning("未注册的策略类型: %s，跳过", stype)
            continue

        config = StrategyConfig(
            strategy_type=stype,
            signal_type=SignalType(cfg_dict.get("signal_type", "alert")),
            enabled=cfg_dict.get("enabled", True),
            params=cfg_dict.get("params", {}),
            cooldown_seconds=cfg_dict.get("cooldown_seconds", 300),
        )
        strategies.append(cls(config))

    return strategies


def get_default_strategies() -> List[Dict[str, Any]]:
    """获取默认策略配置"""
    return [
        {
            "strategy_type": "change_threshold",
            "signal_type": "alert",
            "enabled": True,
            "params": {"threshold": 5.0},
            "cooldown_seconds": 600,
        },
        {
            "strategy_type": "volume_surge",
            "signal_type": "alert",
            "enabled": True,
            "params": {"surge_threshold": 2.0, "shrink_threshold": 0.5},
            "cooldown_seconds": 600,
        },
        {
            "strategy_type": "amplitude_alert",
            "signal_type": "alert",
            "enabled": True,
            "params": {"threshold": 8.0},
            "cooldown_seconds": 600,
        },
        {
            "strategy_type": "turnover_alert",
            "signal_type": "warning",
            "enabled": True,
            "params": {"threshold": 10.0},
            "cooldown_seconds": 900,
        },
    ]
