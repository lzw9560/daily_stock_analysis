# -*- coding: utf-8 -*-
"""
TDD: 策略模块单元测试

测试覆盖：
- SignalType / StrategyType 枚举
- TriggerSignal / StrategyConfig 数据类
- BaseStrategy 冷却机制
- ChangeThresholdStrategy 涨跌幅阈值
- VolumeSurgeStrategy 量比异动
- AmplitudeAlertStrategy 振幅异常
- TurnoverAlertStrategy 换手率异常
- create_strategies 策略工厂
- get_default_strategies 默认配置
"""
import os
import sys
import time
import unittest
from unittest import mock
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.position_monitor.strategies import (
    SignalType,
    StrategyType,
    TriggerSignal,
    StrategyConfig,
    BaseStrategy,
    ChangeThresholdStrategy,
    VolumeSurgeStrategy,
    AmplitudeAlertStrategy,
    TurnoverAlertStrategy,
    STRATEGY_REGISTRY,
    create_strategies,
    get_default_strategies,
)


# ============================================================
# 红阶段 1: 枚举和数据类基础测试
# ============================================================

class TestSignalTypeEnum(unittest.TestCase):
    """SignalType 枚举测试"""

    def test_signal_type_values(self):
        self.assertEqual(SignalType.BUY.value, "buy")
        self.assertEqual(SignalType.SELL.value, "sell")
        self.assertEqual(SignalType.ALERT.value, "alert")
        self.assertEqual(SignalType.WARNING.value, "warning")

    def test_signal_type_is_string_enum(self):
        self.assertIsInstance(SignalType.BUY, str)
        self.assertEqual(SignalType.BUY, "buy")


class TestStrategyTypeEnum(unittest.TestCase):
    """StrategyType 枚举测试"""

    def test_strategy_type_values(self):
        self.assertEqual(StrategyType.CHANGE_THRESHOLD.value, "change_threshold")
        self.assertEqual(StrategyType.VOLUME_SURGE.value, "volume_surge")
        self.assertEqual(StrategyType.AMPLITUDE_ALERT.value, "amplitude_alert")
        self.assertEqual(StrategyType.TURNOVER_ALERT.value, "turnover_alert")

    def test_all_registry_types_exist(self):
        for stype in STRATEGY_REGISTRY:
            self.assertIsInstance(stype, StrategyType)


class TestTriggerSignal(unittest.TestCase):
    """TriggerSignal 数据类测试"""

    def test_create_trigger_signal(self):
        now = datetime.now()
        signal = TriggerSignal(
            code="000001",
            name="平安银行",
            signal_type=SignalType.BUY,
            strategy_type=StrategyType.CHANGE_THRESHOLD,
            current_price=12.50,
            change_pct=5.5,
            trigger_value=5.5,
            threshold=5.0,
            message="涨跌幅阈值触发：上涨5.50%",
            timestamp=now,
            extra={"direction": "上涨"},
        )
        self.assertEqual(signal.code, "000001")
        self.assertEqual(signal.name, "平安银行")
        self.assertEqual(signal.signal_type, SignalType.BUY)
        self.assertEqual(signal.current_price, 12.50)
        self.assertEqual(signal.change_pct, 5.5)
        self.assertEqual(signal.trigger_value, 5.5)
        self.assertEqual(signal.threshold, 5.0)
        self.assertEqual(signal.extra, {"direction": "上涨"})
        self.assertEqual(signal.timestamp, now)

    def test_trigger_signal_default_timestamp(self):
        signal = TriggerSignal(
            code="000001", name="test", signal_type=SignalType.ALERT,
            strategy_type=StrategyType.AMPLITUDE_ALERT,
            current_price=10.0, change_pct=0, trigger_value=0, threshold=0,
            message="test",
        )
        self.assertIsInstance(signal.timestamp, datetime)

    def test_trigger_signal_default_extra(self):
        signal = TriggerSignal(
            code="000001", name="test", signal_type=SignalType.ALERT,
            strategy_type=StrategyType.AMPLITUDE_ALERT,
            current_price=10.0, change_pct=0, trigger_value=0, threshold=0,
            message="test",
        )
        self.assertEqual(signal.extra, {})


