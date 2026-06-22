import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { MessageSquareQuote, Search, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { backtestApi } from '../api/backtest';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Badge, Card, Drawer, EmptyState, StatusDot, Tooltip } from '../components/common';
import type { BacktestOptimizationLogItem, BacktestOptimizationOverview } from '../types/backtest';

const COMPACT_INPUT_CLASS =
  'h-8 rounded-xl border border-white/10 bg-background/80 px-3 text-sm text-foreground placeholder:text-muted-text outline-none transition-colors focus:border-cyan/40 focus:ring-1 focus:ring-cyan/20';

function fmtPct(value?: number | null): string {
  if (value == null) return '--';
  return `${value.toFixed(1)}%`;
}

function formatLogJson(value: unknown): string {
  if (value == null) return '--';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function toNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

type OptimizationCandidateRow = Record<string, unknown> & {
  params?: Record<string, unknown>;
  results?: Array<Record<string, unknown>>;
  score?: unknown;
};

type CandidateSortKey = 'score' | 'window' | 'winRate' | 'sampleSize';

type SummarizedCandidateRow = ReturnType<typeof summarizeCandidateRow>;

const CandidateTable: React.FC<{ results: OptimizationCandidateRow[]; onSelect: (row: SummarizedCandidateRow) => void }> = ({ results, onSelect }) => {
  const [candidateQuery, setCandidateQuery] = useState('');
  const [candidateSortKey, setCandidateSortKey] = useState<CandidateSortKey>('score');
  const [candidateSortDesc, setCandidateSortDesc] = useState(true);

  const rows = useMemo(() => {
    const normalizedQuery = candidateQuery.trim().toLowerCase();
    return results
      .map((row, index) => summarizeCandidateRow(row, index))
      .filter((row) => {
        if (!normalizedQuery) return true;
        const haystack = [row.parameterSummary, row.outcomeSummary, row.trailingStopLabel, row.evalWindowLabel, row.neutralBandLabel, row.stopLossLabel, row.takeProfitLabel]
          .join(' ')
          .toLowerCase();
        return haystack.includes(normalizedQuery);
      })
      .sort((left, right) => {
        const scoreDelta = (right.scoreValue ?? -Infinity) - (left.scoreValue ?? -Infinity);
        const windowDelta = (right.evalWindowDays ?? -Infinity) - (left.evalWindowDays ?? -Infinity);
        const winRateDelta = (right.winRatePct ?? -Infinity) - (left.winRatePct ?? -Infinity);
        const sampleDelta = right.sampleSize - left.sampleSize;
        const sortMap: Record<CandidateSortKey, number> = {
          score: scoreDelta,
          window: windowDelta,
          winRate: winRateDelta,
          sampleSize: sampleDelta,
        };
        const primary = sortMap[candidateSortKey];
        if (primary !== 0) return candidateSortDesc ? primary : -primary;
        return scoreDelta;
      })
      .slice(0, 20);
  }, [candidateQuery, candidateSortDesc, candidateSortKey, results]);

  const topScore = rows[0]?.scoreValue ?? null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1">
          <input
            type="text"
            value={candidateQuery}
            onChange={(e) => setCandidateQuery(e.target.value)}
            placeholder="搜索参数标签，如 ‘止损 5%’ / ‘追踪止损’"
            className={`${COMPACT_INPUT_CLASS} w-full pl-9`}
          />
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-text" />
        </div>
        <button type="button" className={`${COMPACT_INPUT_CLASS} text-xs ${candidateSortKey === 'score' ? 'ring-1 ring-cyan/30' : ''}`} onClick={() => setCandidateSortKey('score')}>按评分</button>
        <button type="button" className={`${COMPACT_INPUT_CLASS} text-xs ${candidateSortKey === 'winRate' ? 'ring-1 ring-cyan/30' : ''}`} onClick={() => setCandidateSortKey('winRate')}>按胜率</button>
        <button type="button" className={`${COMPACT_INPUT_CLASS} text-xs ${candidateSortKey === 'window' ? 'ring-1 ring-cyan/30' : ''}`} onClick={() => setCandidateSortKey('window')}>按窗口</button>
        <button type="button" className={`${COMPACT_INPUT_CLASS} text-xs ${candidateSortKey === 'sampleSize' ? 'ring-1 ring-cyan/30' : ''}`} onClick={() => setCandidateSortKey('sampleSize')}>按样本</button>
        <button type="button" className="btn-secondary text-xs" onClick={() => setCandidateSortDesc((prev) => !prev)}>{candidateSortDesc ? '降序' : '升序'}</button>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[980px] w-full text-xs">
          <thead className="border-b border-white/10 text-left text-muted-text">
            <tr>
              <th className="px-3 py-2 font-medium">排名</th>
              <th className="px-3 py-2 font-medium">评分 {candidateSortKey === 'score' ? (candidateSortDesc ? '↓' : '↑') : ''}</th>
              <th className="px-3 py-2 font-medium">窗口 {candidateSortKey === 'window' ? (candidateSortDesc ? '↓' : '↑') : ''}</th>
              <th className="px-3 py-2 font-medium">中性带</th>
              <th className="px-3 py-2 font-medium">止损</th>
              <th className="px-3 py-2 font-medium">止盈</th>
              <th className="px-3 py-2 font-medium">追踪</th>
              <th className="px-3 py-2 font-medium">完成/样本 {candidateSortKey === 'sampleSize' ? (candidateSortDesc ? '↓' : '↑') : ''}</th>
              <th className="px-3 py-2 font-medium">赢/输/中</th>
              <th className="px-3 py-2 font-medium">胜率 {candidateSortKey === 'winRate' ? (candidateSortDesc ? '↓' : '↑') : ''}</th>
              <th className="px-3 py-2 font-medium">参数标签</th>
              <th className="px-3 py-2 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr
                key={`${row.index}-${index}`}
                className={`border-b border-white/5 last:border-0 ${index === 0 ? 'bg-success/10 ring-1 ring-success/20' : ''} cursor-pointer transition-colors hover:bg-hover/60`}
                onClick={() => onSelect(row)}
              >
                <td className="px-3 py-2 text-secondary-text">#{index + 1}</td>
                <td className="px-3 py-2"><Badge variant={index === 0 ? 'success' : 'history'}>{index === 0 ? '最优' : row.scoreLabel}</Badge></td>
                <td className="px-3 py-2 text-secondary-text">{row.evalWindowLabel}</td>
                <td className="px-3 py-2 text-secondary-text">{row.neutralBandLabel}</td>
                <td className="px-3 py-2 text-secondary-text">{row.stopLossLabel}</td>
                <td className="px-3 py-2 text-secondary-text">{row.takeProfitLabel}</td>
                <td className="px-3 py-2 text-secondary-text">{row.trailingStopLabel}</td>
                <td className="px-3 py-2 text-secondary-text">{row.completedSize} / {row.sampleSize}</td>
                <td className="px-3 py-2 text-secondary-text">赢 {row.winCount} · 输 {row.lossCount} · 中 {row.neutralCount}</td>
                <td className="px-3 py-2 text-secondary-text">{row.winRatePct != null ? `${row.winRatePct.toFixed(1)}%` : '--'}</td>
                <td className="px-3 py-2 text-secondary-text">{row.parameterSummary}</td>
                <td className="px-3 py-2">
                  <button type="button" className="text-xs font-medium text-cyan transition-colors hover:text-cyan/80" onClick={(event) => { event.stopPropagation(); onSelect(row); }}>
                    查看明细
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-text">
        <span>当前筛选下最高评分：{topScore != null ? topScore.toFixed(1) : '--'}</span>
        <span>{rows.length > 0 ? '首行已标记为最优候选' : '暂无可显示的候选'}</span>
      </div>
    </div>
  );
};

