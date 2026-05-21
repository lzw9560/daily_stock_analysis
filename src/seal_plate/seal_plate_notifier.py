"""
打板助手飞书通知器
基于 SEAL_PLATE_ARCHITECTURE.md v2.1 §2.3

推送内容: 涨停总数/炸板率、强势 TOP8、龙头股、板块热度 TOP5、风险提示
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests

from .models import SealPlateReport, SealPlateStock

logger = logging.getLogger(__name__)


class SealPlateNotifier:
    """打板助手通知器 — 架构文档 §2.3"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK_URL", "")
        self.enabled = bool(self.webhook_url)

        # 环境变量开关 — 架构文档 §2.3
        env_enabled = os.getenv("SEAL_PLATE_NOTIFICATION_ENABLED", "true").lower()
        if env_enabled in ("false", "0", "no"):
            self.enabled = False

    # ========================
    #  发送完整报告
    # ========================

    def send_report(self, report: SealPlateReport) -> bool:
        """发送打板分析报告到飞书"""
        if not report.strong_stocks and not report.leader_stocks:
            self.logger.info("没有强势涨停股，跳过通知")
            return True

        if not self.enabled:
            return True

        try:
            card = self._build_report_card(report)
            success = self._send_card(card)
            if success:
                self.logger.info(
                    "打板报告发送成功: %d只强势股, 情绪:%s(%d)",
                    len(report.strong_stocks),
                    report.sentiment_phase,
                    int(report.sentiment_index),
                )
            else:
                self.logger.error("打板报告发送失败")
            return success
        except Exception as exc:
            self.logger.error("发送打板报告异常: %s", exc)
            return False

    # ========================
    #  发送个股预警
    # ========================

    def send_alert(self, stock: SealPlateStock, alert_type: str = "打板信号") -> bool:
        """发送个股预警"""
        if not self.enabled:
            return True

        try:
            card = self._build_alert_card(stock, alert_type)
            return self._send_card(card)
        except Exception as exc:
            self.logger.error("发送预警失败: %s", exc)
            return False

    # ========================
    #  构建卡片
    # ========================

    @staticmethod
    def _send_card(card: dict) -> bool:
        """发送飞书交互卡片"""
        payload = {"msg_type": "interactive", "card": card}
        url = os.getenv("FEISHU_WEBHOOK_URL", "")

        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                result = resp.json()
                code = result.get("code", result.get("StatusCode", -1))
                if code == 0:
                    return True
                logger.error("飞书返回错误: %s", result.get("msg", ""))
            else:
                logger.error("飞书请求失败: HTTP %d", resp.status_code)
            return False
        except Exception as exc:
            logger.error("飞书请求异常: %s", exc)
            return False

    def _build_report_card(self, report: SealPlateReport) -> dict:
        """构建飞书报告卡片 — 架构文档 §7.1"""
        # 强势股 TOP8
        strong_lines: list[str] = []
        for i, stock in enumerate(report.strong_stocks[:8], 1):
            seal = stock.seal_time or "盘中"
            score_emoji = "⭐" if stock.score >= 85 else ("🔥" if stock.score >= 70 else "📊")
            strong_lines.append(
                f"{i}. {score_emoji} **{stock.name}**({stock.code}) "
                f"+{stock.change_pct:.2f}% 封板:{seal} 评分:{stock.score}"
            )
            if stock.reason:
                strong_lines.append(f"   📌 {stock.reason[:30]}")

        # 龙头股
        leader_lines: list[str] = []
        for stock in report.leader_stocks:
            sector = stock.sector or "其他"
            leader_lines.append(f"- 👑 **{stock.name}**({stock.code}) [{sector}] 评分:{stock.score}")

        # 板块热度
        sector_lines: list[str] = []
        for sector, count in report.sector_hot[:5]:
            sector_lines.append(f"- {sector}: {count}只")

        # 风险提示
        warning_text = ""
        if report.warnings:
            warning_lines = "\n".join(f"- {w}" for w in report.warnings)
            warning_text = f"\n⚠️ **风险提示**\n{warning_lines}"

        elements: list[dict] = [
            {
                "tag": "markdown",
                "content": (
                    f"📊 **涨停总数**: {report.total_limit_up} | "
                    f"💥 **炸板**: {report.bomb_count} | "
                    f"🔥 **强势**: {len(report.strong_stocks)}\n"
                    f"🏔 **最高连板**: {report.max_consecutive}板 | "
                    f"👑 **龙头**: {len(report.leader_stocks)}\n"
                    f"💭 **情绪**: {report.sentiment_phase}({report.sentiment_index:.0f}分)"
                ),
            },
            {"tag": "hr"},
        ]

        if sector_lines:
            elements.append({
                "tag": "markdown",
                "content": "📂 **板块热度 TOP5**\n" + "\n".join(sector_lines),
            })
            elements.append({"tag": "hr"})

        if leader_lines:
            elements.append({"tag": "markdown", "content": "👑 **各板块龙头**\n" + "\n".join(leader_lines)})
            elements.append({"tag": "hr"})

        elements.append({"tag": "markdown", "content": "**🔥 强势涨停 TOP8**"})
        elements.append({
            "tag": "markdown",
            "content": "\n".join(strong_lines) if strong_lines else "暂无数据",
        })

        if warning_text:
            elements.append({"tag": "hr"})
            elements.append({"tag": "markdown", "content": warning_text})

        elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": "*仅供参考，不构成投资建议*"})

        return {
            "header": {
                "title": {"tag": "plain_text", "content": f"🔥 打板助手 | {report.date}"},
                "template": "red",
            },
            "elements": elements,
        }

    @staticmethod
    def _build_alert_card(stock: SealPlateStock, alert_type: str) -> dict:
        """构建个股预警卡片"""
        eight_status = f"{stock.eight_standard_pass}/8 通过" if stock.eight_standard_pass else "未评估"
        risk_emoji = {0: "🟢", 1: "🟡", 2: "🔴"}.get(stock.risk_level, "⚪")
        return {
            "header": {
                "title": {"tag": "plain_text", "content": f"⚡ {alert_type}"},
                "template": "red",
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": (
                        f"**{stock.name}**({stock.code})\n\n"
                        f"📈 涨幅: **{stock.change_pct:+.2f}%**\n"
                        f"💰 现价: {stock.close_price:.2f}\n"
                        f"🔥 评分: {stock.score}/100 | 连板: {stock.consecutive_days}d\n"
                        f"📊 换手率: {stock.turnover_rate:.2f}%\n"
                        f"✅ 八项标准: {eight_status}\n"
                        f"{risk_emoji} 风险级别: {stock.risk_level}\n"
                        f"🏷 板块: {stock.sector or '未知'}\n"
                        f"📌 原因: {stock.reason or '暂无'}"
                    ),
                },
                {"tag": "hr"},
                {"tag": "markdown", "content": "*仅供参考，不构成投资建议*"},
            ],
        }
