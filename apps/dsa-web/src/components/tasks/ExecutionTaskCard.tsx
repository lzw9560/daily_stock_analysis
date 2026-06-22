import type React from 'react';
import { Link } from 'react-router-dom';
import type { TaskInfo } from '../../types/analysis';
import type { MonteCarloSimulationResponse } from '../../types/backtest';
import { buildExecutionPanelHref, getLatestExecutionResult, useExecutionMemory } from '../../utils/executionMemory';
import { TaskDetailCardShell, TaskDetailDisclosure } from './TaskDetailCardShell';

interface ExecutionTaskCardProps {
  task: TaskInfo;
  compact?: boolean;
}

const DEFAULT_EXECUTION_PRESET = {
  side: 'buy' as const,
  spot: '100',
  quantity: '100',
  horizonDays: '10',
  paths: '10000',
  model: 'gbm' as const,
  drift: '0',
  vol: '0.2',
  winRate: '0.55',
  payoffRatio: '1.5',
  maxPositionPct: '30',
  dryRun: true,
};

function getExecutionSummaryText(task: TaskInfo, executionSummary: MonteCarloSimulationResponse | null): string {
  if (executionSummary) {
    return `最近一次模拟：VaR95 ${executionSummary.simulation.var95.toFixed(2)}% · 仓位 ${executionSummary.sizing.targetPositionPct.toFixed(2)}%`;
  }

  if (task.runtime?.mode) {
    return `任务运行态：${task.runtime.mode} · 通过 /execution 预填后查看仿真与 WAL 载荷`;
  }

  return '通过 /execution 预填后查看仿真与 WAL 载荷';
}

export const ExecutionTaskCard: React.FC<ExecutionTaskCardProps> = ({ task, compact = false }) => {
  const executionMemory = useExecutionMemory();
  const executionResult = getLatestExecutionResult(task.stockCode);
  const executionSummary = executionResult?.response ?? null;
  const executionParams = {
    ...DEFAULT_EXECUTION_PRESET,
    ...executionMemory.lastParams,
    symbol: task.stockCode || executionResult?.input.symbol || '',
    side: executionResult?.input.side || executionMemory.lastParams.side || 'buy',
    spot: executionResult?.input.spot || executionMemory.lastParams.spot || '100',
    quantity: executionResult?.input.quantity || executionMemory.lastParams.quantity || '100',
    horizonDays: executionResult?.input.horizonDays || executionMemory.lastParams.horizonDays || '10',
    paths: executionResult?.input.paths || executionMemory.lastParams.paths || '10000',
    model: executionResult?.input.model || executionMemory.lastParams.model || 'gbm',
    drift: executionResult?.input.drift || executionMemory.lastParams.drift || '0',
    vol: executionResult?.input.vol || executionMemory.lastParams.vol || '0.2',
    winRate: executionResult?.input.winRate || executionMemory.lastParams.winRate || '0.55',
    payoffRatio: executionResult?.input.payoffRatio || executionMemory.lastParams.payoffRatio || '1.5',
    maxPositionPct: executionResult?.input.maxPositionPct || executionMemory.lastParams.maxPositionPct || '30',
    dryRun: executionResult?.input.dryRun ?? executionMemory.lastParams.dryRun ?? true,
  };
  const executionHref = buildExecutionPanelHref(executionParams);

  return (
    <TaskDetailCardShell
      title="执行任务卡"
      subtitle={`${task.stockName || task.stockCode || '—'} · ${task.stockCode || '—'}`}
      badgeLabel={executionSummary ? '有缓存' : '待执行'}
      badgeVariant={executionSummary ? 'success' : 'warning'}
      compact={compact}
    >
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-border/70 bg-surface/70 p-3">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-text">推荐参数</div>
          <div className="mt-2 text-sm text-secondary-text">
            {executionParams.side === 'sell' ? '卖出' : '买入'} · {String(executionParams.model).toUpperCase()} · {executionParams.horizonDays} 天
          </div>
          <div className="mt-2 text-xs text-muted-text">
            默认价格 / 数量：{executionParams.spot} / {executionParams.quantity}
          </div>
        </div>
        <div className="rounded-xl border border-border/70 bg-surface/70 p-3">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-text">执行状态</div>
          <div className="mt-2 text-sm text-secondary-text">{getExecutionSummaryText(task, executionSummary)}</div>
        </div>
      </div>

      <TaskDetailDisclosure title="执行明细" value={executionParams.symbol || '—'}>
        <div className="grid gap-2 sm:grid-cols-2">
          <div>
            <div className="text-[11px] uppercase tracking-[0.16em] text-muted-text">预填链接</div>
            <Link
              to={executionHref}
              className="mt-1 inline-flex items-center gap-1 rounded-full border border-cyan/20 bg-cyan/10 px-2.5 py-1 text-[11px] font-medium text-cyan transition-colors hover:border-cyan/35 hover:bg-cyan/15"
              aria-label="打开预填执行面板"
            >
              打开执行面板
            </Link>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.16em] text-muted-text">最近结果</div>
            <div className="mt-1 text-secondary-text">
              {executionSummary ? `VaR95 ${executionSummary.simulation.var95.toFixed(2)}% · 仓位 ${executionSummary.sizing.targetPositionPct.toFixed(2)}%` : '暂无缓存结果'}
            </div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.16em] text-muted-text">执行开关</div>
            <div className="mt-1 text-secondary-text">{executionSummary ? (executionSummary.executionEnabled ? '执行开启' : '仅预览') : '未运行'}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.16em] text-muted-text">缓存来源</div>
            <div className="mt-1 text-secondary-text">{executionMemory.latestSymbol || '—'}</div>
          </div>
        </div>
      </TaskDetailDisclosure>
    </TaskDetailCardShell>
  );
};

export default ExecutionTaskCard;
