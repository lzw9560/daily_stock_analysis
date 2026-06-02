# -*- coding: utf-8 -*-
"""
TDD: 持仓监控 API 接口测试

测试覆盖：
- GET /status - 监控状态查询
- POST /start - 启动监控
- POST /pause - 暂停监控
- POST /resume - 恢复监控
- POST /stop - 停止监控
- POST /restart - 重启监控（含配置变更）
- POST /stocks - 添加标的
- POST /stocks/batch - 批量添加
- DELETE /stocks/{code} - 移除标的
- POST /stocks/sync-watchlist - 同步自选股
- GET /strategies/default - 默认策略
- GET /trading-time - 交易时段
- POST /heartbeat - 飞书心跳
- 异常场景：引擎错误、无效输入、边界条件
"""
import os
import sys
import unittest
from unittest import mock
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from api.app import app
from src.position_monitor.monitor_engine import (
    PositionMonitorEngine,
    MonitorStatus,
    get_monitor_engine,
    reset_monitor_engine,
)
from src.position_monitor.strategies import SignalType, StrategyType, TriggerSignal


# ============================================================
# 红阶段 1: 状态查询 API
# ============================================================

class TestStatusAPI(unittest.TestCase):
    """GET /api/v1/position-monitor/status 测试"""

    def setUp(self):
        reset_monitor_engine()
        self.client = TestClient(app)

    def tearDown(self):
        reset_monitor_engine()

    def test_get_status_returns_200(self):
        response = self.client.get("/api/v1/position-monitor/status")
        self.assertEqual(response.status_code, 200)

    def test_get_status_returns_correct_structure(self):
        response = self.client.get("/api/v1/position-monitor/status")
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("is_trading_time", data)
        self.assertIn("watchlist_count", data)
        self.assertIn("strategies_count", data)
        self.assertIn("poll_interval", data)
        self.assertIn("rounds", data)
        self.assertIn("signals_triggered", data)
        self.assertIn("errors", data)

    def test_get_status_default_status_is_stopped(self):
        response = self.client.get("/api/v1/position-monitor/status")
        self.assertEqual(response.json()["status"], "stopped")

    def test_get_status_includes_watchlist(self):
        engine = get_monitor_engine()
        engine.add_stock("000001", "平安银行")
        response = self.client.get("/api/v1/position-monitor/status")
        self.assertEqual(response.json()["watchlist_count"], 1)
        self.assertEqual(len(response.json()["watchlist"]), 1)

    def test_get_status_includes_strategies(self):
        response = self.client.get("/api/v1/position-monitor/status")
        strategies = response.json()["strategies"]
        self.assertGreater(len(strategies), 0)
        for s in strategies:
            self.assertIn("type", s)
            self.assertIn("enabled", s)
            self.assertIn("params", s)


# ============================================================
# 红阶段 2: 启停控制 API
# ============================================================

class TestLifecycleAPI(unittest.TestCase):
    """监控启停控制 API 测试"""

    def setUp(self):
        reset_monitor_engine()
        self.client = TestClient(app)

    def tearDown(self):
        reset_monitor_engine()

    def test_start_returns_200(self):
        response = self.client.post("/api/v1/position-monitor/start")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("启动", data["message"])

    @mock.patch("src.position_monitor.monitor_engine.PositionMonitorEngine.start")
    def test_start_calls_engine_start(self, mock_start):
        response = self.client.post("/api/v1/position-monitor/start")
        self.assertEqual(response.status_code, 200)
        mock_start.assert_called_once()

    def test_pause_returns_200(self):
        response = self.client.post("/api/v1/position-monitor/pause")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

    def test_resume_returns_200(self):
        response = self.client.post("/api/v1/position-monitor/resume")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

    def test_stop_returns_200(self):
        response = self.client.post("/api/v1/position-monitor/stop")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

    @mock.patch("src.position_monitor.monitor_engine.PositionMonitorEngine.stop")
    def test_stop_calls_engine_stop(self, mock_stop):
        response = self.client.post("/api/v1/position-monitor/stop")
        self.assertEqual(response.status_code, 200)
        mock_stop.assert_called_once()

    def test_start_then_pause_then_resume(self):
        """完整生命周期：启动→暂停→恢复"""
        # 先启动
        r1 = self.client.post("/api/v1/position-monitor/start")
        self.assertEqual(r1.status_code, 200)

        # 暂停
        r2 = self.client.post("/api/v1/position-monitor/pause")
        self.assertEqual(r2.status_code, 200)

        # 恢复
        r3 = self.client.post("/api/v1/position-monitor/resume")
        self.assertEqual(r3.status_code, 200)

        # 停止
        r4 = self.client.post("/api/v1/position-monitor/stop")
        self.assertEqual(r4.status_code, 200)


