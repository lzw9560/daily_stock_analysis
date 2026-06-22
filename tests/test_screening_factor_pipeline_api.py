# -*- coding: utf-8 -*-
"""Tests for screening factor pipeline API endpoints."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime
from unittest.mock import patch

from api.v1.endpoints.screening import screening_factor_pipeline_run, screening_record_factor_pipeline
from api.v1.schemas.screening import FactorPipelineTriggerRequest
from src.config import Config
from src.services.factor_pipeline_service import FactorPipelineService
from src.storage import DatabaseManager, ScreeningCandidate, ScreeningRecord


class ScreeningFactorPipelineApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_screening_factor_api.db")
        os.environ["DATABASE_PATH"] = self._db_path
        os.environ["FACTOR_PIPELINE_ENABLED"] = "true"

        Config._instance = None
        DatabaseManager.reset_instance()
        self.db = DatabaseManager.get_instance()

        with self.db.get_session() as session:
            record = ScreeningRecord(
                screening_date=date(2024, 1, 2),
                strategy="dual_low",
                market="cn",
                candidate_count=1,
                status="completed",
                duration_seconds=1.2,
                run_id="run-1",
            )
            session.add(record)
            session.flush()
            session.add(
                ScreeningCandidate(
                    screening_record_id=record.id,
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

    def test_trigger_factor_pipeline_endpoint_runs(self) -> None:
        request = FactorPipelineTriggerRequest(record_id=1, market="cn", screening_date="2024-01-02")
        response = screening_factor_pipeline_run(request)

        self.assertEqual(response.status, "completed")
        self.assertTrue(response.factor_pipeline_enabled)
        self.assertEqual(response.record_id, 1)
        self.assertEqual(response.monitoring["sample_size"], 1)

    def test_trigger_factor_pipeline_endpoint_respects_gate(self) -> None:
        os.environ["FACTOR_PIPELINE_ENABLED"] = "false"
        Config._instance = None
        request = FactorPipelineTriggerRequest(record_id=1, market="cn", screening_date="2024-01-02")
        with self.assertRaises(Exception):
            screening_factor_pipeline_run(request)

    def test_record_factor_pipeline_endpoint_reads_persisted_payload(self) -> None:
        service = FactorPipelineService(self.db)
        service.run_for_screening_record(1, market="cn", screening_date=date(2024, 1, 2))

        response = screening_record_factor_pipeline(1)
        self.assertEqual(response.record_id, 1)
        self.assertEqual(response.factor_pipeline["status"], "completed")
        self.assertEqual(response.factor_pipeline["record_id"], 1)
        self.assertIn("candidates", response.factor_pipeline)


if __name__ == "__main__":
    unittest.main()
