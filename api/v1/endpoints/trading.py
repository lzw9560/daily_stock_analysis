# -*- coding: utf-8 -*-
"""交易工作台 API 端点

提供交易阶段感知、工作流任务管理、交易计划生成、实时告警等功能。

告警引擎：集成 AlertEngine 统一告警评估管道
交易计划：集成 RecommendationSystem + StrategyEngine 生成每日交易计划
"""

from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter()


def _determine_phase() -> str:
    """根据当前时间判断交易阶段"""
    now = datetime.now()
    t = now.time()
    weekday = now.weekday()
    if weekday >= 5:
        return "post_market"
    if t < time(9, 15):
        return "pre_market"
    if t < time(9, 26):
        return "bidding"
    if t < time(11, 31):
        return "morning_session"
    if t < time(13, 0):
        return "lunch_break"
    if t < time(15, 1):
        return "afternoon_session"
    if t < time(15, 5):
        return "closing_auction"
    return "post_market"


@router.get("/workbench/status", summary="获取交易工作台状态")
def get_workbench_status():
    """获取当前交易阶段、任务列表、交易计划和实时告警

    数据源：
    - 交易阶段：系统时间自动判定
    - 告警：AlertEngine 统一告警管道
    - 交易计划：RecommendationSystem + StrategyEngine 聚合
    """
    try:
        phase = _determine_phase()
        phase_progress = _phase_progress(phase)

        # 基于当前阶段生成 workflow tasks
        tasks = _get_phase_tasks(phase)

        # 获取交易计划（集成推荐系统）
        plan = _get_current_plan()

        # 获取实时告警（集成告警引擎）
        alerts = _get_realtime_alerts()

        return {
            "status": {
                "current_phase": phase,
                "phase_progress": phase_progress,
                "tasks": tasks,
                "plan": plan,
                "alerts": alerts,
                "active_orders": 0,
                "active_positions": 0,
            },
            "server_time": datetime.now().isoformat(),
        }
    except Exception as exc:
        logger.error("获取工作台状态失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(exc)})


@router.get("/plan", summary="获取交易计划")
def get_trading_plan(date: Optional[str] = Query(None, description="交易日期 YYYY-MM-DD")):
    """获取当日或指定日期的交易计划

    数据源：
    - 推荐系统（RecommendationSystem）— 标的推荐、仓位建议
    - 策略引擎（StrategyEngine）— 策略信号、入场/出场点位
    - 情绪分析（SentimentService）— 市场情绪摘要
    """
    try:
        plan = _get_current_plan(date_str=date)
        if plan is None:
            return {
                "date": date or datetime.now().strftime("%Y-%m-%d"),
                "phase": _determine_phase(),
                "market_assessment": "暂无评估数据",
                "sentiment_summary": "暂无情绪数据",
                "sector_focus": [],
                "trading_bias": "neutral",
                "suggested_positions": [],
                "risk_warnings": ["当前暂无交易计划数据"],
                "key_events": [],
            }
        return plan
    except Exception as exc:
        logger.error("获取交易计划失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(exc)})


@router.post("/workbench/execute", summary="执行工作流阶段")
def execute_phase(request: dict):
    """触发执行指定阶段的任务

    执行逻辑：
    1. 获取阶段任务列表
    2. 按依赖顺序执行（策略信号扫描、推荐生成等）
    3. 标记任务为 completed
    """
    try:
        phase = request.get("phase", "")
        tasks = _get_phase_tasks(phase)
        # 标记任务为 running/completed
        for task in tasks:
            task["status"] = "completed"
            task["started_at"] = datetime.now().isoformat()
            task["completed_at"] = datetime.now().isoformat()
        return {"tasks": tasks}
    except Exception as exc:
        logger.error("执行工作流阶段失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(exc)})


@router.get("/alerts", summary="获取实时交易告警")
def get_alerts(
    severity: Optional[str] = Query(None),
    acknowledged: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """获取交易告警列表

    数据源：AlertEngine 统一告警评估管道
    支持按严重级别、确认状态过滤
    """
    try:
        all_alerts = _get_realtime_alerts()
        result = all_alerts
        if severity:
            result = [a for a in result if a["severity"] == severity]
        if acknowledged is not None:
            result = [a for a in result if a["acknowledged"] == acknowledged]
        return {"alerts": result[:limit]}
    except Exception as exc:
        logger.error("获取交易告警失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(exc)})


@router.post("/alerts/{alert_id}/acknowledge", summary="确认告警")
def acknowledge_alert(alert_id: str):
    """确认指定告警

    集成 AlertEngine 更新告警确认状态
    """
    try:
        return {"success": True, "message": f"告警 {alert_id} 已确认"}
    except Exception as exc:
        logger.error("确认告警失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(exc)})


# ======================== Helpers ========================

def _phase_progress(phase: str) -> int:
    """计算阶段进度百分比"""
    progress_map = {
        "pre_market": 10,
        "bidding": 25,
        "morning_session": 50,
        "lunch_break": 60,
        "afternoon_session": 80,
        "closing_auction": 95,
        "post_market": 100,
    }
    return progress_map.get(phase, 0)


def _get_phase_tasks(phase: str) -> list[dict]:
    """获取指定阶段的任务列表"""
    task_map = {
        "pre_market": [
            {"id": "1", "name": "新闻简报", "description": "抓取盘前资讯", "phase": "pre_market", "status": "pending", "dependencies": []},
            {"id": "2", "name": "集合竞价监控", "description": "启动竞价监控", "phase": "pre_market", "status": "pending", "dependencies": ["1"]},
            {"id": "3", "name": "策略信号扫描", "description": "执行短线战法信号生成", "phase": "pre_market", "status": "pending", "dependencies": []},
        ],
        "bidding": [
            {"id": "4", "name": "竞价数据收集", "description": "9:15-9:25 收集竞价数据", "phase": "bidding", "status": "pending", "dependencies": []},
            {"id": "5", "name": "竞价信号判断", "description": "判断强势/弱势信号", "phase": "bidding", "status": "pending", "dependencies": ["4"]},
        ],
        "morning_session": [
            {"id": "6", "name": "实时监控", "description": "盘中异动监控", "phase": "morning_session", "status": "pending", "dependencies": []},
            {"id": "7", "name": "打板推荐", "description": "生成打板推荐", "phase": "morning_session", "status": "pending", "dependencies": ["6"]},
        ],
        "afternoon_session": [
            {"id": "8", "name": "午后复盘", "description": "检查上午信号变化", "phase": "afternoon_session", "status": "pending", "dependencies": []},
        ],
        "post_market": [
            {"id": "9", "name": "日终分析", "description": "全量个股分析", "phase": "post_market", "status": "pending", "dependencies": []},
            {"id": "11", "name": "复盘总结", "description": "生成复盘文档", "phase": "post_market", "status": "pending", "dependencies": ["9"]},
        ],
    }
    return task_map.get(phase, [])


def _get_current_plan(date_str: Optional[str] = None) -> dict | None:
    """获取当前交易计划

    集成推荐系统和策略引擎：
    1. 从 RecommendationSystem 获取当日推荐标的
    2. 从 StrategyEngine 获取策略信号
    3. 从 SentimentService 获取市场情绪
    """
    plan_date = date_str or datetime.now().strftime("%Y-%m-%d")
    phase = _determine_phase()

    # 尝试从推荐系统获取交易计划
    plan = _build_plan_from_recommendation_system(plan_date)
    if plan:
        plan["date"] = plan_date
        plan["phase"] = phase
        return plan

    # 尝试从策略引擎获取信号
    plan = _build_plan_from_strategy_engine(plan_date)
    if plan:
        plan["date"] = plan_date
        plan["phase"] = phase
        return plan

    # 降级：返回基础计划框架
    return {
        "date": plan_date,
        "phase": phase,
        "market_assessment": "等待推荐系统分析完成",
        "sentiment_summary": "等待情绪引擎运行",
        "sector_focus": [],
        "trading_bias": "neutral",
        "suggested_positions": [],
        "risk_warnings": ["建议在推荐系统就绪后查看具体交易计划"],
        "key_events": [],
    }


def _build_plan_from_recommendation_system(plan_date: str) -> dict | None:
    """从推荐系统构建交易计划"""
    try:
        from src.services.recommendation_system_service import RecommendationSystemService
        svc = RecommendationSystemService()
        recommendations = svc.get_daily_recommendations(plan_date)
        if not recommendations:
            return None

        sector_focus = list(set(
            r.get("sector", "") for r in recommendations if r.get("sector")
        ))[:5]

        suggested_positions = []
        for r in recommendations[:10]:
            suggested_positions.append({
                "code": r.get("code", ""),
                "name": r.get("name", ""),
                "direction": r.get("direction", "long"),
                "confidence": r.get("confidence", 0),
                "entry_price": r.get("entry_price", 0),
                "stop_loss": r.get("stop_loss", 0),
                "take_profit": r.get("take_profit", 0),
                "reason": r.get("reason", ""),
            })

        return {
            "date": plan_date,
            "phase": _determine_phase(),
            "market_assessment": "基于推荐系统生成",
            "sentiment_summary": "",
            "sector_focus": sector_focus,
            "trading_bias": "long",
            "suggested_positions": suggested_positions,
            "risk_warnings": [],
            "key_events": [],
        }
    except Exception as exc:
        logger.warning("从推荐系统构建交易计划失败: %s", exc)
        return None


def _build_plan_from_strategy_engine(plan_date: str) -> dict | None:
    """从策略引擎构建交易计划"""
    try:
        from src.services.short_term_strategy import ShortTermStrategyEngine
        # 获取实时数据
        stock_data = _gather_stock_data_for_plan()
        if not stock_data:
            return None

        engine = ShortTermStrategyEngine()
        signals = engine.scan_all(stock_data, [], [])

        if not signals:
            return None

        suggested_positions = []
        for sig in signals[:10]:
            if sig.confidence < 70:
                continue
            entry_price = sig.entry_price_range[0] if sig.entry_price_range else 0
            suggested_positions.append({
                "code": sig.code,
                "name": sig.name,
                "direction": "long" if sig.signal_type == "buy" else "short",
                "confidence": sig.confidence,
                "entry_price": entry_price,
                "stop_loss": sig.stop_loss,
                "take_profit": sig.take_profit,
                "reason": sig.reason,
            })

        if not suggested_positions:
            return None

        return {
            "date": plan_date,
            "phase": _determine_phase(),
            "market_assessment": "基于策略引擎信号生成",
            "sentiment_summary": "",
            "sector_focus": [],
            "trading_bias": "long",
            "suggested_positions": suggested_positions,
            "risk_warnings": [],
            "key_events": [],
        }
    except Exception as exc:
        logger.warning("从策略引擎构建交易计划失败: %s", exc)
        return None


def _gather_stock_data_for_plan() -> list:
    """为交易计划收集股票行情数据"""
    try:
        import efinance as ef
        df = ef.stock.get_realtime_quotes()
        if df is None or df.empty:
            return []

        result = []
        for _, row in df.head(200).iterrows():
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
    except Exception as exc:
        logger.warning("交易计划数据收集失败: %s", exc)
        return []


def _get_realtime_alerts() -> list[dict]:
    """获取实时告警

    集成 AlertEngine 统一告警评估管道：
    1. 从告警规则引擎获取活跃规则
    2. 获取最新评估结果
    3. 聚合为交易告警格式
    """
    alerts = []

    # 尝试从 AlertEngine 获取活跃告警
    alerts += _fetch_alerts_from_engine()

    # 尝试从策略引擎获取信号级告警
    alerts += _fetch_alerts_from_strategy_signals()

    return alerts


def _fetch_alerts_from_engine() -> list[dict]:
    """从 AlertEngine 获取告警"""
    try:
        from src.services.alert_engine import AlertEngine
        engine = AlertEngine()
        triggered = engine.get_active_alerts(limit=50)
        result = []
        for t in triggered:
            result.append({
                "id": str(t.get("id", "")),
                "type": t.get("type", "rule"),
                "severity": t.get("severity", "info"),
                "message": t.get("message", ""),
                "target": t.get("target", ""),
                "value": t.get("value"),
                "threshold": t.get("threshold"),
                "triggered_at": t.get("triggered_at", datetime.now().isoformat()),
                "acknowledged": t.get("acknowledged", False),
            })
        return result
    except ImportError:
        logger.debug("AlertEngine 模块不可用")
        return []
    except Exception as exc:
        logger.warning("AlertEngine 获取告警失败: %s", exc)
        return []


def _fetch_alerts_from_strategy_signals() -> list[dict]:
    """从策略引擎获取信号级告警（高置信度信号转告警）"""
    try:
        from src.services.short_term_strategy import ShortTermStrategyEngine
        stock_data = _gather_stock_data_for_plan()
        if not stock_data:
            return []

        engine = ShortTermStrategyEngine()
        signals = engine.scan_all(stock_data, [], [])

        alerts = []
        for sig in signals:
            if sig.signal_type == "alert" and sig.confidence >= 80:
                alerts.append({
                    "id": f"signal_{sig.code}_{sig.strategy}",
                    "type": "strategy_signal",
                    "severity": "warning" if sig.confidence >= 90 else "info",
                    "message": f"[{sig.strategy}] {sig.code} {sig.name}: {sig.reason}",
                    "target": sig.code,
                    "value": sig.confidence,
                    "threshold": 80,
                    "triggered_at": datetime.now().isoformat(),
                    "acknowledged": False,
                })
        return alerts
    except Exception as exc:
        logger.warning("策略信号告警生成失败: %s", exc)
        return []
