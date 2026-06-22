# -*- coding: utf-8 -*-
"""Typed payload helpers for screening persistence."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict, is_dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ScreeningCandidatePayload:
    rank: int
    code: str
    name: str = ""
    score: Optional[float] = None
    screen_score: Optional[float] = None
    llm_score: Optional[float] = None
    llm_confidence: Optional[float] = None
    reason: str = ""
    risk_level: str = ""
    risk_flags: List[str] = field(default_factory=list)
    llm_sector: str = ""
    llm_theme: str = ""
    llm_tags: List[str] = field(default_factory=list)
    llm_thesis: str = ""
    llm_catalysts: List[str] = field(default_factory=list)
    llm_risks: List[str] = field(default_factory=list)
    llm_watch_items: List[str] = field(default_factory=list)
    llm_invalidators: List[str] = field(default_factory=list)
    llm_style_fit: str = ""
    price: Optional[float] = None
    change_pct: Optional[float] = None
    amount: Optional[float] = None
    industry: str = ""
    factor_scores: Dict[str, float] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)
    factor_payload: Optional[Dict[str, Any]] = None

    def to_repo_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.factor_payload is None:
            data.pop("factor_payload", None)
        return data


@dataclass(frozen=True)
class ScreeningCandidateBatchPayload:
    record_id: int
    candidates: List[ScreeningCandidatePayload]

    def to_repo_list(self) -> List[Dict[str, Any]]:
        return [candidate.to_repo_dict() for candidate in self.candidates]
