# -*- coding: utf-8 -*-
"""LLM Prompt 模板（交易系统升级 Phase 1）

按视角分类管理的 Prompt 模板:
- trader_prompt: 交易员视角（结构化JSON，强制输出动作/仓位/止盈止损）
- sentiment_prompt: 情绪视角（市场情绪周期分析）
- fundamental_prompt: 基本面视角（估值/业绩/行业竞争）
"""

from .trader_prompt import (
    TRADER_SYSTEM_PROMPT,
    TRADER_USER_PROMPT_TEMPLATE,
    TRADER_OUTPUT_SCHEMA,
    TRADER_SHORT_TERM_PROMPT,
    get_trader_system_prompt,
    format_trader_user_prompt,
    parse_trader_response,
    TraderDecision,
)

from .sentiment_prompt import (
    SENTIMENT_SYSTEM_PROMPT,
    SENTIMENT_USER_PROMPT_TEMPLATE,
    format_sentiment_user_prompt,
)

from .fundamental_prompt import (
    FUNDAMENTAL_SYSTEM_PROMPT,
    FUNDAMENTAL_USER_PROMPT_TEMPLATE,
    format_fundamental_user_prompt,
)

__all__ = [
    # Trader prompts
    "TRADER_SYSTEM_PROMPT",
    "TRADER_USER_PROMPT_TEMPLATE",
    "TRADER_OUTPUT_SCHEMA",
    "TRADER_SHORT_TERM_PROMPT",
    "get_trader_system_prompt",
    "format_trader_user_prompt",
    "parse_trader_response",
    "TraderDecision",
    # Sentiment prompts
    "SENTIMENT_SYSTEM_PROMPT",
    "SENTIMENT_USER_PROMPT_TEMPLATE",
    "format_sentiment_user_prompt",
    # Fundamental prompts
    "FUNDAMENTAL_SYSTEM_PROMPT",
    "FUNDAMENTAL_USER_PROMPT_TEMPLATE",
    "format_fundamental_user_prompt",
]
