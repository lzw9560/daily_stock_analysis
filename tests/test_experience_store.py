# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services.experience_store import ExperienceStore
from src.storage import DatabaseManager


class ExperienceStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "experience.sqlite3"
        self.db_url = f"sqlite:///{self.db_path}"

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self.tmpdir.cleanup()

    def test_save_and_list_recent(self) -> None:
        with patch("src.storage.get_config") as mock_config:
            mock_config.return_value.get_db_url.return_value = self.db_url
            mock_config.return_value.sqlite_wal_enabled = False
            mock_config.return_value.sqlite_busy_timeout_ms = 0
            mock_config.return_value.sqlite_write_retry_max = 0
            mock_config.return_value.sqlite_write_retry_base_delay = 0
            db = DatabaseManager.get_instance()

        store = ExperienceStore()
        store.save(
            session_id="session-1",
            query_id="query-1",
            stock_code="600519",
            mode="debate",
            stage="research",
            payload={"signal": "buy", "reasoning": "hypothesis"},
            score=0.8,
        )

        entries = store.list_recent("600519", mode="debate", limit=10)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].query_id, "query-1")
        self.assertEqual(entries[0].stage, "research")
        self.assertEqual(entries[0].payload["signal"], "buy")
        self.assertAlmostEqual(entries[0].score or 0.0, 0.8)
