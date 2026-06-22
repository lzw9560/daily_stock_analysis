# -*- coding: utf-8 -*-
"""Tests for backtest optimization endpoint/service."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime

from src.config import Config
from src.services.backtest_service import BacktestService
from src.storage import AnalysisHistory, DatabaseManager, StockDaily


class BacktestOptimizationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_backtest_optimization.db")
        os.environ["DATABASE_PATH"] = self._db_path
        os.environ["BACKTEST_EVAL_WINDOW_DAYS"] = "3"
        os.environ["BACKTEST_ENGINE_VERSION"] = "v1"

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

        with self.db.get_session() as session:
            session.add(
                AnalysisHistory(
                    query_id="q-opt-1",
                    code="600519",
                    name="贵州茅台",
                    report_type="simple",
                    sentiment_score=80,
                    operation_advice="买入",
                    trend_prediction="看多",
                    analysis_summary="opt",
                    stop_loss=95.0,
                    take_profit=110.0,
                    created_at=datetime(2024, 1, 1, 0, 0, 0),
                    context_snapshot='{"enhanced_context": {"date": "2024-01-01"}}',
                )
            )
            session.add(StockDaily(code="600519", date=date(2024, 1, 1), high=101.0, low=99.0, close=100.0))
            session.add_all([
                StockDaily(code="600519", date=date(2024, 1, 2), high=111.0, low=100.0, close=105.0),
                StockDaily(code="600519", date=date(2024, 1, 3), high=108.0, low=103.0, close=106.0),
                StockDaily(code="600519", date=date(2024, 1, 4), high=109.0, low=104.0, close=107.0),
            ])
            session.commit()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    def test_optimize_backtest_returns_grid_results(self) -> None:
        service = BacktestService(self.db)
        with unittest.mock.patch.object(service.vbt_engine, "optimize_default_grid", wraps=service.vbt_engine.optimize_default_grid) as mocked_optimize:
            result = service.optimize_backtest(code="600519", eval_window_days=3, min_age_days=0, limit=10)

        self.assertEqual(result["score_key"], "score")
        self.assertEqual(result["combinations"], 5000)
        self.assertIsNotNone(result["best"])
        self.assertGreaterEqual(len(result["results"]), 1)
        self.assertEqual(mocked_optimize.call_count, 1)


if __name__ == "__main__":
    unittest.main()
