import React, { useEffect, useMemo } from 'react';
import { TrendingUp, TrendingDown, Minus, Activity, DollarSign, BarChart3, Zap, Gauge, AlertTriangle } from 'lucide-react';
import { AppPage, PageHeader, Card, StatCard, Badge } from '../../components/common';
import { recommendationApi } from '../../api/recommendation';
import { useRecommendationData } from '../../hooks/useRecommendationData';
import type { DailyReviewResponse } from '../../api/recommendation';

const DailyReviewPage: React.FC = () => {
  useEffect(() => { document.title = '每日复盘 - DSA'; }, []);

  const { data, isLoading: loading, error } = useRecommendationData<DailyReviewResponse>({
    queryKey: ['recommendation', 'daily-review'],
    queryFn: () => recommendationApi.getDailyReview(),
  });

  const upRatio = useMemo(() => {
    if (!data) return 0;
    const s = data.stats;
    const total = (s.upCount ?? 0) + (s.downCount ?? 0) + (s.flatCount ?? 0);
    return total > 0
      ? ((s.upCount ?? 0) / total * 100).toFixed(1)
      : '0';
  }, [data]);

  if (loading) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">加载中...</div></AppPage>;
  if (error) return <AppPage className="flex items-center justify-center"><Card variant="bordered" padding="md" className="max-w-md text-center"><AlertTriangle className="w-8 h-8 text-warning mx-auto mb-3" /><p className="text-sm text-muted-foreground">{error?.message ?? '加载失败'}</p></Card></AppPage>;
  if (!data) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">暂无数据</div></AppPage>;

  const s = data.stats;

  return (
    <AppPage className="space-y-5">
      <PageHeader eyebrow="Daily Review" title="每日复盘" description="当日数据汇总 — 涨跌统计、北向资金与龙虎榜复盘" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="上涨家数" value={`${s.upCount ?? 0} 家`} tone="success" icon={<TrendingUp className="w-4 h-4" />} />
        <StatCard label="下跌家数" value={`${s.downCount ?? 0} 家`} tone="danger" icon={<TrendingDown className="w-4 h-4" />} />
        <StatCard label="涨停 / 跌停" value={`${s.limitUp ?? 0} / ${s.limitDown ?? 0}`} tone="primary" icon={<Zap className="w-4 h-4" />} />
        <StatCard label="上涨比例" value={`${upRatio}%`} tone={Number(upRatio) > 50 ? 'success' : 'warning'} icon={<Activity className="w-4 h-4" />} />
        <StatCard label="北向资金" value={`${(s.northBoundNet ?? 0) > 0 ? '+' : ''}${(s.northBoundNet ?? 0).toFixed(1)} 亿`} tone={(s.northBoundNet ?? 0) > 0 ? 'success' : 'danger'} icon={<DollarSign className="w-4 h-4" />} />
        <StatCard label="成交额" value={`${(s.turnover ?? 0).toLocaleString()} 亿`} tone="primary" icon={<BarChart3 className="w-4 h-4" />} />
        <StatCard label="平收家数" value={`${s.flatCount ?? 0} 家`} tone="primary" icon={<Minus className="w-4 h-4" />} />
        <StatCard label="振幅" value={`${s.amplitude ?? 0}%`} tone="primary" icon={<Gauge className="w-4 h-4" />} />
      </div>

      {data.lhbTop.length > 0 && (
        <Card title="龙虎榜 TOP5" subtitle="机构 / 游资净买入" variant="bordered" padding="md">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 text-xs text-muted-foreground">
                  <th className="text-left py-2 font-medium">股票</th>
                  <th className="text-right py-2 font-medium">买入(亿)</th>
                  <th className="text-right py-2 font-medium">卖出(亿)</th>
                  <th className="text-right py-2 font-medium">净买入(亿)</th>
                  <th className="text-left py-2 font-medium">类型</th>
                </tr>
              </thead>
              <tbody>
                {data.lhbTop.map((item) => (
                  <tr key={item.code} className="border-b border-border/30 hover:bg-hover/40 transition-colors">
                    <td className="py-2.5 font-medium">{item.name}<span className="text-xs text-muted-foreground ml-1">{item.code}</span></td>
                    <td className="py-2.5 text-right tabular-nums">{item.buyAmount != null ? item.buyAmount.toFixed(2) : '—'}</td>
                    <td className="py-2.5 text-right tabular-nums">{item.sellAmount != null ? item.sellAmount.toFixed(2) : '—'}</td>
                    <td className={`py-2.5 text-right tabular-nums font-medium ${(item.netAmount ?? 0) > 0 ? 'text-success' : 'text-danger'}`}>
                      {item.netAmount != null ? ((item.netAmount > 0 ? '+' : '') + item.netAmount.toFixed(2)) : '—'}
                    </td>
                    <td className="py-2.5"><Badge variant={(item.reason?.includes('机构') ?? false) ? 'info' : 'warning'}>{item.reason || '—'}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {data.sectorLeaders.length > 0 && (
        <Card title="领涨板块及龙头" variant="bordered" padding="md">
          <div className="space-y-2">
            {data.sectorLeaders.map((sl) => {
              const chg = sl.changePct ?? 0;
              const leaderChg = sl.leaderChangePct ?? 0;
              return (
                <div key={sl.sector} className="flex items-center justify-between rounded-lg border border-border/40 p-3">
                  <div className="flex items-center gap-3">
                    <span className={`text-sm font-medium ${chg > 0 ? 'text-success' : 'text-danger'}`}>{chg > 0 ? '+' : ''}{chg}%</span>
                    <span className="text-sm font-medium">{sl.sector}</span>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    龙头: <span className="font-medium text-foreground">{sl.leader}</span>
                    <span className={`ml-1 ${leaderChg > 0 ? 'text-success' : 'text-danger'}`}>{leaderChg > 0 ? '+' : ''}{leaderChg}%</span>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </AppPage>
  );
};

export default DailyReviewPage;
