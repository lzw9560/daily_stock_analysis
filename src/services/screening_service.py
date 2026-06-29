# -*- coding: utf-8 -*-
"""Multi-strategy screening service with auto-backtest."""

from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from src.config import get_config
from src.services.factor_pipeline_service import FactorPipelineService
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
from src.services.screening_payloads import ScreeningCandidateBatchPayload, ScreeningCandidatePayload
from src.repositories.screening_repo import ScreeningRepository
from src.services.screening_payloads import ScreeningCandidateBatchPayload, ScreeningCandidatePayload
from src.storage import DatabaseManager, ScreeningRecord

logger = logging.getLogger(__name__)


class ScreeningService:
    """Orchestrates multi-strategy screening, persistence, and auto-backtest."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()
        self.repo = ScreeningRepository(self.db)
        self.factor_pipeline = FactorPipelineService(self.db)

    # ---- Public API ----

    def get_configured_strategies(self) -> List[str]:
        """Parse SCREENING_STRATEGIES into a list."""
        config = get_config()
        raw = getattr(config, "screening_strategies", "") or ""
        strategies = [s.strip() for s in raw.split(",") if s.strip()]
        if not strategies:
            # Fallback to a default list if config is empty
            strategies = ["dual_low", "growth_at_reasonable_price", "momentum_breakout"]
        return strategies

    def run_daily_screening(
        self,
        strategies: Optional[List[str]] = None,
        market: Optional[str] = None,
        max_results: Optional[int] = None,
        auto_backtest: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Execute screening for all configured strategies and optionally backtest.

        Returns a summary dict with per-strategy results.
        """
        config = get_config()

        if strategies is None:
            strategies = self.get_configured_strategies()
        if market is None:
            market = getattr(config, "screening_market", "cn")
        if max_results is None:
            max_results = int(getattr(config, "screening_max_results", 20))
        if auto_backtest is None:
            auto_backtest = bool(getattr(config, "screening_auto_backtest", True))

        today = date.today()
        logger.info(
            "开始每日多策略选股 | date=%s | strategies=%s | market=%s",
            today, strategies, market,
        )

        results: List[Dict[str, Any]] = []
        all_candidate_codes: List[str] = []

        for strategy in strategies:
            try:
                self._last_start_time = time.time()
                strategy_result = self._run_single_strategy(
                    strategy=strategy,
                    market=market,
                    max_results=max_results,
                    screening_date=today,
                )
                results.append(strategy_result)

                if strategy_result.get("status") == "completed":
                    codes = strategy_result.get("candidate_codes", [])
                    all_candidate_codes.extend(codes)
            except Exception as exc:
                logger.exception("策略 %s 执行失败: %s", strategy, exc)
                duration = time.time() - self._last_start_time
                results.append({
                    "strategy": strategy,
                    "market": market,
                    "status": "failed",
                    "error": str(exc),
                    "record_id": None,
                    "candidate_count": 0,
                    "duration_seconds": round(duration, 2),
                })

        # Deduplicate codes for backtest
        unique_codes = list(dict.fromkeys(all_candidate_codes))

        backtest_result = None
        if auto_backtest and unique_codes:
            try:
                backtest_result = self._run_auto_backtest(
                    codes=unique_codes,
                    record_ids=[
                        r["record_id"] for r in results
                        if r.get("record_id") is not None
                    ],
                    screening_date=today,
                )
            except Exception as exc:
                logger.exception("自动回测执行失败: %s", exc)
                backtest_result = {"status": "failed", "error": str(exc)}

        summary = {
            "screening_date": today.isoformat(),
            "total_strategies": len(strategies),
            "completed_strategies": sum(
                1 for r in results if r.get("status") == "completed"
            ),
            "failed_strategies": sum(
                1 for r in results if r.get("status") == "failed"
            ),
            "total_candidates": sum(
                r.get("candidate_count", 0) for r in results
            ),
            "unique_codes": len(unique_codes),
            "strategies": results,
            "auto_backtest": backtest_result,
        }
        logger.info("每日选股完成: %s", json.dumps(summary, ensure_ascii=False, default=str))
        return summary

    def _run_single_strategy(
        self,
        strategy: str,
        market: str,
        max_results: int,
        screening_date: date,
    ) -> Dict[str, Any]:
        """Execute AlphaSift screen for one strategy and persist results."""
        start_time = time.time()
        log_capture: List[str] = []

        class LogCapture(logging.Handler):
            def emit(self, record):
                try:
                    msg = self.format(record)
                    log_capture.append(msg)
                except Exception:
                    pass

        capture_handler = LogCapture()
        capture_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(capture_handler)
        try:
            return self._execute_screening(strategy, market, max_results, screening_date, log_capture)
        finally:
            logger.removeHandler(capture_handler)

    def _execute_screening(
        self,
        strategy: str,
        market: str,
        max_results: int,
        screening_date: date,
        log_capture: List[str],
    ) -> Dict[str, Any]:
        """Core screening execution with log capture."""
        try:
            from src.shared.alphasift_core import (
                _get_dsa_adapter,
                _get_adapter_callable,
                _to_plain,
            )
        except ImportError as exc:
            raise RuntimeError(f"AlphaSift 模块不可用: {exc}") from exc

        from src.config import Config
        config = Config.get_instance()

        if not config.alphasift_enabled:
            raise RuntimeError("ALPHASIFT_ENABLED=false，选股功能未启用")

        adapter = _get_dsa_adapter()
        screen_fn = _get_adapter_callable(adapter, "screen", "screen() 不可调用。")

        try:
            from src.shared.alphasift_core import _call_alphasift_screen
            raw = _call_alphasift_screen(screen_fn, strategy, market, max_results)
        except Exception as exc:
            duration = time.time() - self._last_start_time
            self._save_failed_record(
                screening_date, strategy, market, str(exc), duration,
                logs="".join(log_capture)[-5000:],
            )
            raise

        raw_data = _to_plain(raw)
        if not isinstance(raw_data, dict):
            raw_data = {"candidates": raw_data}

        from src.shared.alphasift_core import _normalize_candidates
        candidates = _normalize_candidates(raw_data)
        selected = candidates[:max_results]

        duration = time.time() - self._last_start_time

        record = ScreeningRecord(
            screening_date=screening_date,
            strategy=strategy,
            market=market,
            candidate_count=len(selected),
            status="completed",
            duration_seconds=round(duration, 2),
            run_id=raw_data.get("run_id"),
            snapshot_count=raw_data.get("snapshot_count"),
            after_filter_count=raw_data.get("after_filter_count"),
            llm_ranked=raw_data.get("llm_ranked"),
            llm_market_view=raw_data.get("llm_market_view") or "",
            llm_selection_logic=raw_data.get("llm_selection_logic") or "",
            llm_portfolio_risk=raw_data.get("llm_portfolio_risk") or "",
            llm_coverage=json.dumps(raw_data.get("llm_coverage")) if raw_data.get("llm_coverage") else None,
            warnings_json=json.dumps(raw_data.get("warnings") or [], ensure_ascii=False),
            source_errors_json=json.dumps(raw_data.get("source_errors") or [], ensure_ascii=False),
            execution_logs="".join(log_capture)[-10000:] if log_capture else None,
        )

        record_id = self.repo.save_screening_record(record)
        self.repo.save_candidates_batch(self._build_candidate_batch_payload(record_id, selected))
        factor_pipeline_result = self._run_factor_pipeline_if_enabled(record_id, market=market, screening_date=screening_date)

        candidate_codes = [c.get("code", "") for c in selected if c.get("code")]

        logger.info(
            "策略 %s 完成 | record_id=%s | candidates=%d | duration=%.2fs",
            strategy, record_id, len(selected), duration,
        )

        return {
            "strategy": strategy,
            "market": market,
            "status": "completed",
            "record_id": record_id,
            "candidate_count": len(selected),
            "duration_seconds": round(duration, 2),
            "candidate_codes": candidate_codes,
            "llm_market_view": record.llm_market_view,
            "execution_logs": record.execution_logs or "",
            "factor_pipeline": factor_pipeline_result,
        }

    def _save_failed_record(
        self,
        screening_date: date,
        strategy: str,
        market: str,
        error: str,
        duration: float,
        logs: str = "",
    ) -> None:
        try:
            record = ScreeningRecord(
                screening_date=screening_date,
                strategy=strategy,
                market=market,
                candidate_count=0,
                status="failed",
                duration_seconds=round(duration, 2),
                error_message=error[:2000],
                execution_logs=logs[-10000:] if logs else None,
            )
            self.repo.save_screening_record(record)
        except Exception:
            logger.exception("保存失败记录时出错")


    def _build_candidate_batch_payload(self, record_id: int, candidates: List[Dict[str, Any]]) -> ScreeningCandidateBatchPayload:
        payloads: List[ScreeningCandidatePayload] = []
        for candidate in candidates:
            payloads.append(ScreeningCandidatePayload(
                rank=int(candidate.get("rank") or 0),
                code=str(candidate.get("code") or ""),
                name=str(candidate.get("name") or ""),
                score=self._safe_float(candidate.get("score")),
                screen_score=self._safe_float(candidate.get("screen_score")),
                llm_score=self._safe_float(candidate.get("llm_score")),
                llm_confidence=self._safe_float(candidate.get("llm_confidence")),
                reason=str(candidate.get("reason") or ""),
                risk_level=str(candidate.get("risk_level") or ""),
                risk_flags=list(candidate.get("risk_flags") or []),
                llm_sector=str(candidate.get("llm_sector") or ""),
                llm_theme=str(candidate.get("llm_theme") or ""),
                llm_tags=list(candidate.get("llm_tags") or []),
                llm_thesis=str(candidate.get("llm_thesis") or ""),
                llm_catalysts=list(candidate.get("llm_catalysts") or []),
                llm_risks=list(candidate.get("llm_risks") or []),
                llm_watch_items=list(candidate.get("llm_watch_items") or []),
                llm_invalidators=list(candidate.get("llm_invalidators") or []),
                llm_style_fit=str(candidate.get("llm_style_fit") or ""),
                price=self._safe_float(candidate.get("price")),
                change_pct=self._safe_float(candidate.get("change_pct")),
                amount=self._safe_float(candidate.get("amount")),
                industry=str(candidate.get("industry") or ""),
                factor_scores={str(key): float(value) for key, value in (candidate.get("factor_scores") or {}).items()},
                raw=dict(candidate.get("raw") or {}),
                factor_payload=candidate.get("factor_payload"),
            ))
        return ScreeningCandidateBatchPayload(record_id=record_id, candidates=payloads)

    def _run_factor_pipeline_if_enabled(
        self,
        record_id: int,
        *,
        market: str,
        screening_date: date,
    ) -> Dict[str, Any]:
        config = get_config()
        if not bool(getattr(config, "factor_pipeline_enabled", False)):
            return {"status": "disabled", "factor_pipeline_enabled": False}
        try:
            return self.factor_pipeline.run_for_screening_record(
                record_id,
                market=market,
                screening_date=screening_date,
            )
        except Exception as exc:
            logger.exception("因子流水线执行失败: %s", exc)
            return {"status": "failed", "error": str(exc), "factor_pipeline_enabled": True}

    def _run_auto_backtest(
        self,
        codes: List[str],
        record_ids: List[int],
        screening_date: date,
    ) -> Dict[str, Any]:
        """Run backtest on screening candidates and link results.

        After backtesting, queries BacktestResult for recent evaluations
        and creates ScreeningBacktestLink records.
        """
        config = get_config()
        eval_window_days = int(getattr(config, "screening_backtest_eval_window_days", 10))
        min_age_days = int(getattr(config, "screening_backtest_min_age_days", 1))

        from src.services.backtest_service import BacktestService
        bt_service = BacktestService(self.db)

        per_stock_results: List[Dict[str, Any]] = []
        total_linked = 0

        for code in codes:
            try:
                bt_result = bt_service.run_backtest(
                    code=code,
                    force=False,
                    eval_window_days=eval_window_days,
                    min_age_days=min_age_days,
                    limit=5,
                )

                saved_count = bt_result.get("saved", 0)
                per_stock_results.append({
                    "code": code,
                    "status": "completed",
                    "processed": bt_result.get("processed", 0),
                    "saved": saved_count,
                    "completed": bt_result.get("completed", 0),
                })

                # Query recent backtest results for this stock and link
                if saved_count > 0:
                    bt_ids = self.repo.get_bt_result_ids_by_code_date(
                        code=code,
                        after_date=screening_date,
                        limit=max(5, saved_count),
                    )
                    if bt_ids:
                        for record_id in record_ids:
                            if record_id is None:
                                continue
                            linked = self.repo.link_backtest_results(
                                record_id=record_id,
                                backtest_result_ids=bt_ids,
                                code=code,
                            )
                            total_linked += linked

            except Exception as exc:
                logger.warning("回测股票 %s 失败: %s", code, exc)
                per_stock_results.append({
                    "code": code,
                    "status": "failed",
                    "error": str(exc),
                })

        return {
            "status": "completed",
            "total_stocks": len(codes),
            "backtested_stocks": sum(
                1 for r in per_stock_results if r.get("status") == "completed"
            ),
            "total_linked": total_linked,
            "per_stock": per_stock_results,
        }

    def persist_screen_result(
        self,
        strategy: str,
        market: str,
        raw_data: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        duration_seconds: float,
    ) -> int:
        """Persist an already-completed screen result without re-running the adapter."""
        record = ScreeningRecord(
            screening_date=date.today(),
            strategy=strategy,
            market=market,
            candidate_count=len(candidates),
            status="completed",
            duration_seconds=round(duration_seconds, 2),
            run_id=raw_data.get("run_id"),
            snapshot_count=raw_data.get("snapshot_count"),
            after_filter_count=raw_data.get("after_filter_count"),
            llm_ranked=raw_data.get("llm_ranked"),
            llm_market_view=raw_data.get("llm_market_view") or "",
            llm_selection_logic=raw_data.get("llm_selection_logic") or "",
            llm_portfolio_risk=raw_data.get("llm_portfolio_risk") or "",
            llm_coverage=json.dumps(raw_data.get("llm_coverage")) if raw_data.get("llm_coverage") else None,
            warnings_json=json.dumps(raw_data.get("warnings") or [], ensure_ascii=False),
            source_errors_json=json.dumps(raw_data.get("source_errors") or [], ensure_ascii=False),
        )
        record_id = self.repo.save_screening_record(record)
        self.repo.save_candidates_batch(self._build_candidate_batch_payload(record_id, candidates))

        logger.info(
            "Persisted screen result | record_id=%s | strategy=%s | candidates=%d",
            record_id, strategy, len(candidates),
        )
        return record_id

    # ---- Query methods ----

    def get_records(
        self,
        screening_date: Optional[date] = None,
        strategy: Optional[str] = None,
        market: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        records, total = self.repo.list_records(
            screening_date=screening_date,
            strategy=strategy,
            market=market,
            limit=limit,
            offset=offset,
        )
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "records": [
                {
                    "id": r.id,
                    "screening_date": r.screening_date.isoformat() if r.screening_date else None,
                    "strategy": r.strategy,
                    "market": r.market,
                    "candidate_count": r.candidate_count,
                    "status": r.status,
                    "duration_seconds": r.duration_seconds,
                    "run_id": r.run_id,
                    "factor_pipeline": self._get_factor_pipeline_overview(r.id),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ],
        }

    def get_record_detail(self, record_id: int) -> Optional[Dict[str, Any]]:
        record = self.repo.get_record_by_id(record_id)
        if not record:
            return None

        candidates = self.repo.get_candidates_by_record_id(record_id)
        backtest_results = self.repo.get_backtest_results_for_record(record_id)
        backtest_summary = self.repo.get_backtest_summary_for_record(record_id)
        factor_pipeline = self._get_factor_pipeline_overview(record_id)

        def _parse_json(val: Any) -> Any:
            if val is None:
                return None
            if isinstance(val, (list, dict)):
                return val
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return val

        return {
            "id": record.id,
            "screening_date": record.screening_date.isoformat() if record.screening_date else None,
            "strategy": record.strategy,
            "market": record.market,
            "candidate_count": record.candidate_count,
            "status": record.status,
            "duration_seconds": record.duration_seconds,
            "error_message": record.error_message,
            "run_id": record.run_id,
            "snapshot_count": record.snapshot_count,
            "after_filter_count": record.after_filter_count,
            "llm_ranked": record.llm_ranked,
            "llm_market_view": record.llm_market_view,
            "llm_selection_logic": record.llm_selection_logic,
            "llm_portfolio_risk": record.llm_portfolio_risk,
            "llm_coverage": _parse_json(record.llm_coverage),
            "warnings": _parse_json(record.warnings_json) or [],
            "source_errors": _parse_json(record.source_errors_json) or [],
            "execution_logs": record.execution_logs or "",
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "factor_pipeline": factor_pipeline,
            "candidates": [
                {
                    "id": c.id,
                    "rank": c.rank,
                    "code": c.code,
                    "name": c.name,
                    "score": c.score,
                    "screen_score": c.screen_score,
                    "llm_score": c.llm_score,
                    "llm_confidence": c.llm_confidence,
                    "reason": c.reason,
                    "risk_level": c.risk_level,
                    "risk_flags": _parse_json(c.risk_flags_json) or [],
                    "llm_sector": c.llm_sector,
                    "llm_theme": c.llm_theme,
                    "llm_tags": _parse_json(c.llm_tags_json) or [],
                    "llm_thesis": c.llm_thesis,
                    "llm_catalysts": _parse_json(c.llm_catalysts_json) or [],
                    "llm_risks": _parse_json(c.llm_risks_json) or [],
                    "llm_watch_items": _parse_json(c.llm_watch_items_json) or [],
                    "llm_invalidators": _parse_json(c.llm_invalidators_json) or [],
                    "llm_style_fit": c.llm_style_fit,
                    "price": c.price,
                    "change_pct": c.change_pct,
                    "amount": c.amount,
                    "industry": c.industry,
                    "factor_scores": _parse_json(c.factor_scores_json) or {},
                }
                for c in candidates
            ],
            "backtest_results": backtest_results,
            "backtest_summary": backtest_summary,
        }

    def get_available_dates(self) -> List[str]:
        return [d.isoformat() for d in self.repo.get_available_dates()]

    def get_available_strategies(self) -> List[Dict[str, Any]]:
        return self.repo.get_available_strategies()

    def _get_factor_pipeline_overview(self, record_id: int) -> Dict[str, Any]:
        try:
            factor_pipeline = self.factor_pipeline.get_screening_record_factor_pipeline(record_id)
        except Exception as exc:
            logger.warning("获取因子流水线概览失败: record_id=%s, error=%s", record_id, exc)
            return {"status": "unavailable", "error": str(exc), "factor_pipeline_enabled": False}

        candidates = factor_pipeline.get("candidates") or []
        overview = FactorPipelineSummaryPayload(**{
            "status": factor_pipeline.get("status", "unknown"),
            "record_id": record_id,
            "screening_date": factor_pipeline.get("screening_date"),
            "market": factor_pipeline.get("market"),
            "factor_pipeline_enabled": factor_pipeline.get("factor_pipeline_enabled", False),
            "backend": factor_pipeline.get("backend") or "skeleton",
            "factor_family": self._factor_family_payload_from_dict(factor_pipeline.get("factor_family")),
            "training": self._training_payload_from_dict(factor_pipeline.get("training")),
            "runtime_window": factor_pipeline.get("runtime_window") or {},
            "monitoring": self._monitoring_payload_from_dict(factor_pipeline.get("monitoring")),
            "traces": self._traces_payload_from_dict(factor_pipeline.get("traces")),
            "candidates": [],
        })
        return {
            "status": overview.status,
            "factor_pipeline_enabled": overview.factor_pipeline_enabled,
            "backend": overview.backend,
            "training": overview.training.to_dict(),
            "monitoring": overview.monitoring.to_dict(),
            "candidate_count": len(candidates),
            "top_candidates": candidates[:5],
            "factor_family": overview.factor_family.to_dict(),
            "latest_record_id": overview.record_id,
            "latest_strategy": factor_pipeline.get("latest_strategy"),
            "latest_screening_date": factor_pipeline.get("latest_screening_date"),
        }

    def _factor_family_payload_from_dict(self, factor_family: Optional[Dict[str, Any]]) -> FactorPipelineFactorFamilyPayload:
        factor_family = factor_family or {}
        return FactorPipelineFactorFamilyPayload(
            alpha158=[FactorPipelineFactorFamilySpec(**item) for item in factor_family.get("alpha158") or []],
            alpha360=[FactorPipelineFactorFamilySpec(**item) for item in factor_family.get("alpha360") or []],
        )

    def _training_payload_from_dict(self, training: Optional[Dict[str, Any]]) -> FactorPipelineTrainingPayload:
        training = training or {}
        return FactorPipelineTrainingPayload(
            algorithm=str(training.get("algorithm") or "LightGBM"),
            rolling=bool(training.get("rolling", True)),
            enabled=bool(training.get("enabled", False)),
            shap_enabled=bool(training.get("shap_enabled", False)),
            ic_ir_monitoring_enabled=bool(training.get("ic_ir_monitoring_enabled", False)),
            sample_size=int(training.get("sample_size") or 0),
            status=str(training.get("status") or "skeleton"),
            backend=str(training.get("backend") or "skeleton"),
        )

    def _monitoring_payload_from_dict(self, monitoring: Optional[Dict[str, Any]]) -> FactorPipelineMonitoringPayload:
        monitoring = monitoring or {}
        return FactorPipelineMonitoringPayload(
            ic=self._safe_float(monitoring.get("ic")),
            ir=self._safe_float(monitoring.get("ir")),
            decay=self._safe_float(monitoring.get("decay")),
            decay_alert=bool(monitoring.get("decay_alert", False)),
            sample_size=int(monitoring.get("sample_size") or 0),
            backend=str(monitoring.get("backend") or "skeleton"),
        )

    def _traces_payload_from_dict(self, traces: Optional[Dict[str, Any]]) -> FactorPipelineTracesPayload:
        traces = traces or {}
        runtime_window = traces.get("runtime_window") or {}
        candidate_traces = []
        for item in traces.get("candidate_traces") or []:
            candidate_traces.append(
                FactorPipelineTraceItem(
                    code=item.get("code"),
                    backend=item.get("backend"),
                    train_window_days=self._safe_int(item.get("train_window_days")),
                    valid_window_days=self._safe_int(item.get("valid_window_days")),
                    test_window_days=self._safe_int(item.get("test_window_days")),
                    shap_sample_size=self._safe_int(item.get("shap_sample_size")),
                    backend_error=item.get("backend_error"),
                )
            )
        return FactorPipelineTracesPayload(
            backend=str(traces.get("backend") or "skeleton"),
            runtime_window={
                "train_days": int(runtime_window.get("train_days") or 0),
                "valid_days": int(runtime_window.get("valid_days") or 0),
                "test_days": int(runtime_window.get("test_days") or 0),
                "shap_sample_size": int(runtime_window.get("shap_sample_size") or 0),
            },
            candidate_traces=candidate_traces,
            backends_seen=[str(item) for item in traces.get("backends_seen") or []],
        )

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
