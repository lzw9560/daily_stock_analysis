"""通知模块 — 向后兼容包"""
from .notification_service import (
    NotificationService,
    _safe_float,
    get_notification_service,
    send_daily_report,
)

from src.notification_channel import NotificationChannel, ChannelDetector
from src.notification_result import ChannelAttemptResult, NotificationDispatchResult
from src.notification_builder import NotificationBuilder

__all__ = [
    "NotificationChannel",
    "ChannelAttemptResult",
    "NotificationDispatchResult",
    "ChannelDetector",
    "NotificationService",
    "NotificationBuilder",
    "get_notification_service",
    "send_daily_report",
    "_safe_float",
]