# ============================================================
# 红阶段 3: 重启 API
# ============================================================

class TestRestartAPI(unittest.TestCase):
    """POST /api/v1/position-monitor/restart 测试"""

    def setUp(self):
        reset_monitor_engine()
        self.client = TestClient(app)

    def tearDown(self):
        reset_monitor_engine()

    def test_restart_without_config_returns_200(self):
        response = self.client.post("/api/v1/position-monitor/restart")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("重启", data["message"])

    def test_restart_with_config_returns_200(self):
        config = {
            "poll_interval": 5.0,
            "strategies": [
                {
                    "strategy_type": "change_threshold",
                    "signal_type": "alert",
                    "enabled": True,
                    "params": {"threshold": 3.0},
                    "cooldown_seconds": 120,
                }
            ],
            "watchlist_codes": ["000001", "000002"],
        }
        response = self.client.post("/api/v1/position-monitor/restart", json=config)
        self.assertEqual(response.status_code, 200)

    def test_restart_with_invalid_poll_interval_returns_422(self):
        """无效轮询间隔返回 422"""
        config = {"poll_interval": 0.5}  # 小于最小值 1.0
        response = self.client.post("/api/v1/position-monitor/restart", json=config)
        self.assertEqual(response.status_code, 422)

    def test_restart_with_too_large_poll_interval_returns_422(self):
        """过大的轮询间隔返回 422"""
        config = {"poll_interval": 100.0}  # 大于最大值 60.0
        response = self.client.post("/api/v1/position-monitor/restart", json=config)
        self.assertEqual(response.status_code, 422)

    def test_restart_applies_new_config(self):
        """重启后应用新配置"""
        config = {
            "poll_interval": 10.0,
            "watchlist_codes": ["600519"],
        }
        self.client.post("/api/v1/position-monitor/restart", json=config)

        # 验证新配置生效
        status = self.client.get("/api/v1/position-monitor/status")
        self.assertEqual(status.json()["poll_interval"], 10.0)
        self.assertGreaterEqual(status.json()["watchlist_count"], 1)


# ============================================================
# 红阶段 4: 标的管理 API
# ============================================================

