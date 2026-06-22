# -*- coding: utf-8 -*-
"""Tests for vectorized backtest helpers."""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import date, timedelta
from unittest.mock import MagicMock

from src.core.vbt_engine import GridOptimizer, VbtEngine


@dataclass
class Bar:
    date: date
    high: float
    low: float
    close: float


@dataclass
class Analysis:
    code: str
    operation_advice: str
    stop_loss: float | None = None
    take_profit: float | None = None


class VbtEngineTestCase(unittest.TestCase):
    def _series(self, start: date, closes):
        return [Bar(date=start + timedelta(days=i), high=c + 1, low=c - 1, close=c) for i, c in enumerate(closes)]

    def test_evaluate_batch_prefetches_once_per_code(self) -> None:
        analyses = [
            Analysis(code="600519", operation_advice="买入", stop_loss=95, take_profit=110),
            Analysis(code="600519", operation_advice="买入", stop_loss=95, take_profit=110),
        ]
        stock_repo = MagicMock()
        stock_repo.get_range.return_value = self._series(date(2024, 1, 1), [100, 101, 102, 103, 104, 105])
        engine = VbtEngine(stock_repo, lambda analysis: date(2024, 1, 1), lambda *args, **kwargs: None)

        results = engine.evaluate_batch(
            analyses,
            eval_window_days=3,
            neutral_band_pct=2.0,
            engine_version="v1",
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(stock_repo.get_range.call_count, 1)
        self.assertTrue(all(result["eval_status"] == "completed" for result in results))

    def test_optimize_batch_uses_grid_optimizer(self) -> None:
        stock_repo = MagicMock()
        engine = VbtEngine(stock_repo, lambda analysis: date(2024, 1, 1), lambda *args, **kwargs: None)

        report = engine.optimize_batch(
            [Analysis(code="600519", operation_advice="买入")],
            grid={"window": [3, 5]},
            evaluator=lambda analysis, params: {"score": params["window"], "code": analysis.code},
        )

        self.assertEqual(report["combinations"], 2)
        self.assertEqual(report["best"]["score"], 5)
        self.assertEqual(report["best"]["params"]["window"], 5)

    def test_default_grid_has_5000_combinations(self) -> None:
        engine = VbtEngine(MagicMock(), lambda analysis: date(2024, 1, 1), lambda *args, **kwargs: None)
        grid = engine.ta_wrapper.build_default_grid()

        combinations = 1
        for values in grid.values():
            combinations *= len(values)

        self.assertEqual(combinations, 5000)


if __name__ == "__main__":
    unittest.main()
