import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  TrendingUp, TrendingDown, Zap, Shield, AlertTriangle, Target,
  Filter, RefreshCw, Play, CheckCircle2, XCircle, Search,
  BarChart3, ArrowDownRight, Clock, SlidersHorizontal, LineChart,
  Activity, Info, DollarSign,
} from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { Badge } from '@/components/common/Badge';
import { StatCard } from '@/components/common/StatCard';
import { PageHeader } from '@/components/common/PageHeader';
import { Skeleton } from '@/components/common/Skeleton';
import { EmptyState } from '@/components/common/EmptyState';
import { InlineAlert } from '@/components/common/InlineAlert';
import { Select } from '@/components/common/Select';
import { Input } from '@/components/common/Input';
import { Tooltip } from '@/components/common/Tooltip';
import { Collapsible } from '@/components/common/Collapsible';
import { cn } from '@/utils/cn';
import {
  getOptimizationReport,
  getSourceWeights,
  getOptimizedStopParams,
  checkDiscipline,
  filterSignal,
  type OptimizationReport,
  type SourceWeightItem,
  type StopParams,
  type DisciplineCheckResponse,
  type SignalFilterResponse,
} from '../api/strategyOptimizer';

// ── 健康度色阶 ────────────────────────────────────────────────────────────────

function healthColor(score: number): { stroke: string; bg: string; text: string } {
  if (score >= 80) return { stroke: '#10b981', bg: 'bg-emerald-500/10', text: 'text-emerald-400' };
  if (score >= 60) return { stroke: '#f59e0b', bg: 'bg-amber-500/10', text: 'text-amber-400' };
  if (score >= 40) return { stroke: '#f97316', bg: 'bg-orange-500/10', text: 'text-orange-400' };
  return { stroke: '#ef4444', bg: 'bg-red-500/10', text: 'text-red-400' };
}

// ── 动画健康度仪表 ──────────────────────────────────────────────────────────

const HealthGauge: React.FC<{ score: number; level: string }> = ({ score, level }) => {
  const [animated, setAnimated] = useState(0);
  const hc = healthColor(score);
  const circumference = 2 * Math.PI * 54;
  const progress = (animated / 100) * circumference;

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(score), 100);
    return () => clearTimeout(timer);
  }, [score]);

  return (
    <div className="flex flex-col items-center">
      <svg width="150" height="150" viewBox="0 0 140 140" className="drop-shadow-lg">
        {/* 外圈发光 */}
        <defs>
          <filter id="health-glow">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* 背景轨道 */}
        <circle cx="70" cy="70" r="54" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="10" />

        {/* 进度弧 */}
        <circle
          cx="70" cy="70" r="54"
          fill="none"
          stroke={hc.stroke}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          transform="rotate(-90 70 70)"
          filter="url(#health-glow)"
          className="transition-all duration-1000 ease-out"
        />

        {/* 分数 */}
        <text x="70" y="62" textAnchor="middle" fill={hc.stroke} fontSize="30" fontWeight="bold" className="transition-colors duration-500">
          {animated.toFixed(0)}
        </text>
        <text x="70" y="88" textAnchor="middle" fill="#9ca3af" fontSize="13" fontWeight="500">
          {level}
        </text>
      </svg>
    </div>
  );
};

// ── 来源权重条 ──────────────────────────────────────────────────────────────

