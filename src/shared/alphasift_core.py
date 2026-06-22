# -*- coding: utf-8 -*-
"""
===================================
AlphaSift 核心适配与规范化逻辑（共享层）
===================================

被 api/v1/endpoints/alphasift.py 和 src/services/screening_service.py 共用。

职责：
1. AlphaSift 适配层导入与调用封装
2. 选股结果规范化（candidates normalisation）
3. 通用序列化工具（_to_plain 等）

注意：
- 本模块不依赖 FastAPI（不引入 HTTPException），
  错误通过自定义 AlphaSiftError 向上抛出，
  由调用方（API 层 / 服务层）各自转换为合适的异常类型。
"""

from __future__ import annotations

import importlib
import inspect
import logging
import math
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── 常量 ────────────────────────────────────────────────────────────────────
ALPHASIFT_DSA_ADAPTER_MODULE = "alphasift.dsa_adapter"
ALPHASIFT_EXPECTED_MISSING_MODULES = frozenset({"alphasift", ALPHASIFT_DSA_ADAPTER_MODULE})


# ── 自定义异常 ───────────────────────────────────────────────────────────────

class AlphaSiftError(Exception):
    """AlphaSift 共享层异常（无需依赖 FastAPI HTTPException）。"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 424,
        diagnostics: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.diagnostics = diagnostics


class AlphaSiftDisabledError(AlphaSiftError):
    """AlphaSift 功能未启用。"""

    def __init__(self) -> None:
        super().__init__("ALPHASIFT_ENABLED is false.", status_code=403)


# ── 运行时准备 ──────────────────────────────────────────────────────────────

def _prepare_alphasift_runtime_env() -> None:
    if os.getenv("STRATEGIES_DIR"):
        return

    spec = importlib.util.find_spec("alphasift")
    if not spec or not spec.origin:
        return

    package_strategies_dir = Path(spec.origin).resolve().parent / "strategies"
    if package_strategies_dir.is_dir():
        os.environ["STRATEGIES_DIR"] = str(package_strategies_dir)


# ── 适配器导入与调用 ────────────────────────────────────────────────────────

def _is_expected_alphasift_missing(exc: ModuleNotFoundError) -> bool:
    return getattr(exc, "name", None) in ALPHASIFT_EXPECTED_MISSING_MODULES


def _log_unexpected_alphasift_exception(stage: str, exc: BaseException) -> Dict[str, str]:
    logger.warning(
        "Unexpected AlphaSift %s failure: %s",
        stage, exc,
        exc_info=exc.__traceback__ is not None,
    )
    return {
        "reason": "unexpected_exception",
        "stage": stage,
        "error_type": exc.__class__.__name__,
    }


def _import_alphasift() -> Any:
    try:
        _prepare_alphasift_runtime_env()
        return importlib.import_module(ALPHASIFT_DSA_ADAPTER_MODULE)
    except ModuleNotFoundError as exc:
        if _is_expected_alphasift_missing(exc):
            raise AlphaSiftError(
                f"AlphaSift 未安装或未挂载到当前 Python 环境，无法导入 {ALPHASIFT_DSA_ADAPTER_MODULE}：{exc}",
                status_code=424,
            ) from exc
        diagnostics = _log_unexpected_alphasift_exception("import_adapter", exc)
        raise AlphaSiftError(
            f"AlphaSift 适配层导入失败，请检查依赖完整性和当前 Python 环境：{exc}",
            status_code=424,
            diagnostics=diagnostics,
        ) from exc
    except Exception as exc:
        diagnostics = _log_unexpected_alphasift_exception("import_adapter", exc)
        raise AlphaSiftError(
            f"AlphaSift 适配层导入失败，请检查依赖完整性和当前 Python 环境：{exc}",
            status_code=424,
            diagnostics=diagnostics,
        ) from exc


def _get_dsa_adapter() -> Any:
    adapter = _import_alphasift()
    for attr in ("get_status", "list_strategies", "screen"):
        _get_adapter_callable(adapter, attr, f"{attr}() 不可调用。")
    return adapter


def _get_adapter_callable(adapter: Any, name: str, missing_error: str) -> Any:
    callable_obj = getattr(adapter, name, None)
    if not callable(callable_obj):
        raise AlphaSiftError(
            f"已导入 alphasift 适配层，但 {missing_error}",
            status_code=424,
        )
    return callable_obj


def _call_alphasift_screen(screen: Any, strategy: str, market: str, max_results: int) -> Any:
    signature = inspect.signature(screen)
    params = signature.parameters
    supports_var_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in params.values()
    )
    positional_params = [
        parameter
        for parameter in params.values()
        if parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    supports_var_positional = any(
        parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in params.values()
    )

    supports_max_results = "max_results" in params or supports_var_kwargs
    supports_max_output = "max_output" in params or supports_var_kwargs
    supports_use_llm = "use_llm" in params or supports_var_kwargs

    kwargs: Dict[str, Any] = {"market": market}
    if supports_max_results:
        kwargs["max_results"] = max_results
    elif supports_max_output:
        kwargs["max_output"] = max_results
    else:
        kwargs["max_results"] = max_results

    if supports_use_llm:
        kwargs["use_llm"] = True

    try:
        return screen(strategy, **kwargs)
    except TypeError as exc:
        message = str(exc)
        signature_mismatch = ("keyword" in message and "argument" in message) or (
            "positional" in message and "given" in message
        )
        if not signature_mismatch:
            raise
        if not (supports_var_kwargs or supports_var_positional or len(positional_params) >= 3):
            raise
        return screen(strategy, market, max_results)


# ── 序列化工具 ──────────────────────────────────────────────────────────────

def _to_plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict") and callable(value.dict):
        return value.dict()
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    return value


def _remove_non_finite_json_values(value: Any) -> Any:
    if isinstance(value, list):
        return [_remove_non_finite_json_values(item) for item in value]
    if isinstance(value, tuple):
        return [_remove_non_finite_json_values(item) for item in value]
    if isinstance(value, dict):
        return {key: _remove_non_finite_json_values(item) for key, item in value.items()}
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


# ── Candidate 规范化 ────────────────────────────────────────────────────────

def _first_present(primary: Dict[str, Any], source: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if primary.get(key) is not None:
            return primary.get(key)
        if source.get(key) is not None:
            return source.get(key)
    return None


def _build_candidate_reason(item: Dict[str, Any]) -> str:
    summaries = item.get("post_analysis_summaries")
    if isinstance(summaries, dict):
        summary = next((str(value) for value in summaries.values() if value), "")
        if summary:
            return summary

    factors = item.get("factor_scores")
    parts: List[str] = []
    if isinstance(factors, dict) and factors:
        top_factors = sorted(
            ((key, value) for key, value in factors.items() if isinstance(value, (int, float))),
            key=lambda pair: pair[1],
            reverse=True,
        )[:3]
        if top_factors:
            factor_text = "、".join(f"{key} {value:.1f}" for key, value in top_factors)
            parts.append(f"主要因子：{factor_text}")
    if item.get("industry"):
        parts.append(f"行业：{item['industry']}")
    if item.get("risk_level"):
        parts.append(f"风险等级：{item['risk_level']}")
    return "；".join(parts)


def _normalize_candidate(raw: Any, rank: int) -> Dict[str, Any]:
    item = _remove_non_finite_json_values(_to_plain(raw))
    if not isinstance(item, dict):
        item = {"code": str(item)}
    source = item.get("raw") if isinstance(item.get("raw"), dict) else item
    return {
        "rank": item.get("rank") or source.get("rank") or rank,
        "code": (
            item.get("code") or source.get("code")
            or item.get("symbol") or source.get("symbol")
            or item.get("stock_code") or source.get("stock_code") or ""
        ),
        "name": (
            item.get("name") or source.get("name")
            or item.get("stock_name") or source.get("stock_name") or ""
        ),
        "score": _first_present(item, source, "score", "final_score"),
        "screen_score": _first_present(item, source, "screen_score"),
        "reason": (
            item.get("reason") or source.get("reason")
            or source.get("ranking_reason") or source.get("risk_summary")
            or item.get("summary") or _build_candidate_reason(source)
        ),
        "risk_level": item.get("risk_level") or source.get("risk_level") or "",
        "risk_flags": item.get("risk_flags") or source.get("risk_flags") or [],
        "llm_score": _first_present(item, source, "llm_score"),
        "llm_confidence": _first_present(item, source, "llm_confidence"),
        "llm_sector": item.get("llm_sector") or source.get("llm_sector") or "",
        "llm_theme": item.get("llm_theme") or source.get("llm_theme") or "",
        "llm_tags": item.get("llm_tags") or source.get("llm_tags") or [],
        "llm_thesis": item.get("llm_thesis") or source.get("llm_thesis") or "",
        "llm_catalysts": item.get("llm_catalysts") or source.get("llm_catalysts") or [],
        "llm_risks": item.get("llm_risks") or source.get("llm_risks") or [],
        "llm_watch_items": item.get("llm_watch_items") or source.get("llm_watch_items") or [],
        "llm_invalidators": item.get("llm_invalidators") or source.get("llm_invalidators") or [],
        "llm_style_fit": item.get("llm_style_fit") or source.get("llm_style_fit") or "",
        "price": _first_present(item, source, "price"),
        "change_pct": _first_present(item, source, "change_pct"),
        "amount": _first_present(item, source, "amount"),
        "industry": item.get("industry") or source.get("industry") or "",
        "factor_scores": item.get("factor_scores") or source.get("factor_scores") or {},
        "post_analysis_summaries": item.get("post_analysis_summaries") or source.get("post_analysis_summaries") or {},
        "post_analysis_tags": item.get("post_analysis_tags") or source.get("post_analysis_tags") or [],
        "raw": source,
    }


def _normalize_candidates(raw: Any) -> List[Dict[str, Any]]:
    data = _to_plain(raw)
    items = data
    if isinstance(data, dict):
        for key in ("candidates", "picks", "items", "results", "stocks"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
    if not isinstance(items, list):
        return []
    return [_normalize_candidate(item, index + 1) for index, item in enumerate(items)]


# ── 模块公共 API ────────────────────────────────────────────────────────────

__all__ = [
    "ALPHASIFT_DSA_ADAPTER_MODULE",
    "ALPHASIFT_EXPECTED_MISSING_MODULES",
    "AlphaSiftError",
    "AlphaSiftDisabledError",
    "_get_dsa_adapter",
    "_get_adapter_callable",
    "_call_alphasift_screen",
    "_to_plain",
    "_normalize_candidates",
    "_normalize_candidate",
    "_remove_non_finite_json_values",
]
