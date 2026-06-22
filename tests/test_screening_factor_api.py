# -*- coding: utf-8 -*-
"""Tests for screening factor pipeline API exposure."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime

from src.config import Config
from src.services.factor_pipeline_service import FactorPipelineService
from src.services.screening_service import ScreeningService
from src.storage import DatabaseManager, ScreeningCandidate, ScreeningRecord


class ScreeningFactorApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._temp_dir.name, "test_screening_factor_api.db")
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

        FactorPipelineService(self.db).run_for_screening_record(1, market="cn", screening_date=date(2024, 1, 2))

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self._temp_dir.cleanup()

    def test_screening_records_expose_factor_pipeline_overview(self) -> None:
        service = ScreeningService(self.db)
        records = service.get_records(limit=10, offset=0)

        self.assertEqual(records["total"], 1)
        self.assertEqual(records["records"][0]["factor_pipeline"]["status"], "completed")
        self.assertEqual(records["records"][0]["factor_pipeline"]["candidate_count"], 1)

    def test_screening_record_detail_exposes_factor_pipeline_overview(self) -> None:
        service = ScreeningService(self.db)
        detail = service.get_record_detail(1)

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["factor_pipeline"]["status"], "completed")
        self.assertEqual(detail["factor_pipeline"]["candidate_count"], 1)


if __name__ == "__main__":
    unittest.main()
