# -*- coding: utf-8 -*-
"""低吸龙头战法（交易系统升级 Phase 2）

核心逻辑: 龙头第一次分歧 + 回调至均线支撑 + 缩量企稳
适用环境: 分化期、修复期
"""

from __future__ import annotations

from typing import Any, Optional

from .base_strategy import (
    BaseShortStrategy,
    TradeSignal,
    SignalType,
    EntryMethod,
)


class LowSuckLeaderStrategy(BaseShortStrategy):
    """低吸龙头战法

    选股条件:
    1. 近期有过涨停（2-5日内）的强势股
    2. 回调至MA10或MA20支撑
    3. 缩量企稳（成交量低于前5日均量）
    4. 不破前日低点（有支撑确认）
    5. 所属板块仍处于强势
    """

    name = "low_suck_leader"
    display_name = "低吸龙头"
    description = "龙头首次分歧回调至均线支撑+缩量企稳，低吸介入"
    priority = 20

    suitable_phases = ["修复期", "分化期", "高潮期"]
    unsuitable_phases = ["退潮期"]

    # 参数
    MAX_DAYS_SINCE_LIMIT_UP = 5  # 最近涨停在5日内
    MA_SUPPORT_LEVELS = [10, 20]  # 回调目标均线
    BIAS_NEAR_SUPPORT = 3.0       # 偏离支撑位不超过3%
    MAX_VOLUME_RATIO = 0.8        # 缩量（量比<0.8）

    def scan(
        self,
        market_data: dict[str, Any],
        *,
        sentiment_phase: str = "unknown",
        hot_sectors: Optional[list[str]] = None,
        **kwargs,
    ) -> list[TradeSignal]:
        """扫描低吸机会"""
        signals: list[TradeSignal] = []
        hot_sectors = hot_sectors or []

        stocks = market_data.get("stocks", {})
        limit_up_history = market_data.get("limit_up_history", {})

        for code, data in stocks.items():
            # 1. 检查近期是否有涨停
            recent_lu = limit_up_history.get(code, [])
            if not recent_lu:
                continue

            latest_lu_date = recent_lu[-1] if isinstance(recent_lu, list) else recent_lu
            # 简化：检查是否为近期强势股
            name = data.get("name", "")
            sector = data.get("sector", "")

            # 2. 获取K线数据
            bars = data.get("bars", [])
            if not bars or len(bars) < 20:
                continue

            opens, highs, lows, closes, volumes = self._extract_ohlc(bars)
            if not closes:
                continue

            current_price = closes[-1]
            current_vol = volumes[-1] if volumes else 0

            # 3. 检查是否在回调
            high_recent = max(highs[-5:]) if len(highs) >= 5 else current_price
            if current_price > high_recent * 0.97:
                continue  # 没回调，不需要低吸

            # 4. 计算均线
            ma5 = self._calc_ma(closes, 5)
            ma10 = self._calc_ma(closes, 10)
            ma20 = self._calc_ma(closes, 20)
            ma60 = self._calc_ma(closes, 60)

            # 5. 检查是否接近支撑
            nearest_support = None
            support_name = ""
            for ma_val, ma_name in [(ma10, "MA10"), (ma20, "MA20"), (ma60, "MA60")]:
                if ma_val > 0:
                    bias = abs(current_price - ma_val) / ma_val * 100
                    if bias <= self.BIAS_NEAR_SUPPORT:
                        nearest_support = ma_val
                        support_name = ma_name
                        break

            if nearest_support is None:
                continue

            # 6. 缩量检查
            vol_ratio = self._calc_volume_ratio(volumes, current_vol)
            if vol_ratio > self.MAX_VOLUME_RATIO:
                continue  # 没有缩量

            # 7. 不创新低
            low_prev = min(lows[-3:-1]) if len(lows) >= 3 else current_price
            if current_price < low_prev:
                continue  # 创新低，支撑无效

            # 8. 板块检查
            sector_resonance = sector in hot_sectors

            # 计算置信度
            confidence = 0.5
            reasons = []
            risks = []

            # 缩量加分
            if vol_ratio <= 0.5:
                confidence += 0.15
                reasons.append(f"极致缩量(量比{vol_ratio:.2f})，抛压枯竭")
            elif vol_ratio <= 0.7:
                confidence += 0.08
                reasons.append(f"缩量(量比{vol_ratio:.2f})，回调量能健康")

            # 支撑位加分
            bias = abs(current_price - nearest_support) / nearest_support * 100
            if bias <= 1.0:
                confidence += 0.1
                reasons.append(f"精确回踩{support_name}支撑({nearest_support:.2f})")
            else:
                reasons.append(f"接近{support_name}支撑({nearest_support:.2f})")

            # 不创新低加分
            if not lows or current_price <= 0:
                pass
            elif current_price > lows[-1]:
                confidence += 0.05
                reasons.append("未创新低，支撑有效")

            # 板块共振
            if sector_resonance:
                confidence += 0.1
                reasons.append(f"板块{sector}仍属强势板块")

            # 均线排列检查
            if ma5 < ma10 < ma20:
                risks.append("均线空头排列，反弹空间受限")
                confidence -= 0.1

            confidence = max(0.1, min(1.0, confidence))

            # 止损设置在支撑下方3%
            stop_loss = nearest_support * 0.97
            # 止盈目标：前高或MA5
            take_profit = max(high_recent, ma5)

            signal = TradeSignal(
                code=code,
                name=name,
                strategy=self.name,
                signal_id=self.make_signal_id(code),
                signal_type=SignalType.LOW_SUCK,
                entry_method=EntryMethod.低吸,
                confidence=round(confidence, 2),
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                max_position_pct=self.default_position_pct,
                current_price=current_price,
                sector=sector,
                sector_resonance=sector_resonance,
                sentiment_phase=sentiment_phase,
                reasons=reasons,
                risks=risks,
                key_metrics={
                    "ma5": round(ma5, 2),
                    "ma10": round(ma10, 2),
                    "ma20": round(ma20, 2),
                    "support": nearest_support,
                    "support_name": support_name,
                    "volume_ratio": round(vol_ratio, 2),
                    "bias_pct": round(bias, 2),
                },
            )
            signals.append(signal)

        return signals
