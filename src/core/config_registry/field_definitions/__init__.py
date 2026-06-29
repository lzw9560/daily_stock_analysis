"""字段定义 - 按分类聚合"""

FIELD_DEFINITIONS: dict = {}

from .base import FIELD_DEFINITIONS as _base_fields
FIELD_DEFINITIONS.update(_base_fields)
from .ai_model import FIELD_DEFINITIONS as _ai_model_fields
FIELD_DEFINITIONS.update(_ai_model_fields)
from .data_source import FIELD_DEFINITIONS as _data_source_fields
FIELD_DEFINITIONS.update(_data_source_fields)
from .notification import FIELD_DEFINITIONS as _notification_fields
FIELD_DEFINITIONS.update(_notification_fields)
from .system import FIELD_DEFINITIONS as _system_fields
FIELD_DEFINITIONS.update(_system_fields)
from .agent import FIELD_DEFINITIONS as _agent_fields
FIELD_DEFINITIONS.update(_agent_fields)
from .backtest import FIELD_DEFINITIONS as _backtest_fields
FIELD_DEFINITIONS.update(_backtest_fields)

