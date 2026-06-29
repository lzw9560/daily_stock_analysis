# -*- coding: utf-8 -*-
"""交易工作流引擎（交易系统升级 Phase 4）

建立"盘前-盘中-盘后"完整交易流状态机，串联现有各模块。

工作流阶段:
- PRE_MARKET (07:00-09:15): 情绪诊断 + 交易计划生成
- IN_TRADING (09:15-15:00): 实时信号触发 + 盯盘
- POST_MARKET (15:00-22:00): 复盘 + 统计更新
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 工作流阶段定义
# ============================================================

class WorkflowPhase(str, Enum):
    """工作流阶段"""
    IDLE = "idle"
    PRE_MARKET = "pre_market"       # 盘前 (07:00-09:15)
    BIDDING = "bidding"             # 竞价 (09:15-09:25)
    MORNING_SESSION = "morning"     # 早盘 (09:30-11:30)
    LUNCH_BREAK = "lunch"          # 午休 (11:30-13:00)
    AFTERNOON_SESSION = "afternoon" # 午盘 (13:00-15:00)
    CLOSING_AUCTION = "closing"    # 尾盘竞价 (15:00-15:05)
    POST_MARKET = "post_market"    # 盘后 (15:00-22:00)
    OFF_HOURS = "off_hours"        # 非交易时间

    @classmethod
    def from_time(cls, t: Optional[time] = None) -> "WorkflowPhase":
        """根据当前时间判断所处阶段"""
        t = t or datetime.now().time()
        if time(7, 0) <= t < time(9, 15):
            return cls.PRE_MARKET
        if time(9, 15) <= t < time(9, 25):
            return cls.BIDDING
        if time(9, 30) <= t < time(11, 30):
            return cls.MORNING_SESSION
        if time(11, 30) <= t < time(13, 0):
            return cls.LUNCH_BREAK
        if time(13, 0) <= t < time(15, 0):
            return cls.AFTERNOON_SESSION
        if time(15, 0) <= t < time(15,5):
            return cls.CLOSING_AUCTION
        if time(15, 0) <= t < time(22, 0):
            return cls.POST_MARKET
        return cls.OFF_HOURS


class WorkflowStatus(str, Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ============================================================
# 任务定义
# ============================================================

@dataclass
class WorkflowTask:
    """工作流任务"""
    name: str
    phase: WorkflowPhase
    description: str = ""
    enabled: bool = True
    timeout_seconds: int = 300
    retry_count: int = 1
    dependencies: list[str] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    result: dict = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class WorkflowResult:
    """工作流执行结果"""
    phase: WorkflowPhase
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_skipped: int = 0
    task_results: dict[str, dict] = field(default_factory=dict)
    summary: str = ""


# ============================================================
# 交易计划
# ============================================================

@dataclass
class TradingPlan:
    """每日交易计划"""
    date: str = ""
    sentiment_phase: str = "unknown"
    sentiment_score: int = 50
    suggested_total_position: int = 30  # 建议总仓位%
    focus_sectors: list[str] = field(default_factory=list)
    avoid_sectors: list[str] = field(default_factory=list)
    watchlist: list[str] = field(default_factory=list)
    strategy_preferences: list[str] = field(default_factory=list)  # 今日优先策略
    risk_rules: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ReviewResult:
    """复盘结果"""
    date: str = ""
    trades_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    best_trade: Optional[dict] = None
    worst_trade: Optional[dict] = None
    mistakes: list[str] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)
    tomorrow_plan: TradingPlan = field(default_factory=TradingPlan)
    lessons_learned: list[str] = field(default_factory=list)


# ============================================================
# 工作流引擎
# ============================================================

class WorkflowEngine:
    """交易工作流引擎

    管理盘前-盘中-盘后完整交易流，按阶段执行预定义任务。
    可集成现有 daily_tasks.py 和 scheduler.
    """

    def __init__(self):
        self._tasks: dict[WorkflowPhase, list[WorkflowTask]] = {
            phase: [] for phase in WorkflowPhase
        }
        self._handlers: dict[str, Callable] = {}
        self._results: dict[WorkflowPhase, WorkflowResult] = {}
        self._current_phase: WorkflowPhase = WorkflowPhase.IDLE
        self._trading_plan: Optional[TradingPlan] = None
        self._review_result: Optional[ReviewResult] = None

        self._register_default_tasks()

    # ========================
    #  默认任务注册
    # ========================

    def _register_default_tasks(self):
        """注册默认工作流任务"""
        # 盘前任务
        self.add_task(WorkflowTask(
            name="sentiment_diagnosis",
            phase=WorkflowPhase.PRE_MARKET,
            description="市场情绪诊断",
            timeout_seconds=60,
        ))
        self.add_task(WorkflowTask(
            name="overnight_news_scan",
            phase=WorkflowPhase.PRE_MARKET,
            description="隔夜消息扫描",
            timeout_seconds=120,
        ))
        self.add_task(WorkflowTask(
            name="bidding_anomaly_check",
            phase=WorkflowPhase.PRE_MARKET,
            description="竞价异动检查",
            timeout_seconds=30,
        ))
        self.add_task(WorkflowTask(
            name="trading_plan_generation",
            phase=WorkflowPhase.PRE_MARKET,
            description="今日交易计划生成",
            timeout_seconds=180,
            dependencies=["sentiment_diagnosis", "overnight_news_scan"],
        ))

        # 盘中任务
        self.add_task(WorkflowTask(
            name="strategy_scan",
            phase=WorkflowPhase.MORNING_SESSION,
            description="短线战法扫描",
            timeout_seconds=300,
        ))
        self.add_task(WorkflowTask(
            name="seal_plate_monitor",
            phase=WorkflowPhase.MORNING_SESSION,
            description="打板信号监控",
            timeout_seconds=600,
        ))
        self.add_task(WorkflowTask(
            name="stop_loss_check",
            phase=WorkflowPhase.MORNING_SESSION,
            description="止盈止损检查",
            timeout_seconds=30,
        ))
        self.add_task(WorkflowTask(
            name="sector_flow_monitor",
            phase=WorkflowPhase.MORNING_SESSION,
            description="板块资金流向监控",
            timeout_seconds=60,
        ))
        # 午盘复用相同任务
        self.add_task(WorkflowTask(
            name="strategy_scan_pm",
            phase=WorkflowPhase.AFTERNOON_SESSION,
            description="短线战法扫描(午盘)",
            timeout_seconds=300,
        ))
        self.add_task(WorkflowTask(
            name="snapshot_30min",
            phase=WorkflowPhase.MORNING_SESSION,
            description="30分钟快照",
            timeout_seconds=30,
        ))

        # 盘后任务
        self.add_task(WorkflowTask(
            name="trade_summary",
            phase=WorkflowPhase.POST_MARKET,
            description="今日交易总结",
            timeout_seconds=60,
        ))
        self.add_task(WorkflowTask(
            name="backtest_update",
            phase=WorkflowPhase.POST_MARKET,
            description="推荐信号回测更新",
            timeout_seconds=300,
        ))
        self.add_task(WorkflowTask(
            name="win_rate_update",
            phase=WorkflowPhase.POST_MARKET,
            description="胜率统计更新",
            timeout_seconds=60,
        ))
        self.add_task(WorkflowTask(
            name="tomorrow_prediction",
            phase=WorkflowPhase.POST_MARKET,
            description="LLM明日预判",
            timeout_seconds=300,
        ))
        self.add_task(WorkflowTask(
            name="hot_theme_identification",
            phase=WorkflowPhase.POST_MARKET,
            description="新题材/热点识别",
            timeout_seconds=60,
        ))

    # ========================
    #  任务管理
    # ========================

    def add_task(self, task: WorkflowTask):
        self._tasks[task.phase].append(task)

    def get_tasks(self, phase: WorkflowPhase) -> list[WorkflowTask]:
        return self._tasks.get(phase, [])

    def register_handler(self, task_name: str, handler: Callable):
        """注册任务处理器"""
        self._handlers[task_name] = handler

    # ========================
    #  阶段执行
    # ========================

    def execute_phase(
        self,
        phase: WorkflowPhase,
        *,
        context: Optional[dict] = None,
    ) -> WorkflowResult:
        """执行指定阶段的所有任务

        Args:
            phase: 工作流阶段
            context: 上下文数据（如市场数据、持仓数据等）

        Returns:
            WorkflowResult
        """
        self._current_phase = phase
        context = context or {}
        result = WorkflowResult(phase=phase)
        tasks = self.get_tasks(phase)

        # 按依赖排序
        sorted_tasks = self._topological_sort(tasks)

        completed: set[str] = set()
        for task in sorted_tasks:
            if not task.enabled:
                task.status = WorkflowStatus.SKIPPED
                result.tasks_skipped += 1
                continue

            # 检查依赖
            deps_met = all(d in completed for d in task.dependencies)
            if not deps_met:
                task.status = WorkflowStatus.SKIPPED
                task.error = f"依赖未满足: {set(task.dependencies) - completed}"
                result.tasks_skipped += 1
                continue

            # 执行任务
            task.status = WorkflowStatus.RUNNING
            try:
                handler = self._handlers.get(task.name)
                if handler:
                    task_result = handler(context)
                    task.result = task_result or {}
                else:
                    # 无handler的任务标记为完成（调用者后续处理）
                    task.result = {"status": "no_handler", "note": "等待外部处理"}
                task.status = WorkflowStatus.COMPLETED
                result.tasks_completed += 1
                completed.add(task.name)
            except Exception as e:
                logger.exception(f"任务 {task.name} 执行失败: {e}")
                task.status = WorkflowStatus.FAILED
                task.error = str(e)
                result.tasks_failed += 1

            result.task_results[task.name] = {
                "status": task.status.value,
                "result": task.result,
                "error": task.error,
            }

        result.finished_at = datetime.now()
        self._results[phase] = result

        # 生成阶段总结
        result.summary = self._generate_phase_summary(phase, result)
        return result

    def execute_full_cycle(
        self,
        *,
        context: Optional[dict] = None,
        skip_off_hours: bool = True,
    ) -> dict[WorkflowPhase, WorkflowResult]:
        """执行完整交易周期（所有阶段）

        Returns:
            {phase: WorkflowResult}
        """
        context = context or {}
        results: dict[WorkflowPhase, WorkflowResult] = {}

        phases_in_order = [
            WorkflowPhase.PRE_MARKET,
            WorkflowPhase.BIDDING,
            WorkflowPhase.MORNING_SESSION,
            WorkflowPhase.LUNCH_BREAK,
            WorkflowPhase.AFTERNOON_SESSION,
            WorkflowPhase.CLOSING_AUCTION,
            WorkflowPhase.POST_MARKET,
        ]

        for phase in phases_in_order:
            logger.info(f"执行阶段: {phase.value}")
            result = self.execute_phase(phase, context=context)
            results[phase] = result

            # 将当前阶段结果传递到下一阶段
            self._enrich_context(context, phase, result)

        return results

    # ========================
    #  交易计划
    # ========================

    def generate_trading_plan(
        self,
        sentiment_data: dict,
        news_data: Optional[dict] = None,
        watchlist: Optional[list[str]] = None,
    ) -> TradingPlan:
        """生成交易计划

        Args:
            sentiment_data: 情绪诊断数据
            news_data: 盘前资讯
            watchlist: 自选股列表
        """
        phase = sentiment_data.get("phase", "unknown")
        score = sentiment_data.get("score", 50)
        position = sentiment_data.get("position_suggestion", {})
        hot_sectors = sentiment_data.get("hot_sectors", [])
        signals = sentiment_data.get("key_signals", [])

        # 仓位建议
        suggested_pos = position.get("suggested_position", 30)
        pos_range = position.get("position_range", "20-40%")

        # 聚焦板块
        focus = news_data.get("focus_sectors", []) if news_data else []
        avoid = news_data.get("avoid_sectors", []) if news_data else []

        # 策略偏好
        strategy_map = {
            "冰点期": ["首板挖掘"],
            "修复期": ["首板挖掘", "低吸龙头"],
            "分化期": ["首板挖掘", "连板接力", "低吸龙头", "N字反击"],
            "高潮期": ["连板接力", "N字反击"],
            "退潮期": [],
        }
        strategies = strategy_map.get(phase, ["首板挖掘"])

        # 风控规则
        risk_rules = [
            f"总仓位: {pos_range}",
            f"单票最大仓位: {min(30, suggested_pos)}%",
            "单日最大亏损: 总资金3%",
            "连续2笔亏损→停止交易",
        ]

        plan = TradingPlan(
            date=datetime.now().strftime("%Y%m%d"),
            sentiment_phase=phase,
            sentiment_score=score,
            suggested_total_position=suggested_pos,
            focus_sectors=hot_sectors[:5] or focus[:5],
            avoid_sectors=avoid[:3],
            watchlist=watchlist or [],
            strategy_preferences=strategies,
            risk_rules=risk_rules,
            action_items=self._build_action_items(phase, strategies, suggested_pos),
        )

        self._trading_plan = plan
        return plan

    def _build_action_items(
        self, phase: str, strategies: list[str], position: int
    ) -> list[str]:
        """构建行动清单"""
        actions = {
            "冰点期": [
                "仓位降至最低(≤10%)",
                "仅试错首板",
                "关注逆势抗跌标的",
                "不追高，不接力",
            ],
            "修复期": [
                f"仓位控制在{position}%内",
                "优先低位首板",
                "关注率先修复的板块",
                "严格止损，不贪",
            ],
            "分化期": [
                f"仓位{position}%，去弱留强",
                "聚焦主线龙头",
                "板块轮动高抛低吸",
                "单票仓位控制在20%内",
            ],
            "高潮期": [
                "逐步减仓，兑现利润",
                "新开仓比例减半",
                "不追加速板",
                "设置移动止盈",
            ],
            "退潮期": [
                "果断减仓至≤15%",
                "不参与任何接力",
                "不补仓亏损股",
                "耐心等待冰点信号",
            ],
        }
        return actions.get(phase, ["观望为主", "等待明确信号"])

    # ========================
    #  辅助方法
    # ========================

    def _topological_sort(self, tasks: list[WorkflowTask]) -> list[WorkflowTask]:
        """按依赖关系拓扑排序"""
        name_to_task = {t.name: t for t in tasks}
        sorted_tasks: list[WorkflowTask] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(name: str):
            if name in visited:
                return
            if name in visiting:
                return  # 循环依赖，跳过
            visiting.add(name)
            task = name_to_task.get(name)
            if task:
                for dep in task.dependencies:
                    if dep in name_to_task:
                        visit(dep)
            visited.add(name)
            if task:
                sorted_tasks.append(task)

        for task in tasks:
            visit(task.name)

        return sorted_tasks

    def _enrich_context(
        self, context: dict, phase: WorkflowPhase, result: WorkflowResult
    ):
        """将阶段结果注入上下文"""
        key = f"phase_{phase.value}"
        context[key] = {
            "completed": result.tasks_completed,
            "failed": result.tasks_failed,
            "results": result.task_results,
        }

    def _generate_phase_summary(
        self, phase: WorkflowPhase, result: WorkflowResult
    ) -> str:
        """生成阶段执行总结"""
        total = result.tasks_completed + result.tasks_failed + result.tasks_skipped
        parts = [
            f"[{phase.value}] 完成{result.tasks_completed}/{total}个任务"
        ]
        if result.tasks_failed > 0:
            failed_names = [
                name for name, r in result.task_results.items()
                if r.get("status") == "failed"
            ]
            parts.append(f"失败: {', '.join(failed_names)}")
        if result.tasks_skipped > 0:
            parts.append(f"跳过{result.tasks_skipped}个")
        return " | ".join(parts)

    @property
    def trading_plan(self) -> Optional[TradingPlan]:
        return self._trading_plan

    @property
    def current_phase(self) -> WorkflowPhase:
        return self._current_phase

    @property
    def review_result(self) -> Optional[ReviewResult]:
        return self._review_result

    def get_status(self) -> dict:
        """获取工作流整体状态"""
        return {
            "current_phase": self._current_phase.value,
            "trading_plan": self._trading_plan,
            "review_result": self._review_result,
            "phase_results": {
                phase.value: {
                    "tasks_completed": r.tasks_completed,
                    "tasks_failed": r.tasks_failed,
                    "summary": r.summary,
                }
                for phase, r in self._results.items()
            },
        }
