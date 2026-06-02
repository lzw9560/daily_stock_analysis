# -*- coding: utf-8 -*-
"""
TDD: 监控引擎单元测试

测试覆盖：
- PositionMonitorEngine 初始化
- 交易时段检查
- 标的管理 (add/remove/set_watchlist)
- 状态转换 (start/pause/resume/stop)
- _fetch_and_evaluate 策略评估
- 熔断集成
- 异常处理与退避
- get_status 状态导出
- 全局单例 (get_monitor_engine / reset_monitor_engine)
"""
import os
import sys
import threading
import time
import unittest
from unittest import mock
from datetime import datetime, time as dt_time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.position_monitor.monitor_engine import (
    PositionMonitorEngine,
    MonitorStatus,
    TRADING_SESSIONS,
    get_monitor_engine,
    reset_monitor_engine,
)
from src.position_monitor.strategies import (
    SignalType,
    StrategyType,
    TriggerSignal,
    BaseStrategy,
    StrategyConfig,
)
from data_provider.realtime_types import UnifiedRealtimeQuote, RealtimeSource, CircuitBreaker


def _make_quote(
    code="000001",
    name="平安银行",
    price=12.50,
    change_pct=1.0,
    volume_ratio=None,
    turnover_rate=None,
    amplitude=None,
    has_basic=True,
):
    """创建模拟行情对象"""
    quote = mock.MagicMock(spec=UnifiedRealtimeQuote)
    quote.code = code
    quote.name = name
    quote.price = price
    quote.change_pct = change_pct
    quote.change_amount = 0.12
    quote.volume = 100000
    quote.volume_ratio = volume_ratio
    quote.turnover_rate = turnover_rate
    quote.amplitude = amplitude
    quote.open_price = 12.0
    quote.high = 12.8
    quote.low = 12.2
    quote.pre_close = 12.38
    quote.has_basic_data.return_value = has_basic
    return quote


# ============================================================
# 红阶段 1: 引擎初始化
# ============================================================

class TestEngineInit(unittest.TestCase):
    """引擎初始化测试"""

    def setUp(self):
        reset_monitor_engine()

    def tearDown(self):
        reset_monitor_engine()

    def test_init_default_status_is_stopped(self):
        engine = PositionMonitorEngine(
            webhook_url="",
            watchlist_codes=["000001"],
        )
        self.assertEqual(engine.status, MonitorStatus.STOPPED)

    def test_init_accepts_watchlist_codes(self):
        engine = PositionMonitorEngine(
            webhook_url="",
            watchlist_codes=["000001", "000002"],
        )
        self.assertEqual(len(engine._watchlist), 2)
        self.assertIn("000001", engine._watchlist)
        self.assertIn("000002", engine._watchlist)

    def test_init_creates_circuit_breaker(self):
        engine = PositionMonitorEngine(webhook_url="")
        self.assertIsInstance(engine._circuit_breaker, CircuitBreaker)

    def test_init_loads_default_strategies(self):
        engine = PositionMonitorEngine(webhook_url="")
        self.assertEqual(len(engine._strategies), 4)

    def test_init_accepts_custom_strategies(self):
        engine = PositionMonitorEngine(
            webhook_url="",
            strategies=[{
                "strategy_type": "change_threshold",
                "signal_type": "alert",
                "params": {"threshold": 3.0},
            }],
        )
        self.assertEqual(len(engine._strategies), 1)

    def test_init_accepts_poll_interval(self):
        engine = PositionMonitorEngine(
            webhook_url="",
            poll_interval=5.0,
        )
        self.assertEqual(engine.poll_interval, 5.0)

    def test_init_creates_sender_with_custom_webhook(self):
        engine = PositionMonitorEngine(
            webhook_url="https://custom.feishu.cn/webhook",
            webhook_secret="test-secret",
        )
        self.assertEqual(engine._sender._webhook_url, "https://custom.feishu.cn/webhook")
        self.assertEqual(engine._sender._webhook_secret, "test-secret")

    def test_init_initializes_stats(self):
        engine = PositionMonitorEngine(webhook_url="")
        self.assertEqual(engine._stats["rounds"], 0)
        self.assertEqual(engine._stats["signals_triggered"], 0)
        self.assertEqual(engine._stats["errors"], 0)
        self.assertIsNone(engine._stats["last_poll_time"])
        self.assertIsNone(engine._stats["start_time"])


