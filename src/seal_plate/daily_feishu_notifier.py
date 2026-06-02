"""
打板助手早盘推荐 + 收盘复盘飞书通知服务

功能：
1. 每日9:00前发送当日推荐到飞书
2. 收盘后发送复盘报告到飞书
3. 提供次日持仓建议
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Optional

import requests

from .models import SealPlateReport
from .recommender import RecommendationEngine, DailyRecommendationResult
from .capital_flow_analyzer import CapitalFlowAnalyzer, FundFlowAnalysis
from .recommendation_log import RecommendationLogStore

logger = logging.getLogger(__name__)


class DailyFeishuNotifier:
    """每日飞书通知服务
    
    负责：
    - 早盘推荐通知（9:00前）
    - 收盘复盘通知（15:30后）
    - 次日持仓建议
    """

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK_URL", "")
        self.enabled = bool(self.webhook_url)

        env_enabled = os.getenv("SEAL_PLATE_NOTIFICATION_ENABLED", "true").lower()
        if env_enabled in ("false", "0", "no"):
            self.enabled = False

    def send_morning_recommendation(
        self,
        report: SealPlateReport,
        recommendations: DailyRecommendationResult,
        fund_analysis: FundFlowAnalysis,
    ) -> bool:
        """发送早盘推荐到飞书"""
        if not self.enabled:
            logger.info("飞书通知未启用，跳过早盘推荐发送")
            return True

        try:
            card = self._build_morning_card(report, recommendations, fund_analysis)
            return self._send_card(card)
        except Exception as e:
            logger.error("发送早盘推荐失败: %s", e)
            return False

    def send_evening_review(
        self,
        review_data: dict,
        next_day_advice: list[str],
    ) -> bool:
        """发送收盘复盘报告到飞书"""
        if not self.enabled:
            logger.info("飞书通知未启用，跳过复盘报告发送")
            return True

        try:
            card = self._build_evening_card(review_data, next_day_advice)
            return self._send_card(card)
        except Exception as e:
            logger.error("发送复盘报告失败: %s", e)
            return False

    def send_quick_alert(self, title: str, content: str) -> bool:
        """发送快速通知"""
        if not self.enabled:
            return True

        try:
            card = {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "blue",
                },
                "elements": [
                    {"tag": "markdown", "content": content},
                    {"tag": "hr"},
                    {"tag": "markdown", "content": "*系统自动生成，仅供参考*"},
                ],
            }
            return self._send_card(card)
        except Exception as e:
            logger.error("发送快速通知失败: %s", e)
            return False

    # ========================
    #  卡片构建
    # ========================

    def _build_morning_card(
        self,
        report: SealPlateReport,
        recommendations: DailyRecommendationResult,
        fund_analysis: FundFlowAnalysis,
    ) -> dict:
        """构建早盘推荐飞书卡片"""
        date_label = recommendations.label or report.date

        elements: list[dict] = []

        # 标题信息
        elements.append({
            "tag": "markdown",
            "content": (
                f"📊 **市场概况**\n"
                f"涨停总数: **{report.total_limit_up}** | "
                f"炸板: {report.bomb_count} | "
                f"最高连板: {report.max_consecutive}板\n"
                f"情绪: **{report.sentiment_phase}**({report.sentiment_index:.0f}分) | "
                f"资金情绪: **{fund_analysis.fund_sentiment}**"
            ),
        })
        elements.append({"tag": "hr"})

        # 板块热度 + 资金流向
        hot_sector_lines = []
        for sector, count in report.sector_hot[:5]:
            inflow_info = ""
            for fs in fund_analysis.hot_sectors_inflow[:5]:
                if fs.get("name", "") == sector:
                    net = fs.get("net_inflow", 0)
                    inflow_info = f" 资金{'流入' if net > 0 else '流出'}{abs(net):.0f}亿"
                    break
            hot_sector_lines.append(f"• **{sector}** {count}只涨停{inflow_info}")

        if hot_sector_lines:
            elements.append({
                "tag": "markdown",
                "content": "🔥 **热门板块（资金+涨停双重验证）**\n" + "\n".join(hot_sector_lines),
            })
            elements.append({"tag": "hr"})

        # 推荐标的
        if recommendations.recommendations:
            rec_lines = ["🎯 **今日建仓推荐**\n"]
            for i, rec in enumerate(recommendations.recommendations, 1):
                stock = rec.stock
                confidence_emoji = {"高": "🟢", "中": "🟡", "低": "🔴"}.get(rec.confidence, "⚪")
                rec_lines.append(
                    f"{i}. {confidence_emoji} **{stock.name}**({stock.code}) "
                    f"评分:{rec.score} | 仓位:{rec.suggested_position_pct}%"
                )
                if rec.reasons:
                    rec_lines.append(f"   📌 {rec.reasons[0][:50]}")
                # 买入点位
                for bs in fund_analysis.buy_suggestions:
                    if bs.get("code") == stock.code:
                        bp = bs["buy_point"]
                        rec_lines.append(
                            f"   💰 买入区间:{bp['entry_range']} | "
                            f"止损:{bs['stop_loss']['price']} | "
                            f"目标:{bs['target_price']['price']}"
                        )
                        break

            elements.append({
                "tag": "markdown",
                "content": "\n".join(rec_lines),
            })
            elements.append({"tag": "hr"})

        # 风险提示
        all_risks = []
        # 推荐中的风险
        for rec in recommendations.recommendations:
            for w in rec.risk_warnings[:2]:
                all_risks.append(f"• {w}")
        # 资金分析中的风险
        for alert in fund_analysis.risk_alerts[:3]:
            all_risks.append(f"• {alert}")

        if all_risks:
            elements.append({
                "tag": "markdown",
                "content": "⚠️ **风险提示**\n" + "\n".join(all_risks[:8]),
            })
            elements.append({"tag": "hr"})

        # 策略建议
        if recommendations.strategy_notes:
            elements.append({
                "tag": "markdown",
                "content": "💡 **策略建议**\n" + "\n".join(
                    f"• {n}" for n in recommendations.strategy_notes[:3]
                ),
            })
            elements.append({"tag": "hr"})

        # 大基金关注
        if fund_analysis.major_fund_focus:
            elements.append({
                "tag": "markdown",
                "content": "🏛 **大基金关注方向**\n" + "\n".join(
                    f"• {s}" for s in fund_analysis.major_fund_focus[:5]
                ),
            })
            elements.append({"tag": "hr"})

        elements.append({
            "tag": "markdown",
            "content": "*⚠️ 以上为AI分析结果，不构成投资建议。投资有风险，入市需谨慎。*",
        })

        return {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🎯 早盘推荐 | {date_label}",
                },
                "template": "red",
            },
            "elements": elements,
        }

    def _build_evening_card(
        self,
        review_data: dict,
        next_day_advice: list[str],
    ) -> dict:
        """构建收盘复盘飞书卡片"""
        date = review_data.get("date", "")
        elements: list[dict] = []

        # 复盘概览
        settled = review_data.get("settled_count", 0)
        win_rate = review_data.get("win_rate", 0)
        avg_return = review_data.get("avg_return", 0)
        summary = review_data.get("summary", "暂无总结")

        elements.append({
            "tag": "markdown",
            "content": (
                f"📋 **复盘概览**\n"
                f"已结算: **{settled}**笔 | "
                f"胜率: **{win_rate:.1f}%** | "
                f"平均收益: **{avg_return:+.2f}%**\n"
                f"结论: {summary}"
            ),
        })
        elements.append({"tag": "hr"})

        # LLM分析洞察
        success_patterns = review_data.get("success_patterns", [])
        failure_patterns = review_data.get("failure_patterns", [])

        if success_patterns:
            elements.append({
                "tag": "markdown",
                "content": "✅ **成功模式**\n" + "\n".join(
                    f"• {p}" for p in success_patterns[:3]
                ),
            })

        if failure_patterns:
            elements.append({
                "tag": "markdown",
                "content": "❌ **失败模式**\n" + "\n".join(
                    f"• {p}" for p in failure_patterns[:3]
                ),
            })

        if success_patterns or failure_patterns:
            elements.append({"tag": "hr"})

        # 板块洞察
        high_sectors = review_data.get("high_momentum_sectors", [])
        risk_sectors = review_data.get("risk_sectors", [])

        if high_sectors:
            elements.append({
                "tag": "markdown",
                "content": "📈 **高动量板块**\n" + " ".join(
                    f"`{s}`" for s in high_sectors
                ),
            })

        if risk_sectors:
            elements.append({
                "tag": "markdown",
                "content": "📉 **回避板块**\n" + " ".join(
                    f"`{s}`" for s in risk_sectors
                ),
            })

        if high_sectors or risk_sectors:
            elements.append({"tag": "hr"})

        # 次日持仓建议
        if next_day_advice:
            elements.append({
                "tag": "markdown",
                "content": "🔮 **次日持仓建议**\n" + "\n".join(
                    f"• {a}" for a in next_day_advice[:8]
                ),
            })
            elements.append({"tag": "hr"})

        # 仓位建议
        position_advice = review_data.get("position_advice", "")
        if position_advice:
            elements.append({
                "tag": "markdown",
                "content": f"💰 **仓位管理**\n{position_advice}",
            })
            elements.append({"tag": "hr"})

        # 策略调整
        adjustments = review_data.get("strategy_adjustments", [])
        if adjustments:
            elements.append({
                "tag": "markdown",
                "content": "🔧 **策略调整建议**\n" + "\n".join(
                    f"• {a}" for a in adjustments[:5]
                ),
            })
            elements.append({"tag": "hr"})

        elements.append({
            "tag": "markdown",
            "content": "*系统自动复盘，仅供参考。投资有风险，入市需谨慎。*",
        })

        return {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📊 收盘复盘 | {date}",
                },
                "template": "blue",
            },
            "elements": elements,
        }

    @staticmethod
    def _send_card(card: dict) -> bool:
        """发送飞书交互卡片"""
        payload = {"msg_type": "interactive", "card": card}
        url = os.getenv("FEISHU_WEBHOOK_URL", "")

        if not url:
            logger.warning("飞书 Webhook URL 未配置")
            return False

        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                result = resp.json()
                code = result.get("code", result.get("StatusCode", -1))
                if code == 0:
                    logger.info("飞书消息发送成功")
                    return True
                logger.error("飞书返回错误: %s", result.get("msg", ""))
            else:
                logger.error("飞书请求失败: HTTP %d", resp.status_code)
            return False
        except Exception as exc:
            logger.error("飞书请求异常: %s", exc)
            return False


# ========================
#  便捷函数
# ========================

def build_morning_notification_content(
    report: SealPlateReport,
    recommendations: DailyRecommendationResult,
    fund_analysis: FundFlowAnalysis,
) -> str:
    """构建早盘通知文本内容（供非飞书渠道使用）"""
    notifier = DailyFeishuNotifier()
    # 使用飞书卡片发送
    return notifier.send_morning_recommendation(report, recommendations, fund_analysis)


def build_evening_notification_content(
    review_data: dict,
    next_day_advice: list[str],
) -> str:
    """构建复盘通知文本内容"""
    notifier = DailyFeishuNotifier()
    return notifier.send_evening_review(review_data, next_day_advice)
