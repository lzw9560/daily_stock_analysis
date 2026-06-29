#!/usr/bin/env python3
"""拆分 notification.py 中的巨类，使用 mixin 模式重组 NotificationService。"""

import importlib.util
import os
import re
import shutil
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

SRC_FILE = os.path.join(PROJECT_ROOT, "src", "notification.py")
DST_DIR = os.path.join(PROJECT_ROOT, "src", "notification")
FIELD_DIR = os.path.join(DST_DIR, "field_definitions")


def load_module():
    spec = importlib.util.spec_from_file_location("notification", SRC_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SRC_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract_block(source, start_pattern, end_pattern=None):
    """从源代码中提取两个模式之间的文本块。"""
    start_idx = source.find(start_pattern)
    if start_idx < 0:
        return "", -1, -1
    if end_pattern:
        end_idx = source.find(end_pattern, start_idx + len(start_pattern))
        if end_idx < 0:
            end_idx = len(source)
    else:
        end_idx = len(source)
    return source[start_idx:end_idx], start_idx, end_idx


def main():
    print("=== 拆分 notification.py ===\n")

    # 1. 备份原文件
    backup = SRC_FILE + ".bak"
    shutil.copy2(SRC_FILE, backup)
    print(f"📦 已备份: notification.py.bak")

    # 2. 读取原文件
    with open(SRC_FILE, "r", encoding="utf-8") as f:
        original = f.read()

    # 3. 提取各部分
    # 3a. 数据结构和枚举 (NotificationChannel, ChannelAttemptResult, NotificationDispatchResult)
    types_start = original.find("class NotificationChannel")
    types_end = original.find("class ChannelDetector")
    types_block = original[types_start:types_end].rstrip()

    # 3b. ChannelDetector
    detector_start = original.find("class ChannelDetector")
    detector_end = original.find("class NotificationService")
    detector_block = original[detector_start:detector_end].rstrip()

    # 3c. NotificationBuilder
    builder_start = original.find("class NotificationBuilder")
    builder_end = original.find("# ----")
    if builder_end < 0:
        builder_end = original.find("def get_notification_service")
    builder_block = original[builder_start:builder_end].rstrip()

    # 3d. 模块级函数 (get_notification_service, send_daily_report)
    module_funcs_start = original.find("def get_notification_service")
    module_funcs_end = original.find('if __name__ == "__main__"')
    if module_funcs_end < 0:
        module_funcs_end = len(original)
    module_funcs_block = original[module_funcs_start:module_funcs_end].rstrip()

    # 3e. 模块级 _safe_float
    safe_float_start = original.find("def _safe_float")
    safe_float_end = original.find("# ----", safe_float_start)
    if safe_float_end < 0:
        safe_float_end = original.find("class NotificationChannel")
    safe_float_block = original[safe_float_start:safe_float_end].rstrip()

    # 4. 创建目录
    os.makedirs(DST_DIR, exist_ok=True)

    # 5. 写入 channel_types.py (纯数据结构)
    types_imports = '''"""通知渠道类型定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

'''
    with open(os.path.join(DST_DIR, "channel_types.py"), "w", encoding="utf-8") as f:
        f.write(types_imports)
        f.write(types_block.strip() + "\n")
    print(f"  ✅ channel_types.py")

    # 6. 写入 channel_detector.py
    detector_imports = '''"""渠道检测和路由分发"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set, TYPE_CHECKING

from .channel_types import NotificationChannel

if TYPE_CHECKING:
    from src.config import Config

logger = logging.getLogger(__name__)

'''
    with open(os.path.join(DST_DIR, "channel_detector.py"), "w", encoding="utf-8") as f:
        f.write(detector_imports)
        f.write(detector_block.strip() + "\n")
    print(f"  ✅ channel_detector.py")

    # 7. 写入 notification_builder.py
    builder_imports = '''"""便捷通知消息构建器"""

from __future__ import annotations

from typing import Dict, List, Optional, Any

from bot.models import BotMessage

'''
    with open(os.path.join(DST_DIR, "notification_builder.py"), "w", encoding="utf-8") as f:
        f.write(builder_imports)
        f.write(builder_block.strip() + "\n")
    print(f"  ✅ notification_builder.py")

    # 8. 提取 NotificationService 方法并分组成 mixin
    nsvc_start = original.find("class NotificationService")
    nsvc_end = original.find("class NotificationBuilder")
    nsvc_block = original[nsvc_start:nsvc_end]

    # 解析方法边界 - 按 def 和 @ 装饰器分割
    methods = []
    lines = nsvc_block.split("\n")
    current_method_lines = []
    in_method = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        # 检测方法开始
        if re.match(r'^    (def |@)', stripped):
            if in_method and current_method_lines:
                methods.append("\n".join(current_method_lines))
                current_method_lines = []
            in_method = True
            current_method_lines.append(line)
        elif in_method:
            current_method_lines.append(line)

    if current_method_lines:
        methods.append("\n".join(current_method_lines))

    # 分组
    format_methods = []  # A: _format_*, _append_*, _escape_*, _get_*_blocks
    report_methods = []  # B: generate_*
    dispatch_methods = []  # C: send_*, _send_*, evaluate_*, should_broadcast_*
    wechat_methods = []  # D: generate_wechat_*
    init_method = []
    other_methods = []  # __init__ 和类属性

    for method in methods:
        first_line = method.strip().split("\n")[0].strip()
        name = first_line.replace("def ", "").split("(")[0].strip()
        if "@" in first_line:
            # 有装饰器 - 取下一行
            for ml in method.split("\n"):
                if ml.strip().startswith("def "):
                    name = ml.strip().replace("def ", "").split("(")[0].strip()
                    break

        if name == "__init__":
            init_method.append(method)
        elif name.startswith("_format_") or name.startswith("_append_") or name.startswith("_escape_md") or \
             name.startswith("_clean_sniper") or name.startswith("_get_signal") or \
             name.startswith("_get_display_name") or name.startswith("_get_report_language") or \
             name.startswith("_get_labels") or name.startswith("_normalize_report_type") or \
             name.startswith("_get_history_compare_context") or name.startswith("_collect_models_used") or \
             name.startswith("_should_show_llm_model") or name.startswith("_get_source_display_name") or \
             name.startswith("_get_fundamental_blocks") or name.startswith("_sanitize_notification_diagnostics"):
            format_methods.append(method)
        elif name.startswith("generate_wechat_"):
            wechat_methods.append(method)
        elif name.startswith("generate_"):
            report_methods.append(method)
        elif name.startswith("send_") or name.startswith("_send_") or \
             name.startswith("evaluate_noise") or name.startswith("record_noise") or \
             name.startswith("release_noise") or name.startswith("should_broadcast") or \
             name.startswith("_has_context_channel") or name.startswith("_source_platform") or \
             name.startswith("_extract_") or name.startswith("_should_use_image") or \
             name.startswith("_detect_all_channels") or name.startswith("is_available") or \
             name.startswith("get_available_channels") or name.startswith("get_channels_for_route") or \
             name.startswith("get_channel_names") or name.startswith("detect_configured_channels") or \
             name.startswith("save_report"):
            dispatch_methods.append(method)
        else:
            other_methods.append(method)

    print(f"\n方法分组统计:")
    print(f"  __init__: {len(init_method)}")
    print(f"  format_methods: {len(format_methods)}")
    print(f"  report_methods: {len(report_methods)}")
    print(f"  dispatch_methods: {len(dispatch_methods)}")
    print(f"  wechat_methods: {len(wechat_methods)}")
    print(f"  other_methods: {len(other_methods)}")

    # 9. 写入 mixin 模块
    # 9a. notification_formatters.py
    fmt_imports = '''"""报告格式化辅助 Mixin"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from bot.models import BotMessage

if TYPE_CHECKING:
    pass

'''
    with open(os.path.join(DST_DIR, "notification_formatters.py"), "w", encoding="utf-8") as f:
        f.write(fmt_imports)
        f.write("class NotificationFormatterMixin:\n")
        # 写入类属性
        f.write('    _CURRENCY_SUFFIX: dict = {}\n')
        f.write('    _SOURCE_DISPLAY_NAMES: dict = {}\n\n')
        for m in format_methods:
            f.write(m.rstrip() + "\n\n")
    print(f"  ✅ notification_formatters.py")

    # 9b. notification_report_generator.py
    report_imports = '''"""报告生成 Mixin"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from bot.models import BotMessage
from src.enums import ReportType

if TYPE_CHECKING:
    from src.types import AnalysisResult

logger = logging.getLogger(__name__)

'''
    with open(os.path.join(DST_DIR, "notification_report_generator.py"), "w", encoding="utf-8") as f:
        f.write(report_imports)
        f.write("class NotificationReportMixin:\n")
        for m in report_methods + wechat_methods:
            f.write(m.rstrip() + "\n\n")
    print(f"  ✅ notification_report_generator.py")

    # 9c. notification_dispatcher.py
    dispatch_imports = '''"""通知分发 Mixin"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from src.config import get_config
from src.notification_noise import (
    NoiseControlResult,
    get_noise_status,
)
from src.notification_routing import (
    ROUTABLE_NOTIFICATION_CHANNELS,
    NotificationRouteType,
    get_channel_route,
)
from bot.models import BotMessage
from src.utils.sanitize import sanitize_diagnostic_text

from .channel_types import ChannelAttemptResult, NotificationDispatchResult, NotificationChannel
from .channel_detector import ChannelDetector

if TYPE_CHECKING:
    from src.types import AnalysisResult

logger = logging.getLogger(__name__)

'''
    with open(os.path.join(DST_DIR, "notification_dispatcher.py"), "w", encoding="utf-8") as f:
        f.write(dispatch_imports)
        f.write("class NotificationDispatcherMixin:\n")
        for m in dispatch_methods:
            f.write(m.rstrip() + "\n\n")
    print(f"  ✅ notification_dispatcher.py")

    # 10. 写入 __init__.py
    init_code = '''"""通知模块 - 向后兼容包

从原 notification.py 重构为子模块包格式。
所有公开 API 保持不变。
"""

from .channel_types import (
    ChannelAttemptResult,
    NotificationChannel,
    NotificationDispatchResult,
)
from .channel_detector import ChannelDetector
from .notification_builder import NotificationBuilder
from .notification_service import NotificationService

# 模块级函数
from .notification_service import _safe_float, get_notification_service, send_daily_report

__all__ = [
    "NotificationChannel",
    "ChannelAttemptResult",
    "NotificationDispatchResult",
    "ChannelDetector",
    "NotificationService",
    "NotificationBuilder",
    "get_notification_service",
    "send_daily_report",
]
'''
    with open(os.path.join(DST_DIR, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(init_code)
    print(f"  ✅ __init__.py")

    # 11. 创建 notification_service.py（组合 NotificationService）
    # 提取原始 NotificationService 的类声明行和 __init__
    class_decl = ""
    for line in nsvc_block.split("\n"):
        if line.strip().startswith("class NotificationService"):
            class_decl = line.strip()
            # 修改为使用 mixin 继承
            class_decl = "class NotificationService(NotificationDispatcherMixin, NotificationReportMixin, NotificationFormatterMixin):"
            break

    svc_imports = '''"""通知服务核心 - 组合所有 Mixin"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from src.config import Config, get_config
from src.enums import ReportType
from src.notification_noise import NOTIFICATION_SEVERITIES
from src.notification_routing import (
    ROUTABLE_NOTIFICATION_CHANNELS,
    NotificationRouteType,
    get_channel_route,
)
from src.report_language import (
    get_report_language_for_result,
    get_report_labels,
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
)

from .channel_types import ChannelAttemptResult, NotificationDispatchResult, NotificationChannel
from .channel_detector import ChannelDetector
from .notification_formatters import NotificationFormatterMixin
from .notification_report_generator import NotificationReportMixin
from .notification_dispatcher import NotificationDispatcherMixin

logger = logging.getLogger(__name__)

_safe_float = NotificationFormatterMixin._format_percent.__doc__  # placeholder
'''
    # Fix: _safe_float is module-level, need to handle it separately
    # Actually, _safe_float is defined at module level in the original file
    # Let me just import it from the formatter or redefine it

    # The safer approach: rewrite the NotificationService class with mixin inheritance
    # and keep _safe_float as a module-level function

    # Let me extract _safe_float from the original source
    sf_text = safe_float_block

    final_svc = svc_imports.replace(
        '_safe_float = NotificationFormatterMixin._format_percent.__doc__  # placeholder',
        f'{sf_text}'
    )

    # Rebuilt NotificationService as mixin with __init__
    final_svc += f'\n\n{class_decl}\n'
    for m in init_method + other_methods:
        final_svc += m.rstrip() + "\n\n"

    # Add module-level functions
    final_svc += "\n" + module_funcs_block.strip() + "\n"

    with open(os.path.join(DST_DIR, "notification_service.py"), "w", encoding="utf-8") as f:
        f.write(final_svc)
    print(f"  ✅ notification_service.py")

    # 12. 替换原文件为兼容存根
    stub = '''"""
通知模块 - 兼容存根

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
'''
    with open(SRC_FILE, "w", encoding="utf-8") as f:
        f.write(stub)
    print(f"  ✅ 原文件 → 兼容存根")

    print(f"\n{'='*50}")
    print(f"拆分完成！")
    print(f"  新包: src/notification/")
    print(f"  文件: channel_types, channel_detector, notification_builder,")
    print(f"        notification_formatters, notification_report_generator,")
    print(f"        notification_dispatcher, notification_service")
    print(f"  备份: notification.py.bak")


if __name__ == "__main__":
    main()