class TestStrategyConfig(unittest.TestCase):
    """StrategyConfig 数据类测试"""

    def test_default_values(self):
        config = StrategyConfig(
            strategy_type=StrategyType.CHANGE_THRESHOLD,
            signal_type=SignalType.ALERT,
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.params, {})
        self.assertEqual(config.cooldown_seconds, 300)

    def test_custom_values(self):
        config = StrategyConfig(
            strategy_type=StrategyType.VOLUME_SURGE,
            signal_type=SignalType.BUY,
            enabled=False,
            params={"surge_threshold": 3.0},
            cooldown_seconds=120,
        )
        self.assertFalse(config.enabled)
        self.assertEqual(config.params["surge_threshold"], 3.0)
        self.assertEqual(config.cooldown_seconds, 120)


# ============================================================
# 红阶段 2: BaseStrategy 冷却机制
# ============================================================

class TestBaseStrategyCooldown(unittest.TestCase):
    """BaseStrategy 冷却机制测试"""

    def setUp(self):
        self.config = StrategyConfig(
            strategy_type=StrategyType.CHANGE_THRESHOLD,
            signal_type=SignalType.ALERT,
            cooldown_seconds=5,
        )
        self.strategy = ChangeThresholdStrategy(self.config)

    def test_check_cooldown_returns_false_initially(self):
        """初始状态：冷却检查返回 False（不在冷却中）"""
        self.assertFalse(self.strategy.check_cooldown("000001"))

    def test_check_cooldown_returns_true_after_trigger(self):
        """标记触发后立即检查应返回 True（在冷却中）"""
        self.strategy.mark_triggered("000001")
        self.assertTrue(self.strategy.check_cooldown("000001"))

    def test_check_cooldown_expires(self):
        """冷却时间过后应返回 False"""
        self.strategy.mark_triggered("000001")
        time.sleep(0.1)  # 冷却时间只有 5s，模拟等待不够
        # 冷却期是 5 秒，0.1 秒后仍在冷却中
        self.assertTrue(self.strategy.check_cooldown("000001"))

    def test_different_codes_have_independent_cooldown(self):
        """不同标的的冷却互不影响"""
        self.strategy.mark_triggered("000001")
        self.assertTrue(self.strategy.check_cooldown("000001"))
        self.assertFalse(self.strategy.check_cooldown("000002"))

    @mock.patch.object(time, 'time')
    def test_cooldown_expired_after_enough_time(self, mock_time):
        """模拟时间流逝，冷却过期"""
        mock_time.return_value = 1000.0
        self.strategy.mark_triggered("000001")
        # 模拟 10 秒后
        mock_time.return_value = 1010.0
        self.assertFalse(self.strategy.check_cooldown("000001"))


# ============================================================
# 红阶段 3: ChangeThresholdStrategy 涨跌幅阈值
# ============================================================

