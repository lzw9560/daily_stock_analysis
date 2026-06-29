# -*- coding: utf-8 -*-
"""首板挖掘战法（交易系统升级 Phase 2）

核心逻辑: 板块共振 + 量价突破 + 封板力度
适用环境: 修复期、分化期
"""

from __future__ import annotations

from typing import Any, Optional

from .base_strategy import (
    BaseShortStrategy,
    TradeSignal,
    SignalType,
    EntryMethod,
)


class FirstBoardStrategy(BaseShortStrategy):
    """首板挖掘战法

    选股条件:
    1. 当日首板（非连板）
    2. 所属板块至少2只涨停（板块共振）
    3. 封板时间早（10:30前最佳）
    4. 封单强度足够（>5000万）
    5. 流通市值适中（30-150亿）
    6. 换手率合理（5-20%）
    """

    name = "first_board"
    display_name = "首板挖掘"
    description = "低位首板+板块共振+量价突破，适用于修复期和分化期"
    priority = 10  # 最高优先级

    suitable_phases = ["修复期", "分化期", "高潮期"]
    unsuitable_phases = ["退潮期"]

    # 首板参数阈值
    MIN_SEAL_AMOUNT = 5000       # 最小封单金额(万)
    MIN_TURNOVER_RATE = 3.0      # 最小换手率%
    MAX_TURNOVER_RATE = 25.0     # 最大换手率%
    MIN_MARKET_CAP = 30          # 最小流通市值(亿)
    MAX_MARKET_CAP = 200         # 最大流通市值(亿)
    IDEAL_SEAL_HOUR = 10         # 理想封板时间(小时)
    IDEAL_SEAL_MINUTE = 30       # 理想封板时间(分钟)
    SECTOR_RESONANCE_MIN = 2     # 板块共振最少涨停数

    def scan(
        self,
        market_data: dict[str, Any],
        *,
        sentiment_phase: str = "unknown",
        hot_sectors: Optional[list[str]] = None,
        **kwargs,
    ) -> list[TradeSignal]:
        """扫描首板机会"""
        signals: list[TradeSignal] = []
        hot_sectors = hot_sectors or []

        # market_data 应包含涨停板数据
        limit_up_stocks = market_data.get("limit_up_stocks", [])
        sector_limit_up = market_data.get("sector_limit_up_counts", {})

        for stock in limit_up_stocks:
            code = stock.get("code", "")
            name = stock.get("name", "")
            sector = stock.get("sector", "")

            # 1. 必须是首板
            consecutive = stock.get("consecutive_days", 0)
            if consecutive > 1:
                continue

            # 2. 板块共振检查
            sector_count = sector_limit_up.get(sector, 0)
            sector_hot = sector in hot_sectors or sector_count >= self.SECTOR_RESONANCE_MIN

            # 3. 基本参数检查
            seal_amount = stock.get("seal_amount", 0)
            turnover = stock.get("turnover_rate", 0)
            market_cap = stock.get("market_cap", 0)
            seal_time = stock.get("seal_time", "")

            if seal_amount < self.MIN_SEAL_AMOUNT:
                continue
            if turnover < self.MIN_TURNOVER_RATE or turnover > self.MAX_TURNOVER_RATE:
                continue
            if market_cap and (market_cap < self.MIN_MARKET_CAP or market_cap > self.MAX_MARKET_CAP):
                continue

            # 4. 计算置信度
            confidence = 0.5
            reasons = []
            risks = []

            # 封单强度加分
            if seal_amount >= 10000:
                confidence += 0.15
                reasons.append(f"封单{seal_amount:.0f}万，强度极佳")
            elif seal_amount >= 8000:
                confidence += 0.1
                reasons.append(f"封单{seal_amount:.0f}万，强度良好")

            # 板块共振加分
            if sector_hot:
                confidence += 0.15
                reasons.append(f"板块{sector}{sector_count}只涨停，共振确认")

            # 封板时间加分
            if seal_time:
                try:
                    parts = seal_time.split(":")
                    hour, minute = int(parts[0]), int(parts[1])
                    if hour < self.IDEAL_SEAL_HOUR or (
                        hour == self.IDEAL_SEAL_HOUR and minute <= self.IDEAL_SEAL_MINUTE
                    ):
                        confidence += 0.1
                        reasons.append(f"封板时间{seal_time}，早盘封板")
                    elif hour >= 14:
                        confidence -= 0.1
                        risks.append("午后封板，次日溢价不确定")
                except (ValueError, IndexError):
                    pass

            # 换手率评分
            if 5 <= turnover <= 15:
                confidence += 0.05
                reasons.append(f"换手率{turnover:.1f}%，健康换手")

            # 首板初封（非一字板）
            plate_type = stock.get("plate_type", "")
            if plate_type == "first":
                confidence -= 0.15
                risks.append("一字板，参与难度大")

            # 情绪阶段调整
            if sentiment_phase == "高潮期":
                confidence -= 0.05
                risks.append("高潮期首板溢价可能下降")

            confidence = max(0.1, min(1.0, confidence))

            # 计算止损/止盈
            close_price = stock.get("close_price", 0)
            entry_price = close_price
            stop_loss = close_price * 0.93  # -7%
            take_profit = close_price * 1.1  # +10%（次日涨停）

            signal = TradeSignal(
                code=code,
                name=name,
                strategy=self.name,
                signal_id=self.make_signal_id(code),
                signal_type=SignalType.SEAL_PLATE,
                entry_method=EntryMethod.打板,
                confidence=round(confidence, 2),
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                max_position_pct=self.default_position_pct,
                current_price=close_price,
                change_pct=stock.get("change_pct", 0),
                sector=sector,
                sector_resonance=sector_hot,
                sentiment_phase=sentiment_phase,
                reasons=reasons,
                risks=risks,
                key_metrics={
                    "seal_amount": seal_amount,
                    "turnover_rate": turnover,
                    "seal_time": seal_time,
                    "market_cap": market_cap,
                    "sector_limit_up_count": sector_count,
                },
            )
            signals.append(signal)

        return signals
