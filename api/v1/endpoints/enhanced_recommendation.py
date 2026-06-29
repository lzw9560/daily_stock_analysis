# -*- coding: utf-8 -*-
"""增强版推荐系统 API 端点.

整合以下服务：
1. 综合推荐引擎（现有）
2. 策略胜率分析（新增）
3. 板块联动分析（新增）
4. 情绪周期分析（新增）
5. 短线战法信号（新增）
6. 执行规划（现有，整合）
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.services.strategy_performance_service import StrategyPerformanceService
from src.services.sector_analysis_service import SectorAnalysisService
from src.services.sentiment_engine import SentimentEngine
from src.services.short_term_strategy import ShortTermStrategyEngine

from src.services.logic_closure_service import LogicClosureService
from src.services.execution_planner import ExecutionPlanner

logger = logging.getLogger(__name__)
router = APIRouter(tags=["增强推荐系统"])


@router.get("/strategy-stats")
async def get_strategy_stats(
    start_date: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    min_samples: int = Query(5, ge=1, description="最小样本数"),
):
    """获取策略分类统计（按战法/信号类型/板块/情绪阶段）."""
    try:
        svc = StrategyPerformanceService()
        return svc.get_strategy_stats(
            start_date=start_date,
            end_date=end_date,
            min_samples=min_samples,
        )
    except Exception as e:
        logger.error("获取策略统计失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy-ranking")
async def get_strategy_ranking(
    limit: int = Query(10, ge=1, le=50, description="返回数量"),
    min_samples: int = Query(5, ge=1, description="最小样本数"),
):
    """获取策略表现排名（综合评分）."""
    try:
        svc = StrategyPerformanceService()
        return svc.get_top_performing_strategies(
            limit=limit,
            min_samples=min_samples,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy-comparison")
async def compare_strategies(
    strategies: str = Query(..., description="策略列表，逗号分隔，如:首板挖掘,连板接力,低吸龙头"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """策略对比分析."""
    try:
        strat_list = [s.strip() for s in strategies.split(",") if s.strip()]
        if not strat_list:
            raise HTTPException(status_code=400, detail="至少需要一个策略")
        svc = StrategyPerformanceService()
        return svc.get_strategy_comparison(
            strategies=strat_list,
            start_date=start_date,
            end_date=end_date,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/win-rate-trend")
async def get_win_rate_trend(
    days: int = Query(30, ge=7, le=365, description="回溯天数"),
    window: int = Query(10, ge=5, le=50, description="窗口大小"),
):
    """滚动窗口胜率趋势."""
    try:
        svc = StrategyPerformanceService()
        return svc.get_rolling_win_rate(days=days, window=window)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sentiment", deprecated=True)
async def get_sentiment(
    limit_up_count: Optional[int] = Query(None, description="涨停数"),
    limit_down_count: Optional[int] = Query(None, description="跌停数"),
    seal_plate_count: Optional[int] = Query(None, description="封板数"),
    broken_seal_count: Optional[int] = Query(None, description="炸板数"),
    highest_board: Optional[int] = Query(None, description="最高连板"),
    connectivity_count: Optional[int] = Query(None, description="连板股数量"),
    advance_count: Optional[int] = Query(None, description="上涨家数"),
    decline_count: Optional[int] = Query(None, description="下跌家数"),
    north_flow: Optional[float] = Query(None, description="北向资金(亿元)"),
    main_force_flow: Optional[float] = Query(None, description="主力资金(亿元)"),
    turnover_total: Optional[float] = Query(None, description="总成交额(亿元)"),
    turnover_change: Optional[float] = Query(None, description="成交额变化(%)"),
):
    """[已废弃] 情绪周期分析。请使用 /api/v1/sentiment/sector-heatmap 获取完整的板块热力图和情绪数据。
    
    当参数未提供时，自动从实时数据源拉取。
    """
    try:
        # 如果参数未提供，自动拉取实时数据
        if any(v is None for v in [limit_up_count, advance_count, highest_board]):
            realtime_data = _fetch_sentiment_realtime_data()
            if limit_up_count is None:
                limit_up_count = realtime_data.get("limit_up_count", 45)
            if limit_down_count is None:
                limit_down_count = realtime_data.get("limit_down_count", 3)
            if seal_plate_count is None:
                seal_plate_count = realtime_data.get("seal_plate_count", 40)
            if broken_seal_count is None:
                broken_seal_count = realtime_data.get("broken_seal_count", 8)
            if highest_board is None:
                highest_board = realtime_data.get("highest_board", 5)
            if connectivity_count is None:
                connectivity_count = realtime_data.get("connectivity_count", 15)
            if advance_count is None:
                advance_count = realtime_data.get("advance_count", 2800)
            if decline_count is None:
                decline_count = realtime_data.get("decline_count", 2200)
            if north_flow is None:
                north_flow = realtime_data.get("north_flow", 52.0)
            if main_force_flow is None:
                main_force_flow = realtime_data.get("main_force_flow", 15.0)
            if turnover_total is None:
                turnover_total = realtime_data.get("turnover_total", 9500.0)
            if turnover_change is None:
                turnover_change = realtime_data.get("turnover_change", 5.0)

        engine = SentimentEngine()
        metrics = engine.compute_sentiment_metrics(
            limit_up_count=limit_up_count or 45,
            limit_down_count=limit_down_count or 3,
            seal_plate_count=seal_plate_count or 40,
            broken_seal_count=broken_seal_count or 8,
            highest_board=highest_board or 5,
            connectivity_count=connectivity_count or 15,
            advance_count=advance_count or 2800,
            decline_count=decline_count or 2200,
            north_flow=north_flow or 52.0,
            main_force_flow=main_force_flow or 15.0,
            turnover_total=turnover_total or 9500.0,
            turnover_change=turnover_change or 5.0,
        )
        recommendation = engine.get_phase_recommendation(metrics["phase"])
        return {
            "metrics": metrics,
            "recommendation": recommendation,
        }
    except Exception as e:
        logger.error("情绪分析失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _fetch_sentiment_realtime_data() -> Dict[str, Any]:
    """为情绪分析拉取实时市场数据."""
    try:
        from src.services.real_time_data_service import RealTimeDataService
        from src.services.recommendation_system_service import RecommendationSystemService
        
        svc = RealTimeDataService()
        stats = svc.get_market_stats() or {}
        
        # 获取涨停池以计算连板数据
        pool = svc.get_limit_up_pool(n=30) or []
        high_board = max((p.get("consecutive_boards", 0) or 0 for p in pool), default=0)
        connectivity = sum(1 for p in pool if (p.get("consecutive_boards", 0) or 0) >= 2)
        seal_count = sum(1 for p in pool if p.get("seal_status") == "sealed")
        broken_count = sum(1 for p in pool if p.get("seal_status") == "broken")
        
        # 获取北向资金
        north_flow_val = 0.0
        try:
            north_ctx = svc.get_north_bound_context(top_n=5) or {}
            north_flow_val = float(north_ctx.get("today_net_inflow", 0) or 0)
        except Exception:
            pass
        
        return {
            "limit_up_count": stats.get("limit_up_count", 0),
            "limit_down_count": stats.get("limit_down_count", 0),
            "seal_plate_count": seal_count or stats.get("limit_up_count", 40),
            "broken_seal_count": broken_count or 0,
            "highest_board": int(high_board),
            "connectivity_count": connectivity,
            "advance_count": stats.get("advance_count", 0),
            "decline_count": stats.get("decline_count", 0),
            "north_flow": north_flow_val,
            "main_force_flow": 0.0,
            "turnover_total": stats.get("total_turnover", 0) or 0,
            "turnover_change": 0.0,
        }
    except Exception as e:
        logger.warning("实时情绪数据拉取失败: %s", e)
        return {}


@router.get("/sector-analysis")
async def get_sector_analysis(
    sector_data: str = Query("", description="板块数据JSON"),
    limit_up_data: str = Query("", description="涨停数据JSON"),
    capital_flow_data: str = Query("", description="资金流向JSON"),
):
    """板块联动分析.
    
    支持两种模式：
    1. 外部传入 JSON 数据（通过 Query 参数）
    2. 自动从实时数据源拉取（当参数为空时）
    """
    try:
        import json
        
        if sector_data or limit_up_data or capital_flow_data:
            sectors = json.loads(sector_data) if sector_data else []
            limit_ups = json.loads(limit_up_data) if limit_up_data else []
            flows = json.loads(capital_flow_data) if capital_flow_data else []
        else:
            # 自动拉取实时数据
            from src.services.real_time_data_service import RealTimeDataService
            svc = RealTimeDataService()
            sectors, _ = svc.get_sector_rankings(n=20) if hasattr(svc, 'get_sector_rankings') else ([], [])
            limit_ups = svc.get_limit_up_pool(n=30) if hasattr(svc, 'get_limit_up_pool') else []
            flows = svc.get_money_flow(top_n=10) if hasattr(svc, 'get_money_flow') else []

        svc = SectorAnalysisService()
        ranked = svc.analyze_sector_strength(sectors, limit_ups, flows)
        return {"ranked_sectors": ranked, "top_3": ranked[:3]}
    except Exception as e:
        logger.error("板块联动分析失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/short-term-signals")
async def get_short_term_signals(
    stocks_json: str = Query("", description="股票数据JSON"),
    limit_up_json: str = Query("", description="涨停数据JSON"),
    seal_json: str = Query("", description="封板数据JSON"),
):
    """短线战法信号扫描.
    
    支持两种模式：
    1. 外部传入 JSON 数据（通过 Query 参数）
    2. 自动从实时数据源拉取（当参数为空时）
    """
    try:
        import json
        
        # 模式1：使用传入的数据
        if stocks_json or limit_up_json or seal_json:
            stocks = json.loads(stocks_json) if stocks_json else []
            limit_ups = json.loads(limit_up_json) if limit_up_json else []
            seals = json.loads(seal_json) if seal_json else []
        else:
            # 模式2：自动拉取实时数据
            stocks = _fetch_realtime_stocks_for_signals()
            limit_ups = _fetch_realtime_limit_up_for_signals()
            seals = [s for s in limit_ups if s.get("seal_status") == "sealed"]

        engine = ShortTermStrategyEngine()
        signals = engine.scan_all(stocks, limit_ups, seals)
        
        # 按策略分组统计
        by_strategy: Dict[str, int] = {}
        for s in signals:
            strat = s.strategy or "unknown"
            by_strategy[strat] = by_strategy.get(strat, 0) + 1
            
        return {
            "signals": [s.to_dict() for s in signals],
            "total": len(signals),
            "by_strategy": by_strategy,
        }
    except Exception as e:
        logger.error("短线战法信号扫描失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _fetch_realtime_stocks_for_signals() -> List[Dict[str, Any]]:
    """为短线信号扫描拉取实时股票数据."""
    try:
        import efinance as ef
        df = ef.stock.get_realtime_quotes()
        if df is None or df.empty:
            return []
        result = []
        for _, row in df.head(300).iterrows():
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
                    "sectors": str(row.get("所属行业", "")),
                })
            except Exception:
                continue
        return result
    except Exception as e:
        logger.warning("实时股票数据拉取失败: %s", e)
        return []


def _fetch_realtime_limit_up_for_signals() -> List[Dict[str, Any]]:
    """为短线信号扫描拉取涨停池数据."""
    try:
        from src.services.real_time_data_service import RealTimeDataService
        svc = RealTimeDataService()
        pool = svc.get_limit_up_pool(n=30)
        return pool or []
    except Exception as e:
        logger.warning("涨停池数据拉取失败: %s", e)
        return []


@router.get("/execution-plan")
async def get_execution_plan(
    code: str = Query(..., description="股票代码"),
    spot: float = Query(..., description="当前价格"),
    vol: float = Query(0.3, description="波动率"),
    horizon_days: int = Query(5, description="持有天数"),
    total_capital: float = Query(100000, description="总资金"),
):
    """执行规划：MonteCarlo模拟 + Kelly仓位 + VaR."""
    try:
        planner = ExecutionPlanner()
        plan = planner.generate_execution_plan(
            symbol=code,
            spot=spot,
            vol=vol,
            horizon_days=horizon_days,
            total_capital=total_capital,
        )
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
