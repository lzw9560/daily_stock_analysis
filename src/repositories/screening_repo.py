# -*- coding: utf-8 -*-
"""Screening records data access layer."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, select, func

from src.services.screening_payloads import ScreeningCandidateBatchPayload, ScreeningCandidatePayload
from src.storage import (
    DatabaseManager,
    ScreeningRecord,
    ScreeningCandidate,
    ScreeningBacktestLink,
    BacktestResult,
    BacktestSummary,
)

logger = logging.getLogger(__name__)


class ScreeningRepository:
    """Repository for screening records, candidates, and backtest links."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    @staticmethod
    def _json_dumps(value: Any) -> str:
        if value is None:
            return "null"
        if is_dataclass(value):
            value = asdict(value)
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _parse_json(value: Any, default: Any = None) -> Any:
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return default

    # ---- ScreeningRecord CRUD ----

    def save_screening_record(self, record: ScreeningRecord) -> int:
        """Insert or upsert a screening record. Returns the record id."""
        def _write(session):
            existing = session.execute(
                select(ScreeningRecord).where(
                    and_(
                        ScreeningRecord.screening_date == record.screening_date,
                        ScreeningRecord.strategy == record.strategy,
                        ScreeningRecord.market == record.market,
                    )
                )
            ).scalar_one_or_none()

            if existing:
                existing.status = record.status
                existing.candidate_count = record.candidate_count
                existing.duration_seconds = record.duration_seconds
                existing.error_message = record.error_message
                existing.run_id = record.run_id
                existing.snapshot_count = record.snapshot_count
                existing.after_filter_count = record.after_filter_count
                existing.llm_ranked = record.llm_ranked
                existing.llm_market_view = record.llm_market_view
                existing.llm_selection_logic = record.llm_selection_logic
                existing.llm_portfolio_risk = record.llm_portfolio_risk
                existing.llm_coverage = record.llm_coverage
                existing.warnings_json = record.warnings_json
                existing.source_errors_json = record.source_errors_json
                session.flush()
                return existing.id
            else:
                session.add(record)
                session.flush()
                return record.id

        return self.db._run_write_transaction("save_screening_record", _write)

    def get_record_by_id(self, record_id: int) -> Optional[ScreeningRecord]:
        with self.db.get_session() as session:
            return session.execute(
                select(ScreeningRecord).where(ScreeningRecord.id == record_id)
            ).scalar_one_or_none()

    def list_records(
        self,
        screening_date: Optional[date] = None,
        strategy: Optional[str] = None,
        market: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ScreeningRecord], int]:
        with self.db.get_session() as session:
            conditions = []
            if screening_date:
                conditions.append(ScreeningRecord.screening_date == screening_date)
            if strategy:
                conditions.append(ScreeningRecord.strategy == strategy)
            if market:
                conditions.append(ScreeningRecord.market == market)

            where = and_(*conditions) if conditions else True

            total = session.execute(
                select(func.count(ScreeningRecord.id)).where(where)
            ).scalar() or 0

            records = session.execute(
                select(ScreeningRecord)
                .where(where)
                .order_by(desc(ScreeningRecord.screening_date), desc(ScreeningRecord.created_at))
                .offset(offset)
                .limit(limit)
            ).scalars().all()

            return list(records), total

    def get_available_dates(self, limit: int = 30) -> List[date]:
        """Get distinct screening dates in descending order."""
        with self.db.get_session() as session:
            result = session.execute(
                select(ScreeningRecord.screening_date)
                .distinct()
                .order_by(desc(ScreeningRecord.screening_date))
                .limit(limit)
            ).scalars().all()
            return list(result)

    def get_available_strategies(self) -> List[Dict[str, Any]]:
        """Get distinct strategy names with record count."""
        with self.db.get_session() as session:
            result = session.execute(
                select(ScreeningRecord.strategy, func.count(ScreeningRecord.id))
                .group_by(ScreeningRecord.strategy)
                .order_by(desc(func.count(ScreeningRecord.id)))
            ).all()
            return [{"strategy": r[0], "count": r[1]} for r in result]

    # ---- ScreeningCandidate CRUD ----

    def save_candidates_batch(
        self, payload: ScreeningCandidateBatchPayload
    ) -> int:
        """Replace candidates for a record. Returns count saved."""
        def _write(session):
            session.query(ScreeningCandidate).filter(
                ScreeningCandidate.screening_record_id == payload.record_id
            ).delete()

            saved = 0
            for candidate_payload in payload.candidates:
                candidate = ScreeningCandidate(
                    screening_record_id=payload.record_id,
                    rank=candidate_payload.rank,
                    code=candidate_payload.code,
                    name=candidate_payload.name,
                    score=candidate_payload.score,
                    screen_score=candidate_payload.screen_score,
                    llm_score=candidate_payload.llm_score,
                    llm_confidence=candidate_payload.llm_confidence,
                    reason=candidate_payload.reason,
                    risk_level=candidate_payload.risk_level,
                    risk_flags_json=self._json_dumps(candidate_payload.risk_flags),
                    llm_sector=candidate_payload.llm_sector,
                    llm_theme=candidate_payload.llm_theme,
                    llm_tags_json=self._json_dumps(candidate_payload.llm_tags),
                    llm_thesis=candidate_payload.llm_thesis,
                    llm_catalysts_json=self._json_dumps(candidate_payload.llm_catalysts),
                    llm_risks_json=self._json_dumps(candidate_payload.llm_risks),
                    llm_watch_items_json=self._json_dumps(candidate_payload.llm_watch_items),
                    llm_invalidators_json=self._json_dumps(candidate_payload.llm_invalidators),
                    llm_style_fit=candidate_payload.llm_style_fit,
                    price=candidate_payload.price,
                    change_pct=candidate_payload.change_pct,
                    amount=candidate_payload.amount,
                    industry=candidate_payload.industry,
                    factor_scores_json=self._json_dumps(candidate_payload.factor_payload or candidate_payload.factor_scores),
                    raw_json=self._json_dumps(candidate_payload.raw),
                )
                session.add(candidate)
                saved += 1

            return saved

        return self.db._run_write_transaction("save_candidates_batch", _write)

    def get_candidates_by_record_id(
        self, record_id: int
    ) -> List[ScreeningCandidate]:
        with self.db.get_session() as session:
            return list(
                session.execute(
                    select(ScreeningCandidate)
                    .where(ScreeningCandidate.screening_record_id == record_id)
                    .order_by(ScreeningCandidate.rank)
                ).scalars().all()
            )

    def get_candidate_codes_by_record_id(self, record_id: int) -> List[str]:
        with self.db.get_session() as session:
            result = session.execute(
                select(ScreeningCandidate.code)
                .where(ScreeningCandidate.screening_record_id == record_id)
                .distinct()
            ).scalars().all()
            return list(result)

    def parse_factor_scores(self, candidate: ScreeningCandidate) -> Dict[str, Any]:
        return self._parse_json(candidate.factor_scores_json, default={}) or {}

    def write_factor_scores(self, candidate: ScreeningCandidate, payload: Dict[str, Any]) -> None:
        with self.db.get_session() as session:
            row = session.get(ScreeningCandidate, candidate.id)
            if row is None:
                return
            row.factor_scores_json = self._json_dumps(payload)
            session.commit()

    # ---- Backtest Link CRUD ----

    def link_backtest_results(
        self,
        record_id: int,
        backtest_result_ids: List[int],
        code: str = "",
        candidate_id: Optional[int] = None,
        summary_id: Optional[int] = None,
    ) -> int:
        """Create links between screening record and backtest results."""
        def _write(session):
            linked = 0
            for bt_id in backtest_result_ids:
                existing = session.execute(
                    select(ScreeningBacktestLink).where(
                        and_(
                            ScreeningBacktestLink.screening_record_id == record_id,
                            ScreeningBacktestLink.backtest_result_id == bt_id,
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    continue
                link = ScreeningBacktestLink(
                    screening_record_id=record_id,
                    screening_candidate_id=candidate_id,
                    backtest_result_id=bt_id,
                    backtest_summary_id=summary_id,
                    code=code,
                )
                session.add(link)
                linked += 1
            return linked

        return self.db._run_write_transaction("link_backtest_results", _write)

    def get_backtest_results_for_record(
        self, record_id: int
    ) -> List[Dict[str, Any]]:
        """Get all backtest results linked to a screening record."""
        with self.db.get_session() as session:
            rows = session.execute(
                select(
                    ScreeningBacktestLink,
                    BacktestResult,
                )
                .join(
                    BacktestResult,
                    BacktestResult.id == ScreeningBacktestLink.backtest_result_id,
                )
                .where(ScreeningBacktestLink.screening_record_id == record_id)
                .order_by(desc(BacktestResult.evaluated_at))
            ).all()

            results = []
            for link, bt in rows:
                results.append({
                    "link_id": link.id,
                    "backtest_result_id": bt.id,
                    "analysis_history_id": bt.analysis_history_id,
                    "code": bt.code,
                    "analysis_date": bt.analysis_date.isoformat() if bt.analysis_date else None,
                    "eval_window_days": bt.eval_window_days,
                    "engine_version": bt.engine_version,
                    "eval_status": bt.eval_status,
                    "evaluated_at": bt.evaluated_at.isoformat() if bt.evaluated_at else None,
                    "operation_advice": bt.operation_advice,
                    "direction_expected": bt.direction_expected,
                    "direction_correct": bt.direction_correct,
                    "outcome": bt.outcome,
                    "stock_return_pct": bt.stock_return_pct,
                    "simulated_return_pct": bt.simulated_return_pct,
                    "hit_stop_loss": bt.hit_stop_loss,
                    "hit_take_profit": bt.hit_take_profit,
                })
            return results

    def get_backtest_summary_for_record(
        self, record_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get the first backtest summary linked to a screening record."""
        with self.db.get_session() as session:
            row = session.execute(
                select(
                    ScreeningBacktestLink.backtest_summary_id,
                    ScreeningBacktestLink.code,
                )
                .where(ScreeningBacktestLink.screening_record_id == record_id)
                .where(ScreeningBacktestLink.backtest_summary_id.isnot(None))
                .limit(1)
            ).first()

            if not row:
                return None

            summary = session.execute(
                select(BacktestSummary).where(BacktestSummary.id == row[0])
            ).scalar_one_or_none()

            if not summary:
                return None

            return {
                "id": summary.id,
                "scope": summary.scope,
                "code": summary.code,
                "eval_window_days": summary.eval_window_days,
                "total_evaluations": summary.total_evaluations,
                "completed_count": summary.completed_count,
                "win_count": summary.win_count,
                "loss_count": summary.loss_count,
                "direction_accuracy_pct": summary.direction_accuracy_pct,
                "win_rate_pct": summary.win_rate_pct,
                "avg_stock_return_pct": summary.avg_stock_return_pct,
                "avg_simulated_return_pct": summary.avg_simulated_return_pct,
            }

    def get_bt_result_ids_by_code_date(
        self, code: str, after_date: date, limit: int = 5
    ) -> List[int]:
        """Find backtest results for a stock evaluated after a given date."""
        with self.db.get_session() as session:
            result = session.execute(
                select(BacktestResult.id)
                .where(BacktestResult.code == code)
                .where(BacktestResult.evaluated_at >= after_date)
                .order_by(desc(BacktestResult.evaluated_at))
                .limit(limit)
            ).scalars().all()
            return list(result)
