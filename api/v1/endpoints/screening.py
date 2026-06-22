# -*- coding: utf-8 -*-
"""Screening record query and manual trigger API endpoints."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.deps import get_config_dep
from src.config import Config
from api.v1.schemas.screening import (
    FactorPipelineRecordResponse,
    FactorPipelineTriggerRequest,
    FactorPipelineTriggerResponse,
    ScreeningRecordListResponse,
    ScreeningRunRequest,
    ScreeningRunResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/strategies")
def screening_strategies(config: Config = Depends(get_config_dep)) -> Dict[str, Any]:
    """获取已配置的选股策略列表及历史策略统计。"""
    from src.services.screening_service import ScreeningService
    service = ScreeningService()

    configured = service.get_configured_strategies()
    historical = service.get_available_strategies()

    return {
        "configured": configured,
        "historical": historical,
    }


@router.get("/dates")
def screening_dates() -> Dict[str, Any]:
    """获取有选股记录的日期列表。"""
    from src.services.screening_service import ScreeningService
    service = ScreeningService()
    dates = service.get_available_dates()
    return {"dates": dates, "count": len(dates)}


@router.get("/records", response_model=ScreeningRecordListResponse)
def screening_records(
    screening_date: Optional[str] = Query(default=None, description="筛选日期 ISO 格式 YYYY-MM-DD"),
    strategy: Optional[str] = Query(default=None, description="策略名称"),
    market: Optional[str] = Query(default=None, description="市场 cn/hk/us"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    config: Config = Depends(get_config_dep),
) -> Dict[str, Any]:
    """分页查询选股记录列表。"""
    from src.services.screening_service import ScreeningService
    service = ScreeningService()

    parsed_date = None
    if screening_date:
        try:
            parsed_date = date.fromisoformat(screening_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="日期格式无效，请使用 YYYY-MM-DD")

    return ScreeningRecordListResponse(**service.get_records(
        screening_date=parsed_date,
        strategy=strategy,
        market=market,
        limit=limit,
        offset=offset,
    ))


@router.get("/records/{record_id}")
def screening_record_detail(record_id: int) -> Dict[str, Any]:
    """获取单条选股记录的详细信息，包含候选股票和回测结果。"""
    from src.services.screening_service import ScreeningService
    service = ScreeningService()

    detail = service.get_record_detail(record_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"选股记录 {record_id} 不存在")

    return detail


@router.get("/records/{record_id}/backtest-results")
def screening_record_backtest_results(record_id: int) -> Dict[str, Any]:
    """获取与选股记录关联的回测结果。"""
    from src.repositories.screening_repo import ScreeningRepository
    repo = ScreeningRepository()

    record = repo.get_record_by_id(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"选股记录 {record_id} 不存在")

    results = repo.get_backtest_results_for_record(record_id)
    summary = repo.get_backtest_summary_for_record(record_id)

    return {
        "record_id": record_id,
        "screening_date": record.screening_date.isoformat() if record.screening_date else None,
        "strategy": record.strategy,
        "backtest_count": len(results),
        "results": results,
        "summary": summary,
    }


@router.get("/records/{record_id}/factor-pipeline", response_model=FactorPipelineRecordResponse)
def screening_record_factor_pipeline(record_id: int) -> FactorPipelineRecordResponse:
    """获取选股记录的因子流水线结果。"""
    from src.services.screening_service import ScreeningService
    service = ScreeningService()

    from src.services.factor_pipeline_service import FactorPipelineService
    factor_service = FactorPipelineService()

    try:
        factor_pipeline = factor_service.get_screening_record_factor_pipeline(record_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"选股记录 {record_id} 不存在")

    return FactorPipelineRecordResponse(record_id=record_id, factor_pipeline=factor_pipeline)


@router.post("/run", response_model=ScreeningRunResponse)
def screening_run(
    request: ScreeningRunRequest,
    config: Config = Depends(get_config_dep),
) -> Dict[str, Any]:
    """手动触发多策略选股及自动回测。

    可通过 request body 指定策略列表、市场和参数。
    如果未指定 strategies，将使用配置文件中的 SCREENING_STRATEGIES。
    """
    if not config.alphasift_enabled:
        raise HTTPException(
            status_code=403,
            detail="ALPHASIFT_ENABLED=false，选股功能未启用。请先设置 ALPHASIFT_ENABLED=true。",
        )

    from src.services.screening_service import ScreeningService
    service = ScreeningService()

    try:
        result = service.run_daily_screening(
            strategies=request.strategies,
            market=request.market,
            max_results=request.max_results,
            auto_backtest=request.auto_backtest,
        )
        return result
    except Exception as exc:
        logger.exception("手动触发选股失败")
        raise HTTPException(
            status_code=500,
            detail=f"选股执行失败: {exc}",
        )


@router.post("/factor-pipeline/run", response_model=FactorPipelineTriggerResponse)
def screening_factor_pipeline_run(
    request: FactorPipelineTriggerRequest,
    config: Config = Depends(get_config_dep),
) -> FactorPipelineTriggerResponse:
    """显式触发因子流水线骨架。

    该接口用于前端/任务面板对历史选股记录重跑因子摘要。
    """
    from src.services.factor_pipeline_service import FactorPipelineService

    if not getattr(config, "factor_pipeline_enabled", False):
        raise HTTPException(
            status_code=403,
            detail="FACTOR_PIPELINE_ENABLED=false，因子流水线未启用。请先设置 FACTOR_PIPELINE_ENABLED=true。",
        )

    service = FactorPipelineService()
    screening_date = None
    if request.screening_date:
        try:
            screening_date = date.fromisoformat(request.screening_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="日期格式无效，请使用 YYYY-MM-DD")

    try:
        result = service.run_for_screening_record(
            request.record_id,
            market=request.market,
            screening_date=screening_date,
        )
        return FactorPipelineTriggerResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("因子流水线触发失败")
        raise HTTPException(status_code=500, detail=f"因子流水线执行失败: {exc}")
