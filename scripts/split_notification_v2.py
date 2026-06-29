#!/usr/bin/env python3
"""拆分 notification.py Phase 2 — 修复装饰器解析问题。"""

import os
import re
import shutil
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_FILE = os.path.join(PROJECT_ROOT, "src", "notification.py")
DST_DIR = os.path.join(PROJECT_ROOT, "src", "notification")
BACKUP = SRC_FILE + ".phase2.bak"


def parse_class_body(source):
    """Parse a class body, returning methods with decorators properly attached.

    Strategy: find all lines that start a method (4-space indent + def/@), then
    slice the text between consecutive method starts.
    """
    lines = source.split('\n')
    # Find method start lines (indices)
    method_starts = []
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if re.match(r'^    (def |@)', stripped):
            # Only count if the previous line isn't also a decorator (avoid double-count)
            if not method_starts or i > method_starts[-1] + 10:
                # Check if the PREVIOUS non-empty line is a decorator
                # If so, include it (but we'll adjust)
                method_starts.append(i)

    # Adjust: if the previous non-empty line before a def is a decorator,
    # move the start up to include it
    adjusted_starts = []
    for start in method_starts:
        actual_start = start
        j = start - 1
        while j >= 0:
            prev = lines[j].rstrip()
            if prev == '' or prev.startswith('#'):
                j -= 1
            elif re.match(r'^    @', prev):
                actual_start = j
                j -= 1
            else:
                break
        adjusted_starts.append(actual_start)

    # Deduplicate
    adjusted_starts = sorted(set(adjusted_starts))
    methods = []

    for idx, start in enumerate(adjusted_starts):
        if idx + 1 < len(adjusted_starts):
            end = adjusted_starts[idx + 1]
        else:
            end = len(lines)
        method_text = '\n'.join(lines[start:end]).rstrip()
        if method_text:
            methods.append(method_text)

    return methods


def get_method_name(method_text):
    for line in method_text.strip().split('\n'):
        stripped = line.strip()
        if stripped.startswith('def '):
            return stripped.split('(')[0].replace('def ', '')
    return ""


