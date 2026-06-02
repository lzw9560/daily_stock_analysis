# -*- coding: utf-8 -*-
"""
盘前资讯简报服务 (Pre-market News Briefing)
===========================================

功能:
1. 自动抓取国内外宏观新闻、国际局势、地缘冲突等影响A股的消息面
2. 汇总并分析消息面，输出市场情绪判断
3. 基于消息面+策略逻辑，生成重点关注板块与规避板块列表
4. 每日盘前通过飞书推送简报

数据源:
- 东方财富新闻 (eastmoney)
- 财联社快讯 (cls)
- 同花顺热点 (THS)
- 新浪财经 (sina)

使用方式:
    service = NewsBriefingService()
    briefing = service.generate_briefing()
    service.send_to_feishu(briefing)
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

from .cache_manager import get_cache

logger = logging.getLogger(__name__)


class NewsCategory(str, Enum):
    """新闻分类"""
    MACRO = "宏观政策"          # 央行政策、财政政策、GDP等
    INTERNATIONAL = "国际局势"   # 地缘冲突、外交关系、贸易摩擦
    INDUSTRY = "产业政策"       # 行业政策、补贴、监管
    MARKET = "市场动态"         # 资金面、IPO、交易规则
    SECTOR = "板块热点"         # 具体板块新闻
    RISK = "风险事件"           # 黑天鹅、暴雷、退市


class SentimentLabel(str, Enum):
    """情绪标签"""
    BULLISH = "bullish"         # 看多
    BEARISH = "bearish"         # 看空
    NEUTRAL = "neutral"         # 中性


@dataclass
class NewsItem:
    """单条新闻"""
    title: str
    summary: str = ""
    source: str = ""            # 来源
    url: str = ""
    category: NewsCategory = NewsCategory.MARKET
    sentiment: SentimentLabel = SentimentLabel.NEUTRAL
    impact_score: int = 0       # 影响程度 0-100
    related_sectors: List[str] = field(default_factory=list)
    timestamp: str = ""


@dataclass
class SectorAnalysis:
    """板块分析"""
    name: str
    sentiment: SentimentLabel
    reason: str
    confidence: int = 50        # 置信度 0-100
    action: str = ""            # 建议动作: 关注/加仓/回避/减仓


@dataclass
class NewsBriefing:
    """盘前简报"""
    date: str
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 新闻汇总
    total_news: int = 0
    key_news: List[NewsItem] = field(default_factory=list)

    # 市场情绪
    overall_sentiment: SentimentLabel = SentimentLabel.NEUTRAL
    sentiment_score: int = 50            # 0-100, 50=中性, >50偏多, <50偏空

    # 板块分析
    focus_sectors: List[SectorAnalysis] = field(default_factory=list)    # 重点关注
    avoid_sectors: List[SectorAnalysis] = field(default_factory=list)    # 规避板块

    # 风险提示
    risk_alerts: List[str] = field(default_factory=list)

    # 操作建议
    position_advice: str = ""            # 仓位建议
    strategy_notes: List[str] = field(default_factory=list)


class NewsBriefingService:
    """
    盘前资讯简报服务

    数据抓取优先级:
    1. 东方财富新闻 (速度快、覆盖面广)
    2. 同花顺热点 (板块情绪分析)
    3. 财联社 (时效性强)
    """

    # 板块与关键词映射
    SECTOR_KEYWORDS: Dict[str, List[str]] = {
        "半导体/芯片": ["芯片", "半导体", "光刻机", "EDA", "先进封装", "存储", "HBM", "AI芯片", "GPU"],
        "人工智能": ["AI", "人工智能", "大模型", "ChatGPT", "GPT", "多模态", "AGI", "智能体", "Agent"],
        "新能源/光伏": ["光伏", "太阳能", "储能", "锂电池", "固态电池", "钠电池", "钙钛矿", "TOPCon"],
        "新能源汽车": ["新能源汽车", "电动车", "智能驾驶", "自动驾驶", "充电桩", "换电", "汽车零部件"],
        "军工/航天": ["军工", "航天", "卫星", "导弹", "国防", "军贸", "大飞机", "C919"],
        "医药/医疗": ["医药", "创新药", "医疗器械", "生物制药", "CXO", "疫苗", "中药", "减肥药"],
        "消费/食品": ["消费", "白酒", "食品", "预制菜", "免税", "新零售", "直播电商"],
        "金融/券商": ["券商", "银行", "保险", "金融科技", "数字货币", "支付", "信创"],
        "地产/基建": ["房地产", "基建", "城市更新", "保障房", "REITs", "水利"],
        "数字经济": ["数据要素", "数字经济", "信创", "国产替代", "数据安全", "算力"],
        "机器人/自动化": ["机器人", "人形机器人", "具身智能", "工业自动化", "智能制造"],
        "低空经济": ["低空经济", "eVTOL", "飞行汽车", "无人机", "通用航空"],
        "能源/电力": ["电力", "电网", "虚拟电厂", "核电", "氢能", "特高压"],
    }

    # 风险关键词
    RISK_KEYWORDS = [
        "制裁", "关税", "贸易战", "地缘冲突", "军事冲突", "战争",
        "暴雷", "退市", "ST", "*ST", "立案调查", "财务造假",
        "加息", "缩表", "通胀超预期", "经济衰退", "金融危机",
        "限售解禁", "大股东减持", "质押爆仓", "债务违约",
    ]

    # 宏观利好关键词
    BULLISH_KEYWORDS = [
        "降准", "降息", "放水", "宽松", "刺激", "利好",
        "LPR下调", "MLF", "逆回购", "减税", "补贴",
        "GDP超预期", "PMI回升", "社融超预期", "出口增长",
        "外资流入", "北向资金净买入",
    ]

    def __init__(
        self,
        webhook_url: Optional[str] = None,
    ):
        self._webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK_URL", "")
        self._cache = get_cache()
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
        })

    # ============================================================
    #  新闻抓取
    # ============================================================

    def _fetch_eastmoney_news(self) -> List[NewsItem]:
        """抓取东方财富新闻"""
        items: List[NewsItem] = []
        cache_key = f"eastmoney_news:{datetime.now().strftime('%Y%m%d')}"
        cached = self._cache.get("news", cache_key, default_ttl=1800)
        if cached:
            return cached

        try:
            url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
            # 尝试获取要闻列表
            resp = self._session.get(
                "https://np-listapi.eastmoney.com/comm/web/getNewsList",
                params={
                    "client": "web",
                    "biz": "web_news",
                    "columnCode": "yw",  # 要闻
                    "pageIndex": 1,
                    "pageSize": 30,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                news_list = data.get("data", {}).get("list", [])
                for n in news_list[:30]:
                    title = n.get("title", "")
                    summary = n.get("digest", "")
                    item = NewsItem(
                        title=title,
                        summary=summary,
                        source="东方财富",
                        url=n.get("url", ""),
                        timestamp=n.get("showTime", ""),
                    )
                    # 分类
                    self._classify_news(item)
                    items.append(item)
        except Exception as e:
            logger.debug("东方财富新闻抓取失败: %s", e)

        # 缓存
        if items:
            self._cache.set("news", cache_key, value=items, ttl=1800)
        return items

    def _fetch_cls_news(self) -> List[NewsItem]:
        """抓取财联社快讯"""
        items: List[NewsItem] = []
        try:
            resp = self._session.get(
                "https://www.cls.cn/api/sw?app=CailianpressWeb"
                "&os=web&sv=8.4.6",
                params={"type": "telegram"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                news_list = data.get("data", {}).get("roll_data", [])
                for n in news_list[:20]:
                    title = n.get("title", "")
                    brief = n.get("brief", "")
                    item = NewsItem(
                        title=title,
                        summary=brief,
                        source="财联社",
                        url=f"https://www.cls.cn/detail/{n.get('id', '')}",
                        timestamp=str(n.get("ctime", "")),
                    )
                    self._classify_news(item)
                    items.append(item)
        except Exception as e:
            logger.debug("财联社新闻抓取失败: %s", e)

        return items

    def _classify_news(self, item: NewsItem):
        """自动分类新闻 + 判断情绪 + 关联板块"""
        text = item.title + item.summary

        # 1. 分类
        if any(kw in text for kw in self.RISK_KEYWORDS):
            item.category = NewsCategory.RISK
            item.sentiment = SentimentLabel.BEARISH
            item.impact_score = 70
        elif any(kw in text for kw in self.BULLISH_KEYWORDS):
            item.category = NewsCategory.MACRO
            item.sentiment = SentimentLabel.BULLISH
            item.impact_score = 60
        elif any(kw in text for kw in ["政策", "国务院", "发改委", "工信部", "央行", "证监会"]):
            item.category = NewsCategory.MACRO
        elif any(kw in text for kw in ["美国", "中美", "欧洲", "日本", "俄", "乌", "冲突", "制裁"]):
            item.category = NewsCategory.INTERNATIONAL
            item.impact_score = 60

        # 2. 关联板块
        for sector, keywords in self.SECTOR_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                item.related_sectors.append(sector)

        # 3. 情绪判断（如果还没有明确判断）
        if item.sentiment == SentimentLabel.NEUTRAL:
            # 检测负面词
            negative_words = ["下跌", "暴跌", "亏损", "暴雷", "退市", "制裁",
                            "调查", "违规", "减持", "解禁", "预警"]
            if any(w in text for w in negative_words):
                item.sentiment = SentimentLabel.BEARISH
                item.impact_score = 40

    # ============================================================
    #  简报生成
    # ============================================================

    def generate_briefing(self) -> NewsBriefing:
        """生成盘前简报"""
        today = datetime.now().strftime("%Y%m%d")
        briefing = NewsBriefing(date=today)

        # 1. 抓取新闻
        logger.info("开始抓取盘前资讯...")
        all_news = []
        all_news.extend(self._fetch_eastmoney_news())
        all_news.extend(self._fetch_cls_news())

        # 去重（按标题相似度）
        all_news = self._dedup_news(all_news)
        briefing.total_news = len(all_news)

        # 2. 筛选关键新闻（高影响 + 风险事件）
        key_news = [n for n in all_news
                    if n.impact_score >= 50 or n.category == NewsCategory.RISK]
        key_news.sort(key=lambda x: x.impact_score, reverse=True)
        briefing.key_news = key_news[:15]

        # 3. 计算市场情绪
        bullish_count = sum(1 for n in all_news if n.sentiment == SentimentLabel.BULLISH)
        bearish_count = sum(1 for n in all_news if n.sentiment == SentimentLabel.BEARISH)
        total = bullish_count + bearish_count

        if total > 0:
            bullish_ratio = bullish_count / total
            if bullish_ratio >= 0.6:
                briefing.overall_sentiment = SentimentLabel.BULLISH
            elif bullish_ratio <= 0.4:
                briefing.overall_sentiment = SentimentLabel.BEARISH
            else:
                briefing.overall_sentiment = SentimentLabel.NEUTRAL
            briefing.sentiment_score = int(bullish_ratio * 100)

        # 4. 板块分析
        sector_mentions: Dict[str, List[Tuple[SentimentLabel, str]]] = {}
        for n in all_news:
            for sector in n.related_sectors:
                if sector not in sector_mentions:
                    sector_mentions[sector] = []
                sector_mentions[sector].append((n.sentiment, n.title))

        for sector, mentions in sector_mentions.items():
            bullish = sum(1 for s, _ in mentions if s == SentimentLabel.BULLISH)
            bearish = sum(1 for s, _ in mentions if s == SentimentLabel.BEARISH)
            total = bullish + bearish

            if total >= 2:
                if bullish >= bearish * 2:
                    reasons = [t for s, t in mentions if s == SentimentLabel.BULLISH][:2]
                    briefing.focus_sectors.append(SectorAnalysis(
                        name=sector,
                        sentiment=SentimentLabel.BULLISH,
                        reason="; ".join(reasons),
                        confidence=min(90, 50 + bullish * 15),
                        action="关注/加仓",
                    ))
                elif bearish >= bullish * 2:
                    reasons = [t for s, t in mentions if s == SentimentLabel.BEARISH][:2]
                    briefing.avoid_sectors.append(SectorAnalysis(
                        name=sector,
                        sentiment=SentimentLabel.BEARISH,
                        reason="; ".join(reasons),
                        confidence=min(90, 50 + bearish * 15),
                        action="回避/减仓",
                    ))

        # 按置信度排序
        briefing.focus_sectors.sort(key=lambda x: x.confidence, reverse=True)
        briefing.avoid_sectors.sort(key=lambda x: x.confidence, reverse=True)

        # 5. 风险提示
        risk_news = [n for n in all_news if n.category == NewsCategory.RISK]
        for n in risk_news[:5]:
            briefing.risk_alerts.append(f"⚠️ {n.title}")

        # 6. 操作建议
        if briefing.overall_sentiment == SentimentLabel.BULLISH:
            briefing.position_advice = "市场情绪偏多，建议仓位60-80%，积极参与热点板块"
        elif briefing.overall_sentiment == SentimentLabel.BEARISH:
            briefing.position_advice = "市场情绪偏空，建议仓位降至30%以下，防御为主"
        else:
            briefing.position_advice = "市场情绪中性，建议仓位50%，精选标的"

        if briefing.focus_sectors:
            briefing.strategy_notes.append(
                f"重点关注: {'、'.join(s.name for s in briefing.focus_sectors[:5])}"
            )
        if briefing.avoid_sectors:
            briefing.strategy_notes.append(
                f"暂时回避: {'、'.join(s.name for s in briefing.avoid_sectors[:5])}"
            )

        logger.info(
            "盘前简报生成完成: %d条新闻, 情绪=%s(%d), 关注板块=%d, 回避板块=%d",
            briefing.total_news, briefing.overall_sentiment.value,
            briefing.sentiment_score,
            len(briefing.focus_sectors), len(briefing.avoid_sectors),
        )

        return briefing

    def _dedup_news(self, items: List[NewsItem]) -> List[NewsItem]:
        """按标题相似度去重"""
        seen: Set[str] = set()
        result = []
        for item in items:
            # 取标题前20个字符作为特征
            key = item.title[:20]
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    # ============================================================
    #  飞书推送
    # ============================================================

    def send_to_feishu(self, briefing: NewsBriefing) -> bool:
        """发送盘前简报到飞书"""
        if not self._webhook_url:
            logger.warning("飞书 Webhook 未配置")
            return False

        elements: list[dict] = []

        # 情绪概览
        sentiment_emoji = {
            SentimentLabel.BULLISH: "🟢",
            SentimentLabel.BEARISH: "🔴",
            SentimentLabel.NEUTRAL: "🟡",
        }
        emoji = sentiment_emoji.get(briefing.overall_sentiment, "⚪")
        elements.append({
            "tag": "markdown",
            "content": (
                f"{emoji} **盘前市场情绪: {briefing.overall_sentiment.value}** "
                f"({briefing.sentiment_score}/100)\n"
                f"共抓取 {briefing.total_news} 条资讯"
            ),
        })
        elements.append({"tag": "hr"})

        # 重点关注板块
        if briefing.focus_sectors:
            lines = ["🔥 **重点关注板块**\n"]
            for s in briefing.focus_sectors[:6]:
                lines.append(f"• **{s.name}** (置信度{s.confidence}%): {s.reason[:60]}")
            elements.append({"tag": "markdown", "content": "\n".join(lines)})
            elements.append({"tag": "hr"})

        # 规避板块
        if briefing.avoid_sectors:
            lines = ["🚫 **建议规避板块**\n"]
            for s in briefing.avoid_sectors[:6]:
                lines.append(f"• **{s.name}** (置信度{s.confidence}%): {s.reason[:60]}")
            elements.append({"tag": "markdown", "content": "\n".join(lines)})
            elements.append({"tag": "hr"})

        # 关键新闻
        if briefing.key_news:
            lines = ["📰 **关键资讯 (TOP10)**\n"]
            for i, n in enumerate(briefing.key_news[:10], 1):
                sector_str = f" [{', '.join(n.related_sectors)}]" if n.related_sectors else ""
                sentiment_icon = {"bullish": "📈", "bearish": "📉", "neutral": "➖"}.get(
                    n.sentiment.value, "➖"
                )
                lines.append(f"{i}. {sentiment_icon} {n.title[:80]}{sector_str}")
                if n.summary:
                    lines.append(f"   _{n.summary[:60]}_")
            elements.append({"tag": "markdown", "content": "\n".join(lines)})
            elements.append({"tag": "hr"})

        # 风险提示
        if briefing.risk_alerts:
            lines = ["⚠️ **风险提示**\n"]
            for alert in briefing.risk_alerts[:5]:
                lines.append(f"• {alert[:100]}")
            elements.append({"tag": "markdown", "content": "\n".join(lines)})
            elements.append({"tag": "hr"})

        # 操作建议
        elements.append({
            "tag": "markdown",
            "content": (
                f"💡 **操作建议**\n"
                f"• {briefing.position_advice}\n"
                + "\n".join(f"• {n}" for n in briefing.strategy_notes)
            ),
        })
        elements.append({"tag": "hr"})

        elements.append({
            "tag": "markdown",
            "content": "*以上为AI自动抓取分析，不构成投资建议。投资有风险，入市需谨慎。*",
        })

        card = {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📋 盘前资讯简报 | {briefing.date}",
                },
                "template": "blue",
            },
            "elements": elements,
        }

        try:
            payload = {"msg_type": "interactive", "card": card}
            resp = requests.post(
                self._webhook_url, json=payload, timeout=15,
            )
            if resp.status_code == 200 and resp.json().get("code") == 0:
                logger.info("盘前简报飞书推送成功")
                return True
            logger.error("飞书推送失败: %s", resp.text[:200])
            return False
        except Exception as e:
            logger.error("飞书推送异常: %s", e)
            return False


# ============================================================
#  便捷函数
# ============================================================

def generate_and_send_briefing() -> NewsBriefing:
    """生成并发送盘前简报"""
    service = NewsBriefingService()
    briefing = service.generate_briefing()
    service.send_to_feishu(briefing)
    return briefing
