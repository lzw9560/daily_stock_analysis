# -*- coding: utf-8 -*-
"""Backtest endpoints."""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_database_manager
from api.v1.schemas.backtest import (
    BacktestOptimizationRequest,
    BacktestOptimizationResponse,
    BacktestRunRequest, BacktestRunResponse, BacktestResultItem,
    BacktestResultsResponse, PerformanceMetrics,
    MonteCarloSimulationRequest,
    MonteCarloSimulationResponse,
)
from api.v1.schemas.common import ErrorResponse
from src.services.backtest_service import BacktestService
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)
router = APIRouter()


def _validate_date_range(from_date: Optional[date], to_date: Optional[date]) -> None:
    if from_date and to_date and from_date > to_date:
        raise HTTPException(400, detail={"error": "invalid_params", "message": "analysis_date_from cannot be after analysis_date_to"})


def _service(db: DatabaseManager) -> BacktestService:
    return BacktestService(db)


# ──── POST /run ────

@router.post("/run", response_model=BacktestRunResponse,
             responses={200: {"description": "回测执行完成"}, 500: {"description": "服务器错误", "model": ErrorResponse}},
             summary="触发回测")
def run_backtest(request: BacktestRunRequest, db: DatabaseManager = Depends(get_database_manager)) -> BacktestRunResponse:
    try:
        return BacktestRunResponse(**_service(db).run_backtest(
            code=request.code, force=request.force,
            eval_window_days=request.eval_window_days,
            min_age_days=request.min_age_days, limit=request.limit))
    except Exception as exc:
        logger.error(f"回测执行失败: {exc}", exc_info=True)
        raise HTTPException(500, detail={"error": "internal_error", "message": str(exc)})


@router.post("/optimize", response_model=BacktestOptimizationResponse,
            responses={200: {"description": "组合优化完成"}, 500: {"description": "服务器错误", "model": ErrorResponse}},
            summary="优化回测参数组合")
def optimize_backtest(
    request: BacktestOptimizationRequest,
    db: DatabaseManager = Depends(get_database_manager),
) -> BacktestOptimizationResponse:
    try:
        return BacktestOptimizationResponse(**_service(db).optimize_backtest(
            code=request.code,
            eval_window_days=request.eval_window_days,
            min_age_days=request.min_age_days,
            limit=request.limit,
        ))
    except ValueError as exc:
        raise HTTPException(400, detail={"error": "invalid_params", "message": str(exc)})
    except Exception as exc:
        logger.error(f"回测优化失败: {exc}", exc_info=True)
        raise HTTPException(500, detail={"error": "internal_error", "message": str(exc)})


@router.get("/optimize/logs", summary="获取回测优化日志")
def get_backtest_optimization_logs(
    code: Optional[str] = Query(None, description="股票代码筛选"),
    limit: int = Query(20, ge=1, le=100),
    db: DatabaseManager = Depends(get_database_manager),
):
    try:
        return _service(db).get_optimization_log_overview(code=code, limit=limit)
    except Exception as exc:
        logger.error(f"查询回测优化日志失败: {exc}", exc_info=True)
        raise HTTPException(500, detail={"error": "internal_error", "message": str(exc)})


# ──── GET /results ────

@router.get("/results", response_model=BacktestResultsResponse,
            responses={200: {"description": "回测结果列表"}, 500: {"description": "服务器错误", "model": ErrorResponse}},
            summary="获取回测结果")
def get_backtest_results(
    code: Optional[str] = Query(None, description="股票代码筛选"),
    eval_window_days: Optional[int] = Query(None, ge=1, le=120),
    analysis_date_from: Optional[date] = Query(None),
    analysis_date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=200),
    db: DatabaseManager = Depends(get_database_manager),
) -> BacktestResultsResponse:
    _validate_date_range(analysis_date_from, analysis_date_to)
    try:
        data = _service(db).get_recent_evaluations(
            code=code, eval_window_days=eval_window_days,
            limit=limit, page=page,
            analysis_date_from=analysis_date_from, analysis_date_to=analysis_date_to)
        return BacktestResultsResponse(
            total=int(data["total"]), page=page, limit=limit,
            items=[BacktestResultItem(**item) for item in data.get("items", [])])
    except Exception as exc:
        logger.error(f"查询回测结果失败: {exc}", exc_info=True)
        raise HTTPException(500, detail={"error": "internal_error", "message": str(exc)})


