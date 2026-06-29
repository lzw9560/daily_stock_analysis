import React, { useEffect, useMemo } from 'react';
import { TrendingUp, Target, BarChart3, AlertTriangle } from 'lucide-react';
import { AppPage, PageHeader, Card, StatCard, Badge } from '../../components/common';
import { recommendationApi } from '../../api/recommendation';
import { useRecommendationData } from '../../hooks/useRecommendationData';
import type { MidLongTermResponse } from '../../api/recommendation';

const VALUATION_COLORS: Record<string, 'success' | 'warning' | 'danger'> = {
  '低估': 'success',
  '合理偏低': 'success',
  '合理': 'warning',
  '偏高': 'danger',
  '高估': 'danger',
};

const MidLongTermPage: React.FC = () => {
  useEffect(() => { document.title = '中长线波段建仓 - DSA'; }, []);

  const { data, isLoading: loading, error } = useRecommendationData<MidLongTermResponse>({
    queryKey: ['recommendation', 'mid-long-term'],
    queryFn: () => recommendationApi.getMidLongTerm(),
  });

  const avgScore = useMemo(() => {
    const p = data?.positions ?? [];
    const valid = p.filter(x => x.score != null);
    return valid.length > 0 ? (valid.reduce((s, x) => s + (x.score ?? 0), 0) / valid.length).toFixed(0) : '0';
  }, [data]);
  const undervaluedCount = useMemo(() => (data?.positions ?? []).filter((p) => (p.valuation ?? '').includes('低估')).length, [data]);
  const avgUpside = useMemo(() => {
    const p = data?.positions ?? [];
    const valid = p.filter(x => x.price != null && x.price > 0 && x.targetPrice != null);
    if (valid.length === 0) return '0';
    return (valid.reduce((s, x) => s + ((x.targetPrice ?? 0) - (x.price ?? 0)) / (x.price ?? 1), 0) / valid.length * 100).toFixed(1);
  }, [data]);

  if (loading) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">加载中...</div></AppPage>;
  if (error) return <AppPage className="flex items-center justify-center"><Card variant="bordered" padding="md" className="max-w-md text-center"><AlertTriangle className="w-8 h-8 text-warning mx-auto mb-3" /><p className="text-sm text-muted-foreground">{error?.message ?? '加载失败'}</p></Card></AppPage>;
  if (!data) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">暂无数据</div></AppPage>;

  const positions = data.positions;

  return (
    <AppPage className="space-y-5">
      <PageHeader eyebrow="Mid-Long Term" title="中长线波段建仓" description="波段战法建仓 — 趋势确认、估值分位与中线持仓逻辑" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="备选标的" value={`${positions.length} 个`} tone="primary" icon={<Target className="w-4 h-4" />} />
        <StatCard label="低估品种" value={`${undervaluedCount} 个`} tone="success" icon={<TrendingUp className="w-4 h-4" />} />
        <StatCard label="平均评分" value={avgScore} tone="primary" icon={<BarChart3 className="w-4 h-4" />} />
        <StatCard label="平均上涨空间" value={`${avgUpside}%`} tone="success" icon={<TrendingUp className="w-4 h-4" />} />
      </div>

      {data.strategies.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {data.strategies.map((st) => (
            <Card key={st.name} variant="bordered" padding="sm">
              <div className="text-center space-y-1">
                <div className="text-xs text-muted-foreground">{st.name}</div>
                <div className="text-2xl font-bold">{st.count}</div>
                <div className="text-xs text-muted-foreground">{st.desc}</div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Card title="建仓标的详情" subtitle="估值、趋势与策略匹配" variant="bordered" padding="md">
        {positions.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground text-sm">暂无符合条件的建仓标的</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 text-xs text-muted-foreground">
                  <th className="text-left py-2 font-medium">股票</th>
                  <th className="text-right py-2 font-medium">现价</th>
                  <th className="text-right py-2 font-medium">估值</th>
                  <th className="text-right py-2 font-medium">PE(TTM)</th>
                  <th className="text-right py-2 font-medium">PB</th>
                  <th className="text-right py-2 font-medium">ROE</th>
                  <th className="text-right py-2 font-medium">目标价</th>
                  <th className="text-right py-2 font-medium">止损价</th>
                  <th className="text-right py-2 font-medium">上涨空间</th>
                  <th className="text-left py-2 font-medium">策略</th>
                  <th className="text-right py-2 font-medium">评分</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => {
                  const price = p.price ?? 0;
                  const upside = price > 0 ? (((p.targetPrice ?? 0) - price) / price * 100).toFixed(1) : '0';
                  const downside = price > 0 ? ((price - (p.stopLoss ?? 0)) / price * 100).toFixed(1) : '0';
                  const peTtm = (p as any).peTtm;
                  const pb = (p as any).pb;
                  const roe = (p as any).roe;
                  return (
                    <tr key={p.code} className="border-b border-border/30 hover:bg-hover/40 transition-colors">
                      <td className="py-2.5 font-medium">{p.name}<span className="text-xs text-muted-foreground ml-1">{p.code}</span></td>
                      <td className="py-2.5 text-right tabular-nums">{price.toFixed(2)}</td>
                      <td className="py-2.5 text-right"><Badge variant={VALUATION_COLORS[p.valuation] ?? 'info'}>{p.valuation || '—'}</Badge></td>
                      <td className="py-2.5 text-right tabular-nums text-muted-foreground">{peTtm != null && !isNaN(peTtm) ? peTtm.toFixed(1) : '—'}</td>
                      <td className="py-2.5 text-right tabular-nums text-muted-foreground">{pb != null && !isNaN(pb) ? pb.toFixed(2) : '—'}</td>
                      <td className="py-2.5 text-right tabular-nums text-muted-foreground">{roe != null && !isNaN(roe) ? `${roe.toFixed(1)}%` : '—'}</td>
                      <td className="py-2.5 text-right tabular-nums text-success">{(p.targetPrice ?? 0).toFixed(2)}</td>
                      <td className="py-2.5 text-right tabular-nums text-danger">{(p.stopLoss ?? 0).toFixed(2)}</td>
                      <td className="py-2.5 text-right tabular-nums">
                        <span className="text-success">{Number(upside) > 0 ? '+' : ''}{upside}%</span>
                        <span className="text-xs text-muted-foreground ml-1">/ -{downside}%</span>
                      </td>
                      <td className="py-2.5"><Badge variant="info">{p.strategy || '—'}</Badge></td>
                      <td className="py-2.5 text-right tabular-nums font-medium">{p.score ?? '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </AppPage>
  );
};

export default MidLongTermPage;
