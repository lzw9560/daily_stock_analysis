import type React from 'react';
import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import { BarChart3, BookOpen, CheckCircle2, ChevronLeft, ChevronRight, CircleAlert, Clock, Filter, Layers, MessageSquareQuote, Play, PlusCircle, Search, SlidersHorizontal, TrendingUp, Zap } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import {
  alphasiftApi,
  getStrategyNameCn,
  type AlphaSiftCandidate,
  type AlphaSiftScreenResponse,
  type AlphaSiftStrategy,
    type ScreeningRecordDetail,
  type ScreeningRecordItem,
    type ScreeningRunResponse,
} from '../api/alphasift';
import { AppPage, Button, Drawer, InlineAlert, WatchlistButton } from '../components/common';
import FactorPipelineSummaryCard from '../components/factorPipeline/FactorPipelineSummaryCard';
import type { FactorPipelineRecordResponse, FactorPipelineSummary, FactorPipelineTriggerResponse } from '../types/screening';

const toFactorPipelineSummary = (response: FactorPipelineTriggerResponse): FactorPipelineSummary => ({
  status: response.status,
  backend: response.backend ?? undefined,
  factorPipelineEnabled: response.factorPipelineEnabled,
  factorFamily: response.factorFamily ?? undefined,
  training: response.training ?? undefined,
  monitoring: response.monitoring ?? undefined,
  topCandidates: response.candidates ?? undefined,
});

const MARKETS = [{ id: 'cn', label: 'A 股' }];

const formatScore = (score: AlphaSiftCandidate['score']) => {
  if (score == null || Number.isNaN(Number(score))) {
    return '-';
  }
  return Number(score).toFixed(2);
};

const formatNumber = (value: unknown, digits = 2) => {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return '-';
  }
  return Number(value).toFixed(digits);
};

const formatAmount = (value: unknown) => {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return '-';
  }
  const amount = Number(value);
  if (Math.abs(amount) >= 100_000_000) {
    return `${(amount / 100_000_000).toFixed(2)} 亿`;
  }
  if (Math.abs(amount) >= 10_000) {
    return `${(amount / 10_000).toFixed(2)} 万`;
  }
  return amount.toFixed(2);
};

const formatPercent = (value: unknown) => {
  if (value == null || value === '' || Number.isNaN(Number(value))) {
    return '-';
  }
  return `${(Number(value) * 100).toFixed(0)}%`;
};

const getCandidateReason = (item: AlphaSiftCandidate) => {
  if (item.reason) {
    return item.reason;
  }
  const summaries = item.postAnalysisSummaries || {};
  const summary = Object.values(summaries).find((value) => typeof value === 'string' && value.trim());
  if (typeof summary === 'string') {
    return summary;
  }
  return 'AlphaSift 返回候选，但没有给出文字摘要。请查看下方因子、风险和原始字段。';
};

const getSignal = (item: AlphaSiftCandidate) => {
  const rawSignal = item.raw.action ?? item.raw.signal ?? item.raw.recommendation;
  return typeof rawSignal === 'string' && rawSignal.trim() ? rawSignal : '观察';
};



const FACTOR_INTROS = [
  {
    name: 'RSI',
    weight: '技术指标',
    title: '相对强弱指数 (Relative Strength Index)',
    description: '衡量价格变动速度和幅度的动量震荡指标，取值范围 0-100。用于判断股票是否超买或超卖。',
    how_it_works: 'RSI = 100 - 100/(1 + RS)，其中 RS = 平均涨幅周期 / 平均跌幅周期。通常 RSI > 70 视为超买，RSI < 30 视为超卖。',
    signal: { high: '超卖反弹', low: '超买回调' },
  },
  {
    name: 'MACD',
    weight: '技术指标',
    title: '平滑异同移动平均线 (Moving Average Convergence Divergence)',
    description: '通过两条移动平均线的差值来识别趋势变化和动量转换的信号指标。',
    how_it_works: 'MACD线 = EMA(12) - EMA(26)，信号线 = EMA(MACD线, 9)，柱状图 = MACD线 - 信号线。金叉（MACD上穿信号线）为买入信号，死叉反之。',
    signal: { high: '金叉向上', low: '死叉向下' },
  },
  {
    name: '成交量比率',
    weight: '量能指标',
    title: '量价关系 (Volume Ratio)',
    description: '比较当前成交量与历史平均成交量的比值，用于识别资金流向和市场热度。',
    how_it_works: 'VR = N日平均上涨日成交量 / N日平均下跌日成交量 × 100。放量上涨为强势信号，缩量下跌为弱势信号。',
    signal: { high: '放量上涨', low: '缩量下跌' },
  },
  {
    name: '市盈率',
    weight: '估值指标',
    title: '价格盈利比率 (Price-to-Earnings Ratio)',
    description: '衡量股票价格相对于每股收益的倍数，是评估股票估值水平的核心指标。',
    how_it_works: 'PE = 股价 / 每股收益(EPS)。低 PE 通常表示估值较低，但需结合行业特点和增长预期综合判断。',
    signal: { high: '高估值风险', low: '低估值机会' },
  },
  {
    name: '市净率',
    weight: '估值指标',
    title: '价格账面比 (Price-to-Book Ratio)',
    description: '衡量股票价格相对于每股净资产的倍数，适用于评估重资产企业的价值。',
    how_it_works: 'PB = 股价 / 每股净资产。PB < 1 表示股价低于净资产，可能存在低估；PB > 3 通常表示高估。',
    signal: { high: '高估风险', low: '低估机会' },
  },
  {
    name: '换手率',
    weight: '流动性指标',
    title: '股票活跃度 (Turnover Rate)',
    description: '反映股票交易活跃程度和资金流动性的指标，高换手率通常意味着市场关注度高。',
    how_it_works: '换手率 = 成交量 / 流通股本 × 100%。日换手率 > 7% 为活跃，> 15% 为高度活跃，需警惕过热风险。',
    signal: { high: '高度活跃', low: '低流动性' },
  },
  {
    name: '波动率',
    weight: '风险指标',
    title: '价格波动幅度 (Volatility)',
    description: '衡量股票价格变动的剧烈程度，是评估投资风险的重要参考。',
    how_it_works: '通常使用 N 日收益率的标准差来计算。高波动率意味着价格变化大，风险与机会并存。',
    signal: { high: '高风险高收益', low: '低风险低收益' },
  },
  {
    name: '营收增长率',
    weight: '成长指标',
    title: '企业成长性 (Revenue Growth Rate)',
    description: '衡量企业营业收入的增长速度，反映公司的业务扩张能力和市场竞争力。',
    how_it_works: '营收增长率 = (本期营收 - 上期营收) / 上期营收 × 100%。持续增长表明公司业务处于扩张期。',
    signal: { high: '高速增长', low: '增长放缓' },
  },
  {
    name: '净利润率',
    weight: '盈利指标',
    title: '盈利能力 (Net Profit Margin)',
    description: '反映企业将收入转化为利润的能力，是评估经营效率的核心指标。',
    how_it_works: '净利润率 = 净利润 / 营业收入 × 100%。较高的净利润率表明企业具有较强的定价权和成本控制能力。',
    signal: { high: '强盈利', low: '弱盈利' },
  },
  {
    name: '北向资金',
    weight: '资金流向',
    title: '外资流向 (Northbound Fund Flow)',
    description: '追踪通过沪港通、深港通进入 A 股市场的外资动向，被视为"聪明钱"的风向标。',
    how_it_works: '统计个股近期北向资金净流入/流出金额和比例。持续净流入通常被视为积极信号。',
    signal: { high: '外资流入', low: '外资流出' },
  },
  {
    name: '机构持仓',
    weight: '资金流向',
    title: '机构持仓变化 (Institutional Holding Change)',
    description: '监测基金、保险、社保等机构投资者的持仓变动，反映专业资金的看法。',
    how_it_works: '比较最新报告期与上一期机构持仓比例的变化。增持表明机构看好，减持则相反。',
    signal: { high: '机构增持', low: '机构减持' },
  },
  {
    name: '行业景气',
    weight: '行业因子',
    title: '行业景气度 (Industry Prosperity)',
    description: '基于行业政策、供需格局、产业链动态等因素综合评估行业的整体景气水平。',
    how_it_works: '通过行业指数表现、政策利好数量、产业链上下游数据等构建景气度评分。',
    signal: { high: '景气上行', low: '景气下行' },
  },
];

const getFactorEntries = (item: AlphaSiftCandidate) =>
  Object.entries(item.factorScores || {})
    .filter(([, value]) => typeof value === 'number')
    .sort((a, b) => Number(b[1]) - Number(a[1]))
    .slice(0, 6);