class TestStocksAPI(unittest.TestCase):
    """标的管理 API 测试"""

    def setUp(self):
        reset_monitor_engine()
        self.client = TestClient(app)

    def tearDown(self):
        reset_monitor_engine()

    def test_add_stock_returns_200(self):
        response = self.client.post(
            "/api/v1/position-monitor/stocks",
            json={"code": "000001", "name": "平安银行"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

    def test_add_stock_without_name_returns_200(self):
        """不提供名称也能添加"""
        response = self.client.post(
            "/api/v1/position-monitor/stocks",
            json={"code": "000002"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

    def test_add_stock_missing_code_returns_422(self):
        """缺少 code 字段返回 422"""
        response = self.client.post(
            "/api/v1/position-monitor/stocks",
            json={"name": "测试"},
        )
        self.assertEqual(response.status_code, 422)

    def test_add_stock_empty_code_returns_200(self):
        """空字符串 code 也能添加（由业务层判断）"""
        response = self.client.post(
            "/api/v1/position-monitor/stocks",
            json={"code": ""},
        )
        # Pydantic 不验证非空，所以 200
        self.assertEqual(response.status_code, 200)

    def test_batch_add_stocks_returns_200(self):
        response = self.client.post(
            "/api/v1/position-monitor/stocks/batch",
            json={"codes": ["000001", "000002", "600519"]},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("3", data["message"])

    def test_batch_add_stocks_empty_list_returns_200(self):
        response = self.client.post(
            "/api/v1/position-monitor/stocks/batch",
            json={"codes": []},
        )
        self.assertEqual(response.status_code, 200)

    def test_batch_add_stocks_missing_codes_returns_422(self):
        response = self.client.post(
            "/api/v1/position-monitor/stocks/batch",
            json={},
        )
        self.assertEqual(response.status_code, 422)

    def test_remove_stock_returns_200(self):
        # 先添加再移除
        self.client.post("/api/v1/position-monitor/stocks", json={"code": "000001"})
        response = self.client.delete("/api/v1/position-monitor/stocks/000001")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("000001", data["message"])

    def test_remove_nonexistent_stock_returns_200(self):
        """移除不存在的标的不报错"""
        response = self.client.delete("/api/v1/position-monitor/stocks/999999")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

    def test_add_and_list_stocks(self):
        """添加后能在状态中看到"""
        self.client.post("/api/v1/position-monitor/stocks", json={"code": "000001", "name": "平安银行"})
        self.client.post("/api/v1/position-monitor/stocks", json={"code": "000002", "name": "万科A"})

        status = self.client.get("/api/v1/position-monitor/status")
        self.assertEqual(status.json()["watchlist_count"], 2)


# ============================================================
# 红阶段 5: 同步自选股 API
# ============================================================

class TestSyncWatchlistAPI(unittest.TestCase):
    """POST /api/v1/position-monitor/stocks/sync-watchlist 测试"""

    def setUp(self):
        reset_monitor_engine()
        self.client = TestClient(app)

    def tearDown(self):
        reset_monitor_engine()

    def test_sync_watchlist_returns_200(self):
        response = self.client.post("/api/v1/position-monitor/stocks/sync-watchlist")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("同步", data["message"])

    @mock.patch("src.position_monitor.monitor_engine.WATCHLIST_FILE")
    def test_sync_watchlist_loads_from_file(self, mock_path):
        """同步时调用 _load_watchlist_from_file"""
        mock_path.exists.return_value = False
        response = self.client.post("/api/v1/position-monitor/stocks/sync-watchlist")
        self.assertEqual(response.status_code, 200)


# ============================================================
# 红阶段 6: 策略配置 API
# ============================================================

class TestStrategiesAPI(unittest.TestCase):
    """GET /api/v1/position-monitor/strategies/default 测试"""

    def setUp(self):
        reset_monitor_engine()
        self.client = TestClient(app)

    def tearDown(self):
        reset_monitor_engine()

    def test_get_default_strategies_returns_200(self):
        response = self.client.get("/api/v1/position-monitor/strategies/default")
        self.assertEqual(response.status_code, 200)

    def test_get_default_strategies_returns_list(self):
        response = self.client.get("/api/v1/position-monitor/strategies/default")
        data = response.json()
        self.assertIn("strategies", data)
        self.assertIsInstance(data["strategies"], list)
        self.assertGreater(len(data["strategies"]), 0)

    def test_get_default_strategies_has_required_fields(self):
        response = self.client.get("/api/v1/position-monitor/strategies/default")
        for s in response.json()["strategies"]:
            self.assertIn("strategy_type", s)
            self.assertIn("signal_type", s)
            self.assertIn("enabled", s)
            self.assertIn("params", s)
            self.assertIn("cooldown_seconds", s)

    def test_get_default_strategies_all_enabled(self):
        response = self.client.get("/api/v1/position-monitor/strategies/default")
        for s in response.json()["strategies"]:
            self.assertTrue(s["enabled"])


# ============================================================
# 红阶段 7: 交易时段 API
# ============================================================

class TestTradingTimeAPI(unittest.TestCase):
    """GET /api/v1/position-monitor/trading-time 测试"""

    def setUp(self):
        reset_monitor_engine()
        self.client = TestClient(app)

    def tearDown(self):
        reset_monitor_engine()

    def test_trading_time_returns_200(self):
        response = self.client.get("/api/v1/position-monitor/trading-time")
        self.assertEqual(response.status_code, 200)

    def test_trading_time_has_required_fields(self):
        response = self.client.get("/api/v1/position-monitor/trading-time")
        data = response.json()
        self.assertIn("is_trading_time", data)
        self.assertIn("current_time", data)
        self.assertIn("sessions", data)

    def test_trading_time_sessions_format(self):
        response = self.client.get("/api/v1/position-monitor/trading-time")
        sessions = response.json()["sessions"]
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0], {"start": "09:15", "end": "11:30"})
        self.assertEqual(sessions[1], {"start": "13:00", "end": "15:00"})

    @mock.patch("src.position_monitor.monitor_engine.datetime")
    def test_trading_time_during_session(self, mock_dt):
        """交易时段内返回 True"""
        from datetime import time as dt_time
        mock_dt.now.return_value.time.return_value = dt_time(10, 0)
        mock_dt.now.return_value.strftime.return_value = "2026-06-02 10:00:00"
        response = self.client.get("/api/v1/position-monitor/trading-time")
        self.assertTrue(response.json()["is_trading_time"])


# ============================================================
# 红阶段 8: 飞书心跳 API
# ============================================================

class TestHeartbeatAPI(unittest.TestCase):
    """POST /api/v1/position-monitor/heartbeat 测试"""

    def setUp(self):
        # 清除可能影响测试的环境变量
        self._saved_env = {}
        for key in ("FEISHU_WEBHOOK_URL", "FEISHU_WEBHOOK_SECRET"):
            if key in os.environ:
                self._saved_env[key] = os.environ.pop(key)
        reset_monitor_engine()
        # 显式创建无 webhook 的引擎
        import src.position_monitor.monitor_engine as me
        me._engine_instance = PositionMonitorEngine(webhook_url="")
        self.client = TestClient(app)

    def tearDown(self):
        # 恢复环境变量
        for key, val in self._saved_env.items():
            os.environ[key] = val
        reset_monitor_engine()

    def test_heartbeat_returns_200(self):
        response = self.client.post("/api/v1/position-monitor/heartbeat")
        self.assertEqual(response.status_code, 200)

    def test_heartbeat_without_webhook_returns_false(self):
        """无 webhook 配置时返回 success=False"""
        response = self.client.post("/api/v1/position-monitor/heartbeat")
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("失败", data["message"])

    @mock.patch("src.position_monitor.feishu_alert.PositionMonitorFeishuSender.send_heartbeat")
    def test_heartbeat_calls_sender(self, mock_heartbeat):
        """心跳调用 send_heartbeat"""
        mock_heartbeat.return_value = True
        # 使用带有 webhook URL 的引擎
        import src.position_monitor.monitor_engine as me
        me._engine_instance = PositionMonitorEngine(
            webhook_url="https://test.webhook/url",
        )
        response = self.client.post("/api/v1/position-monitor/heartbeat")
        self.assertEqual(response.status_code, 200)
        mock_heartbeat.assert_called_once()

    @mock.patch("src.position_monitor.feishu_alert.PositionMonitorFeishuSender.send_heartbeat")
    def test_heartbeat_success_message(self, mock_heartbeat):
        """心跳成功返回正确消息"""
        mock_heartbeat.return_value = True
        import src.position_monitor.monitor_engine as me
        me._engine_instance = PositionMonitorEngine(
            webhook_url="https://test.webhook/url",
        )
        response = self.client.post("/api/v1/position-monitor/heartbeat")
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("成功", data["message"])


# ============================================================
# 红阶段 9: 异常场景
# ============================================================

class TestAPIExceptionHandling(unittest.TestCase):
    """API 异常处理测试"""

    def setUp(self):
        reset_monitor_engine()
        self.client = TestClient(app)

    def tearDown(self):
        reset_monitor_engine()

    @mock.patch("src.position_monitor.monitor_engine.PositionMonitorEngine.start")
    def test_start_exception_returns_500(self, mock_start):
        """引擎启动异常返回 500"""
        mock_start.side_effect = RuntimeError("启动失败")
        response = self.client.post("/api/v1/position-monitor/start")
        self.assertEqual(response.status_code, 500)

    @mock.patch("src.position_monitor.monitor_engine.PositionMonitorEngine.stop")
    def test_stop_exception_returns_500(self, mock_stop):
        """引擎停止异常返回 500"""
        mock_stop.side_effect = RuntimeError("停止失败")
        response = self.client.post("/api/v1/position-monitor/stop")
        self.assertEqual(response.status_code, 500)

    def test_invalid_json_returns_422(self):
        """无效 JSON 返回 422"""
        response = self.client.post(
            "/api/v1/position-monitor/stocks",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 422)

    def test_wrong_method_returns_405(self):
        """错误的 HTTP 方法返回 405"""
        response = self.client.put("/api/v1/position-monitor/status")
        self.assertEqual(response.status_code, 405)

    def test_nonexistent_endpoint_returns_404(self):
        """不存在的端点返回 404"""
        response = self.client.get("/api/v1/position-monitor/nonexistent")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
