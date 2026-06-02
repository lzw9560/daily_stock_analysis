# -*- coding: utf-8 -*-
"""
飞书盘中告警通知模块

基于飞书 Webhook 发送实时交易信号提醒，包含：
- 股票代码、名称、当前价格
- 触发信号类型（买入/卖出/关注/预警）
- 触发时间、策略说明
- 使用飞书交互卡片（lark_md）格式，支持彩色标记
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from datetime import datetime
from typing import Optional

import requests

from .strategies import SignalType, TriggerSignal

logger = logging.getLogger(__name__)


class PositionMonitorFeishuSender:
    """持仓监控飞书告警发送器"""

    def __init__(
        self,
        webhook_url: str,
        webhook_secret: Optional[str] = None,
        webhook_keyword: Optional[str] = None,
        verify_ssl: bool = True,
    ):
        self._webhook_url = webhook_url
        self._webhook_secret = (webhook_secret or "").strip()
        self._webhook_keyword = (webhook_keyword or "").strip()
        self._verify_ssl = verify_ssl

    # ============================================================
    #  签名 & 关键词
    # ============================================================

    def _build_sign(self) -> dict:
        """构建飞书安全签名"""
        if not self._webhook_secret:
            return {}
        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{self._webhook_secret}"
        sign = base64.b64encode(
            hmac.new(
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        return {"timestamp": timestamp, "sign": sign}

    def _apply_keyword(self, content: str) -> str:
        """添加飞书安全关键词"""
        if not self._webhook_keyword:
            return content
        return f"{self._webhook_keyword}\n{content}"

    # ============================================================
    #  信号颜色映射
    # ============================================================

    @staticmethod
    def _signal_color(signal_type: SignalType) -> str:
        """信号类型 → 飞书颜色标记"""
        return {
            SignalType.BUY: "red",
            SignalType.SELL: "green",
            SignalType.ALERT: "orange",
            SignalType.WARNING: "purple",
        }.get(signal_type, "grey")

    @staticmethod
    def _signal_label(signal_type: SignalType) -> str:
        """信号类型 → 中文标签"""
        return {
            SignalType.BUY: "🟢 买入信号",
            SignalType.SELL: "🔴 卖出信号",
            SignalType.ALERT: "🟡 关注提醒",
            SignalType.WARNING: "🟣 风险预警",
        }.get(signal_type, "⚪ 通知")

    @staticmethod
    def _signal_badge(signal_type: SignalType) -> str:
        """信号类型 → 简短标签"""
        return {
            SignalType.BUY: "BUY",
            SignalType.SELL: "SELL",
            SignalType.ALERT: "关注",
            SignalType.WARNING: "预警",
        }.get(signal_type, "通知")

    # ============================================================
    #  卡片构建
    # ============================================================

    def build_card(self, signal: TriggerSignal) -> dict:
        """构建飞书交互卡片"""
        badge = self._signal_badge(signal.signal_type)
        color = self._signal_color(signal.signal_type)
        label = self._signal_label(signal.signal_type)

        # 涨跌幅方向标记
        if signal.change_pct > 0:
            change_str = f"<font color='red'>+{signal.change_pct:.2f}%</font>"
        elif signal.change_pct < 0:
            change_str = f"<font color='green'>{signal.change_pct:.2f}%</font>"
        else:
            change_str = f"{signal.change_pct:.2f}%"

        # 构建 Markdown 内容
        content_lines = [
            f"**{label}**",
            "",
            f"**{signal.name}** ({signal.code})",
            "",
            f"当前价格：**{signal.current_price:.2f}** 元",
            f"涨跌幅：{change_str}",
            f"触发策略：{signal.strategy_type.value}",
            f"触发描述：{signal.message}",
            f"触发时间：{signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        # 额外信息
        if signal.extra:
            extra_str = " | ".join(
                f"{k}: {v}" for k, v in signal.extra.items()
            )
            content_lines.append(f"详细信息：{extra_str}")

        content = "\n".join(content_lines)

        return {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "template": color,
                    "title": {
                        "tag": "plain_text",
                        "content": f"📊 {badge} - {signal.name}",
                    }
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": content,
                        }
                    },
                    {"tag": "hr"},
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"持仓监控 · 自动推送 · {signal.timestamp.strftime('%H:%M:%S')}",
                            }
                        ],
                    },
                ],
            },
        }

    # ============================================================
    #  发送
    # ============================================================

    def send_signal(self, signal: TriggerSignal) -> bool:
        """发送单条交易信号到飞书"""
        if not self._webhook_url:
            logger.warning("飞书 Webhook 未配置，跳过推送")
            return False

        card = self.build_card(signal)
        card.update(self._build_sign())

        try:
            resp = requests.post(
                self._webhook_url,
                json=card,
                timeout=15,
                verify=self._verify_ssl,
            )
            if resp.status_code == 200:
                result = resp.json()
                code = result.get("code", -1)
                if code == 0:
                    logger.info(
                        "飞书告警发送成功: %s %s",
                        signal.code, signal.signal_type.value,
                    )
                    return True
                else:
                    logger.error(
                        "飞书返回错误: code=%s, msg=%s",
                        code, result.get("msg", "未知"),
                    )
                    return False
            else:
                logger.error("飞书请求失败: HTTP %s", resp.status_code)
                return False
        except requests.exceptions.Timeout:
            logger.error("飞书请求超时")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error("飞书连接失败: %s", e)
            return False
        except Exception as e:
            logger.error("飞书发送异常: %s", e)
            return False

    def send_batch_signals(self, signals: list[TriggerSignal]) -> dict:
        """批量发送信号，返回成功/失败统计"""
        success, failed = 0, 0
        for signal in signals:
            if self.send_signal(signal):
                success += 1
            else:
                failed += 1
        return {"success": success, "failed": failed}

    def send_heartbeat(self) -> bool:
        """发送心跳消息，用于验证飞书连接"""
        if not self._webhook_url:
            return False

        card = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "template": "blue",
                    "title": {
                        "tag": "plain_text",
                        "content": "📡 持仓监控服务 - 心跳检测",
                    }
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"✅ 监控服务运行正常\n\n启动时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        }
                    },
                ],
            },
        }
        card.update(self._build_sign())

        try:
            resp = requests.post(
                self._webhook_url, json=card, timeout=10, verify=self._verify_ssl
            )
            return resp.status_code == 200 and resp.json().get("code") == 0
        except Exception:
            return False
