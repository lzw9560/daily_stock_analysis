import React, { useEffect, useMemo } from 'react';
import { PieChart, TrendingUp, TrendingDown, AlertTriangle, ArrowRightLeft, Brain } from 'lucide-react';
import { AppPage, PageHeader, Card, StatCard, Badge } from '../../components/common';
import { recommendationApi } from '../../api/recommendation';
import { useRecommendationData } from '../../hooks/useRecommendationData';
import type { PositionAdviceResponse } from '../../api/recommendation';

const ADVICE_CONFIG: Record<string, { variant: 'success' | 'warning' | 'danger' | 'info' }> = {
  '持有': { variant: 'success' },
  '加仓': { variant: 'info' },
  '观察': { variant: 'warning' },
  '止盈减仓': { variant: 'warning' },
  '止损清仓': { variant: 'danger' },
};

const PositionAdvicePage: React.FC = () => {
  useEffect(() => { document.title = '持仓建议 - DSA'; }, []);

  const { data, isLoading: loading, error } = useRecommendationData<PositionAdviceResponse>({
    queryKey: ['recommendation', 'position-advice'],
    queryFn: () => recommendationApi.getPositionAdvice(),
  });

  const portfolio = data?.portfolio ?? [];
  const totalWeight = data?.totalWeight ?? portfolio.reduce((s, p) => s + (p.weight ?? 0), 0);
  const totalPnl = useMemo(() => {
    const totalCost = portfolio.reduce((s, p) => s + (p.costPrice ?? 0) * (p.weight ?? 0), 0);
    const totalCurrent = portfolio.reduce((s, p) => s + (p.currentPrice ?? 0) * (p.weight ?? 0), 0);
    return totalCost > 0 ? ((totalCurrent - totalCost) / totalCost * 100).toFixed(2) : '0';
  }, [portfolio]);
  const actionItems = useMemo(() => portfolio.filter((p) => (p.advice ?? '持有') !== '持有'), [portfolio]);
  const profitCount = useMemo(() => portfolio.filter((p) => (p.pnl ?? 0) > 0).length, [portfolio]);
  const lossCount = useMemo(() => portfolio.filter((p) => (p.pnl ?? 0) < 0).length, [portfolio]);

  if (loading) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">加载中...</div></AppPage>;
  if (error) return <AppPage className="flex items-center justify-center"><Card variant="bordered" padding="md" className="max-w-md text-center"><AlertTriangle className="w-8 h-8 text-warning mx-auto mb-3" /><p className="text-sm text-muted-foreground">{error?.message ?? '加载失败'}</p></Card></AppPage>;
  if (!data) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">暂无数据</div></AppPage>;

  return (
    <AppPage className="space-y-5">
      <PageHeader eyebrow="Position Advice" title="持仓建议" description="持仓优化操作 — 调仓信号、仓位再平衡与止盈止损" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="总仓位" value={`${(totalWeight ?? 0).toFixed(0)}%`} tone={(totalWeight ?? 0) > 60 ? 'warning' : 'success'} icon={<PieChart className="w-4 h-4" />} />
        <StatCard label="持仓盈亏" value={`${Number(totalPnl) > 0 ? '+' : ''}${totalPnl}%`} tone={Number(totalPnl) > 0 ? 'success' : 'danger'} icon={<TrendingUp className="w-4 h-4" />} />
        <StatCard label="盈利品种" value={`${profitCount} 个`} tone="success" icon={<TrendingUp className="w-4 h-4" />} />
        <StatCard label="亏损品种" value={`${lossCount} 个`} tone="danger" icon={<TrendingDown className="w-4 h-4" />} />
      </div>

          {data.marketSentimentPhase && (
        <Card variant="bordered" padding="md">
          <div className="flex items-center gap-3 text-sm">
            <Brain className="w-5 h-5 text-primary" />
            <span className="text-muted-foreground">市场情绪阶段：</span>
            <Badge variant={(data.marketSentimentPhase ?? '').includes('高潮') ? 'success' : (data.marketSentimentPhase ?? '').includes('修复') ? 'info' : (data.marketSentimentPhase ?? '').includes('冰点') ? 'danger' : 'warning'}>
              {data.marketSentimentPhase}
            </Badge>
            <span className="text-muted-foreground ml-4">建议总仓位：</span>
            <span className="font-semibold text-foreground">{data.suggestedTotalPosition ?? '30-50%'}</span>
          </div>
        </Card>
      )}

      {actionItems.length > 0 && (
        <Card title="待操作项" subtitle={`${actionItems.length} 项需要关注`} variant="gradient" padding="md">
          <div className="space-y-2">
            {actionItems.map((p) => {
              const pnl = p.pnl ?? 0;
              const advice = p.advice ?? '持有';
              return (
              <div key={p.code} className="flex items-center justify-between rounded-lg bg-base/50 p-3">
                <div className="flex items-center gap-3">
                  <Badge variant={ADVICE_CONFIG[advice]?.variant ?? 'info'}>{advice}</Badge>
                  <div>
                    <span className="font-medium text-sm">{p.name}</span>
                    <span className="text-xs text-muted-foreground ml-1">{p.code}</span>
                    {p.adviceReason && <p className="text-xs text-muted-foreground mt-0.5">{p.adviceReason}</p>}
                  </div>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-muted-foreground">当前权重: <span className="font-medium text-foreground">{p.weight ?? 0}%</span></span>
                  <span className="text-muted-foreground">目标权重: <span className="font-medium text-foreground">{p.targetWeight ?? 0}%</span></span>
                  {p.atrPct != null && <span className="text-muted-foreground">ATR: <span className="font-medium text-foreground">{p.atrPct}%</span></span>}
                  <span className={`font-medium ${pnl > 0 ? 'text-success' : 'text-danger'}`}>
                    {pnl > 0 ? '+' : ''}{pnl}%
                  </span>
                </div>
              </div>
              );
            })}
          </div>
        </Card>
      )}

      <Card title="持仓明细" subtitle={`共 ${portfolio.length} 个标的 · ${data.tradeDate}`} variant="bordered" padding="md">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/50 text-xs text-muted-foreground">
                <th className="text-left py-2 font-medium">股票</th>
                <th className="text-right py-2 font-medium">权重</th>
                <th className="text-right py-2 font-medium">成本价</th>
                <th className="text-right py-2 font-medium">现价</th>
                <th className="text-right py-2 font-medium">盈亏</th>
                <th className="text-center py-2 font-medium">建议</th>
                <th className="text-right py-2 font-medium">目标权重</th>
                <th className="text-right py-2 font-medium">偏差</th>
                <th className="text-left py-2 font-medium">入场信号</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.map((p) => {
                const pnl = p.pnl ?? 0;
                const costPrice = p.costPrice ?? 0;
                const currentPrice = p.currentPrice ?? 0;
                const weight = p.weight ?? 0;
                const targetWeight = p.targetWeight ?? 0;
                const diff = p.diff ?? 0;
                const advice = p.advice ?? '持有';
                return (
                <tr key={p.code} className="border-b border-border/30 hover:bg-hover/40 transition-colors">
                  <td className="py-2.5 font-medium">{p.name}<span className="text-xs text-muted-foreground ml-1">{p.code}</span></td>
                  <td className="py-2.5 text-right tabular-nums">
                    <div className="flex items-center justify-end gap-1.5">
                      <div className="w-12 h-1.5 bg-muted/40 rounded-full overflow-hidden">
                        <div className="h-full rounded-full bg-primary/60" style={{ width: `${Math.min(weight / 15 * 100, 100)}%` }} />
                      </div>
                      <span className="text-xs">{weight}%</span>
                    </div>
                  </td>
                  <td className="py-2.5 text-right tabular-nums">{costPrice.toFixed(2)}</td>
                  <td className="py-2.5 text-right tabular-nums">{currentPrice.toFixed(2)}</td>
                  <td className={`py-2.5 text-right tabular-nums font-medium ${pnl > 0 ? 'text-success' : 'text-danger'}`}>{pnl > 0 ? '+' : ''}{pnl}%</td>
                  <td className="py-2.5 text-center"><Badge variant={ADVICE_CONFIG[advice]?.variant ?? 'info'}>{advice}</Badge></td>
                  <td className="py-2.5 text-right tabular-nums">{targetWeight}%</td>
                  <td className={`py-2.5 text-right tabular-nums ${Math.abs(diff) > 2 ? 'text-warning' : 'text-muted-foreground'}`}>{diff > 0 ? '+' : ''}{diff}%</td>
                  <td className="py-2.5 text-xs text-muted-foreground">
                    {p.entrySignals?.length ? p.entrySignals.join('、') : '—'}
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="再平衡汇总" variant="bordered" padding="md">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="rounded-lg border border-border/40 p-3">
            <div className="flex items-center gap-2 mb-2">
              <ArrowRightLeft className="w-4 h-4 text-info" />
              <span className="text-sm font-medium">调仓操作</span>
            </div>
            <div className="space-y-1 text-xs text-muted-foreground">
              {actionItems.length > 0
                ? actionItems.map((p) => (
                    <div key={p.code} className="flex justify-between">
                      <span>{p.name}</span>
                      <span className="font-medium">{p.advice}</span>
                    </div>
                  ))
                : <span>无需操作</span>}
            </div>
          </div>
          <div className="rounded-lg border border-border/40 p-3">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-success" />
              <span className="text-sm font-medium">止盈提醒</span>
            </div>
            <div className="space-y-1 text-xs text-muted-foreground">
              {portfolio.filter((p) => (p.pnl ?? 0) > 10).map((p) => (
                <div key={p.code} className="flex justify-between"><span>{p.name}</span><span className="text-success">+{p.pnl ?? 0}%</span></div>
              ))}
              {portfolio.filter((p) => (p.pnl ?? 0) > 10).length === 0 && <span>暂无止盈标的</span>}
            </div>
          </div>
          <div className="rounded-lg border border-border/40 p-3">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-danger" />
              <span className="text-sm font-medium">止损预警</span>
            </div>
            <div className="space-y-1 text-xs text-muted-foreground">
              {portfolio.filter((p) => (p.pnl ?? 0) < -10).map((p) => (
                <div key={p.code} className="flex justify-between"><span>{p.name}</span><span className="text-danger">{p.pnl ?? 0}%</span></div>
              ))}
              {portfolio.filter((p) => (p.pnl ?? 0) < -10).length === 0 && <span>暂无止损预警</span>}
            </div>
          </div>
        </div>
      </Card>
    </AppPage>
  );
};

export default PositionAdvicePage;
