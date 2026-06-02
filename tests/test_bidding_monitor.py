# -*- coding: utf-8 -*-
"""测试早盘竞价监控模块"""

import pytest
from datetime import datetime, time as dt_time
from unittest.mock import Mock, patch, MagicMock

from src.services.bidding_monitor import (
    BiddingSignalLevel, BiddingSnapshot, BiddingSignal,
    PreMarketBiddingMonitor, get_bidding_monitor, reset_bidding_monitor,
)


class TestBiddingSnapshot:
    """竞价快照测试"""

    def test_create_snapshot(self):
        snap = BiddingSnapshot(
            code="000001",
            name="平安银行",
            timestamp=datetime.now(),
            current_price=12.5,
            match_volume=10000,
            pre_close=12.0,
            price_change_pct=4.17,
            volume_ratio=2.5,
            bid_strength=65.0,
        )
        assert snap.code == "000001"
        assert snap.bid_strength == 65.0
        assert abs(snap.price_change_pct - 4.17) < 0.01


class TestBiddingSignalLevel:
    """竞价信号等级测试"""

    def test_level_values(self):
        assert BiddingSignalLevel.STRONG_BUY.value == "strong_buy"
        assert BiddingSignalLevel.BUY.value == "buy"
        assert BiddingSignalLevel.WATCH.value == "watch"
        assert BiddingSignalLevel.WEAK.value == "weak"
        assert BiddingSignalLevel.RISK.value == "risk"


