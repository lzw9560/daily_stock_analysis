# -*- coding: utf-8 -*-
"""
TDD: 飞书告警通知模块单元测试

测试覆盖：
- PositionMonitorFeishuSender 初始化
- HMAC-SHA256 签名构建
- 安全关键词添加
- 信号颜色/标签/徽章映射
- 飞书交互卡片构建
- send_signal 各种场景（成功/失败/超时/连接错误）
- send_batch_signals 批量发送
- send_heartbeat 心跳检测
"""
import base64
import hashlib
import hmac
import os
import sys
import time
import unittest
from unittest import mock
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.position_monitor.feishu_alert import PositionMonitorFeishuSender
from src.position_monitor.strategies import (
    SignalType,
    StrategyType,
    TriggerSignal,
)


def _make_signal(
    code="000001",
    name="平安银行",
    signal_type=SignalType.BUY,
    strategy_type=StrategyType.CHANGE_THRESHOLD,
    current_price=12.50,
    change_pct=5.5,
    trigger_value=5.5,
    threshold=5.0,
    message="测试信号",
    extra=None,
):
    return TriggerSignal(
        code=code,
        name=name,
        signal_type=signal_type,
        strategy_type=strategy_type,
        current_price=current_price,
        change_pct=change_pct,
        trigger_value=trigger_value,
        threshold=threshold,
        message=message,
        extra=extra or {},
    )


# ============================================================
# 红阶段 1: 初始化
# ============================================================

class TestFeishuSenderInit(unittest.TestCase):
    """飞书发送器初始化测试"""

    def test_init_with_basic_params(self):
        sender = PositionMonitorFeishuSender(
            webhook_url="https://open.feishu.cn/test",
        )
        self.assertEqual(sender._webhook_url, "https://open.feishu.cn/test")
        self.assertEqual(sender._webhook_secret, "")
        self.assertEqual(sender._webhook_keyword, "")
        self.assertTrue(sender._verify_ssl)

    def test_init_with_all_params(self):
        sender = PositionMonitorFeishuSender(
            webhook_url="https://open.feishu.cn/test",
            webhook_secret="my-secret",
            webhook_keyword="持仓监控",
            verify_ssl=False,
        )
        self.assertEqual(sender._webhook_url, "https://open.feishu.cn/test")
        self.assertEqual(sender._webhook_secret, "my-secret")
        self.assertEqual(sender._webhook_keyword, "持仓监控")
        self.assertFalse(sender._verify_ssl)

    def test_init_strips_secret_whitespace(self):
        sender = PositionMonitorFeishuSender(
            webhook_url="https://open.feishu.cn/test",
            webhook_secret="  secret-with-spaces  ",
        )
        self.assertEqual(sender._webhook_secret, "secret-with-spaces")

    def test_init_strips_keyword_whitespace(self):
        sender = PositionMonitorFeishuSender(
            webhook_url="https://open.feishu.cn/test",
            webhook_keyword="  关键词  ",
        )
        self.assertEqual(sender._webhook_keyword, "关键词")


# ============================================================
# 红阶段 2: HMAC 签名
# ============================================================

