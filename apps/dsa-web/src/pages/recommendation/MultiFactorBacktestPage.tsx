import React, { useEffect, useMemo } from 'react';
import { GitBranch, TrendingUp, BarChart3, Target, AlertTriangle } from 'lucide-react';
import { AppPage, PageHeader, Card, StatCard, Badge } from '../../components/common';
import { recommendationApi } from '../../api/recommendation';
import { useRecommendationData } from '../../hooks/useRecommendationData';
import type { MultiFactorBacktestResponse } from '../../api/recommendation';

const MultiFactorBacktestPage: React.FC = () => {
  useEffect(() => { document.title = '多因子策略回测 - DSA'; }, []);

  const { data, isLoading: loading, error } = useRecommendationData<MultiFactorBacktestResponse>({
    queryKey: ['recommendation', 'multi-factor-backtest'],
    queryFn: () => recommendationApi.getMultiFactorBacktest(),
  });

  const effectiveFactors = useMemo(() => (data?.factors ?? []).filter((f) => f.status === '有效'), [data]);
  const avgIC = useMemo(() => {
    const ef = effectiveFactors.filter((f) => f.ic != null);
    return ef.length > 0 ? (ef.reduce((s, f) => s + Math.abs(f.ic!), 0) / ef.length).toFixed(3) : '—';
  }, [effectiveFactors]);
  const totalReturn = useMemo(() => {
    const nav = data?.navCurve ?? [];
    if (nav.length < 2) return '0';
    return ((nav[nav.length - 1].nav - nav[0].nav) / nav[0].nav * 100).toFixed(2);
  }, [data]);
  const bestSharpe = useMemo(() => {
    const sharpes = (data?.factors ?? []).map((f) => f.sharpe).filter((s) => s != null) as number[];
    return sharpes.length ? Math.max(...sharpes).toFixed(2) : '—';
  }, [data]);

  if (loading) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">加载中...</div></AppPage>;
  if (error) return <AppPage className="flex items-center justify-center"><Card variant="bordered" padding="md" className="max-w-md text-center"><AlertTriangle className="w-8 h-8 text-warning mx-auto mb-3" /><p className="text-sm text-muted-foreground">{error?.message ?? '加载失败'}</p></Card></AppPage>;
  if (!data) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">暂无数据</div></AppPage>;

  const factors = data.factors;
  const navCurve = data.navCurve;

  return (
    <AppPage className="space-y-5">
      <PageHeader eyebrow="Multi-Factor Backtest" title="多因子策略回测" description="Alpha因子IC/IR表现及策略净值曲线展示" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="有效因子" value={`${effectiveFactors.length}个`} tone="success" icon={<GitBranch className="w-4 h-4" />} />
        <StatCard label="平均|IC|" value={avgIC} tone="primary" icon={<BarChart3 className="w-4 h-4" />} />
        <StatCard label="累计收益" value={`${totalReturn}%`} tone={Number(totalReturn) > 0 ? 'success' : 'danger'} icon={<TrendingUp className="w-4 h-4" />} />
        <StatCard label="最佳夏普" value={bestSharpe} tone="primary" icon={<Target className="w-4 h-4" />} />
      </div>

      <Card title="因子表现矩阵" subtitle="IC / IR / RankIC / 胜率 / 夏普" variant="bordered" padding="md">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/50 text-xs text-muted-foreground">
                <th className="text-left py-2 font-medium">因子</th>
                <th className="text-right py-2 font-medium">IC</th>
                <th className="text-right py-2 font-medium">IR</th>
                <th className="text-right py-2 font-medium">RankIC</th>
                <th className="text-right py-2 font-medium">胜率</th>
                <th className="text-right py-2 font-medium">夏普</th>
                <th className="text-center py-2 font-medium">状态</th>
                <th className="text-left py-2 font-medium">来源</th>
              </tr>
            </thead>
            <tbody>
              {factors.map((f) => {
                const ic = f.ic ?? 0;
                return (
                <tr key={f.name} className="border-b border-border/30 hover:bg-hover/40 transition-colors">
                  <td className="py-2.5 font-medium">{f.name}</td>
                  <td className={`py-2.5 text-right tabular-nums font-medium ${ic > 0 ? 'text-success' : 'text-danger'}`}>{f.ic != null ? (ic > 0 ? '+' : '') + ic.toFixed(3) : '—'}</td>
                  <td className={`py-2.5 text-right tabular-nums ${(f.ir ?? 0) > 0 ? 'text-success' : 'text-danger'}`}>{f.ir != null ? f.ir.toFixed(2) : '—'}</td>
                  <td className={`py-2.5 text-right tabular-nums ${(f.rankIc ?? 0) > 0 ? 'text-success' : 'text-danger'}`}>{f.rankIc != null ? ((f.rankIc > 0 ? '+' : '') + f.rankIc.toFixed(3)) : '—'}</td>
                  <td className="py-2.5 text-right tabular-nums">{f.winRate != null ? `${f.winRate}%` : '—'}</td>
                  <td className="py-2.5 text-right tabular-nums">{f.sharpe != null ? f.sharpe.toFixed(2) : '—'}</td>
                  <td className="py-2.5 text-center"><Badge variant={f.status === '有效' ? 'success' : 'warning'}>{f.status}</Badge></td>
                  <td className="py-2.5 text-xs text-muted-foreground">{f.source || ''}</td>
                </tr>
              )})}
            </tbody>
          </table>
        </div>
      </Card>

      {navCurve.length > 0 && (
        <Card title="策略净值曲线" variant="bordered" padding="md">
          <div className="flex items-end gap-1 h-32">
            {navCurve.map((n) => {
              const maxNav = Math.max(...navCurve.map((x) => x.nav));
              const minNav = Math.min(...navCurve.map((x) => x.nav));
              return (
                <div key={n.date} className="flex-1 flex flex-col items-center justify-end">
                  <div
                    className={`w-full rounded-t ${n.nav >= 1 ? 'bg-success/50' : 'bg-danger/50'}`}
                    style={{ height: `${((n.nav - minNav) / (maxNav - minNav || 1)) * 100}%`, maxWidth: '20px' }}
                  />
                </div>
              );
            })}
          </div>
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            {navCurve.filter((_, i) => i % 5 === 0).map((n) => <span key={n.date}>{n.date}</span>)}
          </div>
        </Card>
      )}
    </AppPage>
  );
};

export default MultiFactorBacktestPage;
