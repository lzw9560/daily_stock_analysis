# -*- coding: utf-8 -*-
"""Backtest orchestration service."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select

from src.config import get_config
from src.core.backtest_engine import OVERALL_SENTINEL_CODE, BacktestEngine, EvaluationConfig
from src.core.vbt_engine import GridOptimizer, VbtEngine
from src.repositories.backtest_repo import BacktestRepository
from src.repositories.stock_repo import StockRepository
from src.storage import BacktestResult, BacktestSummary, DatabaseManager

logger = logging.getLogger(__name__)

# ──── Summary field names shared across _build_summary_model / _summary_to_dict ────
_SUMMARY_SCALAR_FIELDS = [
    "total_evaluations", "completed_count", "insufficient_count",
    "long_count", "cash_count", "win_count", "loss_count", "neutral_count",
    "direction_accuracy_pct", "win_rate_pct", "neutral_rate_pct",
    "avg_stock_return_pct", "avg_simulated_return_pct",
    "stop_loss_trigger_rate", "take_profit_trigger_rate",
    "ambiguous_rate", "avg_days_to_first_hit",
]


class BacktestService:
    """Service layer to run and query backtests."""

    MAX_DYNAMIC_SUMMARY_ROWS = 2000

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()
        self.repo = BacktestRepository(self.db)
        self.stock_repo = StockRepository(self.db)
        self.vbt_engine = VbtEngine(
            stock_repo=self.stock_repo,
            resolve_analysis_date=self._resolve_analysis_date,
            fill_daily_data=self._try_fill_daily_data,
            grid_optimizer=GridOptimizer(),
        )

    # ── Run ──────────────────────────────────────────────────────────────

    def run_backtest(
        self,
        *,
        code: Optional[str] = None,
        force: bool = False,
        eval_window_days: Optional[int] = None,
        min_age_days: Optional[int] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        config = get_config()
        if eval_window_days is None:
            eval_window_days = getattr(config, "backtest_eval_window_days", 10)
        if min_age_days is None:
            min_age_days = getattr(config, "backtest_min_age_days", 14)

        engine_version = str(getattr(config, "backtest_engine_version", "v1"))
        neutral_band_pct = float(getattr(config, "backtest_neutral_band_pct", 2.0))

        candidates = self.repo.get_candidates(
            code=code, min_age_days=int(min_age_days), limit=int(limit),
            eval_window_days=int(eval_window_days), engine_version=engine_version, force=force,
        )
        use_vbt_engine = engine_version == "v1"
        if use_vbt_engine:
            config = get_config()
            eval_results = self.vbt_engine.evaluate_batch(
                candidates,
                eval_window_days=int(eval_window_days),
                neutral_band_pct=float(getattr(config, "backtest_neutral_band_pct", 2.0)),
                engine_version=engine_version,
            )
        else:
            eval_results = [
                self._evaluate_one(analysis, eval_window_days, engine_version, use_vbt_engine=False)
                for analysis in candidates
            ]

        processed = completed = insufficient = errors = 0
        touched_codes: set[str] = set()
        results_to_save: List[BacktestResult] = []

        for analysis, eval_result in zip(candidates, eval_results):
            processed += 1
            touched_codes.add(analysis.code)
            try:
                status = eval_result.get("eval_status", "error")
                if status == "insufficient_data":
                    insufficient += 1
                elif status == "completed":
                    completed += 1
                else:
                    errors += 1
                results_to_save.append(self._make_result(analysis, eval_result, eval_window_days, engine_version))
            except Exception as exc:
                errors += 1
                logger.error(f"回测失败: {analysis.code}#{analysis.id}: {exc}")
                results_to_save.append(self._make_error_result(analysis, eval_window_days, engine_version))

        saved = self.repo.save_results_batch(results_to_save, replace_existing=force) if results_to_save else 0
        if saved:
            self._recompute_summaries(
                touched_codes=sorted(touched_codes),
                eval_window_days=int(eval_window_days),
                engine_version=engine_version,
            )

        return {"processed": processed, "saved": saved, "completed": completed, "insufficient": insufficient, "errors": errors}

    def optimize_backtest(
        self,
        *,
        code: Optional[str] = None,
        eval_window_days: Optional[int] = None,
        min_age_days: Optional[int] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        config = get_config()
        if eval_window_days is None:
            eval_window_days = getattr(config, "backtest_eval_window_days", 10)
        if min_age_days is None:
            min_age_days = getattr(config, "backtest_min_age_days", 14)

        engine_version = str(getattr(config, "backtest_engine_version", "v1"))
        candidates = self.repo.get_candidates(
            code=code, min_age_days=int(min_age_days), limit=int(limit),
            eval_window_days=int(eval_window_days), engine_version=engine_version, force=True,
        )
        if not candidates:
            return {"combinations": 0, "score_key": "score", "best": None, "results": []}

        if engine_version != "v1":
            raise ValueError("BACKTEST_ENGINE_VERSION must be v1 for optimization sweeps")

        grid_result = self.vbt_engine.optimize_default_grid(
            candidates,
            eval_window_days=int(eval_window_days),
            neutral_band_pct=float(getattr(config, "backtest_neutral_band_pct", 2.0)),
            engine_version=engine_version,
        )
        self.repo.save_optimization_log(
            code=code,
            eval_window_days=int(eval_window_days),
            engine_version=engine_version,
            combinations=int(grid_result.get("combinations") or 0),
            score_key=str(grid_result.get("score_key") or "score"),
            best_score=self._extract_best_score(grid_result),
            best_params_json=self._json_dumps((grid_result.get("best") or {}).get("params")),
            best_result_json=self._json_dumps(grid_result.get("best")),
            results_json=self._json_dumps(grid_result.get("results")),
        )
        return grid_result

    def get_optimization_logs(
        self,
        *,
        code: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        logs = self.repo.list_optimization_logs(code=code, engine_version="v1", limit=limit)
        items: List[Dict[str, Any]] = []
        for row in logs:
            items.append({
                "id": row.id,
                "code": row.code,
                "eval_window_days": row.eval_window_days,
                "engine_version": row.engine_version,
                "combinations": row.combinations,
                "score_key": row.score_key,
                "best_score": row.best_score,
                "best_params": json.loads(row.best_params_json) if row.best_params_json else None,
                "best_result": json.loads(row.best_result_json) if row.best_result_json else None,
                "results": json.loads(row.results_json) if row.results_json else [],
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })
        return items

    def get_optimization_log_overview(
        self,
        *,
        code: Optional[str] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        logs = self.get_optimization_logs(code=code, limit=limit)
        latest = logs[0] if logs else None
        return {
            "latest": latest,
            "history": logs[:5],
            "total": len(logs),
        }

    # ── Query ────────────────────────────────────────────────────────────

    def get_recent_evaluations(
        self, *, code: Optional[str], eval_window_days: Optional[int] = None,
        limit: int = 50, page: int = 1,
        analysis_date_from: Optional[date] = None, analysis_date_to: Optional[date] = None,
    ) -> Dict[str, Any]:
        config = get_config()
        engine_version = str(getattr(config, "backtest_engine_version", "v1"))

        if eval_window_days is None:
            windows = self.repo.get_distinct_eval_windows(
                code=code, engine_version=engine_version,
                analysis_date_from=analysis_date_from, analysis_date_to=analysis_date_to,
            )
            if windows:
                eval_window_days = windows[0]

        offset = max(page - 1, 0) * limit
        rows, total = self.repo.get_results_paginated(
            code=code, eval_window_days=eval_window_days, engine_version=engine_version,
            analysis_date_from=analysis_date_from, analysis_date_to=analysis_date_to,
            days=None, offset=offset, limit=limit,
        )
        items = [self._result_to_dict(result, stock_name, trend_prediction)
                 for result, stock_name, trend_prediction, _ in rows]
        return {"total": total, "page": page, "limit": limit, "items": items}

    def get_summary(
        self, *, scope: str, code: Optional[str],
        eval_window_days: Optional[int] = None,
        analysis_date_from: Optional[date] = None, analysis_date_to: Optional[date] = None,
    ) -> Optional[Dict[str, Any]]:
        config = get_config()
        engine_version = str(getattr(config, "backtest_engine_version", "v1"))
        lookup_code = OVERALL_SENTINEL_CODE if scope == "overall" else code

        if analysis_date_from is not None or analysis_date_to is not None:
            ew = int(eval_window_days) if eval_window_days is not None else None
            count = self.repo.count_results(
                code=code, eval_window_days=ew, engine_version=engine_version,
                analysis_date_from=analysis_date_from, analysis_date_to=analysis_date_to,
            )
            if count > self.MAX_DYNAMIC_SUMMARY_ROWS:
                raise ValueError("Date-filtered summary matches too many rows; narrow the analysis date range or stock code.")
            rows = self.repo.list_results(
                code=code, eval_window_days=ew, engine_version=engine_version,
                analysis_date_from=analysis_date_from, analysis_date_to=analysis_date_to,
            )
            return self._build_dynamic_summary(
                rows=rows, scope=scope, code=lookup_code,
                eval_window_days=int(eval_window_days) if eval_window_days is not None else None,
                engine_version=engine_version, max_rows=self.MAX_DYNAMIC_SUMMARY_ROWS,
            )

        summary = self.repo.get_summary(
            scope=scope, code=lookup_code, eval_window_days=eval_window_days, engine_version=engine_version,
        )
        return self._summary_to_dict(summary) if summary else None

    def get_global_summary(self, *, eval_window_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
        return self._normalize_learning_summary(
            self.get_summary(scope="overall", code=None, eval_window_days=eval_window_days))

    def get_stock_summary(self, code: str, *, eval_window_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
        return self._normalize_learning_summary(
            self.get_summary(scope="stock", code=code, eval_window_days=eval_window_days))

    def get_skill_summary(self, skill_id: str, *, eval_window_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
        return None  # skill-specific summaries not yet implemented

    def get_strategy_summary(self, strategy_id: str, *, eval_window_days: Optional[int] = None) -> Optional[Dict[str, Any]]:
        summary = self.get_skill_summary(strategy_id, eval_window_days=eval_window_days)
        if summary is None:
            return None
        normalized = dict(summary)
        normalized["strategy_id"] = strategy_id
        return normalized

    # ── Internal ─────────────────────────────────────────────────────────

    def _evaluate_one(
        self,
        analysis,
        eval_window_days: int,
        engine_version: str,
        use_vbt_engine: bool = False,
    ) -> Dict[str, Any]:
        analysis_date = self._resolve_analysis_date(analysis)
        if analysis_date is None:
            return {"eval_status": "error"}

        if use_vbt_engine:
            config = get_config()
            batch_result = self.vbt_engine.evaluate_batch(
                [analysis],
                eval_window_days=eval_window_days,
                neutral_band_pct=float(getattr(config, "backtest_neutral_band_pct", 2.0)),
                engine_version=engine_version,
            )
            return batch_result[0] if batch_result else {"eval_status": "error"}

        start_daily = self.stock_repo.get_start_daily(code=analysis.code, analysis_date=analysis_date)
        if start_daily is None or start_daily.close is None:
            self._try_fill_daily_data(code=analysis.code, analysis_date=analysis_date, eval_window_days=eval_window_days)
            start_daily = self.stock_repo.get_start_daily(code=analysis.code, analysis_date=analysis_date)

        if start_daily is None or start_daily.close is None:
            return {"eval_status": "insufficient_data"}

        forward_bars = self.stock_repo.get_forward_bars(
            code=analysis.code, analysis_date=start_daily.date, eval_window_days=eval_window_days)
        if len(forward_bars) < eval_window_days:
            self._try_fill_daily_data(code=analysis.code, analysis_date=start_daily.date, eval_window_days=eval_window_days)
            forward_bars = self.stock_repo.get_forward_bars(
                code=analysis.code, analysis_date=start_daily.date, eval_window_days=eval_window_days)

        config = get_config()
        eval_config = EvaluationConfig(
            eval_window_days=eval_window_days,
            neutral_band_pct=float(getattr(config, "backtest_neutral_band_pct", 2.0)),
            engine_version=engine_version,
        )

        return BacktestEngine.evaluate_single(
            operation_advice=analysis.operation_advice,
            analysis_date=start_daily.date,
            start_price=float(start_daily.close),
            forward_bars=forward_bars,
            stop_loss=analysis.stop_loss,
            take_profit=analysis.take_profit,
            config=eval_config,
        )

    def _resolve_analysis_date(self, analysis) -> Optional[date]:
        parsed = self.repo.parse_analysis_date_from_snapshot(analysis.context_snapshot)
        if parsed:
            return parsed
        if getattr(analysis, "created_at", None):
            return analysis.created_at.date()
        logger.warning(f"无法确定分析日期，跳过记录: {analysis.code}#{getattr(analysis, 'id', '?')}")
        return None

    def _try_fill_daily_data(self, *, code: str, analysis_date: date, eval_window_days: int) -> None:
        try:
            from data_provider.base import DataFetcherManager
            end_date = analysis_date + timedelta(days=max(eval_window_days * 2, 30))
            manager = DataFetcherManager()
            df, source = manager.get_daily_data(
                stock_code=code,
                start_date=analysis_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                days=eval_window_days * 2,
            )
            if df is not None and not df.empty:
                self.db.save_daily_data(df, code=code, data_source=source)
        except Exception as exc:
            logger.warning(f"补全日线数据失败({code}): {exc}")

    def _recompute_summaries(self, *, touched_codes: List[str], eval_window_days: int, engine_version: str) -> None:
        with self.db.get_session() as session:
            overall_rows = session.execute(
                select(BacktestResult).where(
                    and_(BacktestResult.eval_window_days == eval_window_days, BacktestResult.engine_version == engine_version)
                )
            ).scalars().all()
            overall_data = BacktestEngine.compute_summary(
                results=overall_rows, scope="overall", code=OVERALL_SENTINEL_CODE,
                eval_window_days=eval_window_days, engine_version=engine_version,
            )
            self.repo.upsert_summary(self._build_summary_model(overall_data))

            for code in touched_codes:
                rows = session.execute(
                    select(BacktestResult).where(
                        and_(BacktestResult.code == code, BacktestResult.eval_window_days == eval_window_days,
                             BacktestResult.engine_version == engine_version)
                    )
                ).scalars().all()
                data = BacktestEngine.compute_summary(
                    results=rows, scope="stock", code=code,
                    eval_window_days=eval_window_days, engine_version=engine_version,
                )
                self.repo.upsert_summary(self._build_summary_model(data))

    # ── Build helpers ────────────────────────────────────────────────────

    @staticmethod
    def _make_result(analysis, evaluation: Dict[str, Any], eval_window_days: int, engine_version: str) -> BacktestResult:
        return BacktestResult(
            analysis_history_id=analysis.id,
            code=analysis.code,
            analysis_date=evaluation.get("analysis_date"),
            eval_window_days=int(evaluation.get("eval_window_days") or eval_window_days),
            engine_version=str(evaluation.get("engine_version") or engine_version),
            eval_status=str(evaluation.get("eval_status") or "error"),
            evaluated_at=datetime.now(),
            operation_advice=evaluation.get("operation_advice"),
            position_recommendation=evaluation.get("position_recommendation"),
            start_price=evaluation.get("start_price"),
            end_close=evaluation.get("end_close"),
            max_high=evaluation.get("max_high"),
            min_low=evaluation.get("min_low"),
            stock_return_pct=evaluation.get("stock_return_pct"),
            direction_expected=evaluation.get("direction_expected"),
            direction_correct=evaluation.get("direction_correct"),
            outcome=evaluation.get("outcome"),
            stop_loss=evaluation.get("stop_loss"),
            take_profit=evaluation.get("take_profit"),
            hit_stop_loss=evaluation.get("hit_stop_loss"),
            hit_take_profit=evaluation.get("hit_take_profit"),
            first_hit=evaluation.get("first_hit"),
            first_hit_date=evaluation.get("first_hit_date"),
            first_hit_trading_days=evaluation.get("first_hit_trading_days"),
            simulated_entry_price=evaluation.get("simulated_entry_price"),
            simulated_exit_price=evaluation.get("simulated_exit_price"),
            simulated_exit_reason=evaluation.get("simulated_exit_reason"),
            simulated_return_pct=evaluation.get("simulated_return_pct"),
        )

    @staticmethod
    def _make_error_result(analysis, eval_window_days: int, engine_version: str) -> BacktestResult:
        return BacktestResult(
            analysis_history_id=analysis.id,
            code=analysis.code,
            analysis_date=BacktestService._resolve_analysis_date(analysis),
            eval_window_days=eval_window_days,
            engine_version=engine_version,
            eval_status="error",
            evaluated_at=datetime.now(),
            operation_advice=analysis.operation_advice,
        )

    @staticmethod
    def _build_summary_model(summary_data: Dict[str, Any]) -> BacktestSummary:
        kwargs: Dict[str, Any] = {
            "scope": summary_data.get("scope"),
            "code": summary_data.get("code"),
            "eval_window_days": summary_data.get("eval_window_days"),
            "engine_version": summary_data.get("engine_version"),
            "computed_at": datetime.now(),
        }
        for field in _SUMMARY_SCALAR_FIELDS:
            kwargs[field] = summary_data.get(field) or 0
        kwargs["advice_breakdown_json"] = json.dumps(summary_data.get("advice_breakdown") or {}, ensure_ascii=False)
        kwargs["diagnostics_json"] = json.dumps(summary_data.get("diagnostics") or {}, ensure_ascii=False)
        return BacktestSummary(**kwargs)

    @staticmethod
    def _summary_to_dict(row: BacktestSummary) -> Dict[str, Any]:
        return {
            "scope": row.scope,
            "code": None if row.code == OVERALL_SENTINEL_CODE else row.code,
            "eval_window_days": row.eval_window_days,
            "engine_version": row.engine_version,
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
            **{f: getattr(row, f) for f in _SUMMARY_SCALAR_FIELDS},
            "advice_breakdown": json.loads(row.advice_breakdown_json) if row.advice_breakdown_json else {},
            "diagnostics": json.loads(row.diagnostics_json) if row.diagnostics_json else {},
        }

    @staticmethod
    def _result_to_dict(
        row: BacktestResult, stock_name: Optional[str] = None, trend_prediction: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "analysis_history_id": row.analysis_history_id,
            "code": row.code,
            "stock_name": stock_name,
            "analysis_date": row.analysis_date.isoformat() if row.analysis_date else None,
            "eval_window_days": row.eval_window_days,
            "engine_version": row.engine_version,
            "eval_status": row.eval_status,
            "evaluated_at": row.evaluated_at.isoformat() if row.evaluated_at else None,
            "operation_advice": row.operation_advice,
            "trend_prediction": trend_prediction,
            "position_recommendation": row.position_recommendation,
            "start_price": row.start_price,
            "end_close": row.end_close,
            "max_high": row.max_high,
            "min_low": row.min_low,
            "stock_return_pct": row.stock_return_pct,
            "actual_return_pct": row.stock_return_pct,
            "actual_movement": BacktestService._actual_movement_from_return(row.stock_return_pct),
            "direction_expected": row.direction_expected,
            "direction_correct": row.direction_correct,
            "outcome": row.outcome,
            "stop_loss": row.stop_loss,
            "take_profit": row.take_profit,
            "hit_stop_loss": row.hit_stop_loss,
            "hit_take_profit": row.hit_take_profit,
            "first_hit": row.first_hit,
            "first_hit_date": row.first_hit_date.isoformat() if row.first_hit_date else None,
            "first_hit_trading_days": row.first_hit_trading_days,
            "simulated_entry_price": row.simulated_entry_price,
            "simulated_exit_price": row.simulated_exit_price,
            "simulated_exit_reason": row.simulated_exit_reason,
            "simulated_return_pct": row.simulated_return_pct,
        }

    @staticmethod
    def _build_dynamic_summary(
        *, rows: List[BacktestResult], scope: str, code: Optional[str],
        eval_window_days: Optional[int], engine_version: str, max_rows: Optional[int] = None,
    ) -> Dict[str, Any]:
        filtered_rows = [r for r in rows if getattr(r, "engine_version", None) == engine_version]
        if eval_window_days is not None:
            summary_window_days = int(eval_window_days)
        else:
            window_values = sorted({
                int(r.eval_window_days)
                for r in filtered_rows if getattr(r, "eval_window_days", None) is not None
            })
            if len(window_values) > 1:
                logger.warning(
                    "Multiple eval_window_days values for dynamic summary; using %s (scope=%s, code=%s)",
                    window_values[0], scope, code)
            summary_window_days = window_values[0] if window_values else int(getattr(get_config(), "backtest_eval_window_days", 10))

        filtered_rows = [r for r in filtered_rows if getattr(r, "eval_window_days", None) == summary_window_days]
        if max_rows is not None and len(filtered_rows) > max_rows:
            raise ValueError("Date-filtered summary matches too many rows; narrow the analysis date range or stock code.")

        summary = BacktestEngine.compute_summary(
            results=filtered_rows, scope=scope, code=code,
            eval_window_days=summary_window_days, engine_version=engine_version,
        )
        summary["code"] = None if summary.get("code") == OVERALL_SENTINEL_CODE else summary.get("code")
        summary["computed_at"] = datetime.now().isoformat()
        return summary

    # ── Static utilities ─────────────────────────────────────────────────

    @staticmethod
    def _normalize_learning_summary(summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if summary is None:
            return None
        normalized = dict(summary)
        normalized["win_rate"] = BacktestService._pct_to_ratio(summary.get("win_rate_pct"), default=0.5)
        normalized["direction_accuracy"] = BacktestService._pct_to_ratio(summary.get("direction_accuracy_pct"), default=0.5)
        avg_return_pct = summary.get("avg_simulated_return_pct") or summary.get("avg_stock_return_pct")
        normalized["avg_return"] = BacktestService._pct_to_ratio(avg_return_pct, default=0.0)
        return normalized

    @staticmethod
    def _pct_to_ratio(value: Optional[float], default: float = 0.0) -> float:
        try:
            return float(value) / 100.0
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _actual_movement_from_return(value: Optional[float]) -> Optional[str]:
        if value is None:
            return None
        try:
            r = float(value)
        except (TypeError, ValueError):
            return None
        return "up" if r > 0 else "down" if r < 0 else "flat"

    @staticmethod
    def _json_dumps(value: Any) -> Optional[str]:
        if value is None:
            return None
        try:
            return json.dumps(value, ensure_ascii=False)
        except TypeError:
            return json.dumps(str(value), ensure_ascii=False)

    @staticmethod
    def _extract_best_score(result: Dict[str, Any]) -> Optional[float]:
        best = result.get("best") or {}
        score = best.get("score")
        try:
            return float(score) if score is not None else None
        except (TypeError, ValueError):
            return None
