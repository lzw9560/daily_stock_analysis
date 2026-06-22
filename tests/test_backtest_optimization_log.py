# -*- coding: utf-8 -*-
"""Tests for persisted backtest optimization logs."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime

from src.config import Config
from src.services.backtest_service import BacktestService
from src.storage import AnalysisHistory, DatabaseManager, StockDaily


class BacktestOptimizationLogTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_backtest_optimization_log.db")
        os.environ["DATABASE_PATH"] = self._db_path
        os.environ["BACKTEST_EVAL_WINDOW_DAYS"] = "3"
        os.environ["BACKTEST_ENGINE_VERSION"] = "v1"

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

        with self.db.get_session() as session:
            session.add(
                AnalysisHistory(
                    query_id="q-opt-log-1",
                    code="600519",
                    name="贵州茅台",
                    report_type="simple",
                    sentiment_score=80,
                    operation_advice="买入",
                    trend_prediction="看多",
                    analysis_summary="opt-log",
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

    def test_optimize_backtest_persists_log(self) -> None:
        service = BacktestService(self.db)
        service.optimize_backtest(code="600519", eval_window_days=3, min_age_days=0, limit=10)

        logs = service.get_optimization_logs(code="600519", limit=10)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["combinations"], 5000)
        self.assertIsNotNone(logs[0]["best_params"])
        self.assertIsNotNone(logs[0]["best_result"])


if __name__ == "__main__":
    unittest.main()
