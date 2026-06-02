"""
打板助手服务主模块
基于 SEAL_PLATE_ARCHITECTURE.md v2.1 §2.4

编排流程: 数据获取 → 评分 → 情绪分析 → 龙头识别 → 报告生成 → 通知推送
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Optional

from .models import PlateType, SealPlateReport, SealPlateStock, SealStrength
from .seal_plate_analyzer import SealPlateAnalyzer, SentimentAnalyzer
from .seal_plate_fetcher import SealPlateFetcher
from .seal_plate_notifier import SealPlateNotifier

logger = logging.getLogger(__name__)


class SealPlateService:
    """打板助手服务 — 架构文档 §2.4"""

    def __init__(self, config: Optional[dict] = None):
        """
        Args:
            config:
                - webhook_url: 飞书 Webhook URL
                - feishu_enabled: 是否启用飞书通知
                - min_score: 最低评分阈值（默认 60）
                - output_dir: 报告输出目录
        """
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)

        # 组件初始化
        self.fetcher = SealPlateFetcher()
        self.analyzer = SealPlateAnalyzer(
            min_score=self.config.get("min_score", 60)
        )
        self.sentiment = SentimentAnalyzer()

        # 飞书通知
        webhook_url = self.config.get("webhook_url") or os.getenv("FEISHU_WEBHOOK_URL")
        feishu_enabled = self.config.get("feishu_enabled", True)
        self.notifier = (
            SealPlateNotifier(webhook_url=webhook_url) if feishu_enabled else None
        )

        self.min_score = self.config.get("min_score", 60)
        self.output_dir = self.config.get("output_dir", "reports/seal_plate")

    # ========================
    #  主入口 — 架构文档 §2.4
    # ========================

    def run(
        self, date: Optional[str] = None, force: bool = False
    ) -> Optional[SealPlateReport]:
        """
        运行打板分析全流程

        Args:
            date: 日期 YYYYMMDD，默认自动选择有效日期
            force: 强制运行

        Returns:
            分析报告，无数据返回 None
        """
        from .date_utils import get_effective_date
        date = get_effective_date(date)
        self.logger.info("=== 打板分析启动: %s ===", date)

        # 1. 数据获取
        self.logger.info("[1/5] 获取涨停板数据...")
        stocks = self.fetcher.fetch_all(date)
        if not stocks:
            self.logger.warning("今日无涨停板数据")
            return None
        self.logger.info("[1/5] 获取到 %d 只涨停股", len(stocks))

        # 2. 评分分析
        self.logger.info("[2/5] 分析涨停板...")
        report = self.analyzer.analyze(stocks, date)

        # 3. 情绪周期分析 — 架构文档 §4（含同花顺热点增强）
        self.logger.info("[3/5] 计算情绪周期...")
        hotspot_data = self._fetch_hotspot_data()
        self._compute_sentiment(report, stocks, hotspot_data)

        # 4. 过滤 + 保存报告
        self.logger.info("[4/5] 过滤并保存报告...")
        report.strong_stocks = [
            s for s in report.strong_stocks if s.score >= self.min_score
        ]
        self._save_report(report)

        # 5. 飞书通知
        if self.notifier:
            self.logger.info("[5/5] 发送飞书通知...")
            self.notifier.send_report(report)

        self.logger.info(
            "=== 打板分析完成: %d只强势, 情绪:%s(%.0f) ===",
            len(report.strong_stocks),
            report.sentiment_phase,
            report.sentiment_index,
        )
        return report

    # ========================
    #  情绪计算
    # ========================

    def _compute_sentiment(
        self, report: SealPlateReport, stocks: list[SealPlateStock],
        hotspot_data: Optional[dict] = None,
    ) -> None:
        """计算情绪指数并填入报告 — 架构文档 §4（含同花顺热点增强）"""

        n = len(stocks)

        market_data = {
            "limit_up_count": n,
            "limit_down_count": report.bomb_count,
            "max_consecutive": report.max_consecutive,
            "bomb_rate": report.bomb_count / n if n > 0 else 0,
            "avg_premium": 2.0,
            "advance_rate": (
                len([s for s in stocks if s.consecutive_days > 1]) / n
                if n > 0 else 0
            ),
            "volume_change": 0.0,
        }

        index, phase, indicators = self.sentiment.calculate_sentiment_index(
            market_data
        )

        # 同花顺热点增强
        if hotspot_data:
            enhanced = self.sentiment.enhance_with_hotspot(
                {"sentiment_index": index, "sentiment_phase": phase, "indicators": indicators},
                hotspot_data,
            )
            report.sentiment_index = float(enhanced.get("sentiment_index", index))
            report.sentiment_phase = enhanced.get("sentiment_phase", phase)
            # 附加热点信息到报告
            report._hotspot_data = {
                "market_heat_score": enhanced.get("market_heat_score", 50),
                "hot_concepts_count": enhanced.get("hot_concepts_count", 0),
                "top_hot_concepts": enhanced.get("top_hot_concepts", []),
                "sentiment_signal": enhanced.get("sentiment_signal", "neutral"),
                "fund_inflow_intensity": enhanced.get("fund_inflow_intensity", 0),
            }
        else:
            report.sentiment_index = float(index)
            report.sentiment_phase = phase

        self.logger.debug(
            "情绪指数: %.0f → %s, 指标: %s",
            report.sentiment_index, report.sentiment_phase, indicators,
        )

    def _fetch_hotspot_data(self) -> Optional[dict]:
        """尝试从同花顺获取热点数据"""
        try:
            from data_provider.ths_hotspot_fetcher import create_ths_hotspot_fetcher
            ths = create_ths_hotspot_fetcher()
            return ths.get_market_hot_analysis()
        except Exception as e:
            self.logger.debug("同花顺热点获取失败: %s", e)
            return None

    # ========================
    #  报告保存
    # ========================

    def _save_report(self, report: SealPlateReport) -> None:
        """保存报告为 Markdown + JSON — 架构文档 §7.1"""
        os.makedirs(self.output_dir, exist_ok=True)

        # Markdown
        md_path = os.path.join(self.output_dir, f"seal_plate_{report.date}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report.to_markdown())
        self.logger.info("Markdown 报告已保存: %s", md_path)

        # JSON
        json_path = os.path.join(self.output_dir, f"seal_plate_{report.date}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        self.logger.info("JSON 报告已保存: %s", json_path)


# ========================
#  CLI 入口 — 架构文档 §8
# ========================

def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="打板助手 - Seal Plate Assistant")
    parser.add_argument("--date", type=str, default=None, help="日期 YYYYMMDD")
    parser.add_argument("--force", action="store_true", help="强制执行")
    parser.add_argument("--min-score", type=int, default=60, help="最低评分阈值")
    parser.add_argument("--no-notify", action="store_true", help="禁用飞书通知")
    parser.add_argument("--debug", action="store_true", help="调试模式")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    config = {
        "min_score": args.min_score,
        "feishu_enabled": not args.no_notify,
    }

    service = SealPlateService(config)
    report = service.run(date=args.date, force=args.force)

    if report:
        print(f"\n{report.to_markdown()}")
    else:
        print("分析失败或无数据")


if __name__ == "__main__":
    main()
