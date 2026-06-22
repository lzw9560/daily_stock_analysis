# -*- coding: utf-8 -*-
"""Fixed debate agents for Research → Battle → Consensus."""

from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from src.agent.agents.base_agent import BaseAgent
from src.agent.protocols import AgentContext, AgentOpinion
from src.agent.runner import try_parse_json
from src.services.experience_store import get_experience_store

logger = logging.getLogger(__name__)


def _experience_context(ctx: AgentContext) -> dict:
    query_id = str(ctx.meta.get("query_id") or ctx.session_id or ctx.query or "").strip()
    session_id = str(ctx.session_id or query_id or ctx.stock_code or "").strip()
    return {"query_id": query_id or session_id or ctx.stock_code or "unknown", "session_id": session_id or query_id or ctx.stock_code or "unknown"}


def _save_experience(ctx: AgentContext, stage: str, payload: dict, score: Optional[float] = None) -> None:
    try:
        store = get_experience_store()
        ref = _experience_context(ctx)
        store.save(
            session_id=ref["session_id"],
            query_id=ref["query_id"],
            stock_code=ctx.stock_code or "unknown",
            mode="debate",
            stage=stage,
            payload=payload,
            score=score,
        )
    except Exception:
        logger.debug("[DebateAgent] failed to save experience for %s", stage, exc_info=True)


class DebateResearchAgent(BaseAgent):
    max_steps = 3
    agent_name = "debate_research"

    def system_prompt(self, ctx: AgentContext) -> str:
        return """You are the Research stage. Build the strongest bullish or bearish hypothesis from available evidence. Output only JSON with keys: stage, hypothesis, evidence, confidence, score_adjustment, reasoning."""

    def build_user_message(self, ctx: AgentContext) -> str:
        return f"Research {ctx.stock_code} {ctx.stock_name or ''}. Focus on what is likely true and why."

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        parsed = try_parse_json(raw_text) or {}
        ctx.set_data("debate_research", parsed)
        _save_experience(ctx, "research", parsed, score=float(parsed.get("confidence", 0.5)))
        return AgentOpinion(
            agent_name=self.agent_name,
            signal=str(parsed.get("signal", "hold")),
            confidence=float(parsed.get("confidence", 0.5)),
            reasoning=str(parsed.get("reasoning", "")),
            raw_data=parsed,
        )


class DebateBattleAgent(BaseAgent):
    max_steps = 3
    agent_name = "debate_battle"

    def system_prompt(self, ctx: AgentContext) -> str:
        return """You are the Battle stage. Challenge the research hypothesis with the strongest objections and counterevidence. Output only JSON with keys: stage, objections, evidence, confidence, score_adjustment, reasoning."""

    def build_user_message(self, ctx: AgentContext) -> str:
        research = ctx.get_data("debate_research", {})
        return f"Battle the research hypothesis for {ctx.stock_code}. Prior research: {json.dumps(research, ensure_ascii=False, default=str)[:4000]}"

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        parsed = try_parse_json(raw_text) or {}
        ctx.set_data("debate_battle", parsed)
        _save_experience(ctx, "battle", parsed, score=float(parsed.get("confidence", 0.5)))
        return AgentOpinion(
            agent_name=self.agent_name,
            signal=str(parsed.get("signal", "hold")),
            confidence=float(parsed.get("confidence", 0.5)),
            reasoning=str(parsed.get("reasoning", "")),
            raw_data=parsed,
        )


class DebateConsensusAgent(BaseAgent):
    max_steps = 3
    agent_name = "debate_consensus"

    def system_prompt(self, ctx: AgentContext) -> str:
        return """You are the Consensus stage. Synthesize research and battle into a final scored recommendation. Output only JSON with keys: final_signal, confidence, score, reasoning, decision, risks."""

    def build_user_message(self, ctx: AgentContext) -> str:
        research = ctx.get_data("debate_research", {})
        battle = ctx.get_data("debate_battle", {})
        return (
            f"Consensus for {ctx.stock_code}.\n"
            f"Research: {json.dumps(research, ensure_ascii=False, default=str)[:3000]}\n"
            f"Battle: {json.dumps(battle, ensure_ascii=False, default=str)[:3000]}"
        )

    def post_process(self, ctx: AgentContext, raw_text: str) -> Optional[AgentOpinion]:
        parsed = try_parse_json(raw_text) or {}
        ctx.set_data("debate_consensus", parsed)
        _save_experience(ctx, "consensus", parsed, score=float(parsed.get("confidence", 0.5)))
        return AgentOpinion(
            agent_name=self.agent_name,
            signal=str(parsed.get("final_signal", parsed.get("signal", "hold"))),
            confidence=float(parsed.get("confidence", 0.5)),
            reasoning=str(parsed.get("reasoning", "")),
            raw_data=parsed,
        )