const StockScreeningPage: React.FC = () => {
  const navigate = useNavigate();
  const [enabled, setEnabled] = useState(false);
  const [market, setMarket] = useState('cn');
  const [strategy, setStrategy] = useState('dual_low');
  const [strategies, setStrategies] = useState<AlphaSiftStrategy[]>([]);
  const [maxResults, setMaxResults] = useState(3);
  const [candidates, setCandidates] = useState<AlphaSiftCandidate[]>([]);
  const [screenMeta, setScreenMeta] = useState<AlphaSiftScreenResponse | null>(null);
  const [expandedCode, setExpandedCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [enabling, setEnabling] = useState(false);
  const [loadingStrategies, setLoadingStrategies] = useState(false);
  const [error, setError] = useState('');
  const [strategyLoadError, setStrategyLoadError] = useState('');
  const [factorPipelineLoadingRecordId, setFactorPipelineLoadingRecordId] = useState<number | null>(null);
  const [factorPipelineError, setFactorPipelineError] = useState('');
  const [selectedFactorPipeline, setSelectedFactorPipeline] = useState<FactorPipelineSummary | null>(null);
  const [latestFactorPipeline, setLatestFactorPipeline] = useState<FactorPipelineSummary | null>(null);
  // Batch run state
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchResult, setBatchResult] = useState<ScreeningRunResponse | null>(null);
  // History detail state
  const [historyDetail, setHistoryDetail] = useState<ScreeningRecordDetail | null>(null);
  const [historyDetailLoadingRecordId, setHistoryDetailLoadingRecordId] = useState<number | null>(null);
  const [showFactorIntro, setShowFactorIntro] = useState(false);
  const [expandedCodeHistory, setExpandedCodeHistory] = useState<string | null>(null);


  // History records state
  const [records, setRecords] = useState<ScreeningRecordItem[]>([]);
  const [recordsTotal, setRecordsTotal] = useState(0);
  const [recordsPage, setRecordsPage] = useState(0);
  const [recordsLoading, setRecordsLoading] = useState(false);
  const RECORDS_PAGE_SIZE = 10;

  const selectedStrategy = useMemo(() => strategies.find((item) => item.id === strategy), [strategies, strategy]);
  const selectedStrategyTitle = selectedStrategy?.name || selectedStrategy?.title || '自定义策略';
  const selectedStrategyTag = selectedStrategy?.category || selectedStrategy?.tag || selectedStrategy?.tags?.[0] || '自定义';
  const displayedStrategy = selectedStrategy ? selectedStrategyTitle : `自定义策略 (${strategy})`;

  const clearScreeningResults = () => {
    setCandidates([]);
    setScreenMeta(null);
    setExpandedCode(null);
    setLatestFactorPipeline(null);
  };

  const loadRecords = async (page = recordsPage) => {
    setRecordsLoading(true);
    try {
      const result = await alphasiftApi.getRecords({
        limit: RECORDS_PAGE_SIZE,
        offset: page * RECORDS_PAGE_SIZE,
      });
      setRecords(result.records);
      setRecordsTotal(result.total);
      setRecordsPage(page);
    } catch {
      // Silently fail - records are non-critical
    } finally {
      setRecordsLoading(false);
    }
  };

  const loadStrategies = useCallback(async () => {
    setLoadingStrategies(true);
    try {
      setStrategyLoadError('');
      const result = await alphasiftApi.getStrategies();
      const loadedStrategies = result.strategies || [];
      setStrategies(loadedStrategies);
      if (loadedStrategies.length > 0) {
        setStrategy((currentStrategy) =>
          loadedStrategies.some((item) => item.id === currentStrategy) ? currentStrategy : loadedStrategies[0].id,
        );
      }
    } catch (err) {
      setStrategies([]);
      setStrategyLoadError(err instanceof Error ? err.message : 'AlphaSift 策略列表加载失败');
    } finally {
      setLoadingStrategies(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    alphasiftApi
      .getStatus()
      .then((status) => {
        if (!active) {
          return;
        }
        setEnabled(status.enabled);
        if (status.enabled) {
          void loadStrategies();
        }
        // Always load records on mount (may have persisted history)
        void loadRecords(0);
      })
      .catch(() => {
        if (active) {
          setEnabled(false);
        }
      });
    return () => {
      active = false;
    };
  }, [loadStrategies]);

  const handleEnable = async () => {
    setEnabling(true);
    setError('');
    try {
      await alphasiftApi.enable();
      setEnabled(true);
      await loadStrategies();
    } catch (err) {
      try {
        const status = await alphasiftApi.getStatus();
        setEnabled(status.enabled);
      } catch {
        setEnabled(false);
      }
      setError(err instanceof Error ? err.message : '开启 AlphaSift 失败');
    } finally {
      setEnabling(false);
    }
  };

  const handleStrategyChange = (nextStrategy: string) => {
    if (nextStrategy !== strategy) {
      clearScreeningResults();
    }
    setStrategy(nextStrategy);
  };

  const handleMarketChange = (nextMarket: string) => {
    if (nextMarket !== market) {
      clearScreeningResults();
    }
    setMarket(nextMarket);
  };

  const handleMaxResultsChange = (nextMaxResults: number) => {
    if (nextMaxResults !== maxResults) {
      clearScreeningResults();
    }
    setMaxResults(nextMaxResults);
  };

  const openFactorPipeline = async (recordId: number) => {
    setFactorPipelineLoadingRecordId(recordId);
    setFactorPipelineError('');
    try {
      const response: FactorPipelineRecordResponse = await alphasiftApi.getFactorPipeline(recordId);
      setLatestFactorPipeline(response.factorPipeline);
      setSelectedFactorPipeline(response.factorPipeline);
    } catch (error) {
      setFactorPipelineError(error instanceof Error ? error.message : '加载因子流水线失败');
    } finally {
      setFactorPipelineLoadingRecordId(null);
    }
  };

  const rerunFactorPipeline = async (recordId: number, screeningDate?: string, market?: string) => {
    setFactorPipelineLoadingRecordId(recordId);
    setFactorPipelineError('');
    try {
      const response: FactorPipelineTriggerResponse = await alphasiftApi.triggerFactorPipeline({
        recordId,
        screeningDate,
        market,
      });
      const summary = toFactorPipelineSummary(response);
      setLatestFactorPipeline(summary);
      setSelectedFactorPipeline(summary);
      await loadRecords(recordsPage);
    } catch (error) {
      setFactorPipelineError(error instanceof Error ? error.message : '触发因子流水线失败');
    } finally {
      setFactorPipelineLoadingRecordId(null);
    }
  };

  // Load history record detail with candidates
  const loadRecordDetail = async (recordId: number) => {
    setHistoryDetailLoadingRecordId(recordId);
    setHistoryDetail(null);
    try {
      const detail = await alphasiftApi.getRecordDetail(recordId);
      setHistoryDetail(detail);
    } catch (error) {
      console.error('加载历史记录详情失败:', error);
    } finally {
      setHistoryDetailLoadingRecordId(null);
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError('');
    setScreenMeta(null);
    try {
      const result = await alphasiftApi.screen({ market, strategy, maxResults });
      setScreenMeta(result);
      setCandidates(result.candidates);
      setExpandedCode(result.candidates[0]?.code ?? null);
      // Refresh records list after successful screening
      void loadRecords(0);
    } catch (err) {
      setCandidates([]);
      setError(err instanceof Error ? err.message : '选股失败');
    } finally {
      setLoading(false);
    }
  };

  /** 一键运行所有策略 */
  const handleRunAll = async (notifyFeishu: boolean) => {
    setBatchRunning(true);
    setError('');
    setBatchResult(null);
    try {
      const result = await alphasiftApi.runBatch({
        market,
        maxResults,
        autoBacktest: true,
        notifyFeishu,
      });
      setBatchResult(result);
      // Refresh records after batch run
      void loadRecords(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : '批量选股失败');
    } finally {
      setBatchRunning(false);
    }
  };

  return (
    <AppPage className="max-w-6xl space-y-6 pb-12 pt-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="grid h-7 w-7 place-items-center rounded-full border-2 border-cyan text-cyan shadow-[0_0_24px_hsl(var(--primary)/0.18)]">
            <PlusCircle className="h-4 w-4" />
          </span>
          <div>
            <h1 className="text-2xl font-bold tracking-normal text-foreground">AlphaSift 选股</h1>
            <p className="mt-1 text-sm text-secondary-text">开启后通过 AlphaSift 适配层生成候选股票</p>
          </div>
        </div>

        <div className="inline-flex w-fit items-center gap-2 rounded-2xl border border-border/70 bg-card/80 px-4 py-2 text-sm shadow-soft-card">
          <span className={`h-2.5 w-2.5 rounded-full ${enabled ? 'bg-success' : 'bg-warning'}`} />
          <span className="font-medium text-secondary-text">{enabled ? '选股已开启' : '选股未开启'}</span>
        </div>
      </div>

      {!enabled ? (
        <InlineAlert
          variant="info"
          title="AlphaSift 未开启"
          message="点击后写入 ALPHASIFT_ENABLED=true 并检查 AlphaSift 适配层；桌面发布包已内置依赖，源码部署需先在后端 Python 环境安装。"
          action={
            <Button size="sm" isLoading={enabling} loadingText="开启中..." onClick={() => void handleEnable()}>
              开启 AlphaSift
            </Button>
          }
        />
      ) : null}

      <InlineAlert
        variant="warning"
        title="风险提示"
        message="AlphaSift 选股结果仅用于研究和辅助判断，不构成投资建议；市场有风险，交易决策和损益由使用者自行承担。"
      />
      {factorPipelineError ? (
        <InlineAlert variant="danger" title="因子流水线" message={factorPipelineError} />
      ) : null}

      {error ? <InlineAlert variant="danger" title="调用失败" message={error} /> : null}

      <FactorPipelineSummaryCard
        title="因子流水线结果"
        subtitle={records[0] ? `记录 #${records[0].id}` : '最近一次筛选结果 · 支持显式重跑与只读查看'}
        recordId={records[0]?.id ?? null}
        factorPipeline={latestFactorPipeline}
        loading={factorPipelineLoadingRecordId != null}
        onOpen={() => {
          const latestRecord = records[0];
          if (latestRecord) {
            void openFactorPipeline(latestRecord.id);
          }
        }}
        onRerun={() => {
          const latestRecord = records[0];
          if (latestRecord) {
            void rerunFactorPipeline(latestRecord.id, latestRecord.screeningDate, latestRecord.market);
          }
        }}
      />

      <section className="rounded-2xl border border-cyan/35 bg-card/95 p-4 shadow-soft-card">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-foreground">选择策略</h2>
            <p className="mt-1 text-xs text-secondary-text">策略来自 AlphaSift，DSA 只负责调用稳定适配层。</p>
          </div>
          <span className="rounded-full border border-cyan/30 bg-cyan/10 px-3 py-1 text-xs font-semibold text-cyan">
            {selectedStrategyTag}
          </span>
        </div>

        <div className="mb-4 flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="secondary"
            isLoading={factorPipelineLoadingRecordId != null}
            loadingText="处理中..."
            onClick={() => {
              const latestRecord = records[0];
              if (latestRecord) {
                void rerunFactorPipeline(latestRecord.id, latestRecord.screeningDate, latestRecord.market);
              }
            }}
            disabled={records.length === 0}
          >
            重跑最新因子
          </Button>
          {records[0] ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => void openFactorPipeline(records[0].id)}
            >
              查看最新因子
            </Button>
          ) : null}
        </div>

        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {loadingStrategies ? (
            <div className="rounded-xl border border-dashed border-border bg-surface/70 p-4 text-sm text-secondary-text">
              正在读取可用策略...
            </div>
          ) : strategies.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-surface/70 p-4 text-sm text-secondary-text">
              {strategyLoadError || 'AlphaSift 策略列表暂未载入，可在下方手动输入策略参数。'}
            </div>
          ) : (
            strategies.map((item) => {
              const selected = item.id === strategy;
              return (
                <button
                  key={item.id}
                  className={`min-h-28 rounded-xl border p-4 text-left transition-all ${
                    selected
                      ? 'border-cyan bg-cyan/10 shadow-[0_0_0_1px_hsl(var(--primary)/0.15),0_16px_36px_hsl(var(--primary)/0.12)]'
                      : 'border-border/80 bg-surface/70 hover:border-cyan/45 hover:bg-hover/70'
                  }`}
                  type="button"
                  onClick={() => handleStrategyChange(item.id)}
                >
                  <span className="text-base font-semibold text-foreground">{item.name || item.title || item.id}</span>
                  <span className="mt-2 block text-sm leading-6 text-secondary-text">{item.description || item.id}</span>
                  <span className="mt-3 inline-flex text-xs font-semibold text-cyan">
                    {item.category || item.tag || item.tags?.[0] || item.id}
                  </span>
                </button>
              );
            })
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card/95 p-4 shadow-soft-card">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-foreground">
          <SlidersHorizontal className="h-4 w-4 text-cyan" />
          参数设置
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr_180px_auto] lg:items-end">
          <label className="space-y-2 text-xs font-medium text-secondary-text">
            市场
            <select
              className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none transition-colors focus:border-cyan"
              value={market}
              onChange={(event) => handleMarketChange(event.target.value)}
            >
              {MARKETS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2 text-xs font-medium text-secondary-text">
            策略参数
            <input
              className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none transition-colors focus:border-cyan"
              value={strategy}
              onChange={(event) => handleStrategyChange(event.target.value)}
            />
          </label>

          <label className="space-y-2 text-xs font-medium text-secondary-text">
            返回数量
            <input
              className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none transition-colors focus:border-cyan"
              type="number"
              min={1}
              max={100}
              value={maxResults}
              onChange={(event) => handleMaxResultsChange(Number(event.target.value))}
            />
          </label>

          <Button
            className="h-11 min-w-40"
            isLoading={loading}
            loadingText="筛选中..."
            disabled={!enabled || loading}
            onClick={() => void handleSubmit()}
          >
            <Play className="h-4 w-4" />
            运行选股
          </Button>

          <Button
            className="h-11 min-w-44"
            variant="secondary"
            isLoading={batchRunning}
            loadingText="批量筛选中..."
            disabled={!enabled || batchRunning || loading}
            onClick={() => void handleRunAll(false)}
          >
            <Zap className="h-4 w-4" />
            一键运行全部策略
          </Button>

          <Button
            className="h-11"
            variant="outline"
            isLoading={batchRunning}
            loadingText="筛选中..."
            disabled={!enabled || batchRunning || loading}
            onClick={() => void handleRunAll(true)}
          >
            <Zap className="h-4 w-4" />
            全部策略→飞书
          </Button>
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card/95 p-4 shadow-soft-card">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span
              className={`grid h-7 w-7 place-items-center rounded-full ${
                candidates.length > 0 ? 'text-success' : enabled ? 'text-cyan' : 'text-warning'
              }`}
            >
              {candidates.length > 0 ? <CheckCircle2 className="h-5 w-5" /> : <CircleAlert className="h-5 w-5" />}
            </span>
            <div>
              <h2 className="text-sm font-semibold text-foreground">
                {candidates.length > 0 ? '选股完成' : enabled ? '等待运行' : '等待开启'}
              </h2>
              <p className="mt-1 text-xs text-secondary-text">
                当前策略：{displayedStrategy} · {MARKETS.find((item) => item.id === market)?.label}
              </p>
            </div>
          </div>
          <div className="grid gap-1 text-xs text-secondary-text sm:text-right">
            <span>Run ID：{screenMeta?.runId || '-'}</span>
            <span>
              快照 {screenMeta?.snapshotCount ?? '-'} · 过滤后 {screenMeta?.afterFilterCount ?? '-'} · 候选 {screenMeta?.candidateCount ?? candidates.length}
            </span>
            <span>
              LLM：{screenMeta?.llmRanked ? '已重排' : screenMeta ? '未重排' : '-'}
              {screenMeta?.llmCoverage != null ? ` · 覆盖 ${formatPercent(screenMeta.llmCoverage)}` : ''}
            </span>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card/95 p-4 shadow-soft-card">
        <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-foreground">选股结果</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-secondary-text">
              AlphaSift 返回的候选会在这里展示，展开后可查看因子、风险、后置分析摘要和原始字段。
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-secondary-text hover:text-foreground hover:border-cyan/30 transition-colors"
              onClick={() => navigate('/backtest')}
            >
              <BarChart3 className="h-3.5 w-3.5 text-cyan" />
              去回测
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-secondary-text hover:text-foreground hover:border-cyan/30 transition-colors"
              onClick={() => setShowFactorIntro(true)}
            >
              <BookOpen className="h-3.5 w-3.5 text-cyan" />
              因子介绍
            </button>
            <div className="flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 text-xs text-secondary-text">
            <Search className="h-4 w-4 text-cyan" />
            {candidates.length} 条候选
          </div>
          </div>
        </div>

        {candidates.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-surface/70 px-5 py-10 text-center">
            <p className="text-sm font-medium text-foreground">暂无结果</p>
            <p className="mt-2 text-sm text-secondary-text">开启 AlphaSift 后点击“运行选股”生成候选列表。</p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border">
            <table className="w-full min-w-[860px] border-collapse text-sm">
              <thead className="bg-surface text-left text-xs text-secondary-text">
                <tr>
                  <th className="w-14 px-4 py-3 font-semibold">#</th>
                  <th className="px-4 py-3 font-semibold">代码</th>
                  <th className="px-4 py-3 font-semibold">名称</th>
                  <th className="px-4 py-3 font-semibold">行业</th>
                  <th className="px-4 py-3 font-semibold">价格</th>
                  <th className="px-4 py-3 font-semibold">涨跌幅</th>
                  <th className="px-4 py-3 font-semibold">评分</th>
                  <th className="px-4 py-3 font-semibold">LLM</th>
                  <th className="px-4 py-3 font-semibold">风险</th>
                  <th className="px-4 py-3 font-semibold">详情</th>
                  <th className="px-4 py-3 font-semibold">操作</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((item) => {
                  const expanded = expandedCode === item.code;
                  const factors = getFactorEntries(item);
                  return (
                    <Fragment key={`${item.rank}-${item.code}`}>
                      <tr className="border-t border-border align-top transition-colors hover:bg-hover/50">
                        <td className="px-4 py-3 text-secondary-text">{item.rank}</td>
                        <td className="px-4 py-3 font-mono font-semibold text-foreground">{item.code}</td>
                        <td className="px-4 py-3 font-semibold text-foreground">{item.name || '-'}</td>
                        <td className="px-4 py-3 text-secondary-text">{item.industry || '-'}</td>
                        <td className="px-4 py-3 text-secondary-text">{formatNumber(item.price)}</td>
                        <td className="px-4 py-3 text-secondary-text">{formatNumber(item.changePct)}%</td>
                        <td className="px-4 py-3 font-bold text-cyan">{formatScore(item.score)}</td>
                        <td className="px-4 py-3 text-secondary-text">{formatScore(item.llmScore)}</td>
                        <td className="px-4 py-3">
                          <span className="rounded-lg bg-success/10 px-2.5 py-1 text-xs font-semibold text-success">
                            {item.riskLevel || 'unknown'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <button
                            className="text-sm font-semibold text-cyan transition-colors hover:text-foreground"
                            type="button"
                            onClick={() => setExpandedCode(expanded ? null : item.code)}
                          >
                            {expanded ? '收起' : '展开查看'}
                          </button>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <WatchlistButton
                              code={item.code}
                              name={item.name || ''}
                              score={typeof item.score === 'number' && !Number.isNaN(Number(item.score)) ? Number(item.score) : undefined}
                              sector={item.industry || null}
                              source="screening"
                            />
                            <button
                              type="button"
                              className="inline-flex items-center gap-1 rounded-lg border border-cyan/30 bg-cyan/5 px-2 py-1 text-xs text-cyan transition-colors hover:bg-cyan/10 hover:border-cyan/60"
                              title="问股分析"
                              onClick={() => navigate(`/chat?code=${item.code}&name=${encodeURIComponent(item.name || '')}`)}
                            >
                              <MessageSquareQuote className="h-3 w-3" />
                              问股
                            </button>
                          </div>
                        </td>
                      </tr>
                      {expanded ? (
                        <tr className="border-t border-border bg-surface/45">
                          <td colSpan={11} className="px-4 py-4">
                            {/* 快捷操作栏 */}
                            <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card/60 px-4 py-3">
                              <span className="text-xs font-semibold text-secondary-text">快捷操作：</span>
                              <WatchlistButton
                                code={item.code}
                                name={item.name || ''}
                                score={typeof item.score === 'number' && !Number.isNaN(Number(item.score)) ? Number(item.score) : undefined}
                                sector={item.industry || null}
                                source="screening"
                                size="md"
                              />
                              <button
                                type="button"
                                className="inline-flex items-center gap-2 rounded-lg border border-cyan/30 bg-cyan/5 px-3 py-1.5 text-sm text-cyan transition-colors hover:bg-cyan/10"
                                onClick={() => navigate(`/chat?code=${item.code}&name=${encodeURIComponent(item.name || '')}`)}
                              >
                                <MessageSquareQuote className="h-4 w-4" />
                                问股分析 {item.name || item.code}
                              </button>
                            </div>
                            <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
                              <div className="space-y-3">
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">摘要</p>
                                  <p className="mt-1 text-sm leading-6 text-foreground">{getCandidateReason(item)}</p>
                                </div>
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">操作信号</p>
                                  <p className="mt-1 text-sm text-foreground">{getSignal(item)}</p>
                                </div>
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">LLM 判断</p>
                                  <p className="mt-1 text-sm leading-6 text-foreground">
                                    {item.llmThesis || item.reason || '暂无 LLM 判断'}
                                  </p>
                                  <p className="mt-1 text-xs text-secondary-text">
                                    板块 {item.llmSector || '-'} · 主题 {item.llmTheme || '-'} · 置信度 {formatPercent(item.llmConfidence)}
                                  </p>
                                </div>
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">风险标签</p>
                                  <p className="mt-1 text-sm text-foreground">
                                    {[...(item.riskFlags || []), ...(item.llmRisks || [])].length
                                      ? [...(item.riskFlags || []), ...(item.llmRisks || [])].join('，')
                                      : '无'}
                                  </p>
                                </div>
                              </div>
                              <div className="space-y-3">
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">主要因子</p>
                                  <div className="mt-2 grid grid-cols-2 gap-2">
                                    {factors.length > 0 ? (
                                      factors.map(([key, value]) => (
                                        <div key={key} className="rounded-lg border border-border bg-card px-3 py-2">
                                          <span className="block text-xs text-secondary-text">{key}</span>
                                          <span className="text-sm font-semibold text-foreground">{formatNumber(value)}</span>
                                        </div>
                                      ))
                                    ) : (
                                      <span className="text-sm text-secondary-text">无因子明细</span>
                                    )}
                                  </div>
                                </div>
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">成交额</p>
                                  <p className="mt-1 text-sm text-foreground">{formatAmount(item.amount)}</p>
                                </div>
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">LLM 关注项</p>
                                  <p className="mt-1 text-sm text-foreground">
                                    {item.llmWatchItems?.length ? item.llmWatchItems.join('，') : '无'}
                                  </p>
                                </div>
                                <div>
                                  <p className="text-xs font-semibold text-secondary-text">催化因素</p>
                                  <p className="mt-1 text-sm text-foreground">
                                    {item.llmCatalysts?.length ? item.llmCatalysts.join('，') : '无'}
                                  </p>
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ===== 批量运行结果 ===== */}
      {batchResult ? (
        <section className="rounded-2xl border border-success/40 bg-card/95 p-4 shadow-soft-card">
          <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-foreground">
            <Zap className="h-4 w-4 text-success" />
            全部策略运行完成
            <span className="ml-2 rounded-full bg-surface px-2 py-0.5 text-xs text-secondary-text">
              📅 {batchResult.screeningDate}
            </span>
          </div>

          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-border bg-surface p-3 text-center">
              <p className="text-xs text-secondary-text">策略总数</p>
              <p className="mt-1 text-lg font-bold text-foreground">{batchResult.totalStrategies}</p>
            </div>
            <div className="rounded-xl border border-border bg-surface p-3 text-center">
              <p className="text-xs text-secondary-text">✅ 成功</p>
              <p className="mt-1 text-lg font-bold text-success">{batchResult.completedStrategies}</p>
            </div>
            <div className="rounded-xl border border-border bg-surface p-3 text-center">
              <p className="text-xs text-secondary-text">❌ 失败</p>
              <p className="mt-1 text-lg font-bold text-warning">{batchResult.failedStrategies}</p>
            </div>
            <div className="rounded-xl border border-border bg-surface p-3 text-center">
              <p className="text-xs text-secondary-text">🎯 候选 / 去重</p>
              <p className="mt-1 text-lg font-bold text-cyan">
                {batchResult.totalCandidates} / {batchResult.uniqueCodes}
              </p>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-border">
            <table className="w-full border-collapse text-sm">
              <thead className="bg-surface text-left text-xs text-secondary-text">
                <tr>
                  <th className="px-4 py-2 font-semibold">策略</th>
                  <th className="px-4 py-2 font-semibold">状态</th>
                  <th className="px-4 py-2 font-semibold">候选数</th>
                  <th className="px-4 py-2 font-semibold">候选股票</th>
                </tr>
              </thead>
              <tbody>
                {batchResult.strategies.map((sr) => (
                  <tr key={sr.strategy} className="border-t border-border">
                    <td className="px-4 py-2 font-medium text-foreground">
                      {getStrategyNameCn(sr.strategy)}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`rounded-lg px-2 py-0.5 text-xs font-semibold ${sr.status === 'completed' ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning'}`}>
                        {sr.status === 'completed' ? '完成' : '失败'}
                      </span>
                    </td>
                    <td className="px-4 py-2 font-mono text-cyan">{sr.candidateCount}</td>
                    <td className="px-4 py-2 text-xs text-secondary-text">
                      {sr.candidateCodes?.slice(0, 5).join('、') || '-'}
                      {(sr.candidateCodes?.length ?? 0) > 5 ? '...' : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {batchResult.autoBacktest ? (
            <div className="mt-3 text-xs text-secondary-text">
              回测：{batchResult.autoBacktest.status === 'completed' ? '✅ 完成' : `⚠️ ${batchResult.autoBacktest.error || batchResult.autoBacktest.status}`}
            </div>
          ) : null}
        </section>
      ) : null}

      {/* ===== 历史选股记录 ===== */}
      <section className="rounded-2xl border border-border bg-card/95 p-4 shadow-soft-card">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-foreground">
          <Clock className="h-4 w-4 text-cyan" />
          历史记录
          {recordsTotal > 0 ? (
            <span className="ml-2 rounded-full bg-surface px-2 py-0.5 text-xs text-secondary-text">
              共 {recordsTotal} 条
            </span>
          ) : null}
        </div>

        {recordsLoading ? (
          <div className="rounded-xl border border-dashed border-border bg-surface/70 px-5 py-10 text-center">
            <p className="text-sm text-secondary-text">加载历史记录中...</p>
          </div>
        ) : records.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-surface/70 px-5 py-10 text-center">
            <p className="text-sm font-medium text-foreground">暂无历史记录</p>
            <p className="mt-2 text-sm text-secondary-text">
              运行选股后，结果将自动保存并在此展示。
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-hidden rounded-xl border border-border">
              <table className="w-full min-w-[640px] border-collapse text-sm">
                <thead className="bg-surface text-left text-xs text-secondary-text">
                  <tr>
                    <th className="w-16 px-4 py-3 font-semibold">ID</th>
                    <th className="px-4 py-3 font-semibold">日期</th>
                    <th className="px-4 py-3 font-semibold">策略</th>
                    <th className="px-4 py-3 font-semibold">市场</th>
                    <th className="px-4 py-3 font-semibold">候选数</th>
                    <th className="px-4 py-3 font-semibold">状态</th>
                    <th className="px-4 py-3 font-semibold">耗时</th>
                    <th className="px-4 py-3 font-semibold">因子</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((record) => (
                    <tr
                      key={record.id}
                      className="border-t border-border transition-colors hover:bg-hover/50"
                    >
                      <td className="px-4 py-3 font-mono text-xs text-secondary-text">{record.id}</td>
                      <td className="px-4 py-3 text-foreground">{record.screeningDate || '-'}</td>
                      <td className="px-4 py-3 font-medium text-foreground">{getStrategyNameCn(record.strategy)}</td>
                      <td className="px-4 py-3 text-secondary-text">{record.market}</td>
                      <td className="px-4 py-3 font-mono text-cyan">{record.candidateCount}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${
                            record.status === 'completed'
                              ? 'bg-success/10 text-success'
                              : 'bg-warning/10 text-warning'
                          }`}
                        >
                          {record.status === 'completed' ? '完成' : '失败'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-secondary-text">
                        {record.durationSeconds != null ? `${record.durationSeconds.toFixed(1)}s` : '-'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Button
                            size="xsm"
                            variant="ghost"
                            isLoading={historyDetailLoadingRecordId === record.id}
                            loadingText="加载中"
                            onClick={() => void loadRecordDetail(record.id)}
                          >
                            查看
                          </Button>
                          <Button
                            size="xsm"
                            variant="ghost"
                            isLoading={factorPipelineLoadingRecordId === record.id}
                            loadingText="读取中"
                            onClick={() => void openFactorPipeline(record.id)}
                          >
                            因子
                          </Button>
                          <Button
                            size="xsm"
                            variant="outline"
                            isLoading={factorPipelineLoadingRecordId === record.id}
                            loadingText="重跑中"
                            onClick={() => void rerunFactorPipeline(record.id, record.screeningDate, record.market)}
                          >
                            重跑
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {recordsTotal > RECORDS_PAGE_SIZE ? (
              <div className="mt-4 flex items-center justify-between text-sm text-secondary-text">
                <span>
                  第 {recordsPage * RECORDS_PAGE_SIZE + 1}–{Math.min((recordsPage + 1) * RECORDS_PAGE_SIZE, recordsTotal)} 条，共 {recordsTotal} 条
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs transition-colors hover:border-cyan/30 hover:text-foreground disabled:opacity-40"
                    disabled={recordsPage === 0}
                    onClick={() => void loadRecords(recordsPage - 1)}
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                    上一页
                  </button>
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs transition-colors hover:border-cyan/30 hover:text-foreground disabled:opacity-40"
                    disabled={(recordsPage + 1) * RECORDS_PAGE_SIZE >= recordsTotal}
                    onClick={() => void loadRecords(recordsPage + 1)}
                  >
                    下一页
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ) : null}
          </>
        )}
      </section>

      {/* 因子流水线结果抽屉 */}
      <Drawer
        isOpen={selectedFactorPipeline != null}
        onClose={() => setSelectedFactorPipeline(null)}
        title="因子流水线结果"
        width="max-w-5xl"
      >
        {selectedFactorPipeline ? (
          <pre className="max-h-[70vh] overflow-auto rounded-xl border border-border bg-surface p-4 text-xs leading-6 text-secondary-text">
            {JSON.stringify(selectedFactorPipeline, null, 2)}
          </pre>
        ) : null}
      </Drawer>

      {/* 历史记录详情抽屉 */}
      <Drawer
        isOpen={historyDetail != null}
        onClose={() => setHistoryDetail(null)}
        title={`历史记录 #${historyDetail?.id} · ${historyDetail?.screeningDate || ''}`}
        width="max-w-6xl"
      >
        {historyDetail ? (
          <div className="space-y-4">
            {/* 记录概要 */}
            <div className="space-y-3">
              {/* 基础信息卡片 */}
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="rounded-lg border border-border bg-surface/50 px-3 py-2">
                  <span className="text-xs text-secondary-text">策略</span>
                  <p className="mt-0.5 font-semibold text-foreground">{getStrategyNameCn(historyDetail.strategy)}</p>
                </div>
                <div className="rounded-lg border border-border bg-surface/50 px-3 py-2">
                  <span className="text-xs text-secondary-text">市场</span>
                  <p className="mt-0.5 font-semibold text-foreground">{historyDetail.market}</p>
                </div>
                <div className="rounded-lg border border-border bg-surface/50 px-3 py-2">
                  <span className="text-xs text-secondary-text">状态</span>
                  <p className="mt-0.5">
                    <span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${
                      historyDetail.status === 'completed'
                        ? 'bg-success/10 text-success'
                        : 'bg-warning/10 text-warning'
                    }`}>
                      {historyDetail.status === 'completed' ? '完成' : '失败'}
                    </span>
                  </p>
                </div>
                <div className="rounded-lg border border-border bg-surface/50 px-3 py-2">
                  <span className="text-xs text-secondary-text">耗时</span>
                  <p className="mt-0.5 font-mono font-semibold text-foreground">
                    {historyDetail.durationSeconds != null ? `${historyDetail.durationSeconds.toFixed(1)}s` : '-'}
                  </p>
                </div>
                {historyDetail.runId && (
                  <div className="col-span-2 rounded-lg border border-border bg-surface/50 px-3 py-2">
                    <span className="text-xs text-secondary-text">Run ID</span>
                    <p className="mt-0.5 font-mono text-xs text-secondary-text truncate">{historyDetail.runId}</p>
                  </div>
                )}
              </div>

              {/* 筛选流水线统计 */}
              <div className="rounded-xl border border-border bg-card p-4">
                <h3 className="mb-3 flex items-center gap-1.5 text-sm font-semibold text-foreground">
                  <Filter className="h-4 w-4 text-cyan" />
                  筛选流水线
                </h3>
                <div className="flex items-center gap-3">
                  <div className="flex-1 text-center">
                    <div className="rounded-lg border border-cyan/20 bg-cyan/5 px-3 py-2">
                      <span className="block text-xs text-secondary-text">全市场快照</span>
                      <span className="text-lg font-bold text-cyan">{historyDetail.snapshotCount ?? '-'}</span>
                    </div>
                  </div>
                  <div className="flex items-center text-secondary-text">
                    <ChevronRight className="h-4 w-4" />
                  </div>
                  <div className="flex-1 text-center">
                    <div className="rounded-lg border border-cyan/20 bg-cyan/5 px-3 py-2">
                      <span className="block text-xs text-secondary-text">因子过滤后</span>
                      <span className="text-lg font-bold text-cyan">{historyDetail.afterFilterCount ?? '-'}</span>
                    </div>
                  </div>
                  <div className="flex items-center text-secondary-text">
                    <ChevronRight className="h-4 w-4" />
                  </div>
                  <div className="flex-1 text-center">
                    <div className={`rounded-lg border px-3 py-2 ${historyDetail.llmRanked ? 'border-cyan/20 bg-cyan/5' : 'border-border bg-surface/50'}`}>
                      <span className="block text-xs text-secondary-text">LLM 重排</span>
                      <span className={`text-lg font-bold ${historyDetail.llmRanked ? 'text-cyan' : 'text-secondary-text'}`}>
                        {historyDetail.llmRanked ? '✓' : '✗'}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center text-secondary-text">
                    <ChevronRight className="h-4 w-4" />
                  </div>
                  <div className="flex-1 text-center">
                    <div className="rounded-lg border border-cyan/20 bg-cyan/5 px-3 py-2">
                      <span className="block text-xs text-secondary-text">最终候选</span>
                      <span className="text-lg font-bold text-cyan">{historyDetail.candidateCount}</span>
                    </div>
                  </div>
                </div>
                {historyDetail.snapshotCount != null && historyDetail.afterFilterCount != null && (
                  <div className="mt-3 text-xs text-secondary-text">
                    过滤通过率：{historyDetail.snapshotCount > 0
                      ? `${((historyDetail.afterFilterCount / historyDetail.snapshotCount) * 100).toFixed(2)}%`
                      : '-'}
                    {historyDetail.llmCoverage != null && (
                      <span className="ml-4">LLM 覆盖率：{formatPercent(historyDetail.llmCoverage)}</span>
                    )}
                  </div>
                )}
              </div>

              {/* 错误与告警 */}
              {historyDetail.errorMessage && (
                <div className="rounded-lg border border-danger/20 bg-danger/5 px-3 py-2">
                  <span className="text-xs font-semibold text-danger">错误</span>
                  <p className="mt-1 text-sm text-danger">{historyDetail.errorMessage}</p>
                </div>
              )}
              {historyDetail.warnings && historyDetail.warnings.length > 0 && (
                <div className="rounded-lg border border-warning/20 bg-warning/5 px-3 py-2">
                  <span className="text-xs font-semibold text-warning">警告 ({historyDetail.warnings.length})</span>
                  <ul className="mt-1 list-inside list-disc space-y-0.5 text-sm text-warning">
                    {historyDetail.warnings.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </div>
              )}
              {historyDetail.sourceErrors && historyDetail.sourceErrors.length > 0 && (
                <div className="rounded-lg border border-danger/20 bg-danger/5 px-3 py-2">
                  <span className="text-xs font-semibold text-danger">数据源错误 ({historyDetail.sourceErrors.length})</span>
                  <ul className="mt-1 list-inside list-disc space-y-0.5 text-sm text-danger">
                    {historyDetail.sourceErrors.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                </div>
              )}
              {historyDetail.executionLogs && (
                <details className="rounded-lg border border-border bg-surface/50">
                  <summary className="cursor-pointer select-none px-3 py-2 text-xs font-semibold text-secondary-text hover:text-foreground">
                    📋 执行日志 ({historyDetail.executionLogs.length} 字符)
                  </summary>
                  <pre className="max-h-64 overflow-auto p-3 text-xs leading-5 text-secondary-text">
                    {historyDetail.executionLogs}
                  </pre>
                </details>
              )}
            </div>

            {/* LLM 分析区 */}
            {(historyDetail.llmMarketView || historyDetail.llmSelectionLogic || historyDetail.llmPortfolioRisk) && (
              <div className="space-y-3 rounded-xl border border-border bg-card p-4">
                <h3 className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                  <MessageSquareQuote className="h-4 w-4 text-cyan" />
                  LLM 分析
                  {historyDetail.llmRanked && (
                    <span className="rounded-full bg-cyan/10 px-2 py-0.5 text-xs text-cyan">已启用</span>
                  )}
                </h3>
                <div className="grid gap-3 lg:grid-cols-3">
                  {historyDetail.llmMarketView && (
                    <div className="rounded-lg border border-border bg-surface/50 p-3">
                      <p className="text-xs font-semibold text-secondary-text">市场观点</p>
                      <p className="mt-1.5 text-sm leading-6 text-foreground">{historyDetail.llmMarketView}</p>
                    </div>
                  )}
                  {historyDetail.llmSelectionLogic && (
                    <div className="rounded-lg border border-border bg-surface/50 p-3">
                      <p className="text-xs font-semibold text-secondary-text">选股逻辑</p>
                      <p className="mt-1.5 text-sm leading-6 text-foreground">{historyDetail.llmSelectionLogic}</p>
                    </div>
                  )}
                  {historyDetail.llmPortfolioRisk && (
                    <div className="rounded-lg border border-border bg-surface/50 p-3">
                      <p className="text-xs font-semibold text-secondary-text">组合风险</p>
                      <p className="mt-1.5 text-sm leading-6 text-foreground">{historyDetail.llmPortfolioRisk}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 回测数据区 */}
            {(historyDetail.backtestSummary || (historyDetail.backtestResults && historyDetail.backtestResults.length > 0)) && (
              <div className="space-y-3 rounded-xl border border-border bg-card p-4">
                <h3 className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                  <TrendingUp className="h-4 w-4 text-cyan" />
                  回测数据
                  {historyDetail.backtestResults && historyDetail.backtestResults.length > 0 && (
                    <span className="rounded-full bg-cyan/10 px-2 py-0.5 text-xs text-cyan">
                      {historyDetail.backtestResults.length} 条记录
                    </span>
                  )}
                </h3>
                {historyDetail.backtestSummary && (
                  <div className="grid grid-cols-2 gap-2 text-sm lg:grid-cols-4">
                    {historyDetail.backtestSummary.avgAnnualReturn != null && (
                      <div className="rounded-lg border border-border bg-surface px-3 py-2">
                        <span className="block text-xs text-secondary-text">平均年化收益</span>
                        <span className="text-sm font-semibold text-success">
                          {(Number(historyDetail.backtestSummary.avgAnnualReturn) * 100).toFixed(2)}%
                        </span>
                      </div>
                    )}
                    {historyDetail.backtestSummary.avgMaxDrawdown != null && (
                      <div className="rounded-lg border border-border bg-surface px-3 py-2">
                        <span className="block text-xs text-secondary-text">平均最大回撤</span>
                        <span className="text-sm font-semibold text-warning">
                          {(Number(historyDetail.backtestSummary.avgMaxDrawdown) * 100).toFixed(2)}%
                        </span>
                      </div>
                    )}
                    {historyDetail.backtestSummary.avgSharpe != null && (
                      <div className="rounded-lg border border-border bg-surface px-3 py-2">
                        <span className="block text-xs text-secondary-text">平均夏普比</span>
                        <span className="text-sm font-semibold text-foreground">
                          {Number(historyDetail.backtestSummary.avgSharpe).toFixed(2)}
                        </span>
                      </div>
                    )}
                    {historyDetail.backtestSummary.avgWinRate != null && (
                      <div className="rounded-lg border border-border bg-surface px-3 py-2">
                        <span className="block text-xs text-secondary-text">平均胜率</span>
                        <span className="text-sm font-semibold text-foreground">
                          {(Number(historyDetail.backtestSummary.avgWinRate) * 100).toFixed(1)}%
                        </span>
                      </div>
                    )}
                  </div>
                )}
                {historyDetail.backtestResults && historyDetail.backtestResults.length > 0 && (
                  <div className="overflow-x-auto rounded-lg border border-border">
                    <table className="w-full text-sm">
                      <thead className="bg-surface text-left text-xs text-secondary-text">
                        <tr>
                          <th className="px-3 py-2 font-semibold">周期</th>
                          <th className="px-3 py-2 font-semibold">总收益</th>
                          <th className="px-3 py-2 font-semibold">年化收益</th>
                          <th className="px-3 py-2 font-semibold">最大回撤</th>
                          <th className="px-3 py-2 font-semibold">夏普比</th>
                          <th className="px-3 py-2 font-semibold">胜率</th>
                          <th className="px-3 py-2 font-semibold">Calmar</th>
                        </tr>
                      </thead>
                      <tbody>
                        {historyDetail.backtestResults.map((bt, idx) => {
                          const annualRet = bt.annualReturn != null ? Number(bt.annualReturn) : 0;
                          const maxDd = bt.maxDrawdown != null ? Math.abs(Number(bt.maxDrawdown)) : null;
                          const calmar = maxDd != null && maxDd > 0 ? (annualRet / maxDd).toFixed(2) : '-';
                          return (
                            <tr key={idx} className="border-t border-border transition-colors hover:bg-hover/30">
                              <td className="px-3 py-2.5 font-medium text-foreground">{bt.period || `#${idx + 1}`}</td>
                              <td className="px-3 py-2.5 font-mono">
                                <span className={bt.totalReturn != null && Number(bt.totalReturn) >= 0 ? 'text-success' : 'text-danger'}>
                                  {bt.totalReturn != null ? `${(Number(bt.totalReturn) * 100).toFixed(2)}%` : '-'}
                                </span>
                              </td>
                              <td className="px-3 py-2.5 font-mono">
                                <span className={annualRet >= 0 ? 'text-success' : 'text-danger'}>
                                  {bt.annualReturn != null ? `${(annualRet * 100).toFixed(2)}%` : '-'}
                                </span>
                              </td>
                              <td className="px-3 py-2.5 font-mono text-warning">
                                {bt.maxDrawdown != null ? `${(Number(bt.maxDrawdown) * 100).toFixed(2)}%` : '-'}
                              </td>
                              <td className="px-3 py-2.5 font-mono text-foreground">
                                {bt.sharpeRatio != null ? Number(bt.sharpeRatio).toFixed(2) : '-'}
                              </td>
                              <td className="px-3 py-2.5 font-mono text-foreground">
                                {bt.winRate != null ? `${(Number(bt.winRate) * 100).toFixed(1)}%` : '-'}
                              </td>
                              <td className="px-3 py-2.5 font-mono text-foreground">{calmar}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* 因子流水线概览 */}
            {historyDetail.factorPipeline && (() => {
              const fp = historyDetail.factorPipeline as Record<string, unknown>;
              const training = fp.training as Record<string, unknown> | undefined;
              const monitoring = fp.monitoring as Record<string, unknown> | undefined;
              const factorFamily = fp.factor_family as Record<string, unknown> | undefined;
              const topCandidates = fp.top_candidates as Array<Record<string, unknown>> | undefined;
              return (
                <div className="space-y-3 rounded-xl border border-border bg-card p-4">
                  <h3 className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                    <Layers className="h-4 w-4 text-cyan" />
                    因子流水线概览
                    <span className="rounded-full bg-cyan/10 px-2 py-0.5 text-xs text-cyan">
                      {fp.backend as string || 'skeleton'}
                    </span>
                  </h3>

                  {/* 流水线状态 */}
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div className="rounded-lg border border-border bg-surface/50 px-3 py-2">
                      <span className="text-xs text-secondary-text">状态</span>
                      <p className="mt-0.5 font-semibold text-foreground">{fp.status as string || '-'}</p>
                    </div>
                    <div className="rounded-lg border border-border bg-surface/50 px-3 py-2">
                      <span className="text-xs text-secondary-text">候选数</span>
                      <p className="mt-0.5 font-semibold text-foreground">{fp.candidate_count as number || 0}</p>
                    </div>
                    <div className="rounded-lg border border-border bg-surface/50 px-3 py-2">
                      <span className="text-xs text-secondary-text">最新策略</span>
                      <p className="mt-0.5 font-semibold text-foreground truncate">{fp.latest_strategy as string || '-'}</p>
                    </div>
                  </div>

                  {/* 训练信息 */}
                  {training && Object.keys(training).length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold text-secondary-text">训练信息</p>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        {Object.entries(training).map(([key, value]) => (
                          <div key={key} className="rounded-lg border border-border bg-surface/50 px-3 py-2">
                            <span className="text-xs text-secondary-text">{key}</span>
                            <p className="mt-0.5 font-mono text-xs text-foreground truncate">
                              {typeof value === 'object' ? JSON.stringify(value) : String(value ?? '-')}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 监控指标 */}
                  {monitoring && Object.keys(monitoring).length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold text-secondary-text">监控指标</p>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        {Object.entries(monitoring).map(([key, value]) => (
                          <div key={key} className="rounded-lg border border-border bg-surface/50 px-3 py-2">
                            <span className="text-xs text-secondary-text">{key}</span>
                            <p className="mt-0.5 font-mono text-xs text-foreground truncate">
                              {typeof value === 'object' ? JSON.stringify(value) : String(value ?? '-')}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 因子家族 */}
                  {factorFamily && Object.keys(factorFamily).length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold text-secondary-text">因子家族</p>
                      <div className="grid gap-1.5">
                        {Object.entries(factorFamily).map(([family, specs]) => {
                          const items = Array.isArray(specs) ? specs : [];
                          return (
                            <div key={family} className="rounded-lg border border-border bg-surface/50 px-3 py-2">
                              <span className="text-xs font-semibold text-cyan">{family}</span>
                              <span className="ml-2 text-xs text-secondary-text">
                                {items.length} 个因子
                                {items.length > 0 && ` · ${items.slice(0, 5).map((s: Record<string, unknown>) => s.name || s.factor).filter(Boolean).join(', ')}${items.length > 5 ? '…' : ''}`}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Top Candidates */}
                  {topCandidates && topCandidates.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold text-secondary-text">
                        Top {topCandidates.length} 候选（因子流水线）
                      </p>
                      <div className="grid gap-1.5">
                        {topCandidates.map((c, i) => (
                          <div key={i} className="flex items-center gap-2 rounded-lg border border-border bg-surface/50 px-3 py-1.5 text-xs">
                            <span className="font-mono font-semibold text-foreground">{c.code as string || '-'}</span>
                            <span className="text-foreground">{c.name as string || '-'}</span>
                            {c.score != null && (
                              <span className="ml-auto font-mono text-cyan">{Number(c.score).toFixed(2)}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 折叠的原始 JSON */}
                  <details className="group">
                    <summary className="cursor-pointer text-xs text-secondary-text hover:text-foreground">
                      查看原始数据
                    </summary>
                    <pre className="mt-2 max-h-[30vh] overflow-auto rounded-lg border border-border bg-surface p-3 text-xs leading-5 text-secondary-text">
                      {JSON.stringify(historyDetail.factorPipeline, null, 2)}
                    </pre>
                  </details>
                </div>
              );
            })()}

            {/* 候选股票列表 */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                  <Zap className="h-4 w-4 text-cyan" />
                  候选股票
                  <span className="rounded-full bg-cyan/10 px-2 py-0.5 text-xs text-cyan">
                    {historyDetail.candidates.length} 只
                  </span>
                </h3>
                {historyDetail.candidates.length > 0 && (
                  <span className="text-xs text-secondary-text">
                    均分 {historyDetail.candidates.reduce((sum, c) => sum + (c.score ?? 0), 0) / historyDetail.candidates.length > 0
                      ? (historyDetail.candidates.reduce((sum, c) => sum + (c.score ?? 0), 0) / historyDetail.candidates.length).toFixed(2)
                      : '-'}
                  </span>
                )}
              </div>
              {historyDetail.candidates.length === 0 ? (
                <div className="rounded-xl border border-dashed border-border bg-surface/70 px-5 py-10 text-center">
                  <p className="text-sm text-secondary-text">该记录暂无候选股票</p>
                </div>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-border">
                  <table className="w-full min-w-[1100px] border-collapse text-sm">
                    <thead className="bg-surface text-left text-xs text-secondary-text">
                      <tr>
                        <th className="px-3 py-3 font-semibold">#</th>
                        <th className="px-3 py-3 font-semibold">代码</th>
                        <th className="px-3 py-3 font-semibold">名称</th>
                        <th className="px-3 py-3 font-semibold">行业</th>
                        <th className="px-3 py-3 font-semibold">综合分</th>
                        <th className="px-3 py-3 font-semibold">筛选分</th>
                        <th className="px-3 py-3 font-semibold">LLM分</th>
                        <th className="px-3 py-3 font-semibold">置信度</th>
                        <th className="px-3 py-3 font-semibold">成交额</th>
                        <th className="px-3 py-3 font-semibold">涨跌幅</th>
                        <th className="px-3 py-3 font-semibold">风险</th>
                        <th className="px-3 py-3 font-semibold">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {historyDetail.candidates.map((item) => (
                        <tr
                          key={item.id}
                          className="border-t border-border transition-colors hover:bg-hover/50"
                        >
                          <td className="px-3 py-3 text-secondary-text font-mono">{item.rank}</td>
                          <td className="px-3 py-3 font-mono font-semibold text-foreground">{item.code}</td>
                          <td className="px-3 py-3 font-semibold text-foreground">{item.name || '-'}</td>
                          <td className="px-3 py-3 text-secondary-text text-xs">{item.industry || '-'}</td>
                          <td className="px-3 py-3 font-bold text-cyan">
                            {item.score != null && !Number.isNaN(item.score) ? Number(item.score).toFixed(2) : '-'}
                          </td>
                          <td className="px-3 py-3 text-secondary-text">
                            {item.screenScore != null && !Number.isNaN(item.screenScore) ? Number(item.screenScore).toFixed(2) : '-'}
                          </td>
                          <td className="px-3 py-3 text-secondary-text">
                            {item.llmScore != null && !Number.isNaN(item.llmScore) ? Number(item.llmScore).toFixed(2) : '-'}
                          </td>
                          <td className="px-3 py-3">
                            {item.llmConfidence != null && !Number.isNaN(item.llmConfidence) ? (
                              <div className="flex items-center gap-1.5">
                                <div className="h-1.5 w-12 overflow-hidden rounded-full bg-surface">
                                  <div
                                    className="h-full rounded-full bg-cyan transition-all"
                                    style={{ width: `${Math.min(Number(item.llmConfidence) * 100, 100)}%` }}
                                  />
                                </div>
                                <span className="text-xs text-secondary-text">{formatPercent(item.llmConfidence)}</span>
                              </div>
                            ) : '-'}
                          </td>
                          <td className="px-3 py-3 font-mono text-xs text-secondary-text">{formatAmount(item.amount)}</td>
                          <td className="px-3 py-3 font-mono text-xs">
                            <span className={item.changePct != null && Number(item.changePct) >= 0 ? 'text-success' : 'text-danger'}>
                              {item.changePct != null && !Number.isNaN(item.changePct)
                                ? `${Number(item.changePct) >= 0 ? '+' : ''}${Number(item.changePct).toFixed(2)}%`
                                : '-'}
                            </span>
                          </td>
                          <td className="px-3 py-3">
                            <span className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${
                              item.riskLevel === 'low' ? 'bg-success/10 text-success'
                              : item.riskLevel === 'high' ? 'bg-danger/10 text-danger'
                              : 'bg-warning/10 text-warning'
                            }`}>
                              {item.riskLevel || 'unknown'}
                            </span>
                          </td>
                          <td className="px-3 py-3">
                            <button
                              className="text-sm font-semibold text-cyan transition-colors hover:text-foreground"
                              type="button"
                              onClick={() => {
                                setExpandedCodeHistory(expandedCodeHistory === item.code ? null : item.code);
                              }}
                            >
                              {expandedCodeHistory === item.code ? '收起' : '展开'}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* 候选详情展开行 */}
            {expandedCodeHistory && historyDetail ? (() => {
            const item = historyDetail.candidates.find((c) => c.code === expandedCodeHistory);
            if (!item) return null;
            const factors = Object.entries(item.factorScores || {})
              .filter(([, value]) => typeof value === 'number')
              .sort((a, b) => Number(b[1]) - Number(a[1]));
            const topFactors = factors.slice(0, 8);
            return (
              <div className="rounded-xl border-2 border-cyan/20 bg-card p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <span className="font-mono text-cyan">{item.code}</span>
                    <span>{item.name || item.code}</span>
                    <span className="rounded-full bg-cyan/10 px-2 py-0.5 text-xs text-cyan">#{item.rank}</span>
                  </h3>
                  <button
                    className="text-xs text-secondary-text hover:text-foreground"
                    type="button"
                    onClick={() => setExpandedCodeHistory(null)}
                  >
                    收起
                  </button>
                </div>

                {/* 评分进度条 */}
                <div className="mb-4 grid grid-cols-4 gap-2">
                  <div className="rounded-lg border border-border bg-surface/50 px-3 py-2 text-center">
                    <span className="block text-xs text-secondary-text">综合分</span>
                    <span className="text-lg font-bold text-cyan">{formatNumber(item.score)}</span>
                  </div>
                  <div className="rounded-lg border border-border bg-surface/50 px-3 py-2 text-center">
                    <span className="block text-xs text-secondary-text">筛选分</span>
                    <span className="text-lg font-bold text-foreground">{formatNumber(item.screenScore)}</span>
                  </div>
                  <div className="rounded-lg border border-border bg-surface/50 px-3 py-2 text-center">
                    <span className="block text-xs text-secondary-text">LLM分</span>
                    <span className="text-lg font-bold text-foreground">{formatNumber(item.llmScore)}</span>
                  </div>
                  <div className="rounded-lg border border-border bg-surface/50 px-3 py-2 text-center">
                    <span className="block text-xs text-secondary-text">置信度</span>
                    <span className="text-lg font-bold text-foreground">
                      {item.llmConfidence != null ? `${(Number(item.llmConfidence) * 100).toFixed(0)}%` : '-'}
                    </span>
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
                  {/* 左栏：文本分析 */}
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs font-semibold text-secondary-text">推荐理由</p>
                      <p className="mt-1 text-sm leading-6 text-foreground whitespace-pre-wrap">{item.reason || '-'}</p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-secondary-text">LLM 判断</p>
                      <p className="mt-1 text-sm leading-6 text-foreground whitespace-pre-wrap">
                        {item.llmThesis || item.reason || '暂无 LLM 判断'}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-secondary-text">
                        <span>板块：<span className="text-foreground">{item.llmSector || '-'}</span></span>
                        <span>主题：<span className="text-foreground">{item.llmTheme || '-'}</span></span>
                        <span>风格：<span className="text-foreground">{item.llmStyleFit || '-'}</span></span>
                      </div>
                    </div>
                    {item.llmTags && item.llmTags.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-secondary-text">LLM 标签</p>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {item.llmTags.map((tag) => (
                            <span key={tag} className="rounded-full bg-cyan/10 px-2 py-0.5 text-xs text-cyan">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    <div>
                      <p className="text-xs font-semibold text-secondary-text">风险标签</p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {([...(item.riskFlags || []), ...(item.llmRisks || [])]).length
                          ? [...(item.riskFlags || []), ...(item.llmRisks || [])].map((r) => (
                            <span key={r} className="rounded-full bg-danger/10 px-2 py-0.5 text-xs text-danger">
                              {r}
                            </span>
                          ))
                          : <span className="text-xs text-secondary-text">无</span>}
                      </div>
                    </div>
                    {item.llmCatalysts && item.llmCatalysts.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-secondary-text">催化因素</p>
                        <ul className="mt-1 list-inside list-disc space-y-0.5 text-sm text-foreground">
                          {item.llmCatalysts.map((c, i) => <li key={i}>{c}</li>)}
                        </ul>
                      </div>
                    )}
                    {item.llmWatchItems && item.llmWatchItems.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-secondary-text">关注事项</p>
                        <ul className="mt-1 list-inside list-disc space-y-0.5 text-sm text-foreground">
                          {item.llmWatchItems.map((w, i) => <li key={i}>{w}</li>)}
                        </ul>
                      </div>
                    )}
                    {item.llmInvalidators && item.llmInvalidators.length > 0 && (
                      <div>
                        <p className="text-xs font-semibold text-secondary-text">失效条件</p>
                        <ul className="mt-1 list-inside list-disc space-y-0.5 text-sm text-foreground">
                          {item.llmInvalidators.map((inv, i) => <li key={i}>{inv}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>

                  {/* 右栏：因子与价格 */}
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs font-semibold text-secondary-text">因子得分 ({factors.length})</p>
                      {topFactors.length > 0 ? (
                        <div className="mt-2 space-y-1.5">
                          {topFactors.map(([key, value]) => {
                            const numVal = typeof value === 'number' ? value : 0;
                            const barWidth = Math.max(2, Math.min(100, Math.abs(numVal) * 50));
                            return (
                              <div key={key} className="flex items-center gap-2 text-xs">
                                <span className="w-24 shrink-0 truncate text-secondary-text" title={key}>{key}</span>
                                <div className="flex-1 h-1.5 overflow-hidden rounded-full bg-surface">
                                  <div
                                    className={`h-full rounded-full transition-all ${numVal >= 0 ? 'bg-cyan' : 'bg-danger'}`}
                                    style={{ width: `${barWidth}%` }}
                                  />
                                </div>
                                <span className="w-12 text-right font-mono text-foreground">{numVal.toFixed(2)}</span>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <p className="mt-1 text-sm text-secondary-text">无因子明细</p>
                      )}
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-secondary-text">价格信息</p>
                      <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                        <div className="rounded-lg border border-border bg-surface px-3 py-2">
                          <span className="block text-xs text-secondary-text">价格</span>
                          <span className="text-sm font-semibold text-foreground">{formatNumber(item.price)}</span>
                        </div>
                        <div className="rounded-lg border border-border bg-surface px-3 py-2">
                          <span className="block text-xs text-secondary-text">涨跌幅</span>
                          <span className={`text-sm font-semibold ${item.changePct != null && Number(item.changePct) >= 0 ? 'text-success' : 'text-danger'}`}>
                            {item.changePct != null ? `${Number(item.changePct) >= 0 ? '+' : ''}${Number(item.changePct).toFixed(2)}%` : '-'}
                          </span>
                        </div>
                        <div className="rounded-lg border border-border bg-surface px-3 py-2">
                          <span className="block text-xs text-secondary-text">成交额</span>
                          <span className="text-sm font-semibold text-foreground">{formatAmount(item.amount)}</span>
                        </div>
                        <div className="rounded-lg border border-border bg-surface px-3 py-2">
                          <span className="block text-xs text-secondary-text">行业</span>
                          <span className="text-sm font-semibold text-foreground">{item.industry || '-'}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })() : null}
          </div>
        ) : null}
      </Drawer>

      {/* 因子介绍面板 */}
      <Drawer
        isOpen={showFactorIntro}
        onClose={() => setShowFactorIntro(false)}
        title="因子介绍"
        width="max-w-3xl"
      >
        <div className="space-y-4 text-sm leading-6">
          <p className="text-secondary-text">
            AlphaSift 选股系统使用多因子模型对股票进行评估。以下是各因子的详细说明：
          </p>
          <div className="space-y-3">
            {FACTOR_INTROS.map((factor) => (
              <div key={factor.name} className="rounded-xl border border-border bg-card p-4">
                <div className="mb-2 flex items-center gap-2">
                  <span className="font-mono text-xs text-cyan">{factor.name}</span>
                  <span className="rounded-full bg-cyan/10 px-2 py-0.5 text-xs font-semibold text-cyan">
                    {factor.weight}
                  </span>
                </div>
                <p className="font-semibold text-foreground">{factor.title}</p>
                <p className="mt-1 text-secondary-text">{factor.description}</p>
                {factor.how_it_works && (
                  <div className="mt-2 rounded-lg bg-surface p-3">
                    <p className="text-xs font-semibold text-secondary-text">计算方式</p>
                    <p className="mt-1 text-xs leading-5 text-secondary-text">{factor.how_it_works}</p>
                  </div>
                )}
                {factor.signal && (
                  <div className="mt-2 flex items-center gap-2 text-xs">
                    <span className="text-secondary-text">信号方向：</span>
                    <span className="font-semibold text-success">{factor.signal.high === '买入' ? '↑' : '↓'}</span>
                    <span>{factor.signal.high} / {factor.signal.low}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="rounded-xl border border-warning/30 bg-warning/5 p-4">
            <p className="text-xs font-semibold text-warning">注意事项</p>
            <ul className="mt-2 list-inside space-y-1 text-xs text-secondary-text">
              <li>因子分数经过标准化处理，不同因子之间可能具有不同的量纲</li>
              <li>综合评分采用加权平均方式计算，权重由模型动态调整</li>
              <li>因子表现可能随市场环境变化而波动，建议结合多个时间窗口观察</li>
              <li>本系统仅供参考，不构成投资建议</li>
            </ul>
          </div>
        </div>
      </Drawer>
    </AppPage>
  );
};

export default StockScreeningPage;
