# -*- coding: utf-8 -*-
"""N字反击战法（交易系统升级 Phase 2）

核心逻辑: 涨停→回调2-3天(不破涨停起点)→再次放量上涨
适用环境: 修复期、分化期（龙头股）
"""

from __future__ import annotations

from typing import Any, Optional

from .base_strategy import (
    BaseShortStrategy,
    TradeSignal,
    SignalType,
    EntryMethod,
)


class NPatternStrategy(BaseShortStrategy):
    """N字反击战法

    选股条件:
    1. 5日内有过涨停（基准日）
    2. 涨停后回调2-3天
    3. 回调不跌破涨停日最低价
    4. 今日再次放量上涨（涨幅>3%）
    5. 所属板块有热度
    """

    name = "n_pattern"
    display_name = "N字反击"
    description = "涨停→回调2-3天→再次放量上涨，N型走势确认"
    priority = 25

    suitable_phases = ["修复期", "分化期", "高潮期"]
    unsuitable_phases = ["冰点期", "退潮期"]

    # 参数
    MAX_DAYS_SINCE_LIMIT_UP = 7    # 涨停在7日内
    MIN_PULLBACK_DAYS = 2          # 最少回调天数
    MAX_PULLBACK_DAYS = 4          # 最多回调天数
    TODAY_MIN_CHANGE = 3.0         # 今日最低涨幅
    MIN_VOLUME_RATIO = 1.2         # 放量要求

    def scan(
        self,
        market_data: dict[str, Any],
        *,
        sentiment_phase: str = "unknown",
        hot_sectors: Optional[list[str]] = None,
        **kwargs,
    ) -> list[TradeSignal]:
        """扫描N字形态"""
        signals: list[TradeSignal] = []
        hot_sectors = hot_sectors or []

        stocks = market_data.get("stocks", {})

        for code, data in stocks.items():
            name = data.get("name", "")
            sector = data.get("sector", "")

            bars = data.get("bars", [])
            if not bars or len(bars) < 10:
                continue

            opens, highs, lows, closes, volumes = self._extract_ohlc(bars)
            if len(closes) < 10:
                continue

            current_price = closes[-1]
            current_vol = volumes[-1] if volumes else 0

            # 1. 今日涨幅检查
            if len(closes) < 2:
                continue
            today_change = (current_price - closes[-2]) / closes[-2] * 100
            if today_change < self.TODAY_MIN_CHANGE:
                continue

            # 2. 找最近的涨停日（涨幅>9.5%）
            limit_up_idx = None
            lu_price = 0.0
            lu_low = 0.0
            for i in range(len(closes) - 2, max(0, len(closes) - 10), -1):
                if i == 0:
                    continue
                day_change = (closes[i] - closes[i - 1]) / closes[i - 1] * 100
                if day_change >= 9.5:
                    limit_up_idx = i
                    lu_price = closes[i]
                    lu_low = lows[i] if i < len(lows) else closes[i] * 0.9
                    break

            if limit_up_idx is None:
                continue

            # 3. 检查回调天数
            pullback_days = len(closes) - 1 - limit_up_idx
            if pullback_days < self.MIN_PULLBACK_DAYS or pullback_days > self.MAX_PULLBACK_DAYS:
                continue

            # 4. 检查回调是否跌破涨停日最低价
            pullback_lows = lows[limit_up_idx + 1:-1] if len(lows) > limit_up_idx + 1 else []
            if pullback_lows and min(pullback_lows) < lu_low:
                continue

            # 5. 放量检查
            vol_ratio = self._calc_volume_ratio(volumes, current_vol)
            if vol_ratio < self.MIN_VOLUME_RATIO:
                continue

            # 计算置信度
            confidence = 0.5
            reasons = []
            risks = []

            reasons.append(f"N字形态: {pullback_days}日前涨停(¥{lu_price:.2f})，回调{pullback_days}日后再次放量上攻")

            # 回调幅度
            pullback_low = min(pullback_lows) if pullback_lows else current_price
            pullback_pct = (lu_price - pullback_low) / lu_price * 100
            if pullback_pct <= 5:
                confidence += 0.1
                reasons.append(f"回调幅度小({pullback_pct:.1f}%)，强势整理")
            elif pullback_pct <= 10:
                confidence += 0.05
                reasons.append(f"回调{pullback_pct:.1f}%，标准N字回调")
            else:
                risks.append(f"回调{pullback_pct:.1f}%偏深，注意支撑力度")

            # 放量程度
            if vol_ratio >= 2.0:
                confidence += 0.1
                reasons.append(f"放量{vol_ratio:.1f}倍，增量资金入场明显")
            elif vol_ratio >= 1.5:
                confidence += 0.05
                reasons.append(f"量比{vol_ratio:.1f}，温和放量")

            # 板块共振
            if sector in hot_sectors:
                confidence += 0.08
                reasons.append(f"板块{sector}持续强势")

            # 均线
            ma5 = self._calc_ma(closes, 5)
            ma10 = self._calc_ma(closes, 10)
            if current_price > ma5 > ma10:
                confidence += 0.05
                reasons.append("均线多头排列")
            if current_price < ma5:
                risks.append("股价仍在MA5下方，N字确认需等突破")

            confidence = max(0.1, min(1.0, confidence))

            # 止损：涨停日最低价下方
            stop_loss = lu_low * 0.98
            # 止盈：涨停日收盘价上方10%
            take_profit = lu_price * 1.1

            signal = TradeSignal(
                code=code,
                name=name,
                strategy=self.name,
                signal_id=self.make_signal_id(code),
                signal_type=SignalType.BREAKOUT,
                entry_method=EntryMethod.突破,
                confidence=round(confidence, 2),
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                max_position_pct=self.default_position_pct,
                current_price=current_price,
                change_pct=today_change,
                sector=sector,
                sector_resonance=sector in hot_sectors,
                sentiment_phase=sentiment_phase,
                reasons=reasons,
                risks=risks,
                key_metrics={
                    "lu_price": round(lu_price, 2),
                    "lu_days_ago": pullback_days,
                    "pullback_pct": round(pullback_pct, 1),
                    "volume_ratio": round(vol_ratio, 1),
                    "today_change": round(today_change, 1),
                },
            )
            signals.append(signal)

        return signals
