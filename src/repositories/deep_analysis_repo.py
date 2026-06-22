# -*- coding: utf-8 -*-
"""深度分析任务数据访问层 — TradingAgents 分析任务持久化."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, select

from src.storage import DatabaseManager, DeepAnalysisTask

logger = logging.getLogger(__name__)

# 任务过期时间（秒）
_TASK_EXPIRY_SECONDS = 3600 * 2


class DeepAnalysisRepository:
    """深度分析任务 Repository — SQLite 持久化."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    # ── 写入 ────────────────────────────────────────────────────────────────

    def create_task(self, task_id: str, ticker: str, trade_date: str) -> DeepAnalysisTask:
        """创建新任务记录."""
        with self.db.session_scope() as session:
            task = DeepAnalysisTask(
                task_id=task_id,
                ticker=ticker,
                trade_date=trade_date,
                status="pending",
                started_at=datetime.now(),
            )
            session.add(task)
            session.commit()
            return task

    def update_task(self, task_id: str, **fields) -> Optional[DeepAnalysisTask]:
        """更新任务字段."""
        with self.db.session_scope() as session:
            task = session.execute(
                select(DeepAnalysisTask).where(DeepAnalysisTask.task_id == task_id)
            ).scalar_one_or_none()
            if not task:
                return None
            # JSON 字段自动序列化（映射到 ORM 的 *_json 列）
            _json_fields: Dict[str, str] = {
                "stats": "stats_json",
                "stage_reports": "stage_reports_json",
                "completed_stages": "completed_stages_json",
            }
            for key, value in fields.items():
                if key in _json_fields and isinstance(value, (dict, list)):
                    setattr(task, _json_fields[key], json.dumps(value, ensure_ascii=False))
                else:
                    setattr(task, key, value)
            session.commit()
            return task

    # ── 查询 ────────────────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """查询单个任务."""
        with self.db.session_scope() as session:
            task = session.execute(
                select(DeepAnalysisTask).where(DeepAnalysisTask.task_id == task_id)
            ).scalar_one_or_none()
            return self._to_dict(task) if task else None

    def list_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """列出当前活跃任务（最近创建，排除过期）."""
        with self.db.session_scope() as session:
            tasks = session.execute(
                select(DeepAnalysisTask)
                .where(DeepAnalysisTask.status.in_(["pending", "running"]))
                .order_by(desc(DeepAnalysisTask.started_at))
                .limit(limit)
            ).scalars().all()

            # 同时获取最近完成的任务
            completed = session.execute(
                select(DeepAnalysisTask)
                .where(DeepAnalysisTask.status.in_(["completed", "failed"]))
                .order_by(desc(DeepAnalysisTask.started_at))
                .limit(limit)
            ).scalars().all()

            all_tasks = list(tasks) + list(completed)
            # 去重 + 排序
            seen: set[str] = set()
            result: List[Dict[str, Any]] = []
            for t in sorted(all_tasks, key=lambda x: x.started_at if x.started_at else datetime.min, reverse=True):
                if t.task_id not in seen:
                    seen.add(t.task_id)
                    result.append(self._to_dict(t))
            return result[:limit]

    def cleanup_expired(self) -> int:
        """清理超过 2 小时的 pending/running 任务（标记为 failed）."""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(seconds=_TASK_EXPIRY_SECONDS)
        with self.db.session_scope() as session:
            expired = session.execute(
                select(DeepAnalysisTask).where(
                    and_(
                        DeepAnalysisTask.status.in_(["pending", "running"]),
                        DeepAnalysisTask.started_at < cutoff,
                    )
                )
            ).scalars().all()
            count = 0
            for t in expired:
                t.status = "failed"
                t.error = "任务超时（超过2小时未完成）"
                t.elapsed = _TASK_EXPIRY_SECONDS
                count += 1
            session.commit()
            return count

    def find_existing_task(self, ticker: str, trade_date: str) -> Optional[Dict[str, Any]]:
        """查找同一标的、同一日期已有的活跃/已完成任务."""
        with self.db.session_scope() as session:
            task = session.execute(
                select(DeepAnalysisTask).where(
                    and_(
                        DeepAnalysisTask.ticker == ticker,
                        DeepAnalysisTask.trade_date == trade_date,
                        DeepAnalysisTask.status.in_(["pending", "running", "completed"]),
                    )
                )
            ).scalar_one_or_none()
            return self._to_dict(task) if task else None

    def delete_task(self, task_id: str) -> bool:
        """删除指定任务（物理删除）."""
        with self.db.session_scope() as session:
            task = session.execute(
                select(DeepAnalysisTask).where(DeepAnalysisTask.task_id == task_id)
            ).scalar_one_or_none()
            if not task:
                return False
            session.delete(task)
            session.commit()
            return True

    # ── 内部工具 ────────────────────────────────────────────────────────────

    @staticmethod
    def _to_dict(task: DeepAnalysisTask) -> Dict[str, Any]:
        """将 ORM 对象转为字典."""
        stage_reports: Dict[str, str] = {}
        raw_reports = task.stage_reports_json
        if raw_reports:
            try:
                stage_reports = json.loads(raw_reports)
            except json.JSONDecodeError:
                pass

        completed_stages: List[str] = []
        raw_stages = task.completed_stages_json
        if raw_stages:
            try:
                completed_stages = json.loads(raw_stages)
            except json.JSONDecodeError:
                pass

        stats: Dict[str, int] = {}
        raw_stats = task.stats_json
        if raw_stats:
            try:
                stats = json.loads(raw_stats)
            except json.JSONDecodeError:
                pass

        return {
            "task_id": task.task_id,
            "ticker": task.ticker,
            "trade_date": task.trade_date,
            "status": task.status,
            "signal": task.signal or "",
            "current_stage": task.current_stage or "",
            "completed_stages": completed_stages,
            "stage_reports": stage_reports,
            "stats": stats,
            "elapsed": task.elapsed or 0,
            "error": task.error or "",
            "report_path": task.report_path or "",
            "started_at": task.started_at.isoformat() if task.started_at else "",
        }
