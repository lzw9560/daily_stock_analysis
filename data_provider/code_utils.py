# -*- coding: utf-8 -*-
"""
Lightweight stock code utilities — stdlib only, no heavy imports.

Extracted from data_provider/base.py so that canonical_stock_code() and
normalize_stock_code() can be imported without triggering the full
data_provider package init (pandas, numpy, all fetchers).
"""

from typing import Optional

ETF_PREFIXES = ("51", "52", "56", "58", "15", "16", "18")


def normalize_stock_code(stock_code: str) -> str:
    code = stock_code.strip()
    upper = code.upper()

    if upper.startswith('HK') and not upper.startswith('HK.'):
        candidate = upper[2:]
        if candidate.isdigit() and 1 <= len(candidate) <= 5:
            return f"HK{candidate.zfill(5)}"

    if upper.startswith(('SH', 'SZ')) and not upper.startswith('SH.') and not upper.startswith('SZ.'):
        candidate = code[2:]
        if candidate.isdigit() and len(candidate) in (5, 6):
            return candidate

    if upper.startswith(('SH.', 'SZ.')):
        candidate = code[3:]
        if candidate.isdigit() and len(candidate) in (5, 6):
            return candidate

    if upper.startswith('BJ') and not upper.startswith('BJ.'):
        candidate = code[2:]
        if candidate.isdigit() and len(candidate) == 6:
            return candidate

    if upper.startswith('BJ.'):
        candidate = code[3:]
        if candidate.isdigit() and len(candidate) == 6:
            return candidate

    if '.' in code:
        base, suffix = code.rsplit('.', 1)
        if suffix.upper() == 'HK' and base.isdigit() and 1 <= len(base) <= 5:
            return f"HK{base.zfill(5)}"
        if base.upper() in ('SH', 'SS', 'SZ', 'BJ') and suffix.isdigit():
            return suffix
        if suffix.upper() in ('SH', 'SZ', 'SS', 'BJ') and base.isdigit():
            return base

    return code


def canonical_stock_code(code: str) -> str:
    return (code or "").strip().upper()
