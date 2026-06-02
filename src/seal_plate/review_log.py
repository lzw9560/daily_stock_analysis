"""
复盘分析日志存储

持久化 LLM 复盘分析结果，追踪策略演化历程。
每次复盘生成一个独立的分析报告，记录当日的策略参数快照和 LLM 建议。
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
class ReviewSnapshot:
    """策略快照（复盘时的参数状态）"""
    min_score_threshold: int = 65
    confidence_threshold: str = "中"
    max_daily_recommendations: int = 5
    high_win_sectors: list[str] = field(default_factory=list)
    low_win_sectors: list[str] = field(default_factory=list)


@dataclass
class ReviewLog:
    """每日复盘分析日志"""
    date: str
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # LLM 洞察（来自 LLMReviewer）
    summary: str = ""
    overall_assessment: str = ""
    success_patterns: list[str] = field(default_factory=list)
    failure_patterns: list[str] = field(default_factory=list)
    high_momentum_sectors: list[str] = field(default_factory=list)
    risk_sectors: list[str] = field(default_factory=list)
    strategy_adjustments: list[str] = field(default_factory=list)
    score_weight_suggestions: list[str] = field(default_factory=list)
    position_advice: str = ""

    # 策略参数调整历史
    recommended_min_score: int = 65
    recommended_confidence_threshold: str = "中"
    max_daily_recommendations: int = 5

    # 复盘时的策略快照
    snapshot: Optional[ReviewSnapshot] = None

    # 附加统计
    settled_count: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0

    # 元信息
    model_used: str = ""

    # 手动备注（用户可以追加）
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "generated_at": self.generated_at,
            "summary": self.summary,
            "overall_assessment": self.overall_assessment,
            "success_patterns": self.success_patterns,
            "failure_patterns": self.failure_patterns,
            "high_momentum_sectors": self.high_momentum_sectors,
            "risk_sectors": self.risk_sectors,
            "strategy_adjustments": self.strategy_adjustments,
            "score_weight_suggestions": self.score_weight_suggestions,
            "position_advice": self.position_advice,
            "recommended_min_score": self.recommended_min_score,
            "recommended_confidence_threshold": self.recommended_confidence_threshold,
            "max_daily_recommendations": self.max_daily_recommendations,
            "snapshot": {
                "min_score_threshold": self.snapshot.min_score_threshold,
                "confidence_threshold": self.snapshot.confidence_threshold,
                "max_daily_recommendations": self.snapshot.max_daily_recommendations,
                "high_win_sectors": self.snapshot.high_win_sectors,
                "low_win_sectors": self.snapshot.low_win_sectors,
            } if self.snapshot else None,
            "settled_count": self.settled_count,
            "win_rate": self.win_rate,
            "avg_return": self.avg_return,
            "model_used": self.model_used,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewLog":
        snapshot = None
        if data.get("snapshot"):
            s = data["snapshot"]
            snapshot = ReviewSnapshot(
                min_score_threshold=s.get("min_score_threshold", 65),
                confidence_threshold=s.get("confidence_threshold", "中"),
                max_daily_recommendations=s.get("max_daily_recommendations", 5),
                high_win_sectors=s.get("high_win_sectors", []),
                low_win_sectors=s.get("low_win_sectors", []),
            )

        return cls(
            date=data.get("date", ""),
            generated_at=data.get("generated_at", ""),
            summary=data.get("summary", ""),
            overall_assessment=data.get("overall_assessment", ""),
            success_patterns=data.get("success_patterns", []),
            failure_patterns=data.get("failure_patterns", []),
            high_momentum_sectors=data.get("high_momentum_sectors", []),
            risk_sectors=data.get("risk_sectors", []),
            strategy_adjustments=data.get("strategy_adjustments", []),
            score_weight_suggestions=data.get("score_weight_suggestions", []),
            position_advice=data.get("position_advice", ""),
            recommended_min_score=data.get("recommended_min_score", 65),
            recommended_confidence_threshold=data.get("recommended_confidence_threshold", "中"),
            max_daily_recommendations=data.get("max_daily_recommendations", 5),
            snapshot=snapshot,
            settled_count=data.get("settled_count", 0),
            win_rate=data.get("win_rate", 0.0),
            avg_return=data.get("avg_return", 0.0),
            model_used=data.get("model_used", ""),
            notes=data.get("notes", ""),
        )


class ReviewLogStore:
    """复盘分析日志存储"""

    def __init__(self, base_dir: str = "reports/seal_plate/reviews"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, date: str) -> str:
        return os.path.join(self.base_dir, f"review_{date}.json")

    def save(self, insight) -> None:
        """保存复盘分析结果"""
        if hasattr(insight, 'to_dict'):
            data = insight.to_dict()
        else:
            data = insight

        path = self._path(data.get("date", ""))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("复盘分析已保存: %s", path)

    def load(self, date: str) -> Optional[dict]:
        """加载指定日期的复盘分析"""
        path = self._path(date)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("加载复盘分析失败 %s: %s", date, e)
            return None

    def load_all(self, limit: int = 60) -> list[dict]:
        """加载所有复盘分析（按日期倒序）"""
        results: list[dict] = []
        if not os.path.exists(self.base_dir):
            return results

        files = sorted(
            [f for f in os.listdir(self.base_dir) if f.endswith(".json")],
            reverse=True,
        )[:limit]

        for f in files:
            path = os.path.join(self.base_dir, f)
            try:
                with open(path, "r", encoding="utf-8") as fp:
                    results.append(json.load(fp))
            except Exception as e:
                logger.warning("读取复盘分析文件失败 %s: %s", f, e)

        return results

    def update_notes(self, date: str, notes: str) -> bool:
        """更新复盘备注"""
        data = self.load(date)
        if not data:
            return False
        data["notes"] = notes
        self.save(data)
        return True

    def get_strategy_evolution(self, limit: int = 30) -> list[dict]:
        """获取策略演化时间线（用于追踪参数变化）"""
        all_reviews = self.load_all(limit=limit)
        evolution: list[dict] = []

        for review in reversed(all_reviews):  # 从旧到新
            evolution.append({
                "date": review.get("date", ""),
                "min_score": review.get("recommended_min_score", 65),
                "confidence": review.get("recommended_confidence_threshold", "中"),
                "max_recs": review.get("max_daily_recommendations", 5),
                "win_rate": review.get("win_rate", 0),
                "summary": review.get("summary", ""),
                "adjustments": review.get("strategy_adjustments", []),
            })

        return evolution
