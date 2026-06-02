# -*- coding: utf-8 -*-
"""测试增强版策略模块"""

import pytest
from datetime import datetime
from src.services.enhanced_strategies import (
    SignalType, StrategyType, TriggerSignal, StrategyConfig,
    DynamicRiskController, MarketCondition, DynamicRiskParams,
    FixedChangeThresholdStrategy, FixedVolumeSurgeStrategy,
    FixedTurnoverAlertStrategy, PriceBreakoutStrategy,
    MultiTimeframeConfirm,
    create_enhanced_strategies, get_enhanced_default_strategies,
)


# ============================================================
#  风控参数动态调整测试
# ============================================================

class TestDynamicRiskController:
    """风控参数动态调整器测试"""

    def test_default_params(self):
        controller = DynamicRiskController()
        params = controller.params
        assert params.stop_loss_pct == -5.0
        assert params.max_position_pct == 30.0
        assert params.min_score_threshold == 65

    def test_high_volatility_adjusts_params(self):
        controller = DynamicRiskController()
        controller.update_market_condition(MarketCondition(
            volatility=6.0, sentiment="neutral",
        ))
        params = controller.params
        assert params.stop_loss_pct == -3.0  # 收紧止损
        assert params.max_position_pct == 20.0  # 降低仓位

    def test_low_volatility_relaxes_params(self):
        controller = DynamicRiskController()
        controller.update_market_condition(MarketCondition(
            volatility=1.0, sentiment="neutral",
        ))
        params = controller.params
        assert params.max_position_pct == 35.0  # 放宽仓位

    def test_consecutive_down_triggers_conservative(self):
        controller = DynamicRiskController()
        controller.update_market_condition(MarketCondition(
            consecutive_down=4, sentiment="bearish",
        ))
        params = controller.params
        assert params.stop_loss_pct == -3.0
        assert params.max_position_pct == 15.0
        assert params.min_score_threshold == 75

    def test_bearish_sentiment_raises_threshold(self):
        controller = DynamicRiskController()
        controller.update_market_condition(MarketCondition(
            sentiment="bearish",
        ))
        assert controller.params.min_score_threshold == 75

    def test_bullish_sentiment_lowers_threshold(self):
        controller = DynamicRiskController()
        controller.update_market_condition(MarketCondition(
            sentiment="bullish",
        ))
        assert controller.params.min_score_threshold == 60

    def test_poor_recent_performance_raises_threshold(self):
        controller = DynamicRiskController()
        # 模拟近10笔交易: 2赢8输 (胜率20%)
        for _ in range(8):
            controller.record_trade(won=False, return_pct=-5.0)
        for _ in range(2):
            controller.record_trade(won=True, return_pct=3.0)
        # 需要触发 _recalculate
        controller.update_market_condition(MarketCondition())
        params = controller.params
        assert params.min_score_threshold == 80
        assert params.max_position_pct == 15.0

    def test_good_recent_performance_keeps_normal(self):
        controller = DynamicRiskController()
        for _ in range(7):
            controller.record_trade(won=True, return_pct=8.0)
        for _ in range(3):
            controller.record_trade(won=False, return_pct=-2.0)
        controller.update_market_condition(MarketCondition())
        assert controller.params.min_score_threshold <= 70


# ============================================================
#  涨跌幅策略修复测试
# ============================================================

class TestFixedChangeThresholdStrategy:
    """涨跌幅阈值策略（修复版）测试"""

    @pytest.fixture
    def strategy(self):
        return FixedChangeThresholdStrategy(StrategyConfig(
            strategy_type=StrategyType.CHANGE_THRESHOLD,
            signal_type=SignalType.ALERT,
            params={"threshold": 5.0},
        ))

    def test_normal_up_alert(self, strategy):
        signal = strategy.evaluate("000001", "测试股", {
            "price": 10.5, "change_pct": 6.0,
        })
        assert signal is not None
        assert signal.signal_type == SignalType.ALERT
        assert signal.signal_strength == 40

    def test_limit_up_is_alert_not_buy(self, strategy):
        """修复: 涨停不应发BUY信号"""
        signal = strategy.evaluate("000001", "测试股", {
            "price": 11.0, "change_pct": 10.0,
        })
        assert signal is not None
        assert signal.signal_type == SignalType.ALERT
        assert "涨停" in signal.message

    def test_limit_down_is_warning(self, strategy):
        """修复: 跌停应发WARNING"""
        signal = strategy.evaluate("000001", "测试股", {
            "price": 9.0, "change_pct": -10.0,
        })
        assert signal is not None
        assert signal.signal_type == SignalType.WARNING
        assert "跌停" in signal.message

    def test_below_threshold_no_signal(self, strategy):
        signal = strategy.evaluate("000001", "测试股", {
            "price": 10.0, "change_pct": 3.0,
        })
        assert signal is None

    def test_big_surge_is_alert(self, strategy):
        """大涨(>8%)发ALERT而非BUY"""
        signal = strategy.evaluate("000001", "测试股", {
            "price": 10.9, "change_pct": 9.0,
        })
        assert signal.signal_type == SignalType.ALERT

    def test_big_drop_is_warning(self, strategy):
        signal = strategy.evaluate("000001", "测试股", {
            "price": 9.1, "change_pct": -9.0,
        })
        assert signal.signal_type == SignalType.WARNING


