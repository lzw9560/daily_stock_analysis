"""
打板助手定时任务调度

定时任务：
1. 早盘推荐任务：每个交易日 8:50 执行
   - 获取昨日打板数据
   - 生成建仓推荐
   - 资金流向分析
   - 发送飞书通知
2. 收盘复盘任务：每个交易日 15:30 执行
   - 自动结算前日推荐
   - LLM复盘分析
   - 生成次日持仓建议
   - 发送飞书通知
"""
from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Optional

from .seal_plate_service import SealPlateService
from .recommender import RecommendationEngine
from .recommendation_log import RecommendationLogStore
from .capital_flow_analyzer import CapitalFlowAnalyzer
from .daily_feishu_notifier import DailyFeishuNotifier
from .review_scheduler import ReviewScheduler
from .review_log import ReviewLogStore
from .llm_reviewer import LLMReviewer
from .win_rate_tracker import WinRateTracker

logger = logging.getLogger(__name__)

# 新增模块（延迟导入，避免循环依赖）
_news_briefing_service = None
_bidding_monitor = None


def _get_news_briefing():
    global _news_briefing_service
    if _news_briefing_service is None:
        from src.services.news_briefing import NewsBriefingService
        _news_briefing_service = NewsBriefingService()
    return _news_briefing_service


def _get_bidding_monitor():
    global _bidding_monitor
    if _bidding_monitor is None:
        from src.services.bidding_monitor import PreMarketBiddingMonitor
        _bidding_monitor = PreMarketBiddingMonitor()
    return _bidding_monitor


