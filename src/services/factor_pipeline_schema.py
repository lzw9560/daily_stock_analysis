# -*- coding: utf-8 -*-
"""Typed payload schema for factor pipeline outputs."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class FactorPipelineFactorFamilySpec:
    name: str
    window: int
    provider: str = "qlib"


@dataclass(frozen=True)
class FactorPipelineFactorFamilyPayload:
    alpha158: List[FactorPipelineFactorFamilySpec] = field(default_factory=list)
    alpha360: List[FactorPipelineFactorFamilySpec] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alpha158": [asdict(item) for item in self.alpha158],
            "alpha360": [asdict(item) for item in self.alpha360],
        }


@dataclass(frozen=True)
class FactorPipelineTrainingPayload:
    algorithm: str
    rolling: bool
    enabled: bool
    shap_enabled: bool
    ic_ir_monitoring_enabled: bool
    sample_size: int
    status: str
    backend: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FactorPipelineMonitoringPayload:
    ic: Optional[float]
    ir: Optional[float]
    decay: Optional[float]
    decay_alert: bool
    sample_size: int
    backend: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FactorPipelineInterpretationFeature:
    name: str
    impact: float


@dataclass(frozen=True)
class FactorPipelineInterpretationPayload:
    shap_enabled: bool
    top_features: List[FactorPipelineInterpretationFeature] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shap_enabled": self.shap_enabled,
            "top_features": [asdict(item) for item in self.top_features],
            "score": self.score,
        }


@dataclass(frozen=True)
class FactorPipelineTraceItem:
    code: Optional[str]
    backend: Optional[str]
    train_window_days: Optional[int]
    valid_window_days: Optional[int]
    test_window_days: Optional[int]
    shap_sample_size: Optional[int]
    backend_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FactorPipelineTracesPayload:
    backend: str
    runtime_window: Dict[str, int]
    candidate_traces: List[FactorPipelineTraceItem] = field(default_factory=list)
    backends_seen: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "runtime_window": dict(self.runtime_window),
            "candidate_traces": [item.to_dict() for item in self.candidate_traces],
            "backends_seen": list(self.backends_seen),
        }


@dataclass(frozen=True)
class FactorPipelineCandidatePayload:
    candidate_id: int
    code: str
    name: Optional[str]
    rank: int
    base_score: Optional[float]
    backend: Optional[str]
    factor_scores: Dict[str, float]
    factor_score: float
    model: Dict[str, Any]
    training: FactorPipelineTrainingPayload
    monitoring: FactorPipelineMonitoringPayload
    runtime_window: Dict[str, int]
    traces: FactorPipelineTraceItem
    interpretation: FactorPipelineInterpretationPayload

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "code": self.code,
            "name": self.name,
            "rank": self.rank,
            "base_score": self.base_score,
            "backend": self.backend,
            "factor_scores": dict(self.factor_scores),
            "factor_score": self.factor_score,
            "model": dict(self.model),
            "training": self.training.to_dict(),
            "monitoring": self.monitoring.to_dict(),
            "runtime_window": dict(self.runtime_window),
            "traces": self.traces.to_dict(),
            "interpretation": self.interpretation.to_dict(),
        }


@dataclass(frozen=True)
class FactorPipelineSummaryPayload:
    status: str
    record_id: int
    screening_date: Optional[str]
    market: Optional[str]
    factor_pipeline_enabled: bool
    backend: str
    factor_family: FactorPipelineFactorFamilyPayload
    training: FactorPipelineTrainingPayload
    runtime_window: Dict[str, int]
    monitoring: FactorPipelineMonitoringPayload
    traces: FactorPipelineTracesPayload
    candidates: List[FactorPipelineCandidatePayload]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "record_id": self.record_id,
            "screening_date": self.screening_date,
            "market": self.market,
            "factor_pipeline_enabled": self.factor_pipeline_enabled,
            "backend": self.backend,
            "factor_family": self.factor_family.to_dict(),
            "training": self.training.to_dict(),
            "runtime_window": dict(self.runtime_window),
            "monitoring": self.monitoring.to_dict(),
            "traces": self.traces.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


@dataclass(frozen=True)
class FactorPipelineSnapshotPayload:
    status: str
    record_id: int
    factor_pipeline_enabled: bool
    backend: Optional[str]
    training: Optional[FactorPipelineTrainingPayload]
    monitoring: Optional[FactorPipelineMonitoringPayload]
    candidate_count: int
    top_candidates: List[FactorPipelineCandidatePayload]
    latest_record_id: int
    latest_strategy: Optional[str]
    latest_screening_date: Optional[str]
    factor_family: Optional[FactorPipelineFactorFamilyPayload] = None
    traces: Optional[FactorPipelineTracesPayload] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "record_id": self.record_id,
            "factor_pipeline_enabled": self.factor_pipeline_enabled,
            "backend": self.backend,
            "training": self.training.to_dict() if self.training else None,
            "monitoring": self.monitoring.to_dict() if self.monitoring else None,
            "candidate_count": self.candidate_count,
            "top_candidates": [candidate.to_dict() for candidate in self.top_candidates],
            "latest_record_id": self.latest_record_id,
            "latest_strategy": self.latest_strategy,
            "latest_screening_date": self.latest_screening_date,
            "factor_family": self.factor_family.to_dict() if self.factor_family else None,
            "traces": self.traces.to_dict() if self.traces else None,
        }
