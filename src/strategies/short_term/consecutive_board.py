# -*- coding: utf-8 -*-
"""连板接力战法（交易系统升级 Phase 2）

核心逻辑: 龙头识别 + 换手板 + 板块梯队完整
适用环境: 分化期、高潮期
"""

from __future__ import annotations

from typing import Any, Optional

from .base_strategy import (
    BaseShortStrategy,
    TradeSignal,
    SignalType,
    EntryMethod,
)


class ConsecutiveBoardStrategy(BaseShortStrategy):
    """连板接力战法

    选股条件:
    1. 2-3板龙头，板块内最高板数
    2. 换手板（非一字板接力）
    3. 板块梯队完整（有2板/3板/首板跟随）
    4. 封板时间早
    5. 封单强度足够
    6. 不是连续一字板
    """

    name = "consecutive_board"
    display_name = "连板接力"
    description = "2-3板龙头接力，要求换手板+板块梯队完整"
    priority = 15

    suitable_phases = ["分化期", "高潮期"]
    unsuitable_phases = ["冰点期", "退潮期"]

    MAX_BOARD = 4          # 最多接力到3板（4板以上风险大）
    MIN_SEAL_AMOUNT = 8000 # 连板要求更高封单
    MIN_SECTOR_BOARDS = 2  # 板块内至少2只涨停（梯队）

    def scan(
        self,
        market_data: dict[str, Any],
        *,
        sentiment_phase: str = "unknown",
        hot_sectors: Optional[list[str]] = None,
        **kwargs,
    ) -> list[TradeSignal]:
        """扫描连板接力机会"""
        signals: list[TradeSignal] = []
        hot_sectors = hot_sectors or []

        limit_up_stocks = market_data.get("limit_up_stocks", [])
        sector_limit_up = market_data.get("sector_limit_up_counts", {})

        # 找出每个板块的龙头（最高连板数）
        sector_leaders: dict[str, dict] = {}
        for stock in limit_up_stocks:
            sector = stock.get("sector", "")
            consecutive = stock.get("consecutive_days", 1)
            if sector not in sector_leaders or consecutive > sector_leaders[sector]["consecutive_days"]:
                sector_leaders[sector] = stock

        for stock in limit_up_stocks:
            code = stock.get("code", "")
            name = stock.get("name", "")
            sector = stock.get("sector", "")
            consecutive = stock.get("consecutive_days", 1)

            # 1. 只选2-3板（4板可以看但不推荐）
            if consecutive < 2 or consecutive >= self.MAX_BOARD:
                continue

            # 2. 板块梯队检查
            sector_count = sector_limit_up.get(sector, 0)
            is_leader = code == sector_leaders.get(sector, {}).get("code", "")
            if sector_count < self.MIN_SECTOR_BOARDS:
                continue

            # 3. 必须是换手板（排除一字板接力）
            plate_type = stock.get("plate_type", "")
            if plate_type == "first":
                continue  # 一字板不接力

            # 4. 基本参数检查
            seal_amount = stock.get("seal_amount", 0)
            turnover = stock.get("turnover_rate", 0)
            if seal_amount < self.MIN_SEAL_AMOUNT:
                continue

            # 5. 计算置信度
            confidence = 0.45  # 连板基础置信度低于首板
            reasons = []
            risks = []

            # 龙头加分
            if is_leader:
                confidence += 0.15
                reasons.append(f"板块{sector}龙头({consecutive}板)")

            # 板块梯队完整
            if sector_count >= 4:
                confidence += 0.1
                reasons.append(f"板块梯队完整({sector_count}只涨停)")
            elif sector_count >= 3:
                confidence += 0.05
                reasons.append(f"板块有{sector_count}只涨停，梯队基本完整")

            # 封单强度
            if seal_amount >= 15000:
                confidence += 0.1
                reasons.append("封单极强")

            # 连板数风险
            if consecutive >= 3:
                confidence -= 0.1
                risks.append(f"已{consecutive}板，高位接力风险增大")
                risks.append(f"{consecutive}板炸板率通常>30%")

            # 情绪阶段
            if sentiment_phase == "高潮期" and consecutive >= 3:
                confidence -= 0.1
                risks.append("高潮期高位接力，风险加剧")

            confidence = max(0.1, min(1.0, confidence))

            close_price = stock.get("close_price", 0)
            entry_price = close_price
            # 连板止损更紧
            stop_loss = close_price * (0.94 if consecutive == 2 else 0.95)
            take_profit = close_price * 1.1

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
                max_position_pct=self.default_position_pct * (1.0 if consecutive == 2 else 0.7),
                current_price=close_price,
                change_pct=stock.get("change_pct", 0),
                sector=sector,
                sector_resonance=sector_count >= 3,
                sentiment_phase=sentiment_phase,
                reasons=reasons,
                risks=risks,
                key_metrics={
                    "consecutive_days": consecutive,
                    "seal_amount": seal_amount,
                    "turnover_rate": turnover,
                    "is_leader": is_leader,
                    "sector_limit_up_count": sector_count,
                },
            )
            signals.append(signal)

        return signals