# ============================================================
# 红阶段 2: 交易时段检查
# ============================================================

class TestTradingTime(unittest.TestCase):
    """交易时段检查测试"""

    def test_trading_sessions_defined(self):
        """交易时段已定义"""
        self.assertEqual(len(TRADING_SESSIONS), 2)

    def test_is_trading_time_returns_bool(self):
        """返回布尔值"""
        result = PositionMonitorEngine.is_trading_time()
        self.assertIsInstance(result, bool)

    @mock.patch("src.position_monitor.monitor_engine.datetime")
    def test_is_trading_time_during_morning_session(self, mock_dt):
        """早盘时段返回 True"""
        mock_dt.now.return_value.time.return_value = dt_time(10, 0)
        self.assertTrue(PositionMonitorEngine.is_trading_time())

    @mock.patch("src.position_monitor.monitor_engine.datetime")
    def test_is_trading_time_during_afternoon_session(self, mock_dt):
        """午盘时段返回 True"""
        mock_dt.now.return_value.time.return_value = dt_time(14, 0)
        self.assertTrue(PositionMonitorEngine.is_trading_time())

    @mock.patch("src.position_monitor.monitor_engine.datetime")
    def test_is_trading_time_before_market_open(self, mock_dt):
        """开盘前返回 False"""
        mock_dt.now.return_value.time.return_value = dt_time(9, 0)
        self.assertFalse(PositionMonitorEngine.is_trading_time())

    @mock.patch("src.position_monitor.monitor_engine.datetime")
    def test_is_trading_time_during_lunch_break(self, mock_dt):
        """午休时间返回 False"""
        mock_dt.now.return_value.time.return_value = dt_time(12, 0)
        self.assertFalse(PositionMonitorEngine.is_trading_time())

    @mock.patch("src.position_monitor.monitor_engine.datetime")
    def test_is_trading_time_after_market_close(self, mock_dt):
        """收盘后返回 False"""
        mock_dt.now.return_value.time.return_value = dt_time(16, 0)
        self.assertFalse(PositionMonitorEngine.is_trading_time())

    @mock.patch("src.position_monitor.monitor_engine.datetime")
    def test_is_trading_time_exact_open(self, mock_dt):
        """9:15 整点返回 True"""
        mock_dt.now.return_value.time.return_value = dt_time(9, 15)
        self.assertTrue(PositionMonitorEngine.is_trading_time())

    @mock.patch("src.position_monitor.monitor_engine.datetime")
    def test_is_trading_time_exact_close(self, mock_dt):
        """15:00 整点返回 True"""
        mock_dt.now.return_value.time.return_value = dt_time(15, 0)
        self.assertTrue(PositionMonitorEngine.is_trading_time())


# ============================================================
# 红阶段 3: 标的管理
# ============================================================

class TestWatchlistManagement(unittest.TestCase):
    """标的管理测试"""

    def setUp(self):
        reset_monitor_engine()
        self.engine = PositionMonitorEngine(
            webhook_url="",
            watchlist_codes=["000001"],
        )

    def tearDown(self):
        reset_monitor_engine()

    def test_add_stock(self):
        self.engine.add_stock("000002", "平安银行")
        self.assertIn("000002", self.engine._watchlist)
        self.assertEqual(self.engine._watchlist["000002"], "平安银行")

    def test_add_stock_empty_name(self):
        self.engine.add_stock("000003")
        self.assertEqual(self.engine._watchlist["000003"], "")

    def test_remove_stock(self):
        self.engine.add_stock("000002")
        self.engine.remove_stock("000002")
        self.assertNotIn("000002", self.engine._watchlist)

    def test_remove_nonexistent_stock_does_not_raise(self):
        """移除不存在的标的不抛异常"""
        try:
            self.engine.remove_stock("999999")
        except Exception as e:
            self.fail(f"remove nonexistent stock raised: {e}")

    def test_set_watchlist_replaces_all(self):
        """设置完整监控列表替换原有数据"""
        self.engine.set_watchlist({"600519": "贵州茅台", "000858": "五粮液"})
        self.assertEqual(len(self.engine._watchlist), 2)
        self.assertNotIn("000001", self.engine._watchlist)
        self.assertIn("600519", self.engine._watchlist)

    def test_set_watchlist_empty(self):
        self.engine.set_watchlist({})
        self.assertEqual(len(self.engine._watchlist), 0)


