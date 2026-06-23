import type React from 'react';
import { RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Badge, Card, StatusDot } from '../common';
import { DashboardPanelHeader } from '../dashboard';
import FactorPipelineSummaryCard from '../factorPipeline/FactorPipelineSummaryCard';
import { TaskDetailDisclosure } from './TaskDetailCardShell';
import type { TaskInfo } from '../../types/analysis';

/**
 * 任务项组件属性
 */
interface TaskItemProps {
  task: TaskInfo;
}

/**
 * 单个任务项
 */
const TaskItem: React.FC<TaskItemProps> = ({ task }) => {
  const isPending = task.status === 'pending';
  const isProcessing = task.status === 'processing';
  const statusLabel = isProcessing ? '分析中' : '等待中';
  const statusVariant = isProcessing ? 'info' : 'default';
  const statusTone = isProcessing ? 'info' : 'neutral';
  const progress = Math.max(0, Math.min(100, task.progress || 0));
  const traceId = (task.traceId || '').trim();
  const factorPipeline = task.factorPipeline;
  const runtime = task.runtime;

  return (
    <div className="home-subpanel flex items-center gap-3 px-3 py-2.5">
      {/* 状态图标 */}
      <div className="shrink-0">
        {isProcessing ? (
          <StatusDot tone="info" pulse className="h-2.5 w-2.5" aria-label="任务进行中" />
        ) : isPending ? (
          <StatusDot tone="neutral" className="h-2.5 w-2.5" aria-label="任务等待中" />
        ) : null}
      </div>

      {/* 任务信息 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground truncate">
            {task.stockName || task.stockCode}
          </span>
          <span className="text-xs text-muted-text">
            {task.stockCode}
          </span>
        </div>
        {task.message && (
          <p className="text-xs text-secondary-text truncate mt-0.5">
            {task.message}
          </p>
        )}
        <div className="mt-2 flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/8">
            <div
              className="h-full rounded-full bg-cyan transition-[width] duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="shrink-0 text-[11px] text-muted-text tabular-nums">
            {progress}%
          </span>
        </div>
        {traceId ? (
          <TaskDetailDisclosure title="运行诊断" value={traceId.length > 18 ? `${traceId.slice(0, 10)}...` : traceId}>
            <span className="mr-1">Trace:</span>
            <code className="break-all font-mono text-[11px] text-secondary-text">
              {traceId}
            </code>
          </TaskDetailDisclosure>
        ) : null}
        {runtime ? (
          <TaskDetailDisclosure title="运行态" value={runtime.mode}>
            <div className="grid gap-2 sm:grid-cols-2">
              <div>
                <div className="text-[11px] uppercase tracking-[0.16em] text-muted-text">编排</div>
                <div className="mt-1 text-secondary-text">{runtime.arch} / {runtime.mode}</div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.16em] text-muted-text">模型</div>
                <div className="mt-1 break-all text-secondary-text">{runtime.provider || '—'} · {runtime.model || '—'}</div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.16em] text-muted-text">技能</div>
                <div className="mt-1 break-words text-secondary-text">{runtime.skills.length > 0 ? runtime.skills.join('、') : '—'}</div>
              </div>
              <div>
                <div className="text-[11px] uppercase tracking-[0.16em] text-muted-text">统计</div>
                <div className="mt-1 text-secondary-text">{runtime.totalSteps} steps · {runtime.toolCalls} tools · {runtime.totalTokens} tokens</div>
              </div>
            </div>
            {runtime.debate ? (
              <div className="mt-3 space-y-2">
                <div className="rounded-md bg-base/70 px-2 py-1.5 text-[11px] text-secondary-text">
                  辩论链路：{runtime.debate.stages.join(' → ')}
                </div>
                {runtime.debate.recentExperiences?.length ? (
                  <div className="space-y-1.5">
                    {runtime.debate.recentExperiences.map((item) => (
                      <div key={item.id} className="flex items-center justify-between gap-2 rounded-md bg-base/70 px-2 py-1 text-[11px] text-secondary-text">
                        <span>{item.stage} · #{item.queryId}</span>
                        <span className="font-mono">{item.score ?? '—'}</span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
          </TaskDetailDisclosure>
        ) : null}
        {factorPipeline ? (
          <div className="mt-2">
            <FactorPipelineSummaryCard
              title="因子流水线"
              subtitle={factorPipeline.latestRecordId ? `#${factorPipeline.latestRecordId}${factorPipeline.latestScreeningDate ? ` · ${factorPipeline.latestScreeningDate}` : ''}` : '任务附带的因子结果'}
              factorPipeline={factorPipeline}
              compact
            />
          </div>
        ) : null}
        <ExecutionTaskCard task={task} compact />
      </div>

      {/* 状态标签 */}
      <div className="flex-shrink-0">
        <Badge
          variant={statusVariant}
          className="min-w-[4.75rem] justify-center gap-1.5 shadow-none"
          aria-label={`任务状态：${statusLabel}`}
        >
          <StatusDot tone={statusTone} pulse={isProcessing} className="h-1.5 w-1.5" />
          {statusLabel}
        </Badge>
      </div>
    </div>
  );
};

