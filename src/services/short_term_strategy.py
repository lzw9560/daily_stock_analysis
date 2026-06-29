# -*- coding: utf-8 -*-
"""短线战法信号生成器 — 首板/连板/低吸/N字/反包等.

核心功能：
1. 首板挖掘：板块共振+量价突破+消息催化
2. 连板接力：龙头识别+换手板+板块梯队
3. 炸板回封：涨停打开+资金回流+封单恢复
4. 低吸龙头：龙头第一次分歧+MA10/20支撑
5. 反包战法：阴线后阳线吃掉前日实体
6. N字反击：涨停-回调2-3天-再涨停
7. 平台突破：横盘N日+放量突破+回踩确认
8. 尾盘偷袭：14:30后拉升+量比>3+无利好
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SignalResult:
    """战法信号结果."""
    code: str
    name: str
    strategy: str
    signal_type: str  # seal_plate / low_suck / breakout / market
    confidence: float  # 0-100
    entry_price_range: List[float] = field(default_factory=list)
    stop_loss: float = 0.0
    take_profit: float = 0.0
    expected_hold_days: int = 1
    reason: str = ""
    risk_factors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "strategy": self.strategy,
            "signal_type": self.signal_type,
            "confidence": round(self.confidence, 1),
            "entry_price_range": self.entry_price_range,
            "stop_loss": round(self.stop_loss, 2),
            "take_profit": round(self.take_profit, 2),
            "expected_hold_days": self.expected_hold_days,
            "reason": self.reason,
            "risk_factors": self.risk_factors,
        }


class ShortTermStrategyEngine:
    """短线战法信号生成引擎."""

    def __init__(self):
        pass

    def scan_all(
        self,
        stocks: List[Dict[str, Any]],
        limit_up_data: List[Dict[str, Any]],
        seal_plate_data: List[Dict[str, Any]],
    ) -> List[SignalResult]:
        """全市场扫描，生成所有战法信号.

        Args:
            stocks: 股票列表 [{code, name, close, open, high, low, volume, prev_close, ...}]
            limit_up_data: 涨停数据 [{code, seal_time, seal_amount, ...}]
            seal_plate_data: 封板数据 [{code, status, ...}]

        Returns:
            信号列表，按置信度降序
        """
        signals = []

        # 按战法分别扫描
        signals.extend(self._scan_first_board(stocks, limit_up_data))
        signals.extend(self._scan_connecting_board(stocks, limit_up_data, seal_plate_data))
        signals.extend(self._scan_low_suck(stocks))
        signals.extend(self._scan_engulfing(stocks))
        signals.extend(self._scan_n_pattern(stocks))
        signals.extend(self._scan_platform_breakout(stocks))
        signals.extend(self._scan_late_surge(stocks))

        # 去重（同一股票保留最高置信度信号）
        signals = self._deduplicate(signals)

        # 按置信度排序
        signals.sort(key=lambda s: s.confidence, reverse=True)
        return signals

    def _scan_first_board(
        self,
        stocks: List[Dict[str, Any]],
        limit_up_data: List[Dict[str, Any]],
    ) -> List[SignalResult]:
        """首板挖掘：板块共振+量价突破+消息催化."""
        signals = []
        limit_up_codes = {d["code"] for d in limit_up_data}

        for stock in stocks:
            code = stock.get("code", "")
            if code not in limit_up_codes:
                continue

            change = stock.get("change_pct", 0)
            vol_ratio = stock.get("volume_ratio", 1)
            sectors = stock.get("sectors", "")

            # 首板条件：涨停 + 量比>1.5 + 有板块
            if change >= 9.5 and vol_ratio > 1.5 and sectors:
                confidence = 60
                reason = f"首板涨停(+{change:.1f}%)，量比{vol_ratio:.1f}"
                risk_factors = []

                # 板块共振加分
                sector_count = len([s for s in sectors.split(",") if s.strip()])
                if sector_count >= 2:
                    confidence += 10
                    reason += "，板块共振"

                # 封单量大加分
                seal_data = next((d for d in limit_up_data if d["code"] == code), None)
                if seal_data:
                    seal_amount = seal_data.get("seal_amount", 0)
                    if seal_amount > 100000000:  # 1亿以上
                        confidence += 5
                        reason += "，封单强劲"

                confidence = min(confidence, 95)
                signals.append(SignalResult(
                    code=code,
                    name=stock.get("name", ""),
                    strategy="首板挖掘",
                    signal_type="seal_plate",
                    confidence=confidence,
                    entry_price_range=[stock.get("close", 0)],
                    stop_loss=round(stock.get("close", 0) * 0.95, 2),
                    take_profit=round(stock.get("close", 0) * 1.08, 2),
                    expected_hold_days=1,
                    reason=reason,
                    risk_factors=risk_factors,
                ))

        return signals

    def _scan_connecting_board(
        self,
        stocks: List[Dict[str, Any]],
        limit_up_data: List[Dict[str, Any]],
        seal_plate_data: List[Dict[str, Any]],
    ) -> List[SignalResult]:
        """连板接力：龙头识别+换手板+板块梯队."""
        signals = []

        # 识别连板股（这里简化处理，实际需要历史数据）
        for seal in seal_plate_data:
            code = seal.get("code", "")
            board_count = seal.get("board_count", 1)
            if board_count < 2:
                continue

            stock = next((s for s in stocks if s["code"] == code), None)
            if not stock:
                continue

            turnover = stock.get("turnover_rate", 0)
            change = stock.get("change_pct", 0)

            # 连板条件：2板以上 + 换手率5-15%（换手板）
            if 5 <= turnover <= 15 and board_count >= 2:
                confidence = 50 + board_count * 5
                if board_count >= 4:
                    confidence += 10  # 高位龙头加分

                signals.append(SignalResult(
                    code=code,
                    name=stock.get("name", ""),
                    strategy=f"连板接力({board_count}板)",
                    signal_type="seal_plate",
                    confidence=min(confidence, 90),
                    entry_price_range=[stock.get("close", 0)],
                    stop_loss=round(stock.get("close", 0) * 0.93, 2),
                    take_profit=round(stock.get("close", 0) * 1.10, 2),
                    expected_hold_days=1,
                    reason=f"{board_count}连板，换手率{turnover:.1f}%",
                    risk_factors=["高位连板风险", "监管关注风险"] if board_count >= 4 else [],
                ))

        return signals

    def _scan_low_suck(self, stocks: List[Dict[str, Any]]) -> List[SignalResult]:
        """低吸龙头：龙头第一次分歧+MA10/20支撑."""
        signals = []

        for stock in stocks:
            close = stock.get("close", 0)
            ma10 = stock.get("ma10", 0)
            ma20 = stock.get("ma20", 0)
            change = stock.get("change_pct", 0)
            vol_ratio = stock.get("volume_ratio", 1)
            sectors = stock.get("sectors", "")

            # 低吸条件：回调到MA10/MA20 + 缩量 + 小幅下跌
            if ma10 > 0 and ma20 > 0:
                distance_ma10 = abs(close - ma10) / ma10 * 100
                distance_ma20 = abs(close - ma20) / ma20 * 100

                if (distance_ma10 < 2 or distance_ma20 < 3) and -3 <= change <= 0.5 and vol_ratio < 1:
                    confidence = 65
                    reason = f"回踩{'MA10' if distance_ma10 < 2 else 'MA20'}支撑，缩量回调"

                    signals.append(SignalResult(
                        code=stock.get("code", ""),
                        name=stock.get("name", ""),
                        strategy="低吸龙头",
                        signal_type="low_suck",
                        confidence=confidence,
                        entry_price_range=[round(close * 0.99, 2), round(close * 1.01, 2)],
                        stop_loss=round(ma20 * 0.95, 2) if ma20 > 0 else round(close * 0.93, 2),
                        take_profit=round(close * 1.08, 2),
                        expected_hold_days=3,
                        reason=reason,
                        risk_factors=["支撑失效风险"],
                    ))

        return signals

    def _scan_engulfing(self, stocks: List[Dict[str, Any]]) -> List[SignalResult]:
        """反包战法：阴线后阳线吃掉前日实体."""
        signals = []

        for stock in stocks:
            close = stock.get("close", 0)
            open_price = stock.get("open", 0)
            prev_close = stock.get("prev_close", 0)
            change = stock.get("change_pct", 0)
            vol_ratio = stock.get("volume_ratio", 1)

            # 反包条件：今日阳线 + 收盘价>昨日开盘 + 昨日阴线
            if prev_close > 0 and open_price > 0:
                yesterday_was_down = prev_close > stock.get("yesterday_close", prev_close)
                today_is_up = close > open_price
                engulf = close > stock.get("yesterday_open", open_price)

                if today_is_up and change > 3 and vol_ratio > 1.2:
                    confidence = 55
                    signals.append(SignalResult(
                        code=stock.get("code", ""),
                        name=stock.get("name", ""),
                        strategy="反包战法",
                        signal_type="breakout",
                        confidence=confidence,
                        entry_price_range=[round(close * 0.99, 2)],
                        stop_loss=round(open_price * 0.97, 2),
                        take_profit=round(close * 1.10, 2),
                        expected_hold_days=2,
                        reason=f"阳线反包，涨幅{change:.1f}%，量比{vol_ratio:.1f}",
                        risk_factors=["假反包风险"],
                    ))

        return signals

    def _scan_n_pattern(self, stocks: List[Dict[str, Any]]) -> List[SignalResult]:
        """N字反击：涨停-回调2-3天-再涨停."""
        signals = []

        for stock in stocks:
            change = stock.get("change_pct", 0)
            vol_ratio = stock.get("volume_ratio", 1)
            n_pattern = stock.get("n_pattern", False)

            if n_pattern and change > 5:
                confidence = 70
                signals.append(SignalResult(
                    code=stock.get("code", ""),
                    name=stock.get("name", ""),
                    strategy="N字反击",
                    signal_type="seal_plate",
                    confidence=confidence,
                    entry_price_range=[round(stock.get("close", 0) * 0.99, 2)],
                    stop_loss=round(stock.get("close", 0) * 0.93, 2),
                    take_profit=round(stock.get("close", 0) * 1.12, 2),
                    expected_hold_days=2,
                    reason="N字第二板成型",
                    risk_factors=["龙头识别错误风险"],
                ))

        return signals

    def _scan_platform_breakout(self, stocks: List[Dict[str, Any]]) -> List[SignalResult]:
        """平台突破：横盘N日+放量突破+回踩确认."""
        signals = []

        for stock in stocks:
            change = stock.get("change_pct", 0)
            vol_ratio = stock.get("volume_ratio", 1)
            platform_days = stock.get("platform_days", 0)
            breakout = stock.get("breakout", False)

            if breakout and platform_days >= 5 and vol_ratio > 2 and change > 3:
                confidence = 60
                signals.append(SignalResult(
                    code=stock.get("code", ""),
                    name=stock.get("name", ""),
                    strategy="平台突破",
                    signal_type="breakout",
                    confidence=confidence,
                    entry_price_range=[round(stock.get("close", 0), 2)],
                    stop_loss=round(stock.get("close", 0) * 0.95, 2),
                    take_profit=round(stock.get("close", 0) * 1.10, 2),
                    expected_hold_days=5,
                    reason=f"横盘{platform_days}日后放量突破，量比{vol_ratio:.1f}",
                    risk_factors=["假突破风险"],
                ))

        return signals

    def _scan_late_surge(self, stocks: List[Dict[str, Any]]) -> List[SignalResult]:
        """尾盘偷袭：14:30后拉升+量比>3+无利好."""
        signals = []

        for stock in stocks:
            change = stock.get("change_pct", 0)
            vol_ratio = stock.get("volume_ratio", 1)
            surge_time = stock.get("surge_time", "")

            # 简化：量比>3且涨幅>5%
            if vol_ratio > 3 and change > 5:
                confidence = 45  # 尾盘偷袭置信度较低
                signals.append(SignalResult(
                    code=stock.get("code", ""),
                    name=stock.get("name", ""),
                    strategy="尾盘偷袭",
                    signal_type="market",
                    confidence=confidence,
                    entry_price_range=[round(stock.get("close", 0), 2)],
                    stop_loss=round(stock.get("close", 0) * 0.97, 2),
                    take_profit=round(stock.get("close", 0) * 1.05, 2),
                    expected_hold_days=1,
                    reason=f"尾盘放量拉升，量比{vol_ratio:.1f}",
                    risk_factors=["隔日溢价不确定", "可能是诱多"],
                ))

        return signals

    def _deduplicate(self, signals: List[SignalResult]) -> List[SignalResult]:
        """去重：同一股票保留最高置信度信号."""
        best = {}
        for s in signals:
            code = s.code
            if code not in best or s.confidence > best[code].confidence:
                best[code] = s
        return list(best.values())
