# -*- coding: utf-8 -*-
"""SQLite-backed experience store for agent debate runs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select

from src.storage import ExperienceRecord, get_db

logger = logging.getLogger(__name__)


@dataclass
class ExperienceEntry:
    id: int
    session_id: str
    query_id: str
    stock_code: str
    mode: str
    stage: str
    payload: Dict[str, Any]
    score: Optional[float]
    created_at: datetime


class ExperienceStore:
    """Persist and retrieve debate experience snapshots."""

    def save(
        self,
        *,
        session_id: str,
        query_id: str,
        stock_code: str,
        mode: str,
        stage: str,
        payload: Dict[str, Any],
        score: Optional[float] = None,
    ) -> None:
        db = get_db()
        with db.session_scope() as session:
            session.add(
                ExperienceRecord(
                    session_id=session_id,
                    query_id=query_id,
                    stock_code=stock_code,
                    mode=mode,
                    stage=stage,
                    payload=json.dumps(payload, ensure_ascii=False, default=str),
                    score=score,
                )
            )

    def list_recent(
        self,
        stock_code: str,
        *,
        mode: Optional[str] = None,
        limit: int = 20,
    ) -> List[ExperienceEntry]:
        db = get_db()
        with db.session_scope() as session:
            stmt = select(ExperienceRecord).where(ExperienceRecord.stock_code == stock_code)
            if mode:
                stmt = stmt.where(ExperienceRecord.mode == mode)
            stmt = stmt.order_by(desc(ExperienceRecord.created_at), desc(ExperienceRecord.id)).limit(limit)
            rows = session.execute(stmt).scalars().all()
            entries: List[ExperienceEntry] = []
            for row in rows:
                payload: Dict[str, Any] = {}
                try:
                    parsed = json.loads(row.payload or "{}")
                    if isinstance(parsed, dict):
                        payload = parsed
                except (TypeError, ValueError):
                    payload = {}
                entries.append(
                    ExperienceEntry(
                        id=row.id,
                        session_id=row.session_id,
                        query_id=row.query_id,
                        stock_code=row.stock_code,
                        mode=row.mode,
                        stage=row.stage,
                        payload=payload,
                        score=row.score,
                        created_at=row.created_at,
                    )
                )
            return entries


_EXPERIENCE_STORE = ExperienceStore()


def get_experience_store() -> ExperienceStore:
    return _EXPERIENCE_STORE