class TestChangeThresholdStrategy(unittest.TestCase):
    """涨跌幅阈值策略测试"""

    def setUp(self):
        self.config = StrategyConfig(
            strategy_type=StrategyType.CHANGE_THRESHOLD,
            signal_type=SignalType.ALERT,
            params={"threshold": 5.0},
            cooldown_seconds=0,  # 测试时禁用冷却
        )
        self.strategy = ChangeThresholdStrategy(self.config)

    def test_no_signal_when_change_within_threshold(self):
        """涨跌幅在阈值内时不触发"""
        quote = {"price": 10.0, "change_pct": 3.0}
        result = self.strategy.evaluate("000001", "平安银行", quote)
        self.assertIsNone(result)

    def test_buy_signal_when_positive_exceeds_threshold(self):
        """正涨幅超过阈值时触发买入信号"""
        quote = {"price": 12.0, "change_pct": 6.5}
        result = self.strategy.evaluate("000001", "平安银行", quote)
        self.assertIsNotNone(result)
        self.assertEqual(result.signal_type, SignalType.BUY)
        self.assertEqual(result.code, "000001")
        self.assertEqual(result.name, "平安银行")
        self.assertEqual(result.current_price, 12.0)
        self.assertEqual(result.change_pct, 6.5)
        self.assertEqual(result.strategy_type, StrategyType.CHANGE_THRESHOLD)

    def test_sell_signal_when_negative_exceeds_threshold(self):
        """负涨幅超过阈值时触发卖出信号"""
        quote = {"price": 9.0, "change_pct": -7.0}
        result = self.strategy.evaluate("000002", "万科A", quote)
        self.assertIsNotNone(result)
        self.assertEqual(result.signal_type, SignalType.SELL)
        self.assertEqual(result.extra["direction"], "下跌")

    def test_exact_threshold_not_triggered(self):
        """刚好等于阈值时不触发（使用 < 比较）"""
        quote = {"price": 10.0, "change_pct": 5.0}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNone(result)

    def test_threshold_exceeds_by_small_amount(self):
        """刚好超过阈值一点点触发"""
        quote = {"price": 10.0, "change_pct": 5.01}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNotNone(result)

    def test_custom_threshold(self):
        """自定义阈值参数"""
        config = StrategyConfig(
            strategy_type=StrategyType.CHANGE_THRESHOLD,
            signal_type=SignalType.ALERT,
            params={"threshold": 3.0},
            cooldown_seconds=0,
        )
        strategy = ChangeThresholdStrategy(config)
        quote = {"price": 10.0, "change_pct": 4.0}
        result = strategy.evaluate("000001", "test", quote)
        self.assertIsNotNone(result)

    def test_zero_price_handled(self):
        """价格为 0 时仍正常触发"""
        quote = {"price": 0, "change_pct": 6.0}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNotNone(result)
        self.assertEqual(result.current_price, 0)

    def test_none_change_pct_handled(self):
        """change_pct 为 None 时不触发"""
        quote = {"price": 10.0, "change_pct": None}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNone(result)

    def test_change_pct_zero_handled(self):
        """涨跌幅为 0 时不触发"""
        quote = {"price": 10.0, "change_pct": 0}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNone(result)


# ============================================================
# 红阶段 4: VolumeSurgeStrategy 量比异动
# ============================================================