/**
 * 任务面板属性
 */
interface TaskPanelProps {
  /** 任务列表 */
  tasks: TaskInfo[];
  /** 是否显示 */
  visible?: boolean;
  /** 标题 */
  title?: string;
  /** 自定义类名 */
  className?: string;
}

/**
 * 任务面板组件
 * 显示进行中的分析任务列表
 */
export const TaskPanel: React.FC<TaskPanelProps> = ({
  tasks,
  visible = true,
  title = '分析任务',
  className = '',
}) => {
  // 筛选活跃任务（pending 和 processing）
  const activeTasks = tasks.filter(
    (t) => t.status === 'pending' || t.status === 'processing'
  );

  // 无任务或不可见时不渲染
  if (!visible || activeTasks.length === 0) {
    return null;
  }

  const pendingCount = activeTasks.filter((t) => t.status === 'pending').length;
  const processingCount = activeTasks.filter((t) => t.status === 'processing').length;

  return (
    <Card
      variant="bordered"
      padding="none"
      className={`home-panel-card overflow-hidden ${className}`}
    >
      <div className="border-b border-subtle px-3 py-3">
        <DashboardPanelHeader
          className="mb-0"
          title={title}
          titleClassName="text-sm font-medium"
          leading={(
            <RefreshCw className="h-4 w-4 text-cyan" aria-hidden="true" />
          )}
          headingClassName="items-center"
          actions={(
            <div className="flex items-center gap-2 text-xs text-muted-text">
              <Link
                to="/execution"
                className="inline-flex items-center gap-1 rounded-full border border-cyan/20 bg-cyan/10 px-2.5 py-1 text-[11px] font-medium text-cyan transition-colors hover:border-cyan/35 hover:bg-cyan/15"
                aria-label="打开执行面板"
              >
                执行面板
              </Link>
              {processingCount > 0 && (
                <span className="flex items-center gap-1">
                  <StatusDot tone="info" pulse className="h-1.5 w-1.5" aria-label="进行中任务" />
                  {processingCount} 进行中
                </span>
              )}
              {pendingCount > 0 ? (
                <span className="flex items-center gap-1">
                  <StatusDot tone="neutral" className="h-1.5 w-1.5" aria-label="等待中任务" />
                  {pendingCount} 等待中
                </span>
              ) : null}
            </div>
          )}
        />
      </div>

      <div className="max-h-64 overflow-y-auto p-2">
        <div className="space-y-2">
          {activeTasks.map((task) => (
            <TaskItem key={task.taskId} task={task} />
          ))}
        </div>
      </div>
    </Card>
  );
};

export default TaskPanel;
