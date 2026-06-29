"""
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
