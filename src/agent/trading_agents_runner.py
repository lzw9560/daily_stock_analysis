# -*- coding: utf-8 -*-
"""TradingAgents 分析引擎 — 直接调用 TradingAgentsGraph 执行 A股多Agent分析.

TradingAgents-astock 已作为主项目依赖安装，无需子进程。
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── TradingAgents 包导入 ──────────────────────────────────────────────────

try:
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from cli.stats_handler import StatsCallbackHandler
    _TA_AVAILABLE = True
except ImportError:
    _TA_AVAILABLE = False
    logger.warning("TradingAgents-astock 未安装，深度分析功能不可用。")

# ── mootdx 兼容补丁 ─────────────────────────────────────────────────────────
# mootdx bestip 失败后 stocks() 返回 counts=None，导致 TypeError: '>' not supported
# between instances of 'NoneType' and 'int'。在 mootdx 上游修复前，monkey-patch 兜底。

def _patch_mootdx_stocks():
    try:
        import pandas as pd
        from mootdx.quotes import Quotes

        _original_stocks = Quotes.stocks

        def _safe_stocks(self, market=None, **kwargs):
            try:
                return _original_stocks(self, market=market, **kwargs)
            except TypeError as e:
                if "'>' not supported between instances of 'NoneType' and 'int'" in str(e):
                    logger.warning("mootdx stocks() returned None counts (bestip failed), returning empty DataFrame")
                    return pd.DataFrame()
                raise

        Quotes.stocks = _safe_stocks
        logger.debug("mootdx stocks() monkey-patch applied")
    except ImportError:
        logger.debug("mootdx not available, skipping monkey-patch")
    except Exception:
        logger.debug("mootdx monkey-patch failed (non-blocking)", exc_info=True)

_patch_mootdx_stocks()

# ── 数据目录 ──────────────────────────────────────────────────────────────

_TA_DATA_ROOT = Path(os.getenv("TA_DATA_ROOT", Path(__file__).resolve().parent.parent.parent / "data" / "tradingagents"))


# ── 流水线阶段定义 ─────────────────────────────────────────────────────────

PIPELINE_STAGES: list[dict[str, str]] = [
    {"id": "market", "name": "技术分析", "icon": "📊", "report_key": "market_report"},
    {"id": "social", "name": "情绪分析", "icon": "💬", "report_key": "sentiment_report"},
    {"id": "news", "name": "新闻舆情", "icon": "📰", "report_key": "news_report"},
    {"id": "fundamentals", "name": "基本面", "icon": "📋", "report_key": "fundamentals_report"},
    {"id": "policy", "name": "政策分析", "icon": "🏛️", "report_key": "policy_report"},
    {"id": "hot_money", "name": "游资追踪", "icon": "🔥", "report_key": "hot_money_report"},
    {"id": "lockup", "name": "解禁监控", "icon": "🔒", "report_key": "lockup_report"},
    {"id": "quality_gate", "name": "质量门控", "icon": "✅", "report_key": "data_quality_summary"},
    {"id": "debate", "name": "多空辩论", "icon": "⚔️", "report_key": "investment_plan"},
    {"id": "trader", "name": "交易决策", "icon": "💹", "report_key": "trader_investment_plan"},
    {"id": "risk", "name": "风控评估", "icon": "🛡️", "report_key": "risk_debate_state"},
    {"id": "pm", "name": "最终决策", "icon": "👔", "report_key": "final_trade_decision"},
]

_REPORT_TO_STAGE = {s["report_key"]: s["id"] for s in PIPELINE_STAGES}
_ALL_REPORT_KEYS = [s["report_key"] for s in PIPELINE_STAGES]


def _strip_think(text: Any) -> str:
    """去掉 &lt;think&gt; 标签内容."""
    if isinstance(text, str):
        return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()
    return str(text) if text else ""


def _extract_text(raw: Any) -> str:
    """提取文本内容（兼容字符串、dict、list 等格式）"""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        return raw.get("judge_decision", raw.get("content", raw.get("text", json.dumps(raw, ensure_ascii=False))))
    if isinstance(raw, list):
        return "\n".join(_extract_text(item) for item in raw)
    return str(raw) if raw else ""


# ── 运行器 ─────────────────────────────────────────────────────────────────

class TradingAgentsRunner:
    """通过 TradingAgentsGraph 直接执行多Agent分析."""

    _MAX_CONCURRENT = 2
    _DEFAULT_RECURSION_LIMIT = int(os.getenv("TA_GRAPH_RECURSION_LIMIT", "150"))
    _semaphore = threading.BoundedSemaphore(_MAX_CONCURRENT)

    def __init__(self):
        self._graph_recursion_limit = self._DEFAULT_RECURSION_LIMIT

    @property
    def available(self) -> bool:
        """检查 TradingAgents 包是否可用."""
        return _TA_AVAILABLE

    def run(
        self,
        ticker: str,
        trade_date: str,
        base_url: str = "",
        model: str = "",
        on_progress: Optional[Callable] = None,
        on_result: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """执行分析并返回结果.

        Args:
            ticker: 股票代码
            trade_date: 分析日期 YYYY-MM-DD
            base_url: LLM 代理地址
            on_progress: 进度回调 (progress: dict) -> None
            on_result: 结果回调 (result: dict) -> None
            on_error: 错误回调 (error_msg: str) -> None

        Returns:
            {"signal": str, "stage_reports": dict, "elapsed": float}
        """
        if not self.available:
            raise RuntimeError("TradingAgents-astock 未安装，深度分析不可用。请确保已安装依赖。")

        # 获取并发槽位
        acquired = self._semaphore.acquire(timeout=300)
        if not acquired:
            raise RuntimeError("深度分析并发已满，请稍后再试（最多2个并行任务）")

        try:
            return self._run_internal(ticker, trade_date, base_url, model, on_progress, on_result, on_error)
        finally:
            self._semaphore.release()

    def _run_internal(
        self,
        ticker: str,
        trade_date: str,
        base_url: str,
        model: str,
        on_progress: Optional[Callable],
        on_result: Optional[Callable],
        on_error: Optional[Callable],
    ) -> Dict[str, Any]:
        start_time = time.time()

        config = self._build_config(base_url, model)

        # 确保数据目录存在
        _TA_DATA_ROOT.mkdir(parents=True, exist_ok=True)
        results_dir = _TA_DATA_ROOT / "results"
        cache_dir = _TA_DATA_ROOT / "cache"
        results_dir.mkdir(exist_ok=True)
        cache_dir.mkdir(exist_ok=True)

        config["results_dir"] = str(results_dir)
        config["data_cache_dir"] = str(cache_dir)

        # 设置 API key 环境变量，确保 TradingAgents 能正确使用
        # TradingAgents 对 openai provider 使用 OPENAI_API_KEY 环境变量
        api_key = config.pop("_api_key", "")
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
            logger.info("已设置 OPENAI_API_KEY 为匹配 channel 的 key")

        stats_handler = StatsCallbackHandler()

        graph = TradingAgentsGraph(
            debug=True,
            config=config,
            callbacks=[stats_handler],
        )

        init_state = graph.propagator.create_initial_state(ticker, trade_date)
        args = graph.propagator.get_graph_args(callbacks=[stats_handler])

        last_chunk: Dict[str, Any] = {}
        completed_stages: list[str] = []

        # 添加递归限制，防止 analyst 节点中 tool_call 无限循环
        args.setdefault("config", {})
        args["config"].setdefault("recursion_limit", self._graph_recursion_limit)

        for chunk in graph.graph.stream(init_state, **args):
            last_chunk = chunk

            # 检测新完成的阶段
            for report_key in _ALL_REPORT_KEYS:
                if report_key in _REPORT_TO_STAGE:
                    stage_id = _REPORT_TO_STAGE[report_key]
                    content = chunk.get(report_key)
                    if content and stage_id not in completed_stages:
                        completed_stages.append(stage_id)

            # 推断当前活跃阶段（第一个未完成的）
            current = completed_stages[-1] if completed_stages else "market"
            s = stats_handler.get_stats()
            progress = {
                "stage": current,
                "done_stages": completed_stages,
                "stats": {
                    "llm_calls": s["llm_calls"],
                    "tool_calls": s["tool_calls"],
                    "tokens_in": s["tokens_in"],
                    "tokens_out": s["tokens_out"],
                },
            }
            if on_progress:
                on_progress(progress)

        signal = graph.process_signal(last_chunk.get("final_trade_decision", ""))

        # 保存日志
        try:
            graph.ticker = ticker
            graph._log_state(trade_date, last_chunk)
        except Exception:
            logger.exception("保存 TradingAgents 日志失败")

        # 提取各阶段报告
        stage_reports: Dict[str, str] = {}
        for s in PIPELINE_STAGES:
            raw = last_chunk.get(s["report_key"], "")
            text = _extract_text(raw)
            if text.strip():
                stage_reports[s["id"]] = _strip_think(text)

        elapsed = time.time() - start_time

        result = {
            "signal": signal,
            "stage_reports": stage_reports,
            "elapsed": elapsed,
        }

        if on_result:
            on_result(result)

        return result

    def _build_config(self, base_url: str = "", model: str = "") -> Dict[str, Any]:
        """构建 TradingAgents 配置字典.

        模型优先级：前端传入 model > TA_DEEP_THINK_LLM 环境变量 > LITELLM_MODEL > 默认值.
        base_url 优先级：显式传入 base_url > LLM_CHANNELS 匹配 > OPENAI_BASE_URL.
        api_key: 从 LLM_CHANNELS 匹配的 channel 获取，确保 TradingAgents 能正确使用.
        """
        config = DEFAULT_CONFIG.copy()

        # ── LLM provider & model ──
        # 优先使用前端显式传入的 model，其次才 fallback 到环境变量
        raw_model = (model or os.getenv("LITELLM_MODEL", "")).strip()
        if "/" in raw_model:
            derived_provider = raw_model.split("/")[0]
            derived_model = raw_model.split("/", 1)[1]
        else:
            derived_provider = "openai"
            derived_model = raw_model if raw_model else "deepseek-chat"

        # 仅当 TA_DEEP_THINK_LLM 被设置时才覆盖（记录警告），否则使用前端/LITELLM_MODEL 值
        env_deep = os.getenv("TA_DEEP_THINK_LLM", "").strip()
        env_quick = os.getenv("TA_QUICK_THINK_LLM", "").strip()
        env_provider = os.getenv("TA_LLM_PROVIDER", "").strip()

        if env_deep:
            logger.warning("TA_DEEP_THINK_LLM=%s overrides derived model=%s", env_deep, derived_model)
            derived_model = env_deep
        if env_quick:
            logger.warning("TA_QUICK_THINK_LLM=%s overrides derived quick model=%s", env_quick, derived_model)
        if env_provider:
            logger.warning("TA_LLM_PROVIDER=%s overrides derived provider=%s", env_provider, derived_provider)
            derived_provider = env_provider

        config["llm_provider"] = derived_provider
        config["deep_think_llm"] = env_deep or derived_model
        config["quick_think_llm"] = env_quick or derived_model

        # ── LLM 代理地址和 API Key（从 LLM_CHANNELS 查找匹配的 channel）──
        backend_url, api_key = self._resolve_channel(raw_model)
        if base_url:
            backend_url = base_url
        config["backend_url"] = backend_url or None

        # 存储 API key 供 _run_internal 使用
        config["_api_key"] = api_key

        # ── 数据源 ──
        config["data_vendors"] = {
            "core_stock_apis": "a_stock",
            "technical_indicators": "a_stock",
            "fundamental_data": "a_stock",
            "news_data": "a_stock",
            "signal_data": "a_stock",
        }

        # ── 分析参数 ──
        config["max_debate_rounds"] = int(os.getenv("TA_MAX_DEBATE_ROUNDS", "1"))
        config["max_risk_discuss_rounds"] = int(os.getenv("TA_MAX_RISK_ROUNDS", "1"))
        config["output_language"] = "Chinese"

        return config

    def _resolve_channel(self, model: str) -> tuple[str, str]:
        """根据模型名称从 LLM_CHANNELS 查找匹配的 channel，返回 (base_url, api_key)."""
        if not model:
            return os.getenv("OPENAI_BASE_URL", ""), os.getenv("OPENAI_API_KEY", "")

        try:
            from src.config import get_config
            config = get_config()
            channels = getattr(config, "llm_channels", []) or []
            model_lower = model.lower()

            for ch in channels:
                ch_models = ch.get("models", [])
                if any(model_lower in m.lower() or m.lower() in model_lower for m in ch_models):
                    ch_url = ch.get("base_url", "")
                    ch_keys = ch.get("api_keys", [])
                    ch_key = ch_keys[0] if ch_keys else ""
                    if ch_url:
                        logger.info("Resolved channel '%s': base_url=%s, has_key=%s",
                                   ch.get("name"), ch_url, bool(ch_key))
                        return ch_url, ch_key
        except Exception:
            logger.debug("Failed to resolve channel from LLM_CHANNELS, using defaults")

        return os.getenv("OPENAI_BASE_URL", ""), os.getenv("OPENAI_API_KEY", "")

    @staticmethod
    def get_pipeline_stages() -> list[dict[str, str]]:
        """获取流水线阶段定义."""
        return PIPELINE_STAGES
