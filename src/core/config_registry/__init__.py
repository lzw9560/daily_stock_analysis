"""
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