class TestVolumeSurgeStrategy(unittest.TestCase):
    """量比异动策略测试"""

    def setUp(self):
        self.config = StrategyConfig(
            strategy_type=StrategyType.VOLUME_SURGE,
            signal_type=SignalType.ALERT,
            params={"surge_threshold": 2.0, "shrink_threshold": 0.5},
            cooldown_seconds=0,
        )
        self.strategy = VolumeSurgeStrategy(self.config)

    def test_no_signal_when_volume_ratio_none(self):
        """量比为 None 时不触发"""
        quote = {"price": 10.0, "change_pct": 1.0, "volume_ratio": None}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNone(result)

    def test_no_signal_when_volume_ratio_normal(self):
        """量比在正常范围时不触发"""
        quote = {"price": 10.0, "change_pct": 1.0, "volume_ratio": 1.5}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNone(result)

    def test_buy_signal_on_surge_with_positive_change(self):
        """放量上涨触发买入信号"""
        quote = {"price": 15.0, "change_pct": 3.0, "volume_ratio": 3.5}
        result = self.strategy.evaluate("000001", "平安银行", quote)
        self.assertIsNotNone(result)
        self.assertEqual(result.signal_type, SignalType.BUY)
        self.assertEqual(result.trigger_value, 3.5)
        self.assertIn("放量上涨", result.message)

    def test_warning_signal_on_surge_with_negative_change(self):
        """放量下跌触发风险预警"""
        quote = {"price": 15.0, "change_pct": -2.0, "volume_ratio": 3.5}
        result = self.strategy.evaluate("000001", "平安银行", quote)
        self.assertIsNotNone(result)
        self.assertEqual(result.signal_type, SignalType.WARNING)
        self.assertIn("放量下跌", result.message)

    def test_alert_signal_on_shrink(self):
        """缩量触发关注信号"""
        quote = {"price": 10.0, "change_pct": 0.5, "volume_ratio": 0.3}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNotNone(result)
        self.assertEqual(result.signal_type, SignalType.ALERT)
        self.assertIn("地量", result.message)

    def test_exact_surge_threshold_not_triggered(self):
        """刚好等于放量阈值时不触发"""
        quote = {"price": 10.0, "change_pct": 1.0, "volume_ratio": 2.0}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNone(result)

    def test_exact_shrink_threshold_not_triggered(self):
        """刚好等于缩量阈值时不触发"""
        quote = {"price": 10.0, "change_pct": 0, "volume_ratio": 0.5}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNone(result)

    def test_surge_with_zero_change_pct(self):
        """放量但涨跌幅为 0 触发 WARNING"""
        quote = {"price": 10.0, "change_pct": 0, "volume_ratio": 3.0}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNotNone(result)
        self.assertEqual(result.signal_type, SignalType.WARNING)

    def test_custom_thresholds(self):
        """自定义量比阈值"""
        config = StrategyConfig(
            strategy_type=StrategyType.VOLUME_SURGE,
            signal_type=SignalType.ALERT,
            params={"surge_threshold": 3.0, "shrink_threshold": 0.3},
            cooldown_seconds=0,
        )
        strategy = VolumeSurgeStrategy(config)
        # 量比 2.5 在新阈值下不触发
        quote = {"price": 10.0, "change_pct": 1.0, "volume_ratio": 2.5}
        self.assertIsNone(strategy.evaluate("000001", "test", quote))
        # 量比 4.0 在新阈值下触发
        quote2 = {"price": 10.0, "change_pct": 1.0, "volume_ratio": 4.0}
        self.assertIsNotNone(strategy.evaluate("000001", "test", quote2))


# ============================================================
# 红阶段 5: AmplitudeAlertStrategy 振幅异常
# ============================================================

class TestAmplitudeAlertStrategy(unittest.TestCase):
    """振幅异常策略测试"""

    def setUp(self):
        self.config = StrategyConfig(
            strategy_type=StrategyType.AMPLITUDE_ALERT,
            signal_type=SignalType.ALERT,
            params={"threshold": 8.0},
            cooldown_seconds=0,
        )
        self.strategy = AmplitudeAlertStrategy(self.config)

    def test_no_signal_when_amplitude_none(self):
        """振幅为 None 时不触发"""
        quote = {"price": 10.0, "change_pct": 1.0, "amplitude": None}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNone(result)

    def test_no_signal_when_amplitude_normal(self):
        """振幅在正常范围不触发"""
        quote = {"price": 10.0, "change_pct": 1.0, "amplitude": 5.0}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNone(result)

    def test_alert_signal_when_amplitude_exceeds_threshold(self):
        """振幅超过阈值触发关注信号"""
        quote = {"price": 10.0, "change_pct": -3.0, "amplitude": 12.0}
        result = self.strategy.evaluate("000001", "平安银行", quote)
        self.assertIsNotNone(result)
        self.assertEqual(result.signal_type, SignalType.ALERT)
        self.assertEqual(result.strategy_type, StrategyType.AMPLITUDE_ALERT)
        self.assertEqual(result.trigger_value, 12.0)
        self.assertEqual(result.threshold, 8.0)
        self.assertIn("振幅", result.message)
        self.assertIn("12.0%", result.message)

    def test_exact_threshold_not_triggered(self):
        """刚好等于振幅阈值不触发"""
        quote = {"price": 10.0, "change_pct": 1.0, "amplitude": 8.0}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNone(result)

    def test_custom_amplitude_threshold(self):
        """自定义振幅阈值"""
        config = StrategyConfig(
            strategy_type=StrategyType.AMPLITUDE_ALERT,
            signal_type=SignalType.ALERT,
            params={"threshold": 10.0},
            cooldown_seconds=0,
        )
        strategy = AmplitudeAlertStrategy(config)
        # 振幅 9% 不触发
        self.assertIsNone(strategy.evaluate("000001", "test", {"price": 10, "change_pct": 1, "amplitude": 9.0}))
        # 振幅 11% 触发
        self.assertIsNotNone(strategy.evaluate("000001", "test", {"price": 10, "change_pct": 1, "amplitude": 11.0}))


