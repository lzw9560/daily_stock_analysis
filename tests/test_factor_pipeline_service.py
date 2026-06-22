# -*- coding: utf-8 -*-
"""Tests for factor pipeline skeleton."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime

from src.config import Config
from src.services.factor_pipeline_service import FactorPipelineService
from src.services.screening_service import ScreeningService
from src.storage import DatabaseManager, ScreeningCandidate, ScreeningRecord


class FactorPipelineServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_factor_pipeline.db")
        os.environ["DATABASE_PATH"] = self._db_path
        os.environ["FACTOR_PIPELINE_ENABLED"] = "false"
        os.environ["ALPHASIFT_ENABLED"] = "true"

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

    def test_disabled_factor_pipeline_returns_disabled_status(self) -> None:
        service = FactorPipelineService(self.db)
        result = service.run_for_screening_record(1, market="cn", screening_date=date(2024, 1, 2))

        self.assertEqual(result["status"], "disabled")
        self.assertFalse(result["factor_pipeline_enabled"])

    def test_enabled_factor_pipeline_persists_factor_scores(self) -> None:
        os.environ["FACTOR_PIPELINE_ENABLED"] = "true"
        Config._instance = None
        service = FactorPipelineService(self.db)
        result = service.run_for_screening_record(1, market="cn", screening_date=date(2024, 1, 2))

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["factor_pipeline_enabled"])
        self.assertEqual(result["monitoring"]["sample_size"], 1)

        with self.db.get_session() as session:
            candidate = session.query(ScreeningCandidate).filter(ScreeningCandidate.code == "600519").one()
            self.assertIsNotNone(candidate.factor_scores_json)
            self.assertIn("alpha158", candidate.factor_scores_json)

    def test_screening_service_attaches_factor_pipeline_result(self) -> None:
        os.environ["FACTOR_PIPELINE_ENABLED"] = "false"
        Config._instance = None
        service = ScreeningService(self.db)
        result = service._run_factor_pipeline_if_enabled(1, market="cn", screening_date=date(2024, 1, 2))

        self.assertEqual(result["status"], "disabled")


if __name__ == "__main__":
    unittest.main()
