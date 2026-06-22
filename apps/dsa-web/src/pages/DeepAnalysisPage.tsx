import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Brain, Play, RefreshCw, Clock, CheckCircle2,
  Loader2, TrendingUp, TrendingDown, BarChart3, Zap, Activity,
  XCircle, Download, FileText, ListTree, ExternalLink,
  Trash2, AlertTriangle,
} from 'lucide-react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Button } from '@/components/common/Button';
import { Card } from '@/components/common/Card';
import { Input } from '@/components/common/Input';
import { Badge } from '@/components/common/Badge';
import { EmptyState } from '@/components/common/EmptyState';
import { PageHeader } from '@/components/common/PageHeader';

import { deepAnalysisApi } from '@/api/deepAnalysis';
import type { PipelineStage, TaskStatus } from '@/api/deepAnalysis';
import { DeepAnalysisModelSelector, type DeepAnalysisModelSelection } from '@/components/deepAnalysis/DeepAnalysisModelSelector';

// ── 信号解析 ────────────────────────────────────────────────────────────────

function parseSignal(signal: string): { direction: 'bullish' | 'bearish' | 'neutral'; label: string } {
  const s = signal.toLowerCase();
  if (s.includes('bullish') || s.includes('buy') || s.includes('做多') || s.includes('看多')) {
    return { direction: 'bullish', label: '看多' };
  }
  if (s.includes('bearish') || s.includes('sell') || s.includes('做空') || s.includes('看空')) {
    return { direction: 'bearish', label: '看空' };
  }
  return { direction: 'neutral', label: '观望' };
}

// ── Markdown 渲染（简易） ─────────────────────────────────────────────────────