const SourceWeightRow: React.FC<{ item: SourceWeightItem; rank: number }> = ({ item, rank }) => {
  const weightPct = Math.min((item.weight / 1.5) * 100, 100);
  const color =
    item.weight >= 1.2 ? 'from-emerald-500 to-emerald-400'
    : item.weight >= 0.7 ? 'from-amber-500 to-amber-400'
    : 'from-red-500 to-red-400';

  const sourceNames: Record<string, string> = {
    analysis: '常规分析',
    deep_analysis: '深度分析',
    seal_plate: '打板',
    comprehensive: '综合推荐',
    manual: '手动录入',
  };

  return (
    <div className="group py-2.5 px-1 rounded-lg hover:bg-white/[0.03] transition-colors">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 font-mono w-4">#{rank}</span>
          <span className="text-sm text-gray-200 font-medium">{sourceNames[item.source] || item.source}</span>
          {item.total < 5 && (
            <Badge variant="warning" size="sm">
              <Info className="w-2.5 h-2.5 mr-0.5" />
              样本少
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs">
          <Tooltip content={`${item.source} 近 ${item.total} 笔推荐方向的正确率`}>
            <span className={cn('font-mono', item.win_rate >= 50 ? 'text-emerald-400' : 'text-red-400')}>
              胜率 {item.win_rate}%
            </span>
          </Tooltip>
          <span className="text-gray-500">{item.total} 笔</span>
          <span className="font-mono font-bold text-gray-300">×{item.weight.toFixed(1)}</span>
        </div>
      </div>
      <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full bg-gradient-to-r transition-all duration-700 ease-out', color)}
          style={{ width: `${weightPct}%` }}
        />
      </div>
    </div>
  );
};

// ── 止损/止盈参数卡片 ──────────────────────────────────────────────────────

const StopParamCard: React.FC<{ label: string; value: string; icon: React.ReactNode; tone: 'danger' | 'warning' | 'success' | 'info' }> = ({
  label, value, icon, tone,
}) => {
  const colors = {
    danger: 'border-red-500/20 bg-red-500/5',
    warning: 'border-amber-500/20 bg-amber-500/5',
    success: 'border-emerald-500/20 bg-emerald-500/5',
    info: 'border-cyan-500/20 bg-cyan-500/5',
  };
  const textColors = {
    danger: 'text-red-400',
    warning: 'text-amber-400',
    success: 'text-emerald-400',
    info: 'text-cyan-400',
  };

  return (
    <div className={cn('rounded-xl border p-4 flex items-center gap-3', colors[tone])}>
      <div className={cn('p-2 rounded-lg', colors[tone])}>
        {icon}
      </div>
      <div>
        <p className="text-xs text-gray-400">{label}</p>
        <p className={cn('text-xl font-mono font-bold', textColors[tone])}>{value}</p>
      </div>
    </div>
  );
};

// ── 高风险持仓表格 ──────────────────────────────────────────────────────────

const RiskTable: React.FC<{ positions: OptimizationReport['high_risk_positions'] }> = ({ positions }) => {
  if (!positions.length) return null;

  return (
    <div className="overflow-x-auto -mx-1">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-red-500/15">
            <th className="text-left py-3 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">标的</th>
            <th className="text-left py-3 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">推荐日</th>
            <th className="text-left py-3 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">方向</th>
            <th className="text-right py-3 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">推荐价</th>
            <th className="text-right py-3 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">现价</th>
            <th className="text-right py-3 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">偏差</th>
            <th className="text-right py-3 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">风险等级</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/50">
          {positions.map((pos) => {
            const isSevere = Math.abs(pos.deviation_pct) > 7;
            return (
              <tr key={pos.id} className={cn('hover:bg-red-500/[0.03] transition-colors', isSevere && 'bg-red-500/[0.04]')}>
                <td className="py-2.5 px-3">
                  <span className="font-mono text-white font-medium">{pos.code}</span>
                </td>
                <td className="py-2.5 px-3 text-gray-400">{pos.trade_date}</td>
                <td className="py-2.5 px-3">
                  <Badge
                    variant={pos.signal === 'buy' ? 'success' : pos.signal === 'sell' ? 'danger' : 'warning'}
                    size="sm"
                  >
                    {pos.signal === 'buy' ? <TrendingUp className="w-3 h-3 mr-1" /> : pos.signal === 'sell' ? <TrendingDown className="w-3 h-3 mr-1" /> : null}
                    {pos.signal === 'buy' ? '看多' : pos.signal === 'sell' ? '看空' : pos.signal}
                  </Badge>
                </td>
                <td className="py-2.5 px-3 text-right text-gray-300 font-mono">{pos.recommendation_price.toFixed(2)}</td>
                <td className="py-2.5 px-3 text-right text-gray-300 font-mono">{pos.current_price.toFixed(2)}</td>
                <td className="py-2.5 px-3 text-right">
                  <span className={cn('font-mono font-semibold flex items-center justify-end gap-1', isSevere ? 'text-red-400' : 'text-orange-400')}>
                    <ArrowDownRight className="w-3.5 h-3.5" />
                    {pos.deviation_pct}%
                  </span>
                </td>
                <td className="py-2.5 px-3 text-right">
                  <Badge variant={isSevere ? 'danger' : 'warning'} size="sm" glow={isSevere}>
                    {isSevere ? '严重' : '关注'}
                  </Badge>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

// ── 交易纪律检查器（交互式）─────────────────────────────────────────────────

const DisciplineChecker: React.FC = () => {
  const [code, setCode] = useState('');
  const [biasMa5, setBiasMa5] = useState('');
  const [volumeRatio, setVolumeRatio] = useState('');
  const [maAlignment, setMaAlignment] = useState('');
  const [concentration90, setConcentration90] = useState('');
  const [profitRatio, setProfitRatio] = useState('');
  const [result, setResult] = useState<DisciplineCheckResponse | null>(null);
  const [checking, setChecking] = useState(false);
  const [hasChecked, setHasChecked] = useState(false);

  const handleCheck = useCallback(async () => {
    if (!code) return;
    setChecking(true);
    try {
      const res = await checkDiscipline({
        code,
        bias_ma5: biasMa5 ? parseFloat(biasMa5) : 0,
        volume_ratio: volumeRatio ? parseFloat(volumeRatio) : undefined,
        ma_alignment: maAlignment,
        concentration_90: concentration90 ? parseFloat(concentration90) / 100 : undefined,
        profit_ratio: profitRatio ? parseFloat(profitRatio) / 100 : undefined,
      });
      setResult(res);
      setHasChecked(true);
    } catch {
      setResult({ passed: false, violations: ['网络请求失败，请重试'], rules: {} });
      setHasChecked(true);
    } finally {
      setChecking(false);
    }
  }, [code, biasMa5, volumeRatio, maAlignment, concentration90, profitRatio]);

  return (
    <Card variant="glass" padding="lg" className="h-full">
      <div className="flex items-center gap-2 mb-5">
        <Shield className="w-5 h-5 text-cyan-400" />
        <h3 className="text-lg font-semibold text-white">交易纪律检查器</h3>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
        <Input label="股票代码" value={code} onChange={(e) => setCode(e.target.value)} placeholder="如 000001" disabled={checking} />
        <Input label="乖离率MA5(%)" value={biasMa5} onChange={(e) => setBiasMa5(e.target.value)} placeholder="如 3.2" disabled={checking} />
        <Input label="量比" value={volumeRatio} onChange={(e) => setVolumeRatio(e.target.value)} placeholder="如 1.5" disabled={checking} />
        <Select
          label="均线排列"
          value={maAlignment}
          onChange={(v) => setMaAlignment(v)}
          options={[
            { value: '', label: '-- 选择 --' },
            { value: '多头排列', label: '多头排列' },
            { value: '空头排列', label: '空头排列' },
            { value: '纠缠', label: '纠缠' },
          ]}
          disabled={checking}
        />
        <Input label="90%筹码集中度(%)" value={concentration90} onChange={(e) => setConcentration90(e.target.value)} placeholder="如 30" disabled={checking} />
        <Input label="获利比例(%)" value={profitRatio} onChange={(e) => setProfitRatio(e.target.value)} placeholder="如 60" disabled={checking} />
      </div>

      <Button onClick={handleCheck} disabled={!code || checking} className="w-full" variant="primary">
        {checking ? (
          <><RefreshCw className="w-4 h-4 mr-2 animate-spin" /> 检查中...</>
        ) : (
          <><Play className="w-4 h-4 mr-2" /> 执行纪律检查</>
        )}
      </Button>

      {/* 结果 */}
      {hasChecked && result && (
        <div className={cn(
          'mt-4 p-4 rounded-xl border transition-all duration-300',
          result.passed
            ? 'border-emerald-500/20 bg-emerald-500/5'
            : 'border-red-500/20 bg-red-500/5'
        )}>
          <div className="flex items-center gap-2 mb-3">
            {result.passed ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            ) : (
              <XCircle className="w-5 h-5 text-red-400" />
            )}
            <span className={cn('font-semibold', result.passed ? 'text-emerald-400' : 'text-red-400')}>
              {result.passed ? '✅ 全部纪律规则通过' : `❌ ${result.violations.length} 项违规`}
            </span>
          </div>

          {result.violations.length > 0 && (
            <ul className="space-y-1.5 mb-3">
              {result.violations.map((v, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-red-300/80">
                  <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-red-400" />
                  {v}
                </li>
              ))}
            </ul>
          )}

          {Object.keys(result.rules).length > 0 && (
            <Collapsible title="查看纪律规则详情" className="mt-2">
              <div className="grid grid-cols-2 gap-2 mt-2">
                {Object.entries(result.rules).map(([key, val]) => (
                  <div key={key} className="flex justify-between text-xs py-1 px-2 rounded bg-gray-800/50">
                    <span className="text-gray-400">{key}</span>
                    <span className="text-gray-200 font-mono">{val}</span>
                  </div>
                ))}
              </div>
            </Collapsible>
          )}
        </div>
      )}
    </Card>
  );
};

// ── 信号过滤器（交互式）─────────────────────────────────────────────────────

const SignalFilter: React.FC = () => {
  const [code, setCode] = useState('');
  const [source, setSource] = useState('analysis');
  const [sentimentScore, setSentimentScore] = useState('');
  const [biasMa5, setBiasMa5] = useState('');
  const [volRatio, setVolRatio] = useState('');
  const [result, setResult] = useState<SignalFilterResponse | null>(null);
  const [filtering, setFiltering] = useState(false);
  const [hasFiltered, setHasFiltered] = useState(false);

  const handleFilter = useCallback(async () => {
    if (!code || !sentimentScore) return;
    setFiltering(true);
    try {
      const res = await filterSignal({
        code,
        source,
        sentiment_score: parseFloat(sentimentScore),
        bias_ma5: biasMa5 ? parseFloat(biasMa5) : undefined,
        volume_ratio: volRatio ? parseFloat(volRatio) : undefined,
      });
      setResult(res);
      setHasFiltered(true);
    } catch {
      setResult({ filtered: true, reasons: ['网络请求失败，默认过滤'], source_weight: 0 });
      setHasFiltered(true);
    } finally {
      setFiltering(false);
    }
  }, [code, source, sentimentScore, biasMa5, volRatio]);

  return (
    <Card variant="glass" padding="lg" className="h-full">
      <div className="flex items-center gap-2 mb-5">
        <Filter className="w-5 h-5 text-purple-400" />
        <h3 className="text-lg font-semibold text-white">信号过滤器</h3>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
        <Input label="股票代码" value={code} onChange={(e) => setCode(e.target.value)} placeholder="如 000001" disabled={filtering} className="sm:col-span-full" />
        <Select
          label="来源"
          value={source}
          onChange={(v) => setSource(v)}
          options={[
            { value: 'analysis', label: '常规分析' },
            { value: 'deep_analysis', label: '深度分析' },
            { value: 'seal_plate', label: '打板' },
            { value: 'comprehensive', label: '综合推荐' },
          ]}
          disabled={filtering}
        />
        <Input label="情绪评分(0-100)" value={sentimentScore} onChange={(e) => setSentimentScore(e.target.value)} placeholder="如 65" disabled={filtering} />
        <Input label="乖离率MA5(%)" value={biasMa5} onChange={(e) => setBiasMa5(e.target.value)} placeholder="如 2.5" disabled={filtering} />
        <Input label="量比" value={volRatio} onChange={(e) => setVolRatio(e.target.value)} placeholder="如 2.0" disabled={filtering} />
      </div>

      <Button onClick={handleFilter} disabled={!code || !sentimentScore || filtering} className="w-full" variant="secondary">
        {filtering ? (
          <><RefreshCw className="w-4 h-4 mr-2 animate-spin" /> 过滤中...</>
        ) : (
          <><Search className="w-4 h-4 mr-2" /> 信号过滤检查</>
        )}
      </Button>

      {hasFiltered && result && (
        <div className={cn(
          'mt-4 p-4 rounded-xl border transition-all duration-300',
          result.filtered
            ? 'border-red-500/20 bg-red-500/5'
            : 'border-emerald-500/20 bg-emerald-500/5'
        )}>
          <div className="flex items-center gap-2 mb-3">
            {result.filtered ? (
              <XCircle className="w-5 h-5 text-red-400" />
            ) : (
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            )}
            <span className={cn('font-semibold', result.filtered ? 'text-red-400' : 'text-emerald-400')}>
              {result.filtered ? `🚫 信号被过滤 (${result.reasons.length} 条原因)` : '✅ 信号通过过滤'}
            </span>
          </div>

          {result.reasons.length > 0 && (
            <ul className="space-y-1 mb-3">
              {result.reasons.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-red-300/80">
                  <span className="text-red-400 mt-0.5">•</span>
                  {r}
                </li>
              ))}
            </ul>
          )}

          <div className="flex items-center gap-2 text-sm text-gray-400">
            <span>当前来源权重:</span>
            <span className={cn('font-mono font-bold', result.source_weight >= 1.0 ? 'text-emerald-400' : 'text-amber-400')}>
              ×{result.source_weight.toFixed(2)}
            </span>
          </div>
        </div>
      )}
    </Card>
  );
};

// ── 骨架屏 ──────────────────────────────────────────────────────────────────

const DashboardSkeleton: React.FC = () => (
  <div className="p-6 max-w-7xl mx-auto space-y-6">
    <Skeleton variant="rectangular" height={80} className="rounded-2xl" />
    <Skeleton variant="rectangular" height={200} className="rounded-2xl" />
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Skeleton variant="rectangular" height={160} className="rounded-2xl" />
      <Skeleton variant="rectangular" height={160} className="rounded-2xl" />
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <Skeleton variant="rectangular" height={200} className="rounded-2xl" />
      <Skeleton variant="rectangular" height={200} className="rounded-2xl" />
    </div>
  </div>
);

// ── 主页面 ──────────────────────────────────────────────────────────────────

const StrategyOptimizerPage: React.FC = () => {
  const [report, setReport] = useState<OptimizationReport | null>(null);
  const [weights, setWeights] = useState<SourceWeightItem[]>([]);
  const [stopParams, setStopParams] = useState<StopParams | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'tools'>('dashboard');

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [reportData, weightsData, stopData] = await Promise.all([
        getOptimizationReport(),
        getSourceWeights(),
        getOptimizedStopParams(),
      ]);
      setReport(reportData);
      setWeights(weightsData);
      setStopParams(stopData);
      setLastFetched(new Date());
    } catch (e: unknown) {
      const apiErr = e as { response?: { data?: { detail?: string } }; message?: string };
      const msg = apiErr.response?.data?.detail || apiErr.message || '获取策略优化数据失败';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // 健康度等级翻译
  const healthLevelLabel = useMemo(() => {
    if (!report) return '';
    const map: Record<string, string> = { excellent: '优秀', good: '良好', fair: '一般', poor: '较差' };
    return map[report.health_level] || report.health_level;
  }, [report]);

  // ── 加载态 ──
  if (loading) return <DashboardSkeleton />;

  // ── 错误态 ──
  if (error && !report) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <EmptyState
          title="数据加载失败"
          description={error}
          icon={<AlertTriangle className="w-12 h-12 text-red-400" />}
          action={
            <Button onClick={fetchData} variant="primary" size="sm">
              <RefreshCw className="w-4 h-4 mr-2" />
              重试
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="p-3 sm:p-6 max-w-7xl mx-auto space-y-6 animate-slide-in-right">
      {/* ── 页头 ── */}
      <PageHeader
        eyebrow="策略优化"
        title="策略优化中心"
        description="基于回测与推荐追踪数据的自适应策略优化、信号过滤与交易纪律"
        actions={
          <div className="flex items-center gap-3">
            {report?.error && (
              <InlineAlert variant="warning" message={report.error} className="text-sm py-1 px-3" />
            )}
            {lastFetched && (
              <span className="text-xs text-gray-500 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {lastFetched.toLocaleTimeString()}
              </span>
            )}
            <Button onClick={fetchData} variant="ghost" size="sm" disabled={loading}>
              <RefreshCw className={cn('w-4 h-4 mr-1.5', loading && 'animate-spin')} />
              刷新
            </Button>
          </div>
        }
        className="mb-6"
      />

      {/* ── Tab 切换 ── */}
      <div className="flex gap-1 bg-gray-800/40 rounded-xl p-1 overflow-x-auto">
        <button
          onClick={() => setActiveTab('dashboard')}
          className={cn(
            'px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 flex items-center gap-2 whitespace-nowrap',
            activeTab === 'dashboard'
              ? 'bg-cyan-500/20 text-cyan-300 shadow-sm'
              : 'text-gray-400 hover:text-gray-200'
          )}
        >
          <BarChart3 className="w-4 h-4 shrink-0" />
          策略仪表盘
        </button>
        <button
          onClick={() => setActiveTab('tools')}
          className={cn(
            'px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 flex items-center gap-2 whitespace-nowrap',
            activeTab === 'tools'
              ? 'bg-cyan-500/20 text-cyan-300 shadow-sm'
              : 'text-gray-400 hover:text-gray-200'
          )}
        >
          <SlidersHorizontal className="w-4 h-4 shrink-0" />
          交互工具
        </button>
      </div>

      {/* ── Dashboard Tab ── */}
      {activeTab === 'dashboard' && report && (
        <>
          {/* 健康度评分 + 关键指标 */}
          <Card variant="glass" padding="lg">
            <div className="flex flex-col md:flex-row items-center gap-8">
              {/* 健康度仪表 */}
              <div className="flex-shrink-0">
                <HealthGauge score={report.health_score} level={healthLevelLabel} />
              </div>

              {/* 关键指标 */}
              <div className="flex-1 grid grid-cols-2 lg:grid-cols-3 gap-3">
                <StatCard
                  label="胜率"
                  value={`${report.key_metrics.win_rate}%`}
                  tone={report.key_metrics.win_rate >= 50 ? 'success' : 'danger'}
                  icon={<Target className="w-4 h-4" />}
                />
                <StatCard
                  label="盈亏比"
                  value={report.key_metrics.profit_factor}
                  tone={report.key_metrics.profit_factor >= 1.5 ? 'success' : 'warning'}
                  icon={<DollarSign className="w-4 h-4" />}
                />
                <StatCard
                  label="方向准确率"
                  value={`${report.key_metrics.direction_accuracy}%`}
                  tone="primary"
                  icon={<Activity className="w-4 h-4" />}
                />
                <StatCard
                  label="总推荐数"
                  value={report.key_metrics.total_records}
                  tone="default"
                  icon={<Target className="w-4 h-4" />}
                />
                <StatCard
                  label="已平仓"
                  value={report.key_metrics.closed_count}
                  tone="default"
                  icon={<Shield className="w-4 h-4" />}
                />
                <StatCard
                  label="高风险持仓"
                  value={report.high_risk_positions.length}
                  tone={report.high_risk_positions.length > 0 ? 'danger' : 'success'}
                  icon={<AlertTriangle className="w-4 h-4" />}
                  hint={report.high_risk_positions.length > 0 ? '需关注' : undefined}
                />
              </div>
            </div>
          </Card>

          {/* 问题 & 建议 */}
          {(report.issues.length > 0 || report.suggestions.length > 0) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {report.issues.length > 0 && (
                <Card variant="glass" padding="lg">
                  <div className="flex items-center gap-2 mb-4">
                    <AlertTriangle className="w-5 h-5 text-red-400" />
                    <h3 className="text-lg font-semibold text-red-300">识别的问题</h3>
                    <Badge variant="danger" size="sm">{report.issues.length}</Badge>
                  </div>
                  <ul className="space-y-3">
                    {report.issues.map((issue, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-3 text-sm text-red-200/80 p-3 rounded-lg bg-red-500/5 border border-red-500/10"
                      >
                        <span className="text-red-400 font-mono text-xs mt-0.5 flex-shrink-0">[{i + 1}]</span>
                        {issue}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {report.suggestions.length > 0 && (
                <Card variant="glass" padding="lg">
                  <div className="flex items-center gap-2 mb-4">
                    <Zap className="w-5 h-5 text-emerald-400" />
                    <h3 className="text-lg font-semibold text-emerald-300">优化建议</h3>
                    <Badge variant="success" size="sm">{report.suggestions.length}</Badge>
                  </div>
                  <ul className="space-y-3">
                    {report.suggestions.map((s, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-3 text-sm text-emerald-200/80 p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/10"
                      >
                        <span className="text-emerald-400 font-mono text-xs mt-0.5 flex-shrink-0">[{i + 1}]</span>
                        {s}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}
            </div>
          )}

          {/* 来源权重 + 止损参数 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 来源权重 */}
            <Card variant="glass" padding="lg">
              <div className="flex items-center gap-2 mb-4">
                <LineChart className="w-5 h-5 text-cyan-400" />
                <h3 className="text-lg font-semibold text-white">来源权重（动态）</h3>
              </div>
              {weights.length > 0 ? (
                <div className="space-y-0.5">
                  {weights.map((w, idx) => (
                    <SourceWeightRow key={w.source} item={w} rank={idx + 1} />
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-sm py-4 text-center">暂无来源权重数据</p>
              )}
              <p className="text-[11px] text-gray-600 mt-4 leading-relaxed">
                权重基于各来源历史胜率自动计算。
                <span className="text-amber-500/70">样本量 &lt; 5 笔</span> 时有额外折扣，
                胜率 ≥ 60% 权重放大至 1.5×。
              </p>
            </Card>

            {/* 止损/止盈参数 */}
            <Card variant="glass" padding="lg">
              <div className="flex items-center gap-2 mb-4">
                <Shield className="w-5 h-5 text-red-400" />
                <h3 className="text-lg font-semibold text-white">优化止损/止盈参数</h3>
              </div>
              {stopParams ? (
                <div className="grid grid-cols-2 gap-3">
                  <StopParamCard
                    label="硬止损"
                    value={`${stopParams.hard_stop_pct}%`}
                    icon={<XCircle className="w-4 h-4 text-red-400" />}
                    tone="danger"
                  />
                  <StopParamCard
                    label="移动止损"
                    value={`${stopParams.trailing_stop_pct}%`}
                    icon={<AlertTriangle className="w-4 h-4 text-amber-400" />}
                    tone="warning"
                  />
                  <StopParamCard
                    label="止盈目标"
                    value={`+${stopParams.take_profit_target_pct}%`}
                    icon={<CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                    tone="success"
                  />
                  <StopParamCard
                    label="时间止损"
                    value={`${stopParams.time_stop_days} 天`}
                    icon={<Clock className="w-4 h-4 text-cyan-400" />}
                    tone="info"
                  />
                </div>
              ) : (
                <p className="text-gray-500 text-sm py-4 text-center">暂无优化参数</p>
              )}
              <p className="text-[11px] text-gray-600 mt-4 leading-relaxed">
                基于回测数据自适应调整。
                <span className="text-emerald-500/70">盈亏比 &gt; 2.5</span> 时可放宽止损，
                <span className="text-red-400/70">最大亏损超标</span> 时收紧。
              </p>
            </Card>
          </div>

          {/* 高风险持仓预警 */}
          {report.high_risk_positions.length > 0 && (
            <Card variant="glass" padding="lg">
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="w-5 h-5 text-red-400" />
                <h3 className="text-lg font-semibold text-red-300">高风险持仓预警</h3>
                <Badge variant="danger" size="sm" glow>{report.high_risk_positions.length}</Badge>
                <span className="text-xs text-red-400/60 ml-2">偏差 &lt; -3% 自动识别</span>
              </div>
              <RiskTable positions={report.high_risk_positions} />
            </Card>
          )}

          {/* 空数据：无高风险持仓、无问题、无建议 */}
          {report.high_risk_positions.length === 0 && report.issues.length === 0 && report.suggestions.length === 0 && (
            <Card variant="glass" padding="lg">
              <div className="text-center py-6">
                <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
                <p className="text-emerald-300 font-medium">策略运行良好，暂无风险信号</p>
                <p className="text-gray-500 text-sm mt-1">各指标均在健康范围内，继续保持</p>
              </div>
            </Card>
          )}
        </>
      )}

      {/* ── Tools Tab ── */}
      {activeTab === 'tools' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-slide-in-right">
          <DisciplineChecker />
          <SignalFilter />
        </div>
      )}
    </div>
  );
};

export default StrategyOptimizerPage;
