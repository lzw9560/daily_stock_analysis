"""
LLM驱动复盘分析器

基于历史推荐日志，调用大模型进行深度分析：
1. 识别成功/失败的模式
2. 生成评分权重建言
3. 提出策略优化建议
4. 输出人类可读的复盘报告
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .recommendation_log import RecommendationLog, RecommendationItem, RecommendationLogStore
from .win_rate_tracker import WinRateTracker, WinRateStats

logger = logging.getLogger(__name__)


@dataclass
class ReviewInsight:
    """LLM复盘洞察"""
    date: str
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 核心结论
    summary: str = ""                          # 一句话总结
    overall_assessment: str = ""               # 整体评估

    # 模式识别
    success_patterns: list[str] = field(default_factory=list)    # 成功模式
    failure_patterns: list[str] = field(default_factory=list)    # 失败模式
    high_momentum_sectors: list[str] = field(default_factory=list)  # 高动量板块
    risk_sectors: list[str] = field(default_factory=list)           # 风险板块

    # 策略建议
    strategy_adjustments: list[str] = field(default_factory=list)   # 策略调整建议
    score_weight_suggestions: list[str] = field(default_factory=list)  # 评分权重建言
    position_advice: str = ""                   # 仓位建议

    # 参数调优
    recommended_min_score: int = 65             # 建议最低评分
    recommended_confidence_threshold: str = "中"  # 建议置信度门槛
    max_daily_recommendations: int = 5           # 建议每日最大推荐数

    # 元信息
    model_used: str = ""                        # 使用的LLM模型
    analysis_logs_count: int = 0                # 分析的日志数量
    raw_llm_response: str = ""                  # LLM原始响应（调试用）

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "generated_at": self.generated_at,
            "summary": self.summary,
            "overall_assessment": self.overall_assessment,
            "success_patterns": self.success_patterns,
            "failure_patterns": self.failure_patterns,
            "high_momentum_sectors": self.high_momentum_sectors,
            "risk_sectors": self.risk_sectors,
            "strategy_adjustments": self.strategy_adjustments,
            "score_weight_suggestions": self.score_weight_suggestions,
            "position_advice": self.position_advice,
            "recommended_min_score": self.recommended_min_score,
            "recommended_confidence_threshold": self.recommended_confidence_threshold,
            "max_daily_recommendations": self.max_daily_recommendations,
            "model_used": self.model_used,
            "analysis_logs_count": self.analysis_logs_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewInsight":
        return cls(
            date=data.get("date", ""),
            generated_at=data.get("generated_at", ""),
            summary=data.get("summary", ""),
            overall_assessment=data.get("overall_assessment", ""),
            success_patterns=data.get("success_patterns", []),
            failure_patterns=data.get("failure_patterns", []),
            high_momentum_sectors=data.get("high_momentum_sectors", []),
            risk_sectors=data.get("risk_sectors", []),
            strategy_adjustments=data.get("strategy_adjustments", []),
            score_weight_suggestions=data.get("score_weight_suggestions", []),
            position_advice=data.get("position_advice", ""),
            recommended_min_score=data.get("recommended_min_score", 65),
            recommended_confidence_threshold=data.get("recommended_confidence_threshold", "中"),
            max_daily_recommendations=data.get("max_daily_recommendations", 5),
            model_used=data.get("model_used", ""),
            analysis_logs_count=data.get("analysis_logs_count", 0),
        )


class LLMReviewer:
    """LLM驱动的复盘分析器

    工作流程：
    1. 加载最近N天的推荐日志
    2. 构建复盘提示词（包含历史表现数据）
    3. 调用 LLM 进行分析
    4. 解析 LLM 响应为结构化洞察
    5. 保存复盘报告
    """

    DAYS_TO_ANALYZE = 30   # 分析最近30天
    MODEL_PREFERENCE = ["gemini/gemini-2.0-flash", "gemini/gemini-1.5-pro", "deepseek/deepseek-chat"]

    def __init__(
        self,
        log_store: Optional[RecommendationLogStore] = None,
        model: Optional[str] = None,
    ):
        self.log_store = log_store or RecommendationLogStore()
        self.tracker = WinRateTracker(self.log_store)
        self.model = model

    def analyze(
        self,
        target_date: Optional[str] = None,
        days: int = DAYS_TO_ANALYZE,
    ) -> Optional[ReviewInsight]:
        """
        执行LLM驱动的复盘分析

        Args:
            target_date: 目标复盘日期（默认为今天）
            days: 分析最近多少天
        """
        target = target_date or datetime.now().strftime("%Y%m%d")

        # 1. 加载历史数据
        logs = self.log_store.load_all(limit=days)
        if not logs:
            logger.warning("无历史推荐数据，跳过复盘分析")
            return None

        # 2. 计算统计指标
        stats = self.tracker.compute_stats(logs)

        # 3. 构建分析数据
        analysis_data = self._build_analysis_data(logs, stats)

        # 4. 调用 LLM
        prompt = self._build_review_prompt(analysis_data)
        llm_response = self._call_llm(prompt)

        if not llm_response:
            logger.warning("LLM复盘分析未返回有效结果")
            return None

        # 5. 解析 LLM 响应
        insight = self._parse_llm_response(llm_response, target, len(logs))
        logger.info(
            "LLM复盘分析完成: %s, 分析%d天日志, 模型=%s",
            target, days, insight.model_used,
        )

        return insight

    def _build_analysis_data(self, logs: list[RecommendationLog], stats: WinRateStats) -> dict:
        """构建传给LLM的分析数据"""
        # 收集所有已结算的推荐
        settled_items: list[dict] = []
        for log in logs:
            for r in log.recommendations:
                if r.outcome is not None:
                    settled_items.append({
                        "date": log.date,
                        "phase": log.sentiment_phase,
                        "sentiment": log.sentiment_index,
                        "code": r.code,
                        "name": r.name,
                        "score": r.score,
                        "sector": r.sector,
                        "seal_time": r.seal_time,
                        "outcome": r.outcome,
                        "return_pct": r.actual_return_pct,
                        "won": r.won,
                    })

        # 按结果分组
        wins = [it for it in settled_items if it["won"]]
        losses = [it for it in settled_items if not it["won"]]

        # 构建板块表现汇总
        sector_performance = []
        for sector, d in sorted(stats.by_sector.items(), key=lambda x: x[1]["rate"], reverse=True):
            if d["total"] >= 2:
                sector_performance.append({
                    "sector": sector,
                    "won": d["won"],
                    "total": d["total"],
                    "rate": d["rate"],
                })

        # 评分区间表现
        score_performance = []
        for bucket, d in sorted(stats.by_score_range.items()):
            if d["total"] >= 2:
                score_performance.append({
                    "score_range": bucket,
                    "won": d["won"],
                    "total": d["total"],
                    "rate": d["rate"],
                })

        # 情绪周期表现
        phase_performance = {}
        for it in settled_items:
            phase = it["phase"]
            if phase not in phase_performance:
                phase_performance[phase] = {"won": 0, "total": 0}
            phase_performance[phase]["total"] += 1
            if it["won"]:
                phase_performance[phase]["won"] += 1
        for phase, d in phase_performance.items():
            d["rate"] = round(d["won"] / d["total"] * 100, 1) if d["total"] else 0

        # 时间特征（封板时间与结果的关系）
        time_analysis = {}
        for it in settled_items:
            hour = "早盘(10:00前)" if (it["seal_time"] or "99") < "10:00" else \
                   "午盘(10:00-14:00)" if (it["seal_time"] or "14:30") < "14:00" else "尾盘(14:00后)"
            if hour not in time_analysis:
                time_analysis[hour] = {"won": 0, "total": 0}
            time_analysis[hour]["total"] += 1
            if it["won"]:
                time_analysis[hour]["won"] += 1
        for hour, d in time_analysis.items():
            d["rate"] = round(d["won"] / d["total"] * 100, 1) if d["total"] else 0

        return {
            "total_settled": stats.settled,
            "total_won": stats.won,
            "total_lost": stats.lost,
            "pending": stats.pending,
            "win_rate": stats.win_rate,
            "avg_return": stats.avg_return,
            "max_return": stats.max_return,
            "rolling_win_rate_10": stats.rolling_win_rate_10,
            "trend": stats.trend,
            "wins": wins[-20:],          # 最近20笔成功案例
            "losses": losses[-20:],      # 最近20笔失败案例
            "sector_performance": sector_performance,
            "score_performance": score_performance,
            "phase_performance": phase_performance,
            "time_analysis": time_analysis,
            "current_adjustments": stats.strategy_adjustments,
        }

    def _build_review_prompt(self, data: dict) -> str:
        """构建复盘分析提示词"""
        return f"""你是一位专业的A股涨停板策略分析师。请基于以下历史推荐复盘的量化数据，进行深度分析。