# ──── GET /performance ────

@router.get("/performance", response_model=PerformanceMetrics,
            responses={200: {"description": "整体回测表现"}, 404: {"description": "无回测汇总", "model": ErrorResponse}},
            summary="获取整体回测表现")
def get_overall_performance(
    eval_window_days: Optional[int] = Query(None, ge=1, le=120),
    analysis_date_from: Optional[date] = Query(None),
    analysis_date_to: Optional[date] = Query(None),
    db: DatabaseManager = Depends(get_database_manager),
) -> PerformanceMetrics:
    _validate_date_range(analysis_date_from, analysis_date_to)
    try:
        summary = _service(db).get_summary(
            scope="overall", code=None, eval_window_days=eval_window_days,
            analysis_date_from=analysis_date_from, analysis_date_to=analysis_date_to)
        if summary is None:
            raise HTTPException(404, detail={"error": "not_found", "message": "未找到整体回测汇总"})
        return PerformanceMetrics(**summary)
    except ValueError as exc:
        raise HTTPException(400, detail={"error": "invalid_params", "message": str(exc)})
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"查询整体表现失败: {exc}", exc_info=True)
        raise HTTPException(500, detail={"error": "internal_error", "message": str(exc)})


# ──── GET /performance/{code} ────

@router.get("/performance/{code}", response_model=PerformanceMetrics,
            responses={200: {"description": "单股回测表现"}, 404: {"description": "无回测汇总", "model": ErrorResponse}},
            summary="获取单股回测表现")
def get_stock_performance(
    code: str,
    eval_window_days: Optional[int] = Query(None, ge=1, le=120),
    analysis_date_from: Optional[date] = Query(None),
    analysis_date_to: Optional[date] = Query(None),
    db: DatabaseManager = Depends(get_database_manager),
) -> PerformanceMetrics:
    _validate_date_range(analysis_date_from, analysis_date_to)
    try:
        summary = _service(db).get_summary(
            scope="stock", code=code, eval_window_days=eval_window_days,
            analysis_date_from=analysis_date_from, analysis_date_to=analysis_date_to)
        if summary is None:
            raise HTTPException(404, detail={"error": "not_found", "message": f"未找到 {code} 的回测汇总"})
        return PerformanceMetrics(**summary)
    except ValueError as exc:
        raise HTTPException(400, detail={"error": "invalid_params", "message": str(exc)})
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"查询单股表现失败: {exc}", exc_info=True)
        raise HTTPException(500, detail={"error": "internal_error", "message": str(exc)})


@router.post("/phase4/simulate", response_model=MonteCarloSimulationResponse, summary="Phase 4 蒙特卡洛+原子执行计划")
def simulate_phase4(request: MonteCarloSimulationRequest) -> MonteCarloSimulationResponse:
    try:
        from src.services.execution_planner import ExecutionPlanner

        planner = ExecutionPlanner()
        return MonteCarloSimulationResponse(
            **planner.plan(
                symbol=request.symbol,
                side=request.side,
                spot=request.spot,
                quantity=request.quantity,
                horizon_days=request.horizon_days,
                paths=request.paths,
                model=request.model,
                drift=request.drift,
                vol=request.vol,
                win_rate=request.win_rate,
                payoff_ratio=request.payoff_ratio,
                max_position_pct=request.max_position_pct,
                dry_run=request.dry_run,
                metadata=request.metadata,
            )
        )
    except Exception as exc:
        logger.exception("Phase 4 simulation failed")
        raise HTTPException(500, detail={"error": "internal_error", "message": f"Phase 4 simulation failed: {exc}"})
