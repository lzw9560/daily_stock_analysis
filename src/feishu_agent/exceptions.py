# -*- coding: utf-8 -*-
"""
飞书智能体自定义异常类
"""


class FeishuAgentError(Exception):
    """飞书智能体基础异常"""

    def __init__(self, message: str, code: int = -1, details: str = ""):
        super().__init__(message)
        self.code = code
        self.details = details

    def __str__(self):
        parts = [super().__str__()]
        if self.code != -1:
            parts.append(f"[code={self.code}]")
        if self.details:
            parts.append(f"details: {self.details}")
        return " ".join(parts)


class AuthenticationError(FeishuAgentError):
    """认证失败异常（App ID/Secret 无效或权限不足）"""

    def __init__(self, message: str = "飞书智能体认证失败", code: int = -1, details: str = ""):
        super().__init__(message, code, details)


class SessionError(FeishuAgentError):
    """会话管理异常"""

    def __init__(self, message: str = "会话操作失败", code: int = -1, details: str = ""):
        super().__init__(message, code, details)


class MessageError(FeishuAgentError):
    """消息发送异常"""

    def __init__(self, message: str = "消息发送失败", code: int = -1, details: str = ""):
        super().__init__(message, code, details)


class RunError(FeishuAgentError):
    """智能体运行异常"""

    def __init__(self, message: str = "智能体运行失败", code: int = -1, details: str = ""):
        super().__init__(message, code, details)


class TimeoutError(FeishuAgentError):
    """请求超时异常"""

    def __init__(self, message: str = "请求超时", code: int = -1, details: str = ""):
        super().__init__(message, code, details)
