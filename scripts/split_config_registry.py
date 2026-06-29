#!/usr/bin/env python3
"""通过 importlib 加载 config_registry 模块，按类别拆分 _FIELD_DEFINITIONS。"""

import importlib.util
import os
import shutil
import sys
from pprint import pformat

# 添加项目根目录到 Python 路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

SRC_FILE = os.path.join(PROJECT_ROOT, "src", "core", "config_registry.py")
DST_DIR = os.path.join(PROJECT_ROOT, "src", "core", "config_registry")
FIELD_DIR = os.path.join(DST_DIR, "field_definitions")

CATEGORY_MAP = {
    "base": "base.py",
    "ai_model": "ai_model.py",
    "data_source": "data_source.py",
    "notification": "notification.py",
    "system": "system.py",
    "agent": "agent.py",
    "backtest": "backtest.py",
    "uncategorized": "uncategorized.py",
}


def load_module():
    """加载 config_registry 模块"""
    spec = importlib.util.spec_from_file_location("config_registry", SRC_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {SRC_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract_source_range(lines, start_key, end_key):
    """从原文件中提取两个标记之间的文本"""
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if start_idx is None and start_key in line:
            start_idx = i
        if end_idx is None and start_idx is not None and end_key in line:
            end_idx = i
            break
    if start_idx is not None and end_idx is not None:
        return lines[start_idx:end_idx+1]
    return []


def write_field_module(category, fields, filepath):
    """将某个 category 的字段写入 Python 文件"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f'"""\n字段定义 - {category} 分类\n从 config_registry.py 按 category 拆分\n"""\n\n')
        f.write("FIELD_DEFINITIONS: dict = {\n")
        for i, (key, value) in enumerate(fields.items()):
            comma = "," if i < len(fields) - 1 else ""
            f.write(f'    "{key}": {pformat(value, width=120, indent=8)}{comma}\n')
        f.write("}\n")
    return len(fields)


def main():
    print("=== 拆分 config_registry.py (importlib 方式) ===\n")

    # 1. 加载模块
    module = load_module()
    field_defs: dict = module._FIELD_DEFINITIONS
    print(f"✅ 加载成功，_FIELD_DEFINITIONS 共 {len(field_defs)} 个字段\n")

    # 2. 按 category 分组
    categorized: dict[str, dict] = {}
    for key, meta in field_defs.items():
        cat = meta.get("category", "uncategorized")
        categorized.setdefault(cat, {})[key] = meta

    for cat, fields in sorted(categorized.items()):
        print(f"  {cat}: {len(fields)} fields")

    # 3. 创建目录
    os.makedirs(FIELD_DIR, exist_ok=True)

    # 4. 备份原文件
    backup = SRC_FILE + ".bak"
    shutil.copy2(SRC_FILE, backup)
    print(f"\n📦 原文件已备份至: config_registry.py.bak")

    # 5. 写入各分类模块
    print("\n生成分类模块:")
    for cat, filename in CATEGORY_MAP.items():
        if cat not in categorized:
            continue
        filepath = os.path.join(FIELD_DIR, filename)
        count = write_field_module(cat, categorized[cat], filepath)
        print(f"  ✅ {filename} ({count} fields)")

    # 6. 写入 field_definitions/__init__.py - 聚合所有字段
    with open(os.path.join(FIELD_DIR, "__init__.py"), "w", encoding="utf-8") as f:
        f.write('"""字段定义 - 按分类聚合"""\n\n')
        f.write('FIELD_DEFINITIONS: dict = {}\n\n')
        for cat, filename in CATEGORY_MAP.items():
            if cat in categorized:
                mod = filename[:-3]  # 去掉 .py
                f.write(f"from .{mod} import FIELD_DEFINITIONS as _{cat}_fields\n")
                f.write(f"FIELD_DEFINITIONS.update(_{cat}_fields)\n")
        f.write("\n")
    print(f"  ✅ __init__.py（聚合所有字段）")

    # 7. 写入 categories.py（_CATEGORY_DEFINITIONS + WEB_SETTINGS_HIDDEN_FROM_UI）
    # 同时也写 SCHEMA_VERSION
    cat_lines = [
        '"""配置分类定义"""',
        "",
        f'SCHEMA_VERSION = "{module.SCHEMA_VERSION}"',
        "",
        f"_CATEGORY_DEFINITIONS = {pformat(module._CATEGORY_DEFINITIONS, width=120, indent=4)}",
        "",
        f"WEB_SETTINGS_HIDDEN_FROM_UI = {pformat(module.WEB_SETTINGS_HIDDEN_FROM_UI)}",
        "",
    ]
    with open(os.path.join(DST_DIR, "categories.py"), "w", encoding="utf-8") as f:
        f.write("\n".join(cat_lines))
    print(f"  ✅ categories.py")

    # 8. 写入 help_metadata.py
    md_lines = ['"""字段帮助元数据"""', ""]
    md_lines.append(f"_FIELD_HELP_METADATA = {pformat(module._FIELD_HELP_METADATA, width=120, indent=4)}")
    md_lines.append("")
    with open(os.path.join(FIELD_DIR, "help_metadata.py"), "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"  ✅ help_metadata.py")

    # 9. 从原文件中提取函数并写入对应模块
    with open(SRC_FILE + ".bak", "r", encoding="utf-8") as f:
        original = f.read()

    # 9a. 提取所有函数
    import re

    def extract_func(source, func_name_start):
        """从 source 中提取函数及其完整代码"""
        pattern = rf"\n(def {re.escape(func_name_start)}\([^)]*\).*?)(?=\n(?:def |class |$)|\Z)"
        match = re.search(pattern, source, re.DOTALL)
        if match:
            # 包含函数体直到下一个顶级 def/class 或文件结束
            func_text = match.group(1)
            # 扩展：找到直到下一个顶级 def/class 或 EOF
            start = match.start()
            end = start + len(func_text)
            # 继续查找后续行直到下一个顶级声明
            rest = source[end:]
            for i, line in enumerate(rest.split("\n")):
                if re.match(r'^(def |class )', line.strip()):
                    break
                func_text += "\n" + line
            return func_text.strip()
        return None

    # 9b. Schema builder 函数
    schema_funcs = {
        "get_field_definition": None,
        "build_schema_response": None,
        "get_category_definitions": None,
    }
    for func_name in schema_funcs:
        func_text = extract_func(original, func_name)
        if func_text:
            schema_funcs[func_name] = func_text

    # 9c. Infer 函数
    infer_funcs = {
        "_extract_option_values": None,
        "get_registered_field_keys": None,
        "_is_sensitive_key": None,
        "_infer_category": None,
        "_infer_data_type": None,
        "_infer_ui_control": None,
    }
    for func_name in infer_funcs:
        func_text = extract_func(original, func_name)
        if func_text:
            infer_funcs[func_name] = func_text

    # 9d. 写入 schema_builder.py
    with open(os.path.join(DST_DIR, "schema_builder.py"), "w", encoding="utf-8") as f:
        f.write('"""Schema 构建和字段查询"""\n\n')
        f.write("from copy import deepcopy\n")
        f.write("from typing import Any, Dict, List, Optional\n\n")
        f.write("from .categories import _CATEGORY_DEFINITIONS, WEB_SETTINGS_HIDDEN_FROM_UI\n")
        f.write("from .field_definitions import FIELD_DEFINITIONS\n")
        f.write("from .field_definitions.help_metadata import _FIELD_HELP_METADATA\n")
        f.write("from .infer import (\n")
        f.write("    _extract_option_values,\n")
        f.write("    _infer_category,\n")
        f.write("    _infer_data_type,\n")
        f.write("    _infer_ui_control,\n")
        f.write("    _is_sensitive_key,\n")
        f.write("    get_registered_field_keys,\n")
        f.write(")\n\n")
        for func_text in schema_funcs.values():
            if func_text:
                f.write(func_text + "\n\n")
    print(f"  ✅ schema_builder.py")

    # 9e. 写入 infer.py
    with open(os.path.join(DST_DIR, "infer.py"), "w", encoding="utf-8") as f:
        f.write('"""分类推断和字段查询辅助函数"""\n\n')
        f.write("from typing import Any, Dict, List, Optional\n\n")
        for func_text in infer_funcs.values():
            if func_text:
                f.write(func_text + "\n\n")
    print(f"  ✅ infer.py")

    # 10. 写入 __init__.py（向后兼容的 re-export）
    init_code = '''"""
配置注册表 - 向后兼容包

从原 config_registry.py 重构为子模块包格式。
所有公开 API 保持不变。
"""

from .categories import SCHEMA_VERSION, _CATEGORY_DEFINITIONS, WEB_SETTINGS_HIDDEN_FROM_UI
from .field_definitions import FIELD_DEFINITIONS as _FIELD_DEFINITIONS
from .field_definitions.help_metadata import _FIELD_HELP_METADATA
from .infer import (
    _extract_option_values,
    _infer_category,
    _infer_data_type,
    _infer_ui_control,
    _is_sensitive_key,
    get_registered_field_keys,
)
from .schema_builder import (
    build_schema_response,
    get_category_definitions,
    get_field_definition,
)

__all__ = [
    "SCHEMA_VERSION",
    "_CATEGORY_DEFINITIONS",
    "WEB_SETTINGS_HIDDEN_FROM_UI",
    "_FIELD_DEFINITIONS",
    "_FIELD_HELP_METADATA",
    "build_schema_response",
    "get_category_definitions",
    "get_field_definition",
    "_extract_option_values",
    "_infer_category",
    "_infer_data_type",
    "_infer_ui_control",
    "_is_sensitive_key",
    "get_registered_field_keys",
]
'''
    with open(os.path.join(DST_DIR, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(init_code)
    print(f"  ✅ __init__.py")

    # 11. 将原文件替换为兼容存根
    stub = '''"""
配置注册表 - 兼容存根

重构至 src/core/config_registry/ 包。
此文件保持向后兼容，所有导入从新包位置重新导出。
"""
# flake8: noqa: F401
from src.core.config_registry import (
    SCHEMA_VERSION,
    _CATEGORY_DEFINITIONS,
    _FIELD_DEFINITIONS,
    _FIELD_HELP_METADATA,
    WEB_SETTINGS_HIDDEN_FROM_UI,
    _extract_option_values,
    _infer_category,
    _infer_data_type,
    _infer_ui_control,
    _is_sensitive_key,
    build_schema_response,
    get_category_definitions,
    get_field_definition,
    get_registered_field_keys,
)
'''
    with open(SRC_FILE, "w", encoding="utf-8") as f:
        f.write(stub)
    print(f"  ✅ 原文件 → 兼容存根 ({len(stub)} 字节)")

    print(f"\n{'='*50}")
    print(f"拆分完成！")
    print(f"  新包: src/core/config_registry/")
    print(f"  字段: {len(field_defs)} 个 ({len(categorized)} 个分类)")
    print(f"  备份: config_registry.py.bak")


if __name__ == "__main__":
    main()