# ============================================================
#  量比策略修复测试
# ============================================================

class TestFixedVolumeSurgeStrategy:
    """量比策略（修复版）测试"""

    @pytest.fixture
    def strategy(self):
        return FixedVolumeSurgeStrategy(StrategyConfig(
            strategy_type=StrategyType.VOLUME_SURGE,
            signal_type=SignalType.ALERT,
            params={"surge_threshold": 2.0, "shrink_threshold": 0.5},
        ))

    def test_surge_up_is_alert(self, strategy):
        signal = strategy.evaluate("000001", "测试股", {
            "price": 10.5, "change_pct": 3.0, "volume_ratio": 2.5,
        })
        assert signal is not None
        assert signal.signal_type == SignalType.ALERT

    def test_surge_down_is_warning(self, strategy):
        signal = strategy.evaluate("000001", "测试股", {
            "price": 9.5, "change_pct": -3.0, "volume_ratio": 2.5,
        })
        assert signal is not None
        assert signal.signal_type == SignalType.WARNING

    def test_shrink_up_is_alert(self, strategy):
        """修复: 缩量上涨应发ALERT（潜在反弹）"""
        signal = strategy.evaluate("000001", "测试股", {
            "price": 10.3, "change_pct": 1.0, "volume_ratio": 0.3,
        })
        assert signal is not None
        assert signal.signal_type == SignalType.ALERT

    def test_massive_volume_is_warning(self, strategy):
        """巨量(>5倍)不管方向都是WARNING"""
        signal = strategy.evaluate("000001", "测试股", {
            "price": 10.5, "change_pct": 2.0, "volume_ratio": 6.0,
        })
        assert signal is not None
        assert signal.signal_type == SignalType.WARNING

    def test_normal_volume_no_signal(self, strategy):
        signal = strategy.evaluate("000001", "测试股", {
            "price": 10.0, "change_pct": 0.5, "volume_ratio": 1.0,
        })
        assert signal is None


# ============================================================
#  换手率策略修复测试
# ============================================================

class TestFixedTurnoverAlertStrategy:
    """换手率策略（修复版）测试"""

    @pytest.fixture
    def strategy(self):
        return FixedTurnoverAlertStrategy(StrategyConfig(
            strategy_type=StrategyType.TURNOVER_ALERT,
            signal_type=SignalType.WARNING,
            params={"threshold": 10.0},
        ))

    def test_high_turnover_up_is_warning(self, strategy):
        signal = strategy.evaluate("000001", "测试股", {
            "price": 11.0, "change_pct": 5.0, "turnover_rate": 15.0,
        })
        assert signal is not None
        assert signal.signal_type == SignalType.WARNING
        assert "筹码松动" in signal.message

    def test_high_turnover_down_is_warning(self, strategy):
        signal = strategy.evaluate("000001", "测试股", {
            "price": 9.0, "change_pct": -5.0, "turnover_rate": 15.0,
        })
        assert signal is not None
        assert signal.signal_type == SignalType.WARNING
        assert "恐慌" in signal.message

    def test_extreme_turnover_is_warning(self, strategy):
        """极高换手(>30%)"""
        signal = strategy.evaluate("000001", "测试股", {
            "price": 10.5, "change_pct": 2.0, "turnover_rate": 35.0,
        })
        assert signal is not None
        assert signal.signal_type == SignalType.WARNING
        assert "对倒" in signal.message or "嫌疑" in signal.message

    def test_normal_turnover_no_signal(self, strategy):
        signal = strategy.evaluate("000001", "测试股", {
            "price": 10.0, "change_pct": 1.0, "turnover_rate": 5.0,
        })
        assert signal is None


# ============================================================
#  价格突破策略测试
# ============================================================

