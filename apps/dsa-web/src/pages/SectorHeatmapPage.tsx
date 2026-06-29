import React, { useEffect, useMemo, useState, useCallback } from 'react';
import {
  TrendingUp, BarChart3, Search, ArrowRightLeft,
  Zap, Target, Activity, RefreshCw, AlertTriangle, Loader2,
  Flame, ArrowRight,
} from 'lucide-react';
import { AppPage, PageHeader, Card, SectorHeatmap, Badge, MoneyFlowBar } from '../components/common';
import { cn } from '../utils/cn';
import type { SectorHeatItem } from '../components/common/SectorHeatmap';
import type { MoneyFlowItem } from '../components/common/MoneyFlowBar';
import { sentimentApi } from '../api/sentiment';
import type { SectorHeatmapResponse, SectorHeatmapItem, RotationSignal } from '../api/sentiment';

// ============ 工具函数 ============

const TREND_LABELS: Record<string, string> = {
  accelerating: '加速上涨',
  steady: '走势平稳',
  cooling: '逐步降温',
  reversing: '趋势转向',
};

const TREND_COLORS: Record<string, string> = {
  accelerating: 'text-amber-400 bg-amber-400/10 border-amber-400/30',
  steady: 'text-muted-foreground bg-muted/40 border-muted/30',
  cooling: 'text-blue-400 bg-blue-400/10 border-blue-400/30',
  reversing: 'text-danger bg-danger/10 border-danger/30',
};

const CONFIDENCE_COLORS: Record<string, string> = {
  '高': 'bg-success/10 text-success border-success/30',
  '中': 'bg-amber-400/10 text-amber-400 border-amber-400/30',
  '低': 'bg-muted/40 text-muted-foreground border-muted/30',
};

// ============ 组件 ============

