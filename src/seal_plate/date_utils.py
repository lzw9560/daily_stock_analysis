"""
打板助手日期工具
智能日期解析：默认取最新有效的交易日数据
"""
from __future__ import annotations

import logging
from datetime import datetime, time

logger = logging.getLogger(__name__)

# A股交易时间：上午9:30-11:30，下午13:00-15:00
_MARKET_CLOSE = time(15, 0)


def is_market_closed(check_time: datetime | None = None) -> bool:
    """判断今日是否已收盘"""
    now = check_time or datetime.now()
    # 周末
    if now.weekday() >= 5:
        return True
    return now.time() >= _MARKET_CLOSE


def get_effective_date(target_date: str | None = None) -> str:
    """
    智能获取有效日期

    逻辑：
    1. 如果指定了 target_date，直接使用
    2. 如果今日已收盘 → 用今日
    3. 如果今日未收盘 → 用上一个交易日
    4. 周末 → 用上一个交易日

    Returns:
        YYYYMMDD 格式的日期字符串
    """
    if target_date:
        return target_date

    now = datetime.now()
    today = now.strftime("%Y%m%d")

    # 今日已收盘 → 用今日
    if now.weekday() < 5 and now.time() >= _MARKET_CLOSE:
        return today

    # 未收盘或周末 → 回溯到上一个交易日
    ref = now
    for _ in range(7):
        ref = datetime(ref.year, ref.month, ref.day)  # 重置到0点
        # 周一 → 回溯到上周五
        if ref.weekday() == 0:
            ref = datetime.fromordinal(ref.toordinal() - 3)
        else:
            ref = datetime.fromordinal(ref.toordinal() - 1)
        if ref.weekday() < 5:
            return ref.strftime("%Y%m%d")

    return today  # fallback


def get_label_for_date(date_str: str) -> str:
    """获取日期的可读标签"""
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        wd = weekday_names[dt.weekday()]
        return f"{dt.strftime('%Y-%m-%d')} {wd}"
    except ValueError:
        return date_str