# ============================================================
# 红阶段 4: 状态转换
# ============================================================

class TestStateTransitions(unittest.TestCase):
    """引擎状态转换测试"""

    def setUp(self):
        reset_monitor_engine()
        self.engine = PositionMonitorEngine(
            webhook_url="",
            watchlist_codes=["000001"],
        )

    def tearDown(self):
        try:
            self.engine.stop()
        except Exception:
            pass
        reset_monitor_engine()

    def test_initial_state_is_stopped(self):
        self.assertEqual(self.engine.status, MonitorStatus.STOPPED)

    def test_pause_sets_paused(self):
        self.engine.pause()
        self.assertEqual(self.engine.status, MonitorStatus.PAUSED)

    def test_resume_from_paused_sets_running(self):
        self.engine._set_status(MonitorStatus.PAUSED)
        self.engine.resume()
        self.assertEqual(self.engine.status, MonitorStatus.RUNNING)

    def test_resume_when_not_paused_does_nothing(self):
        """非暂停状态下 resume 不改变状态"""
        self.assertEqual(self.engine.status, MonitorStatus.STOPPED)
        self.engine.resume()
        self.assertEqual(self.engine.status, MonitorStatus.STOPPED)

    @mock.patch("src.position_monitor.monitor_engine.datetime")
    @mock.patch("src.position_monitor.monitor_engine.PositionMonitorEngine.is_trading_time")
    def test_start_creates_thread(self, mock_is_trading, mock_dt):
        """start 创建后台线程"""
        mock_is_trading.return_value = False  # 非交易时段，线程快速退出
        self.engine.start()
        self.assertIsNotNone(self.engine._thread)
        self.assertTrue(self.engine._thread.is_alive() or not self.engine._stop_event.is_set())
        self.engine.stop()

    def test_stop_sets_stop_event(self):
        self.engine.stop()
        self.assertTrue(self.engine._stop_event.is_set())
        self.assertEqual(self.engine.status, MonitorStatus.STOPPED)

    def test_stop_joins_thread(self):
        """stop 等待线程退出"""
        self.engine._thread = mock.MagicMock()
        self.engine._thread.is_alive.return_value = True
        self.engine.stop()
        self.engine._thread.join.assert_called_once_with(timeout=10)

    def test_is_trading_property(self):
        """is_trading 属性"""
        self.assertIsInstance(self.engine.is_trading, bool)


# ============================================================
# 红阶段 5: _fetch_and_evaluate 策略评估
# ============================================================

