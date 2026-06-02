# -*- coding: utf-8 -*-
"""
持仓监控 API 端点

提供：
- 监控服务启停控制
- 监控标的管理
- 策略配置
- 实时状态查询
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.position_monitor.monitor_engine import (
    PositionMonitorEngine,
    get_monitor_engine,
    reset_monitor_engine,
)
from src.position_monitor.strategies import get_default_strategies

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/position-monitor", tags=["PositionMonitor"])


# ============================================================
#  请求/响应模型
# ============================================================

class MonitorStatusResponse(BaseModel):
    """监控状态响应"""
    status: str
    is_trading_time: bool
    watchlist_count: int
    watchlist: list = Field(default_factory=list)
    strategies_count: int
    strategies: list = Field(default_factory=list)
    poll_interval: float
    circuit_breaker: dict = Field(default_factory=dict)
    rounds: int = 0
    signals_triggered: int = 0
    errors: int = 0
    last_poll_time: Optional[str] = None
    start_time: Optional[str] = None


class AddStockRequest(BaseModel):
    """添加监控标的"""
    code: str = Field(description="股票代码")
    name: str = Field("", description="股票名称")


class BatchAddStocksRequest(BaseModel):
    """批量添加监控标的"""
    codes: List[str] = Field(description="股票代码列表")


class StrategyConfigRequest(BaseModel):
    """策略配置"""
    strategy_type: str
    signal_type: str = "alert"
    enabled: bool = True
    params: dict = Field(default_factory=dict)
    cooldown_seconds: int = 300


class MonitorConfigRequest(BaseModel):
    """监控配置"""
    poll_interval: float = Field(3.0, ge=1.0, le=60.0, description="轮询间隔(秒)")
    strategies: Optional[List[StrategyConfigRequest]] = None
    watchlist_codes: Optional[List[str]] = None


class SimpleResponse(BaseModel):
    """通用响应"""
    success: bool
    message: str = ""


# ============================================================
#  状态查询
# ============================================================

@router.get("/status", response_model=MonitorStatusResponse, summary="获取监控状态")
async def get_monitor_status():
    """获取当前监控引擎的完整状态"""
    engine = get_monitor_engine()
    return MonitorStatusResponse(**engine.get_status())


# ============================================================
#  启停控制
# ============================================================

@router.post("/start", response_model=SimpleResponse, summary="启动监控")
async def start_monitor():
    """启动盘中监控服务"""
    engine = get_monitor_engine()
    try:
        engine.start()
        return SimpleResponse(success=True, message="监控已启动")
    except Exception as e:
        logger.error("启动监控失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pause", response_model=SimpleResponse, summary="暂停监控")
async def pause_monitor():
    """暂停监控（保留状态）"""
    engine = get_monitor_engine()
    engine.pause()
    return SimpleResponse(success=True, message="监控已暂停")


@router.post("/resume", response_model=SimpleResponse, summary="恢复监控")
async def resume_monitor():
    """恢复暂停的监控"""
    engine = get_monitor_engine()
    engine.resume()
    return SimpleResponse(success=True, message="监控已恢复")


@router.post("/stop", response_model=SimpleResponse, summary="停止监控")
async def stop_monitor():
    """完全停止监控服务"""
    engine = get_monitor_engine()
    try:
        engine.stop()
        return SimpleResponse(success=True, message="监控已停止")
    except Exception as e:
        logger.error("停止监控失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restart", response_model=SimpleResponse, summary="重启监控")
async def restart_monitor(config: Optional[MonitorConfigRequest] = None):
    """重启监控（应用新配置）"""
    try:
        reset_monitor_engine()

        if config:
            engine = PositionMonitorEngine(
                poll_interval=config.poll_interval,
                strategies=[s.model_dump() for s in config.strategies] if config.strategies else None,
            )
            if config.watchlist_codes:
                engine.set_watchlist({c: "" for c in config.watchlist_codes})
            # 替换全局实例
            import src.position_monitor.monitor_engine as me
            me._engine_instance = engine
        else:
            engine = get_monitor_engine()

        engine.start()
        return SimpleResponse(success=True, message="监控已重启")
    except Exception as e:
        logger.error("重启监控失败: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
#  标的管理
# ============================================================

@router.post("/stocks", response_model=SimpleResponse, summary="添加监控标的")
async def add_stock(request: AddStockRequest):
    """添加单个监控标的"""
    engine = get_monitor_engine()
    engine.add_stock(request.code, request.name)
    return SimpleResponse(success=True, message=f"已添加 {request.code}")


@router.post("/stocks/batch", response_model=SimpleResponse, summary="批量添加标的")
async def batch_add_stocks(request: BatchAddStocksRequest):
    """批量添加监控标的"""
    engine = get_monitor_engine()
    for code in request.codes:
        engine.add_stock(code.strip())
    return SimpleResponse(success=True, message=f"已批量添加 {len(request.codes)} 只标的")


@router.delete("/stocks/{code}", response_model=SimpleResponse, summary="移除监控标的")
async def remove_stock(code: str):
    """从监控列表中移除标的"""
    engine = get_monitor_engine()
    engine.remove_stock(code)
    return SimpleResponse(success=True, message=f"已移除 {code}")


@router.post("/stocks/sync-watchlist", response_model=SimpleResponse, summary="同步自选股")
async def sync_watchlist():
    """从 watchlist.json 同步自选股到监控列表"""
    engine = get_monitor_engine()
    engine._load_watchlist_from_file()
    return SimpleResponse(
        success=True,
        message=f"已同步自选股，当前监控 {len(engine._watchlist)} 只标的",
    )


# ============================================================
#  策略配置
# ============================================================

@router.get("/strategies/default", summary="获取默认策略")
async def get_default_strategies_config():
    """获取系统默认策略配置"""
    return {"strategies": get_default_strategies()}


# ============================================================
#  交易时段
# ============================================================

@router.get("/trading-time", summary="检查交易时段")
async def check_trading_time():
    """检查当前是否在交易时段"""
    from src.position_monitor.monitor_engine import PositionMonitorEngine
    is_trading = PositionMonitorEngine.is_trading_time()
    return {
        "is_trading_time": is_trading,
        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sessions": [
            {"start": "09:15", "end": "11:30"},
            {"start": "13:00", "end": "15:00"},
        ],
    }


# ============================================================
#  心跳测试
# ============================================================

@router.post("/heartbeat", response_model=SimpleResponse, summary="飞书心跳测试")
async def send_heartbeat():
    """发送一条飞书心跳消息，验证 Webhook 连接"""
    engine = get_monitor_engine()
    try:
        ok = engine._sender.send_heartbeat()
        if ok:
            return SimpleResponse(success=True, message="飞书心跳发送成功")
        else:
            return SimpleResponse(success=False, message="飞书心跳发送失败，请检查 Webhook 配置")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
