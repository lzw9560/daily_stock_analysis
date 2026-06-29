"""
综合推荐列表 — 每日飞书群聊机器人通知服务

功能：
1. 从每日个股分析结果中提取推荐列表
2. 按评分/决策类型排序，筛选买入/加仓标的
3. 简述推荐理由（核心看点、操作理由、风险提示）
4. 格式化为飞书交互卡片并通过群聊机器人 Webhook 推送

用法：
    notifier = DailyRecommendationNotifier()
    notifier.send_recommendation_list(results, market_report="...")

飞书群聊机器人协议：
- 使用自定义机器人 Webhook URL
- 支持安全签名（timestamp + hmac-sha256 sign）
- 支持关键字校验（keyword）
- 使用交互卡片（msg_type=interactive）发送
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from src.analyzer import AnalysisResult

logger = logging.getLogger(__name__)


class DailyRecommendationNotifier:
    """综合推荐列表飞书群聊机器人通知服务"""

    def __init__(self, webhook_url: Optional[str] = None, config: Optional[Any] = None):
        """
        初始化通知服务

        Args:
            webhook_url: 飞书 Webhook URL（优先使用）
            config: Config 对象（次选）
        """
        self.webhook_url = (
            webhook_url
            or os.getenv("FEISHU_WEBHOOK_URL", "")
        )

        # 飞书群聊机器人安全配置
        self._webhook_secret = ""
        self._webhook_keyword = ""

        if config:
            if not self.webhook_url:
                self.webhook_url = getattr(config, "feishu_webhook_url", None) or ""
            self._webhook_secret = (getattr(config, "feishu_webhook_secret", None) or "").strip()
            self._webhook_keyword = (getattr(config, "feishu_webhook_keyword", None) or "").strip()

        self._timeout_seconds = float(getattr(config, "feishu_timeout_seconds", 30.0)) if config else 30.0
        self._verify_ssl = bool(getattr(config, "webhook_verify_ssl", True)) if config else True

        self.enabled = bool(self.webhook_url)
        if not self.enabled:
            logger.warning("飞书 Webhook URL 未配置，综合推荐通知将不会发送")
        else:
            has_sign = bool(self._webhook_secret)
            has_kw = bool(self._webhook_keyword)
            logger.info(
                "飞书群聊机器人已就绪 (签名验证=%s, 关键字校验=%s)",
                "已启用" if has_sign else "未启用",
                "已启用" if has_kw else "未启用",
            )

    # ============================================================
    #  公开方法
    # ============================================================

    def send_recommendation_list(
        self,
        results: List[Any],
        market_report: str = "",
        report_date: Optional[str] = None,
    ) -> bool:
        """
        发送综合推荐列表到飞书

        Args:
            results: AnalysisResult 列表
            market_report: 大盘复盘内容（可选）
            report_date: 报告日期（默认今天）

        Returns:
            是否发送成功
        """
        if not results:
            logger.info("无分析结果，跳过综合推荐通知")
            return True

        if not self.enabled:
            logger.info("飞书通知未启用，跳过综合推荐发送")
            return False

        try:
            if report_date is None:
                report_date = datetime.now().strftime("%Y-%m-%d")

            card = self._build_recommendation_card(results, market_report, report_date)
            success = self._send_card(card)

            if success:
                logger.info("综合推荐列表已发送到飞书 (%s 只标的)", len(results))
            return success

        except Exception as e:
            logger.error("发送综合推荐列表失败: %s", e)
            return False

    # ============================================================
    #  卡片构建
    # ============================================================

    def _build_recommendation_card(
        self,
        results: List[Any],
        market_report: str,
        report_date: str,
    ) -> dict:
        """构建综合推荐飞书交互卡片"""
        elements: List[dict] = []

        # ---- 卡片头部：日期 + 概览 ----
        buy_count = sum(1 for r in results if getattr(r, "decision_type", "") == "buy")
        sell_count = sum(1 for r in results if getattr(r, "decision_type", "") == "sell")
        hold_count = sum(
            1 for r in results
            if getattr(r, "decision_type", "") in ("hold", "")
        )
        avg_score = (
            sum(r.sentiment_score for r in results) / len(results)
            if results else 0
        )

        elements.append({
            "tag": "markdown",
            "content": (
                f"📊 **综合推荐列表**\n"
                f"日期：{report_date} | "
                f"共分析 **{len(results)}** 只标的\n"
                f"🟢 买入/加仓：**{buy_count}** | "
                f"🟡 持有/观望：**{hold_count}** | "
                f"🔴 卖出/减仓：**{sell_count}** | "
                f"平均评分：**{avg_score:.0f}**"
            ),
        })
        elements.append({"tag": "hr"})

        # ---- 大盘概览（如果有） ----
        if market_report:
            overview = market_report.strip()
            # 截取前 200 字作为摘要
            if len(overview) > 200:
                overview = overview[:200] + "..."
            elements.append({
                "tag": "markdown",
                "content": f"📈 **大盘概览**\n{overview}",
            })
            elements.append({"tag": "hr"})

        # ---- 推荐标的列表 ----
        recommendations = self._build_recommendation_list(results)
        if recommendations:
            rec_lines = ["🎯 **核心推荐标的**\n"]
            for i, rec in enumerate(recommendations, 1):
                rec_lines.append(
                    f"{i}. {rec['emoji']} **{rec['name']}**"
                    f"({rec['code']}) "
                    f"评分：{rec['score']} | {rec['advice']}"
                )
                if rec.get("reason"):
                    rec_lines.append(f"   📌 {rec['reason']}")
                if rec.get("risk_short"):
                    rec_lines.append(f"   ⚠️ {rec['risk_short']}")

            elements.append({
                "tag": "markdown",
                "content": "\n".join(rec_lines),
            })
            elements.append({"tag": "hr"})

        # ---- 观望/减仓提示 ----
        watch_sells = self._build_watch_sell_list(results)
        if watch_sells:
            lines = ["👀 **其他关注标的**\n"]
            for ws in watch_sells[:5]:
                lines.append(
                    f"• {ws['emoji']} {ws['name']}({ws['code']}) "
                    f"{ws['advice']} | 评分:{ws['score']}"
                )
            elements.append({
                "tag": "markdown",
                "content": "\n".join(lines),
            })
            elements.append({"tag": "hr"})

        # ---- 底部 ----
        elements.append({
            "tag": "markdown",
            "content": (
                f"*生成时间：{datetime.now().strftime('%H:%M:%S')}*\n"
                "*以上内容由 AI 生成，不构成投资建议*"
            ),
        })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{report_date} 综合推荐",
                },
                "template": "blue",
            },
            "elements": elements,
        }

    def _build_recommendation_list(self, results: List[Any]) -> List[Dict[str, str]]:
        """
        从分析结果中构建推荐列表

        逻辑：
        1. 按评分降序排列
        2. 优先展示买入/加仓标的（decision_type == "buy"）
        3. 每只标的分行展示：信号、名称代码、评分、操作建议、推荐理由
        """
        recommendations = []

        # 按评分降序
        sorted_results = sorted(
            results,
            key=lambda r: r.sentiment_score,
            reverse=True,
        )

        for r in sorted_results:
            decision = getattr(r, "decision_type", "hold")
            advice = getattr(r, "operation_advice", "持有")

            # 买入/加仓的排前面
            if decision != "buy":
                continue

            emoji = self._get_decision_emoji(r)

            # 简述推荐理由：优先用 key_points，其次 buy_reason
            reason = ""
            if hasattr(r, "key_points") and r.key_points:
                reason = r.key_points
            elif hasattr(r, "buy_reason") and r.buy_reason:
                reason = r.buy_reason
            # 截断过长理由
            if len(reason) > 70:
                reason = reason[:67] + "..."

            # 风险提示（简短版）
            risk_short = ""
            if hasattr(r, "risk_warning") and r.risk_warning:
                risk_short = r.risk_warning
                if len(risk_short) > 60:
                    risk_short = risk_short[:57] + "..."

            recommendations.append({
                "emoji": emoji,
                "name": r.name,
                "code": r.code,
                "score": r.sentiment_score,
                "advice": advice,
                "reason": reason,
                "risk_short": risk_short,
            })

        return recommendations

    def _build_watch_sell_list(self, results: List[Any]) -> List[Dict[str, Any]]:
        """构建观望/减仓/卖出标的列表"""
        watch_sells = []
        sorted_results = sorted(
            results,
            key=lambda r: r.sentiment_score,
            reverse=True,
        )

        for r in sorted_results:
            decision = getattr(r, "decision_type", "hold")
            if decision == "buy":
                continue

            emoji = self._get_decision_emoji(r)
            watch_sells.append({
                "emoji": emoji,
                "name": r.name,
                "code": r.code,
                "score": r.sentiment_score,
                "advice": getattr(r, "operation_advice", "持有"),
            })

        return watch_sells

    @staticmethod
    def _get_decision_emoji(result: Any) -> str:
        """根据分析结果获取信号 emoji"""
        # 优先使用 result 自带的 get_emoji 方法
        if hasattr(result, "get_emoji"):
            return result.get_emoji()

        # 根据 sentiment_score 降级
        score = result.sentiment_score
        if score >= 80:
            return "🟢"
        elif score >= 65:
            return "🟡"
        elif score >= 50:
            return "🟠"
        else:
            return "🔴"

    # ============================================================
    #  安全签名 + 发送（飞书群聊机器人协议）
    # ============================================================

    def _get_keyword_prefix(self) -> str:
        """获取飞书群聊机器人关键字校验前缀"""
        if not self._webhook_keyword:
            return ""
        return f"{self._webhook_keyword}\n"

    def _build_security_fields(self) -> Dict[str, Any]:
        """
        构建飞书群聊机器人安全签名字段

        飞书自定义机器人安全设置支持「签名校验」，
        需要 POST 时附带 timestamp 和 hmac-sha256 sign。
        """
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

        return {
            "timestamp": timestamp,
            "sign": sign,
        }

    def _send_card(self, card: dict) -> bool:
        """
        通过飞书群聊机器人 Webhook 发送交互卡片

        协议：
        - msg_type: "interactive"
        - 支持安全签名（timestamp + sign）
        - 卡片兼容 wide_screen_mode
        """
        if not self.webhook_url:
            logger.warning("飞书 Webhook URL 未配置，无法发送")
            return False

        payload: Dict[str, Any] = {"msg_type": "interactive", "card": card}

        # 附加安全签名
        security_fields = self._build_security_fields()
        payload.update(security_fields)

        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self._timeout_seconds,
                verify=self._verify_ssl,
            )
            if resp.status_code == 200:
                result = resp.json()
                code = result.get("code", result.get("StatusCode", -1))
                if code == 0:
                    logger.info("综合推荐飞书消息发送成功")
                    return True
                logger.error("飞书返回错误: %s", result.get("msg", ""))
            else:
                logger.error("飞书请求失败: HTTP %d, 响应: %s", resp.status_code, resp.text[:300])
            return False
        except requests.exceptions.Timeout:
            logger.error("飞书请求超时 (%.0fs)", self._timeout_seconds)
            return False
        except requests.exceptions.SSLError as exc:
            logger.error("飞书请求 SSL 错误: %s", exc)
            return False
        except Exception as exc:
            logger.error("飞书请求异常: %s", exc)
            return False
