"""
自动复盘调度器

在每日收盘后自动执行：
1. 检查前一日推荐是否已结算（尝试从次日行情数据自动填充收益率）
2. 触发 LLM 复盘分析
3. 保存复盘报告
4. 输出策略优化建议
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from .recommendation_log import RecommendationLogStore
from .llm_reviewer import LLMReviewer
from .review_log import ReviewLogStore as ReviewLogStoreNew
from .win_rate_tracker import WinRateTracker

logger = logging.getLogger(__name__)


class ReviewScheduler:
    """自动复盘调度器

    职责：
    - 收盘后自动执行复盘流程
    - 尝试从行情数据自动填充推荐结果
    - 触发 LLM 分析生成策略建议
    """

    def __init__(self):
        self.log_store = RecommendationLogStore()
        self.review_store = ReviewLogStoreNew()
        self.win_tracker = WinRateTracker(self.log_store)
        self.reviewer = LLMReviewer(self.log_store)

    def run_daily_review(self, target_date: Optional[str] = None) -> dict:
        """
        执行每日复盘流程

        Returns:
            {"status": "ok/partial/noop", "message": "...", "auto_settled": count, "llm_analysis": bool}
        """
        target = target_date or datetime.now().strftime("%Y%m%d")
        result = {
            "status": "ok",
            "date": target,
            "auto_settled": 0,
            "llm_analysis": False,
            "message": "",
        }

        # ---------- 步骤1: 自动结算前一日推荐 ----------
        auto_settled = self._auto_settle_pending(target)
        result["auto_settled"] = auto_settled

        # ---------- 步骤2: LLM 复盘分析 ----------
        # 仅当有足够的已结算数据时才进行分析
        logs = self.log_store.load_all(limit=30)
        settled = sum(
            1 for log in logs
            for r in log.recommendations if r.outcome is not None
        )
        if settled >= 3:
            try:
                insight = self.reviewer.analyze_and_save(target_date=target)
                if insight:
                    result["llm_analysis"] = True
                    result["message"] = f"复盘完成，自动结算{auto_settled}笔，LLM分析已生成。建议: {insight.summary}"
                else:
                    result["status"] = "partial"
                    result["message"] = f"自动结算{auto_settled}笔，但LLM分析未生成"
            except Exception as e:
                logger.exception("LLM复盘分析失败: %s", e)
                result["status"] = "partial"
                result["message"] = f"自动结算{auto_settled}笔，LLM分析失败: {e}"
        else:
            result["status"] = "noop"
            result["message"] = f"已结算数据不足（{settled}笔），暂不触发LLM分析。已自动结算{auto_settled}笔"

        logger.info(
            "每日复盘: date=%s, status=%s, auto_settled=%d, llm=%s",
            target, result["status"], auto_settled, result["llm_analysis"],
        )
        return result

    def _auto_settle_pending(self, target_date: str) -> int:
        """
        自动结算前置交易的推荐结果

        读取最近待结算的推荐，尝试从行情数据获取次日涨跌幅，
        自动计算 outcome 和 actual_return_pct。

        Returns: 成功自动结算的笔数
        """
        auto_settled = 0
        logs = self.log_store.load_all(limit=5)

        for log in logs:
            # 只处理今天之前的数据
            if log.date >= target_date:
                continue

            for r in log.recommendations:
                if r.outcome is not None:
                    continue  # 已结算

                # 尝试获取次日开盘价/收盘价用于自动结算
                next_day_change = self._fetch_next_day_change(log.date, r.code)
                if next_day_change is not None:
                    r.outcome = "成功" if next_day_change > 0 else "失败"
                    r.actual_return_pct = round(next_day_change, 2)
                    r.won = next_day_change > 0
                    r.review_note = f"自动结算(次日涨跌幅 {next_day_change:+.2f}%)"
                    auto_settled += 1
                    logger.info(
                        "自动结算: %s %s(%s) → %s, 次日涨跌幅 %+.2f%%",
                        log.date, r.name, r.code, r.outcome, next_day_change,
                    )

            # 保存更新
            if any(
                r.outcome is not None and r.review_note and r.review_note.startswith("自动结算")
                for r in log.recommendations
            ):
                self.log_store.save(log)

        return auto_settled

    def _fetch_next_day_change(self, date_str: str, code: str) -> Optional[float]:
        """
        获取某股票某日之后的次日涨跌幅

        优先使用 AKShare → 降级到腾讯财经
        """
        # 计算次日日期
        from datetime import datetime as dt, timedelta
        date_obj = dt.strptime(date_str, "%Y%m%d")
        next_day = date_obj + timedelta(days=1)

        # 跳过周末
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        next_day_str = next_day.strftime("%Y%m%d")

        # 如果次日还没到，无法结算
        if next_day > dt.now():
            return None

        # 方法1: 通过 AKShare 获取
        try:
            import akshare as ak
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=date_str,
                end_date=next_day_str,
                adjust="",
            )
            if df is not None and len(df) >= 2:
                # 计算昨日收盘到今日收盘的涨跌幅
                prev_close = df.iloc[-2]["收盘"]
                cur_close = df.iloc[-1]["收盘"]
                return (cur_close - prev_close) / prev_close * 100
        except Exception as e:
            logger.debug("AKShare获取次日行情失败 %s: %s", code, e)

        # 方法2: 通过腾讯财经获取
        try:
            import requests
            url = f"https://qt.gtimg.cn/q=sh{code}" if code.startswith(("6", "0")) else \
                  f"https://qt.gtimg.cn/q=sz{code}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                text = resp.text
                parts = text.split("~")
                if len(parts) > 32:
                    prev_close = float(parts[4]) if parts[4] else 0
                    cur_price = float(parts[3]) if parts[3] else 0
                    if prev_close > 0:
                        return (cur_price - prev_close) / prev_close * 100
        except Exception as e:
            logger.debug("腾讯财经获取次日行情失败 %s: %s", code, e)

        return None


# ============================================================
# 便捷函数：可直接作为调度器的 daily task
# ============================================================

def run_auto_review() -> dict:
    """便捷函数：执行每日复盘（可注册为调度器任务）"""
    logger.info("=" * 50)
    logger.info("开始执行每日自动复盘...")
    logger.info("=" * 50)

    scheduler = ReviewScheduler()
    result = scheduler.run_daily_review()

    logger.info("每日复盘结果: %s", result.get("message", ""))
    logger.info("=" * 50)

    return result
