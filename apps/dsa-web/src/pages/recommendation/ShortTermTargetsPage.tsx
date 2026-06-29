import React, { useEffect, useMemo } from 'react';
import { Zap, TrendingUp, Shield, BarChart3, AlertTriangle } from 'lucide-react';
import { AppPage, PageHeader, Card, StatCard, Badge } from '../../components/common';
import { recommendationApi } from '../../api/recommendation';
import { useRecommendationData } from '../../hooks/useRecommendationData';
import type { ShortTermTargetsResponse } from '../../api/recommendation';

const RATING_CONFIG: Record<string, { label: string; variant: 'success' | 'info' | 'warning' | 'danger' }> = {
  S: { label: 'S级', variant: 'success' },
  A: { label: 'A级', variant: 'info' },
  B: { label: 'B级', variant: 'warning' },
  C: { label: 'C级', variant: 'danger' },
};

const ShortTermTargetsPage: React.FC = () => {
  useEffect(() => { document.title = '短线打板标的 - DSA'; }, []);

  const { data, isLoading: loading, error } = useRecommendationData<ShortTermTargetsResponse>({
    queryKey: ['recommendation', 'short-term-targets'],
    queryFn: () => recommendationApi.getShortTermTargets(),
  });

  const sTargets = useMemo(() => (data?.targets ?? []).filter((t) => t.rating === 'S' || t.rating === 'A'), [data]);
  const avgSeal = useMemo(() => {
    const t = data?.targets ?? [];
    const valid = t.filter(x => x.sealStrength != null);
    return valid.length > 0 ? (valid.reduce((s, x) => s + (x.sealStrength ?? 0), 0) / valid.length).toFixed(0) : '0';
  }, [data]);
  const avgPremium = useMemo(() => {
    const t = data?.targets ?? [];
    const valid = t.filter(x => x.premiumRate != null);
    return valid.length > 0 ? (valid.reduce((s, x) => s + (x.premiumRate ?? 0), 0) / valid.length).toFixed(1) : '0';
  }, [data]);

  if (loading) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">加载中...</div></AppPage>;
  if (error) return <AppPage className="flex items-center justify-center"><Card variant="bordered" padding="md" className="max-w-md text-center"><AlertTriangle className="w-8 h-8 text-warning mx-auto mb-3" /><p className="text-sm text-muted-foreground">{error?.message ?? '加载失败'}</p></Card></AppPage>;
  if (!data) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">暂无数据</div></AppPage>;

  const targets = data.targets;

  return (
    <AppPage className="space-y-5">
      <PageHeader eyebrow="Short-term Targets" title="短线打板标的" description="打板战法选股 — 封板强度、溢价率与短线爆发力评估" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="S/A级标的" value={`${sTargets.length} 个`} tone="success" icon={<Zap className="w-4 h-4" />} />
        <StatCard label="平均封板强度" value={avgSeal} tone="primary" icon={<Shield className="w-4 h-4" />} />
        <StatCard label="平均溢价率" value={`${avgPremium}%`} tone="success" icon={<TrendingUp className="w-4 h-4" />} />
        <StatCard label="今日涨停家数" value={`${data.limitUpCount} 家`} tone="primary" icon={<BarChart3 className="w-4 h-4" />} />
      </div>

      <Card title="打板标的列表" subtitle="按封板强度排序" variant="bordered" padding="md">
        {targets.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground text-sm">今日暂无打板标的</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 text-xs text-muted-foreground">
                  <th className="text-left py-2 font-medium">股票</th>
                  <th className="text-right py-2 font-medium">现价</th>
                  <th className="text-right py-2 font-medium">涨幅</th>
                  <th className="text-center py-2 font-medium">评级</th>
                  <th className="text-right py-2 font-medium">封板强度</th>
                  <th className="text-right py-2 font-medium">封板时间</th>
                  <th className="text-right py-2 font-medium">溢价率</th>
                  <th className="text-left py-2 font-medium">逻辑</th>
                </tr>
              </thead>
              <tbody>
                {targets.map((t) => {
                  const rating = RATING_CONFIG[t.rating] ?? { label: t.rating ?? '—', variant: 'info' as const };
                  const price = t.price ?? 0;
                  const chg = t.changePct ?? 0;
                  const sealStr = t.sealStrength ?? 0;
                  const premium = t.premiumRate ?? 0;
                  return (
                    <tr key={t.code} className="border-b border-border/30 hover:bg-hover/40 transition-colors">
                      <td className="py-2.5 font-medium">{t.name}<span className="text-xs text-muted-foreground ml-1">{t.code}</span></td>
                      <td className="py-2.5 text-right tabular-nums">{price.toFixed(2)}</td>
                      <td className={`py-2.5 text-right tabular-nums font-medium ${chg > 0 ? 'text-success' : 'text-danger'}`}>{chg > 0 ? '+' : ''}{chg}%</td>
                      <td className="py-2.5 text-center"><Badge variant={rating.variant}>{rating.label}</Badge></td>
                      <td className="py-2.5 text-right tabular-nums">
                        <div className="flex items-center justify-end gap-1.5">
                          <div className="w-12 h-1.5 bg-muted/40 rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${sealStr >= 80 ? 'bg-success' : sealStr >= 60 ? 'bg-warning' : 'bg-danger'}`} style={{ width: `${sealStr}%` }} />
                          </div>
                          <span className="text-xs">{sealStr}</span>
                        </div>
                      </td>
                      <td className="py-2.5 text-right tabular-nums text-muted-foreground">{t.sealTime || '—'}</td>
                      <td className={`py-2.5 text-right tabular-nums font-medium ${premium > 0 ? 'text-success' : 'text-danger'}`}>{premium > 0 ? '+' : ''}{premium}%</td>
                      <td className="py-2.5 text-xs text-muted-foreground max-w-60 truncate">{t.reason || '—'}</td>
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

export default ShortTermTargetsPage;
