"""
字段定义 - base 分类
从 config_registry.py 按 category 拆分
"""

FIELD_DEFINITIONS: dict = {
    "STOCK_LIST": {       'category': 'base',
        'data_type': 'array',
        'default_value': '600519,300750,002594',
        'description': 'Comma-separated watchlist stock codes.',
        'display_order': 10,
        'docs': [       {       'href': 'https://github.com/ZhuLinsen/daily_stock_analysis/blob/main/docs/full-guide.md#环境变量完整列表',
                                'label': '完整指南：环境变量完整列表'},
                        {       'href': 'https://github.com/ZhuLinsen/daily_stock_analysis/blob/main/docs/TUSHARE_STOCK_LIST_GUIDE.md',
                                'label': 'Tushare 股票列表指南'}],
        'examples': ['STOCK_LIST=600519,300750,002594', 'STOCK_LIST=600519,hk00700,AAPL'],
        'help_key': 'settings.base.STOCK_LIST',
        'is_editable': True,
        'is_required': False,
        'is_sensitive': False,
        'options': [],
        'title': 'Stock List',
        'ui_control': 'textarea',
        'validation': {'min_items': 1},
        'warning_codes': []}
}