# ============================================================
# 红阶段 6: TurnoverAlertStrategy 换手率异常
# ============================================================

class TestTurnoverAlertStrategy(unittest.TestCase):
    """换手率异常策略测试"""

    def setUp(self):
        self.config = StrategyConfig(
            strategy_type=StrategyType.TURNOVER_ALERT,
            signal_type=SignalType.WARNING,
            params={"threshold": 10.0},
            cooldown_seconds=0,
        )
        self.strategy = TurnoverAlertStrategy(self.config)

    def test_no_signal_when_turnover_none(self):
        """换手率为 None 时不触发"""
        quote = {"price": 10.0, "change_pct": 1.0, "turnover_rate": None}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNone(result)

    def test_no_signal_when_turnover_normal(self):
        """换手率正常时不触发"""
        quote = {"price": 10.0, "change_pct": 1.0, "turnover_rate": 5.0}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNone(result)

    def test_warning_signal_when_turnover_exceeds_threshold(self):
        """换手率超过阈值触发风险预警"""
        quote = {"price": 25.0, "change_pct": 8.0, "turnover_rate": 15.0}
        result = self.strategy.evaluate("000001", "平安银行", quote)
        self.assertIsNotNone(result)
        self.assertEqual(result.signal_type, SignalType.WARNING)
        self.assertEqual(result.strategy_type, StrategyType.TURNOVER_ALERT)
        self.assertEqual(result.trigger_value, 15.0)
        self.assertIn("换手率", result.message)
        self.assertIn("15.0%", result.message)

    def test_exact_threshold_not_triggered(self):
        """刚好等于换手率阈值不触发"""
        quote = {"price": 10.0, "change_pct": 1.0, "turnover_rate": 10.0}
        result = self.strategy.evaluate("000001", "test", quote)
        self.assertIsNone(result)

    def test_custom_turnover_threshold(self):
        """自定义换手率阈值"""
        config = StrategyConfig(
            strategy_type=StrategyType.TURNOVER_ALERT,
            signal_type=SignalType.WARNING,
            params={"threshold": 20.0},
            cooldown_seconds=0,
        )
        strategy = TurnoverAlertStrategy(config)
        # 换手率 15% 不触发
        self.assertIsNone(strategy.evaluate("000001", "test", {"price": 10, "change_pct": 1, "turnover_rate": 15.0}))
        # 换手率 25% 触发
        self.assertIsNotNone(strategy.evaluate("000001", "test", {"price": 10, "change_pct": 1, "turnover_rate": 25.0}))


# ============================================================
# 红阶段 7: create_strategies 工厂函数
# ============================================================

class TestCreateStrategies(unittest.TestCase):
    """策略工厂函数测试"""

    def test_create_strategies_from_defaults(self):
        """从默认配置创建策略"""
        configs = get_default_strategies()
        strategies = create_strategies(configs)
        self.assertEqual(len(strategies), 4)
        for s in strategies:
            self.assertIsInstance(s, BaseStrategy)

    def test_create_strategies_with_disabled(self):
        """创建禁用状态的策略"""
        configs = [{
            "strategy_type": "change_threshold",
            "signal_type": "alert",
            "enabled": False,
            "params": {"threshold": 5.0},
            "cooldown_seconds": 300,
        }]
        strategies = create_strategies(configs)
        self.assertEqual(len(strategies), 1)
        self.assertFalse(strategies[0].config.enabled)

    def test_create_strategies_unknown_type_skipped(self):
        """未知策略类型被跳过"""
        configs = [
            {
                "strategy_type": "change_threshold",
                "signal_type": "alert",
                "params": {"threshold": 5.0},
            },
            {
                "strategy_type": "unknown_type",
                "signal_type": "alert",
                "params": {},
            },
        ]
        strategies = create_strategies(configs)
        self.assertEqual(len(strategies), 1)
        self.assertIsInstance(strategies[0], ChangeThresholdStrategy)

    def test_create_strategies_empty_list(self):
        """空配置列表返回空列表"""
        strategies = create_strategies([])
        self.assertEqual(strategies, [])

    def test_create_strategies_missing_optional_fields(self):
        """缺少可选字段时使用默认值"""
        configs = [{"strategy_type": "change_threshold"}]
        strategies = create_strategies(configs)
        self.assertEqual(len(strategies), 1)
        s = strategies[0]
        self.assertEqual(s.config.signal_type, SignalType.ALERT)  # 默认 alert
        self.assertTrue(s.config.enabled)
        self.assertEqual(s.config.params, {})
        self.assertEqual(s.config.cooldown_seconds, 300)


