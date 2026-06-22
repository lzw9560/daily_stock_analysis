# -*- coding: utf-8 -*-
"""深度分析 API schemas — TradingAgents 多Agent投研分析."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RunAnalysisRequest(BaseModel):
    """启动深度分析请求."""

    ticker: str = Field(..., min_length=1, max_length=20, description="股票代码，如 000001、600519")
    trade_date: str = Field(..., min_length=8, max_length=10, description="分析日期，格式 YYYY-MM-DD")
    base_url: str = Field("", description="LLM 代理地址，留空使用系统默认配置")
    model: str = Field("", description="可选：深度分析显式使用的主模型；留空则继承系统当前主模型")


class PipelineStageSchema(BaseModel):
    """分析流水线阶段定义."""

    id: str
    name: str
    icon: str


class TaskStatsSchema(BaseModel):
    """分析任务统计信息."""

    llm_calls: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0


class TaskStatusResponse(BaseModel):
    """分析任务状态与结果."""

    task_id: str
    ticker: str
    trade_date: str
    status: str  # pending | running | completed | failed
    signal: str = ""
    current_stage: str = ""
    completed_stages: List[str] = Field(default_factory=list)
    stage_reports: Dict[str, str] = Field(default_factory=dict)
    stats: TaskStatsSchema = Field(default_factory=TaskStatsSchema)
    elapsed: float = 0
    error: str = ""
    report_path: str = ""
    report_download_url: str = ""


class TaskCreatedResponse(BaseModel):
    """任务创建成功响应."""

    task_id: str
    status: str = "pending"
