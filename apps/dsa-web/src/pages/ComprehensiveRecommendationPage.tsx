import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  AlertTriangle, Shield, Target,
  BarChart3, RefreshCw, Calendar, Brain, Zap, Activity,
  Layers, Gauge, ArrowRight, Info, CheckCircle,
  ChevronDown, ChevronUp, Trash2,
} from 'lucide-react';
import { Button } from '@/components/common/Button';
import { StockNameDisplay } from '@/components/common/StockNameDisplay';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Loading } from '@/components/common/Loading';
import { EmptyState } from '@/components/common/EmptyState';
import { sealPlateApi } from '@/api/sealPlate';
import type {
  ComprehensiveRecommendationResponse,
  WinRateBriefResponse,
  BuySellAnalysis,
  TermAdvice,
  IndividualStockRisk,
  FactorCorrelation,
  StressTestResult,
} from '@/types/sealPlate';

// ============ 工具函数 ============

/**
 * 前端数据完整性校验
 * 在渲染前验证数据完整性，修复常见的导致页面崩溃的问题
 */
interface DataValidationResult {
  valid: boolean;
  fixedFields: string[];
  warnings: string[];
}

function validatePageData(data: ComprehensiveRecommendationResponse | null): {
  validated: ComprehensiveRecommendationResponse | null;
  validation: DataValidationResult;
} {
  const result: DataValidationResult = { valid: true, fixedFields: [], warnings: [] };

  if (!data) {
    return { validated: null, validation: { ...result, valid: false, warnings: ['data_is_null'] } };
  }

  // 深拷贝避免修改原数据
  const v = { ...data } as ComprehensiveRecommendationResponse & Record<string, unknown>;

  // 必填数组字段确保为数组
  const arrayFields = [
    'buySellAnalyses', 'termAdvices', 'individualStockRisks',
    'factorCorrelations', 'stressTestResults',
    'strategyAdjustments', 'adjustmentReasons',
  ];
  for (const field of arrayFields) {
    if (!Array.isArray((v as Record<string, unknown>)[field])) {
      (v as Record<string, unknown>)[field] = [];
      result.fixedFields.push(field);
      result.warnings.push(`${field}_was_not_array`);
    }
  }

  // 数值字段范围校验与修复
  if (typeof v.sentimentIndex !== 'number' || Number.isNaN(v.sentimentIndex)) {
    v.sentimentIndex = 50;
    result.fixedFields.push('sentimentIndex');
  }
  if (typeof v.marketHeatScore !== 'number' || Number.isNaN(v.marketHeatScore)) {
    v.marketHeatScore = 50;
    result.fixedFields.push('marketHeatScore');
  }
  if (typeof v.totalLimitUp !== 'number' || Number.isNaN(v.totalLimitUp)) {
    v.totalLimitUp = 0;
    result.fixedFields.push('totalLimitUp');
  }

  // 动态仓位数据校验
  if (v.dynamicPosition) {
    const dp = v.dynamicPosition;
    if (!Array.isArray(dp.stockWeights)) {
      dp.stockWeights = [];
      result.fixedFields.push('dynamicPosition.stockWeights');
    }
    // 检仓仓位与现金比例逻辑一致性
    if (typeof dp.targetPositionPct === 'number' && typeof dp.cashReservePct === 'number') {
      if (Math.abs(dp.targetPositionPct + dp.cashReservePct - 100) > 1) {
        dp.cashReservePct = 100 - dp.targetPositionPct;
        result.fixedFields.push('dynamicPosition.cashReservePct');
        result.warnings.push('position_cash_mismatch_fixed');
      }
    }
  }

  result.valid = result.warnings.filter(w => w.includes('null')).length === 0;

  return { validated: v as ComprehensiveRecommendationResponse, validation: result };
}

function riskColor(level: string): string {
  switch (level) {
    case '低风险': case 'low': return 'bg-emerald-100 text-emerald-700 border-emerald-200';
    case '中风险': case 'medium': return 'bg-amber-100 text-amber-700 border-amber-200';
    case '高风险': case 'high': return 'bg-rose-100 text-rose-700 border-rose-200';
    case '极高风险': case 'critical': return 'bg-red-100 text-red-700 border-red-200';
    default: return 'bg-slate-100 text-slate-600 border-slate-200';
  }
}

function sentimentEmoji(phase: string): string {
  switch (phase) {
    case '冰点期': return '🥶';
    case '启动期': return '🌱';
    case '发酵期': return '🔥';
    case '高潮期': return '🚀';
    case '退潮期': return '📉';
    default: return '➖';
  }
}

function confidenceBadge(confidence: string) {
  switch (confidence) {
    case '高': return { variant: 'success' as const, label: '🟢 高' };
    case '中': return { variant: 'warning' as const, label: '🟡 中' };
    case '低': return { variant: 'danger' as const, label: '🔴 低' };
    default: return { variant: 'default' as const, label: confidence };
  }
}

function circuitColor(level: string): string {
  switch (level) {
    case 'none': return 'text-emerald-500';
    case 'yellow': return 'text-amber-500';
    case 'red': return 'text-rose-500';
    case 'black': return 'text-red-700';
    default: return 'text-slate-400';
  }
}

