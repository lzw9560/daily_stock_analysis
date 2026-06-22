# -*- coding: utf-8 -*-
"""Vectorized backtest execution helpers.

This module centralizes the batched forward-bar prefetch path used by the
v1 backtest flow and provides a generic grid optimizer scaffold for future
parameter sweeps.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import product
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from src.core.backtest_engine import BacktestEngine, EvaluationConfig


@dataclass(frozen=True)
class _DailyBarSeries:
    bars: List[Any]
    dates: List[date]

    @classmethod
    def from_bars(cls, bars: List[Any]) -> "_DailyBarSeries":
        ordered_bars = sorted(bars, key=lambda row: row.date)
        return cls(bars=ordered_bars, dates=[row.date for row in ordered_bars])

    def get_start_daily(self, analysis_date: date) -> Optional[Any]:
        index = bisect_right(self.dates, analysis_date) - 1
        if index < 0:
            return None
        return self.bars[index]

    def get_forward_bars(self, analysis_date: date, eval_window_days: int) -> List[Any]:
        start_index = bisect_right(self.dates, analysis_date)
        end_index = start_index + max(eval_window_days, 0)
        return self.bars[start_index:end_index]


class TAWrapper:
    """Compatibility adapter for TA-driven backtest inputs."""

    def build_default_grid(self) -> Dict[str, Sequence[Any]]:
        """Return a 5,000-combination parameter grid for future sweeps."""
        return {
            "eval_window_days": (5, 10, 15, 20, 30),
            "neutral_band_pct": (1.0, 1.5, 2.0, 2.5, 3.0),
            "stop_loss_pct": (3, 4, 5, 6, 7, 8, 9, 10, 12, 15),
            "take_profit_rr": (1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0),
            "use_trailing_stop": (False, True),
        }

    def build_effective_params(
        self,
        analysis: Any,
        *,
        eval_window_days: int,
        neutral_band_pct: float,
        engine_version: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        params = dict(params or {})
        start_price = float(params.pop("start_price", 0.0) or 0.0)
        stop_loss_pct = params.pop("stop_loss_pct", None)
        take_profit_rr = params.pop("take_profit_rr", None)

        stop_loss = getattr(analysis, "stop_loss", None)
        if stop_loss_pct is not None and start_price > 0:
            stop_loss = start_price * (1 - float(stop_loss_pct) / 100.0)

        take_profit = getattr(analysis, "take_profit", None)
        if take_profit_rr is not None and start_price > 0 and stop_loss is not None:
            risk_per_share = max(start_price - float(stop_loss), 0.0)
            take_profit = start_price + risk_per_share * float(take_profit_rr)

        return {
            "operation_advice": analysis.operation_advice,
            "analysis_date": params.pop("analysis_date", None),
            "start_price": start_price,
            "forward_bars": params.pop("forward_bars", ()),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "config": EvaluationConfig(
                eval_window_days=int(params.pop("eval_window_days", eval_window_days)),
                neutral_band_pct=float(params.pop("neutral_band_pct", neutral_band_pct)),
                engine_version=str(params.pop("engine_version", engine_version)),
            ),
            "use_trailing_stop": bool(params.pop("use_trailing_stop", False)),
        }

    def evaluate(
        self,
        analysis: Any,
        *,
        analysis_date: date,
        start_price: float,
        forward_bars: Sequence[Any],
        eval_window_days: int,
        neutral_band_pct: float,
        engine_version: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        effective = self.build_effective_params(
            analysis,
            eval_window_days=eval_window_days,
            neutral_band_pct=neutral_band_pct,
            engine_version=engine_version,
            params={**(params or {}), "analysis_date": analysis_date, "start_price": start_price, "forward_bars": forward_bars},
        )
        result = BacktestEngine.evaluate_single(
            operation_advice=effective["operation_advice"],
            analysis_date=analysis_date,
            start_price=start_price,
            forward_bars=forward_bars,
            stop_loss=effective["stop_loss"],
            take_profit=effective["take_profit"],
            config=effective["config"],
        )
        result["ta_params"] = {
            "use_trailing_stop": effective["use_trailing_stop"],
            "stop_loss_pct": (params or {}).get("stop_loss_pct"),
            "take_profit_rr": (params or {}).get("take_profit_rr"),
        }
        return result

    def score(self, result: Dict[str, Any]) -> float:
        if result.get("eval_status") != "completed":
            return float("-inf")
        score = 0.0
        if result.get("outcome") == "win":
            score += 100.0
        if result.get("direction_correct") is True:
            score += 25.0
        if result.get("hit_take_profit") is True:
            score += 10.0
        if result.get("hit_stop_loss") is True:
            score -= 10.0
        return score


class GridOptimizer:
    """Generic grid-search helper for future parameter sweeps."""

    def optimize(
        self,
        *,
        grid: Dict[str, Sequence[Any]],
        evaluator: Callable[[Dict[str, Any]], Dict[str, Any]],
        score_key: str = "score",
    ) -> Dict[str, Any]:
        keys = list(grid.keys())
        combinations = [dict(zip(keys, values)) for values in product(*(grid[key] for key in keys))]

        best_result: Optional[Dict[str, Any]] = None
        results: List[Dict[str, Any]] = []

        for params in combinations:
            result = dict(evaluator(params))
            result["params"] = params
            results.append(result)
            score = result.get(score_key)
            if score is None:
                continue
            if best_result is None or score > best_result.get(score_key, float("-inf")):
                best_result = result

        return {
            "best": best_result,
            "results": results,
            "combinations": len(combinations),
            "score_key": score_key,
        }


class VbtEngine:
    """Vectorized backtest executor with code-grouped prefetch."""

    def __init__(
        self,
        stock_repo: Any,
        resolve_analysis_date: Callable[[Any], Optional[date]],
        fill_daily_data: Callable[[str, date, int], None],
        *,
        grid_optimizer: Optional[GridOptimizer] = None,
        ta_wrapper: Optional[TAWrapper] = None,
    ) -> None:
        self.stock_repo = stock_repo
        self.resolve_analysis_date = resolve_analysis_date
        self.fill_daily_data = fill_daily_data
        self.grid_optimizer = grid_optimizer or GridOptimizer()
        self.ta_wrapper = ta_wrapper or TAWrapper()

    def evaluate_batch(
        self,
        analyses: Sequence[Any],
        *,
        eval_window_days: int,
        neutral_band_pct: float,
        engine_version: str,
    ) -> List[Dict[str, Any]]:
        caches = self._build_daily_bar_cache(analyses, eval_window_days)
        results: List[Dict[str, Any]] = []

        for analysis in analyses:
            result = self._evaluate_one(
                analysis=analysis,
                eval_window_days=eval_window_days,
                neutral_band_pct=neutral_band_pct,
                engine_version=engine_version,
                cached_series=caches.get(analysis.code),
            )
            results.append(result)

        return results

    def optimize_batch(
        self,
        analyses: Sequence[Any],
        *,
        grid: Dict[str, Sequence[Any]],
        evaluator: Callable[[Any, Dict[str, Any]], Dict[str, Any]],
        score_key: str = "score",
    ) -> Dict[str, Any]:
        """Run grid search per analysis and keep a consolidated best result."""

        def batch_evaluator(params: Dict[str, Any]) -> Dict[str, Any]:
            combined = [evaluator(analysis, params) for analysis in analyses]
            best_score = max((item.get(score_key) for item in combined if item.get(score_key) is not None), default=None)
            return {
                score_key: best_score,
                "per_analysis": combined,
            }

        return self.grid_optimizer.optimize(grid=grid, evaluator=batch_evaluator, score_key=score_key)

    def optimize_default_grid(
        self,
        analyses: Sequence[Any],
        *,
        eval_window_days: int,
        neutral_band_pct: float,
        engine_version: str,
    ) -> Dict[str, Any]:
        """Run the default TA grid sweep used by the Phase 1 plan."""

        caches = self._build_daily_bar_cache(analyses, eval_window_days)
        grid = self.ta_wrapper.build_default_grid()

        def evaluator(params: Dict[str, Any]) -> Dict[str, Any]:
            results: List[Dict[str, Any]] = []
            for analysis in analyses:
                analysis_date = self.resolve_analysis_date(analysis)
                if analysis_date is None:
                    continue
                cached_series = caches.get(analysis.code)
                if cached_series is None:
                    continue
                start_daily = cached_series.get_start_daily(analysis_date)
                if start_daily is None or getattr(start_daily, "close", None) is None:
                    continue
                forward_bars = cached_series.get_forward_bars(analysis_date, int(params.get("eval_window_days", eval_window_days)))
                if len(forward_bars) < int(params.get("eval_window_days", eval_window_days)):
                    continue
                result = self.ta_wrapper.evaluate(
                    analysis,
                    analysis_date=start_daily.date,
                    start_price=float(start_daily.close),
                    forward_bars=forward_bars,
                    eval_window_days=int(params.get("eval_window_days", eval_window_days)),
                    neutral_band_pct=float(params.get("neutral_band_pct", neutral_band_pct)),
                    engine_version=str(engine_version),
                    params={**params, "start_price": float(start_daily.close)},
                )
                results.append(result)

            if not results:
                return {"score": float("-inf"), "results": []}

            scores = [self.ta_wrapper.score(result) for result in results]
            avg_score = sum(scores) / len(scores)
            return {
                "score": avg_score,
                "results": results,
                "completed_count": sum(1 for result in results if result.get("eval_status") == "completed"),
                "win_count": sum(1 for result in results if result.get("outcome") == "win"),
            }

        return self.grid_optimizer.optimize(grid=grid, evaluator=evaluator, score_key="score")

    def optimize_parameter_grid(
        self,
        *,
        grid: Dict[str, Sequence[Any]],
        evaluator: Callable[[Dict[str, Any]], Dict[str, Any]],
        score_key: str = "score",
    ) -> Dict[str, Any]:
        return self.grid_optimizer.optimize(grid=grid, evaluator=evaluator, score_key=score_key)

    def _build_daily_bar_cache(
        self,
        analyses: Sequence[Any],
        eval_window_days: int,
    ) -> Dict[str, _DailyBarSeries]:
        grouped_dates: Dict[str, List[date]] = {}
        for analysis in analyses:
            analysis_date = self.resolve_analysis_date(analysis)
            if analysis_date is None:
                continue
            grouped_dates.setdefault(analysis.code, []).append(analysis_date)

        cached_series: Dict[str, _DailyBarSeries] = {}
        prefetch_padding_days = max(30, eval_window_days * 4)
        forward_padding_days = max(10, eval_window_days * 2)

        for code, analysis_dates in grouped_dates.items():
            if not analysis_dates:
                continue
            start_date = min(analysis_dates) - timedelta(days=prefetch_padding_days)
            end_date = max(analysis_dates) + timedelta(days=forward_padding_days)
            bars = self.stock_repo.get_range(code=code, start_date=start_date, end_date=end_date)
            if bars:
                cached_series[code] = _DailyBarSeries.from_bars(list(bars))

        return cached_series

    def _evaluate_one(
        self,
        *,
        analysis: Any,
        eval_window_days: int,
        neutral_band_pct: float,
        engine_version: str,
        cached_series: Optional[_DailyBarSeries],
    ) -> Dict[str, Any]:
        analysis_date = self.resolve_analysis_date(analysis)
        if analysis_date is None:
            return {"eval_status": "error"}

        if cached_series is not None:
            start_daily = cached_series.get_start_daily(analysis_date)
            if start_daily is not None and getattr(start_daily, "close", None) is not None:
                forward_bars = cached_series.get_forward_bars(analysis_date, eval_window_days)
                if len(forward_bars) >= eval_window_days:
                    return self._evaluate_with_bars(
                        analysis=analysis,
                        analysis_date=start_daily.date,
                        start_price=float(start_daily.close),
                        forward_bars=forward_bars,
                        eval_window_days=eval_window_days,
                        neutral_band_pct=neutral_band_pct,
                        engine_version=engine_version,
                    )

        start_daily = self.stock_repo.get_start_daily(code=analysis.code, analysis_date=analysis_date)
        if start_daily is None or start_daily.close is None:
            self.fill_daily_data(analysis.code, analysis_date, eval_window_days)
            start_daily = self.stock_repo.get_start_daily(code=analysis.code, analysis_date=analysis_date)

        if start_daily is None or start_daily.close is None:
            return {"eval_status": "insufficient_data"}

        forward_bars = self.stock_repo.get_forward_bars(
            code=analysis.code, analysis_date=start_daily.date, eval_window_days=eval_window_days)
        if len(forward_bars) < eval_window_days:
            self.fill_daily_data(analysis.code, start_daily.date, eval_window_days)
            forward_bars = self.stock_repo.get_forward_bars(
                code=analysis.code, analysis_date=start_daily.date, eval_window_days=eval_window_days)

        if len(forward_bars) < eval_window_days:
            return {
                "analysis_date": start_daily.date,
                "operation_advice": analysis.operation_advice,
                "position_recommendation": BacktestEngine.infer_position_recommendation(analysis.operation_advice),
                "direction_expected": BacktestEngine.infer_direction_expected(analysis.operation_advice),
                "eval_status": "insufficient_data",
                "eval_window_days": eval_window_days,
            }

        return self._evaluate_with_bars(
            analysis=analysis,
            analysis_date=start_daily.date,
            start_price=float(start_daily.close),
            forward_bars=forward_bars,
            eval_window_days=eval_window_days,
            neutral_band_pct=neutral_band_pct,
            engine_version=engine_version,
        )

    def _evaluate_with_bars(
        self,
        *,
        analysis: Any,
        analysis_date: date,
        start_price: float,
        forward_bars: Sequence[Any],
        eval_window_days: int,
        neutral_band_pct: float,
        engine_version: str,
    ) -> Dict[str, Any]:
        return self.ta_wrapper.evaluate(
            analysis,
            analysis_date=analysis_date,
            start_price=start_price,
            forward_bars=forward_bars,
            eval_window_days=eval_window_days,
            neutral_band_pct=neutral_band_pct,
            engine_version=engine_version,
        )
