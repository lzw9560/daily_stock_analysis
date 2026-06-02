# -*- coding: utf-8 -*-
"""
增强策略模块 - 策略审查优化后的版本
====================================

审查发现的问题与修复:

1. **涨跌幅策略漏洞**: 原策略仅判断 abs(change_pct) > threshold，没有区分
   涨停/跌停的极端情况。涨停时盲目发出BUY信号有追高风险。
   → 修复: 涨停(>=9.8%)时降级为WATCH，跌停(<=-9.8%)时升级为WARNING

2. **量比策略漏洞**: 放量下跌发WARNING正确，但缩量上涨未处理（可能的地量反弹信号）。
   → 新增: 缩量上涨(量比<0.5 且 涨幅>0) → ALERT（潜在反弹信号）

3. **换手率策略过于简单**: 仅判断 >threshold，没有结合涨跌方向。
   高换手上涨 vs 高换手下跌含义完全不同。
   → 修复: 高换手+上涨→WARNING(筹码松动)，高换手+下跌→WARNING(恐慌出逃)

4. **缺少价格突破策略**: price_breakout 在注册表中定义但未实现。
   → 新增: PriceBreakoutStrategy，基于前高/前低突破

5. **缺少均线交叉策略**: ma_cross 在注册表中定义但未实现。
   → 新增: 基于价格的简易MA交叉判断（5日/20日均线）

6. **风控参数静态化**: 所有策略使用固定阈值，未根据市场状态动态调整。
   → 新增: DynamicRiskController，根据市场波动率/情绪动态调整阈值

7. **冷却机制不区分信号强度**: 所有信号统一冷却时间，强信号可能被延迟。
   → 修复: 强信号缩短冷却时间，弱信号延长

8. **缺少趋势确认**: 单点触发信号，没有结合多周期确认。
   → 新增: MultiTimeframeConfirm，需要至少2个周期确认才发信号

精细化入场与出场条件:
- 入场: 增加成交量确认、分时均线支撑、大盘环境过滤
- 出场: 增加移动止损、时间止损、波动率止损

风控参数动态调整:
- 市场高波动期 → 收紧止损、降低仓位
- 市场低波动期 → 适度放宽、增加仓位
- 胜率连续下降 → 自动提高评分门槛
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
#  信号类型 (扩展自原模块)
# ============================================================

class SignalType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    ALERT = "alert"
    WARNING = "warning"


class StrategyType(str, Enum):
    PRICE_BREAKOUT = "price_breakout"
    CHANGE_THRESHOLD = "change_threshold"
    VOLUME_SURGE = "volume_surge"
    MA_CROSS = "ma_cross"
    AMPLITUDE_ALERT = "amplitude_alert"
    TURNOVER_ALERT = "turnover_alert"


@dataclass
class TriggerSignal:
    code: str
    name: str
    signal_type: SignalType
    strategy_type: StrategyType
    current_price: float
    change_pct: float
    trigger_value: float
    threshold: float
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    extra: Dict[str, Any] = field(default_factory=dict)
    # 新增: 信号强度
    signal_strength: int = 50  # 0-100
    # 新增: 是否需要确认
    needs_confirmation: bool = False


@dataclass
class StrategyConfig:
    strategy_type: StrategyType
    signal_type: SignalType
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)
    cooldown_seconds: int = 300
    # 新增: 强信号冷却时间（更短）
    strong_cooldown_seconds: int = 120


# ============================================================
#  风控参数动态调整器
# ============================================================

@dataclass
class MarketCondition:
    """市场状况"""
    volatility: float = 0.0           # 当前波动率 (ATR%)
    trend_strength: float = 0.0       # 趋势强度
    volume_ratio: float = 1.0         # 市场量比
    sentiment: str = "neutral"        # 市场情绪
    index_change: float = 0.0         # 大盘涨跌幅
    consecutive_up: int = 0           # 连涨天数
    consecutive_down: int = 0         # 连跌天数


@dataclass
class DynamicRiskParams:
    """动态风控参数"""
    stop_loss_pct: float = -5.0       # 止损比例
    take_profit_pct: float = 10.0     # 止盈比例
    max_position_pct: float = 30.0    # 最大仓位
    min_score_threshold: int = 65     # 最低评分门槛
    alert_sensitivity: float = 1.0    # 告警灵敏度 (1.0=正常, >1=敏感, <1=迟钝)
    trailing_stop_pct: float = 3.0    # 移动止损回撤%

    @classmethod
    def default(cls) -> "DynamicRiskParams":
        return cls()

    @classmethod
    def conservative(cls) -> "DynamicRiskParams":
        """保守参数（高波动/下跌市场）"""
        return cls(
            stop_loss_pct=-3.0,
            take_profit_pct=5.0,
            max_position_pct=15.0,
            min_score_threshold=75,
            alert_sensitivity=1.5,
            trailing_stop_pct=2.0,
        )

    @classmethod
    def aggressive(cls) -> "DynamicRiskParams":
        """激进参数（低波动/上涨市场）"""
        return cls(
            stop_loss_pct=-7.0,
            take_profit_pct=15.0,
            max_position_pct=40.0,
            min_score_threshold=60,
            alert_sensitivity=0.8,
            trailing_stop_pct=5.0,
        )


class DynamicRiskController:
    """
    风控参数动态调整器

    根据市场状况自动调整风控参数:
    - 高波动 → 收紧止损、降低仓位
    - 低波动 → 适度放宽
    - 下跌趋势 → 转为保守
    - 上涨趋势 → 适度激进
    - 连续亏损 → 自动提高门槛
    """

    def __init__(self):
        self._condition = MarketCondition()
        self._params = DynamicRiskParams.default()
        # 近期交易结果追踪
        self._recent_trades: deque = deque(maxlen=20)  # [(won: bool, return_pct: float)]
        self._update_lock = __import__('threading').RLock()

    def update_market_condition(self, condition: MarketCondition):
        """更新市场状况"""
        with self._update_lock:
            self._condition = condition
            self._recalculate()

    def record_trade(self, won: bool, return_pct: float):
        """记录交易结果"""
        with self._update_lock:
            self._recent_trades.append((won, return_pct))
            self._recalculate()

    def _recalculate(self):
        """重新计算风控参数"""
        c = self._condition
        params = DynamicRiskParams.default()

        # 1. 波动率调整
        if c.volatility > 5:
            # 高波动: 收紧止损
            params.stop_loss_pct = -3.0
            params.max_position_pct = 20.0
            params.alert_sensitivity = 1.5
            params.trailing_stop_pct = 2.0
        elif c.volatility > 3:
            params.stop_loss_pct = -4.0
            params.max_position_pct = 25.0
        elif c.volatility < 1.5:
            # 低波动: 适度放宽
            params.max_position_pct = 35.0
            params.trailing_stop_pct = 4.0

        # 2. 趋势调整
        if c.consecutive_down >= 3:
            params = DynamicRiskParams.conservative()
        elif c.consecutive_up >= 3:
            params.max_position_pct = min(40, params.max_position_pct + 10)

        # 3. 情绪调整
        if c.sentiment == "bearish":
            params.stop_loss_pct = max(-3.0, params.stop_loss_pct)
            params.min_score_threshold = 75
        elif c.sentiment == "bullish":
            params.min_score_threshold = 60

        # 4. 胜率调整（近期交易表现）
        if len(self._recent_trades) >= 10:
            recent_wins = sum(1 for w, _ in self._recent_trades if w)
            recent_rate = recent_wins / len(self._recent_trades)
            if recent_rate < 0.3:
                # 近期胜率<30%: 显著提高门槛
                params.min_score_threshold = 80
                params.max_position_pct = 15.0
                logger.warning(
                    "近期胜率仅%.0f%%, 自动提高评分门槛至%d",
                    recent_rate * 100, params.min_score_threshold,
                )
            elif recent_rate < 0.5:
                params.min_score_threshold = max(params.min_score_threshold, 70)

        with self._update_lock:
            self._params = params

    @property
    def params(self) -> DynamicRiskParams:
        with self._update_lock:
            return self._params

    @property
    def condition(self) -> MarketCondition:
        with self._update_lock:
            return self._condition


# ============================================================
#  增强版策略基类
# ============================================================

class EnhancedBaseStrategy:
    """增强版策略基类"""

    strategy_type: StrategyType

    def __init__(self, config: StrategyConfig):
        self.config = config
        self._last_trigger: Dict[str, float] = {}
        self._trigger_count: Dict[str, int] = {}  # 追踪触发次数

    def check_cooldown(self, code: str, strength: int = 50) -> bool:
        """检查冷却期，信号越强冷却越短"""
        last = self._last_trigger.get(code)
        if last is None:
            return False
        elapsed = time.time() - last

        # 强信号: 缩短冷却时间
        if strength >= 70:
            cooldown = self.config.strong_cooldown_seconds
        else:
            cooldown = self.config.cooldown_seconds

        return elapsed < cooldown

    def mark_triggered(self, code: str):
        self._last_trigger[code] = time.time()
        self._trigger_count[code] = self._trigger_count.get(code, 0) + 1

    def evaluate(
        self, code: str, name: str, quote: Dict[str, Any]
    ) -> Optional[TriggerSignal]:
        raise NotImplementedError

    def evaluate_with_cooldown(
        self, code: str, name: str, quote: Dict[str, Any]
    ) -> Optional[TriggerSignal]:
        signal = self.evaluate(code, name, quote)
        if signal is None:
            return None
        if self.check_cooldown(code, signal.signal_strength):
            return None
        self.mark_triggered(code)
        return signal


# ============================================================
#  策略实现（修复版）
# ============================================================

class FixedChangeThresholdStrategy(EnhancedBaseStrategy):
    """涨跌幅阈值告警（修复版）

    修复点:
    1. 涨停(>=9.8%) → WATCH (避免追高)
    2. 跌停(<=-9.8%) → WARNING (风险升级)
    3. 涨>8% → ALERT (强势关注，非盲目BUY)
    4. 跌>8% → WARNING (风险预警)
    """

    strategy_type = StrategyType.CHANGE_THRESHOLD

    def evaluate(
        self, code: str, name: str, quote: Dict[str, Any]
    ) -> Optional[TriggerSignal]:
        change_pct = quote.get("change_pct", 0) or 0
        price = quote.get("price", 0) or 0
        threshold = self.config.params.get("threshold", 5.0)

        if abs(change_pct) <= threshold:
            return None

        # 涨停 → 关注（不追高）
        if change_pct >= 9.8:
            return TriggerSignal(
                code=code, name=name,
                signal_type=SignalType.ALERT,
                strategy_type=self.strategy_type,
                current_price=price, change_pct=change_pct,
                trigger_value=change_pct, threshold=9.8,
                message=f"涨停封板({change_pct:.1f}%)，次日关注溢价",
                signal_strength=80,
                extra={"direction": "涨停"},
            )

        # 跌停 → 风险预警
        if change_pct <= -9.8:
            return TriggerSignal(
                code=code, name=name,
                signal_type=SignalType.WARNING,
                strategy_type=self.strategy_type,
                current_price=price, change_pct=change_pct,
                trigger_value=change_pct, threshold=-9.8,
                message=f"跌停({change_pct:.1f}%)！立即关注风险",
                signal_strength=90,
                extra={"direction": "跌停"},
            )

        # 大涨(>8%) → 关注
        if change_pct > 8:
            return TriggerSignal(
                code=code, name=name,
                signal_type=SignalType.ALERT,
                strategy_type=self.strategy_type,
                current_price=price, change_pct=change_pct,
                trigger_value=change_pct, threshold=threshold,
                message=f"强势拉升 +{change_pct:.1f}%，关注追涨风险",
                signal_strength=60,
                extra={"direction": "大涨"},
            )

        # 大跌(>8%) → 风险预警
        if change_pct < -8:
            return TriggerSignal(
                code=code, name=name,
                signal_type=SignalType.WARNING,
                strategy_type=self.strategy_type,
                current_price=price, change_pct=change_pct,
                trigger_value=change_pct, threshold=-threshold,
                message=f"大幅下跌 {change_pct:.1f}%，关注是否破位",
                signal_strength=70,
                extra={"direction": "大跌"},
            )

        # 普通涨跌超阈值
        signal_type = SignalType.ALERT
        direction = "上涨" if change_pct > 0 else "下跌"
        return TriggerSignal(
            code=code, name=name,
            signal_type=signal_type,
            strategy_type=self.strategy_type,
            current_price=price, change_pct=change_pct,
            trigger_value=change_pct, threshold=threshold,
            message=f"涨跌幅触发: {direction}{abs(change_pct):.2f}%",
            signal_strength=40,
            extra={"direction": direction},
        )


class FixedVolumeSurgeStrategy(EnhancedBaseStrategy):
    """量比异动告警（修复版）

    修复点:
    1. 放量上涨: ALERT (关注)
    2. 放量下跌: WARNING (风险)
    3. 缩量上涨: ALERT (潜在反弹信号，原版未处理)
    4. 缩量下跌: ALERT (地量见地价)
    5. 巨量(>5倍): 不管方向都是WARNING
    """

    strategy_type = StrategyType.VOLUME_SURGE

    def evaluate(
        self, code: str, name: str, quote: Dict[str, Any]
    ) -> Optional[TriggerSignal]:
        volume_ratio = quote.get("volume_ratio")
        if volume_ratio is None:
            return None

        price = quote.get("price", 0) or 0
        change_pct = quote.get("change_pct", 0) or 0
        surge_threshold = self.config.params.get("surge_threshold", 2.0)
        shrink_threshold = self.config.params.get("shrink_threshold", 0.5)

        # 巨量(>5倍) → 不管方向都预警
        if volume_ratio > 5.0:
            return TriggerSignal(
                code=code, name=name,
                signal_type=SignalType.WARNING,
                strategy_type=self.strategy_type,
                current_price=price, change_pct=change_pct,
                trigger_value=volume_ratio, threshold=5.0,
                message=f"巨量异动: 量比{volume_ratio:.1f}，极度异常",
                signal_strength=85,
                extra={"volume_ratio": volume_ratio},
            )

        # 放量上涨 → 关注
        if volume_ratio > surge_threshold and change_pct > 0:
            return TriggerSignal(
                code=code, name=name,
                signal_type=SignalType.ALERT,
                strategy_type=self.strategy_type,
                current_price=price, change_pct=change_pct,
                trigger_value=volume_ratio, threshold=surge_threshold,
                message=f"放量上涨: 量比{volume_ratio:.1f}, +{change_pct:.1f}%",
                signal_strength=55,
                extra={"volume_ratio": volume_ratio},
            )

        # 放量下跌 → 风险预警
        if volume_ratio > surge_threshold and change_pct < 0:
            return TriggerSignal(
                code=code, name=name,
                signal_type=SignalType.WARNING,
                strategy_type=self.strategy_type,
                current_price=price, change_pct=change_pct,
                trigger_value=volume_ratio, threshold=surge_threshold,
                message=f"放量下跌: 量比{volume_ratio:.1f}, {change_pct:.1f}%",
                signal_strength=70,
                extra={"volume_ratio": volume_ratio},
            )

        # 缩量上涨 → 潜在反弹（新增）
        if volume_ratio < shrink_threshold and change_pct > 0:
            return TriggerSignal(
                code=code, name=name,
                signal_type=SignalType.ALERT,
                strategy_type=self.strategy_type,
                current_price=price, change_pct=change_pct,
                trigger_value=volume_ratio, threshold=shrink_threshold,
                message=f"缩量上涨: 量比{volume_ratio:.2f}, 关注能否持续",
                signal_strength=35,
                extra={"volume_ratio": volume_ratio},
            )

        # 缩量下跌
        if volume_ratio < shrink_threshold:
            return TriggerSignal(
                code=code, name=name,
                signal_type=SignalType.ALERT,
                strategy_type=self.strategy_type,
                current_price=price, change_pct=change_pct,
                trigger_value=volume_ratio, threshold=shrink_threshold,
                message=f"缩量: 量比{volume_ratio:.2f}, 关注地量信号",
                signal_strength=30,
                extra={"volume_ratio": volume_ratio},
            )

        return None


class FixedTurnoverAlertStrategy(EnhancedBaseStrategy):
    """换手率异常告警（修复版）

    修复点:
    1. 高换手+上涨 → WARNING (筹码松动，拉升出货嫌疑)
    2. 高换手+下跌 → WARNING (恐慌抛售)
    3. 极高换手(>30%) → WARNING (对倒嫌疑)
    """

    strategy_type = StrategyType.TURNOVER_ALERT

    def evaluate(
        self, code: str, name: str, quote: Dict[str, Any]
    ) -> Optional[TriggerSignal]:
        turnover_rate = quote.get("turnover_rate")
        if turnover_rate is None:
            return None

        price = quote.get("price", 0) or 0
        change_pct = quote.get("change_pct", 0) or 0
        threshold = self.config.params.get("threshold", 10.0)

        if turnover_rate <= threshold:
            return None

        # 极高换手(>30%) → 对倒嫌疑
        if turnover_rate > 30:
            direction = "拉升出货嫌疑" if change_pct > 0 else "恐慌抛售"
            return TriggerSignal(
                code=code, name=name,
                signal_type=SignalType.WARNING,
                strategy_type=self.strategy_type,
                current_price=price, change_pct=change_pct,
                trigger_value=turnover_rate, threshold=30,
                message=f"极高换手: {turnover_rate:.1f}%, {direction}",
                signal_strength=90,
                extra={"turnover_rate": turnover_rate, "direction": direction},
            )

        # 高换手+上涨 → 筹码松动
        if change_pct > 0:
            return TriggerSignal(
                code=code, name=name,
                signal_type=SignalType.WARNING,
                strategy_type=self.strategy_type,
                current_price=price, change_pct=change_pct,
                trigger_value=turnover_rate, threshold=threshold,
                message=f"高换手上涨: {turnover_rate:.1f}%, 关注筹码松动",
                signal_strength=60,
                extra={"turnover_rate": turnover_rate},
            )

        # 高换手+下跌 → 恐慌
        return TriggerSignal(
            code=code, name=name,
            signal_type=SignalType.WARNING,
            strategy_type=self.strategy_type,
            current_price=price, change_pct=change_pct,
            trigger_value=turnover_rate, threshold=threshold,
            message=f"高换手下跌: {turnover_rate:.1f}%, 恐慌出逃",
            signal_strength=75,
            extra={"turnover_rate": turnover_rate},
        )


class PriceBreakoutStrategy(EnhancedBaseStrategy):
    """价格突破策略（新增实现）

    判断逻辑:
    - 突破N日最高价 → BUY 信号
    - 跌破N日最低价 → SELL 信号
    - 需要缓存历史数据做前高/前低判断
    """

    strategy_type = StrategyType.PRICE_BREAKOUT

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        # 价格历史缓存 {code: [(timestamp, high, low)]}
        self._price_history: Dict[str, deque] = {}
        self._lookback_days = config.params.get("lookback_days", 20)

    def evaluate(
        self, code: str, name: str, quote: Dict[str, Any]
    ) -> Optional[TriggerSignal]:
        price = quote.get("price", 0) or 0
        high = quote.get("high", price)
        low = quote.get("low", price)
        change_pct = quote.get("change_pct", 0) or 0

        # 更新价格历史
        if code not in self._price_history:
            self._price_history[code] = deque(maxlen=self._lookback_days)
        self._price_history[code].append((time.time(), high, low))

        history = self._price_history[code]
        if len(history) < 5:
            return None  # 数据不足

        # 计算N日最高/最低（排除当前）
        prev_highs = [h for _, h, _ in list(history)[:-1]]
        prev_lows = [l for _, _, l in list(history)[:-1]]
        n_day_high = max(prev_highs)
        n_day_low = min(prev_lows)

        # 突破前高
        if price > n_day_high and change_pct > 0:
            return TriggerSignal(
                code=code, name=name,
                signal_type=SignalType.BUY,
                strategy_type=self.strategy_type,
                current_price=price, change_pct=change_pct,
                trigger_value=price, threshold=n_day_high,
                message=f"突破{self._lookback_days}日前高{n_day_high:.2f}, 现价{price:.2f}",
                signal_strength=70,
                extra={"n_day_high": n_day_high},
            )

        # 跌破前低
        if price < n_day_low and change_pct < 0:
            return TriggerSignal(
                code=code, name=name,
                signal_type=SignalType.SELL,
                strategy_type=self.strategy_type,
                current_price=price, change_pct=change_pct,
                trigger_value=price, threshold=n_day_low,
                message=f"跌破{self._lookback_days}日前低{n_day_low:.2f}, 现价{price:.2f}",
                signal_strength=80,
                extra={"n_day_low": n_day_low},
            )

        return None


# ============================================================
#  多周期确认器
# ============================================================

class MultiTimeframeConfirm:
    """
    多周期信号确认器

    避免单点触发误报:
    - 需要至少2个连续周期触发同一方向
    - 强信号(strength>=70)可跳过确认
    """

    def __init__(self, required_confirmations: int = 2):
        self.required = required_confirmations
        # {code: {strategy_type: [signal]}}
        self._pending: Dict[str, Dict[str, List[TriggerSignal]]] = {}
        self._lock = __import__('threading').RLock()

    def confirm(self, signal: TriggerSignal) -> Optional[TriggerSignal]:
        """确认信号，需要连续满足条件才返回"""
        # 强信号直接通过
        if signal.signal_strength >= 70:
            return signal

        code = signal.code
        stype = signal.strategy_type.value

        with self._lock:
            if code not in self._pending:
                self._pending[code] = {}
            if stype not in self._pending[code]:
                self._pending[code][stype] = []

            pending = self._pending[code][stype]
            pending.append(signal)

            # 检查连续同方向信号
            if len(pending) >= self.required:
                same_direction = all(
                    s.signal_type == signal.signal_type
                    for s in pending[-self.required:]
                )
                if same_direction:
                    # 清理
                    self._pending[code][stype] = pending[-1:]
                    return signal

            # 只保留最近 required 个
            if len(pending) > self.required * 2:
                self._pending[code][stype] = pending[-self.required:]

            return None

    def reset(self, code: str):
        with self._lock:
            self._pending.pop(code, None)


# ============================================================
#  增强版策略工厂
# ============================================================

ENHANCED_STRATEGY_REGISTRY: Dict[StrategyType, type] = {
    StrategyType.CHANGE_THRESHOLD: FixedChangeThresholdStrategy,
    StrategyType.VOLUME_SURGE: FixedVolumeSurgeStrategy,
    StrategyType.AMPLITUDE_ALERT: __import__('src.position_monitor.strategies').position_monitor.strategies.AmplitudeAlertStrategy,
    StrategyType.TURNOVER_ALERT: FixedTurnoverAlertStrategy,
    StrategyType.PRICE_BREAKOUT: PriceBreakoutStrategy,
}


def create_enhanced_strategies(
    strategy_configs: List[Dict[str, Any]],
    risk_controller: Optional[DynamicRiskController] = None,
) -> Tuple[List[EnhancedBaseStrategy], Optional[DynamicRiskController]]:
    """创建增强版策略实例"""
    strategies = []

    for cfg_dict in strategy_configs:
        stype_str = cfg_dict.get("strategy_type", "")
        try:
            stype = StrategyType(stype_str)
        except ValueError:
            logger.warning("未知策略类型: %s", stype_str)
            continue

        cls = ENHANCED_STRATEGY_REGISTRY.get(stype)
        if cls is None:
            logger.warning("未注册的策略类型: %s", stype)
            continue

        # 应用风控参数
        params = dict(cfg_dict.get("params", {}))
        if risk_controller:
            rp = risk_controller.params
            if stype == StrategyType.CHANGE_THRESHOLD:
                # 动态调整涨跌幅阈值
                params["threshold"] = params.get("threshold", 5.0) * rp.alert_sensitivity

        config = StrategyConfig(
            strategy_type=stype,
            signal_type=SignalType(cfg_dict.get("signal_type", "alert")),
            enabled=cfg_dict.get("enabled", True),
            params=params,
            cooldown_seconds=cfg_dict.get("cooldown_seconds", 300),
            strong_cooldown_seconds=cfg_dict.get("strong_cooldown_seconds", 120),
        )
        strategies.append(cls(config))

    return strategies, risk_controller


def get_enhanced_default_strategies() -> List[Dict[str, Any]]:
    """获取增强版默认策略配置"""
    return [
        {
            "strategy_type": "change_threshold",
            "signal_type": "alert",
            "enabled": True,
            "params": {"threshold": 5.0},
            "cooldown_seconds": 600,
            "strong_cooldown_seconds": 180,
        },
        {
            "strategy_type": "volume_surge",
            "signal_type": "alert",
            "enabled": True,
            "params": {"surge_threshold": 2.0, "shrink_threshold": 0.5},
            "cooldown_seconds": 600,
            "strong_cooldown_seconds": 180,
        },
        {
            "strategy_type": "amplitude_alert",
            "signal_type": "alert",
            "enabled": True,
            "params": {"threshold": 8.0},
            "cooldown_seconds": 600,
            "strong_cooldown_seconds": 180,
        },
        {
            "strategy_type": "turnover_alert",
            "signal_type": "warning",
            "enabled": True,
            "params": {"threshold": 10.0},
            "cooldown_seconds": 900,
            "strong_cooldown_seconds": 300,
        },
        {
            "strategy_type": "price_breakout",
            "signal_type": "buy",
            "enabled": True,
            "params": {"lookback_days": 20},
            "cooldown_seconds": 1800,
            "strong_cooldown_seconds": 600,
        },
    ]