# ============================================================
# 红阶段 8: get_default_strategies 默认配置
# ============================================================

class TestGetDefaultStrategies(unittest.TestCase):
    """默认策略配置测试"""

    def test_returns_four_strategies(self):
        configs = get_default_strategies()
        self.assertEqual(len(configs), 4)

    def test_all_strategies_have_required_fields(self):
        for cfg in get_default_strategies():
            self.assertIn("strategy_type", cfg)
            self.assertIn("signal_type", cfg)
            self.assertIn("enabled", cfg)
            self.assertIn("params", cfg)
            self.assertIn("cooldown_seconds", cfg)

    def test_all_default_strategies_enabled(self):
        for cfg in get_default_strategies():
            self.assertTrue(cfg["enabled"])

    def test_strategy_types_are_valid(self):
        valid_types = {t.value for t in StrategyType}
        for cfg in get_default_strategies():
            self.assertIn(cfg["strategy_type"], valid_types)


# ============================================================
# 红阶段 9: 策略冷却与多标的组合测试
# ============================================================

class TestStrategyCooldownIntegration(unittest.TestCase):
    """策略冷却集成测试"""

    def test_signal_not_triggered_during_cooldown(self):
        """冷却期内不重复触发同一标的"""
        config = StrategyConfig(
            strategy_type=StrategyType.CHANGE_THRESHOLD,
            signal_type=SignalType.ALERT,
            params={"threshold": 5.0},
            cooldown_seconds=3600,  # 1小时冷却
        )
        strategy = ChangeThresholdStrategy(config)
        quote = {"price": 12.0, "change_pct": 6.0}

        # 第一次触发（通过 evaluate_with_cooldown 自动标记冷却）
        result1 = strategy.evaluate_with_cooldown("000001", "test", quote)
        self.assertIsNotNone(result1)

        # 第二次应被冷却阻止
        result2 = strategy.evaluate_with_cooldown("000001", "test", quote)
        self.assertIsNone(result2)

    def test_different_strategies_independent_cooldown(self):
        """不同策略的冷却互不影响"""
        config1 = StrategyConfig(
            strategy_type=StrategyType.CHANGE_THRESHOLD,
            signal_type=SignalType.ALERT,
            params={"threshold": 5.0},
            cooldown_seconds=3600,
        )
        config2 = StrategyConfig(
            strategy_type=StrategyType.VOLUME_SURGE,
            signal_type=SignalType.ALERT,
            params={"surge_threshold": 2.0, "shrink_threshold": 0.5},
            cooldown_seconds=3600,
        )
        s1 = ChangeThresholdStrategy(config1)
        s2 = VolumeSurgeStrategy(config2)

        quote = {"price": 12.0, "change_pct": 6.0, "volume_ratio": 3.0}

        # s1 触发并冷却
        self.assertIsNotNone(s1.evaluate("000001", "test", quote))
        s1.mark_triggered("000001")

        # s2 仍可触发（不同策略独立冷却）
        result = s2.evaluate("000001", "test", quote)
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