function SimpleMarkdown({ content }: { content: string }) {
  if (!content) return null;
  // 去掉 <think> 标签
  const text = content.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
  // 基本 Markdown 渲染
  const html = text
    .replace(/### (.+)/g, '<h4 class="text-sm font-semibold text-foreground mt-3 mb-1">$1</h4>')
    .replace(/## (.+)/g, '<h3 class="text-base font-bold text-foreground mt-4 mb-2">$1</h3>')
    .replace(/# (.+)/g, '<h2 class="text-lg font-bold text-foreground mt-4 mb-2">$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-[hsl(var(--primary))]">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded bg-muted text-xs">$1</code>')
    .replace(/^- (.+)/gm, '<li class="ml-4 list-disc text-sm text-secondary-text">$1</li>')
    .replace(/\n/g, '<br/>');

  return <div className="prose-sm max-w-none text-secondary-text" dangerouslySetInnerHTML={{ __html: html }} />;
}

// ── 流水线进度条 ─────────────────────────────────────────────────────────────

function ProgressBar({
  stages,
  completedStages,
  currentStage,
  status,
}: {
  stages: PipelineStage[];
  completedStages: string[];
  currentStage: string;
  status: string;
}) {
  if (status === 'pending') {
    return (
      <div className="flex items-center gap-2 text-secondary-text">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        <span className="text-sm">任务排队中...</span>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
      {stages.map((stage) => {
        const isDone = completedStages.includes(stage.id);
        const isActive = currentStage === stage.id && !isDone;

        return (
          <div
            key={stage.id}
            className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-all ${
              isDone
                ? 'border-[hsl(var(--primary))/0.3] bg-[hsl(var(--primary))/0.08] text-[hsl(var(--primary))]'
                : isActive
                  ? 'border-[hsl(var(--primary))/0.4] bg-[hsl(var(--primary))/0.1] text-[hsl(var(--primary))] animate-pulse'
                  : 'border-border/40 bg-card/40 text-muted-foreground'
            }`}
          >
            <span className="text-base">{stage.icon}</span>
            <span className="truncate">{stage.name}</span>
            {isDone && <CheckCircle2 className="ml-auto h-3 w-3 shrink-0" />}
            {isActive && <Loader2 className="ml-auto h-3 w-3 shrink-0 animate-spin" />}
          </div>
        );
      })}
    </div>
  );
}

// ── 分析报告面板 ─────────────────────────────────────────────────────────────

function ReportPanel({
  stages,
  stageReports,
  signal,
  stats,
  elapsed,
  reportDownloadUrl,
  taskId,
}: {
  stages: PipelineStage[];
  stageReports: Record<string, string>;
  signal: string;
  stats: { llm_calls: number; tool_calls: number; tokens_in: number; tokens_out: number };
  elapsed: number;
  reportDownloadUrl: string;
  taskId: string;
}) {
  const [expandedStage, setExpandedStage] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'stages' | 'full'>('stages');
  const [fullReport, setFullReport] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const sig = parseSignal(signal);

  // 切换到完整报告视图时，自动加载报告内容
  const handleSwitchToFull = useCallback(async () => {
    setViewMode('full');
    if (fullReport !== null) return; // 已加载过

    setReportLoading(true);
    setReportError(null);
    try {
      const data = await deepAnalysisApi.getReportContent(taskId);
      setFullReport(data.content);
    } catch (err) {
      setReportError(err instanceof Error ? err.message : '加载报告失败');
    } finally {
      setReportLoading(false);
    }
  }, [taskId, fullReport]);

  return (
    <div className="space-y-4">
      {/* 决策信号 + 操作按钮 */}
      <Card className="ring-1 ring-[hsl(var(--primary))]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {sig.direction === 'bullish' ? (
              <TrendingUp className="h-6 w-6 text-emerald-500" />
            ) : sig.direction === 'bearish' ? (
              <TrendingDown className="h-6 w-6 text-red-500" />
            ) : (
              <Activity className="h-6 w-6 text-amber-500" />
            )}
            <div>
              <p className="text-sm font-semibold text-foreground">最终决策</p>
              <p className="text-xs text-secondary-text">{signal}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge
              variant={sig.direction === 'bullish' ? 'success' : sig.direction === 'bearish' ? 'danger' : 'default'}
            >
              {sig.label}
            </Badge>
            {reportDownloadUrl && (
              <a href={reportDownloadUrl} download>
                <Button variant="outline" size="sm">
                  <Download className="h-3.5 w-3.5 mr-1.5" />
                  下载报告
                </Button>
              </a>
            )}
          </div>
        </div>
      </Card>

      {/* 统计信息 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="text-center py-2">
          <p className="text-xs text-muted-foreground">LLM 调用</p>
          <p className="text-lg font-bold text-foreground">{stats.llm_calls}</p>
        </Card>
        <Card className="text-center py-2">
          <p className="text-xs text-muted-foreground">工具调用</p>
          <p className="text-lg font-bold text-foreground">{stats.tool_calls}</p>
        </Card>
        <Card className="text-center py-2">
          <p className="text-xs text-muted-foreground">Token 输入</p>
          <p className="text-lg font-bold text-foreground">{Math.round(stats.tokens_in / 1000)}k</p>
        </Card>
        <Card className="text-center py-2">
          <p className="text-xs text-muted-foreground">耗时</p>
          <p className="text-lg font-bold text-foreground">{elapsed.toFixed(0)}s</p>
        </Card>
      </div>

      {/* 视图切换标签 */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center rounded-lg border border-border/60 p-0.5 bg-muted/30">
            <button
              type="button"
              onClick={() => setViewMode('stages')}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                viewMode === 'stages'
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-secondary-text'
              }`}
            >
              <ListTree className="h-3.5 w-3.5" />
              分段详情
            </button>
            <button
              type="button"
              onClick={handleSwitchToFull}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                viewMode === 'full'
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-secondary-text'
              }`}
            >
              <FileText className="h-3.5 w-3.5" />
              完整报告
            </button>
          </div>
        </div>

        {/* 分段详情视图 */}
        {viewMode === 'stages' && (
          <div className="space-y-1.5">
            {stages.map((stage) => {
              const report = stageReports[stage.id];
              const hasReport = !!report;
              const isExpanded = expandedStage === stage.id;

              if (!hasReport && stage.id !== 'pm') return null;

              return (
                <div key={stage.id} className="rounded-lg border border-border/60">
                  <button
                    type="button"
                    onClick={() => setExpandedStage(isExpanded ? null : stage.id)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-hover/50 transition-colors"
                  >
                    <span>{stage.icon}</span>
                    <span className="flex-1 font-medium text-foreground">{stage.name}</span>
                    {hasReport ? (
                      <Badge variant="success" size="sm">已完成</Badge>
                    ) : (
                      <Badge variant="default" size="sm">待完成</Badge>
                    )}
                    <ChevronIcon expanded={isExpanded} />
                  </button>
                  {isExpanded && hasReport && (
                    <div className="px-3 pb-3 border-t border-border/40 pt-2 max-h-64 overflow-y-auto">
                      <SimpleMarkdown content={report} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* 完整报告视图 */}
        {viewMode === 'full' && (
          <Card className="p-4">
            {reportLoading ? (
              <div className="flex flex-col items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-[hsl(var(--primary))] mb-3" />
                <p className="text-sm text-muted-foreground">加载报告内容...</p>
              </div>
            ) : reportError ? (
              <div className="flex flex-col items-center justify-center py-12">
                <XCircle className="h-8 w-8 text-red-500 mb-3" />
                <p className="text-sm text-red-400 mb-3">{reportError}</p>
                <Button variant="outline" size="sm" onClick={handleSwitchToFull}>重新加载</Button>
              </div>
            ) : fullReport ? (
              <div
                className="prose prose-sm prose-invert max-w-none
                  prose-headings:text-foreground prose-headings:font-semibold
                  prose-h1:text-xl prose-h1:mt-6 prose-h1:mb-4
                  prose-h2:text-lg prose-h2:mt-5 prose-h2:mb-3 prose-h2:pb-2 prose-h2:border-b prose-h2:border-border/40
                  prose-h3:text-base prose-h3:mt-4 prose-h3:mb-2
                  prose-p:leading-relaxed prose-p:mb-3 prose-p:text-secondary-text
                  prose-strong:text-foreground prose-strong:font-semibold
                  prose-ul:my-2 prose-ol:my-2 prose-li:my-1 prose-li:text-secondary-text
                  prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:bg-muted prose-code:text-xs prose-code:before:content-none prose-code:after:content-none
                  prose-pre:bg-muted prose-pre:border prose-pre:border-border/40
                  prose-table:border-collapse prose-th:border prose-th:border-border/40 prose-th:px-3 prose-th:py-2 prose-td:border prose-td:border-border/40 prose-td:px-3 prose-td:py-2
                  prose-hr:border-border/40 prose-hr:my-6
                  prose-a:text-[hsl(var(--primary))] prose-a:no-underline hover:prose-a:underline
                  prose-blockquote:border-l-[hsl(var(--primary))] prose-blockquote:bg-[hsl(var(--primary))/0.04] prose-blockquote:py-1 prose-blockquote:px-4 prose-blockquote:rounded-r-lg
                  prose-blockquote:text-secondary-text
                  whitespace-pre-line break-words
                "
              >
                <Markdown remarkPlugins={[remarkGfm]}>{fullReport}</Markdown>
              </div>
            ) : null}
          </Card>
        )}
      </div>
    </div>
  );
}

function ChevronIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg
      className={`h-4 w-4 text-muted-foreground transition-transform ${expanded ? 'rotate-180' : ''}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  );
}

// ── 主页面 ───────────────────────────────────────────────────────────────────

export default function DeepAnalysisPage() {
  const [ticker, setTicker] = useState('');
  const [tradeDate, setTradeDate] = useState(() => {
    // 默认今天
    const d = new Date();
    return d.toISOString().slice(0, 10);
  });
  const [baseUrl, setBaseUrl] = useState('');
  const [modelSelection, setModelSelection] = useState<DeepAnalysisModelSelection>({ mode: 'inherit', model: '' });
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [tasks, setTasks] = useState<TaskStatus[]>([]);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);  // 启动失败的错误信息
  const [deletingTaskId, setDeletingTaskId] = useState<string | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reportAreaRef = useRef<HTMLDivElement>(null);

  // 加载阶段定义和任务列表
  useEffect(() => {
    deepAnalysisApi.getPipelineStages().then(setStages).catch(console.error);
    refreshTasks();
  }, []);

  const refreshTasks = useCallback(async () => {
    try {
      const data = await deepAnalysisApi.listTasks();
      setTasks(data);
    } catch {
      // ignore
    }
  }, []);

  // ── 轮询配置常量 ──────────────────────────────────────────────────────────
  const POLL_INITIAL_INTERVAL = 2_000;   // 初始间隔 2s
  const POLL_MAX_INTERVAL = 30_000;       // 最大间隔 30s
  const POLL_BACKOFF_FACTOR = 1.5;        // 退避因子
  const POLL_MAX_ATTEMPTS = 120;           // 最大轮询次数 (~8min 考虑退避)
  const POLL_STALE_TIMEOUT = 10 * 60_000;  // 停滞超时 10min（无新阶段完成）

  // 使用 ref 管理轮询状态，避免闭包陷阱
  const pollStateRef = useRef({
    attempts: 0,
    lastCompletedLen: 0,
    lastProgressTime: 0,
    currentInterval: POLL_INITIAL_INTERVAL,
  });

  // 轮询活跃任务
  const startPolling = useCallback((taskId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);

    setActiveTaskId(taskId);
    pollStateRef.current = {
      attempts: 0,
      lastCompletedLen: 0,
      lastProgressTime: Date.now(),
      currentInterval: POLL_INITIAL_INTERVAL,
    };

    const doPoll = async () => {
      const state = pollStateRef.current;
      try {
        const status = await deepAnalysisApi.getTaskStatus(taskId);
        setTasks(prev => prev.map(t => t.task_id === taskId ? status : t));

        // 完成或失败 → 停止
        if (status.status === 'completed' || status.status === 'failed') {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          return;
        }

        // 检查进度：有新的阶段完成？
        const currentLen = (status.completed_stages || []).length;
        if (currentLen > state.lastCompletedLen) {
          // 有进展 → 重置间隔和计数
          state.lastCompletedLen = currentLen;
          state.lastProgressTime = Date.now();
          state.currentInterval = POLL_INITIAL_INTERVAL;
          state.attempts = 0;
        } else {
          state.attempts += 1;
        }

        // 停滞超时检查
        if (Date.now() - state.lastProgressTime > POLL_STALE_TIMEOUT) {
          console.warn(`[DeepAnalysis] 任务 ${taskId} 超过 ${POLL_STALE_TIMEOUT / 60_000}min 无进展，停止轮询`);
          clearInterval(pollRef.current!);
          pollRef.current = null;
          return;
        }

        // 超过最大尝试次数（考虑退避）
        if (state.attempts > POLL_MAX_ATTEMPTS) {
          console.warn(`[DeepAnalysis] 任务 ${taskId} 超过最大轮询次数 ${POLL_MAX_ATTEMPTS}，停止轮询`);
          clearInterval(pollRef.current!);
          pollRef.current = null;
          return;
        }

        // 指数退避：每次无进展时增加间隔
        if (state.attempts > 1) {
          state.currentInterval = Math.min(
            POLL_INITIAL_INTERVAL * Math.pow(POLL_BACKOFF_FACTOR, state.attempts - 1),
            POLL_MAX_INTERVAL,
          );
        }

        // 调整定时器间隔
        clearInterval(pollRef.current!);
        pollRef.current = setInterval(doPoll, state.currentInterval);
      } catch {
        // 网络错误 → 指数退避后重试
        state.attempts += 1;
        state.currentInterval = Math.min(
          POLL_INITIAL_INTERVAL * Math.pow(POLL_BACKOFF_FACTOR, state.attempts),
          POLL_MAX_INTERVAL,
        );
        if (state.attempts > POLL_MAX_ATTEMPTS) {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          return;
        }
        clearInterval(pollRef.current!);
        pollRef.current = setInterval(doPoll, state.currentInterval);
      }
    };

    // 首次立即执行，之后按间隔轮询
    doPoll();
    pollRef.current = setInterval(doPoll, POLL_INITIAL_INTERVAL);
  }, []);

  // 清理轮询
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // 启动分析
  const handleStart = async () => {
    if (!ticker.trim() || !tradeDate) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const { task_id } = await deepAnalysisApi.startAnalysis({
        ticker: ticker.trim(),
        trade_date: tradeDate,
        base_url: baseUrl.trim() || undefined,
        model: modelSelection.model || undefined,
      });
      setActiveTaskId(task_id);
      startPolling(task_id);
      await refreshTasks();
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string } }; message?: string };
      const msg = apiErr.response?.data?.detail || apiErr.message || '启动分析失败';
      setErrorMsg(msg);
      console.error('启动分析失败:', err);
    } finally {
      setLoading(false);
    }
  };

  // 删除任务
  const handleDeleteTask = useCallback(async (taskId: string) => {
    setDeletingTaskId(taskId);
    setDeleteConfirmId(null);
    try {
      await deepAnalysisApi.deleteTask(taskId);
      // 如果删除的是当前活跃任务，清除
      if (activeTaskId === taskId) {
        setActiveTaskId(null);
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      }
      await refreshTasks();
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string } }; message?: string };
      const msg = apiErr.response?.data?.detail || apiErr.message || '删除失败';
      setErrorMsg(msg);
    } finally {
      setDeletingTaskId(null);
    }
  }, [activeTaskId, refreshTasks]);

  // 点击历史任务 → 查看详情
  const handleViewHistoryTask = useCallback(async (taskId: string) => {
    // 先停止任何进行中的轮询
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }

    setActiveTaskId(taskId);

    // 从本地 tasks 中找到该任务
    const localTask = tasks.find(t => t.task_id === taskId);

    // 如果本地数据不完整（没有 stage_reports），则从服务端拉取完整数据
    if (!localTask || (localTask.status === 'completed' && !localTask.stage_reports && Object.keys(localTask.stage_reports || {}).length === 0)) {
      try {
        const fullTask = await deepAnalysisApi.getTaskStatus(taskId);
        setTasks(prev => prev.map(t => t.task_id === taskId ? fullTask : t));
      } catch {
        // 拉取失败也不影响，用本地数据显示
      }
    }

    // 滚动到报告区域
    setTimeout(() => {
      reportAreaRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  }, [tasks]);

  // 恢复轮询已有任务
  useEffect(() => {
    const running = tasks.find(t => t.status === 'pending' || t.status === 'running');
    if (running && !pollRef.current) {
      startPolling(running.task_id);
    }
  }, [tasks, startPolling]);

  const activeTask = tasks.find(t => t.task_id === activeTaskId)
    || tasks.find(t => t.status === 'running' || t.status === 'pending');

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <PageHeader
        title="深度分析"
        description="TradingAgents 多Agent投研框架 — 7位AI分析师 → 质量门控 → 多空辩论 → 风控评估 → 最终决策"
      />

      {/* 输入区域 */}
      <Card>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-12 lg:items-end">
          <div className="min-w-0 lg:col-span-4 xl:col-span-5">
            <label className="block text-xs font-medium text-secondary-text mb-1">股票代码</label>
            <Input
              placeholder="如 000001、600519"
              value={ticker}
              onChange={e => { setTicker(e.target.value.toUpperCase()); setErrorMsg(null); }}
              className="w-full"
            />
          </div>
          <div className="w-full lg:col-span-2 xl:col-span-2">
            <label className="block text-xs font-medium text-secondary-text mb-1">分析日期</label>
            <Input
              type="date"
              value={tradeDate}
              onChange={e => { setTradeDate(e.target.value); setErrorMsg(null); }}
              className="w-full"
            />
          </div>
          <div className="w-full lg:col-span-3 xl:col-span-3">
            <label className="block text-xs font-medium text-secondary-text mb-1">LLM 代理地址 (可选)</label>
            <Input
              placeholder="http://127.0.0.1:65430/v1"
              value={baseUrl}
              onChange={e => setBaseUrl(e.target.value)}
              className="w-full"
            />
          </div>
          <div className="w-full lg:col-span-3 xl:col-span-2">
            <DeepAnalysisModelSelector value={modelSelection} onChange={setModelSelection} />
          </div>
          <Button
            onClick={handleStart}
            disabled={loading || !ticker.trim() || !tradeDate}
            className="w-full lg:col-span-12 xl:col-span-12 xl:w-auto xl:justify-self-end"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Play className="h-4 w-4 mr-2" />
            )}
            开始分析
          </Button>
        </div>
        {/* 错误提示 */}
        {errorMsg && (
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/8 px-3 py-2">
            <AlertTriangle className="h-4 w-4 text-red-400 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-red-400">{errorMsg}</p>
            </div>
            <button
              type="button"
              onClick={() => setErrorMsg(null)}
              className="text-muted-foreground hover:text-foreground flex-shrink-0"
            >
              <XCircle className="h-4 w-4" />
            </button>
          </div>
        )}
      </Card>

      {/* 当前活跃任务进度 / 报告 / 失败 - 统一包裹以便滚动定位 */}
      <div ref={reportAreaRef}>
        {/* 当前活跃任务进度 */}
        {activeTask && (activeTask.status === 'pending' || activeTask.status === 'running') && (
        <Card>
          <div className="flex items-center gap-2 mb-3">
            <Loader2 className="h-4 w-4 animate-spin text-[hsl(var(--primary))]" />
            <span className="text-sm font-semibold text-foreground">
              正在分析 {activeTask.ticker} ({activeTask.trade_date})
            </span>
            {activeTask.elapsed > 0 && (
              <span className="text-xs text-muted-foreground ml-auto">{activeTask.elapsed.toFixed(0)}s</span>
            )}
          </div>
          <ProgressBar
            stages={stages}
            completedStages={activeTask.completed_stages}
            currentStage={activeTask.current_stage}
            status={activeTask.status}
          />
        </Card>
      )}

      {/* 已完成的任务结果 */}
      {activeTask && activeTask.status === 'completed' && (
        <ReportPanel
          stages={stages}
          stageReports={activeTask.stage_reports}
          signal={activeTask.signal}
          stats={activeTask.stats}
          elapsed={activeTask.elapsed}
          reportDownloadUrl={activeTask.report_download_url || deepAnalysisApi.getReportDownloadUrl(activeTask.task_id)}
          taskId={activeTask.task_id}
        />
      )}

      {/* 失败 */}
      {activeTask && activeTask.status === 'failed' && (
        <Card className="border-red-500/30 bg-red-500/5">
          <div className="flex items-start gap-3">
            <XCircle className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <p className="text-sm font-semibold text-red-400">
                  分析失败 - {activeTask.ticker} ({activeTask.trade_date})
                </p>
              </div>
              <p className="text-xs text-secondary-text break-words">{activeTask.error || '未知错误'}</p>
              {activeTask.elapsed > 0 && (
                <p className="text-xs text-muted-foreground mt-1">耗时: {activeTask.elapsed.toFixed(0)}s</p>
              )}
            </div>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <Button
                variant="danger-subtle"
                size="sm"
                title="删除此任务"
                onClick={() => {
                  if (deleteConfirmId === activeTask.task_id) {
                    handleDeleteTask(activeTask.task_id);
                  } else {
                    setDeleteConfirmId(activeTask.task_id);
                  }
                }}
                disabled={deletingTaskId === activeTask.task_id}
              >
                {deletingTaskId === activeTask.task_id ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : deleteConfirmId === activeTask.task_id ? (
                  <>
                    <AlertTriangle className="h-3.5 w-3.5" />
                    确认删除
                  </>
                ) : (
                  <>
                    <Trash2 className="h-3.5 w-3.5" />
                    删除
                  </>
                )}
              </Button>
            </div>
          </div>
        </Card>
      )}
      </div>

      {/* 历史任务列表 */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-foreground">
            <Clock className="inline h-4 w-4 mr-1.5 -mt-0.5" />
            分析历史
          </h3>
          <Button variant="ghost" size="sm" onClick={refreshTasks}>
            <RefreshCw className="h-3.5 w-3.5 mr-1" />
            刷新
          </Button>
        </div>

        {tasks.length === 0 ? (
          <EmptyState
            icon={<BarChart3 className="h-8 w-8 text-muted-foreground" />}
            title="暂无分析记录"
            description="输入股票代码和日期，开始你的第一次深度分析"
          />
        ) : (
          <div className="space-y-2">
            {tasks.map(task => {
              const sig = parseSignal(task.signal);
              const isActive = task.task_id === activeTaskId;
              const hasReport = task.status === 'completed' && !!task.report_path;
              const isFailed = task.status === 'failed';
              const isConfirmingDelete = deleteConfirmId === task.task_id;
              const isDeleting = deletingTaskId === task.task_id;
              return (
                <div
                  key={task.task_id}
                  className={`transition-all cursor-pointer ${
                    isActive
                      ? 'ring-2 ring-[hsl(var(--primary))/0.5] bg-[hsl(var(--primary))/0.06]'
                      : isFailed
                        ? 'border-red-500/20 bg-red-500/[0.03] hover:bg-red-500/[0.06]'
                        : 'hover:bg-hover/30'
                  }`}
                  onClick={() => handleViewHistoryTask(task.task_id)}
                >
                <Card className="border-none bg-transparent shadow-none p-0">
                  <div className="flex items-center gap-3">
                    <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${
                      isActive
                        ? 'bg-[hsl(var(--primary))/0.2]'
                        : isFailed
                          ? 'bg-red-500/15'
                          : 'bg-[hsl(var(--primary))/0.12]'
                    }`}>
                      {isFailed ? (
                        <XCircle className="h-5 w-5 text-red-400" />
                      ) : (
                        <Brain className="h-5 w-5 text-[hsl(var(--primary))]" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-foreground">{task.ticker}</p>
                        <span className="text-xs text-muted-foreground">{task.trade_date}</span>
                        {isActive && (
                          <Badge variant="info" size="sm">
                            <ExternalLink className="h-3 w-3 mr-0.5" />
                            查看中
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        {task.status === 'running' || task.status === 'pending' ? (
                          <Badge variant="info" size="sm">
                            <Loader2 className="h-3 w-3 animate-spin mr-1" />
                            分析中
                          </Badge>
                        ) : task.status === 'completed' ? (
                          <Badge
                            variant={sig.direction === 'bullish' ? 'success' : sig.direction === 'bearish' ? 'danger' : 'default'}
                            size="sm"
                          >
                            {sig.direction === 'bullish' ? <TrendingUp className="h-3 w-3 mr-1" /> : sig.direction === 'bearish' ? <TrendingDown className="h-3 w-3 mr-1" /> : <Activity className="h-3 w-3 mr-1" />}
                            {sig.label}
                          </Badge>
                        ) : (
                          <Badge variant="danger" size="sm">
                            <XCircle className="h-3 w-3 mr-1" />
                            失败
                          </Badge>
                        )}
                        {task.stats.llm_calls > 0 && (
                          <span className="text-xs text-muted-foreground">
                            <Zap className="inline h-3 w-3 mr-0.5" />
                            {task.stats.llm_calls}次调用
                          </span>
                        )}
                        {task.elapsed > 0 && (
                          <span className="text-xs text-muted-foreground">{task.elapsed.toFixed(0)}s</span>
                        )}
                      </div>
                      {/* 失败原因摘要 */}
                      {isFailed && task.error && (
                        <p className="text-xs text-red-400/70 mt-1 truncate max-w-[320px]" title={task.error}>
                          {task.error}
                        </p>
                      )}
                    </div>
                    {/* 操作按钮 */}
                    <div className="flex items-center gap-1.5 flex-shrink-0" onClick={e => e.stopPropagation()}>
                      {hasReport && (
                        <a
                          href={task.report_download_url || deepAnalysisApi.getReportDownloadUrl(task.task_id)}
                          download
                          title="下载报告"
                          className="inline-flex items-center justify-center gap-1.5 h-9 rounded-lg px-3 text-sm font-medium border border-cyan/25 bg-transparent text-cyan hover:bg-cyan/10 transition-all duration-200"
                        >
                          <Download className="h-3.5 w-3.5" />
                          下载
                        </a>
                      )}
                      {task.status === 'completed' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          title="查看详情"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleViewHistoryTask(task.task_id);
                          }}
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      {/* 删除按钮（含二次确认） */}
                      {isConfirmingDelete ? (
                        <Button
                          variant="danger"
                          size="sm"
                          title="确认删除"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteTask(task.task_id);
                          }}
                          disabled={isDeleting}
                        >
                          {isDeleting ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            '确认'
                          )}
                        </Button>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          title="删除任务"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteConfirmId(task.task_id);
                          }}
                          className="text-muted-foreground hover:text-red-400"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </div>
                </Card>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