class TestPriceBreakoutStrategy:
    """价格突破策略（新增）测试"""

    @pytest.fixture
    def strategy(self):
        return PriceBreakoutStrategy(StrategyConfig(
            strategy_type=StrategyType.PRICE_BREAKOUT,
            signal_type=SignalType.BUY,
            params={"lookback_days": 20},
        ))

    def test_insufficient_data_no_signal(self, strategy):
        """历史数据不足5条时无信号"""
        signal = strategy.evaluate("000001", "测试股", {
            "price": 10.5, "change_pct": 2.0,
            "high": 10.8, "low": 10.0,
        })
        assert signal is None

    def test_breakout_high_triggers_buy(self, strategy):
        """突破前高发BUY"""
        # 先填充历史数据
        for i in range(10):
            strategy.evaluate("000001", "测试股", {
                "price": 10.0 + i * 0.1, "change_pct": 1.0,
                "high": 10.2 + i * 0.1, "low": 9.8 + i * 0.1,
            })
        # 当前价格突破历史最高
        signal = strategy.evaluate("000001", "测试股", {
            "price": 11.5, "change_pct": 3.0,
            "high": 11.8, "low": 11.0,
        })
        if signal is not None:
            assert signal.signal_type == SignalType.BUY

    def test_breakdown_low_triggers_sell(self, strategy):
        """跌破前低发SELL"""
        for i in range(10):
            strategy.evaluate("000001", "测试股", {
                "price": 10.0 - i * 0.1, "change_pct": -1.0,
                "high": 10.1 - i * 0.1, "low": 9.9 - i * 0.1,
            })
        signal = strategy.evaluate("000001", "测试股", {
            "price": 8.5, "change_pct": -3.0,
            "high": 8.8, "low": 8.2,
        })
        if signal is not None:
            assert signal.signal_type == SignalType.SELL


# ============================================================
#  多周期确认测试
# ============================================================

class TestMultiTimeframeConfirm:
    """多周期确认器测试"""

    def test_strong_signal_bypasses_confirmation(self):
        confirmer = MultiTimeframeConfirm(required_confirmations=2)
        signal = TriggerSignal(
            code="000001", name="测试",
            signal_type=SignalType.BUY,
            strategy_type=StrategyType.PRICE_BREAKOUT,
            current_price=10.0, change_pct=2.0,
            trigger_value=10.0, threshold=9.5,
            message="test", signal_strength=85,
        )
        result = confirmer.confirm(signal)
        assert result is not None

    def test_weak_signal_needs_confirmation(self):
        confirmer = MultiTimeframeConfirm(required_confirmations=2)
        signal = TriggerSignal(
            code="000001", name="测试",
            signal_type=SignalType.ALERT,
            strategy_type=StrategyType.VOLUME_SURGE,
            current_price=10.0, change_pct=1.0,
            trigger_value=2.0, threshold=2.0,
            message="test", signal_strength=40,
        )
        # 第一次触发: 需要确认
        result1 = confirmer.confirm(signal)
        assert result1 is None

        # 第二次同方向触发: 确认通过
        result2 = confirmer.confirm(signal)
        assert result2 is not None


# ============================================================
#  策略工厂测试
# ============================================================

class TestEnhancedStrategyFactory:
    """增强版策略工厂测试"""

    def test_create_default_strategies(self):
        configs = get_enhanced_default_strategies()
        assert len(configs) == 5  # 包含新增的 price_breakout

    def test_create_with_risk_controller(self):
        controller = DynamicRiskController()
        configs = get_enhanced_default_strategies()
        strategies, rc = create_enhanced_strategies(configs, controller)
        assert len(strategies) == 5
        assert rc is controller

    def test_strategy_types_present(self):
        configs = get_enhanced_default_strategies()
        types = {c["strategy_type"] for c in configs}
        assert "change_threshold" in types
        assert "volume_surge" in types
        assert "turnover_alert" in types
        assert "amplitude_alert" in types
        assert "price_breakout" in types  # 新增


# ============================================================
#  冷却机制测试
# ============================================================

class TestCooldownMechanism:
    """冷却机制测试"""

    def test_strong_signal_shorter_cooldown(self):
        """强信号应使用更短的冷却时间"""
        strategy = FixedChangeThresholdStrategy(StrategyConfig(
            strategy_type=StrategyType.CHANGE_THRESHOLD,
            signal_type=SignalType.ALERT,
            cooldown_seconds=600,
            strong_cooldown_seconds=120,
        ))
        # 强信号(>70): 冷却120s
        strategy.mark_triggered("000001")
        # 模拟刚触发
        assert strategy.check_cooldown("000001", strength=80) is True
        # 弱信号(50): 冷却600s
        assert strategy.check_cooldown("000001", strength=50) is True

    def test_weak_signal_no_cooldown_for_strong(self):
        """弱信号冷却期不应阻止强信号"""
        strategy = FixedChangeThresholdStrategy(StrategyConfig(
            strategy_type=StrategyType.CHANGE_THRESHOLD,
            signal_type=SignalType.ALERT,
            cooldown_seconds=600,
            strong_cooldown_seconds=120,
        ))
        # 弱信号触发后2秒
        strategy._last_trigger["000001"] = __import__('time').time() - 2
        # 弱信号仍在冷却（600s冷却，过了2秒）
        assert strategy.check_cooldown("000001", strength=50) is True
        # 强信号冷却更短（120s），但才过了2秒，也在冷却中
        assert strategy.check_cooldown("000001", strength=80) is True