class SealPlateDailyTasks:
    """打板助手每日定时任务管理器"""

    def __init__(self):
        self.feishu = DailyFeishuNotifier()
        self.recommendation_engine = RecommendationEngine()
        self.capital_analyzer = CapitalFlowAnalyzer()
        self.review_scheduler = ReviewScheduler()
        self.log_store = RecommendationLogStore()
        self.review_store = ReviewLogStore()

    # ========================
    #  早盘推荐任务 (8:50)
    # ========================

    def run_morning_recommendation(self, target_date: Optional[str] = None) -> dict:
        """
        早盘推荐任务

        流程：
        1. 获取最新打板数据
        2. 资金流向分析
        3. 生成建仓推荐（融合资金流向信息）
        4. 发送飞书通知
        """
        date = target_date or datetime.now().strftime("%Y%m%d")
        logger.info("=" * 50)
        logger.info("开始执行早盘推荐任务: %s", date)
        logger.info("=" * 50)

        result = {
            "status": "ok",
            "date": date,
            "recommendations_count": 0,
            "feishu_sent": False,
            "message": "",
        }

        try:
            # 1. 获取打板数据
            service = SealPlateService(config={
                'min_score': 60,
                'feishu_enabled': False,  # 不在此处发送，统一由本模块发送
            })
            report = service.run(date=date, force=True)

            if not report:
                result["status"] = "no_data"
                result["message"] = "无涨停板数据"
                logger.warning("早盘推荐: 无涨停板数据")
                return result

            # 2. 资金流向分析
            fund_analysis = self.capital_analyzer.analyze(
                hot_sectors=report.sector_hot,
                strong_stocks=list(report.strong_stocks) + list(report.watch_stocks),
                date=date,
            )
            logger.info(
                "资金流向分析完成: 情绪=%s, 热度=%d",
                fund_analysis.fund_sentiment,
                fund_analysis.fund_heat_score,
            )

            # 3. 生成建仓推荐（融合资金流向）
            recommendations = self.recommendation_engine.generate_recommendations(
                report, date_label=date,
                fund_analysis={
                    "hot_sectors_inflow": fund_analysis.hot_sectors_inflow,
                    "hot_sectors_outflow": fund_analysis.hot_sectors_outflow,
                },
            )

            if recommendations.recommendations:
                # 融合资金流向信息到推荐结果中
                self._enrich_recommendations_with_fund_flow(
                    recommendations, fund_analysis
                )
                # 保存推荐日志
                self.recommendation_engine.save_recommendations(recommendations)

            result["recommendations_count"] = len(recommendations.recommendations)

            # 4. 发送飞书通知
            if self.feishu.enabled:
                sent = self.feishu.send_morning_recommendation(
                    report, recommendations, fund_analysis
                )
                result["feishu_sent"] = sent
                if sent:
                    result["message"] = (
                        f"早盘推荐已发送: {len(recommendations.recommendations)}只标的, "
                        f"资金情绪:{fund_analysis.fund_sentiment}"
                    )
                else:
                    result["message"] = "飞书通知发送失败"
            else:
                result["message"] = (
                    f"推荐生成完成: {len(recommendations.recommendations)}只标的(飞书通知未启用)"
                )

            logger.info("早盘推荐任务完成: %s", result["message"])

        except Exception as e:
            logger.exception("早盘推荐任务失败: %s", e)
            result["status"] = "error"
            result["message"] = f"任务失败: {str(e)}"

        return result

    def _enrich_recommendations_with_fund_flow(
        self, recommendations, fund_analysis
    ) -> None:
        """将资金流向信息融入推荐结果"""
        # 将资金流向中的风险提示合并到策略建议中
        if fund_analysis.risk_alerts:
            for alert in fund_analysis.risk_alerts[:3]:
                if alert not in recommendations.strategy_notes:
                    recommendations.strategy_notes.append(alert)

        # 添加买卖点建议到策略说明
        if fund_analysis.buy_suggestions:
            recommendations.strategy_notes.append(
                f"💡 资金面支持{len(fund_analysis.buy_suggestions)}只标的的买入建议"
            )

    # ========================
    #  收盘复盘任务 (15:30)
    # ========================

    def run_evening_review(self, target_date: Optional[str] = None) -> dict:
        """
        收盘复盘任务

        流程：
        1. 自动结算前日推荐
        2. LLM复盘分析
        3. 生成次日持仓建议
        4. 发送飞书通知
        """
        date = target_date or datetime.now().strftime("%Y%m%d")
        logger.info("=" * 50)
        logger.info("开始执行收盘复盘任务: %s", date)
        logger.info("=" * 50)

        result = {
            "status": "ok",
            "date": date,
            "auto_settled": 0,
            "llm_analysis": False,
            "feishu_sent": False,
            "message": "",
        }

        try:
            # 1. 自动结算
            review_result = self.review_scheduler.run_daily_review(target_date=date)
            result["auto_settled"] = review_result.get("auto_settled", 0)
            result["llm_analysis"] = review_result.get("llm_analysis", False)

            # 2. 获取最新复盘数据
            review_data = self.review_store.load(date)
            if not review_data:
                all_reviews = self.review_store.load_all(limit=1)
                review_data = all_reviews[0] if all_reviews else {}

            # 3. 生成次日持仓建议
            next_day_advice = self._generate_next_day_advice(date, review_data)

            # 4. 发送飞书通知（复盘）
            if self.feishu.enabled and review_data:
                sent = self.feishu.send_evening_review(review_data, next_day_advice)
                result["feishu_sent"] = sent

            # 5. 战法+建仓合并分析，推送到飞书
            combined_sent = False
            try:
                from .combined_analyzer import CombinedAnalyzer
                from .recommender import DailyRecommendationResult, PositionRecommendation
                from .models import SealPlateStock
                from .recommendation_log import RecommendationLogStore
                from .win_rate_tracker import WinRateStats

                rec_log = RecommendationLogStore().load(date)
                if rec_log and rec_log.recommendations:
                    rec_result = DailyRecommendationResult(
                        date=rec_log.date,
                        label=date,
                        sentiment_index=rec_log.sentiment_index,
                        sentiment_phase=rec_log.sentiment_phase,
                        total_limit_up=rec_log.total_limit_up,
                        recommendations=[
                            PositionRecommendation(
                                stock=SealPlateStock(
                                    code=r.code,
                                    name=r.name,
                                    close_price=0.0,
                                    change_pct=r.change_pct or 0.0,
                                    limit_up_price=0.0,
                                    turnover_rate=0.0,
                                ),
                                score=r.score,
                                rank=i + 1,
                                confidence="中",
                                reasons=r.reasons,
                                risk_warnings=[],
                                suggested_position_pct=0.0,
                            )
                            for i, r in enumerate(rec_log.recommendations)
                        ],
                        win_rate_stats=None,
                    )
                    analyzer = CombinedAnalyzer()
                    combined = analyzer.analyze(rec_result)
                    if self.feishu.enabled:
                        combined_sent = self.feishu.send_combined_analysis(combined)
                        if combined_sent:
                            result.setdefault("combined_sent", True)
                else:
                    logger.info("无推荐标的，跳过合并分析飞书推送")
            except Exception as exc:
                logger.warning("合并分析推送失败（已跳过）: %s", exc)

            # 构建消息
            parts = []
            if result["auto_settled"] > 0:
                parts.append(f"自动结算{result['auto_settled']}笔")
            if result["llm_analysis"]:
                parts.append("LLM分析已完成")
            if result["feishu_sent"]:
                parts.append("飞书通知已发送")
            if combined_sent:
                parts.append("合并分析已推送")
            result["message"] = "、".join(parts) if parts else "复盘完成"

            logger.info("收盘复盘任务完成: %s", result["message"])

        except Exception as e:
            logger.exception("收盘复盘任务失败: %s", e)
            result["status"] = "error"
            result["message"] = f"任务失败: {str(e)}"

        return result

    def _generate_next_day_advice(
        self, date: str, review_data: dict
    ) -> list[str]:
        """生成次日持仓建议"""
        advice = []

        # 1. 基于LLM分析的建议
        summary = review_data.get("summary", "")
        if summary:
            advice.append(f"📌 复盘结论: {summary}")

        # 2. 高动量板块建议
        high_sectors = review_data.get("high_momentum_sectors", [])
        if high_sectors:
            advice.append(f"🔥 重点关注板块: {'、'.join(high_sectors[:3])}")

        # 3. 回避板块
        risk_sectors = review_data.get("risk_sectors", [])
        if risk_sectors:
            advice.append(f"🚫 暂时回避: {'、'.join(risk_sectors[:3])}")

        # 4. 仓位建议
        position_advice = review_data.get("position_advice", "")
        if position_advice:
            advice.append(f"💰 {position_advice}")

        # 5. 成功模式参考
        success_patterns = review_data.get("success_patterns", [])
        if success_patterns:
            advice.append(f"✅ 成功经验: {success_patterns[0][:60]}")

        # 6. 失败模式规避
        failure_patterns = review_data.get("failure_patterns", [])
        if failure_patterns:
            advice.append(f"❌ 避免: {failure_patterns[0][:60]}")

        # 7. 评分门槛
        min_score = review_data.get("recommended_min_score", 65)
        confidence = review_data.get("recommended_confidence_threshold", "中")
        advice.append(f"🎯 次日选股标准: 评分≥{min_score}, 置信度≥{confidence}")

        # 8. 策略调整
        adjustments = review_data.get("strategy_adjustments", [])
        if adjustments:
            advice.append(f"🔧 策略调整: {adjustments[0][:60]}")

        return advice

    # ========================
    #  盘前资讯简报任务 (8:30)
    # ========================

    def run_news_briefing(self) -> dict:
        """
        盘前资讯简报任务

        流程:
        1. 抓取国内外宏观新闻
        2. 分析消息面情绪
        3. 生成重点关注/规避板块
        4. 发送飞书推送
        """
        logger.info("=" * 50)
        logger.info("开始执行盘前资讯简报任务...")
        logger.info("=" * 50)

        result = {
            "status": "ok",
            "news_count": 0,
            "sentiment": "",
            "feishu_sent": False,
            "message": "",
        }

        try:
            service = _get_news_briefing()
            briefing = service.generate_briefing()

            result["news_count"] = briefing.total_news
            result["sentiment"] = briefing.overall_sentiment.value
            result["focus_sectors"] = [s.name for s in briefing.focus_sectors]
            result["avoid_sectors"] = [s.name for s in briefing.avoid_sectors]

            sent = service.send_to_feishu(briefing)
            result["feishu_sent"] = sent

            if sent:
                result["message"] = (
                    f"盘前简报已发送: {briefing.total_news}条资讯, "
                    f"情绪={briefing.overall_sentiment.value}({briefing.sentiment_score}), "
                    f"关注板块={len(briefing.focus_sectors)}, "
                    f"规避板块={len(briefing.avoid_sectors)}"
                )
            else:
                result["message"] = "简报已生成但飞书推送未启用"

            logger.info("盘前资讯简报完成: %s", result["message"])

        except Exception as e:
            logger.exception("盘前资讯简报失败: %s", e)
            result["status"] = "error"
            result["message"] = f"任务失败: {str(e)}"

        return result

    # ========================
    #  竞价监控启动任务 (9:14)
    # ========================

    def start_bidding_monitor(self) -> dict:
        """启动竞价监控（9:14启动，9:15开始收集数据）"""
        logger.info("启动早盘竞价监控...")

        result = {"status": "ok", "message": ""}

        try:
            monitor = _get_bidding_monitor()
            # 从 watchlist.json 加载标的
            from pathlib import Path
            watchlist_path = Path(__file__).parent.parent.parent / "watchlist.json"
            if watchlist_path.exists():
                import json
                with open(watchlist_path) as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    monitor.set_watchlist(data)

            monitor.start_monitoring()
            result["message"] = f"竞价监控已启动: {len(monitor._watchlist)}只标的"
            logger.info(result["message"])
        except Exception as e:
            logger.exception("启动竞价监控失败: %s", e)
            result["status"] = "error"
            result["message"] = str(e)

        return result

    # ========================
    #  综合任务（完整流程）
    # ========================

    def run_full_daily_cycle(self, target_date: Optional[str] = None) -> dict:
        """
        执行完整的每日循环

        时间线:
        - 8:30  盘前资讯简报
        - 8:50  早盘推荐
        - 9:14  启动竞价监控
        - 15:30 收盘复盘
        """
        date = target_date or datetime.now().strftime("%Y%m%d")
        now = datetime.now()
        current_time = now.time()

        results = {
            "date": date,
            "news_briefing": None,
            "morning": None,
            "bidding": None,
            "evening": None,
        }

        # 8:30前 → 盘前简报
        if current_time >= time(8, 0) and current_time < time(9, 15):
            logger.info("执行盘前资讯简报")
            results["news_briefing"] = self.run_news_briefing()

        # 8:50 → 早盘推荐
        if time(8, 0) <= current_time < time(15, 0):
            logger.info("执行早盘推荐流程")
            results["morning"] = self.run_morning_recommendation(target_date=date)

        # 9:14 → 启动竞价监控
        if time(9, 14) <= current_time < time(9, 30):
            logger.info("启动竞价监控")
            results["bidding"] = self.start_bidding_monitor()

        # 15:30 → 收盘复盘
        if current_time >= time(15, 0):
            logger.info("执行收盘复盘流程")
            results["evening"] = self.run_evening_review(target_date=date)

        return results


# ========================
#  便捷函数
# ========================

def run_morning_task() -> dict:
    """便捷函数：执行早盘推荐任务（可注册为调度器任务）"""
    tasks = SealPlateDailyTasks()
    return tasks.run_morning_recommendation()


def run_evening_task() -> dict:
    """便捷函数：执行收盘复盘任务（可注册为调度器任务）"""
    tasks = SealPlateDailyTasks()
    return tasks.run_evening_review()


def run_news_briefing_task() -> dict:
    """便捷函数：执行盘前资讯简报"""
    tasks = SealPlateDailyTasks()
    return tasks.run_news_briefing()


def run_bidding_monitor_task() -> dict:
    """便捷函数：启动竞价监控"""
    tasks = SealPlateDailyTasks()
    return tasks.start_bidding_monitor()


def run_full_daily_cycle() -> dict:
    """便捷函数：执行完整每日循环"""
    tasks = SealPlateDailyTasks()
    return tasks.run_full_daily_cycle()