function summarizeCandidateRow(row: OptimizationCandidateRow, index: number) {
  const params = row.params ?? {};
  const nestedResults = Array.isArray(row.results) ? row.results : [];
  const completedResults = nestedResults.filter((item) => item && item.eval_status === 'completed');
  const winCount = completedResults.filter((item) => item.outcome === 'win').length;
  const lossCount = completedResults.filter((item) => item.outcome === 'loss').length;
  const neutralCount = completedResults.filter((item) => item.outcome === 'neutral').length;
  const scoreValue = toNumber(row.score);
  const evalWindowDays = toNumber(params.evalWindowDays);
  const neutralBandPct = toNumber(params.neutralBandPct);
  const stopLossPct = toNumber(params.stopLossPct);
  const takeProfitRr = toNumber(params.takeProfitRr);
  const useTrailingStop = params.useTrailingStop == null ? null : Boolean(params.useTrailingStop);
  return {
    index,
    params,
    scoreValue,
    scoreLabel: scoreValue != null ? scoreValue.toFixed(1) : '--',
    evalWindowDays,
    evalWindowLabel: evalWindowDays != null ? `${evalWindowDays} 日` : '--',
    neutralBandPct,
    neutralBandLabel: neutralBandPct != null ? `±${neutralBandPct}%` : '--',
    stopLossPct,
    stopLossLabel: stopLossPct != null ? `${stopLossPct}%` : '--',
    takeProfitRr,
    takeProfitLabel: takeProfitRr != null ? `${takeProfitRr}R` : '--',
    useTrailingStop,
    trailingStopLabel: useTrailingStop == null ? '--' : useTrailingStop ? '开启' : '关闭',
    sampleSize: nestedResults.length,
    completedSize: completedResults.length,
    winCount,
    lossCount,
    neutralCount,
    winRatePct: completedResults.length > 0 ? (winCount / completedResults.length) * 100 : null,
    lossRatePct: completedResults.length > 0 ? (lossCount / completedResults.length) * 100 : null,
    neutralRatePct: completedResults.length > 0 ? (neutralCount / completedResults.length) * 100 : null,
    outcomeSummary: completedResults.length > 0 ? `赢 ${winCount} · 输 ${lossCount} · 中 ${neutralCount}` : '--',
    parameterSummary: formatLogParams(params),
  };
}

