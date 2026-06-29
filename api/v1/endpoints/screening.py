# -*- coding: utf-8 -*-
"""Screening record query and manual trigger API endpoints."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.deps import get_config_dep
from src.config import Config
from api.v1.schemas.screening import (
    FactorPipelineRecordResponse,
    FactorPipelineTriggerRequest,
    FactorPipelineTriggerResponse,
    ScreeningRecordListResponse,
    ScreeningRunRequest,
    ScreeningRunResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# AlphaSift 策略中文名称映射表
STRATEGY_NAME_CN: Dict[str, str] = {
    "dual_low": "双低策略",
    "quality_value": "优质价值",
    "volume_breakout": "放量突破",
    "balanced_alpha": "均衡阿尔法",
    "capital_heat": "资金热度",
    "growth_at_reasonable_price": "合理价格成长",
    "momentum_breakout": "动量突破",
    "low_volatility_quality": "低波优质",
    "deep_value": "深度价值",
    "dividend_aristocrats": "红利贵族",
    "quality_compounders": "优质复利",
    "turnaround_opportunities": "困境反转",
}


def _get_strategy_name_cn(key: str) -> str:
    """获取策略中文名，无映射时返回原始 key。"""
    return STRATEGY_NAME_CN.get(key, key)


@router.get("/strategies")
def screening_strategies(config: Config = Depends(get_config_dep)) -> Dict[str, Any]:
    """获取已配置的选股策略列表及历史策略统计。"""
    from src.services.screening_service import ScreeningService
    service = ScreeningService()

    configured = service.get_configured_strategies()
    historical = service.get_available_strategies()

    # 附加中文名称映射
    name_map = {k: _get_strategy_name_cn(k) for k in set(configured + historical)}

    return {
        "configured": configured,
        "historical": historical,
        "name_map": name_map,
    }


@router.get("/dates")
def screening_dates() -> Dict[str, Any]:
    """获取有选股记录的日期列表。"""
    from src.services.screening_service import ScreeningService
    service = ScreeningService()
    dates = service.get_available_dates()
    return {"dates": dates, "count": len(dates)}


@router.get("/records", response_model=ScreeningRecordListResponse)
def screening_records(
    screening_date: Optional[str] = Query(default=None, description="筛选日期 ISO 格式 YYYY-MM-DD"),
    strategy: Optional[str] = Query(default=None, description="策略名称"),
    market: Optional[str] = Query(default=None, description="市场 cn/hk/us"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    config: Config = Depends(get_config_dep),
) -> Dict[str, Any]:
    """分页查询选股记录列表。"""
    from src.services.screening_service import ScreeningService
    service = ScreeningService()

    parsed_date = None
    if screening_date:
        try:
            parsed_date = date.fromisoformat(screening_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="日期格式无效，请使用 YYYY-MM-DD")

    return ScreeningRecordListResponse(**service.get_records(
        screening_date=parsed_date,
        strategy=strategy,
        market=market,
        limit=limit,
        offset=offset,
    ))


@router.get("/records/{record_id}")
def screening_record_detail(record_id: int) -> Dict[str, Any]:
    """获取单条选股记录的详细信息，包含候选股票和回测结果。"""
    from src.services.screening_service import ScreeningService
    service = ScreeningService()

    detail = service.get_record_detail(record_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"选股记录 {record_id} 不存在")

    return detail


@router.get("/records/{record_id}/backtest-results")
def screening_record_backtest_results(record_id: int) -> Dict[str, Any]:
    """获取与选股记录关联的回测结果。"""
    from src.repositories.screening_repo import ScreeningRepository
    repo = ScreeningRepository()

    record = repo.get_record_by_id(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"选股记录 {record_id} 不存在")

    results = repo.get_backtest_results_for_record(record_id)
    summary = repo.get_backtest_summary_for_record(record_id)

    return {
        "record_id": record_id,
        "screening_date": record.screening_date.isoformat() if record.screening_date else None,
        "strategy": record.strategy,
        "backtest_count": len(results),
        "results": results,
        "summary": summary,
    }


@router.get("/records/{record_id}/factor-pipeline", response_model=FactorPipelineRecordResponse)
def screening_record_factor_pipeline(record_id: int) -> FactorPipelineRecordResponse:
    """获取选股记录的因子流水线结果。"""
    from src.services.screening_service import ScreeningService
    service = ScreeningService()

    from src.services.factor_pipeline_service import FactorPipelineService
    factor_service = FactorPipelineService()

    try:
        factor_pipeline = factor_service.get_screening_record_factor_pipeline(record_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"选股记录 {record_id} 不存在")

    return FactorPipelineRecordResponse(record_id=record_id, factor_pipeline=factor_pipeline)


@router.post("/run", response_model=ScreeningRunResponse)
def screening_run(
    request: ScreeningRunRequest,
    config: Config = Depends(get_config_dep),
) -> Dict[str, Any]:
    """手动触发多策略选股及自动回测。

    可通过 request body 指定策略列表、市场和参数。
    如果未指定 strategies，将使用配置文件中的 SCREENING_STRATEGIES。
    notify_feishu=True 时，结束后将结果摘要发送到飞书。
    """
    if not config.alphasift_enabled:
        raise HTTPException(
            status_code=403,
            detail="ALPHASIFT_ENABLED=false，选股功能未启用。请先设置 ALPHASIFT_ENABLED=true。",
        )

    from src.services.screening_service import ScreeningService
    service = ScreeningService()

    try:
        result = service.run_daily_screening(
            strategies=request.strategies,
            market=request.market,
            max_results=request.max_results,
            auto_backtest=request.auto_backtest,
        )

        # 可选：发送飞书通知
        if request.notify_feishu:
            try:
                _send_screening_feishu_notification(result, config)
            except Exception as exc:
                logger.exception("飞书通知发送失败: %s", exc)

        return result
    except Exception as exc:
        logger.exception("手动触发选股失败")
        raise HTTPException(
            status_code=500,
            detail=f"选股执行失败: {exc}",
        )


def _send_screening_feishu_notification(result: Dict[str, Any], config: Config) -> None:
    """构建选股结果摘要并通过飞书 webhook 发送。"""
    from src.notification_sender.feishu_sender import FeishuSender

    sender = FeishuSender(config)

    strategies_result = result.get("strategies", [])
    lines = [
        "📊 **选股结果汇总**",
        "",
        f"📅 日期：{result.get('screening_date', '-')}",
        f"📈 策略总数：{result.get('total_strategies', 0)}",
        f"✅ 成功：{result.get('completed_strategies', 0)}  ·  ❌ 失败：{result.get('failed_strategies', 0)}",
        f"🎯 候选总数：{result.get('total_candidates', 0)}  ·  🔢 去重股票：{result.get('unique_codes', 0)}",
        "",
        "---",
        "",
    ]

    for sr in strategies_result:
        s_name = _get_strategy_name_cn(sr.get("strategy", ""))
        status_icon = "✅" if sr.get("status") == "completed" else "❌"
        candidate_count = sr.get("candidate_count", 0)
        error_msg = sr.get("error", "")
        logs_msg = sr.get("execution_logs", "")
        codes = sr.get("candidate_codes", [])[:5]

        lines.append(f"{status_icon} **{s_name}**（{sr.get('strategy')}）: {candidate_count} 只候选")
        if codes:
            lines.append(f"   股票：{', '.join(codes[:5])}")
        if error_msg:
            lines.append(f"   ⚠️ 错误：{error_msg}")
        if logs_msg:
            truncated = logs_msg[:500] + ("..." if len(logs_msg) > 500 else "")
            lines.append(f"   📋 日志：{truncated}")
        lines.append("")

    # 回测结果
    backtest = result.get("auto_backtest")
    if backtest:
        bt_status = "✅" if backtest.get("status") == "completed" else "❌"
        lines.append(f"{bt_status} 回测：{backtest.get('status', '-')}")
        if backtest.get("error"):
            lines.append(f"   ⚠️ {backtest['error']}")

    content = "\n".join(lines)
    sender.send_to_feishu(content)


@router.post("/factor-pipeline/run", response_model=FactorPipelineTriggerResponse)
def screening_factor_pipeline_run(
    request: FactorPipelineTriggerRequest,
    config: Config = Depends(get_config_dep),
) -> FactorPipelineTriggerResponse:
    """显式触发因子流水线骨架。

    该接口用于前端/任务面板对历史选股记录重跑因子摘要。
    """
    from src.services.factor_pipeline_service import FactorPipelineService

    if not getattr(config, "factor_pipeline_enabled", False):
        raise HTTPException(
            status_code=403,
            detail="FACTOR_PIPELINE_ENABLED=false，因子流水线未启用。请先设置 FACTOR_PIPELINE_ENABLED=true。",
        )

    service = FactorPipelineService()
    screening_date = None
    if request.screening_date:
        try:
            screening_date = date.fromisoformat(request.screening_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="日期格式无效，请使用 YYYY-MM-DD")

    try:
        result = service.run_for_screening_record(
            request.record_id,
            market=request.market,
            screening_date=screening_date,
        )
        return FactorPipelineTriggerResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("因子流水线触发失败")
        raise HTTPException(status_code=500, detail=f"因子流水线执行失败: {exc}")
