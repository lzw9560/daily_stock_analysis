import React, { useEffect, useMemo } from 'react';
import { TrendingUp, TrendingDown, DollarSign, BarChart3, AlertTriangle } from 'lucide-react';
import { AppPage, PageHeader, Card, StatCard, Badge } from '../../components/common';
import { recommendationApi } from '../../api/recommendation';
import { useRecommendationData } from '../../hooks/useRecommendationData';
import type { CapitalFlowResponse } from '../../api/recommendation';

const CapitalFlowPage: React.FC = () => {
  useEffect(() => { document.title = '资金与板块热点 - DSA'; }, []);

  const { data, isLoading: loading, error } = useRecommendationData<CapitalFlowResponse>({
    queryKey: ['recommendation', 'capital-flow'],
    queryFn: () => recommendationApi.getCapitalFlow(),
  });

  const totalOutflow = useMemo(() => Math.abs(data?.totalOutflow ?? 0), [data]);

  if (loading) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">加载中...</div></AppPage>;
  if (error) return <AppPage className="flex items-center justify-center"><Card variant="bordered" padding="md" className="max-w-md text-center"><AlertTriangle className="w-8 h-8 text-warning mx-auto mb-3" /><p className="text-sm text-muted-foreground">{error?.message ?? '加载失败'}</p></Card></AppPage>;
  if (!data) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">暂无数据</div></AppPage>;

  return (
    <AppPage className="space-y-5">
      <PageHeader eyebrow="Capital Flow" title="资金与板块热点" description="资金流向分析 — 板块轮动、主力资金与北向资金监控" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="主力净流入" value={`+${data.totalInflow.toFixed(1)} 亿`} tone="success" icon={<TrendingUp className="w-4 h-4" />} />
        <StatCard label="主力净流出" value={`-${totalOutflow.toFixed(1)} 亿`} tone="danger" icon={<TrendingDown className="w-4 h-4" />} />
        <StatCard label="今日北向" value={`${data.todayNorthBound > 0 ? '+' : ''}${data.todayNorthBound.toFixed(1)} 亿`} tone={data.todayNorthBound > 0 ? 'success' : 'danger'} icon={<DollarSign className="w-4 h-4" />} />
        <StatCard label="两市成交" value={data.totalAmount} tone="primary" icon={<BarChart3 className="w-4 h-4" />} />
      </div>

      {data.moneyFlow.length > 0 && (
        <Card title="板块资金流向" subtitle="单日板块净流入 TOP12" variant="bordered" padding="md">
          <div className="space-y-2">
            {data.moneyFlow.map((mf) => {
              const maxAmt = Math.max(...data.moneyFlow.map(m => Math.abs(m.amount)), 1);
              return (
                <div key={mf.name} className="flex items-center gap-3">
                  <span className="w-20 text-xs text-muted-foreground truncate">{mf.name}</span>
                  <div className="flex-1 h-4 bg-muted/20 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${mf.amount > 0 ? 'bg-success/60' : 'bg-danger/60'}`}
                      style={{ width: `${(Math.abs(mf.amount) / maxAmt) * 100}%` }}
                    />
                  </div>
                  <span className={`w-20 text-right text-xs font-medium tabular-nums ${mf.amount > 0 ? 'text-success' : 'text-danger'}`}>
                    {mf.amount > 0 ? '+' : ''}{mf.amount.toFixed(1)} 亿
                  </span>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {data.northBound.length > 0 && (
        <Card title="北向资金个股流向" subtitle="沪深股通净买入/卖出 TOP8" variant="bordered" padding="md">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 text-xs text-muted-foreground">
                  <th className="text-left py-2 font-medium">股票</th>
                  <th className="text-right py-2 font-medium">净流入(亿)</th>
                  <th className="text-left py-2 font-medium">方向</th>
                </tr>
              </thead>
              <tbody>
                {data.northBound.map((nb) => (
                  <tr key={nb.code} className="border-b border-border/30 hover:bg-hover/40 transition-colors">
                    <td className="py-2.5 font-medium">{nb.name}<span className="text-xs text-muted-foreground ml-1">{nb.code}</span></td>
                    <td className={`py-2.5 text-right tabular-nums font-medium ${nb.netInflow > 0 ? 'text-success' : 'text-danger'}`}>
                      {nb.netInflow > 0 ? '+' : ''}{nb.netInflow.toFixed(2)}
                    </td>
                    <td className="py-2.5">
                      <Badge variant={nb.direction === '流入' ? 'success' : 'danger'}>{nb.direction}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {data.sectorRotation.length > 0 && (
        <Card title="板块轮动详情" variant="bordered" padding="md">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 text-xs text-muted-foreground">
                  <th className="text-left py-2 font-medium">板块</th>
                  <th className="text-right py-2 font-medium">流入(亿)</th>
                  <th className="text-right py-2 font-medium">流出(亿)</th>
                  <th className="text-right py-2 font-medium">净额(亿)</th>
                  <th className="text-left py-2 font-medium">状态</th>
                </tr>
              </thead>
              <tbody>
                {data.sectorRotation.map((sr) => (
                  <tr key={sr.sector} className="border-b border-border/30 hover:bg-hover/40 transition-colors">
                    <td className="py-2.5 font-medium">{sr.sector}</td>
                    <td className="py-2.5 text-right tabular-nums text-success">{sr.flowIn.toFixed(1)}</td>
                    <td className="py-2.5 text-right tabular-nums text-danger">{sr.flowOut.toFixed(1)}</td>
                    <td className={`py-2.5 text-right tabular-nums font-medium ${sr.net > 0 ? 'text-success' : 'text-danger'}`}>{sr.net > 0 ? '+' : ''}{sr.net.toFixed(1)}</td>
                    <td className="py-2.5"><Badge variant={sr.status === '净流入' ? 'success' : 'danger'}>{sr.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </AppPage>
  );
};

export default CapitalFlowPage;