function formatLogParams(params?: Record<string, unknown> | null): string {
  if (!params) return '--';
  const parts: string[] = [];
  const windowDays = toNumber(params.evalWindowDays);
  if (windowDays != null) parts.push(`窗口 ${windowDays} 日`);
  const neutralBandPct = toNumber(params.neutralBandPct);
  if (neutralBandPct != null) parts.push(`中性带 ±${neutralBandPct}%`);
  const stopLossPct = toNumber(params.stopLossPct);
  if (stopLossPct != null) parts.push(`止损 ${stopLossPct}%`);
  const takeProfitRr = toNumber(params.takeProfitRr);
  if (takeProfitRr != null) parts.push(`止盈 ${takeProfitRr}R`);
  if (params.useTrailingStop != null) parts.push(`追踪止损 ${params.useTrailingStop ? '开启' : '关闭'}`);
  return parts.length > 0 ? parts.join(' · ') : formatLogJson(params);
}

const CandidateLogDrawer: React.FC<{
  selectedOptimizationLog: BacktestOptimizationLogItem | null;
  selectedCandidate: SummarizedCandidateRow | null;
  onCloseLog: () => void;
  onSelectCandidate: (row: SummarizedCandidateRow | null) => void;
}> = ({ selectedOptimizationLog, selectedCandidate, onCloseLog, onSelectCandidate }) => (
  <>
    <Drawer
      isOpen={selectedOptimizationLog != null}
      onClose={onCloseLog}
      title={selectedOptimizationLog ? `优化详情 · ${selectedOptimizationLog.code || '全市场'}` : '优化详情'}
      width="max-w-6xl"
    >
      {selectedOptimizationLog ? (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <MetricRow label="时间" value={selectedOptimizationLog.createdAt ? new Date(selectedOptimizationLog.createdAt).toLocaleString() : '--'} />
            <MetricRow label="窗口" value={`${selectedOptimizationLog.evalWindowDays} 日`} />
            <MetricRow label="组合数" value={`${selectedOptimizationLog.combinations}`} />
            <MetricRow label="最佳评分" value={selectedOptimizationLog.bestScore != null ? selectedOptimizationLog.bestScore.toFixed(1) : '--'} accent />
            <MetricRow label="评分键" value={selectedOptimizationLog.scoreKey} />
            <MetricRow label="引擎" value={selectedOptimizationLog.engineVersion} />
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-card/60 p-4">
              <div className="mb-2 text-xs font-medium uppercase tracking-[0.18em] text-muted-text">最优参数展开详情</div>
              <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-secondary-text">{formatLogJson(selectedOptimizationLog.bestParams)}</pre>
            </div>
            <div className="rounded-2xl border border-white/10 bg-card/60 p-4">
              <div className="mb-2 text-xs font-medium uppercase tracking-[0.18em] text-muted-text">最佳结果</div>
              <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-secondary-text">{formatLogJson(selectedOptimizationLog.bestResult)}</pre>
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-card/60 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <div className="text-xs font-medium uppercase tracking-[0.18em] text-muted-text">完整候选结果</div>
                <div className="mt-1 text-xs text-muted-text">更适合逐行阅读的候选表格，支持搜索、排序和点击查看明细。</div>
              </div>
              <Badge variant="history">{selectedOptimizationLog.results.length} 条</Badge>
            </div>
            {selectedOptimizationLog.results.length > 0 ? (
              <CandidateTable results={selectedOptimizationLog.results as OptimizationCandidateRow[]} onSelect={(row) => onSelectCandidate(row)} />
            ) : (
              <div className="text-sm text-muted-text">暂无候选结果。</div>
            )}
            <details className="mt-4 rounded-2xl border border-white/10 bg-background/70 px-4 py-3">
              <summary className="cursor-pointer text-xs font-medium uppercase tracking-[0.18em] text-muted-text">原始 JSON</summary>
              <pre className="mt-3 max-h-[24rem] overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-secondary-text">{formatLogJson(selectedOptimizationLog.results)}</pre>
            </details>
          </div>
        </div>
      ) : null}
    </Drawer>

    <Drawer
      isOpen={selectedCandidate != null}
      onClose={() => onSelectCandidate(null)}
      title={selectedCandidate ? `候选明细 · #${selectedCandidate.index + 1}` : '候选明细'}
      width="max-w-2xl"
    >
      {selectedCandidate ? (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <MetricRow label="评分" value={selectedCandidate.scoreLabel} accent />
            <MetricRow label="窗口" value={selectedCandidate.evalWindowLabel} />
            <MetricRow label="中性带" value={selectedCandidate.neutralBandLabel} />
            <MetricRow label="止损" value={selectedCandidate.stopLossLabel} />
            <MetricRow label="止盈" value={selectedCandidate.takeProfitLabel} />
            <MetricRow label="追踪止损" value={selectedCandidate.trailingStopLabel} />
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <MetricRow label="完成/样本" value={`${selectedCandidate.completedSize} / ${selectedCandidate.sampleSize}`} />
            <MetricRow label="赢/输/中" value={`赢 ${selectedCandidate.winCount} · 输 ${selectedCandidate.lossCount} · 中 ${selectedCandidate.neutralCount}`} />
            <MetricRow label="胜率" value={fmtPct(selectedCandidate.winRatePct)} />
          </div>
          <div className="rounded-2xl border border-white/10 bg-card/60 p-4">
            <div className="mb-2 text-xs font-medium uppercase tracking-[0.18em] text-muted-text">参数标签</div>
            <div className="text-sm text-secondary-text">{selectedCandidate.parameterSummary}</div>
          </div>
          <details className="rounded-2xl border border-white/10 bg-background/70 px-4 py-3">
            <summary className="cursor-pointer text-xs font-medium uppercase tracking-[0.18em] text-muted-text">完整参数 JSON</summary>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <MetricRow label="参数标签" value={selectedCandidate.parameterSummary} />
              <MetricRow label="完成/样本" value={`${selectedCandidate.completedSize} / ${selectedCandidate.sampleSize}`} />
              <MetricRow label="赢/输/中" value={`赢 ${selectedCandidate.winCount} · 输 ${selectedCandidate.lossCount} · 中 ${selectedCandidate.neutralCount}`} />
              <MetricRow label="胜率" value={fmtPct(selectedCandidate.winRatePct)} />
            </div>
            <pre className="mt-3 max-h-[24rem] overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-secondary-text">{formatLogJson(selectedCandidate.params)}</pre>
          </details>
        </div>
      ) : null}
    </Drawer>
  </>
);

