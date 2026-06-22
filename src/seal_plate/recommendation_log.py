"""
打板助手推荐日志
持久化每日推荐记录，支持复盘与胜率追踪
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RecommendationItem:
    """单个推荐标的记录"""
    code: str
    name: str
    score: int
    change_pct: float
    seal_time: Optional[str]
    sector: Optional[str]
    reasons: list[str] = field(default_factory=list)
    # 事后追踪
    outcome: Optional[str] = None       # 未结算 / 成功 / 失败
    actual_return_pct: Optional[float] = None  # 实际收益率（次日表现）
    won: Optional[bool] = None          # 是否盈利
    review_note: Optional[str] = None   # 复盘备注


@dataclass
class RecommendationLog:
    """每日推荐日志"""
    date: str
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    sentiment_index: float = 50.0
    sentiment_phase: str = "中性"
    total_limit_up: int = 0
    recommendations: list[RecommendationItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "generated_at": self.generated_at,
            "sentiment_index": self.sentiment_index,
            "sentiment_phase": self.sentiment_phase,
            "total_limit_up": self.total_limit_up,
            "recommendations": [
                {
                    "code": r.code, "name": r.name,
                    "score": r.score, "change_pct": r.change_pct,
                    "seal_time": r.seal_time, "sector": r.sector,
                    "reasons": r.reasons,
                    "outcome": r.outcome,
                    "actual_return_pct": r.actual_return_pct,
                    "won": r.won,
                    "review_note": r.review_note,
                }
                for r in self.recommendations
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RecommendationLog":
        return cls(
            date=data["date"],
            generated_at=data.get("generated_at", ""),
            sentiment_index=data.get("sentiment_index", 50.0),
            sentiment_phase=data.get("sentiment_phase", "中性"),
            total_limit_up=data.get("total_limit_up", 0),
            recommendations=[
                RecommendationItem(
                    code=r["code"], name=r["name"],
                    score=r.get("score", 0),
                    change_pct=r.get("change_pct", 0),
                    seal_time=r.get("seal_time"),
                    sector=r.get("sector"),
                    reasons=r.get("reasons", []),
                    outcome=r.get("outcome"),
                    actual_return_pct=r.get("actual_return_pct"),
                    won=r.get("won"),
                    review_note=r.get("review_note"),
                )
                for r in data.get("recommendations", [])
            ],
        )


class RecommendationLogStore:
    """推荐日志存储管理"""

    def __init__(self, base_dir: str = "reports/seal_plate/recommendations"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, date: str) -> str:
        return os.path.join(self.base_dir, f"recommend_{date}.json")

    def save(self, log: RecommendationLog) -> None:
        """保存当日推荐日志（原子写入，防止截断）"""
        path = self._path(log.date)
        tmp_path = path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(log.to_dict(), f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)  # 原子替换
            logger.info("推荐日志已保存: %s", path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def load(self, date: str) -> Optional[RecommendationLog]:
        """加载指定日期的推荐日志"""
        path = self._path(date)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return RecommendationLog.from_dict(json.load(f))
        except Exception as e:
            logger.warning("加载推荐日志失败 %s: %s", date, e)
            return None

    def load_all(self, limit: int = 60) -> list[RecommendationLog]:
        """加载所有推荐日志（按日期倒序）"""
        logs: list[RecommendationLog] = []
        if not os.path.exists(self.base_dir):
            return logs

        files = sorted(
            [f for f in os.listdir(self.base_dir) if f.endswith(".json")],
            reverse=True,
        )[:limit]

        for f in files:
            path = os.path.join(self.base_dir, f)
            try:
                with open(path, "r", encoding="utf-8") as fp:
                    logs.append(RecommendationLog.from_dict(json.load(fp)))
            except Exception as e:
                logger.warning("读取日志文件失败 %s: %s", f, e)

        return logs

    def update_outcome(self, date: str, code: str, outcome: str,
                       actual_return: Optional[float] = None,
                       review_note: Optional[str] = None) -> bool:
        """更新某日某股票的推荐结果"""
        log = self.load(date)
        if not log:
            return False

        for r in log.recommendations:
            if r.code == code:
                r.outcome = outcome
                r.actual_return_pct = actual_return
                r.won = (actual_return or 0) > 0
                r.review_note = review_note
                self.save(log)
                return True
        return False
