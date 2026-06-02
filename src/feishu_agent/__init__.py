# -*- coding: utf-8 -*-
"""
===================================
飞书智能体（Aily）集成模块
===================================

提供飞书智能体的核心交互能力：
- 会话管理（创建/查询/删除）
- 消息发送与接收
- 智能体回复轮询

依赖：lark-oapi SDK（已集成在项目中）
"""

from src.feishu_agent.client import FeishuAgentClient
from src.feishu_agent.exceptions import (
    FeishuAgentError,
    AuthenticationError,
    SessionError,
    MessageError,
    RunError,
    TimeoutError as AgentTimeoutError,
)

__all__ = [
    "FeishuAgentClient",
    "FeishuAgentError",
    "AuthenticationError",
    "SessionError",
    "MessageError",
    "RunError",
    "AgentTimeoutError",
]