const SectorHeatmapPage: React.FC = () => {
  useEffect(() => {
    document.title = '热力图 - DSA';
  }, []);

  const [data, setData] = useState<SectorHeatmapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<'change' | 'volume' | 'flow' | 'trend'>('change');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSector, setSelectedSector] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await sentimentApi.getSectorHeatmap();
      setData(result);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '获取数据失败';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // 转换为 SectorHeatItem
  const heatmapItems = useMemo<SectorHeatItem[]>(() => {
    if (!data?.sectors) return [];
    return data.sectors.map((s: SectorHeatmapItem) => ({
      name: s.sector,
      changePct: s.changePct,
      volume: Math.abs(s.netInflow), // 用净流入的绝对值做成交额参考
      stockCount: s.limitUpCount > 0 ? s.limitUpCount : undefined,
      trend: s.trend,
      trendScore: s.trendScore,
      mainline: s.mainline,
    }));
  }, [data]);

  // 转换为 MoneyFlowItem
  const moneyFlowItems = useMemo<MoneyFlowItem[]>(() => {
    if (!data?.sectors) return [];
    return data.sectors
      .sort((a, b) => Math.abs(b.netInflow) - Math.abs(a.netInflow))
      .slice(0, 10)
      .map((s) => ({
        name: s.sector,
        amount: s.netInflow,
        changePct: s.changePct,
      }));
  }, [data]);

  // 排序+搜索
  const sortedSectors = useMemo(() => {
    let filtered = heatmapItems;
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      filtered = filtered.filter((s) => s.name.toLowerCase().includes(q));
    }
    return [...filtered].sort((a, b) => {
      switch (sortMode) {
        case 'change':
          return Math.abs(b.changePct) - Math.abs(a.changePct);
        case 'volume':
          return (b.volume ?? 0) - (a.volume ?? 0);
        case 'flow':
          return Math.abs(b.changePct) - Math.abs(a.changePct); // 资金流排序在 MoneyFlow 组件中
        case 'trend':
          return Math.abs(b.trendScore ?? 0) - Math.abs(a.trendScore ?? 0);
        default:
          return 0;
      }
    });
  }, [heatmapItems, sortMode, searchQuery]);


  // 选中板块的详情
  const selectedSectorData = useMemo(() => {
    if (!selectedSector || !data?.sectors) return null;
    return data.sectors.find((s) => s.sector === selectedSector) ?? null;
  }, [selectedSector, data]);

  // ── Loading 状态 ──
  if (loading) {
    return (
      <AppPage className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="w-8 h-8 animate-spin" />
          <span className="text-sm">正在获取板块热力图数据...</span>
        </div>
      </AppPage>
    );
  }

  // ── Error 状态 ──
  if (error) {
    return (
      <AppPage className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4 text-muted-foreground">
          <AlertTriangle className="w-10 h-10 text-danger" />
          <span className="text-sm">{error}</span>
          <button
            onClick={fetchData}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-primary/10 text-primary text-sm hover:bg-primary/20 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            重试
          </button>
        </div>
      </AppPage>
    );
  }

  // ── 空数据状态 ──
  if (!data || data.sectors.length === 0) {
    return (
      <AppPage className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <BarChart3 className="w-10 h-10" />
          <span className="text-sm">暂无板块热力图数据</span>
          <button
            onClick={fetchData}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-primary/10 text-primary text-sm hover:bg-primary/20 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            刷新
          </button>
        </div>
      </AppPage>
    );
  }

  const summary = data.summary;

  return (
    <AppPage className="space-y-5">
      <PageHeader
        eyebrow="Sector Heatmap"
        title="热力图"
        description="实时监控各板块涨跌幅和资金流向，分析趋势变化，推测下一日资金动向。"
        actions={
          <button
            onClick={fetchData}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-muted/40 hover:bg-muted/60 text-xs text-muted-foreground transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            刷新
          </button>
        }
      />

      {/* ========== 市场总览卡片 ========== */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card variant="bordered" padding="sm" className="text-center">
          <div className="text-2xl font-bold text-success">{summary.upCount}</div>
          <div className="text-[10px] text-muted-foreground mt-0.5">上涨板块</div>
        </Card>
        <Card variant="bordered" padding="sm" className="text-center">
          <div className="text-2xl font-bold text-danger">{summary.downCount}</div>
          <div className="text-[10px] text-muted-foreground mt-0.5">下跌板块</div>
        </Card>
        <Card variant="bordered" padding="sm" className="text-center">
          <div className={cn(
            'text-2xl font-bold',
            summary.totalNetInflow > 0 ? 'text-success' : 'text-danger'
          )}>
            {summary.totalNetInflow > 0 ? '+' : ''}{summary.totalNetInflow.toFixed(1)}
          </div>
          <div className="text-[10px] text-muted-foreground mt-0.5">资金净流入(亿)</div>
        </Card>
        <Card variant="bordered" padding="sm" className="text-center">
          <div className="text-sm font-bold text-amber-400 truncate px-1" title={summary.hotMoneyDirection}>
            {summary.hotMoneyDirection}
          </div>
          <div className="text-[10px] text-muted-foreground mt-0.5">热点方向</div>
        </Card>
      </div>

      {/* ========== 市场情绪 & 轮动信号 ========== */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Card variant="bordered" padding="sm">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-primary" />
            <span className="text-xs font-medium">市场情绪</span>
            <Badge
              variant={summary.marketSentiment === '偏多' ? 'success' : summary.marketSentiment === '偏空' ? 'danger' : 'default'}
              size="sm"
            >
              {summary.marketSentiment}
            </Badge>
          </div>
        </Card>
        <Card variant="bordered" padding="sm">
          <div className="flex items-center gap-2">
            <ArrowRightLeft className="w-4 h-4 text-amber-400" />
            <span className="text-xs font-medium">轮动信号</span>
            <span className="text-xs text-muted-foreground truncate">
              {summary.rotationSignal}
            </span>
          </div>
        </Card>
      </div>

      {/* ========== 排序 + 搜索 ========== */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="搜索板块..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input-surface h-9 rounded-xl border bg-transparent pl-8 pr-3 text-xs transition-all focus:outline-none"
          />
        </div>
        {([
          { key: 'change', label: '按涨跌幅' },
          { key: 'trend', label: '按趋势变化' },
          { key: 'volume', label: '按成交额' },
        ] as const).map((s) => (
          <button
            key={s.key}
            type="button"
            onClick={() => setSortMode(s.key)}
            className={`rounded-full px-3 py-1 text-xs transition-colors ${
              sortMode === s.key
                ? 'bg-primary/15 text-primary border border-primary/30'
                : 'bg-muted/40 text-muted-foreground border border-transparent hover:bg-muted/60'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* ========== 两列：热力图 + 资金流向 ========== */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card
          title={
            <span className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-primary" />
              板块涨跌分布
            </span>
          }
          subtitle={`共 ${sortedSectors.length} 个板块`}
          variant="bordered"
          padding="md"
        >
          <SectorHeatmap items={sortedSectors} showTrend />
        </Card>

        <Card
          title={
            <span className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary" />
              资金流向排行
            </span>
          }
          subtitle="今日主力资金净流入/流出 TOP10"
          variant="bordered"
          padding="md"
        >
          <MoneyFlowBar items={moneyFlowItems} maxBars={10} />
        </Card>
      </div>

      {/* ========== 趋势变化分析 ========== */}
      <Card
        title={
          <span className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-amber-400" />
            板块趋势变化
          </span>
        }
        subtitle="对比前日数据，识别加速上涨/降温/转向信号"
        variant="bordered"
        padding="md"
      >
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {(['accelerating', 'steady', 'cooling', 'reversing'] as const).map((trend) => {
            const count = data.sectors.filter((s) => s.trend === trend).length;
            return (
              <div
                key={trend}
                className={cn(
                  'rounded-lg border px-3 py-2 text-center',
                  TREND_COLORS[trend]
                )}
              >
                <div className="text-lg font-bold">{count}</div>
                <div className="text-[10px]">{TREND_LABELS[trend]}</div>
              </div>
            );
          })}
        </div>

        {/* 趋势变化显著的板块列表 */}
        <div className="mt-3 space-y-1.5">
          {data.sectors
            .filter((s) => s.trend === 'accelerating' || s.trend === 'reversing')
            .sort((a, b) => Math.abs(b.trendScore) - Math.abs(a.trendScore))
            .slice(0, 6)
            .map((s) => (
              <div
                key={s.sector}
                className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-muted/20 hover:bg-muted/40 cursor-pointer transition-colors"
                onClick={() => setSelectedSector(s.sector === selectedSector ? null : s.sector)}
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium">{s.sector}</span>
                  <Badge
                    variant={s.trend === 'accelerating' ? 'success' : 'danger'}
                    size="sm"
                  >
                    {TREND_LABELS[s.trend]}
                  </Badge>
                </div>
                <span className={cn(
                  'text-xs font-mono',
                  s.trendScore > 0 ? 'text-success' : 'text-danger'
                )}>
                  {s.trendScore > 0 ? '+' : ''}{s.trendScore.toFixed(2)}%
                </span>
              </div>
            ))}
        </div>
      </Card>

      {/* ========== 资金流向推测 ========== */}
      <Card
        title={
          <span className="flex items-center gap-2">
            <Target className="h-4 w-4 text-primary" />
            资金流向推测
          </span>
        }
        subtitle="基于趋势变化、资金流向和板块强度，推测下一日资金动向"
        variant="bordered"
        padding="md"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {data.sectors
            .filter((s) => s.flowPrediction.direction !== '观望')
            .sort((a, b) => b.flowPrediction.nextDayProbability - a.flowPrediction.nextDayProbability)
            .slice(0, 6)
            .map((s) => (
              <div
                key={s.sector}
                className={cn(
                  'rounded-xl border p-3 cursor-pointer transition-all hover:shadow-sm',
                  selectedSector === s.sector ? 'border-primary/50 bg-primary/5' : 'border-border/50'
                )}
                onClick={() => setSelectedSector(s.sector === selectedSector ? null : s.sector)}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">{s.sector}</span>
                  <Badge
                    className={CONFIDENCE_COLORS[s.flowPrediction.confidence] || 'bg-muted/40'}
                    size="sm"
                  >
                    {s.flowPrediction.confidence}置信度
                  </Badge>
                </div>
                <div className="flex items-center gap-2 mb-1.5">
                  <Badge
                    variant={s.flowPrediction.direction.includes('流入') ? 'success' : 'danger'}
                    size="sm"
                  >
                    {s.flowPrediction.direction}
                  </Badge>
                  <span className="text-[10px] text-muted-foreground">
                    概率 {Math.round(s.flowPrediction.nextDayProbability * 100)}%
                  </span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
                  {s.flowPrediction.reason}
                </p>
                <div className="flex items-center gap-3 mt-2 pt-2 border-t border-border/30">
                  <span className={cn('text-xs font-mono', s.changePct > 0 ? 'text-success' : 'text-danger')}>
                    涨跌 {s.changePct > 0 ? '+' : ''}{s.changePct.toFixed(2)}%
                  </span>
                  <span className={cn('text-xs font-mono', s.netInflow > 0 ? 'text-success' : 'text-danger')}>
                    资金 {s.netInflow > 0 ? '+' : ''}{s.netInflow.toFixed(1)}亿
                  </span>
                  {s.mainline && (
                    <span className="flex items-center gap-0.5 text-[10px] text-amber-400">
                      <Flame className="w-2.5 h-2.5" />
                      主线
                    </span>
                  )}
                </div>
              </div>
            ))}
        </div>
      </Card>

      {/* ========== 板块轮动信号 ========== */}
      {data.rotations && data.rotations.length > 0 && (
        <Card
          title={
            <span className="flex items-center gap-2">
              <ArrowRightLeft className="h-4 w-4 text-amber-400" />
              资金轮动信号
            </span>
          }
          subtitle="检测资金从高位板块向低位板块迁移的轮动信号"
          variant="bordered"
          padding="md"
        >
          <div className="space-y-2">
            {data.rotations.map((r: RotationSignal, idx: number) => (
              <div
                key={idx}
                className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-muted/20"
              >
                {/* 流出 */}
                <div className="flex flex-col items-end min-w-0 flex-1">
                  <span className="text-xs font-medium truncate max-w-full">{r.fromSector}</span>
                  <span className="text-[10px] text-danger">
                    {r.fromFlow > 0 ? '+' : ''}{r.fromFlow.toFixed(1)}亿
                  </span>
                </div>

                {/* 箭头 + 信号 */}
                <div className="flex flex-col items-center flex-shrink-0">
                  <ArrowRight className="w-4 h-4 text-muted-foreground" />
                  <Badge
                    variant={r.signal === 'high' ? 'danger' : r.signal === 'medium' ? 'warning' : 'default'}
                    size="sm"
                    className="mt-0.5"
                  >
                    {r.signal === 'high' ? '强信号' : r.signal === 'medium' ? '中等' : '弱'}
                  </Badge>
                </div>

                {/* 流入 */}
                <div className="flex flex-col items-start min-w-0 flex-1">
                  <span className="text-xs font-medium truncate max-w-full">{r.toSector}</span>
                  <span className="text-[10px] text-success">
                    {r.toFlow > 0 ? '+' : ''}{r.toFlow.toFixed(1)}亿
                  </span>
                </div>

                {/* 转移量 */}
                <div className="flex-shrink-0 text-right">
                  <span className="text-[10px] text-muted-foreground">
                    约{r.flowAmount.toFixed(1)}亿
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ========== 选中板块详情弹层 ========== */}
      {selectedSectorData && (
        <Card
          variant="bordered"
          padding="md"
          className="border-primary/30 bg-primary/[0.02]"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold">{selectedSectorData.sector}</span>
              <Badge
                variant={selectedSectorData.changePct > 0 ? 'success' : 'danger'}
                size="sm"
              >
                {selectedSectorData.changePct > 0 ? '+' : ''}{selectedSectorData.changePct.toFixed(2)}%
              </Badge>
              {selectedSectorData.mainline && (
                <Badge variant="warning" size="sm">
                  <Flame className="w-2.5 h-2.5 mr-0.5" />
                  主线
                </Badge>
              )}
            </div>
            <button
              onClick={() => setSelectedSector(null)}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              关闭
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div>
              <span className="text-muted-foreground">强度评分</span>
              <div className="font-bold text-sm">{selectedSectorData.strength.toFixed(1)}</div>
            </div>
            <div>
              <span className="text-muted-foreground">涨停数</span>
              <div className="font-bold text-sm">{selectedSectorData.limitUpCount}</div>
            </div>
            <div>
              <span className="text-muted-foreground">连续上榜</span>
              <div className="font-bold text-sm">{selectedSectorData.consecutiveDays}天</div>
            </div>
            <div>
              <span className="text-muted-foreground">趋势</span>
              <div className={cn('font-bold text-sm', TREND_COLORS[selectedSectorData.trend]?.split(' ')[0])}>
                {TREND_LABELS[selectedSectorData.trend]}
              </div>
            </div>
          </div>

          {/* 资金流向推测详情 */}
          <div className="mt-3 p-3 rounded-lg bg-muted/20">
            <div className="flex items-center gap-2 mb-1">
              <Target className="w-3.5 h-3.5 text-primary" />
              <span className="text-xs font-medium">下一日资金推测</span>
            </div>
            <div className="flex items-center gap-2 mb-1.5">
              <Badge
                variant={selectedSectorData.flowPrediction.direction.includes('流入') ? 'success' : 'danger'}
                size="sm"
              >
                {selectedSectorData.flowPrediction.direction}
              </Badge>
              <span className="text-[11px] text-muted-foreground">
                置信度: {selectedSectorData.flowPrediction.confidence} · 概率: {Math.round(selectedSectorData.flowPrediction.nextDayProbability * 100)}%
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              {selectedSectorData.flowPrediction.reason}
            </p>
          </div>

          {/* 板块内个股 */}
          {selectedSectorData.stocks && selectedSectorData.stocks.length > 0 && (
            <div className="mt-3">
              <div className="text-xs font-medium mb-1.5">板块内个股</div>
              <div className="flex flex-wrap gap-1.5">
                {selectedSectorData.stocks.map((stock) => (
                  <span
                    key={stock.code}
                    className={cn(
                      'inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] border',
                      stock.isLeader
                        ? 'bg-amber-400/10 border-amber-400/30 text-amber-400'
                        : 'bg-muted/20 border-border/30 text-muted-foreground'
                    )}
                  >
                    {stock.name}
                    <span className={stock.changePct > 0 ? 'text-success' : 'text-danger'}>
                      {stock.changePct > 0 ? '+' : ''}{stock.changePct.toFixed(1)}%
                    </span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}
    </AppPage>
  );
};

export default SectorHeatmapPage;
