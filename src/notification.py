"""
通知模块 — 兼容存根

重构至 src/notification/ 包。
此文件保持向后兼容，所有导入从新包位置重新导出。
"""
# flake8: noqa: F401
from src.notification.notification_service import (
    NotificationService,
    _safe_float,
    get_notification_service,
    send_daily_report,
)
from src.notification_channel import NotificationChannel, ChannelDetector
from src.notification_result import ChannelAttemptResult, NotificationDispatchResult
from src.notification_builder import NotificationBuilder
