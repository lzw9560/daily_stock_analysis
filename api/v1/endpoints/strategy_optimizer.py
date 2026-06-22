# -*- coding: utf-8 -*-
"""策略优化 API 端点 — 策略自省、参数优化、信号过滤."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["策略优化"])


# ── Response Models ──────────────────────────────────────────────────────────


class SourceWeightItem(BaseModel):
    source: str
    weight: float
    win_rate: float
    total: int


class StopParamsModel(BaseModel):
    hard_stop_pct: float
    trailing_stop_pct: float
    take_profit_target_pct: float
    time_stop_days: int


class KeyMetricsModel(BaseModel):
    win_rate: float
    profit_factor: float
    direction_accuracy: float
    total_records: int
    closed_count: int


class HighRiskPositionModel(BaseModel):
    id: int
    code: str
    trade_date: str
    signal: str
    recommendation_price: float
    current_price: float
    deviation_pct: float


class OptimizationReportResponse(BaseModel):
    generated_at: str
    health_score: float
    health_level: str
    key_metrics: KeyMetricsModel
    source_weights: Dict[str, float]
    optimized_params: StopParamsModel
    issues: List[str]
    suggestions: List[str]
    high_risk_positions: List[HighRiskPositionModel]
    error: Optional[str] = None


class SignalFilterRequest(BaseModel):
    code: str
    source: str = "analysis"
    sentiment_score: float
    bias_ma5: float = 0
    volume_ratio: Optional[float] = None


class SignalFilterResponse(BaseModel):
    filtered: bool
    reasons: List[str]
    source_weight: float


class DisciplineCheckRequest(BaseModel):
    code: str
    bias_ma5: float = 0
    volume_ratio: Optional[float] = None
    ma_alignment: str = ""
    concentration_90: Optional[float] = None
    profit_ratio: Optional[float] = None


class DisciplineCheckResponse(BaseModel):
    passed: bool
    violations: List[str]
    rules: Dict[str, float]


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/report", response_model=OptimizationReportResponse)
async def get_optimization_report():
    """获取策略优化报告.

    整合回测 + 推荐追踪数据，产出：
    - 综合健康度评分
    - 来源权重建议
    - 止损/止盈参数优化
    - 问题识别与改进建议
    - 高风险持仓预警
    """
    try:
        from src.services.strategy_optimizer import StrategyOptimizer

        optimizer = StrategyOptimizer()
        report = optimizer.generate_optimization_report()
        return report
    except Exception as exc:
        logger.exception("生成优化报告失败")
        raise HTTPException(status_code=500, detail=f"生成优化报告失败: {exc}")


@router.post("/filter-signal", response_model=SignalFilterResponse)
async def filter_signal(request: SignalFilterRequest):
    """信号过滤检查.

    基于历史胜率、评分、乖离率、量比等维度，
    判断信号是否应该被过滤。
    """
    try:
        from src.services.strategy_optimizer import StrategyOptimizer

        optimizer = StrategyOptimizer()
        filtered, reasons = optimizer.should_filter_signal(
            code=request.code,
            source=request.source,
            sentiment_score=request.sentiment_score,
            bias_ma5=request.bias_ma5,
            volume_ratio=request.volume_ratio,
        )
        weights = optimizer.compute_source_weights()
        source_weight = weights.get(request.source, 1.0)

        return SignalFilterResponse(
            filtered=filtered,
            reasons=reasons,
            source_weight=source_weight,
        )
    except Exception as exc:
        logger.exception("信号过滤检查失败")
        raise HTTPException(status_code=500, detail=f"信号过滤检查失败: {exc}")


@router.post("/check-discipline", response_model=DisciplineCheckResponse)
async def check_discipline(request: DisciplineCheckRequest):
    """交易纪律前置检查.

    检查是否违反硬约束规则：
    - 乖离率不超过5%
    - 均线多头排列
    - 量比不超过3倍
    - 筹码集中度合理
    - 获利比例合理
    """
    try:
        from src.services.logic_closure_service import LogicClosureService, DISCIPLINE_RULES

        closure = LogicClosureService()
        violations = []

        # 乖离率
        if abs(request.bias_ma5) > DISCIPLINE_RULES["max_bias_ma5"]:
            violations.append(
                f"乖离率过高: {abs(request.bias_ma5):.1f}% > {DISCIPLINE_RULES['max_bias_ma5']}%"
            )

        # 均线排列
        if request.ma_alignment and "多头" not in request.ma_alignment:
            violations.append(f"均线排列不符合多头: {request.ma_alignment}")

        # 量比
        if request.volume_ratio and request.volume_ratio > DISCIPLINE_RULES["max_volume_ratio_buy"]:
            violations.append(
                f"量比过高: {request.volume_ratio:.1f} > {DISCIPLINE_RULES['max_volume_ratio_buy']}"
            )

        # 筹码集中度
        if request.concentration_90 and request.concentration_90 > DISCIPLINE_RULES["max_concentration_90"]:
            violations.append(
                f"筹码分散: 90%集中度={request.concentration_90:.1%}"
            )

        # 获利比例
        if request.profit_ratio is not None and request.profit_ratio < DISCIPLINE_RULES["min_profit_ratio"]:
            violations.append(f"获利比例过低: {request.profit_ratio:.1%}")

        return DisciplineCheckResponse(
            passed=len(violations) == 0,
            violations=violations,
            rules=DISCIPLINE_RULES,
        )
    except Exception as exc:
        logger.exception("交易纪律检查失败")
        raise HTTPException(status_code=500, detail=f"交易纪律检查失败: {exc}")


@router.get("/source-weights", response_model=List[SourceWeightItem])
async def get_source_weights():
    """获取各推荐来源的动态权重."""
    try:
        from src.services.strategy_optimizer import StrategyOptimizer
        from src.services.recommendation_tracking_service import RecommendationTrackingService

        optimizer = StrategyOptimizer()
        tracking_svc = RecommendationTrackingService()

        weights = optimizer.compute_source_weights()
        stats = tracking_svc.get_stats()
        by_source = stats.get("by_source", {})

        items = []
        for source, weight in weights.items():
            source_data = by_source.get(source, {})
            items.append(SourceWeightItem(
                source=source,
                weight=weight,
                win_rate=source_data.get("win_rate", 0),
                total=source_data.get("total", 0),
            ))

        return sorted(items, key=lambda x: x.weight, reverse=True)
    except Exception as exc:
        logger.exception("获取来源权重失败")
        raise HTTPException(status_code=500, detail=f"获取来源权重失败: {exc}")


@router.get("/stop-params", response_model=StopParamsModel)
async def get_optimized_stop_params():
    """获取优化后的止损/止盈参数."""
    try:
        from src.services.strategy_optimizer import StrategyOptimizer

        optimizer = StrategyOptimizer()
        params = optimizer.optimize_stop_params()
        return StopParamsModel(**params)
    except Exception as exc:
        logger.exception("获取止损参数失败")
        raise HTTPException(status_code=500, detail=f"获取止损参数失败: {exc}")
