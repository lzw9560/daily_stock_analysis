# -*- coding: utf-8 -*-
"""短线战法基类与标准化信号输出（交易系统升级 Phase 2）

所有短线战法继承 BaseShortStrategy，输出标准的 TradeSignal。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


class SignalType(str, Enum):
    """信号类型"""
    SEAL_PLATE = "seal_plate"     # 打板
    LOW_SUCK = "low_suck"         # 低吸
    BREAKOUT = "breakout"         # 突破
    MARKET = "market"             # 市价
    LIMIT_ORDER = "limit_order"   # 限价


class EntryMethod(str, Enum):
    """入场方式"""
    打板 = "seal_plate"
    低吸 = "low_suck"
    突破 = "breakout"
    市价 = "market"
    限价 = "limit_order"


@dataclass
class TradeSignal:
    """标准化短线交易信号

    所有战法统一输出此格式，方便前端展示和回测引擎消费。
    """
    # === 基础信息 ===
    code: str                      # 股票代码
    name: str = ""                 # 股票名称
    strategy: str = ""             # 战法名称：首板/连板/低吸/N字/反包/...
    signal_id: str = ""            # 信号唯一ID（strategy_code_date）

    # === 交易参数 ===
    signal_type: SignalType = SignalType.MARKET
    entry_method: EntryMethod = EntryMethod.市价
    confidence: float = 0.5        # 置信度 0-1
    entry_price: float = 0.0       # 建议入场价
    stop_loss: float = 0.0         # 止损价
    take_profit: float = 0.0       # 止盈价
    max_position_pct: float = 20.0 # 最大仓位比%

    # === 分析信息 ===
    current_price: float = 0.0
    change_pct: float = 0.0
    sector: str = ""               # 所属板块
    sector_resonance: bool = False # 板块共振
    sentiment_phase: str = "unknown"

    # === 理由和风险 ===
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    key_metrics: dict[str, Any] = field(default_factory=dict)

    # === 元数据 ===
    generated_at: datetime = field(default_factory=datetime.now)
    data_quality: str = "ok"       # ok/degraded/insufficient

    # === K线数据（可选，供回测使用） ===
    kline_data: Optional[Any] = None  # pd.DataFrame 或 list[dict]

    @property
    def risk_reward_ratio(self) -> float:
        """盈亏比"""
        if self.stop_loss <= 0 or self.entry_price <= 0:
            return 0.0
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)
        return reward / risk if risk > 0 else 0.0

    @property
    def is_valid(self) -> bool:
        """信号是否有效"""
        return (
            self.confidence >= 0.4
            and self.entry_price > 0
            and self.stop_loss > 0
            and self.stop_loss < self.entry_price
            and self.data_quality == "ok"
        )

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "strategy": self.strategy,
            "signal_id": self.signal_id,
            "signal_type": self.signal_type.value,
            "entry_method": self.entry_method.value,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "max_position_pct": self.max_position_pct,
            "current_price": self.current_price,
            "change_pct": self.change_pct,
            "sector": self.sector,
            "sector_resonance": self.sector_resonance,
            "sentiment_phase": self.sentiment_phase,
            "reasons": self.reasons,
            "risks": self.risks,
            "key_metrics": self.key_metrics,
            "generated_at": self.generated_at.isoformat(),
            "data_quality": self.data_quality,
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
        }


class BaseShortStrategy(ABC):
    """短线战法基类

    子类必须实现:
    - scan(): 扫描全市场符合条件的标的
    - validate(): 验证单个信号的有效性
    """

    # 策略元信息（子类覆盖）
    name: str = "base"
    display_name: str = "基类"
    description: str = ""
    version: str = "1.0"
    priority: int = 50  # 优先级（越小越高）

    # 适用环境
    suitable_phases: list[str] = []  # 适合的情绪阶段
    unsuitable_phases: list[str] = []  # 不适合的情绪阶段

    # 参数
    min_confidence: float = 0.5
    default_position_pct: float = 20.0

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abstractmethod
    def scan(
        self,
        market_data: dict[str, Any],
        *,
        sentiment_phase: str = "unknown",
        hot_sectors: Optional[list[str]] = None,
        **kwargs,
    ) -> list[TradeSignal]:
        """扫描全市场，返回符合条件的信号列表

        Args:
            market_data: {stock_code: {ohlcv, indicators, ...}}
            sentiment_phase: 当前情绪阶段
            hot_sectors: 当前热点板块列表
        """
        ...

    def validate(self, signal: TradeSignal) -> bool:
        """验证信号有效性（可被子类覆盖）"""
        if not signal.is_valid:
            self.logger.debug(f"信号 {signal.signal_id} 基础检查未通过")
            return False
        if signal.confidence < self.min_confidence:
            self.logger.debug(f"信号 {signal.signal_id} 置信度{signal.confidence}低于阈值{self.min_confidence}")
            return False
        return True

    def is_suitable_phase(self, phase: str) -> bool:
        """检查当前阶段是否适合此策略"""
        if self.unsuitable_phases and phase in self.unsuitable_phases:
            return False
        if self.suitable_phases and phase not in self.suitable_phases:
            return False
        return True

    def adjust_for_sentiment(
        self, signal: TradeSignal, phase: str, sentiment_score: int = 50
    ) -> TradeSignal:
        """根据情绪阶段调整信号参数"""
        adjustments = {
            "冰点期": {"confidence_penalty": 0.1, "position_multiplier": 0.3},
            "修复期": {"confidence_penalty": 0.0, "position_multiplier": 0.6},
            "分化期": {"confidence_penalty": 0.0, "position_multiplier": 0.8},
            "高潮期": {"confidence_penalty": 0.05, "position_multiplier": 1.0},
            "退潮期": {"confidence_penalty": 0.2, "position_multiplier": 0.2},
        }
        adj = adjustments.get(phase, {"confidence_penalty": 0.0, "position_multiplier": 1.0})
        signal.confidence = max(0, signal.confidence - adj["confidence_penalty"])
        signal.max_position_pct *= adj["position_multiplier"]
        signal.sentiment_phase = phase
        return signal

    def make_signal_id(self, code: str, date_str: str = "") -> str:
        """生成信号唯一ID"""
        from datetime import date as dt
        d = date_str or dt.today().strftime("%Y%m%d")
        return f"{self.name}_{code}_{d}"

    def _find_support_resistance(
        self, bars: list, current_price: float
    ) -> tuple[float, float, float, float]:
        """从K线找最近支撑和压力

        Returns: (nearest_support, nearest_resistance, ma20, ma60)
        """
        if not bars or len(bars) < 20:
            return current_price * 0.95, current_price * 1.05, current_price, current_price

        closes = [b.close if hasattr(b, 'close') else b.get('close', 0) for b in bars[-60:]]
        closes = [c for c in closes if c > 0]

        if not closes:
            return current_price * 0.95, current_price * 1.05, current_price, current_price

        # 最近20日低点作为支撑参考
        support = min(closes[-20:]) if len(closes) >= 20 else current_price * 0.95
        # 最近20日高点作为压力参考
        resistance = max(closes[-20:]) if len(closes) >= 20 else current_price * 1.05

        # MA20 和 MA60
        ma20 = sum(closes[-20:]) / min(20, len(closes)) if len(closes) >= 20 else current_price
        ma60 = sum(closes[-60:]) / min(60, len(closes)) if len(closes) >= 20 else current_price

        return support, resistance, ma20, ma60

    @staticmethod
    def _calc_ma(values: list[float], period: int) -> float:
        """计算移动平均"""
        if not values or len(values) < period:
            return values[-1] if values else 0.0
        return sum(values[-period:]) / period

    @staticmethod
    def _calc_volume_ratio(
        volumes: list[float], current_vol: float
    ) -> float:
        """计算量比（相对5日均量）"""
        if not volumes or len(volumes) < 5:
            return 1.0
        avg_vol = sum(volumes[-5:]) / 5
        return current_vol / avg_vol if avg_vol > 0 else 1.0

    @staticmethod
    def _extract_ohlc(bars: list) -> tuple[list[float], list[float], list[float], list[float], list[float]]:
        """从 bar 列表提取 OHLCV"""
        opens, highs, lows, closes, volumes = [], [], [], [], []
        for b in bars:
            try:
                if hasattr(b, 'open'):
                    opens.append(float(b.open))
                    highs.append(float(b.high))
                    lows.append(float(b.low))
                    closes.append(float(b.close))
                    volumes.append(float(getattr(b, 'volume', 0)))
                elif isinstance(b, dict):
                    opens.append(float(b.get('open', 0)))
                    highs.append(float(b.get('high', 0)))
                    lows.append(float(b.get('low', 0)))
                    closes.append(float(b.get('close', 0)))
                    volumes.append(float(b.get('volume', 0)))
            except (TypeError, ValueError):
                continue
        return opens, highs, lows, closes, volumes


class StrategyRegistry:
    """策略注册中心"""

    _strategies: dict[str, BaseShortStrategy] = {}

    @classmethod
    def register(cls, strategy: BaseShortStrategy):
        cls._strategies[strategy.name] = strategy
        logger.info(f"注册策略: {strategy.display_name} ({strategy.name}) v{strategy.version}")

    @classmethod
    def get(cls, name: str) -> Optional[BaseShortStrategy]:
        return cls._strategies.get(name)

    @classmethod
    def list_all(cls) -> list[BaseShortStrategy]:
        return sorted(cls._strategies.values(), key=lambda s: s.priority)

    @classmethod
    def list_by_phase(cls, phase: str) -> list[BaseShortStrategy]:
        return [s for s in cls._strategies.values() if s.is_suitable_phase(phase)]

    @classmethod
    def clear(cls):
        cls._strategies.clear()