const MetricRow: React.FC<{ label: string; value: React.ReactNode; accent?: boolean }> = ({ label, value, accent = false }) => (
  <div className={`rounded-2xl border border-white/10 bg-background/70 p-4 ${accent ? 'ring-1 ring-cyan/20' : ''}`}>
    <div className="text-[11px] uppercase tracking-[0.18em] text-muted-text">{label}</div>
    <div className={`mt-2 text-sm font-medium ${accent ? 'text-cyan' : 'text-secondary-text'}`}>{value}</div>
  </div>
);

const OptimizationCard: React.FC<{ overview: BacktestOptimizationOverview; loading: boolean; onRun: () => void; onViewLog: (log: BacktestOptimizationLogItem) => void }> = ({ overview, loading, onRun, onViewLog }) => {
  const latest = overview.latest ?? overview.history[0] ?? null;
  const history = overview.history.slice(0, 5);

  return (
    <Card className="space-y-4 border-white/10 bg-card/70 p-5 shadow-[0_16px_40px_rgba(0,0,0,0.12)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-medium uppercase tracking-[0.18em] text-muted-text">回测优化</div>
          <h2 className="mt-1 text-lg font-semibold text-foreground">参数扫描工作台</h2>
          <p className="mt-1 text-sm text-secondary-text">快速比较参数组合，查看最优结果与最近 5 次扫描历史。</p>
        </div>
        <Badge variant="history">{overview.total}</Badge>
      </div>
      <button
        type="button"
        onClick={onRun}
        disabled={loading}
        className="btn-primary flex w-full items-center justify-center gap-2"
      >
        {loading ? <div className="backtest-spinner sm" /> : <Sparkles className="h-4 w-4" />}
        {loading ? '扫描中...' : '开始扫描'}
      </button>
      {latest ? (
        <div className="space-y-3 rounded-2xl border border-white/10 bg-background/60 p-4">
          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="text-xs font-medium uppercase tracking-[0.18em] text-muted-text">最新扫描</div>
              <div className="mt-1 text-sm text-secondary-text">{latest.code || '全市场'} · {latest.evalWindowDays} 日 · {latest.combinations} 组合</div>
            </div>
            <button type="button" className="text-xs font-medium text-cyan transition-colors hover:text-cyan/80" onClick={() => onViewLog(latest)}>查看</button>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <MetricRow label="最佳评分" value={latest.bestScore != null ? latest.bestScore.toFixed(1) : '--'} accent />
            <MetricRow label="评分键" value={latest.scoreKey} />
          </div>
          <div className="text-xs text-muted-text">最佳参数：{latest.bestParams ? formatLogJson(latest.bestParams) : '--'}</div>
        </div>
      ) : (
        <EmptyState title="暂无扫描记录" description="先运行一次参数扫描，才能查看最优组合和历史轨迹。" className="min-h-[11rem] border-dashed bg-background/40 shadow-none" />
      )}
      <div className="space-y-2 rounded-2xl border border-white/10 bg-background/60 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs font-medium uppercase tracking-[0.18em] text-muted-text">最近 5 次扫描历史表</div>
            <div className="mt-1 text-xs text-muted-text">点击任意一行查看该次扫描的最优参数和候选明细。</div>
          </div>
        </div>
        {history.length > 0 ? (
          <div className="overflow-hidden rounded-2xl border border-white/10">
            <table className="min-w-full divide-y divide-white/10 text-xs">
              <thead className="bg-background/80 text-left text-muted-text">
                <tr>
                  <th className="px-3 py-2 font-medium">时间</th>
                  <th className="px-3 py-2 font-medium">代码</th>
                  <th className="px-3 py-2 font-medium">窗口</th>
                  <th className="px-3 py-2 font-medium">组合</th>
                  <th className="px-3 py-2 font-medium">最佳评分</th>
                  <th className="px-3 py-2 font-medium">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {history.map((item) => (
                  <tr key={item.id} className="bg-card/40 transition-colors hover:bg-hover/60">
                    <td className="px-3 py-2 text-secondary-text">{item.createdAt ? new Date(item.createdAt).toLocaleString() : '--'}</td>
                    <td className="px-3 py-2 text-secondary-text">{item.code || '全市场'}</td>
                    <td className="px-3 py-2 text-secondary-text">{item.evalWindowDays} 日</td>
                    <td className="px-3 py-2 text-secondary-text">{item.combinations}</td>
                    <td className="px-3 py-2 text-secondary-text">{item.bestScore != null ? item.bestScore.toFixed(1) : '--'}</td>
                    <td className="px-3 py-2">
                      <button type="button" className="text-xs font-medium text-cyan transition-colors hover:text-cyan/80" onClick={() => onViewLog(item)}>查看</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-sm text-muted-text">暂无历史扫描。</div>
        )}
      </div>
    </Card>
  );
};

const BacktestOptimizationPage: React.FC = () => {
  const navigate = useNavigate();
  const [optimizationOverview, setOptimizationOverview] = useState<BacktestOptimizationOverview>({ history: [], total: 0 });
  const [selectedOptimizationLog, setSelectedOptimizationLog] = useState<BacktestOptimizationLogItem | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<SummarizedCandidateRow | null>(null);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);

  const loadOptimizationLogs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const overview = await backtestApi.getOptimizationLogs({ limit: 20 });
      setOptimizationOverview(overview);
      setSelectedOptimizationLog((current) => current ?? overview.latest ?? null);
    } catch (err) {
      const parsedError = getParsedApiError(err);
      setError(parsedError);
      console.error('Failed to load optimization logs:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadOptimizationLogs();
  }, [loadOptimizationLogs]);

  const handleOptimize = useCallback(async () => {
    setIsOptimizing(true);
    setError(null);
    try {
      await backtestApi.optimize({ limit: 20 });
      await loadOptimizationLogs();
    } catch (err) {
      const parsedError = getParsedApiError(err);
      setError(parsedError);
      console.error('Failed to run optimization:', err);
    } finally {
      setIsOptimizing(false);
    }
  }, [loadOptimizationLogs]);

  const openLog = useCallback((log: BacktestOptimizationLogItem) => {
    setSelectedOptimizationLog(log);
    setSelectedCandidate(null);
  }, []);

  const onSelectCandidate = useCallback((row: SummarizedCandidateRow | null) => {
    setSelectedCandidate(row);
  }, []);

  const latest = optimizationOverview.latest ?? optimizationOverview.history[0] ?? null;
  const hasContent = optimizationOverview.total > 0;

  const summaryCards = useMemo(() => [
    { label: '扫描总数', value: String(optimizationOverview.total) },
    { label: '最近窗口', value: latest ? `${latest.evalWindowDays} 日` : '--' },
    { label: '最新组合', value: latest ? String(latest.combinations) : '--' },
    { label: '引擎版本', value: latest?.engineVersion ?? '--' },
  ], [latest, optimizationOverview.total]);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-4 py-4 sm:px-6 lg:px-8">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-text">
            <Sparkles className="h-3.5 w-3.5" />
            回测优化工作台
          </div>
          <h1 className="mt-1 text-2xl font-semibold text-foreground">参数扫描与候选对比</h1>
          <p className="mt-2 max-w-3xl text-sm text-secondary-text">在独立页面里查看参数扫描、最近 5 次历史、最优参数展开详情，以及更适合阅读的完整候选结果表格。</p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" className="btn-secondary flex items-center gap-2" onClick={() => navigate('/backtest')}>
            <MessageSquareQuote className="h-4 w-4" />
            返回回测页
          </button>
          <button type="button" className="btn-primary flex items-center gap-2" onClick={() => void handleOptimize()} disabled={isOptimizing}>
            {isOptimizing ? <div className="backtest-spinner sm" /> : <Sparkles className="h-4 w-4" />}
            {isOptimizing ? '扫描中...' : '立即扫描'}
          </button>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
        <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
          <div className="space-y-4">
            <Card className="space-y-4 border-white/10 bg-card/70 p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-xs font-medium uppercase tracking-[0.18em] text-muted-text">概览</div>
                  <h2 className="mt-1 text-lg font-semibold text-foreground">快速状态</h2>
                </div>
                <Badge variant="history">{optimizationOverview.total}</Badge>
              </div>
              <div className="grid gap-3">
                {summaryCards.map((card) => (
                  <div key={card.label} className="rounded-2xl border border-white/10 bg-background/60 p-4">
                    <div className="text-[11px] uppercase tracking-[0.18em] text-muted-text">{card.label}</div>
                    <div className="mt-2 text-base font-medium text-secondary-text">{card.value}</div>
                  </div>
                ))}
              </div>
              {error ? <ApiErrorAlert error={error} /> : null}
            </Card>

            <OptimizationCard overview={optimizationOverview} loading={isOptimizing} onRun={handleOptimize} onViewLog={openLog} />
          </div>

          <div className="space-y-4">
            {isLoading ? (
              <Card className="flex min-h-[24rem] items-center justify-center border-dashed border-white/10 bg-card/50">
                <div className="flex items-center gap-3 text-secondary-text">
                  <div className="backtest-spinner sm" />
                  正在加载优化记录...
                </div>
              </Card>
            ) : hasContent ? (
              <Card className="border-white/10 bg-card/70 p-5">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div>
                    <div className="text-xs font-medium uppercase tracking-[0.18em] text-muted-text">优化日志</div>
                    <h2 className="mt-1 text-lg font-semibold text-foreground">候选明细与原始结果</h2>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="history">{optimizationOverview.history.length} 条历史</Badge>
                    <Tooltip content="查看最优参数展开详情和完整候选结果表格">
                      <button type="button" className="btn-secondary h-8 px-3 text-xs" onClick={() => latest && openLog(latest)}>
                        查看最新
                      </button>
                    </Tooltip>
                  </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-background/60 p-4">
                  <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-text">
                    <StatusDot tone="success" />
                    当前最优与历史候选
                  </div>
                  <p className="mt-2 text-sm text-secondary-text">点击任意历史记录可展开最优参数、结果和候选表；候选行也可直接进入细节抽屉。</p>
                </div>
              </Card>
            ) : (
              <EmptyState title="暂无优化记录" description="运行一次参数扫描后，这里会展示历史和候选详情。" className="min-h-[24rem] border-dashed bg-card/50 shadow-none" />
            )}
          </div>
        </div>
      </main>

      <CandidateLogDrawer selectedOptimizationLog={selectedOptimizationLog} selectedCandidate={selectedCandidate} onCloseLog={() => setSelectedOptimizationLog(null)} onSelectCandidate={onSelectCandidate} />
    </div>
  );
};

export default BacktestOptimizationPage;