## 总体表现
- 总推荐笔数: {data['total_settled']}（已结算）
- 盈利: {data['total_won']} | 亏损: {data['total_lost']} | 待结算: {data['pending']}
- 胜率: {data['win_rate']}%
- 平均收益率: {data['avg_return']}%
- 最高收益: {data['max_return']}%
- 近10笔滚动胜率: {data['rolling_win_rate_10']}%
- 趋势: {'上升' if data['trend'] == 'improving' else '下降' if data['trend'] == 'declining' else '稳定'}

## 板块表现（胜率由高到低）
{json.dumps(data['sector_performance'], ensure_ascii=False, indent=2)}

## 评分区间表现
{json.dumps(data['score_performance'], ensure_ascii=False, indent=2)}

## 不同情绪周期的表现
{json.dumps(data['phase_performance'], ensure_ascii=False, indent=2)}

## 封板时间与结果
{json.dumps(data['time_analysis'], ensure_ascii=False, indent=2)}

## 最近成功案例
{json.dumps(data['wins'], ensure_ascii=False, indent=2)}

## 最近失败案例
{json.dumps(data['losses'], ensure_ascii=False, indent=2)}

## 当前策略调整
{json.dumps(data['current_adjustments'], ensure_ascii=False, indent=2)}

---

请以JSON格式输出你的分析结果（严格JSON，不要markdown代码块包裹）：