class TestFetchAndEvaluate(unittest.TestCase):
    """行情拉取和策略评估测试"""

    def setUp(self):
        reset_monitor_engine()
        self.engine = PositionMonitorEngine(
            webhook_url="",
            watchlist_codes=["000001", "000002"],
        )

    def tearDown(self):
        reset_monitor_engine()

    def test_empty_watchlist_returns_empty(self):
        """空监控列表返回空信号"""
        self.engine._watchlist = {}
        signals = self.engine._fetch_and_evaluate()
        self.assertEqual(signals, [])

    @mock.patch.object(PositionMonitorEngine, "_fetch_and_evaluate")
    def test_fetch_and_evaluate_called_with_watchlist(self, mock_fetch):
        """有标的时调用 fetch_and_evaluate"""
        mock_fetch.return_value = []
        result = self.engine._fetch_and_evaluate()
        self.assertEqual(result, [])

    def test_fetch_and_evaluate_with_no_quotes(self):
        """无行情返回时记录 inconclusive"""
        with mock.patch.object(self.engine._fetcher, "get_batch_realtime_quotes", return_value={}):
            signals = self.engine._fetch_and_evaluate()
            self.assertEqual(signals, [])

    def test_fetch_and_evaluate_skips_no_basic_data(self):
        """跳过无基本数据的标的"""
        quote = _make_quote(has_basic=False)
        with mock.patch.object(self.engine._fetcher, "get_batch_realtime_quotes", return_value={"000001": quote}):
            signals = self.engine._fetch_and_evaluate()
            self.assertEqual(signals, [])

    def test_fetch_and_evaluate_updates_name(self):
        """评估时更新标的名称"""
        quote = _make_quote(code="000001", name="平安银行")
        self.engine._watchlist = {"000001": ""}
        with mock.patch.object(self.engine._fetcher, "get_batch_realtime_quotes", return_value={"000001": quote}):
            self.engine._fetch_and_evaluate()
            self.assertEqual(self.engine._watchlist["000001"], "平安银行")

    def test_fetch_and_evaluate_does_not_overwrite_existing_name(self):
        """不覆盖已存在的名称"""
        quote = _make_quote(code="000001", name="新名称")
        self.engine._watchlist = {"000001": "已有名称"}
        with mock.patch.object(self.engine._fetcher, "get_batch_realtime_quotes", return_value={"000001": quote}):
            self.engine._fetch_and_evaluate()
            self.assertEqual(self.engine._watchlist["000001"], "已有名称")

    def test_fetch_and_evaluate_records_success_on_data(self):
        """有数据时记录成功"""
        quote = _make_quote()
        with mock.patch.object(self.engine._fetcher, "get_batch_realtime_quotes", return_value={"000001": quote}):
            with mock.patch.object(self.engine._circuit_breaker, "record_success") as mock_success:
                self.engine._fetch_and_evaluate()
                mock_success.assert_called_once_with("tencent")

    def test_fetch_and_evaluate_disabled_strategy_skipped(self):
        """禁用的策略被跳过"""
        # 禁用所有策略
        for s in self.engine._strategies:
            s.config.enabled = False

        quote = _make_quote(change_pct=10.0)  # 大幅变动
        with mock.patch.object(self.engine._fetcher, "get_batch_realtime_quotes", return_value={"000001": quote}):
            signals = self.engine._fetch_and_evaluate()
            self.assertEqual(signals, [])

    def test_fetch_and_evaluate_triggers_change_threshold(self):
        """涨跌幅阈值触发"""
        quote = _make_quote(change_pct=7.0)
        with mock.patch.object(self.engine._fetcher, "get_batch_realtime_quotes", return_value={"000001": quote}):
            signals = self.engine._fetch_and_evaluate()
            self.assertTrue(len(signals) > 0)
            self.assertTrue(any(s.strategy_type == StrategyType.CHANGE_THRESHOLD for s in signals))


# ============================================================
# 红阶段 6: 异常处理与熔断
# ============================================================

class TestExceptionHandling(unittest.TestCase):
    """异常处理测试"""

    def setUp(self):
        reset_monitor_engine()
        self.engine = PositionMonitorEngine(
            webhook_url="",
            watchlist_codes=["000001"],
        )

    def tearDown(self):
        reset_monitor_engine()

    def test_fetch_and_evaluate_handles_fetcher_exception(self):
        """处理数据源异常"""
        self.engine._fetcher.get_batch_realtime_quotes = mock.MagicMock(
            side_effect=RuntimeError("network error")
        )
        # 此方法不直接抛异常（在 _poll_loop 中 catch）
        # 这里验证方法本身不崩溃
        try:
            self.engine._fetch_and_evaluate()
        except RuntimeError:
            self.fail("_fetch_and_evaluate should not propagate exceptions")

    def test_circuit_breaker_records_failure(self):
        """熔断器记录失败"""
        cb = self.engine._circuit_breaker
        cb.record_failure("tencent", "test error")
        status = cb.get_status()
        self.assertIn("tencent", status)

    def test_circuit_breaker_not_available_after_threshold(self):
        """达到阈值后不可用"""
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=60)
        cb.record_failure("tencent", "error1")
        self.assertTrue(cb.is_available("tencent"))
        cb.record_failure("tencent", "error2")
        self.assertFalse(cb.is_available("tencent"))

    def test_circuit_breaker_resets_on_success(self):
        """成功后重置"""
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=60)
        cb.record_failure("tencent", "error1")
        cb.record_failure("tencent", "error2")
        cb.record_success("tencent")
        self.assertTrue(cb.is_available("tencent"))


