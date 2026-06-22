# -*- coding: utf-8 -*-
"""Tests for factor pipeline runtime window and trace outputs."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime
from unittest.mock import patch

from src.config import Config
from src.services.factor_pipeline_adapters import FactorBackendAdapter
from src.services.factor_pipeline_service import FactorPipelineService
from src.storage import DatabaseManager, ScreeningCandidate, ScreeningRecord


class FactorPipelineRuntimeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_factor_pipeline_runtime.db")
        os.environ["DATABASE_PATH"] = self._db_path
        os.environ["FACTOR_PIPELINE_ENABLED"] = "true"
        os.environ["FACTOR_PIPELINE_TRAIN_DAYS"] = "365"
        os.environ["FACTOR_PIPELINE_VALID_DAYS"] = "60"
        os.environ["FACTOR_PIPELINE_TEST_DAYS"] = "30"
        os.environ["FACTOR_PIPELINE_SHAP_SAMPLE_SIZE"] = "32"
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

    def test_runtime_window_reads_config(self) -> None:
        service = FactorPipelineService(self.db)
        window = service.get_runtime_window()
        self.assertEqual(window["train_days"], 365)
        self.assertEqual(window["valid_days"], 60)
        self.assertEqual(window["test_days"], 30)
        self.assertEqual(window["shap_sample_size"], 32)

    def test_backend_payload_includes_traces_and_window(self) -> None:
        service = FactorPipelineService(self.db)
        adapter = FactorBackendAdapter()
        self.assertIn(adapter.backend, {"real", "skeleton"})

        result = service.run_for_screening_record(1, market="cn", screening_date=date(2024, 1, 2))
        self.assertEqual(result["status"], "completed")
        self.assertIn("runtime_window", result)
        self.assertIn("traces", result["candidates"][0])
        self.assertIn("training", result["candidates"][0])

    def test_real_backend_failure_falls_back_to_skeleton(self) -> None:
        service = FactorPipelineService(self.db)
        with patch.object(service.adapter, "backend", "real"):
            with patch.object(service.adapter, "_run_family_pipeline", side_effect=RuntimeError("boom")):
                result = service.run_for_screening_record(1, market="cn", screening_date=date(2024, 1, 2))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["training"]["backend"], "real")


if __name__ == "__main__":
    unittest.main()
