# -*- coding: utf-8 -*-
"""策略信号与板块轮动 API 端点

scan 端点依赖 efinance 包获取实时行情数据。
efinance 安装：pip install efinance>=0.5.0
如 efinance 不可用，会自动降级到 DataFetcherManager 统一数据源。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()


# ======================== Scan ========================

@router.post("/scan", summary="扫描策略信号")
def scan_signals(request: Dict[str, Any] | None = None):
    """扫描短线战法信号

    数据源：efinance 实时行情（优先级最高），降级到 DataFetcherManager

    Request body (optional):
        strategies: 策略列表，默认全部
        min_confidence: 最低置信度，默认60
        signal_type: 信号类型 buy/sell/alert
    """
    try:
        req = request or {}
        strategies_filter = req.get("strategies", None)
        min_confidence = req.get("min_confidence", 60)
        filter_signal_type = req.get("signal_type", None)

        # 收集数据（优先 efinance，降级到 DataFetcherManager）
        stock_data = _gather_stock_data()
        limit_up_data = _gather_limit_up_data()
        seal_plate_data = _gather_seal_plate_data()

        if not stock_data:
            return {
                "signals": [],
                "total": 0,
                "strategies": [],
                "note": "无法获取实时行情数据（efinance 和 DataFetcherManager 均不可用）",
            }

        from src.services.short_term_strategy import ShortTermStrategyEngine
        engine = ShortTermStrategyEngine()
        raw_signals = engine.scan_all(stock_data, limit_up_data, seal_plate_data)

        # 过滤与格式化
        signals = []
        strategy_counts: Dict[str, int] = {}
        for sig in raw_signals:
            if min_confidence and sig.confidence < min_confidence:
                continue
            if strategies_filter and sig.strategy not in strategies_filter:
                continue
            if filter_signal_type and sig.signal_type != filter_signal_type:
                continue

            entry_price = sig.entry_price_range[0] if sig.entry_price_range else 0
            signals.append({
                "id": f"{sig.code}_{sig.strategy}_{int(datetime.now().timestamp())}",
                "code": sig.code,
                "name": sig.name,
                "strategy": sig.strategy,
                "strategy_name": sig.strategy,
                "signal_type": sig.signal_type,
                "entry_method": "market",
                "confidence": sig.confidence,
                "entry_price": entry_price,
                "current_price": entry_price,
                "stop_loss": sig.stop_loss,
                "take_profit": sig.take_profit,
                "max_position_pct": 20,
                "sector": "",
                "sentiment_phase": "",
                "reason": sig.reason,
                "risk_level": "high" if sig.confidence < 70 else ("medium" if sig.confidence < 85 else "low"),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            strategy_counts[sig.strategy] = strategy_counts.get(sig.strategy, 0) + 1

        return {
            "signals": signals,
            "total": len(signals),
            "strategies": _get_perf_list(strategy_counts),
        }
    except Exception as exc:
        logger.error("扫描策略信号失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(exc)})


# ======================== Performance ========================

@router.get("/performance", summary="获取策略绩效")
def get_performance():
    """获取所有策略的历史绩效统计"""
    try:
        from src.services.strategy_performance_service import StrategyPerformanceService
        perf_svc = StrategyPerformanceService()
        stats = perf_svc.get_strategy_stats()
        return {"strategies": _stats_to_perf_list(stats)}
    except Exception as exc:
        logger.error("获取策略绩效失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(exc)})


# ======================== Sector Rotation ========================

@router.get("/sector-rotation", summary="获取板块轮动数据")
def get_sector_rotation():
    """获取板块强度评分、主线识别和轮动信号

    数据源：RealTimeDataService（efinance + DataFetcherManager 聚合）
    """
    try:
        from src.services.real_time_data_service import RealTimeDataService
        from src.services.sector_analysis_service import SectorAnalysisService

        rts = RealTimeDataService()

        # 获取板块排名
        sector_rankings_result = rts.get_sector_rankings(n=20)
        if isinstance(sector_rankings_result, tuple) and len(sector_rankings_result) >= 1:
            sector_data = sector_rankings_result[0]
        else:
            sector_data = sector_rankings_result if isinstance(sector_rankings_result, list) else []

        # 获取涨停数据
        limit_up_data = rts.get_limit_up_pool(n=50)

        # 获取资金流向
        money_flow = rts.get_money_flow(top_n=50)

        # 格式化 sector_data
        formatted_sectors = []
        for i, s in enumerate(sector_data if isinstance(sector_data, list) else []):
            if isinstance(s, dict):
                formatted_sectors.append({
                    "sector": s.get("name", s.get("sector", "")),
                    "change_pct": float(s.get("change_pct", s.get("change", 0)) or 0),
                    "volume": float(s.get("volume", 0) or 0),
                })

        # 格式化 capital_flow
        formatted_flow = []
        for f in (money_flow if isinstance(money_flow, list) else []):
            if isinstance(f, dict):
                formatted_flow.append({
                    "sector": f.get("sector", f.get("industry", f.get("name", ""))),
                    "net_inflow": float(f.get("net_inflow", f.get("net_amount", 0)) or 0),
                })

        svc = SectorAnalysisService()
        scores = svc.analyze_sector_strength(formatted_sectors, limit_up_data, formatted_flow)

        main_lines_list = svc.identify_main_line([scores]) if scores else []
        main_lines = [ml.get("sector", "") for ml in main_lines_list]

        sectors_output = []
        for s in scores:
            sectors_output.append({
                "sector": s.get("sector", ""),
                "strength": s.get("score", 0),
                "rank": s.get("rank", 0),
                "stocks": [],
            })

        rotation_signals = _build_rotation_signals(svc, scores)

        return {
            "sectors": sectors_output,
            "mainline": main_lines,
            "rotation_signals": rotation_signals,
        }
    except Exception as exc:
        logger.error("获取板块轮动数据失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(exc)})


# ======================== Helpers ========================

def _gather_stock_data() -> List[Dict[str, Any]]:
    """收集股票行情数据

    优先级：
    1. efinance（实时行情，覆盖全A股）
    2. DataFetcherManager 统一数据源降级
    """
    # 尝试 efinance 实时行情
    data = _gather_via_efinance()
    if data:
        return data

    # 降级到 DataFetcherManager
    return _gather_via_data_fetcher()


def _gather_via_efinance() -> List[Dict[str, Any]]:
    """通过 efinance 获取实时行情数据"""
    try:
        import efinance as ef
        df = ef.stock.get_realtime_quotes()
        if df is None or df.empty:
            logger.info("efinance 返回空数据")
            return []

        result = []
        for _, row in df.iterrows():
            try:
                result.append({
                    "code": str(row.get("股票代码", "")),
                    "name": str(row.get("股票名称", "")),
                    "close": float(row.get("最新价", 0) or 0),
                    "open": float(row.get("开盘价", 0) or 0),
                    "high": float(row.get("最高价", 0) or 0),
                    "low": float(row.get("最低价", 0) or 0),
                    "volume": float(row.get("成交量", 0) or 0),
                    "prev_close": float(row.get("昨收", 0) or 0),
                    "change_pct": float(row.get("涨跌幅", 0) or 0),
                    "volume_ratio": float(row.get("量比", 1) or 1),
                    "sectors": str(row.get("所属行业", row.get("sector", ""))),
                })
            except Exception:
                continue

        logger.info("efinance 获取 %d 条实时行情", len(result))
        return result
    except ImportError:
        logger.warning("efinance 未安装，请执行: pip install efinance>=0.5.0")
        return []
    except Exception as exc:
        logger.warning("efinance 获取行情失败: %s", exc)
        return []


def _gather_via_data_fetcher() -> List[Dict[str, Any]]:
    """通过 DataFetcherManager 降级获取数据"""
    try:
        from src.services.real_time_data_service import RealTimeDataService
        rts = RealTimeDataService()
        manager = rts._get_manager()
        if not manager:
            return []

        # 尝试通过 manager 获取实时行情
        quotes = manager.fetch_realtime_quotes()
        if not quotes:
            return []

        result = []
        for q in quotes:
            try:
                if isinstance(q, dict):
                    result.append({
                        "code": str(q.get("code", q.get("symbol", ""))),
                        "name": str(q.get("name", "")),
                        "close": float(q.get("price", q.get("close", 0)) or 0),
                        "open": float(q.get("open", 0) or 0),
                        "high": float(q.get("high", 0) or 0),
                        "low": float(q.get("low", 0) or 0),
                        "volume": float(q.get("volume", 0) or 0),
                        "prev_close": float(q.get("prev_close", 0) or 0),
                        "change_pct": float(q.get("change_pct", 0) or 0),
                        "volume_ratio": float(q.get("volume_ratio", 1) or 1),
                        "sectors": str(q.get("sector", q.get("industry", ""))),
                    })
            except Exception:
                continue
        return result
    except Exception as exc:
        logger.warning("DataFetcherManager 获取行情失败: %s", exc)
        return []


def _gather_limit_up_data() -> List[Dict[str, Any]]:
    """收集涨停板数据"""
    try:
        from src.services.real_time_data_service import RealTimeDataService
        return RealTimeDataService().get_limit_up_pool(n=50)
    except Exception:
        return []


def _gather_seal_plate_data() -> List[Dict[str, Any]]:
    """收集封板数据（复用涨停数据）"""
    try:
        return _gather_limit_up_data()
    except Exception:
        return []


def _get_perf_list(strategy_counts: Dict[str, int]) -> List[Dict[str, Any]]:
    """生成带绩效的列表"""
    try:
        from src.services.strategy_performance_service import StrategyPerformanceService
        stats = StrategyPerformanceService().get_strategy_stats()
        return _stats_to_perf_list(stats, strategy_counts)
    except Exception:
        return [
            {
                "strategy": n, "strategy_name": n,
                "total_signals": c, "win_rate": 0, "avg_pnl": 0,
                "profit_factor": 0, "max_drawdown": 0,
                "sharpe_ratio": 0, "last_month_win_rate": 0,
            }
            for n, c in strategy_counts.items()
        ]


def _stats_to_perf_list(
    stats: Dict[str, Any],
    extra_counts: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """将策略统计转为前端格式"""
    by_strategy = stats.get("by_strategy", {})
    result = []
    for name, s in by_strategy.items():
        extra = extra_counts.get(name, 0) if extra_counts else 0
        result.append({
            "strategy": name,
            "strategy_name": name,
            "total_signals": extra or s.get("total", 0),
            "win_rate": s.get("win_rate", 0),
            "avg_pnl": s.get("avg_pl_pct", 0),
            "profit_factor": s.get("profit_factor", 0),
            "max_drawdown": s.get("max_drawdown", 0),
            "sharpe_ratio": 0,
            "last_month_win_rate": s.get("win_rate", 0),
        })
    return result


def _build_rotation_signals(svc, scores: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """构建板块轮动信号"""
    try:
        rotations = svc.detect_rotation(scores, scores)
        return [
            {"from": r.get("from_sector", ""), "to": r.get("to_sector", ""),
             "confidence": r.get("confidence", 0)}
            for r in (rotations or [])
        ]
    except Exception:
        return []
