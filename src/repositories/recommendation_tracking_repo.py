# -*- coding: utf-8 -*-
"""历史推荐追踪数据访问层 — RecommendationRecord 持久化."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func, select

from src.storage import DatabaseManager, RecommendationRecord

logger = logging.getLogger(__name__)


class RecommendationTrackingRepository:
    """历史推荐追踪 Repository — SQLite 持久化."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    # ── 写入 ────────────────────────────────────────────────────────────────

    def create(self, **fields) -> RecommendationRecord:
        """创建推荐记录."""
        with self.db.session_scope() as session:
            session.expire_on_commit = False
            record = RecommendationRecord(**fields)
            session.add(record)
            session.commit()
            return record

    def update(self, record_id: int, **fields) -> Optional[RecommendationRecord]:
        """更新推荐记录字段."""
        with self.db.session_scope() as session:
            record = session.execute(
                select(RecommendationRecord).where(RecommendationRecord.id == record_id)
            ).scalar_one_or_none()
            if not record:
                return None
            for key, value in fields.items():
                setattr(record, key, value)
            session.commit()
            return record

    def delete(self, record_id: int) -> bool:
        """删除推荐记录."""
        with self.db.session_scope() as session:
            record = session.execute(
                select(RecommendationRecord).where(RecommendationRecord.id == record_id)
            ).scalar_one_or_none()
            if not record:
                return False
            session.delete(record)
            session.commit()
            return True

    # ── 查询 ────────────────────────────────────────────────────────────────

    def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """按 ID 查询单条记录."""
        with self.db.session_scope() as session:
            record = session.execute(
                select(RecommendationRecord).where(RecommendationRecord.id == record_id)
            ).scalar_one_or_none()
            return self._to_dict(record) if record else None

    def find_by_code_and_date(
        self,
        code: str,
        trade_date: str,
        status: Optional[str] = None,
        limit: int = 1,
    ) -> List[Dict[str, Any]]:
        """按标的和日期查询推荐记录（用于回测反馈匹配）."""
        with self.db.session_scope() as session:
            conditions = [
                RecommendationRecord.code == code,
                RecommendationRecord.trade_date == trade_date,
            ]
            if status:
                conditions.append(RecommendationRecord.status == status)

            query = (
                select(RecommendationRecord)
                .where(and_(*conditions))
                .order_by(desc(RecommendationRecord.recommendation_time))
                .limit(limit)
            )
            records = session.execute(query).scalars().all()
            return [self._to_dict(r) for r in records]

    def list_records(
        self,
        code: Optional[str] = None,
        status: Optional[str] = None,
        signal: Optional[str] = None,
        source: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """分页查询推荐记录列表."""
        with self.db.session_scope() as session:
            conditions = []
            if code:
                conditions.append(RecommendationRecord.code == code)
            if status:
                conditions.append(RecommendationRecord.status == status)
            if signal:
                conditions.append(RecommendationRecord.signal == signal)
            if source:
                conditions.append(RecommendationRecord.source == source)
            if start_date:
                conditions.append(RecommendationRecord.trade_date >= start_date)
            if end_date:
                conditions.append(RecommendationRecord.trade_date <= end_date)

            base_query = select(RecommendationRecord)
            if conditions:
                base_query = base_query.where(and_(*conditions))

            # 总数
            total = session.execute(
                select(func.count()).select_from(base_query.subquery())
            ).scalar() or 0

            # 分页
            query = base_query.order_by(
                desc(RecommendationRecord.recommendation_time)
            ).offset((page - 1) * limit).limit(limit)

            records = session.execute(query).scalars().all()

            return {
                "total": total,
                "page": page,
                "limit": limit,
                "items": [self._to_dict(r) for r in records],
            }

    def get_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """统计推荐胜率与偏差数据."""
        with self.db.session_scope() as session:
            conditions = []
            if start_date:
                conditions.append(RecommendationRecord.trade_date >= start_date)
            if end_date:
                conditions.append(RecommendationRecord.trade_date <= end_date)

            # 全部记录
            all_query = select(RecommendationRecord)
            # 已平仓记录
            closed_query = select(RecommendationRecord).where(
                RecommendationRecord.status == "closed"
            )
            # 活跃记录
            active_query = select(RecommendationRecord).where(
                RecommendationRecord.status == "active"
            )

            if conditions:
                all_query = all_query.where(and_(*conditions))
                closed_query = closed_query.where(and_(*conditions))
                active_query = active_query.where(and_(*conditions))

            all_records = session.execute(all_query).scalars().all()
            closed_records = session.execute(closed_query).scalars().all()
            active_records = session.execute(active_query).scalars().all()

            # 胜率统计（仅已平仓）
            total_closed = len(closed_records)
            win_count = 0
            loss_count = 0
            total_pl = 0.0
            win_pl_total = 0.0
            loss_pl_total = 0.0
            max_win_pct = 0.0
            max_loss_pct = 0.0

            for r in closed_records:
                pl = r.profit_loss_pct or 0
                total_pl += pl
                if pl > 0:
                    win_count += 1
                    win_pl_total += pl
                    if pl > max_win_pct:
                        max_win_pct = pl
                else:
                    loss_count += 1
                    loss_pl_total += pl
                    if pl < max_loss_pct:
                        max_loss_pct = pl

            win_rate = (win_count / total_closed * 100) if total_closed > 0 else 0
            avg_pl = total_pl / total_closed if total_closed > 0 else 0
            avg_win_pl = win_pl_total / win_count if win_count > 0 else 0
            avg_loss_pl = loss_pl_total / loss_count if loss_count > 0 else 0
            profit_factor = abs(win_pl_total / loss_pl_total) if loss_pl_total != 0 else (999 if win_pl_total > 0 else 0)

            # 按方向分拆
            by_signal: Dict[str, Any] = {}
            for sig in ["buy", "sell", "hold"]:
                sig_records = [r for r in closed_records if r.signal == sig]
                sig_total = len(sig_records)
                sig_win = sum(1 for r in sig_records if (r.profit_loss_pct or 0) > 0)
                sig_pl = sum(r.profit_loss_pct or 0 for r in sig_records)
                by_signal[sig] = {
                    "total": sig_total,
                    "wins": sig_win,
                    "win_rate": round(sig_win / sig_total * 100, 1) if sig_total > 0 else 0,
                    "avg_pl_pct": round(sig_pl / sig_total, 2) if sig_total > 0 else 0,
                }

            # 按来源分拆
            by_source: Dict[str, Any] = {}
            for r in closed_records:
                src = r.source or "unknown"
                if src not in by_source:
                    by_source[src] = {"total": 0, "wins": 0, "total_pl": 0.0}
                by_source[src]["total"] += 1
                by_source[src]["total_pl"] += (r.profit_loss_pct or 0)
                if (r.profit_loss_pct or 0) > 0:
                    by_source[src]["wins"] += 1

            for src, data in by_source.items():
                data["win_rate"] = round(data["wins"] / data["total"] * 100, 1) if data["total"] > 0 else 0
                data["avg_pl_pct"] = round(data["total_pl"] / data["total"], 2) if data["total"] > 0 else 0

            # 活跃持仓偏差汇总
            active_deviation: List[Dict[str, Any]] = []
            for r in active_records:
                if r.current_price and r.recommendation_price:
                    deviation = (r.current_price - r.recommendation_price) / r.recommendation_price * 100
                    active_deviation.append({
                        "id": r.id,
                        "code": r.code,
                        "trade_date": r.trade_date,
                        "signal": r.signal,
                        "recommendation_price": r.recommendation_price,
                        "current_price": r.current_price,
                        "deviation_pct": round(deviation, 2),
                    })

            # 按战法分类统计
            by_strategy: Dict[str, Any] = {}
            for r in closed_records:
                pattern = (r.strategy_pattern or "unknown").strip() or "unknown"
                if pattern not in by_strategy:
                    by_strategy[pattern] = {"total": 0, "wins": 0, "total_pl": 0.0}
                by_strategy[pattern]["total"] += 1
                by_strategy[pattern]["total_pl"] += (r.profit_loss_pct or 0)
                if (r.profit_loss_pct or 0) > 0:
                    by_strategy[pattern]["wins"] += 1

            for pattern, data in by_strategy.items():
                data["win_rate"] = round(data["wins"] / data["total"] * 100, 1) if data["total"] > 0 else 0
                data["avg_pl_pct"] = round(data["total_pl"] / data["total"], 2) if data["total"] > 0 else 0

            # 按情绪阶段统计
            by_sentiment: Dict[str, Any] = {}
            for r in closed_records:
                phase = (r.sentiment_phase or "unknown").strip() or "unknown"
                if phase not in by_sentiment:
                    by_sentiment[phase] = {"total": 0, "wins": 0, "total_pl": 0.0}
                by_sentiment[phase]["total"] += 1
                by_sentiment[phase]["total_pl"] += (r.profit_loss_pct or 0)
                if (r.profit_loss_pct or 0) > 0:
                    by_sentiment[phase]["wins"] += 1

            for phase, data in by_sentiment.items():
                data["win_rate"] = round(data["wins"] / data["total"] * 100, 1) if data["total"] > 0 else 0
                data["avg_pl_pct"] = round(data["total_pl"] / data["total"], 2) if data["total"] > 0 else 0

            return {
                "total_records": len(all_records),
                "active_count": len(active_records),
                "closed_count": total_closed,
                "win_rate": round(win_rate, 1),
                "win_count": win_count,
                "loss_count": loss_count,
                "avg_pl_pct": round(avg_pl, 2),
                "avg_win_pl_pct": round(avg_win_pl, 2),
                "avg_loss_pl_pct": round(avg_loss_pl, 2),
                "max_win_pct": round(max_win_pct, 2),
                "max_loss_pct": round(max_loss_pct, 2),
                "profit_factor": round(profit_factor, 2),
                "total_pl_pct": round(total_pl, 2),
                "by_signal": by_signal,
                "by_source": by_source,
                "by_strategy": by_strategy,
                "by_sentiment": by_sentiment,
                "active_deviation": active_deviation,
            }

    # ── 内部工具 ────────────────────────────────────────────────────────────

    @staticmethod
    def _to_dict(record: RecommendationRecord) -> Dict[str, Any]:
        """ORM 对象转字典."""
        return {
            "id": record.id,
            "code": record.code,
            "trade_date": record.trade_date,
            "recommendation_time": record.recommendation_time.isoformat() if record.recommendation_time else "",
            "signal": record.signal,
            "recommendation_price": record.recommendation_price,
            "current_price": record.current_price,
            "price_deviation_pct": record.price_deviation_pct,
            "status": record.status,
            "close_price": record.close_price,
            "close_date": record.close_date.isoformat() if record.close_date else None,
            "profit_loss_pct": record.profit_loss_pct,
            "source": record.source,
            "source_task_id": record.source_task_id,
            "reason": record.reason or "",
            "notes": record.notes or "",
            "created_at": record.created_at.isoformat() if record.created_at else "",
            "updated_at": record.updated_at.isoformat() if record.updated_at else "",
            # 新增字段
            "signal_type": record.signal_type or "technical",
            "strategy_pattern": record.strategy_pattern or "",
            "confidence": record.confidence or 0.0,
            "entry_method": record.entry_method or "market",
            "stop_loss": record.stop_loss,
            "take_profit": record.take_profit,
            "sectors": record.sectors or "",
            "sentiment_phase": record.sentiment_phase or "",
            "expected_hold_days": record.expected_hold_days,
            "time_horizon": record.time_horizon or "",
        }