def main():
    print("=== notification.py Phase 2 拆分 ===\n")

    # 1. 备份
    shutil.copy2(SRC_FILE, BACKUP)
    print(f"📦 备份: notification.py.phase2.bak")

    # 2. 读取
    with open(SRC_FILE, 'r') as f:
        original = f.read()

    # 3. 提取 NotificationService 类
    nsvc_start = original.find('class NotificationService(')
    nsvc_end = original.find('class NotificationBuilder')
    if nsvc_end < 0:
        nsvc_end = original.find('\ndef get_notification_service')
    nsvc_body = original[nsvc_start:nsvc_end]

    print(f"  NotificationService body: {len(nsvc_body)} chars")

    methods = parse_class_body(nsvc_body)

    # 分类
    fmt_methods = []
    report_methods = []
    dispatch_methods = []
    init_methods = []
    other_methods = []

    fmt_prefixes = (
        '_format_', '_append_', '_escape_md', '_clean_sniper', '_get_signal',
        '_get_display_name', '_get_report_language', '_get_labels',
        '_normalize_report_type', '_get_history_compare_context',
        '_collect_models_used', '_should_show_llm_model',
        '_get_source_display_name', '_get_fundamental_blocks',
        '_sanitize_notification_diagnostics',
    )

    skipped_decorator_only = 0

    for m in methods:
        name = get_method_name(m)
        if not name:
            # Decorator-only fragment (no def) - skip
            skipped_decorator_only += 1
            continue

        if name == '__init__':
            init_methods.append(m)
        elif name.startswith('generate_'):
            report_methods.append(m)
        elif any(name.startswith(p) for p in fmt_prefixes):
            fmt_methods.append(m)
        elif (name.startswith('send') or name.startswith('_send') or
              name.startswith('evaluate_noise') or name.startswith('record_noise') or
              name.startswith('release_noise') or name.startswith('should_broadcast') or
              name.startswith('_has_context') or name.startswith('_source_platform') or
              name.startswith('_extract_') or name.startswith('_should_use_image') or
              name.startswith('_detect_all') or name.startswith('is_available') or
              name.startswith('get_available') or name.startswith('get_channels') or
              name.startswith('get_channel') or name.startswith('detect_configured') or
              name.startswith('save_report')):
            dispatch_methods.append(m)
        else:
            other_methods.append(m)

    print(f"分类: init={len(init_methods)} formatter={len(fmt_methods)} report={len(report_methods)} dispatch={len(dispatch_methods)} other={len(other_methods)} skipped_decorators={skipped_decorator_only}")
    print(f"  总计 methods: {len(methods)}")

    # 4. 提取模块级函数
    after_ns = original[nsvc_end:]

    # 5. 创建目录
    os.makedirs(DST_DIR, exist_ok=True)

    # ============================================================
    # notification_formatters.py
    # ============================================================
    with open(os.path.join(DST_DIR, 'notification_formatters.py'), 'w') as f:
        f.write('''"""报告格式化辅助 Mixin"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from bot.models import BotMessage

if TYPE_CHECKING:
    pass


class NotificationFormatterMixin:
    """报告格式化辅助方法集合。"""
''')
        for m in fmt_methods:
            f.write('\n' + m.rstrip() + '\n')
    print(f"  ✅ notification_formatters.py ({len(fmt_methods)} methods)")

    # ============================================================
    # notification_report_generator.py
    # ============================================================
    with open(os.path.join(DST_DIR, 'notification_report_generator.py'), 'w') as f:
        f.write('''"""报告生成 Mixin"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from bot.models import BotMessage
from src.enums import ReportType

if TYPE_CHECKING:
    from src.analyzer import AnalysisResult

logger = logging.getLogger(__name__)


class NotificationReportMixin:
    """报告生成方法集合。"""
''')
        for m in report_methods:
            f.write('\n' + m.rstrip() + '\n')
    print(f"  ✅ notification_report_generator.py ({len(report_methods)} methods)")

    # ============================================================
    # notification_dispatcher.py
    # ============================================================
    with open(os.path.join(DST_DIR, 'notification_dispatcher.py'), 'w') as f:
        f.write('''"""通知分发 Mixin"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from src.config import Config, get_config
from src.notification_noise import (
    NotificationNoiseDecision,
    evaluate_notification_noise,
    record_notification_noise,
    release_notification_noise,
)
from src.notification_routing import (
    get_notification_route_config,
    split_notification_route_channels,
)
from bot.models import BotMessage
from src.utils.sanitize import sanitize_diagnostic_text
from src.notification_sender import (
    WECHAT_IMAGE_MAX_BYTES,
    resolve_gotify_message_endpoint,
    resolve_ntfy_endpoint,
)

from src.notification_channel import NotificationChannel, ChannelDetector
from src.notification_result import ChannelAttemptResult, NotificationDispatchResult

if TYPE_CHECKING:
    from src.analyzer import AnalysisResult

logger = logging.getLogger(__name__)


class NotificationDispatcherMixin:
    """通知分发方法集合。"""
''')
        for m in dispatch_methods:
            f.write('\n' + m.rstrip() + '\n')
    print(f"  ✅ notification_dispatcher.py ({len(dispatch_methods)} methods)")

    # ============================================================
    # notification_service.py
    # ============================================================
    svc = '''"""通知服务核心 — 组合所有 Mixin 与 Sender 类"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from src.config import Config, get_config
from src.enums import ReportType
from src.notification_noise import (
    NotificationNoiseDecision,
    evaluate_notification_noise,
    record_notification_noise,
    release_notification_noise,
)
from src.notification_routing import (
    get_notification_route_config,
    split_notification_route_channels,
)
from src.report_language import (
    get_localized_stock_name,
    get_report_labels,
    get_signal_level,
    normalize_report_language,
)
from bot.models import BotMessage
from src.utils.sanitize import sanitize_diagnostic_text
from src.utils.data_processing import normalize_model_used
from src.notification_sender import (
    AstrbotSender,
    CustomWebhookSender,
    DiscordSender,
    EmailSender,
    FeishuSender,
    GotifySender,
    NtfySender,
    PushoverSender,
    PushplusSender,
    Serverchan3Sender,
    SlackSender,
    TelegramSender,
    WechatSender,
    WECHAT_IMAGE_MAX_BYTES,
    resolve_gotify_message_endpoint,
    resolve_ntfy_endpoint,
)

from src.notification_channel import NotificationChannel, ChannelDetector
from src.notification_result import ChannelAttemptResult, NotificationDispatchResult

from .notification_formatters import NotificationFormatterMixin
from .notification_report_generator import NotificationReportMixin
from .notification_dispatcher import NotificationDispatcherMixin

logger = logging.getLogger(__name__)


'''
    # 添加 _safe_float 模块级函数
    sf_start = original.find('\ndef _safe_float(')
    if sf_start < 0:
        sf_start = original.find('def _safe_float(')
    sf_end = original.find('\n\n', sf_start + 1)
    if sf_end > 0:
        svc += original[sf_start:sf_end].strip() + '\n\n'

    svc += '''
if TYPE_CHECKING:
    from src.analyzer import AnalysisResult


'''

    # 提取 docstring
    ds_match = re.search(
        r'class NotificationService\(.*?\).*?:\n(    """[^"]*""")\n',
        original[nsvc_start:nsvc_start+3000],
        re.DOTALL,
    )
    docstring = ds_match.group(1) if ds_match else '    """通知服务"""'

    svc += f'''class NotificationService(
    NotificationDispatcherMixin,
    NotificationReportMixin,
    NotificationFormatterMixin,
    AstrbotSender,
    CustomWebhookSender,
    DiscordSender,
    EmailSender,
    FeishuSender,
    GotifySender,
    NtfySender,
    PushoverSender,
    PushplusSender,
    Serverchan3Sender,
    SlackSender,
    TelegramSender,
    WechatSender,
):
{docstring}
'''

    # Add __init__ + other methods
    for m in init_methods + other_methods:
        svc += '\n' + m.rstrip() + '\n'

    # Add module-level convenience functions (separated by double newline)
    mod_func_start = original.find('\ndef get_notification_service')
    mod_func_end = original.find('\nif __name__')
    if mod_func_start > 0 and mod_func_end > mod_func_start:
        svc += '\n' + original[mod_func_start:mod_func_end].strip() + '\n'

    with open(os.path.join(DST_DIR, 'notification_service.py'), 'w') as f:
        f.write(svc)
    print(f"  ✅ notification_service.py")

    # ============================================================
    # __init__.py
    # ============================================================
    with open(os.path.join(DST_DIR, '__init__.py'), 'w') as f:
        f.write('''"""通知模块 — 向后兼容包"""
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
''')
    print(f"  ✅ __init__.py")

    # ============================================================
    # 兼容存根
    # ============================================================
    with open(SRC_FILE, 'w') as f:
        f.write('''"""
通知模块 — 兼容存根

重构至 src/notification/ 包。
此文件保持向后兼容，所有导入从新包位置重新导出。
"""
# flake8: noqa: F401
from src.notification import (
    ChannelAttemptResult,
    ChannelDetector,
    NotificationBuilder,
    NotificationChannel,
    NotificationDispatchResult,
    NotificationService,
    _safe_float,
    get_notification_service,
    send_daily_report,
)
''')
    print(f"  ✅ 兼容存根")

    print(f"\n拆分完成！")
    print(f"  包: src/notification/")
    print(f"  存根: src/notification.py (向后兼容)")


if __name__ == "__main__":
    main()
