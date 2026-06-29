# -*- coding: utf-8 -*-
"""Screening API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScreeningRunRequest(BaseModel):
    strategies: Optional[List[str]] = Field(
        default=None, min_length=1, max_length=20,
        description="策略列表，留空则使用 SCREENING_STRATEGIES 配置",
    )
    market: str = Field(default="cn", min_length=1, max_length=16)
    max_results: int = Field(default=20, ge=1, le=100)
    auto_backtest: bool = Field(default=True)
    notify_feishu: bool = Field(default=False, description="是否发送飞书通知")


class ScreeningRunResponse(BaseModel):
    screening_date: str
    total_strategies: int
    completed_strategies: int
    failed_strategies: int
    total_candidates: int
    unique_codes: int
    strategies: List[Dict[str, Any]]
    auto_backtest: Optional[Dict[str, Any]] = None
    factor_pipeline: Optional[Dict[str, Any]] = None


class ScreeningRecordListItem(BaseModel):
    id: int
    screening_date: Optional[str] = None
    strategy: str
    market: str
    candidate_count: int
    status: str
    duration_seconds: Optional[float] = None
    run_id: Optional[str] = None
    factor_pipeline: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


class ScreeningRecordListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    records: List[ScreeningRecordListItem] = Field(default_factory=list)


class FactorPipelineTriggerRequest(BaseModel):
    record_id: int = Field(..., ge=1, description="选股记录 ID")
    market: Optional[str] = Field(default=None, min_length=1, max_length=16)
    screening_date: Optional[str] = Field(default=None, description="筛选日期 ISO 格式 YYYY-MM-DD")


class FactorPipelineCandidateTrace(BaseModel):
    code: Optional[str] = None
    backend: Optional[str] = None
    train_window_days: Optional[int] = None
    valid_window_days: Optional[int] = None
    test_window_days: Optional[int] = None
    shap_sample_size: Optional[int] = None
    backend_error: Optional[str] = None


class FactorPipelineTraces(BaseModel):
    backend: Optional[str] = None
    runtime_window: Dict[str, int] = Field(default_factory=dict)
    candidate_traces: List[FactorPipelineCandidateTrace] = Field(default_factory=list)
    backends_seen: List[str] = Field(default_factory=list)


class FactorPipelineInterpretationFeature(BaseModel):
    name: str
    impact: float


class FactorPipelineInterpretation(BaseModel):
    shap_enabled: bool = False
    top_features: List[FactorPipelineInterpretationFeature] = Field(default_factory=list)
    score: float = 0.0


class FactorPipelineCandidate(BaseModel):
    candidate_id: int
    code: str
    name: Optional[str] = None
    rank: int
    base_score: Optional[float] = None
    backend: Optional[str] = None
    factor_scores: Dict[str, float] = Field(default_factory=dict)
    factor_score: float
    model: Dict[str, Any] = Field(default_factory=dict)
    training: Dict[str, Any] = Field(default_factory=dict)
    monitoring: Dict[str, Any] = Field(default_factory=dict)
    runtime_window: Dict[str, int] = Field(default_factory=dict)
    traces: Dict[str, Any] = Field(default_factory=dict)
    interpretation: FactorPipelineInterpretation


class FactorPipelineFactorFamilySpec(BaseModel):
    name: str
    window: int
    provider: str = "qlib"


class FactorPipelineFactorFamily(BaseModel):
    alpha158: List[FactorPipelineFactorFamilySpec] = Field(default_factory=list)
    alpha360: List[FactorPipelineFactorFamilySpec] = Field(default_factory=list)


class FactorPipelineTraining(BaseModel):
    algorithm: str
    rolling: bool
    enabled: bool
    shap_enabled: bool
    ic_ir_monitoring_enabled: bool
    sample_size: int
    status: str
    backend: str


class FactorPipelineMonitoring(BaseModel):
    ic: Optional[float] = None
    ir: Optional[float] = None
    decay: Optional[float] = None
    decay_alert: bool = False
    sample_size: int = 0
    backend: str


class FactorPipelineSummaryPayload(BaseModel):
    status: str
    record_id: int
    screening_date: Optional[str] = None
    market: Optional[str] = None
    factor_pipeline_enabled: bool
    backend: str
    factor_family: FactorPipelineFactorFamily
    training: FactorPipelineTraining
    runtime_window: Dict[str, int] = Field(default_factory=dict)
    monitoring: FactorPipelineMonitoring
    traces: Optional[FactorPipelineTraces] = None
    candidates: List[FactorPipelineCandidate] = Field(default_factory=list)


class FactorPipelineTriggerResponse(BaseModel):
    status: str
    record_id: int
    factor_pipeline_enabled: bool
    screening_date: Optional[str] = None
    market: Optional[str] = None
    backend: Optional[str] = None
    factor_family: Optional[FactorPipelineFactorFamily] = None
    training: Optional[FactorPipelineTraining] = None
    monitoring: Optional[FactorPipelineMonitoring] = None
    traces: Optional[FactorPipelineTraces] = None
    candidates: Optional[List[FactorPipelineCandidate]] = None
    error: Optional[str] = None


class FactorPipelineRecordResponse(BaseModel):
    record_id: int
    factor_pipeline: FactorPipelineSummaryPayload
