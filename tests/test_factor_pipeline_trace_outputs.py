# -*- coding: utf-8 -*-
"""Tests for factor pipeline traces and configurable windows."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime

from src.config import Config
from src.services.factor_pipeline_service import FactorPipelineService
from src.storage import DatabaseManager, ScreeningCandidate, ScreeningRecord


class FactorPipelineTraceOutputsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_factor_pipeline_trace_outputs.db")
        os.environ["DATABASE_PATH"] = self._db_path
        os.environ["FACTOR_PIPELINE_ENABLED"] = "true"
        os.environ["FACTOR_PIPELINE_TRAIN_DAYS"] = "365"
        os.environ["FACTOR_PIPELINE_VALID_DAYS"] = "60"
        os.environ["FACTOR_PIPELINE_TEST_DAYS"] = "30"
        os.environ["FACTOR_PIPELINE_SHAP_SAMPLE_SIZE"] = "16"
        os.environ["FACTOR_PIPELINE_INSTRUMENTS"] = "csi300"
        os.environ["FACTOR_QLIB_REGION"] = "cn"

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

        with self.db.get_session() as session:
            session.add(
                ScreeningRecord(
                    screening_date=date(2024, 1, 2),
                    strategy="dual_low",
                    market="cn",
                    candidate_count=1,
                    status="completed",
                    duration_seconds=1.2,
                    run_id="run-1",
                )
            )
            session.flush()
            record_id = session.query(ScreeningRecord.id).filter(ScreeningRecord.strategy == "dual_low").scalar()
            session.add(
                ScreeningCandidate(
                    screening_record_id=record_id,
                    rank=1,
                    code="600519",
                    name="贵州茅台",
                    score=88.0,
                )
            )
            session.commit()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    def test_traces_include_runtime_window(self) -> None:
        service = FactorPipelineService(self.db)
        result = service.run_for_screening_record(1, market="cn", screening_date=date(2024, 1, 2))

        self.assertEqual(result["status"], "completed")
        self.assertIn("runtime_window", result)
        self.assertIn("traces", result)
        self.assertEqual(result["runtime_window"]["train_days"], 365)
        self.assertEqual(result["runtime_window"]["valid_days"], 60)
        self.assertEqual(result["runtime_window"]["test_days"], 30)
        self.assertEqual(result["runtime_window"]["shap_sample_size"], 16)
        self.assertIn("backends_seen", result["traces"])
        self.assertIn("candidate_traces", result["traces"])
        self.assertGreaterEqual(len(result["traces"]["candidate_traces"]), 1)

    def test_get_record_factor_pipeline_returns_traces(self) -> None:
        service = FactorPipelineService(self.db)
        result = service.get_screening_record_factor_pipeline(1)
        self.assertEqual(result["status"], "empty")
        self.assertIn("traces", result)
        self.assertEqual(result["traces"]["runtime_window"]["train_days"], 365)


if __name__ == "__main__":
    unittest.main()