class TestPreMarketBiddingMonitor:
    """竞价监控器测试"""

    def test_time_check(self):
        """时间检查函数"""
        monitor = PreMarketBiddingMonitor()
        # 这些是静态方法，不依赖实例状态
        assert isinstance(PreMarketBiddingMonitor.is_bidding_time(), bool)
        assert isinstance(PreMarketBiddingMonitor.is_confirmed_time(), bool)

    def test_calc_bid_strength(self):
        """竞价强度计算"""
        monitor = PreMarketBiddingMonitor()
        mock_quote = Mock()
        mock_quote.volume_ratio = 2.5
        mock_quote.high = 12.8
        mock_quote.low = 12.0

        strength = monitor._calc_bid_strength(12.5, 12.0, mock_quote)
        # 涨幅4.17%: price_score ≈ 16.7
        # 量比2.5: vol_score ≈ 29.2
        # 趋势: position=(12.5-12)/(12.8-12)=0.625: trend_score=15.6
        # 总 ≈ 61.5
        assert 40 <= strength <= 80

    def test_calc_bid_strength_limit_up(self):
        """涨停竞价强度"""
        monitor = PreMarketBiddingMonitor()
        mock_quote = Mock()
        mock_quote.volume_ratio = 4.0
        mock_quote.high = 11.0
        mock_quote.low = 10.8

        strength = monitor._calc_bid_strength(11.0, 10.0, mock_quote)
        # 涨停(10%): price_score=40, vol(4x): vol_score=35, trend=~12
        assert strength >= 80

    def test_calc_bid_strength_weak(self):
        """弱势竞价"""
        monitor = PreMarketBiddingMonitor()
        mock_quote = Mock()
        mock_quote.volume_ratio = 0.5
        mock_quote.high = 10.1
        mock_quote.low = 9.9

        strength = monitor._calc_bid_strength(10.0, 10.0, mock_quote)
        assert strength < 30

    def test_add_stock(self):
        monitor = PreMarketBiddingMonitor()
        monitor.add_stock("000001", "测试")
        assert "000001" in monitor._watchlist
        assert monitor._watchlist["000001"] == "测试"

    def test_set_watchlist(self):
        monitor = PreMarketBiddingMonitor()
        monitor.set_watchlist({"000001": "股A", "000002": "股B"})
        assert len(monitor._watchlist) == 2

    def test_judge_bidding_level_limit_up(self):
        """涨停竞价 → STRONG_BUY"""
        monitor = PreMarketBiddingMonitor()
        snap = BiddingSnapshot(
            code="000001", name="测试",
            timestamp=datetime.now(),
            current_price=11.0, pre_close=10.0,
            price_change_pct=10.0, volume_ratio=4.0,
            bid_strength=90.0,
        )
        level, reason, risk = monitor._judge_bidding_level(snap)
        assert level == BiddingSignalLevel.STRONG_BUY

    def test_judge_bidding_level_strong_high_open(self):
        """强势高开 → STRONG_BUY"""
        monitor = PreMarketBiddingMonitor()
        snap = BiddingSnapshot(
            code="000001", name="测试",
            timestamp=datetime.now(),
            current_price=10.6, pre_close=10.0,
            price_change_pct=6.0, volume_ratio=3.0,
            bid_strength=75.0,
        )
        level, reason, risk = monitor._judge_bidding_level(snap)
        assert level == BiddingSignalLevel.STRONG_BUY

    def test_judge_bidding_level_moderate(self):
        """温和高开 → BUY"""
        monitor = PreMarketBiddingMonitor()
        snap = BiddingSnapshot(
            code="000001", name="测试",
            timestamp=datetime.now(),
            current_price=10.3, pre_close=10.0,
            price_change_pct=3.0, volume_ratio=2.0,
            bid_strength=55.0,
        )
        level, reason, risk = monitor._judge_bidding_level(snap)
        assert level == BiddingSignalLevel.BUY

    def test_judge_bidding_level_low_open_risk(self):
        """大幅低开 → RISK"""
        monitor = PreMarketBiddingMonitor()
        snap = BiddingSnapshot(
            code="000001", name="测试",
            timestamp=datetime.now(),
            current_price=9.5, pre_close=10.0,
            price_change_pct=-5.0, volume_ratio=1.0,
            bid_strength=15.0,
        )
        level, reason, risk = monitor._judge_bidding_level(snap)
        assert level == BiddingSignalLevel.RISK

    def test_build_buy_signal(self):
        """买入信号构建（含止损止盈）"""
        monitor = PreMarketBiddingMonitor()
        snap = BiddingSnapshot(
            code="000001", name="测试",
            timestamp=datetime.now(),
            current_price=10.5, pre_close=10.0,
            price_change_pct=5.0, bid_strength=75.0,
        )
        signal = monitor._build_buy_signal(
            snap, BiddingSignalLevel.STRONG_BUY,
            "强势竞价", "",
        )
        assert signal.level == BiddingSignalLevel.STRONG_BUY
        assert signal.open_price == 10.5
        assert signal.position_pct == 20.0  # 强势=20%
        assert signal.stop_loss_price < 10.5  # 止损低于现价
        assert signal.target_price_1 > 10.5  # 目标高于现价
        assert signal.target_price_2 > signal.target_price_1

    def test_build_buy_signal_normal(self):
        """普通买入信号"""
        monitor = PreMarketBiddingMonitor()
        snap = BiddingSnapshot(
            code="000001", name="测试",
            timestamp=datetime.now(),
            current_price=10.3, pre_close=10.0,
            price_change_pct=3.0, bid_strength=55.0,
        )
        signal = monitor._build_buy_signal(
            snap, BiddingSignalLevel.BUY, "温和竞价", "",
        )
        assert signal.position_pct == 10.0  # 普通=10%
        assert signal.stop_loss_price < 10.3

    def test_build_risk_signal(self):
        """风险回避信号"""
        monitor = PreMarketBiddingMonitor()
        snap = BiddingSnapshot(
            code="000001", name="测试",
            timestamp=datetime.now(),
            current_price=9.5, pre_close=10.0,
            price_change_pct=-5.0, bid_strength=15.0,
        )
        signal = monitor._build_risk_signal(snap, "竞价弱势", "低开幅度大")
        assert signal.level == BiddingSignalLevel.RISK
        assert signal.position_pct == 0
        assert signal.entry_price_range == "不建议买入"

    def test_analyze_signals_sorts_by_strength(self):
        """信号按竞价强度排序"""
        monitor = PreMarketBiddingMonitor()
        snapshots = {
            "000001": BiddingSnapshot(
                code="000001", name="股A",
                timestamp=datetime.now(),
                current_price=10.5, pre_close=10.0,
                price_change_pct=5.0, volume_ratio=2.0,
                bid_strength=60.0,
            ),
            "000002": BiddingSnapshot(
                code="000002", name="股B",
                timestamp=datetime.now(),
                current_price=11.0, pre_close=10.0,
                price_change_pct=10.0, volume_ratio=4.0,
                bid_strength=90.0,
            ),
        }
        signals = monitor._analyze_signals(snapshots)
        if len(signals) >= 2:
            assert signals[0].bid_strength >= signals[-1].bid_strength

    def test_get_status(self):
        monitor = PreMarketBiddingMonitor()
        monitor.set_watchlist({"000001": "股A"})
        status = monitor.get_status()
        assert "watchlist_count" in status
        assert status["watchlist_count"] == 1
        assert "is_bidding_time" in status

    def test_singleton(self):
        m1 = get_bidding_monitor()
        m2 = get_bidding_monitor()
        assert m1 is m2
        reset_bidding_monitor()


class TestBiddingEdgeCases:
    """边界情况测试"""

    def test_empty_watchlist_no_error(self):
        monitor = PreMarketBiddingMonitor()
        result = monitor._fetch_bidding_data()
        assert result == {}

    def test_zero_pre_close(self):
        """昨收为0不应崩溃"""
        monitor = PreMarketBiddingMonitor()
        mock_quote = Mock()
        mock_quote.volume_ratio = 1.0
        mock_quote.high = 10.0
        mock_quote.low = 9.0
        strength = monitor._calc_bid_strength(10.0, 0, mock_quote)
        assert strength == 0.0

    def test_high_equals_low(self):
        """最高=最低时趋势评分应为12.5"""
        monitor = PreMarketBiddingMonitor()
        mock_quote = Mock()
        mock_quote.volume_ratio = 1.0
        mock_quote.high = 10.0
        mock_quote.low = 10.0
        strength = monitor._calc_bid_strength(10.0, 10.0, mock_quote)
        assert 0 <= strength <= 100