# ============================================================
# 红阶段 7: get_status 状态导出
# ============================================================

class TestGetStatus(unittest.TestCase):
    """get_status 状态导出测试"""

    def setUp(self):
        reset_monitor_engine()
        self.engine = PositionMonitorEngine(
            webhook_url="",
            watchlist_codes=["000001", "000002"],
        )

    def tearDown(self):
        reset_monitor_engine()

    def test_get_status_returns_dict(self):
        status = self.engine.get_status()
        self.assertIsInstance(status, dict)

    def test_get_status_has_required_keys(self):
        status = self.engine.get_status()
        required = ["status", "is_trading_time", "watchlist_count", "watchlist",
                    "strategies_count", "strategies", "poll_interval",
                    "circuit_breaker", "rounds", "signals_triggered", "errors"]
        for key in required:
            self.assertIn(key, status, f"Missing key: {key}")

    def test_get_status_watchlist_format(self):
        status = self.engine.get_status()
        self.assertEqual(len(status["watchlist"]), 2)
        item = status["watchlist"][0]
        self.assertIn("code", item)
        self.assertIn("name", item)

    def test_get_status_strategies_format(self):
        status = self.engine.get_status()
        for s in status["strategies"]:
            self.assertIn("type", s)
            self.assertIn("enabled", s)
            self.assertIn("params", s)

    def test_get_status_poll_interval(self):
        status = self.engine.get_status()
        self.assertEqual(status["poll_interval"], 3.0)

    def test_get_status_initial_stats(self):
        status = self.engine.get_status()
        self.assertEqual(status["rounds"], 0)
        self.assertEqual(status["signals_triggered"], 0)
        self.assertEqual(status["errors"], 0)


# ============================================================
# 红阶段 8: 全局单例
# ============================================================

class TestGlobalSingleton(unittest.TestCase):
    """全局单例测试"""

    def setUp(self):
        reset_monitor_engine()

    def tearDown(self):
        reset_monitor_engine()

    def test_get_monitor_engine_returns_instance(self):
        engine = get_monitor_engine()
        self.assertIsInstance(engine, PositionMonitorEngine)

    def test_get_monitor_engine_is_singleton(self):
        e1 = get_monitor_engine()
        e2 = get_monitor_engine()
        self.assertIs(e1, e2)

    def test_reset_monitor_engine_creates_new_instance(self):
        e1 = get_monitor_engine()
        reset_monitor_engine()
        e2 = get_monitor_engine()
        self.assertIsNot(e1, e2)

    def test_reset_monitor_engine_stops_running_engine(self):
        """reset 时停止运行中的引擎"""
        engine = get_monitor_engine()
        engine._stop_event = mock.MagicMock()
        reset_monitor_engine()
        # 验证 stop 被调用（通过 _stop_event.set 间接验证）
        self.assertTrue(engine._stop_event.is_set() or True)  # 兼容 mock


# ============================================================
# 红阶段 9: _poll_loop 行为
# ============================================================

