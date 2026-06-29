# -*- coding: utf-8 -*-
"""
历史推荐追踪 API 端点.

提供推荐记录的 CRUD、胜率统计、自省总结等功能。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.recommendation_tracking import (
    CloseRecordRequest,
    CommonalityResponse,
    CreateRecommendationRequest,
    RecommendationListResponse,
    RecommendationRecordSchema,
    RecommendationStatsResponse,
    SummaryRequest,
    SummaryResponse,
    UpdatePriceRequest,
    UpdateRecordRequest,
)
from src.services.recommendation_tracking_service import RecommendationTrackingService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["推荐追踪"])


# ── 创建 ────────────────────────────────────────────────────────────────────


@router.post("/records", response_model=RecommendationRecordSchema, status_code=201)
async def create_record(req: CreateRecommendationRequest) -> Dict[str, Any]:
    """创建推荐追踪记录（支持增强分类字段）."""
    try:
        service = RecommendationTrackingService()
        return service.create_record(
            code=req.code,
            trade_date=req.trade_date,
            recommendation_price=req.recommendation_price,
            signal=req.signal,
            source=req.source,
            source_task_id=req.source_task_id,
            reason=req.reason,
            signal_type=req.signal_type,
            strategy_pattern=req.strategy_pattern,
            confidence=req.confidence,
            entry_method=req.entry_method,
            stop_loss=req.stop_loss,
            take_profit=req.take_profit,
            sectors=req.sectors,
            sentiment_phase=req.sentiment_phase,
            expected_hold_days=req.expected_hold_days,
            time_horizon=req.time_horizon,
        )
    except Exception as exc:
        logger.exception("创建推荐记录失败")
        raise HTTPException(status_code=500, detail=str(exc))


# ── 查询列表 ────────────────────────────────────────────────────────────────


@router.get("/records", response_model=RecommendationListResponse)
async def list_records(
    code: Optional[str] = Query(None, description="股票代码"),
    status: Optional[str] = Query(None, description="状态: active/closed/expired"),
    signal: Optional[str] = Query(None, description="方向: buy/sell/hold"),
    source: Optional[str] = Query(None, description="来源: analysis/deep_analysis/seal_plate/comprehensive/manual"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
) -> Dict[str, Any]:
    """分页查询推荐记录列表，支持多维度筛选."""
    try:
        service = RecommendationTrackingService()
        return service.list_records(
            code=code,
            status=status,
            signal=signal,
            source=source,
            start_date=start_date,
            end_date=end_date,
            page=page,
            limit=limit,
        )
    except Exception as exc:
        logger.exception("查询推荐记录列表失败")
        raise HTTPException(status_code=500, detail=str(exc))


# ── 查询单条 ────────────────────────────────────────────────────────────────


@router.get("/records/{record_id}", response_model=RecommendationRecordSchema)
async def get_record(record_id: int) -> Dict[str, Any]:
    """获取单条推荐记录详情."""
    service = RecommendationTrackingService()
    record = service.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    return record


# ── 更新 ────────────────────────────────────────────────────────────────────


@router.put("/records/{record_id}", response_model=RecommendationRecordSchema)
async def update_record(record_id: int, req: UpdateRecordRequest) -> Dict[str, Any]:
    """部分更新推荐记录."""
    service = RecommendationTrackingService()
    updates = {k: v for k, v in req.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="至少需要提供一个更新字段")
    result = service.update_record(record_id, **updates)
    if not result:
        raise HTTPException(status_code=404, detail="记录不存在")
    return result


# ── 删除 ────────────────────────────────────────────────────────────────────


@router.delete("/records/{record_id}")
async def delete_record(record_id: int) -> Dict[str, str]:
    """删除推荐记录."""
    service = RecommendationTrackingService()
    deleted = service.delete_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"message": "记录已删除", "record_id": str(record_id)}


# ── 平仓 ────────────────────────────────────────────────────────────────────


@router.post("/records/{record_id}/close", response_model=RecommendationRecordSchema)
async def close_record(record_id: int, req: CloseRecordRequest) -> Dict[str, Any]:
    """平仓推荐记录，自动计算盈亏."""
    try:
        service = RecommendationTrackingService()
        result = service.close_record(record_id, req.close_price)
        if not result:
            raise HTTPException(status_code=404, detail="记录不存在")
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("平仓失败")
        raise HTTPException(status_code=500, detail=str(exc))


# ── 更新价格 ────────────────────────────────────────────────────────────────


@router.post("/records/{record_id}/price", response_model=RecommendationRecordSchema)
async def update_price(record_id: int, req: UpdatePriceRequest) -> Dict[str, Any]:
    """更新当前价格并重新计算偏差."""
    try:
        service = RecommendationTrackingService()
        result = service.update_current_price(record_id, req.current_price)
        if not result:
            raise HTTPException(status_code=404, detail="记录不存在")
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── 统计 ────────────────────────────────────────────────────────────────────


@router.get("/stats", response_model=RecommendationStatsResponse)
async def get_stats(
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
) -> Dict[str, Any]:
    """获取推荐胜率与偏差统计数据."""
    try:
        service = RecommendationTrackingService()
        return service.get_stats(start_date=start_date, end_date=end_date)
    except Exception as exc:
        logger.exception("查询统计数据失败")
        raise HTTPException(status_code=500, detail=str(exc))


# ── 自省总结 ────────────────────────────────────────────────────────────────


@router.post("/summary", response_model=SummaryResponse)
async def generate_summary(req: SummaryRequest = SummaryRequest()) -> Dict[str, Any]:
    """基于历史数据生成推荐策略的自省总结与优化建议."""
    try:
        service = RecommendationTrackingService()
        return service.generate_summary(
            start_date=req.start_date,
            end_date=req.end_date,
        )
    except Exception as exc:
        logger.exception("生成自省总结失败")
        raise HTTPException(status_code=500, detail=str(exc))


# ── 共同点分析 ────────────────────────────────────────────────────────────────


@router.get("/commonality", response_model=CommonalityResponse)
async def get_commonality(
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    tag_filter: Optional[str] = Query(None, description="按标签过滤 (key:value 格式)"),
) -> Dict[str, Any]:
    """分析推荐记录之间的共同特征与关联性.

    从板块归属、信号方向、来源、价格区间、时间窗口、理由关键词
    等多个维度挖掘推荐股票间的共同点，以标签形式展示。
    """
    try:
        service = RecommendationTrackingService()
        return service.get_commonality(
            start_date=start_date,
            end_date=end_date,
            tag_filter=tag_filter,
        )
    except Exception as exc:
        logger.exception("共同点分析失败")
        raise HTTPException(status_code=500, detail=str(exc))
