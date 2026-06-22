# -*- coding: utf-8 -*-
"""
深度分析 API 端点 — TradingAgents A股多Agent投研分析.

提供：
- POST   /api/v1/deep-analysis/run — 启动分析任务
- GET    /api/v1/deep-analysis/tasks/{task_id} — 查询任务进度/结果
- GET    /api/v1/deep-analysis/tasks — 列出所有任务
- DELETE /api/v1/deep-analysis/tasks/{task_id} — 删除任务
- GET    /api/v1/deep-analysis/stages — 获取流水线阶段定义
- GET    /api/v1/deep-analysis/tasks/{task_id}/report/download — 下载分析报告
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from api.v1.schemas.deep_analysis import (
    PipelineStageSchema,
    RunAnalysisRequest,
    TaskCreatedResponse,
    TaskStatsSchema,
    TaskStatusResponse,
)
from src.services.deep_analysis_service import DeepAnalysisService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["深度分析"])

# 报告存储目录
_REPORTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "reports"


# ── 路由 ────────────────────────────────────────────────────────────────────


@router.post("/run", response_model=TaskCreatedResponse)
async def start_analysis(req: RunAnalysisRequest) -> Dict[str, str]:
    """启动深度分析任务，返回 task_id."""
    try:
        service = DeepAnalysisService()
        result = service.start_analysis(
            ticker=req.ticker,
            trade_date=req.trade_date,
            base_url=req.base_url,
            model=req.model,
        )
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("启动深度分析任务失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """查询任务状态与结果."""
    service = DeepAnalysisService()
    task = service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    return _build_response(task)


@router.get("/tasks", response_model=List[TaskStatusResponse])
async def list_tasks() -> List[TaskStatusResponse]:
    """列出所有活跃任务."""
    service = DeepAnalysisService()
    tasks = service.list_tasks()
    return [_build_response(t) for t in tasks]


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str) -> Dict[str, str]:
    """删除指定深度分析任务."""
    service = DeepAnalysisService()
    deleted = service.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return {"message": "任务已删除", "task_id": task_id}


@router.get("/stages", response_model=List[PipelineStageSchema])
async def get_pipeline_stages() -> List[PipelineStageSchema]:
    """获取分析流水线的阶段定义."""
    service = DeepAnalysisService()
    stages = service.get_pipeline_stages()
    return [PipelineStageSchema(**s) for s in stages]


@router.get("/tasks/{task_id}/report")
async def get_report_content(task_id: str):
    """获取深度分析报告内容（用于页面展示）."""
    service = DeepAnalysisService()
    task = service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    report_path = task.get("report_path", "")
    if not report_path:
        raise HTTPException(status_code=404, detail="该任务尚未生成报告文件")

    filepath = _REPORTS_DIR / report_path
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="报告文件不存在，可能已被清理")

    content = filepath.read_text(encoding="utf-8")
    return {"content": content, "filename": report_path}


@router.get("/tasks/{task_id}/report/download", name="download_report")
async def download_report(task_id: str, request: Request):
    """下载深度分析报告文件."""
    service = DeepAnalysisService()
    task = service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    report_path = task.get("report_path", "")
    if not report_path:
        raise HTTPException(status_code=404, detail="该任务尚未生成报告文件")

    filepath = _REPORTS_DIR / report_path
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="报告文件不存在，可能已被清理")

    # 安全的文件名用于下载（RFC 5987 编码支持中文）
    safe_filename = f"深度分析报告_{task['ticker']}_{task['trade_date']}.md"
    from urllib.parse import quote
    encoded_filename = quote(safe_filename)
    return FileResponse(
        path=str(filepath),
        media_type="text/markdown; charset=utf-8",
        filename=safe_filename,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )


# ── 内部工具 ────────────────────────────────────────────────────────────────


def _build_response(task: Dict[str, Any]) -> TaskStatusResponse:
    """将仓库层字典转为 Pydantic 响应模型."""
    stats_data = task.get("stats", {})

    # 构建报告下载 URL（相对路径，避免 localhost/Docker 主机问题）
    report_download_url = ""
    report_path = task.get("report_path", "")
    if report_path:
        report_download_url = f"/api/v1/deep-analysis/tasks/{task['task_id']}/report/download"

    return TaskStatusResponse(
        task_id=task["task_id"],
        ticker=task["ticker"],
        trade_date=task["trade_date"],
        status=task["status"],
        signal=task.get("signal", ""),
        current_stage=task.get("current_stage", ""),
        completed_stages=task.get("completed_stages", []),
        stage_reports=task.get("stage_reports", {}),
        stats=TaskStatsSchema(
            llm_calls=stats_data.get("llm_calls", 0),
            tool_calls=stats_data.get("tool_calls", 0),
            tokens_in=stats_data.get("tokens_in", 0),
            tokens_out=stats_data.get("tokens_out", 0),
        ),
        elapsed=task.get("elapsed", 0),
        error=task.get("error", ""),
        report_path=report_path,
        report_download_url=report_download_url,
    )