function circuitLabel(level: string): string {
  switch (level) {
    case 'none': return '无熔断';
    case 'yellow': return '黄色预警';
    case 'red': return '红色熔断';
    case 'black': return '黑色熔断';
    default: return level || '--';
  }
}

// ============ 子组件 ============

/** 股票名称高亮组件 */
// StockNameDisplay is imported from common components

/** 进度条组件 */
function ProgressBar({ value, max = 100, color = 'teal', label = '' }: { value: number; max?: number; color?: string; label?: string }) {
  const pct = Math.min(Math.round((value / max) * 100), 100);
  const colorMap: Record<string, string> = {
    teal: 'bg-teal-400',
    emerald: 'bg-emerald-400',
    amber: 'bg-amber-400',
    rose: 'bg-rose-400',
    indigo: 'bg-indigo-400',
    sky: 'bg-sky-400',
    orange: 'bg-orange-400',
    slate: 'bg-slate-400',
  };

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${colorMap[color] || 'bg-slate-400'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {label && <span className="text-xs text-slate-500 font-mono min-w-[3rem] text-right">{label}</span>}
    </div>
  );
}

/** 可折叠面板 */
function CollapsibleSection({ title, icon, defaultOpen = true, children }: {
  title: string;
  icon: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-5 py-3.5 bg-slate-50 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
      >
        <span className="text-teal-500">{icon}</span>
        <span className="font-semibold text-slate-700 dark:text-slate-200 text-sm flex-1 text-left">{title}</span>
        {open ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
      </button>
      {open && <div className="p-5">{children}</div>}
    </div>
  );
}

// ============ 主页面 ============

export default function ComprehensiveRecommendationPage() {
  const [data, setData] = useState<ComprehensiveRecommendationResponse | null>(null);
  const [winBrief, setWinBrief] = useState<WinRateBriefResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState('');

  // 移除标的状态管理
  const [removingCodes, setRemovingCodes] = useState<Set<string>>(new Set());
  const [removedCodes, setRemovedCodes] = useState<Set<string>>(new Set());
  const [validationResult, setValidationResult] = useState<DataValidationResult | null>(null);

  const fetchData = useCallback(async (date?: string) => {
    setLoading(true);
    setError(null);
    try {
      const comprehensive = await sealPlateApi.getComprehensiveRecommendations(date);
      setData(comprehensive);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '获取综合推荐数据失败';
      setError(msg);
      setLoading(false);
      return;
    }

    // 胜率简报为非关键数据，失败不影响主页面
    try {
      const brief = await sealPlateApi.getWinRateBrief();
      setWinBrief(brief);
    } catch (err: unknown) {
      console.warn('胜率简报加载失败（非关键）:', err);
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // 数据校验（使用 useMemo 避免不必要的重新计算）
  const { validated: validData, validation } = useMemo(
    () => validatePageData(data),
    [data]
  );

  // 仅在新数据到达且有问题时展示校验结果，避免持续闪烁
  useEffect(() => {
    if (validation && (validation.warnings.length > 0 || validation.fixedFields.length > 0)) {
      setValidationResult(validation);
    } else {
      setValidationResult(null);  // 数据正常时清除提醒
    }
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  /** 从仓位管理中移除标的 */
  const handleRemoveStock = async (code: string) => {
    setRemovingCodes(prev => new Set(prev).add(code));
    try {
      await sealPlateApi.removePositionStock(code);
      setRemovedCodes(prev => new Set(prev).add(code));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '移除失败';
      setError(msg);
    } finally {
      setRemovingCodes(prev => {
        const next = new Set(prev);
        next.delete(code);
        return next;
      });
    }
  };

  const formatDate = (d: string) => {
    if (!d || d.length !== 8) return d;
    return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[70vh]">
        <Loading label="正在生成综合推荐分析..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Card className="p-8 text-center">
          <AlertTriangle className="w-12 h-12 text-rose-400 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-slate-700 mb-2">数据加载失败</h3>
          <p className="text-slate-500 mb-4">{error}</p>
          <div className="flex items-center justify-center gap-3">
            <Calendar className="w-4 h-4 text-slate-400" />
            <input
              type="date"
              value={selectedDate ? formatDate(selectedDate) : ''}
              onChange={(e) => {
                const d = e.target.value.replace(/-/g, '');
                setSelectedDate(d);
              }}
              max={new Date().toISOString().split('T')[0]}
              className="px-3 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg text-sm"
            />
            <Button onClick={() => fetchData(selectedDate)} variant="primary">
              <RefreshCw className="w-4 h-4 mr-2" /> 重新加载
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  if (!validData) {
    return (
      <EmptyState
        icon={<BarChart3 className="w-12 h-12" />}
        title="暂无数据"
        description="请确保今日已完成打板分析后重试"
      />
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* ============ 数据完整性提醒 ============ */}
      {validationResult && (validationResult.warnings.length > 0 || validationResult.fixedFields.length > 0) && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 rounded-xl text-sm">
          <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-amber-700 dark:text-amber-400 mb-1">数据完整性提醒</p>
            {validationResult.fixedFields.length > 0 && (
              <p className="text-amber-600 dark:text-amber-300">
                已自动修复 {validationResult.fixedFields.length} 个字段
              </p>
            )}
            {validationResult.warnings.filter(w => w !== 'data_is_null').map((w, i) => (
              <p key={i} className="text-amber-500 dark:text-amber-400 text-xs mt-0.5">• {w}</p>
            ))}
            <button
              onClick={() => setValidationResult(null)}
              className="mt-2 text-xs text-amber-600 underline hover:text-amber-800"
            >
              关闭提醒
            </button>
          </div>
        </div>
      )}

      {/* ============ Header ============ */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-teal-100 dark:bg-teal-900/30 rounded-xl">
            <Brain className="w-6 h-6 text-teal-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">综合推荐系统</h1>
            <p className="text-sm text-slate-500">
              {validData.label} · {formatDate(validData.date)} · 多维度智能分析
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Calendar className="w-4 h-4 text-slate-400" />
          <input
            type="date"
            value={(selectedDate || validData.date)
              ? formatDate(selectedDate || validData.date)
              : ''}
            onChange={(e) => {
              const d = e.target.value.replace(/-/g, '');
              setSelectedDate(d);
              if (d) fetchData(d);
            }}
            max={new Date().toISOString().split('T')[0]}
            className="px-3 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-lg text-sm"
          />
          <Button onClick={() => fetchData(selectedDate)} disabled={loading} variant="outline">
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} /> 刷新
          </Button>
        </div>
      </div>

      {/* ============ 情绪 & 热度 概览 ============ */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <Card className="p-4 text-center">
          <p className="text-xs text-slate-400 mb-1">情绪指数</p>
          <p className="text-2xl font-bold text-teal-600">{validData.sentimentIndex}</p>
          <p className="text-xs text-slate-500 mt-1">{sentimentEmoji(validData.sentimentPhase)} {validData.sentimentPhase}</p>
        </Card>
        <Card className="p-4 text-center">
          <p className="text-xs text-slate-400 mb-1">市场热度</p>
          <p className="text-2xl font-bold text-amber-600">{validData.marketHeatScore}</p>
          <div className="mt-1"><ProgressBar value={validData.marketHeatScore} color="amber" /></div>
        </Card>
        <Card className="p-4 text-center">
          <p className="text-xs text-slate-400 mb-1">涨停数量</p>
          <p className="text-2xl font-bold text-primary">{validData.totalLimitUp}</p>
          <p className="text-xs text-slate-500 mt-1">只</p>
        </Card>
        <Card className="p-4 text-center">
          <p className="text-xs text-slate-400 mb-1">资金情绪</p>
          <p className="text-xl font-bold text-emerald-600">{validData.fundSentiment}</p>
          <p className="text-xs text-slate-500 mt-1">
            {validData.fundSentiment.includes('乐观') ? '🟢' : validData.fundSentiment.includes('谨慎') ? '🟡' : '➖'}
          </p>
        </Card>
        {winBrief && (
          <>
            <Card className="p-4 text-center">
              <p className="text-xs text-slate-400 mb-1">总胜率</p>
              <p className={`text-2xl font-bold ${winBrief.winRate >= 50 ? 'text-emerald-600' : 'text-rose-600'}`}>
                {winBrief.winRate}%
              </p>
              <p className="text-xs text-slate-500 mt-1">{winBrief.won}赢/{winBrief.lost}输</p>
            </Card>
            <Card className="p-4 text-center">
              <p className="text-xs text-slate-400 mb-1">近10笔/均收益</p>
              <p className="text-2xl font-bold text-primary">{winBrief.rolling10}%</p>
              <p className="text-xs text-slate-500 mt-1">{winBrief.avgReturn > 0 ? '+' : ''}{winBrief.avgReturn}%</p>
            </Card>
          </>
        )}
      </div>

      {/* 策略调整 */}
      {validData.strategyAdjustments.length > 0 && (
        <Card className="border-indigo-200 bg-indigo-50/50 dark:bg-indigo-900/10">
          <div className="flex items-center gap-2 text-indigo-600 mb-3">
            <Brain className="w-5 h-5" />
            <span className="font-semibold">策略自适应调整</span>
          </div>
          <div className="space-y-1.5">
            {validData.strategyAdjustments.map((adj, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-indigo-700 dark:text-indigo-300">
                <ArrowRight className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                <span>{adj}</span>
              </div>
            ))}
            {validData.adjustmentReasons.map((reason, i) => (
              <div key={`r-${i}`} className="flex items-start gap-2 text-xs text-indigo-500 dark:text-indigo-400 ml-5">
                <Info className="w-3 h-3 mt-0.5 flex-shrink-0" />
                <span>{reason}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ============ 1. 买卖点位与意愿分析 ============ */}
      <CollapsibleSection title="1. 买卖点位与意愿分析" icon={<Activity className="w-5 h-5" />}>
        {validData.buySellAnalyses.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-4">暂无买卖分析数据</p>
        ) : (
          <div className="space-y-4">
            {validData.buySellAnalyses.map((item: BuySellAnalysis) => (
              <Card key={item.code} className="ring-1 ring-teal-400">
                <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                  {/* 左侧：股票信息 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-3">
                      <Target className="w-4 h-4 text-teal-500" />
                      <StockNameDisplay name={item.name} code={item.code} />
                    </div>

                    {/* 买卖意愿 */}
                    <div className="grid grid-cols-2 gap-3 mb-4">
                      <div className="p-3 bg-emerald-50 dark:bg-emerald-900/10 rounded-lg">
                        <p className="text-xs text-emerald-500 mb-1">买入意愿</p>
                        <ProgressBar value={item.buyWillingness} color="emerald" label={`${item.buyWillingness}/100`} />
                      </div>
                      <div className="p-3 bg-rose-50 dark:bg-rose-900/10 rounded-lg">
                        <p className="text-xs text-rose-500 mb-1">卖出意愿</p>
                        <ProgressBar value={item.sellWillingness} color="rose" label={`${item.sellWillingness}/100`} />
                      </div>
                    </div>

                    {/* 买卖信号 */}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-xs font-medium text-emerald-600 mb-1">买入信号</p>
                        {item.buySignals.map((s, i) => (
                          <p key={i} className="text-xs text-slate-600 flex items-center gap-1">
                            <span className="text-emerald-400">+</span>{s}
                          </p>
                        ))}
                      </div>
                      <div>
                        <p className="text-xs font-medium text-rose-600 mb-1">卖出信号</p>
                        {item.sellSignals.map((s, i) => (
                          <p key={i} className="text-xs text-slate-600 flex items-center gap-1">
                            <span className="text-rose-400">-</span>{s}
                          </p>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* 右侧：关键价格 */}
                  <div className="lg:w-64 bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 space-y-2 flex-shrink-0">
                    <p className="text-xs font-medium text-slate-500 mb-2">关键价位</p>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-500">买入区间</span>
                      <span className="font-mono text-teal-600">{item.buyRangeLow} - {item.buyRangeHigh}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-500">理想买入</span>
                      <span className="font-mono font-semibold text-teal-700">{item.idealBuyPrice}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-500">止损价</span>
                      <span className="font-mono text-rose-600">{item.stopLossPrice}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-500">短线止盈</span>
                      <span className="font-mono text-emerald-600">{item.takeProfitShort}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-500">长线止盈</span>
                      <span className="font-mono text-emerald-600">{item.takeProfitLong}</span>
                    </div>
                  </div>
                </div>

                {/* 进出策略 */}
                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-700 flex gap-4 text-xs">
                  <div className="flex-1">
                    <span className="text-teal-600 font-medium">进场: </span>
                    <span className="text-slate-600">{item.entryStrategy}</span>
                  </div>
                  <div className="flex-1">
                    <span className="text-rose-600 font-medium">离场: </span>
                    <span className="text-slate-600">{item.exitStrategy}</span>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </CollapsibleSection>

      {/* ============ 2. 短中长期投资建议 ============ */}
      <CollapsibleSection title="2. 短/中/长期投资建议" icon={<Layers className="w-5 h-5" />} defaultOpen={false}>
        {validData.termAdvices.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-4">暂无投资建议</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {validData.termAdvices.map((advice: TermAdvice) => {
              const badge = confidenceBadge(advice.confidence);
              return (
                <Card key={advice.term} className="text-center hover:shadow-lg transition-shadow">
                  <p className="text-xs text-slate-400 mb-2">{advice.label}</p>
                  <div className="text-3xl mb-2">
                    {advice.action.includes('买入') || advice.action.includes('加仓') ? '📈'
                      : advice.action.includes('卖出') || advice.action.includes('减仓') ? '📉'
                      : advice.action.includes('持有') ? '📊' : '➖'}
                  </div>
                  <p className="font-semibold text-slate-700 text-lg mb-2">{advice.action}</p>
                  <div className="flex items-center justify-center gap-2 mb-3">
                    <Badge variant={badge.variant}>{badge.label}</Badge>
                    <span className={`text-xs px-2 py-0.5 rounded border ${riskColor(advice.riskLevel)}`}>
                      {advice.riskLevel}
                    </span>
                  </div>
                  <div className="space-y-1.5 text-sm text-slate-500">
                    <div className="flex justify-between"><span>目标收益</span><span className="text-emerald-600 font-mono">+{advice.targetReturnPct}%</span></div>
                    <div className="flex justify-between"><span>持有周期</span><span className="font-mono">{advice.holdDays}</span></div>
                  </div>
                  <p className="text-xs text-slate-500 mt-3 leading-relaxed">{advice.strategyDesc}</p>
                  {advice.keyLevels.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-700">
                      <p className="text-xs text-slate-400 mb-1">关键位</p>
                      <div className="flex flex-wrap gap-1 justify-center">
                        {advice.keyLevels.map((kl, i) => (
                          <span key={i} className="text-xs px-2 py-0.5 bg-slate-100 dark:bg-slate-700 rounded">{kl}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </CollapsibleSection>

      {/* ============ 3. 板块轮动分析 ============ */}
      {validData.sectorRotation && (
        <CollapsibleSection title="3. 热点资金意愿与板块轮动分析" icon={<Layers className="w-5 h-5" />} defaultOpen={false}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
            {/* 热门板块 */}
            <Card className="ring-1 ring-emerald-400">
              <p className="text-sm font-semibold text-emerald-600 mb-3">🔥 当前热门板块</p>
              <div className="space-y-2">
                {validData.sectorRotation.hotSectors.length === 0 ? (
                  <p className="text-xs text-slate-400">暂无热门板块</p>
                ) : (
                  validData.sectorRotation.hotSectors.map((s, i) => (
                    <div key={i} className="flex items-center justify-between text-sm">
                      <span className="text-slate-700">{s.name}</span>
                      <span className="text-slate-400 text-xs">{s.count}只涨停</span>
                    </div>
                  ))
                )}
              </div>
            </Card>

            {/* 冷却板块 */}
            <Card className="ring-1 ring-amber-400">
              <p className="text-sm font-semibold text-amber-600 mb-3">🌡️ 正在降温</p>
              <div className="space-y-2">
                {validData.sectorRotation.coolingSectors.length === 0 ? (
                  <p className="text-xs text-slate-400">暂无降温板块</p>
                ) : (
                  validData.sectorRotation.coolingSectors.map((s, i) => (
                    <div key={i} className="flex items-center justify-between text-sm">
                      <span className="text-slate-700">{s.name}</span>
                      <span className="text-rose-400 text-xs font-mono">
                        {s.netOutflow ? `-${(s.netOutflow / 10000).toFixed(1)}亿` : s.count ? `${s.count}只` : '--'}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </Card>

            {/* 潜力板块 */}
            <Card className="ring-1 ring-indigo-400">
              <p className="text-sm font-semibold text-indigo-600 mb-3">💡 轮动潜力方向</p>
              <div className="space-y-2">
                {validData.sectorRotation.nextPotentialSectors.length === 0 ? (
                  <p className="text-xs text-slate-400">暂无潜力板块</p>
                ) : (
                  validData.sectorRotation.nextPotentialSectors.map((s, i) => (
                    <div key={i} className="text-sm">
                      <span className="text-slate-700">{s.name}</span>
                      {s.reason && <p className="text-xs text-slate-400 mt-0.5">{s.reason}</p>}
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>

          {/* 资金流向 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-medium text-slate-500 mb-2">游资聚焦</p>
              <div className="flex flex-wrap gap-1.5">
                {validData.sectorRotation.hotMoneyFocus.map((f, i) => (
                  <Badge key={i} variant="warning" className="text-xs">{f}</Badge>
                ))}
              </div>
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500 mb-2">机构聚焦</p>
              <div className="flex flex-wrap gap-1.5">
                {validData.sectorRotation.institutionFocus.map((f, i) => (
                  <Badge key={i} variant="info" className="text-xs">{f}</Badge>
                ))}
              </div>
            </div>
          </div>

          {validData.sectorRotation.suggestions.length > 0 && (
            <div className="mt-4 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
              <p className="text-xs font-medium text-slate-500 mb-2">轮动建议</p>
              {validData.sectorRotation.suggestions.map((s, i) => (
                <p key={i} className="text-sm text-slate-600 flex items-center gap-1">
                  <ArrowRight className="w-3 h-3 text-teal-400" />{s}
                </p>
              ))}
            </div>
          )}
        </CollapsibleSection>
      )}

      {/* ============ 4. 整体风险评估 ============ */}
      {validData.riskAssessment && (
        <CollapsibleSection title="4. 整体风险等级评估" icon={<Shield className="w-5 h-5" />} defaultOpen={false}>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <div className="flex items-center gap-4 mb-4">
                <div className={`text-4xl font-bold ${validData.riskAssessment.overallRiskScore <= 30 ? 'text-emerald-500' : validData.riskAssessment.overallRiskScore <= 60 ? 'text-amber-500' : 'text-rose-500'}`}>
                  {validData.riskAssessment.overallRiskScore}
                </div>
                <div>
                  <p className="text-sm text-slate-400">综合风险评分</p>
                  <span className={`inline-block px-2 py-0.5 rounded text-xs border ${riskColor(validData.riskAssessment.overallRiskLevel)}`}>
                    {validData.riskAssessment.overallRiskLevel}
                  </span>
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-xs text-slate-500 mb-1"><span>市场风险</span><span>{validData.riskAssessment.marketRisk}/100</span></div>
                  <ProgressBar value={validData.riskAssessment.marketRisk} color={validData.riskAssessment.marketRisk > 60 ? 'rose' : 'amber'} />
                </div>
                <div>
                  <div className="flex justify-between text-xs text-slate-500 mb-1"><span>仓位风险</span><span>{validData.riskAssessment.positionRisk}/100</span></div>
                  <ProgressBar value={validData.riskAssessment.positionRisk} color={validData.riskAssessment.positionRisk > 60 ? 'rose' : 'amber'} />
                </div>
                <div>
                  <div className="flex justify-between text-xs text-slate-500 mb-1"><span>板块集中度</span><span>{validData.riskAssessment.sectorConcentrationRisk}/100</span></div>
                  <ProgressBar value={validData.riskAssessment.sectorConcentrationRisk} color={validData.riskAssessment.sectorConcentrationRisk > 50 ? 'rose' : 'teal'} />
                </div>
                <div>
                  <div className="flex justify-between text-xs text-slate-500 mb-1"><span>流动性风险</span><span>{validData.riskAssessment.liquidityRisk}/100</span></div>
                  <ProgressBar value={validData.riskAssessment.liquidityRisk} color={validData.riskAssessment.liquidityRisk > 50 ? 'rose' : 'teal'} />
                </div>
                <div>
                  <div className="flex justify-between text-xs text-slate-500 mb-1"><span>情绪风险</span><span>{validData.riskAssessment.sentimentRisk}/100</span></div>
                  <ProgressBar value={validData.riskAssessment.sentimentRisk} color={validData.riskAssessment.sentimentRisk > 50 ? 'rose' : 'teal'} />
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <p className="text-sm font-medium text-slate-600 mb-2">风险因素</p>
                {validData.riskAssessment.riskFactors.map((f, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm text-slate-600 py-1">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                    {f}
                  </div>
                ))}
              </div>
              <div>
                <p className="text-sm font-medium text-slate-600 mb-2">风险缓解</p>
                {validData.riskAssessment.riskMitigations.map((m, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm text-slate-600 py-1">
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                    {m}
                  </div>
                ))}
              </div>
              <div className="p-3 bg-indigo-50 dark:bg-indigo-900/10 rounded-lg">
                <p className="text-sm text-indigo-600">
                  建议最大仓位: <span className="font-bold text-lg">{validData.riskAssessment.maxRecommendedPosition}%</span>
                </p>
              </div>
            </div>
          </div>
        </CollapsibleSection>
      )}

      {/* ============ 5. 个股风险分析 ============ */}
      <CollapsibleSection title="5. 个股风险剖析" icon={<AlertTriangle className="w-5 h-5" />} defaultOpen={false}>
        {validData.individualStockRisks.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-4">暂无个股风险数据</p>
        ) : (
          <div className="space-y-4">
            {validData.individualStockRisks.map((stock: IndividualStockRisk) => (
              <Card key={stock.code} className={`ring-1 ${stock.riskScore <= 30 ? 'ring-emerald-400' : stock.riskScore <= 60 ? 'ring-amber-400' : 'ring-rose-400'}`}>
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <StockNameDisplay name={stock.name} code={stock.code} />
                    <span className={`text-xs px-2 py-0.5 rounded border ${riskColor(stock.riskLevel)}`}>
                      {stock.riskLevel}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className={`text-lg font-bold ${stock.riskScore <= 30 ? 'text-emerald-500' : stock.riskScore <= 60 ? 'text-amber-500' : 'text-rose-500'}`}>
                      {stock.riskScore}
                    </span>
                    <span className="text-xs text-slate-400">/100</span>
                  </div>
                </div>

                {/* 风险雷达 */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
                  {[
                    { label: '估值', val: stock.valuationRisk },
                    { label: '技术', val: stock.technicalRisk },
                    { label: '资金流', val: stock.fundFlowRisk },
                    { label: '情绪', val: stock.sentimentRisk },
                    { label: '板块', val: stock.sectorRisk },
                    { label: '流动性', val: stock.liquidityRisk },
                    { label: '黑天鹅', val: stock.blackSwanRisk, color: stock.blackSwanRisk > 50 ? 'rose' : 'slate' },
                  ].map((item) => (
                    <div key={item.label} className="text-center">
                      <p className="text-xs text-slate-400 mb-0.5">{item.label}</p>
                      <ProgressBar value={item.val} color={item.color || (item.val > 50 ? 'amber' : 'emerald')} label={`${item.val}`} />
                    </div>
                  ))}
                </div>

                {/* 具体风险项 */}
                {stock.riskItems.length > 0 && (
                  <div className="mb-3">
                    {stock.riskItems.map((ri, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs py-0.5">
                        <span className={ri.level === 'high' ? 'text-rose-500' : ri.level === 'medium' ? 'text-amber-500' : 'text-slate-400'}>
                          {ri.level === 'high' ? '🔴' : ri.level === 'medium' ? '🟡' : '🟢'}
                        </span>
                        <span className="text-slate-600">{ri.type}: {ri.desc}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* 建议 */}
                <div className="flex items-center justify-between text-xs">
                  <div className="flex gap-2 flex-wrap">
                    {stock.suggestions.map((s, i) => (
                      <span key={i} className="px-2 py-0.5 bg-indigo-50 dark:bg-indigo-900/10 text-indigo-600 rounded">{s}</span>
                    ))}
                  </div>
                  <span className="text-slate-400">仓位上限 {stock.positionLimitPct}%</span>
                </div>
              </Card>
            ))}
          </div>
        )}
      </CollapsibleSection>

      {/* ============ 6. 动态仓位管理 ============ */}
      {validData.dynamicPosition && (
        <CollapsibleSection title="6. 动态仓位管理" icon={<Gauge className="w-5 h-5" />} defaultOpen={false}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* 仓位仪表 */}
            <div className="lg:col-span-1">
              <div className="relative w-40 h-40 mx-auto mb-4">
                <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
                  <circle cx="60" cy="60" r="50" fill="none" stroke="currentColor" strokeWidth="8" className="text-slate-100 dark:text-slate-700" />
                  <circle
                    cx="60" cy="60" r="50" fill="none"
                    strokeWidth="8"
                    strokeLinecap="round"
                    className={validData.dynamicPosition.targetPositionPct > 60 ? 'text-rose-400' : validData.dynamicPosition.targetPositionPct > 30 ? 'text-amber-400' : 'text-emerald-400'}
                    strokeDasharray={`${(validData.dynamicPosition.targetPositionPct / 100) * 314} 314`}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-3xl font-bold text-slate-700">{validData.dynamicPosition.targetPositionPct}%</span>
                  <span className="text-xs text-slate-400">目标仓位</span>
                </div>
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-500">当前仓位</span>
                  <span className="font-mono">{validData.dynamicPosition.currentPositionPct}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">最大仓位</span>
                  <span className="font-mono text-rose-500">{validData.dynamicPosition.maxPositionPct}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">现金储备</span>
                  <span className="font-mono text-emerald-500">{validData.dynamicPosition.cashReservePct}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">总资金</span>
                  <span className="font-mono">{(validData.dynamicPosition.totalCapital / 10000).toFixed(1)}万</span>
                </div>
              </div>

              {validData.dynamicPosition.rebalancingNeeded && (
                <div className="mt-4 p-3 bg-amber-50 dark:bg-amber-900/10 rounded-lg text-sm text-amber-700">
                  ⚠️ 需要再平衡: {validData.dynamicPosition.adjustmentReason}
                </div>
              )}
            </div>

            {/* 个股权重 */}
            <div className="lg:col-span-2">
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm font-medium text-slate-600">个股配置权重</p>
                {removedCodes.size > 0 && (
                  <span className="text-xs text-slate-400">
                    已排除 {removedCodes.size} 只（刷新后生效）
                  </span>
                )}
              </div>
              <div className="space-y-3">
                {validData.dynamicPosition.stockWeights
                  .filter((sw: Record<string, unknown>) => !removedCodes.has(String(sw.code || '')))
                  .map((sw: Record<string, unknown>, i: number) => {
                    const weightPct = Number(sw.weightPct || sw.weight || 0);
                    const stockCode = String(sw.code || '');
                    const stockName = String(sw.name || '');
                    const isRemoving = removingCodes.has(stockCode);
                    return (
                  <div key={i} className="bg-slate-50 dark:bg-slate-800/30 rounded-lg p-3 relative group">
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-700">
                          {stockName}
                          <span className="text-xs text-slate-400 font-mono ml-1.5">{stockCode}</span>
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-mono text-teal-600">{weightPct}%</span>
                         <button
                           onClick={() => handleRemoveStock(stockCode)}
                           disabled={isRemoving}
                           className="p-1 rounded text-rose-600 hover:text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-900/10 opacity-0 group-hover:opacity-100 transition-all disabled:opacity-50"
                           title={`移除 ${stockName}`}
                         >
                          <Trash2 className={`w-3.5 h-3.5 ${isRemoving ? 'animate-spin' : ''}`} />
                        </button>
                      </div>
                    </div>
                    <ProgressBar value={weightPct} color={weightPct > 30 ? 'rose' : weightPct > 15 ? 'amber' : 'teal'} />
                    {(sw.suggestion || sw.suggestedPct !== undefined) && (
                      <p className="text-xs text-slate-400 mt-1">
                        {String(sw.suggestion || `建议仓位 ${sw.suggestedPct}%`)}
                      </p>
                    )}
                  </div>
                    );
                  })}
                {validData.dynamicPosition.stockWeights.filter(
                  (sw: Record<string, unknown>) => !removedCodes.has(String(sw.code || ''))
                ).length === 0 && (
                  <p className="text-sm text-slate-400 text-center py-6">所有持仓标的已移除</p>
                )}
              </div>
            </div>
          </div>
        </CollapsibleSection>
      )}

      {/* ============ 7. 因子相关性监控 ============ */}
      <CollapsibleSection title="7. 多因子相关性监控" icon={<Activity className="w-5 h-5" />} defaultOpen={false}>
        {validData.factorCorrelations.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-4">暂无因子监控数据</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {validData.factorCorrelations.map((factor: FactorCorrelation, i: number) => (
              <Card key={i} className="text-center">
                <p className="text-sm font-semibold text-slate-700 mb-2">{factor.factorName}</p>
                <div className="text-2xl font-bold text-primary mb-1">{factor.currentValue.toFixed(2)}</div>
                <div className="space-y-1.5 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Z-Score</span>
                    <span className={`font-mono ${Math.abs(factor.zScore) > 2 ? 'text-rose-500' : 'text-slate-500'}`}>{factor.zScore.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">市场相关性</span>
                    <span className="font-mono text-slate-500">{(factor.correlationWithMarket ?? 0).toFixed(2)}</span>
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-center gap-2">
                  <Badge variant={
                    factor.status === 'normal' ? 'success' :
                    factor.status === 'warning' ? 'warning' :
                    'danger'
                  }>
                    {factor.status === 'normal' ? '正常' :
                     factor.status === 'warning' ? '关注' :
                     factor.status === 'anomaly' ? '异常' : factor.status}
                  </Badge>
                </div>
                {factor.warningMsg && (
                  <p className="text-xs text-amber-600 mt-2">{factor.warningMsg}</p>
                )}
              </Card>
            ))}
          </div>
        )}
      </CollapsibleSection>

      {/* ============ 8. 黑天鹅压力测试 & 熔断 ============ */}
      <CollapsibleSection title="8. 黑天鹅压力测试与熔断机制" icon={<Zap className="w-5 h-5" />} defaultOpen={false}>
        {validData.stressTestResults.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-4">暂无压力测试数据</p>
        ) : (
          <div className="space-y-4">
            {validData.stressTestResults.map((test: StressTestResult, i: number) => (
               <Card key={i} className={`ring-1 ${test.circuitBreakerTriggered ? 'ring-rose-400' : 'ring-emerald-400'}`}>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="font-semibold text-slate-700">{test.scenario}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-sm font-medium ${circuitColor(test.circuitBreakerLevel)}`}>
                        {circuitLabel(test.circuitBreakerLevel)}
                      </span>
                      {test.circuitBreakerTriggered && (
                        <Badge variant="danger" className="text-xs">熔断触发</Badge>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold text-rose-500">-{test.maxDrawdownPct}%</p>
                    <p className="text-xs text-slate-400">最大回撤</p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4 mb-3">
                  <div className="text-center p-2 bg-slate-50 dark:bg-slate-800/30 rounded">
                    <p className="text-xs text-slate-400">组合损失</p>
                    <p className="text-lg font-semibold text-rose-500">-{test.portfolioLossPct}%</p>
                  </div>
                  <div className="text-center p-2 bg-slate-50 dark:bg-slate-800/30 rounded">
                    <p className="text-xs text-slate-400">预估恢复</p>
                    <p className="text-lg font-semibold text-slate-600">{test.recoveryDaysEst}天</p>
                  </div>
                  <div className="text-center p-2 bg-indigo-50 dark:bg-indigo-900/10 rounded">
                    <p className="text-xs text-indigo-400">建议动作</p>
                    <p className="text-sm font-medium text-indigo-600 mt-1">{test.suggestedAction}</p>
                  </div>
                </div>

                {test.impactOnHoldings.length > 0 && (
                  <div>
                    <p className="text-xs text-slate-400 mb-2">持仓影响</p>
                    <div className="space-y-1">
                      {test.impactOnHoldings.map((imp, i) => (
                        <div key={i} className="flex items-center justify-between text-xs bg-slate-50 dark:bg-slate-800/20 rounded px-2 py-1">
                          <span className="text-slate-600"><StockNameDisplay name={imp.name} code={imp.code} codeClassName="text-xs" /></span>
                          <span className="font-mono text-rose-500">-{imp.loss}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </CollapsibleSection>

      {/* ============ 胜率回溯摘要 ============ */}
      {winBrief && (
        <CollapsibleSection title="胜率回溯概览" icon={<BarChart3 className="w-5 h-5" />} defaultOpen={false}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <Card className="p-4 text-center">
              <p className="text-xs text-slate-400">总推荐</p>
              <p className="text-xl font-bold text-slate-700">{winBrief.total}</p>
            </Card>
            <Card className="p-4 text-center">
              <p className="text-xs text-slate-400">已结算</p>
              <p className="text-xl font-bold text-indigo-600">{winBrief.settled}</p>
            </Card>
            <Card className="p-4 text-center">
              <p className="text-xs text-slate-400">胜率</p>
              <p className={`text-xl font-bold ${winBrief.winRate >= 50 ? 'text-emerald-600' : 'text-rose-600'}`}>
                {winBrief.winRate}%
              </p>
              <p className="text-xs text-slate-400 mt-1">趋势: {winBrief.trend === 'improving' ? '📈 上升' : winBrief.trend === 'declining' ? '📉 下降' : '➡️ 稳定'}</p>
            </Card>
            <Card className="p-4 text-center">
              <p className="text-xs text-slate-400">待结算</p>
              <p className="text-xl font-bold text-amber-600">{winBrief.pending}</p>
            </Card>
          </div>

          {Object.keys(winBrief.bySector).length > 0 && (
            <div>
              <p className="text-sm font-medium text-slate-600 mb-3">板块胜率排行</p>
              <div className="space-y-2">
                {Object.entries(winBrief.bySector).map(([sector, sectorData]) => (
                  <div key={sector} className="flex items-center gap-3">
                    <span className="text-sm text-slate-600 w-24 truncate">{sector}</span>
                    <div className="flex-1">
                      <ProgressBar
                        value={sectorData.rate}
                        color={sectorData.rate >= 60 ? 'emerald' : sectorData.rate >= 40 ? 'amber' : 'rose'}
                        label={`${sectorData.rate.toFixed(0)}%`}
                      />
                    </div>
                    <span className="text-xs text-slate-400">{sectorData.won}/{sectorData.total}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CollapsibleSection>
      )}

      {/* Footer */}
      <div className="text-center text-sm text-slate-400">
        综合推荐生成时间: {validData.generatedAt ? new Date(validData.generatedAt).toLocaleString('zh-CN') : '--'}
      </div>
    </div>
  );
}
