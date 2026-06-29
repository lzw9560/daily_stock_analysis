# -*- coding: utf-8 -*-
"""逻辑闭环服务 — 严密的信号→执行→验证→反馈→优化全链路管理.

核心职责：
1. 自动将分析结果/深度分析/打板/综合推荐等所有推荐信号自动同步到 RecommendationRecord
2. 回测结果自动反馈到推荐追踪模块（标记推荐是否正确）
3. 统一ID链路追踪（signal_id 贯穿信号→推荐→回测→反馈）
4. 动态止损/止盈规则管理（基于回测历史自适应调整）
5. 交易纪律前置校验（乖离率、均线排列等硬约束自动拦截）
6. 全局异常降级与自动恢复
7. 策略自省与参数优化建议
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── 交易纪律硬约束 ───────────────────────────────────────────────────────────

DISCIPLINE_RULES = {
    "max_bias_ma5": 5.0,        # 乖离率超过5%不买入
    "min_ma_alignment": 3,      # 至少需要3条均线多头排列
    "max_volume_ratio_buy": 3.0,  # 量比超过3倍不追高
    "min_turnover_rate": 0.5,   # 最低换手率0.5%
    "max_concentration_90": 0.5,  # 90%筹码集中度上限
    "min_profit_ratio": 0.3,    # 获利比例最低30%
}

# 动态止损规则（基于回测历史自适应）
DEFAULT_STOP_LOSS_RULES = {
    "hard_stop_pct": -5.0,       # 硬止损线
    "trailing_stop_pct": -3.0,   # 移动止损
    "time_stop_days": 10,        # 时间止损（交易日）
    "max_drawdown_pct": -8.0,    # 最大回撤容忍
}


class LogicClosureService:
    """逻辑闭环服务 — 信号→执行→验证→反馈→优化 全链路管理.

    单例模式，确保所有模块使用同一实例。
    """

    _instance: Optional["LogicClosureService"] = None

    def __new__(cls) -> "LogicClosureService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._discipline_rules = dict(DISCIPLINE_RULES)
        self._stop_loss_rules = dict(DEFAULT_STOP_LOSS_RULES)

    # ── 核心闭环入口 ────────────────────────────────────────────────────────

    def on_analysis_completed(
        self,
        code: str,
        trade_date: str,
        result: Any,  # AnalysisResult
        query_id: str = "",
        source: str = "analysis",
        trend_result: Optional[Any] = None,
        realtime_quote: Optional[Any] = None,
        chip_data: Optional[Any] = None,
        auto_create_record: bool = True,
    ) -> Dict[str, Any]:
        """分析完成后的闭环钩子.

        1. 交易纪律校验 → 标记信号是否通过
        2. 自动创建 RecommendationRecord（如果通过纪律校验）
        3. 动态止损计算

        Returns:
            {
                "discipline_pass": bool,
                "discipline_violations": [...],
                "recommendation_record_id": int|None,
                "stop_loss_rules": {...},
                "signal_id": str,
            }
        """
        from src.services.recommendation_tracking_service import RecommendationTrackingService

        signal_id = f"{source}:{code}:{trade_date}:{query_id[:8] if query_id else datetime.now().strftime('%H%M%S')}"

        # 1. 交易纪律校验
        discipline_pass, violations = self._check_discipline(
            code=code,
            result=result,
            trend_result=trend_result,
            realtime_quote=realtime_quote,
            chip_data=chip_data,
        )

        # 2. 动态止损计算
        stop_loss_rules = self._compute_dynamic_stop_loss(code=code, result=result)

        # 3. 自动创建推荐记录
        record_id = None
        if auto_create_record and discipline_pass and result and getattr(result, "success", False):
            try:
                # 提取推荐价格
                rec_price = self._extract_recommendation_price(result, realtime_quote)

                # 推断信号方向
                signal = self._infer_signal_direction(result)

                # 提取推荐理由
                reason = self._extract_reason(result)

                tracking_svc = RecommendationTrackingService()
                record = tracking_svc.create_record(
                    code=code,
                    trade_date=trade_date,
                    recommendation_price=rec_price,
                    signal=signal,
                    source=source,
                    source_task_id=signal_id,
                    reason=reason,
                )
                record_id = record.get("id")
                logger.info(
                    "[逻辑闭环] 自动创建推荐追踪记录: code=%s signal=%s price=%.2f id=%s",
                    code, signal, rec_price, record_id,
                )
            except Exception as exc:
                logger.warning("[逻辑闭环] 自动创建推荐记录失败: code=%s error=%s", code, exc)

        return {
            "discipline_pass": discipline_pass,
            "discipline_violations": violations,
            "recommendation_record_id": record_id,
            "stop_loss_rules": stop_loss_rules,
            "signal_id": signal_id,
        }

    def on_deep_analysis_completed(
        self,
        ticker: str,
        trade_date: str,
        signal: str,
        task_id: str,
        report_path: Optional[str] = None,
        auto_create_record: bool = True,
    ) -> Dict[str, Any]:
        """深度分析(TradingAgents)完成后的闭环钩子."""
        from src.services.recommendation_tracking_service import RecommendationTrackingService

        signal_id = f"deep_analysis:{ticker}:{trade_date}:{task_id[:8]}"

        record_id = None
        if auto_create_record and signal:
            try:
                # 从报告路径读取推荐价格
                rec_price = self._extract_price_from_deep_report(report_path) if report_path else 0.0

                # 映射信号方向
                sig_map = {
                    "strong_buy": "buy", "buy": "buy",
                    "strong_sell": "sell", "sell": "sell",
                    "hold": "hold",
                }
                mapped_signal = sig_map.get(signal, signal)

                tracking_svc = RecommendationTrackingService()
                record = tracking_svc.create_record(
                    code=ticker,
                    trade_date=trade_date,
                    recommendation_price=rec_price,
                    signal=mapped_signal,
                    source="deep_analysis",
                    source_task_id=signal_id,
                    reason=f"TradingAgents深度分析: {signal}",
                )
                record_id = record.get("id")
                logger.info("[逻辑闭环] 深度分析自动创建推荐记录: ticker=%s signal=%s id=%s", ticker, signal, record_id)
            except Exception as exc:
                logger.warning("[逻辑闭环] 深度分析创建推荐记录失败: ticker=%s error=%s", ticker, exc)

        return {
            "discipline_pass": True,
            "discipline_violations": [],
            "recommendation_record_id": record_id,
            "signal_id": signal_id,
        }

    def on_backtest_completed(
        self,
        backtest_results: List[Dict[str, Any]],
        auto_feedback: bool = True,
    ) -> Dict[str, Any]:
        """回测完成后的闭环钩子 — 将回测结果反馈到推荐追踪.

        核心逻辑：
        - 通过 analysis_history_id 关联到原始分析记录
        - 如果原始分析已创建 RecommendationRecord，则更新其盈亏数据
        - 自适应调整止损/止盈规则
        """
        if not auto_feedback or not backtest_results:
            return {"feedback_count": 0, "rule_updates": []}

        feedback_count = 0
        rule_updates = []

        try:
            from src.repositories.analysis_repo import AnalysisRepository
            from src.repositories.recommendation_tracking_repo import RecommendationTrackingRepository

            analysis_repo = AnalysisRepository()
            tracking_repo = RecommendationTrackingRepository()

            for bt_result in backtest_results:
                if bt_result.get("eval_status") != "completed":
                    continue

                analysis_id = bt_result.get("analysis_history_id")
                if not analysis_id:
                    continue

                # 通过 analysis_history 找到对应的 query_id，再匹配 recommendation_record
                analysis_record = analysis_repo.get_by_id(analysis_id)
                if not analysis_record:
                    continue

                # 查找匹配的推荐记录（同一code同一天创建的active记录）
                code = bt_result.get("code", "")
                analysis_date = bt_result.get("analysis_date", "")
                records = tracking_repo.find_by_code_and_date(
                    code=code, trade_date=analysis_date, status="active", limit=1
                )
                if not records:
                    continue

                record = records[0]
                simulated_return = bt_result.get("simulated_return_pct")
                outcome = bt_result.get("outcome")

                # 更新记录：标记回测结果
                tracking_repo.update(
                    record["id"],
                    profit_loss_pct=round(simulated_return, 2) if simulated_return else 0,
                    notes=f"回测结果: outcome={outcome}, return={simulated_return}%",
                )
                feedback_count += 1

                # 如果是亏损，检查是否需要收紧止损规则
                if simulated_return and simulated_return < -3:
                    rule_updates.append(f"建议收紧 {code} 止损线: 回测亏损 {simulated_return:.1f}%")

        except Exception as exc:
            logger.warning("[逻辑闭环] 回测反馈失败: %s", exc)

        # 自适应规则调整
        if rule_updates:
            self._adapt_stop_loss_rules(rule_updates)

        return {
            "feedback_count": feedback_count,
            "rule_updates": rule_updates,
        }

    # ── 交易纪律校验 ─────────────────────────────────────────────────────────

    def _check_discipline(
        self,
        code: str,
        result: Any,
        trend_result: Optional[Any] = None,
        realtime_quote: Optional[Any] = None,
        chip_data: Optional[Any] = None,
    ) -> Tuple[bool, List[str]]:
        """检查交易纪律硬约束.

        Returns:
            (是否通过, 违反的规则列表)
        """
        violations = []

        # 1. 乖离率检查
        if trend_result and hasattr(trend_result, "bias_ma5"):
            bias = abs(trend_result.bias_ma5)
            if bias > self._discipline_rules["max_bias_ma5"]:
                violations.append(
                    f"乖离率过高: MA5乖离={bias:.1f}% > {self._discipline_rules['max_bias_ma5']}%（不追高原则）"
                )

        # 2. 均线排列检查
        if trend_result and hasattr(trend_result, "ma_alignment"):
            alignment = trend_result.ma_alignment or ""
            if "多头" not in alignment and "bullish" not in alignment.lower():
                violations.append(f"均线排列不符合: {alignment}（趋势交易原则）")

        # 3. 量比检查（买入信号时检查）
        if realtime_quote and hasattr(realtime_quote, "volume_ratio"):
            vr = realtime_quote.volume_ratio
            if vr and vr > self._discipline_rules["max_volume_ratio_buy"]:
                violations.append(f"量比过高: {vr:.1f} > {self._discipline_rules['max_volume_ratio_buy']}（不追高原则）")

        # 4. 筹码集中度检查
        if chip_data and hasattr(chip_data, "concentration_90"):
            conc = chip_data.concentration_90
            if conc and conc > self._discipline_rules["max_concentration_90"]:
                violations.append(
                    f"筹码分散: 90%集中度={conc:.1%} > {self._discipline_rules['max_concentration_90']:.0%}"
                )

        # 5. 获利比例检查
        if chip_data and hasattr(chip_data, "profit_ratio"):
            pr = chip_data.profit_ratio
            if pr is not None and pr < self._discipline_rules["min_profit_ratio"]:
                violations.append(f"获利比例过低: {pr:.1%} < {self._discipline_rules['min_profit_ratio']:.0%}")

        return len(violations) == 0, violations

    # ── 动态止损计算 ─────────────────────────────────────────────────────────

    def _compute_dynamic_stop_loss(
        self,
        code: str,
        result: Any,
    ) -> Dict[str, float]:
        """基于历史回测数据计算动态止损/止盈位.

        规则：
        - 优先使用最近回测的最大亏损作为参考
        - 如果没有回测数据，使用默认值
        - 动态调整：胜率高的标的可以放宽止损，亏损多的标的收紧止损
        """
        rules = dict(self._stop_loss_rules)

        try:
            from src.services.recommendation_tracking_service import RecommendationTrackingService

            tracking_svc = RecommendationTrackingService()
            stats = tracking_svc.get_stats()

            # 如果该标的已有回测反馈，动态调整
            if stats.get("closed_count", 0) > 0:
                max_loss = abs(stats.get("max_loss_pct", 0))
                if max_loss > 0:
                    # 硬止损设为历史最大亏损的1.2倍
                    rules["hard_stop_pct"] = round(-max_loss * 1.2, 1)
                    # 移动止损设为历史最大亏损的0.8倍
                    rules["trailing_stop_pct"] = round(-max_loss * 0.8, 1)
        except Exception as e:
            logger.debug("回测统计数据获取失败，跳过动态止损调整: %s", e)

        # 从 result 中提取已设置的止损位（如果有）
        if result and hasattr(result, "stop_loss") and result.stop_loss:
            rules["result_stop_loss"] = result.stop_loss
        if result and hasattr(result, "take_profit") and result.take_profit:
            rules["result_take_profit"] = result.take_profit

        return rules

    def _adapt_stop_loss_rules(self, rule_updates: List[str]) -> None:
        """根据回测反馈自适应调整止损规则."""
        for update in rule_updates:
            logger.info("[止损自适应] %s", update)

        # 整体收紧止损线（如果近期回测亏损比例上升）
        try:
            from src.services.recommendation_tracking_service import RecommendationTrackingService

            tracking_svc = RecommendationTrackingService()
            stats = tracking_svc.get_stats()

            win_rate = stats.get("win_rate", 50)
            if win_rate < 40:
                # 胜率偏低，收紧止损
                self._stop_loss_rules["hard_stop_pct"] = max(
                    self._stop_loss_rules["hard_stop_pct"] + 1.0, -8.0
                )
                logger.info("[止损自适应] 胜率%.1f%%偏低，收紧硬止损至%.1f%%", win_rate, self._stop_loss_rules["hard_stop_pct"])
            elif win_rate > 65:
                # 胜率较高，可以略微放宽
                self._stop_loss_rules["hard_stop_pct"] = min(
                    self._stop_loss_rules["hard_stop_pct"] - 0.5, -3.0
                )
        except Exception as exc:
            logger.debug("[止损自适应] 统计查询失败: %s", exc)

    # ── 统一ID链路 ───────────────────────────────────────────────────────────

    def generate_signal_id(
        self,
        source: str,
        code: str,
        trade_date: str,
        suffix: str = "",
    ) -> str:
        """生成统一信号ID，贯穿信号→推荐→回测→反馈全链路."""
        base = f"{source}:{code}:{trade_date}"
        return f"{base}:{suffix}" if suffix else base

    # ── 全局异常降级 ─────────────────────────────────────────────────────────

    def safe_execute(
        self,
        func_name: str,
        func: callable,
        *args,
        fallback_value: Any = None,
        **kwargs,
    ) -> Any:
        """安全执行函数，异常时返回降级值并记录."""
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            logger.warning(
                "[逻辑闭环] %s 执行失败，使用降级值: %s",
                func_name, exc,
            )
            return fallback_value

    # ── 内部工具方法 ─────────────────────────────────────────────────────────

    @staticmethod
    def _extract_recommendation_price(result: Any, realtime_quote: Optional[Any]) -> float:
        """从分析结果中提取推荐价格."""
        # 优先使用实时行情价格
        if realtime_quote and hasattr(realtime_quote, "price") and realtime_quote.price:
            return float(realtime_quote.price)
        # 其次使用结果中的当前价格
        if hasattr(result, "current_price") and result.current_price:
            return float(result.current_price)
        # 最后从上下文中查找
        if hasattr(result, "enhanced_context") and isinstance(result.enhanced_context, dict):
            rt = result.enhanced_context.get("realtime", {})
            if isinstance(rt, dict) and rt.get("price"):
                return float(rt["price"])
        return 0.0

    @staticmethod
    def _infer_signal_direction(result: Any) -> str:
        """从分析结果推断信号方向."""
        advice = getattr(result, "operation_advice", "") or ""
        advice_lower = advice.lower()

        bullish = ["买入", "加仓", "强烈买入", "增持", "建仓", "buy", "strong buy", "add"]
        bearish = ["卖出", "减仓", "强烈卖出", "清仓", "sell", "strong sell", "reduce"]
        hold = ["持有", "观望", "hold", "wait"]

        for kw in bullish:
            if kw in advice_lower or kw in advice:
                return "buy"
        for kw in bearish:
            if kw in advice_lower or kw in advice:
                return "sell"
        for kw in hold:
            if kw in advice_lower or kw in advice:
                return "hold"
        return "hold"

    @staticmethod
    def _extract_reason(result: Any) -> str:
        """提取推荐理由."""
        parts = []
        if hasattr(result, "operation_advice") and result.operation_advice:
            parts.append(f"操作建议: {result.operation_advice}")
        if hasattr(result, "sentiment_score") and result.sentiment_score is not None:
            parts.append(f"评分: {result.sentiment_score}")
        if hasattr(result, "trend_prediction") and result.trend_prediction:
            parts.append(f"趋势: {result.trend_prediction}")
        return "; ".join(parts) if parts else ""

    @staticmethod
    def _extract_price_from_deep_report(report_path: Optional[str]) -> float:
        """从深度分析报告中提取推荐价格."""
        if not report_path:
            return 0.0
        try:
            import re
            from pathlib import Path

            path = Path(report_path)
            if path.exists():
                content = path.read_text(encoding="utf-8")
                # 尝试匹配价格模式
                price_match = re.search(r"(?:当前价格|现价|最新价)[：:]\s*(\d+\.?\d*)", content)
                if price_match:
                    return float(price_match.group(1))
        except Exception as e:
            logger.debug("从报告文件提取价格失败: report_path=%s, error=%s", report_path, e)
        return 0.0
