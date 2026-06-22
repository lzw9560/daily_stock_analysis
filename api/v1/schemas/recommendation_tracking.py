# -*- coding: utf-8 -*-
"""历史推荐追踪 API Schema — 请求/响应模型."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


# ── 请求模型 ────────────────────────────────────────────────────────────────


class CreateRecommendationRequest(BaseModel):
    """创建推荐记录请求."""
    code: str = Field(..., description="股票代码", examples=["000001"])
    trade_date: str = Field(..., description="交易日期 (YYYY-MM-DD)", examples=["2026-06-13"])
    recommendation_price: float = Field(..., description="推荐价格", examples=[12.50])
    signal: str = Field(default="buy", description="推荐方向: buy/sell/hold")
    source: str = Field(default="analysis", description="来源: analysis/deep_analysis/seal_plate/comprehensive/manual")
    source_task_id: Optional[str] = Field(None, description="来源任务ID")
    reason: Optional[str] = Field(None, description="推荐理由")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "code": "000001",
            "trade_date": "2026-06-13",
            "recommendation_price": 12.50,
            "signal": "buy",
            "source": "deep_analysis",
            "source_task_id": "abc123def456",
            "reason": "多维度分析看多信号，技术面+基本面共振"
        }
    })


class UpdateRecordRequest(BaseModel):
    """更新推荐记录请求（部分更新）."""
    code: Optional[str] = None
    trade_date: Optional[str] = None
    signal: Optional[str] = None
    recommendation_price: Optional[float] = None
    current_price: Optional[float] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None


class CloseRecordRequest(BaseModel):
    """平仓请求."""
    close_price: float = Field(..., description="平仓价格")

    model_config = ConfigDict(json_schema_extra={
        "example": {"close_price": 13.80}
    })


class UpdatePriceRequest(BaseModel):
    """更新当前价格请求."""
    current_price: float = Field(..., description="当前价格")

    model_config = ConfigDict(json_schema_extra={
        "example": {"current_price": 13.15}
    })


class SummaryRequest(BaseModel):
    """生成自省总结请求."""
    start_date: Optional[str] = Field(None, description="开始日期 (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="结束日期 (YYYY-MM-DD)")

    model_config = ConfigDict(json_schema_extra={
        "example": {"start_date": "2026-05-01", "end_date": "2026-06-13"}
    })


# ── 响应模型 ────────────────────────────────────────────────────────────────


class RecommendationRecordSchema(BaseModel):
    """推荐记录响应."""
    id: int
    code: str
    trade_date: str
    recommendation_time: str
    signal: str
    recommendation_price: float
    current_price: Optional[float]
    price_deviation_pct: Optional[float]
    status: str
    close_price: Optional[float]
    close_date: Optional[str]
    profit_loss_pct: Optional[float]
    source: str
    source_task_id: Optional[str]
    reason: str
    notes: str
    created_at: str
    updated_at: str


class RecommendationListResponse(BaseModel):
    """推荐记录列表响应."""
    total: int
    page: int
    limit: int
    items: List[RecommendationRecordSchema]


class SignalStat(BaseModel):
    """按方向的分项统计."""
    total: int
    wins: int
    win_rate: float
    avg_pl_pct: float


class SourceStat(BaseModel):
    """按来源的分项统计."""
    total: int
    wins: int
    win_rate: float
    avg_pl_pct: float


class ActiveDeviationItem(BaseModel):
    """活跃持仓偏差项."""
    id: int
    code: str
    trade_date: str
    signal: str
    recommendation_price: float
    current_price: float
    deviation_pct: float


class RecommendationStatsResponse(BaseModel):
    """推荐胜率与偏差统计响应."""
    total_records: int
    active_count: int
    closed_count: int
    win_rate: float
    win_count: int
    loss_count: int
    avg_pl_pct: float
    avg_win_pl_pct: float
    avg_loss_pl_pct: float
    max_win_pct: float
    max_loss_pct: float
    profit_factor: float
    total_pl_pct: float
    by_signal: Dict[str, SignalStat] = {}
    by_source: Dict[str, SourceStat] = {}
    active_deviation: List[ActiveDeviationItem] = []


class SummaryResponse(BaseModel):
    """自省总结响应."""
    stats: RecommendationStatsResponse
    summary: str
