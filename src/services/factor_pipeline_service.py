# -*- coding: utf-8 -*-
"""Factor pipeline service for Phase 2."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Sequence

from src.config import get_config
from src.repositories.screening_repo import ScreeningRepository
from src.services.factor_pipeline_adapters import FactorBackendAdapter
from src.services.factor_pipeline_schema import (
    FactorPipelineCandidatePayload,
    FactorPipelineFactorFamilyPayload,
    FactorPipelineFactorFamilySpec,
    FactorPipelineInterpretationFeature,
    FactorPipelineInterpretationPayload,
    FactorPipelineMonitoringPayload,
    FactorPipelineSnapshotPayload,
    FactorPipelineSummaryPayload,
    FactorPipelineTraceItem,
    FactorPipelineTracesPayload,
    FactorPipelineTrainingPayload,
)
from src.storage import DatabaseManager, ScreeningCandidate, ScreeningRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FactorSeriesSpec:
    name: str
    window: int
    provider: str = "qlib"


@dataclass(frozen=True)
class FactorPipelineConfig:
    enabled: bool
    alpha_158: Sequence[FactorSeriesSpec] = field(default_factory=tuple)
    alpha_360: Sequence[FactorSeriesSpec] = field(default_factory=tuple)
    lgbm_enabled: bool = False
    shap_enabled: bool = False
    ic_ir_monitoring_enabled: bool = False
    backend: str = "skeleton"


class FactorPipelineService:
    """Opt-in multi-factor screening pipeline."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()
        self.repo = ScreeningRepository(self.db)
        self.adapter = FactorBackendAdapter()

    def get_config(self) -> FactorPipelineConfig:
        config = get_config()
        enabled = bool(getattr(config, "factor_pipeline_enabled", False))
        return FactorPipelineConfig(
            enabled=enabled,
            alpha_158=(
                FactorSeriesSpec(name="alpha158_1", window=1, provider="qlib"),
                FactorSeriesSpec(name="alpha158_5", window=5, provider="qlib"),
                FactorSeriesSpec(name="alpha158_10", window=10, provider="qlib"),
            ),
            alpha_360=(
                FactorSeriesSpec(name="alpha360_20", window=20, provider="qlib"),
                FactorSeriesSpec(name="alpha360_60", window=60, provider="qlib"),
            ),
            lgbm_enabled=enabled,
            shap_enabled=enabled,
            ic_ir_monitoring_enabled=enabled,
            backend=self.adapter.backend,
        )

    def get_runtime_window(self) -> Dict[str, int]:
        config = get_config()
        return {
            "train_days": int(getattr(config, "factor_pipeline_train_days", 730)),
            "valid_days": int(getattr(config, "factor_pipeline_valid_days", 90)),
            "test_days": int(getattr(config, "factor_pipeline_test_days", 90)),
            "shap_sample_size": int(getattr(config, "factor_pipeline_shap_sample_size", 128)),
        }

    def run_for_screening_record(
        self,
        record_id: int,
        *,
        market: Optional[str] = None,
        screening_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        config = self.get_config()
        runtime_window = self.get_runtime_window()
        if not config.enabled:
            return {
                "status": "disabled",
                "record_id": record_id,
                "factor_pipeline_enabled": False,
                "backend": config.backend,
            }

        record = self.repo.get_record_by_id(record_id)
        if record is None:
            raise ValueError(f"screening record {record_id} not found")

        snapshot = self._build_summary_payload(record, market=market, screening_date=screening_date, config=config, runtime_window=runtime_window)
        logger.info("Factor pipeline completed: %s", json.dumps(snapshot.to_dict(), ensure_ascii=False, default=str))
        return snapshot.to_dict()

    def get_screening_record_factor_pipeline(self, record_id: int) -> Dict[str, Any]:
        record = self.repo.get_record_by_id(record_id)
        if record is None:
            raise ValueError(f"screening record {record_id} not found")

        candidates = self.repo.get_candidates_by_record_id(record_id)
        raw_candidates = [self._parse_factor_payload(candidate) for candidate in candidates]
        runtime_window = self.get_runtime_window()
        factor_family = self._build_factor_family_payload(self.get_config())
        monitoring = self._build_monitoring_metrics(raw_candidates)
        training = self._build_training_summary(raw_candidates, self.get_config())
        top_candidates = [self._payload_candidate_from_dict(c) for c in raw_candidates[:5]]
        traces = self._build_pipeline_traces(
            raw_candidates, runtime_window
        ) if raw_candidates else FactorPipelineTracesPayload(
            backend=self.get_config().backend,
            runtime_window=runtime_window,
        )
        snapshot = FactorPipelineSnapshotPayload(
            status="completed" if raw_candidates else "empty",
            record_id=record_id,
            factor_pipeline_enabled=bool(getattr(get_config(), "factor_pipeline_enabled", False)),
            backend=self.get_config().backend,
            training=training,
            monitoring=monitoring,
            candidate_count=len(raw_candidates),
            top_candidates=top_candidates,
            latest_record_id=record.id,
            latest_strategy=record.strategy,
            latest_screening_date=record.screening_date.isoformat() if record.screening_date else None,
            factor_family=factor_family,
            traces=traces,
        )
        return snapshot.to_dict()

    def get_latest_task_factor_pipeline(self, stock_code: str) -> Optional[Dict[str, Any]]:
        records = self.repo.list_records(strategy=None, market=None, limit=20, offset=0)[0]
        latest_record = None
        for record in records:
            if not record.candidate_count:
                continue
            if record.status != "completed":
                continue
            if any(candidate.code == stock_code for candidate in self.repo.get_candidates_by_record_id(record.id)):
                latest_record = record
                break

        if latest_record is None:
            return None

        overview = self.get_screening_record_factor_pipeline(latest_record.id)
        candidates = overview.get("candidates") or []
        top_candidates = [candidate for candidate in candidates if candidate.get("code") == stock_code]
        snapshot = FactorPipelineSnapshotPayload(
            status=overview.get("status", "unknown"),
            record_id=latest_record.id,
            factor_pipeline_enabled=overview.get("factor_pipeline_enabled", False),
            backend=overview.get("backend"),
            training=self._payload_training_from_dict(overview.get("training")),
            monitoring=self._payload_monitoring_from_dict(overview.get("monitoring")),
            candidate_count=len(candidates),
            top_candidates=[self._payload_candidate_from_dict(candidate) for candidate in top_candidates[:5]],
            latest_record_id=latest_record.id,
            latest_strategy=latest_record.strategy,
            latest_screening_date=latest_record.screening_date.isoformat() if latest_record.screening_date else None,
            factor_family=self._payload_factor_family_from_dict(overview.get("factor_family")),
        )
        return snapshot.to_dict()

    def _build_candidate_factor_payload(
        self,
        record: ScreeningRecord,
        candidate: ScreeningCandidate,
        config: FactorPipelineConfig,
        runtime_window: Dict[str, int],
    ) -> FactorPipelineCandidatePayload:
        factor_specs = [spec.__dict__ for spec in (*config.alpha_158, *config.alpha_360)]
        backend_payload = self.adapter.build_factor_rows(
            screening_date=record.screening_date,
            strategy=record.strategy,
            candidate_code=candidate.code,
            candidate_rank=candidate.rank,
            factor_specs=factor_specs,
            train_days=runtime_window["train_days"],
            valid_days=runtime_window["valid_days"],
            test_days=runtime_window["test_days"],
            shap_sample_size=runtime_window["shap_sample_size"],
            instruments=str(getattr(get_config(), "factor_pipeline_instruments", "csi300") or "csi300"),
            region=str(getattr(get_config(), "factor_qlib_region", "cn") or "cn"),
        )
        factor_scores = backend_payload.get("factor_scores") or {}
        factor_score = float(backend_payload.get("factor_score") or 0.0)
        model = backend_payload.get("model_artifacts") or {}
        training = self._payload_training_from_dict(backend_payload.get("training_summary"))
        monitoring = self._payload_monitoring_from_dict(backend_payload.get("monitoring_summary"))
        traces = self._payload_trace_item_from_dict(candidate.code, backend_payload.get("traces"), backend_payload.get("backend"), runtime_window)
        interpretation = self._payload_interpretation_from_dict(backend_payload.get("interpretation"), factor_scores, factor_score, model)
        payload = FactorPipelineCandidatePayload(
            candidate_id=candidate.id,
            code=candidate.code,
            name=candidate.name,
            rank=candidate.rank,
            base_score=candidate.score,
            backend=backend_payload.get("backend"),
            factor_scores={str(key): float(value) for key, value in factor_scores.items()},
            factor_score=factor_score,
            model=model,
            training=training,
            monitoring=monitoring,
            runtime_window=runtime_window,
            traces=traces,
            interpretation=interpretation,
        )
        self._persist_factor_payload(candidate.id, payload.to_dict())
        return payload

    def _build_summary_payload(
        self,
        record: ScreeningRecord,
        *,
        market: Optional[str],
        screening_date: Optional[date],
        config: FactorPipelineConfig,
        runtime_window: Dict[str, int],
    ) -> FactorPipelineSummaryPayload:
        candidates = self.repo.get_candidates_by_record_id(record.id)
        factor_results = [self._build_candidate_factor_payload(record, candidate, config, runtime_window) for candidate in candidates]
        monitoring = self._build_monitoring_metrics([candidate.to_dict() for candidate in factor_results])
        training = self._build_training_summary([candidate.to_dict() for candidate in factor_results], config)
        traces = self._build_pipeline_traces([candidate.to_dict() for candidate in factor_results], runtime_window)
        return FactorPipelineSummaryPayload(
            status="completed",
            record_id=record.id,
            screening_date=(screening_date or record.screening_date).isoformat() if (screening_date or record.screening_date) else None,
            market=market or record.market,
            factor_pipeline_enabled=True,
            backend=config.backend,
            factor_family=self._build_factor_family_payload(config),
            training=training,
            runtime_window=runtime_window,
            monitoring=monitoring,
            traces=traces,
            candidates=factor_results,
        )

    def _build_factor_family_payload(self, config: FactorPipelineConfig) -> FactorPipelineFactorFamilyPayload:
        return FactorPipelineFactorFamilyPayload(
            alpha158=[FactorPipelineFactorFamilySpec(**spec.__dict__) for spec in config.alpha_158],
            alpha360=[FactorPipelineFactorFamilySpec(**spec.__dict__) for spec in config.alpha_360],
        )

    def _build_interpretation_from_dict(
        self,
        interpretation: Optional[Dict[str, Any]],
        factors: Dict[str, Any],
        score: float,
        model: Dict[str, Any],
    ) -> FactorPipelineInterpretationPayload:
        if interpretation:
            top_features = [FactorPipelineInterpretationFeature(name=str(item.get("name") or ""), impact=float(item.get("impact") or 0.0)) for item in interpretation.get("top_features") or []]
            return FactorPipelineInterpretationPayload(
                shap_enabled=bool(interpretation.get("shap_enabled")),
                top_features=top_features,
                score=float(interpretation.get("score") or score),
            )
        top_features = sorted((factors or {}).items(), key=lambda item: abs(item[1]), reverse=True)[:3]
        shap_values = (model or {}).get("shap_values") or {}
        return FactorPipelineInterpretationPayload(
            shap_enabled=bool(shap_values),
            top_features=[FactorPipelineInterpretationFeature(name=str(name), impact=float(value)) for name, value in top_features],
            score=score,
        )

    def _payload_training_from_dict(self, training: Optional[Dict[str, Any]]) -> FactorPipelineTrainingPayload:
        training = training or {}
        return FactorPipelineTrainingPayload(
            algorithm=str(training.get("algorithm") or "LightGBM"),
            rolling=bool(training.get("rolling", True)),
            enabled=bool(training.get("enabled", False)),
            shap_enabled=bool(training.get("shap_enabled", False)),
            ic_ir_monitoring_enabled=bool(training.get("ic_ir_monitoring_enabled", False)),
            sample_size=int(training.get("sample_size") or 0),
            status=str(training.get("status") or "skeleton"),
            backend=str(training.get("backend") or self.adapter.backend),
        )

    def _payload_monitoring_from_dict(self, monitoring: Optional[Dict[str, Any]]) -> FactorPipelineMonitoringPayload:
        monitoring = monitoring or {}
        return FactorPipelineMonitoringPayload(
            ic=self._safe_float(monitoring.get("ic")),
            ir=self._safe_float(monitoring.get("ir")),
            decay=self._safe_float(monitoring.get("decay")),
            decay_alert=bool(monitoring.get("decay_alert", False)),
            sample_size=int(monitoring.get("sample_size") or 0),
            backend=str(monitoring.get("backend") or self.adapter.backend),
        )

    def _payload_trace_item_from_dict(self, code: str, traces: Optional[Dict[str, Any]], backend: Optional[str], runtime_window: Dict[str, int]) -> FactorPipelineTraceItem:
        traces = traces or {}
        return FactorPipelineTraceItem(
            code=code,
            backend=backend,
            train_window_days=int(traces.get("train_window_days") or runtime_window.get("train_days") or 0),
            valid_window_days=int(traces.get("valid_window_days") or runtime_window.get("valid_days") or 0),
            test_window_days=int(traces.get("test_window_days") or runtime_window.get("test_days") or 0),
            shap_sample_size=int(traces.get("shap_sample_size") or runtime_window.get("shap_sample_size") or 0),
            backend_error=traces.get("backend_error"),
        )

    def _payload_factor_family_from_dict(self, factor_family: Optional[Dict[str, Any]]) -> Optional[FactorPipelineFactorFamilyPayload]:
        if factor_family is None:
            return None
        return FactorPipelineFactorFamilyPayload(
            alpha158=[FactorPipelineFactorFamilySpec(**item) for item in factor_family.get("alpha158") or []],
            alpha360=[FactorPipelineFactorFamilySpec(**item) for item in factor_family.get("alpha360") or []],
        )

    def _payload_candidate_from_dict(self, candidate: Dict[str, Any]) -> FactorPipelineCandidatePayload:
        training = self._payload_training_from_dict(candidate.get("training"))
        monitoring = self._payload_monitoring_from_dict(candidate.get("monitoring"))
        traces = self._payload_trace_item_from_dict(str(candidate.get("code") or ""), candidate.get("traces"), candidate.get("backend"), candidate.get("runtime_window") or self.get_runtime_window())
        interpretation = self._build_interpretation_from_dict(candidate.get("interpretation"), candidate.get("factor_scores") or {}, float(candidate.get("factor_score") or 0.0), candidate.get("model") or {})
        return FactorPipelineCandidatePayload(
            candidate_id=int(candidate.get("candidate_id") or 0),
            code=str(candidate.get("code") or ""),
            name=candidate.get("name"),
            rank=int(candidate.get("rank") or 0),
            base_score=self._safe_float(candidate.get("base_score")),
            backend=candidate.get("backend"),
            factor_scores={str(key): float(value) for key, value in (candidate.get("factor_scores") or {}).items()},
            factor_score=float(candidate.get("factor_score") or 0.0),
            model=candidate.get("model") or {},
            training=training,
            monitoring=monitoring,
            runtime_window=candidate.get("runtime_window") or self.get_runtime_window(),
            traces=traces,
            interpretation=interpretation,
        )

    def _build_pipeline_traces(self, candidates: Iterable[Dict[str, Any]], runtime_window: Dict[str, int]) -> FactorPipelineTracesPayload:
        candidates = list(candidates)
        backends = sorted({str(item.get("backend") or "unknown") for item in candidates})
        trace_items = []
        for item in candidates[:10]:
            traces = item.get("traces") or {}
            trace_items.append(FactorPipelineTraceItem(
                code=str(item.get("code") or ""),
                backend=item.get("backend"),
                train_window_days=self._safe_int(traces.get("train_window_days") or runtime_window.get("train_days")),
                valid_window_days=self._safe_int(traces.get("valid_window_days") or runtime_window.get("valid_days")),
                test_window_days=self._safe_int(traces.get("test_window_days") or runtime_window.get("test_days")),
                shap_sample_size=self._safe_int(traces.get("shap_sample_size") or runtime_window.get("shap_sample_size")),
                backend_error=traces.get("backend_error"),
            ))
        return FactorPipelineTracesPayload(
            backend=self.adapter.backend,
            runtime_window=runtime_window,
            candidate_traces=trace_items,
            backends_seen=backends,
        )

    def _build_monitoring_metrics(self, candidates: Iterable[Dict[str, Any]]) -> FactorPipelineMonitoringPayload:
        candidates = list(candidates)
        if not candidates:
            return FactorPipelineMonitoringPayload(ic=None, ir=None, decay=None, decay_alert=False, sample_size=0, backend=self.adapter.backend)
        monitoring = [item.get("monitoring") or {} for item in candidates]
        ic_values = [item.get("ic") for item in monitoring if item.get("ic") is not None]
        ir_values = [item.get("ir") for item in monitoring if item.get("ir") is not None]
        decay_values = [item.get("decay") for item in monitoring if item.get("decay") is not None]
        return FactorPipelineMonitoringPayload(
            ic=round(sum(ic_values) / len(ic_values), 4) if ic_values else None,
            ir=round(sum(ir_values) / len(ir_values), 4) if ir_values else None,
            decay=round(sum(decay_values) / len(decay_values), 4) if decay_values else None,
            decay_alert=bool(decay_values and min(decay_values) < 0.2),
            sample_size=len(candidates),
            backend=self.adapter.backend,
        )

    def _build_training_summary(self, candidates: Iterable[Dict[str, Any]], config: FactorPipelineConfig) -> FactorPipelineTrainingPayload:
        candidates = list(candidates)
        return FactorPipelineTrainingPayload(
            algorithm="LightGBM",
            rolling=True,
            enabled=config.lgbm_enabled,
            shap_enabled=config.shap_enabled,
            ic_ir_monitoring_enabled=config.ic_ir_monitoring_enabled,
            sample_size=len(candidates),
            status="real" if config.backend == "real" else "skeleton",
            backend=config.backend,
        )

    def _persist_factor_payload(self, candidate_id: int, payload: Dict[str, Any]) -> None:
        with self.db.get_session() as session:
            candidate = session.get(ScreeningCandidate, candidate_id)
            if candidate is None:
                return
            candidate.factor_scores_json = json.dumps(payload, ensure_ascii=False, default=str)
            session.commit()

    def _parse_factor_payload(self, candidate: ScreeningCandidate) -> Dict[str, Any]:
        try:
            payload = json.loads(candidate.factor_scores_json) if candidate.factor_scores_json else {}
        except (TypeError, json.JSONDecodeError):
            payload = {}
        if not payload:
            payload = {
                "candidate_id": candidate.id,
                "code": candidate.code,
                "name": candidate.name,
                "rank": candidate.rank,
                "base_score": candidate.score,
                "factor_scores": {},
                "factor_score": candidate.score,
                "model": self._build_model_summary(self.get_config()),
                "interpretation": {"shap_enabled": False, "top_features": [], "score": candidate.score or 0.0},
                "monitoring": {"ic": None, "ir": None, "decay": None},
            }
        return payload

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None


__all__ = ["FactorPipelineService", "FactorPipelineConfig", "FactorSeriesSpec"]