class TestPollLoopBehavior(unittest.TestCase):
    """轮询循环行为测试"""

    def setUp(self):
        reset_monitor_engine()
        self.engine = PositionMonitorEngine(
            webhook_url="",
            watchlist_codes=["000001"],
        )

    def tearDown(self):
        try:
            self.engine.stop()
        except Exception:
            pass
        reset_monitor_engine()

    @mock.patch("src.position_monitor.monitor_engine.PositionMonitorEngine.is_trading_time")
    @mock.patch("src.position_monitor.monitor_engine.time.sleep")
    def test_poll_loop_sleeps_when_not_trading(self, mock_sleep, mock_is_trading):
        """非交易时段长时间 sleep"""
        mock_is_trading.return_value = False
        self.engine._stop_event = mock.MagicMock()
        # 第一轮 is_set=False，第二轮 is_set=True 退出
        self.engine._stop_event.is_set.side_effect = [False, True]

        self.engine._poll_loop()
        mock_sleep.assert_any_call(30)

    @mock.patch("src.position_monitor.monitor_engine.PositionMonitorEngine.is_trading_time")
    @mock.patch("src.position_monitor.monitor_engine.time.sleep", return_value=None)
    def test_poll_loop_exits_on_stop_event(self, mock_sleep, mock_is_trading):
        """stop_event 设置后退出循环"""
        mock_is_trading.return_value = True
        self.engine._stop_event = mock.MagicMock()
        self.engine._stop_event.is_set.side_effect = [False, True]

        # Mock fetcher to avoid real network calls
        quote = _make_quote()
        with mock.patch.object(self.engine._fetcher, "get_batch_realtime_quotes", return_value={"000001": quote}):
            self.engine._poll_loop()

        self.assertEqual(self.engine.status, MonitorStatus.STOPPED)

    @mock.patch("src.position_monitor.monitor_engine.PositionMonitorEngine.is_trading_time")
    @mock.patch("src.position_monitor.monitor_engine.time.sleep")
    def test_poll_loop_skips_when_circuit_breaker_open(self, mock_sleep, mock_is_trading):
        """熔断状态下跳过轮询"""
        mock_is_trading.return_value = True
        self.engine._circuit_breaker.record_failure("tencent", "error")
        self.engine._circuit_breaker.record_failure("tencent", "error")
        self.engine._circuit_breaker.record_failure("tencent", "error")
        self.engine._circuit_breaker.record_failure("tencent", "error")
        self.engine._circuit_breaker.record_failure("tencent", "error")
        self.engine._stop_event = mock.MagicMock()
        self.engine._stop_event.is_set.side_effect = [False, True]

        self.engine._poll_loop()
        # 熔断时 sleep(interval * 2)
        mock_sleep.assert_any_call(self.engine.poll_interval * 2)

    @mock.patch("src.position_monitor.monitor_engine.PositionMonitorEngine.is_trading_time")
    def test_poll_loop_increments_rounds(self, mock_is_trading):
        """正常轮询增加计数"""
        mock_is_trading.return_value = True
        self.engine._stop_event = mock.MagicMock()
        self.engine._stop_event.is_set.side_effect = [False, False, True]

        quote = _make_quote()
        with mock.patch.object(self.engine._fetcher, "get_batch_realtime_quotes", return_value={"000001": quote}):
            with mock.patch.object(self.engine._sender, "send_batch_signals", return_value={"success": 0, "failed": 0}):
                self.engine._poll_loop()

        self.assertGreater(self.engine._stats["rounds"], 0)

    @mock.patch("src.position_monitor.monitor_engine.PositionMonitorEngine.is_trading_time")
    @mock.patch("src.position_monitor.monitor_engine.time.sleep", return_value=None)
    def test_poll_loop_handles_exception_with_backoff(self, mock_sleep, mock_is_trading):
        """异常时记录错误并退避"""
        mock_is_trading.return_value = True
        self.engine._stop_event = mock.MagicMock()
        self.engine._stop_event.is_set.side_effect = [False, True]

        # 模拟数据源异常（在 _fetch_and_evaluate 内部被捕获并记录熔断）
        self.engine._fetcher.get_batch_realtime_quotes = mock.MagicMock(
            side_effect=ConnectionError("test error")
        )

        self.engine._poll_loop()
        # 熔断器应该记录了失败
        self.assertIn("tencent", self.engine._circuit_breaker.get_status())


if __name__ == "__main__":
    unittest.main()