{{
  "summary": "一句话总结当前策略表现",
  "overall_assessment": "对当前推荐策略的整体评估（150字以内）",
  "success_patterns": ["成功模式的共性特征1", "成功模式的共性特征2", ...],
  "failure_patterns": ["失败模式的核心原因1", "失败模式的核心原因2", ...],
  "high_momentum_sectors": ["当前高胜率可持续板块"],
  "risk_sectors": ["当前需要回避的板块"],
  "strategy_adjustments": ["具体可执行的策略优化建议1", "建议2", ...],
  "score_weight_suggestions": ["对当前评分维度的权重调整建议1", "建议2", ...],
  "position_advice": "基于当前胜率的仓位管理建议（100字以内）",
  "recommended_min_score": 数字（建议的最低评分门槛),
  "recommended_confidence_threshold": "高/中/低",
  "max_daily_recommendations": 数字（建议的每日最大推荐数)
}}

请确保：
1. 建议具体、可量化、可执行
2. 结合市场环境给出context-aware的建议
3. 成功/失败模式的总结要有归纳性，不只罗列数据
4. 评分权重建言要考虑维度间的平衡
5. 仓位建议要考虑当前胜率趋势
"""

    def _call_llm(self, prompt: str) -> Optional[str]:
        """调用LLM进行分析"""
        try:
            from litellm import completion

            models_to_try = [self.model] if self.model else self.MODEL_PREFERENCE

            for model in models_to_try:
                try:
                    response = completion(
                        model=model,
                        messages=[
                            {
                                "role": "system",
                                "content": "你是一位量化交易策略分析师，擅长从统计数据中发现规律。请只输出要求的JSON格式数据，不要包含任何其他文字。"
                            },
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.3,  # 低温度保证一致性
                        max_tokens=4096,
                    )
                    content = response.choices[0].message.content
                    if content:
                        logger.info("LLM复盘分析调用成功: %s", model)
                        return content
                except Exception as e:
                    logger.warning("LLM复盘分析(%s)失败: %s", model, e)
                    continue

            return None

        except ImportError:
            logger.error("litellm未安装，无法进行LLM复盘分析")
            return None

    def _parse_llm_response(
        self, response: str, target_date: str, logs_count: int
    ) -> Optional[ReviewInsight]:
        """解析LLM响应为结构化洞察"""
        try:
            # 尝试提取JSON（处理可能的markdown包裹）
            text = response.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])

            data = json.loads(text)

            return ReviewInsight(
                date=target_date,
                summary=data.get("summary", ""),
                overall_assessment=data.get("overall_assessment", ""),
                success_patterns=data.get("success_patterns", []),
                failure_patterns=data.get("failure_patterns", []),
                high_momentum_sectors=data.get("high_momentum_sectors", []),
                risk_sectors=data.get("risk_sectors", []),
                strategy_adjustments=data.get("strategy_adjustments", []),
                score_weight_suggestions=data.get("score_weight_suggestions", []),
                position_advice=data.get("position_advice", ""),
                recommended_min_score=data.get("recommended_min_score", 65),
                recommended_confidence_threshold=data.get("recommended_confidence_threshold", "中"),
                max_daily_recommendations=data.get("max_daily_recommendations", 5),
                model_used="litellm/multi",
                analysis_logs_count=logs_count,
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.error("解析LLM复盘响应失败: %s", e)
            logger.debug("原始响应: %s", response[:500])

            # 降级：即使解析失败，也返回基本的分析结果
            return ReviewInsight(
                date=target_date,
                summary="LLM响应解析失败，请检查原始响应",
                overall_assessment=response[:200] if response else "无法获取LLM分析结果",
                model_used="litellm/multi",
                analysis_logs_count=logs_count,
            )

    def analyze_and_save(self, target_date: Optional[str] = None) -> Optional[ReviewInsight]:
        """执行分析并保存"""
        from .review_log import ReviewLogStore as ReviewLogStoreNew

        insight = self.analyze(target_date=target_date)
        if insight:
            store = ReviewLogStoreNew()
            store.save(insight)
        return insight
