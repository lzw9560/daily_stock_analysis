# -*- coding: utf-8 -*-
"""测试盘前资讯简报模块"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.services.news_briefing import (
    NewsCategory, SentimentLabel, NewsItem, SectorAnalysis,
    NewsBriefing, NewsBriefingService, generate_and_send_briefing,
)


class TestNewsItem:
    """新闻条目测试"""

    def test_create_news_item(self):
        item = NewsItem(
            title="央行降准0.5个百分点",
            summary="释放长期资金约1万亿",
            source="东方财富",
            category=NewsCategory.MACRO,
            sentiment=SentimentLabel.BULLISH,
            impact_score=70,
            related_sectors=["金融/券商"],
        )
        assert item.title == "央行降准0.5个百分点"
        assert item.category == NewsCategory.MACRO
        assert item.sentiment == SentimentLabel.BULLISH
        assert "金融/券商" in item.related_sectors


class TestSectorAnalysis:
    """板块分析测试"""

    def test_create_sector_analysis(self):
        sa = SectorAnalysis(
            name="半导体/芯片",
            sentiment=SentimentLabel.BULLISH,
            reason="国家大基金三期获批",
            confidence=85,
            action="关注/加仓",
        )
        assert sa.name == "半导体/芯片"
        assert sa.confidence == 85
        assert sa.action == "关注/加仓"


class TestNewsBriefing:
    """简报数据结构测试"""

    def test_create_briefing(self):
        briefing = NewsBriefing(date="20260602")
        assert briefing.date == "20260602"
        assert briefing.overall_sentiment == SentimentLabel.NEUTRAL
        assert briefing.sentiment_score == 50
        assert briefing.total_news == 0
        assert len(briefing.key_news) == 0


class TestNewsBriefingService:
    """简报服务测试"""

    @pytest.fixture
    def service(self):
        return NewsBriefingService(webhook_url="")

    def test_classify_macro_news(self, service):
        """宏观政策新闻分类"""
        item = NewsItem(title="央行宣布降准0.5个百分点")
        service._classify_news(item)
        assert item.category == NewsCategory.MACRO
        assert item.sentiment == SentimentLabel.BULLISH

    def test_classify_international_news(self, service):
        """国际局势新闻分类"""
        item = NewsItem(title="中美贸易谈判取得进展")
        service._classify_news(item)
        assert item.category == NewsCategory.INTERNATIONAL

    def test_classify_risk_news(self, service):
        """风险事件新闻分类"""
        item = NewsItem(title="某公司涉嫌财务造假被立案调查")
        service._classify_news(item)
        assert item.category == NewsCategory.RISK
        assert item.sentiment == SentimentLabel.BEARISH

    def test_classify_sector_news(self, service):
        """板块关联"""
        item = NewsItem(title="AI芯片需求暴增，英伟达股价创新高")
        service._classify_news(item)
        assert "半导体/芯片" in item.related_sectors
        assert "人工智能" in item.related_sectors

    def test_classify_bearish_news(self, service):
        """负面情绪检测"""
        item = NewsItem(title="某白马股业绩暴雷，股价暴跌20%")
        service._classify_news(item)
        assert item.sentiment == SentimentLabel.BEARISH

    def test_dedup_news(self, service):
        """新闻去重"""
        items = [
            NewsItem(title="央行降准0.5个百分点释放万亿资金利好A股"),
            NewsItem(title="央行降准0.5个百分点释放万亿资金利好A股专家解读"),
            NewsItem(title="A股三大指数集体收涨"),
        ]
        result = service._dedup_news(items)
        # 前两条标题前20字相同，应去重为1条
        assert len(result) == 2

    def test_sector_keywords_mapping(self, service):
        """板块关键词映射覆盖"""
        # 验证关键板块存在
        sectors = list(service.SECTOR_KEYWORDS.keys())
        assert "半导体/芯片" in sectors
        assert "人工智能" in sectors
        assert "新能源/光伏" in sectors
        assert "军工/航天" in sectors
        assert "低空经济" in sectors

    def test_risk_keywords_present(self, service):
        """风险关键词覆盖"""
        assert len(service.RISK_KEYWORDS) > 10
        assert "制裁" in service.RISK_KEYWORDS
        assert "贸易战" in service.RISK_KEYWORDS
        assert "财务造假" in service.RISK_KEYWORDS

    def test_bullish_keywords_present(self, service):
        """利好关键词覆盖"""
        assert len(service.BULLISH_KEYWORDS) > 5
        assert "降准" in service.BULLISH_KEYWORDS
        assert "降息" in service.BULLISH_KEYWORDS

    @patch.object(NewsBriefingService, '_fetch_eastmoney_news')
    @patch.object(NewsBriefingService, '_fetch_cls_news')
    def test_generate_briefing_with_mock_data(
        self, mock_cls, mock_em, service,
    ):
        """使用mock数据测试简报生成"""
        mock_em.return_value = [
            NewsItem(
                title="央行降准0.5个百分点",
                category=NewsCategory.MACRO,
                sentiment=SentimentLabel.BULLISH,
                impact_score=70,
                related_sectors=["金融/券商"],
            ),
            NewsItem(
                title="AI大模型应用加速落地",
                category=NewsCategory.INDUSTRY,
                sentiment=SentimentLabel.BULLISH,
                impact_score=60,
                related_sectors=["人工智能", "半导体/芯片"],
            ),
        ]
        mock_cls.return_value = [
            NewsItem(
                title="美国对华芯片制裁升级",
                category=NewsCategory.RISK,
                sentiment=SentimentLabel.BEARISH,
                impact_score=80,
                related_sectors=["半导体/芯片"],
            ),
        ]

        briefing = service.generate_briefing()
        assert briefing.total_news >= 2
        assert len(briefing.key_news) >= 1
        # 有2条利好1条利空 → 偏多
        assert briefing.overall_sentiment in (
            SentimentLabel.BULLISH, SentimentLabel.NEUTRAL,
        )

    @patch.object(NewsBriefingService, '_fetch_eastmoney_news')
    @patch.object(NewsBriefingService, '_fetch_cls_news')
    def test_generate_briefing_bearish(self, mock_cls, mock_em, service):
        """偏空市场"""
        mock_em.return_value = [
            NewsItem(
                title="地缘冲突升级，全球股市暴跌",
                category=NewsCategory.RISK,
                sentiment=SentimentLabel.BEARISH,
                impact_score=90,
            ),
            NewsItem(
                title="某地产巨头债务违约",
                category=NewsCategory.RISK,
                sentiment=SentimentLabel.BEARISH,
                impact_score=80,
            ),
        ]
        mock_cls.return_value = []

        briefing = service.generate_briefing()
        assert briefing.overall_sentiment == SentimentLabel.BEARISH
        assert len(briefing.risk_alerts) > 0
        # 偏空时仓位建议保守
        assert "30%" in briefing.position_advice or "防御" in briefing.position_advice

    def test_no_webhook_no_error(self, service):
        """无webhook时不应崩溃"""
        briefing = NewsBriefing(date="20260602")
        result = service.send_to_feishu(briefing)
        assert result is False  # 未配置webhook

    def test_sector_analysis_with_mock(self, service):
        """板块分析逻辑"""
        # 模拟2条半导体利好 vs 0条利空 → 应进入关注板块
        item1 = NewsItem(title="国家大基金三期获批利好半导体板块受益")
        item2 = NewsItem(title="存储芯片价格持续上涨利好行业")
        item3 = NewsItem(title="AI芯片需求旺盛利好半导体")

        service._classify_news(item1)
        service._classify_news(item2)
        service._classify_news(item3)

        for item in [item1, item2, item3]:
            assert "半导体/芯片" in item.related_sectors
            # "利好"关键词 → BULLISH
            assert item.sentiment == SentimentLabel.BULLISH


class TestNewsBriefingEdgeCases:
    """边界情况测试"""

    def test_empty_news(self):
        """无新闻时简报不崩溃"""
        service = NewsBriefingService(webhook_url="")
        with patch.object(service, '_fetch_eastmoney_news', return_value=[]):
            with patch.object(service, '_fetch_cls_news', return_value=[]):
                briefing = service.generate_briefing()
                assert briefing.total_news == 0
                assert briefing.overall_sentiment == SentimentLabel.NEUTRAL

    def test_all_neutral_news(self):
        """全中性新闻"""
        service = NewsBriefingService(webhook_url="")
        items = [
            NewsItem(title=f"新闻{i}") for i in range(5)
        ]
        for item in items:
            service._classify_news(item)

        with patch.object(service, '_fetch_eastmoney_news', return_value=items):
            with patch.object(service, '_fetch_cls_news', return_value=[]):
                briefing = service.generate_briefing()
                # 全是中性 → 情绪分默认50
                assert 45 <= briefing.sentiment_score <= 55

    def test_duplicate_titles_dedup(self):
        """大量重复标题去重"""
        service = NewsBriefingService(webhook_url="")
        # 前20字完全相同的标题应去重（使用长前缀确保>20字符相同）
        prefix = "央行宣布降准释放万亿流动性重大利好政策解读"
        items = [
            NewsItem(title=f"{prefix} 第{i}次详细报道分析")
            for i in range(10)
        ]
        result = service._dedup_news(items)
        # 前20字完全相同 → 去重为1条
        assert len(result) == 1
