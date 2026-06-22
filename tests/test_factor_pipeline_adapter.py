# -*- coding: utf-8 -*-
"""Tests for factor pipeline adapters."""

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


class FactorBackendAdapterTestCase(unittest.TestCase):
    def test_detect_backend_falls_back_when_deps_missing(self) -> None:
        with patch("src.services.factor_pipeline_adapters.__import__", side_effect=ModuleNotFoundError):
            adapter = FactorBackendAdapter()
            self.assertEqual(adapter.backend, "skeleton")

    def test_build_skeleton_factor_rows(self) -> None:
        adapter = FactorBackendAdapter()
        rows = adapter.build_factor_rows(
            screening_date=date(2024, 1, 2),
            strategy="dual_low",
            candidate_code="600519",
            candidate_rank=1,
            factor_specs=[{"name": "alpha158_1"}, {"name": "alpha360_20"}],
        )
        self.assertIn(rows["backend"], {"real", "skeleton"})
        self.assertIn("factor_scores", rows)
        self.assertIn("training_summary", rows)
        self.assertIn("monitoring_summary", rows)


class FactorPipelineServiceAdapterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_factor_pipeline_adapter.db")
        os.environ["DATABASE_PATH"] = self._db_path
        os.environ["FACTOR_PIPELINE_ENABLED"] = "true"

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

    def test_pipeline_persists_factor_payload(self) -> None:
        service = FactorPipelineService(self.db)
        result = service.run_for_screening_record(1, market="cn", screening_date=date(2024, 1, 2))

        self.assertEqual(result["status"], "completed")
        self.assertIn(result["backend"], {"real", "skeleton"})
        self.assertEqual(result["monitoring"]["sample_size"], 1)

        with self.db.get_session() as session:
            candidate = session.query(ScreeningCandidate).filter(ScreeningCandidate.code == "600519").one()
            self.assertIsNotNone(candidate.factor_scores_json)
            self.assertIn("factor_scores", candidate.factor_scores_json)


if __name__ == "__main__":
    unittest.main()
