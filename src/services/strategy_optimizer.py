# -*- coding: utf-8 -*-
"""策略优化器 — 基于历史回测与推荐追踪数据的自适应策略调优.

核心能力：
1. 来源权重动态调整：根据各来源的历史胜率，动态计算推荐权重
2. 止损/止盈参数自适应：基于回测数据自动优化止损线和止盈目标
3. 信号过滤规则：识别低质量信号特征，建立自动过滤规则
4. 策略自省报告：整合回测+推荐追踪数据，生成优化建议
5. 执行纪律检查：每次交易前检查是否违反纪律规则
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── 默认参数 ─────────────────────────────────────────────────────────────────

DEFAULT_PARAMS = {
    "min_win_rate": 45.0,         # 最低胜率阈值
    "min_profit_factor": 1.2,     # 最低盈亏比
    "max_consecutive_losses": 3,   # 最大连续亏损次数
    "position_sizing_base": 0.2,  # 基础仓位比例
    "source_weight_default": 1.0,  # 默认来源权重
    "stop_loss_ats": -5.0,        # ATR止损倍数
    "take_profit_rr": 2.0,        # 盈亏比目标
}


class StrategyOptimizer:
    """策略优化器 — 自适应参数调优与信号过滤.

    单例模式。
    """

    _instance: Optional["StrategyOptimizer"] = None

    def __new__(cls) -> "StrategyOptimizer":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._params = dict(DEFAULT_PARAMS)

    # ── 来源权重计算 ─────────────────────────────────────────────────────────

    def compute_source_weights(self) -> Dict[str, float]:
        """基于各推荐来源的历史胜率计算动态权重.

        权重计算规则：
        - 胜率 >= 60%: 权重 1.5
        - 胜率 50-60%: 权重 1.0
        - 胜率 40-50%: 权重 0.7
        - 胜率 < 40%: 权重 0.3
        - 无数据: 权重 1.0
        - 样本量 < 5: 权重打8折（小样本惩罚）
        """
        try:
            from src.services.recommendation_tracking_service import RecommendationTrackingService

            tracking_svc = RecommendationTrackingService()
            stats = tracking_svc.get_stats()
            by_source = stats.get("by_source", {})

            weights = {}
            for source, data in by_source.items():
                win_rate = data.get("win_rate", 0)
                total = data.get("total", 0)

                if win_rate >= 60:
                    weight = 1.5
                elif win_rate >= 50:
                    weight = 1.0
                elif win_rate >= 40:
                    weight = 0.7
                else:
                    weight = 0.3

                # 小样本惩罚
                if total < 5:
                    weight *= 0.8

                weights[source] = round(weight, 2)

            # 确保所有已知来源都有权重
            for source in ["analysis", "deep_analysis", "seal_plate", "comprehensive", "manual"]:
                if source not in weights:
                    weights[source] = 1.0

            logger.info("[策略优化] 来源权重: %s", weights)
            return weights
        except Exception as exc:
            logger.warning("[策略优化] 来源权重计算失败，使用默认权重: %s", exc)
            return {"analysis": 1.0, "deep_analysis": 1.0, "seal_plate": 1.0, "comprehensive": 1.0, "manual": 1.0}

    # ── 止损/止盈参数优化 ────────────────────────────────────────────────────

    def optimize_stop_params(self) -> Dict[str, float]:
        """基于回测历史优化止损/止盈参数.

        规则：
        1. 如果平均盈利 / 平均亏损 > 2.5，可略微放宽止损
        2. 如果最大亏损超过平均亏损的2倍，收紧硬止损
        3. 如果止盈触发率 < 30%，降低止盈目标
        4. 如果止损触发率 > 50%，收紧止损线
        """
        try:
            from src.services.backtest_service import BacktestService
            from src.services.recommendation_tracking_service import RecommendationTrackingService

            backtest_svc = BacktestService()
            tracking_svc = RecommendationTrackingService()

            # 获取回测汇总
            bt_summary = backtest_svc.get_global_summary()
            rec_stats = tracking_svc.get_stats()

            params = {
                "hard_stop_pct": -5.0,
                "trailing_stop_pct": -3.0,
                "take_profit_target_pct": 10.0,
                "time_stop_days": 10,
            }

            if bt_summary:
                sl_trigger_rate = bt_summary.get("stop_loss_trigger_rate", 0) or 0
                tp_trigger_rate = bt_summary.get("take_profit_trigger_rate", 0) or 0

                # 止损触发率过高 → 收紧止损
                if sl_trigger_rate > 50:
                    params["hard_stop_pct"] = -3.0
                    params["trailing_stop_pct"] = -2.0
                    logger.info("[策略优化] 止损触发率%.1f%%过高，收紧止损至%.1f%%", sl_trigger_rate, params["hard_stop_pct"])

                # 止盈触发率过低 → 降低止盈目标
                if tp_trigger_rate < 30:
                    params["take_profit_target_pct"] = 5.0
                    logger.info("[策略优化] 止盈触发率%.1f%%偏低，降低止盈目标至%.1f%%", tp_trigger_rate, params["take_profit_target_pct"])

            # 推荐追踪统计
            avg_win = abs(rec_stats.get("avg_win_pl_pct", 0) or 0)
            avg_loss = abs(rec_stats.get("avg_loss_pl_pct", 0) or 0)
            max_loss = abs(rec_stats.get("max_loss_pct", 0) or 0)

            if avg_loss > 0 and avg_win > 0:
                rr_ratio = avg_win / avg_loss
                if rr_ratio > 2.5:
                    # 盈亏比优秀，可略微放宽
                    params["hard_stop_pct"] = max(params["hard_stop_pct"] - 0.5, -8.0)
                    logger.info("[策略优化] 盈亏比%.1f优秀，放宽止损至%.1f%%", rr_ratio, params["hard_stop_pct"])

            if max_loss > avg_loss * 2:
                # 存在极端亏损，收紧硬止损
                params["hard_stop_pct"] = max(params["hard_stop_pct"] + 1.0, -8.0)
                logger.info("[策略优化] 最大亏损%.1f%%远超平均%.1f%%，收紧硬止损至%.1f%%", max_loss, avg_loss, params["hard_stop_pct"])

            return params
        except Exception as exc:
            logger.warning("[策略优化] 止损参数优化失败，使用默认值: %s", exc)
            return {"hard_stop_pct": -5.0, "trailing_stop_pct": -3.0, "take_profit_target_pct": 10.0, "time_stop_days": 10}

    # ── 信号过滤 ─────────────────────────────────────────────────────────────

    def should_filter_signal(
        self,
        code: str,
        source: str,
        sentiment_score: float,
        bias_ma5: float = 0,
        volume_ratio: Optional[float] = None,
    ) -> Tuple[bool, List[str]]:
        """判断是否应该过滤掉某个信号.

        Returns:
            (是否过滤, 过滤原因列表)
        """
        reasons = []
        weights = self.compute_source_weights()
        source_weight = weights.get(source, 1.0)

        # 来源权重过低 → 过滤
        if source_weight < 0.5:
            reasons.append(f"来源 {source} 历史胜率过低(权重={source_weight})，自动过滤")

        # 情绪评分过低 → 过滤
        if sentiment_score < 30:
            reasons.append(f"情绪评分 {sentiment_score} 过低(<30)，自动过滤")

        # 乖离率过高 → 过滤
        if abs(bias_ma5) > 5.0:
            reasons.append(f"乖离率 {abs(bias_ma5):.1f}% 过高(>5%)，不追高")

        # 量比异常 → 过滤
        if volume_ratio is not None and volume_ratio > 3.0:
            reasons.append(f"量比 {volume_ratio:.1f} 过高(>3)，不追高")

        return len(reasons) > 0, reasons

    # ── 策略自省报告 ─────────────────────────────────────────────────────────

    def generate_optimization_report(self) -> Dict[str, Any]:
        """生成策略优化报告.

        整合回测+推荐追踪数据，产出自省与优化建议。
        """
        try:
            from src.services.backtest_service import BacktestService
            from src.services.recommendation_tracking_service import RecommendationTrackingService

            backtest_svc = BacktestService()
            tracking_svc = RecommendationTrackingService()

            bt_summary = backtest_svc.get_global_summary() or {}
            rec_stats = tracking_svc.get_stats()
            source_weights = self.compute_source_weights()
            stop_params = self.optimize_stop_params()

            # 综合评分
            win_rate = rec_stats.get("win_rate", 0)
            profit_factor = rec_stats.get("profit_factor", 0)
            direction_accuracy = bt_summary.get("direction_accuracy_pct", 0) or 0

            # 综合健康度评分 (0-100)
            health_score = 0
            health_score += min(win_rate * 0.8, 40)  # 胜率最多贡献40分
            health_score += min(profit_factor * 15, 30)  # 盈亏比最多贡献30分
            health_score += min(direction_accuracy * 0.3, 30)  # 方向准确率最多贡献30分
            health_score = min(health_score, 100)

            # 问题识别
            issues = []
            suggestions = []

            if win_rate < 45:
                issues.append(f"胜率偏低 ({win_rate}%)，需审视推荐信号质量")
                suggestions.append("加强信号过滤：仅保留评分>50且来源权重>0.7的信号")
            if profit_factor < 1.2:
                issues.append(f"盈亏比不足 ({profit_factor})，亏损幅度接近或超过盈利")
                suggestions.append(f"收紧止损至 {stop_params['hard_stop_pct']}%，降低止盈目标至 {stop_params['take_profit_target_pct']}%")
            if direction_accuracy < 50:
                issues.append(f"方向判断准确率低 ({direction_accuracy}%)，趋势分析可能需要校准")
                suggestions.append("强化趋势分析权重，仅做多头排列标的")

            # 来源问题
            for src, weight in source_weights.items():
                if weight < 0.7:
                    issues.append(f"来源 {src} 表现差(权重={weight})，建议降低依赖或引入二次确认")

            # 持仓风险
            active_dev = rec_stats.get("active_deviation", [])
            high_risk_positions = [d for d in active_dev if d.get("deviation_pct", 0) < -3]
            if high_risk_positions:
                issues.append(f"当前 {len(high_risk_positions)} 只持仓亏损超3%，需评估是否止损")

            return {
                "generated_at": datetime.now().isoformat(),
                "health_score": round(health_score, 1),
                "health_level": "优秀" if health_score >= 80 else "良好" if health_score >= 60 else "一般" if health_score >= 40 else "需改进",
                "key_metrics": {
                    "win_rate": win_rate,
                    "profit_factor": profit_factor,
                    "direction_accuracy": direction_accuracy,
                    "total_records": rec_stats.get("total_records", 0),
                    "closed_count": rec_stats.get("closed_count", 0),
                },
                "source_weights": source_weights,
                "optimized_params": stop_params,
                "issues": issues,
                "suggestions": suggestions,
                "high_risk_positions": high_risk_positions[:10],
            }
        except Exception as exc:
            logger.warning("[策略优化] 优化报告生成失败: %s", exc)
            return {
                "generated_at": datetime.now().isoformat(),
                "health_score": 0,
                "health_level": "数据不足",
                "key_metrics": {
                    "win_rate": 0,
                    "profit_factor": 0,
                    "direction_accuracy": 0,
                    "total_records": 0,
                    "closed_count": 0,
                },
                "source_weights": {},
                "optimized_params": {
                    "hard_stop_pct": -7.0,
                    "trailing_stop_pct": -3.0,
                    "take_profit_target_pct": 10.0,
                    "time_stop_days": 5,
                },
                "issues": [],
                "suggestions": [],
                "high_risk_positions": [],
                "error": str(exc),
            }