class TestFeishuSign(unittest.TestCase):
    """飞书签名测试"""

    def test_build_sign_without_secret(self):
        """无 secret 时返回空字典"""
        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        result = sender._build_sign()
        self.assertEqual(result, {})

    @mock.patch.object(time, 'time')
    def test_build_sign_with_secret(self, mock_time):
        """有 secret 时返回 timestamp 和 sign"""
        mock_time.return_value = 1234567890
        sender = PositionMonitorFeishuSender(
            webhook_url="https://test",
            webhook_secret="test-secret",
        )
        result = sender._build_sign()
        self.assertIn("timestamp", result)
        self.assertIn("sign", result)
        self.assertEqual(result["timestamp"], "1234567890")

        # 验证签名正确性
        expected_sign = base64.b64encode(
            hmac.new(
                b"1234567890\ntest-secret",
                digestmod=hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        self.assertEqual(result["sign"], expected_sign)

    @mock.patch.object(time, 'time')
    def test_build_sign_different_timestamps_produce_different_signs(self, mock_time):
        """不同时间戳产生不同签名"""
        sender = PositionMonitorFeishuSender(
            webhook_url="https://test",
            webhook_secret="secret",
        )
        mock_time.return_value = 100
        sign1 = sender._build_sign()["sign"]
        mock_time.return_value = 200
        sign2 = sender._build_sign()["sign"]
        self.assertNotEqual(sign1, sign2)


# ============================================================
# 红阶段 3: 关键词
# ============================================================

class TestFeishuKeyword(unittest.TestCase):
    """飞书关键词测试"""

    def test_apply_keyword_without_keyword(self):
        """无关键词时返回原内容"""
        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        content = "这是一条测试消息"
        self.assertEqual(sender._apply_keyword(content), content)

    def test_apply_keyword_with_keyword(self):
        """有关键词时添加前缀"""
        sender = PositionMonitorFeishuSender(
            webhook_url="https://test",
            webhook_keyword="监控告警",
        )
        content = "这是一条测试消息"
        result = sender._apply_keyword(content)
        self.assertTrue(result.startswith("监控告警"))
        self.assertIn("这是一条测试消息", result)


# ============================================================
# 红阶段 4: 颜色/标签/徽章映射
# ============================================================

class TestFeishuColorMapping(unittest.TestCase):
    """颜色映射测试"""

    def setUp(self):
        self.sender = PositionMonitorFeishuSender(webhook_url="https://test")

    def test_buy_color_is_red(self):
        self.assertEqual(self.sender._signal_color(SignalType.BUY), "red")

    def test_sell_color_is_green(self):
        self.assertEqual(self.sender._signal_color(SignalType.SELL), "green")

    def test_alert_color_is_orange(self):
        self.assertEqual(self.sender._signal_color(SignalType.ALERT), "orange")

    def test_warning_color_is_purple(self):
        self.assertEqual(self.sender._signal_color(SignalType.WARNING), "purple")


class TestFeishuLabelMapping(unittest.TestCase):
    """标签映射测试"""

    def setUp(self):
        self.sender = PositionMonitorFeishuSender(webhook_url="https://test")

    def test_buy_label_contains_买入(self):
        self.assertIn("买入", self.sender._signal_label(SignalType.BUY))

    def test_sell_label_contains_卖出(self):
        self.assertIn("卖出", self.sender._signal_label(SignalType.SELL))

    def test_alert_label_contains_关注(self):
        self.assertIn("关注", self.sender._signal_label(SignalType.ALERT))

    def test_warning_label_contains_预警(self):
        self.assertIn("预警", self.sender._signal_label(SignalType.WARNING))


class TestFeishuBadgeMapping(unittest.TestCase):
    """徽章映射测试"""

    def setUp(self):
        self.sender = PositionMonitorFeishuSender(webhook_url="https://test")

    def test_buy_badge_is_buy(self):
        self.assertEqual(self.sender._signal_badge(SignalType.BUY), "BUY")

    def test_sell_badge_is_sell(self):
        self.assertEqual(self.sender._signal_badge(SignalType.SELL), "SELL")

    def test_alert_badge_is_关注(self):
        self.assertEqual(self.sender._signal_badge(SignalType.ALERT), "关注")

    def test_warning_badge_is_预警(self):
        self.assertEqual(self.sender._signal_badge(SignalType.WARNING), "预警")


# ============================================================
# 红阶段 5: 卡片构建
# ============================================================

class TestFeishuCardBuilding(unittest.TestCase):
    """飞书卡片构建测试"""

    def setUp(self):
        self.sender = PositionMonitorFeishuSender(webhook_url="https://test")

    def test_build_card_has_required_structure(self):
        """卡片包含必要结构"""
        signal = _make_signal()
        card = self.sender.build_card(signal)

        self.assertEqual(card["msg_type"], "interactive")
        self.assertIn("card", card)
        self.assertIn("header", card["card"])
        self.assertIn("elements", card["card"])
        self.assertEqual(len(card["card"]["elements"]), 3)  # div + hr + note

    def test_build_card_header_contains_stock_name(self):
        """卡片头部包含股票名称"""
        signal = _make_signal(name="贵州茅台")
        card = self.sender.build_card(signal)
        header_title = card["card"]["header"]["title"]["content"]
        self.assertIn("贵州茅台", header_title)

    def test_build_card_content_contains_price(self):
        """卡片内容包含当前价格"""
        signal = _make_signal(current_price=1850.00)
        card = self.sender.build_card(signal)
        content = card["card"]["elements"][0]["text"]["content"]
        self.assertIn("1850.00", content)

    def test_build_card_content_contains_change_pct(self):
        """卡片内容包含涨跌幅"""
        signal = _make_signal(change_pct=5.23)
        card = self.sender.build_card(signal)
        content = card["card"]["elements"][0]["text"]["content"]
        self.assertIn("5.23%", content)

    def test_build_card_content_contains_strategy_type(self):
        """卡片内容包含策略类型"""
        signal = _make_signal(strategy_type=StrategyType.CHANGE_THRESHOLD)
        card = self.sender.build_card(signal)
        content = card["card"]["elements"][0]["text"]["content"]
        self.assertIn("change_threshold", content)

    def test_build_card_content_contains_trigger_time(self):
        """卡片内容包含触发时间"""
        signal = _make_signal()
        card = self.sender.build_card(signal)
        content = card["card"]["elements"][0]["text"]["content"]
        self.assertIn(signal.timestamp.strftime('%Y-%m-%d %H:%M:%S'), content)

    def test_build_card_positive_change_has_red_font(self):
        """正涨跌幅使用红色字体"""
        signal = _make_signal(change_pct=5.5)
        card = self.sender.build_card(signal)
        content = card["card"]["elements"][0]["text"]["content"]
        self.assertIn("red", content)

    def test_build_card_negative_change_has_green_font(self):
        """负涨跌幅使用绿色字体"""
        signal = _make_signal(change_pct=-3.5)
        card = self.sender.build_card(signal)
        content = card["card"]["elements"][0]["text"]["content"]
        self.assertIn("green", content)

    def test_build_card_zero_change_no_color(self):
        """零涨跌幅不使用颜色标签"""
        signal = _make_signal(change_pct=0)
        card = self.sender.build_card(signal)
        content = card["card"]["elements"][0]["text"]["content"]
        self.assertNotIn("<font", content)

    def test_build_card_extra_fields_included(self):
        """额外信息字段包含在内容中"""
        signal = _make_signal(extra={"direction": "上涨", "volume_ratio": 3.5})
        card = self.sender.build_card(signal)
        content = card["card"]["elements"][0]["text"]["content"]
        self.assertIn("direction", content)
        self.assertIn("上涨", content)

    def test_build_card_note_element_has_timestamp(self):
        """底部注释包含时间戳"""
        signal = _make_signal()
        card = self.sender.build_card(signal)
        note_content = card["card"]["elements"][2]["elements"][0]["content"]
        self.assertIn("持仓监控", note_content)
        self.assertIn("自动推送", note_content)

    def test_build_card_wide_screen_mode_enabled(self):
        """宽屏模式已启用"""
        signal = _make_signal()
        card = self.sender.build_card(signal)
        self.assertTrue(card["card"]["config"]["wide_screen_mode"])


# ============================================================
# 红阶段 6: send_signal 发送逻辑
# ============================================================

class TestFeishuSendSignal(unittest.TestCase):
    """send_signal 方法测试"""

    def setUp(self):
        self.signal = _make_signal()

    def test_send_signal_no_webhook_returns_false(self):
        """无 webhook URL 时返回 False"""
        sender = PositionMonitorFeishuSender(webhook_url="")
        result = sender.send_signal(self.signal)
        self.assertFalse(result)

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_signal_success(self, mock_post):
        """发送成功返回 True"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"code": 0, "msg": "success"}

        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        result = sender.send_signal(self.signal)
        self.assertTrue(result)
        mock_post.assert_called_once()

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_signal_feishu_error_code(self, mock_post):
        """飞书返回非零 code 返回 False"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"code": 10001, "msg": "invalid token"}

        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        result = sender.send_signal(self.signal)
        self.assertFalse(result)

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_signal_http_error(self, mock_post):
        """HTTP 非 200 返回 False"""
        mock_post.return_value.status_code = 500

        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        result = sender.send_signal(self.signal)
        self.assertFalse(result)

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_signal_timeout(self, mock_post):
        """请求超时返回 False"""
        import requests as req_lib
        mock_post.side_effect = req_lib.exceptions.Timeout("timeout")

        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        result = sender.send_signal(self.signal)
        self.assertFalse(result)

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_signal_connection_error(self, mock_post):
        """连接错误返回 False"""
        import requests as req_lib
        mock_post.side_effect = req_lib.exceptions.ConnectionError("connection refused")

        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        result = sender.send_signal(self.signal)
        self.assertFalse(result)

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_signal_generic_exception(self, mock_post):
        """通用异常返回 False"""
        mock_post.side_effect = Exception("unexpected error")

        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        result = sender.send_signal(self.signal)
        self.assertFalse(result)

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_signal_includes_sign(self, mock_post):
        """发送时包含签名"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"code": 0}

        sender = PositionMonitorFeishuSender(
            webhook_url="https://test",
            webhook_secret="secret",
        )
        sender.send_signal(self.signal)
        call_args = mock_post.call_args[1]
        self.assertIn("timestamp", call_args["json"])
        self.assertIn("sign", call_args["json"])

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_signal_posts_to_correct_url(self, mock_post):
        """发送到正确的 URL"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"code": 0}

        sender = PositionMonitorFeishuSender(webhook_url="https://custom.webhook/url")
        sender.send_signal(self.signal)
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args[0][0], "https://custom.webhook/url")


# ============================================================
# 红阶段 7: send_batch_signals 批量发送
# ============================================================

class TestFeishuBatchSend(unittest.TestCase):
    """批量发送测试"""

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_batch_signals_all_success(self, mock_post):
        """全部成功返回正确统计"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"code": 0}

        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        signals = [_make_signal(code=f"00000{i}") for i in range(1, 4)]
        result = sender.send_batch_signals(signals)

        self.assertEqual(result["success"], 3)
        self.assertEqual(result["failed"], 0)

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_batch_signals_partial_failure(self, mock_post):
        """部分失败返回正确统计"""
        # 第一次成功，第二次失败，第三次成功
        mock_post.side_effect = [
            mock.MagicMock(status_code=200, json=lambda: {"code": 0}),
            mock.MagicMock(status_code=500),
            mock.MagicMock(status_code=200, json=lambda: {"code": 0}),
        ]

        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        signals = [_make_signal(code=f"00000{i}") for i in range(1, 4)]
        result = sender.send_batch_signals(signals)

        self.assertEqual(result["success"], 2)
        self.assertEqual(result["failed"], 1)

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_batch_signals_all_failed(self, mock_post):
        """全部失败返回正确统计"""
        mock_post.return_value.status_code = 500

        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        signals = [_make_signal(code=f"00000{i}") for i in range(1, 3)]
        result = sender.send_batch_signals(signals)

        self.assertEqual(result["success"], 0)
        self.assertEqual(result["failed"], 2)

    def test_send_batch_signals_empty_list(self):
        """空信号列表"""
        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        result = sender.send_batch_signals([])
        self.assertEqual(result["success"], 0)
        self.assertEqual(result["failed"], 0)

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_batch_signals_without_webhook(self, mock_post):
        """无 webhook 时全部失败"""
        sender = PositionMonitorFeishuSender(webhook_url="")
        signals = [_make_signal(), _make_signal()]
        result = sender.send_batch_signals(signals)
        self.assertEqual(result["failed"], 2)


# ============================================================
# 红阶段 8: send_heartbeat 心跳
# ============================================================

class TestFeishuHeartbeat(unittest.TestCase):
    """心跳检测测试"""

    def test_send_heartbeat_no_webhook_returns_false(self):
        """无 webhook 返回 False"""
        sender = PositionMonitorFeishuSender(webhook_url="")
        self.assertFalse(sender.send_heartbeat())

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_heartbeat_success(self, mock_post):
        """心跳成功返回 True"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"code": 0}

        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        self.assertTrue(sender.send_heartbeat())

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_heartbeat_http_failure(self, mock_post):
        """HTTP 失败返回 False"""
        mock_post.return_value.status_code = 404

        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        self.assertFalse(sender.send_heartbeat())

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_heartbeat_feishu_error(self, mock_post):
        """飞书错误码返回 False"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"code": 10001}

        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        self.assertFalse(sender.send_heartbeat())

    @mock.patch("src.position_monitor.feishu_alert.requests.post")
    def test_send_heartbeat_exception_returns_false(self, mock_post):
        """异常返回 False"""
        mock_post.side_effect = Exception("network error")

        sender = PositionMonitorFeishuSender(webhook_url="https://test")
        self.assertFalse(sender.send_heartbeat())


if __name__ == "__main__":
    unittest.main()
