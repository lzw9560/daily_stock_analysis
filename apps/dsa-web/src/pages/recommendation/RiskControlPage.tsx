import React, { useEffect } from 'react';
import { ShieldAlert, TrendingUp, AlertTriangle, PieChart } from 'lucide-react';
import { AppPage, PageHeader, Card, StatCard, Badge } from '../../components/common';
import { recommendationApi } from '../../api/recommendation';
import { useRecommendationData } from '../../hooks/useRecommendationData';
import type { RiskControlResponse } from '../../api/recommendation';

const ADVICE_CONFIG: Record<string, { variant: 'success' | 'warning' | 'danger' | 'info' }> = {
  '持有': { variant: 'success' },
  '持有观察': { variant: 'warning' },
  '设止损': { variant: 'info' },
};

const RiskControlPage: React.FC = () => {
  useEffect(() => { document.title = '风控与仓位管理 - DSA'; }, []);

  const { data, isLoading: loading, error } = useRecommendationData<RiskControlResponse>({
    queryKey: ['recommendation', 'risk-control'],
    queryFn: () => recommendationApi.getRiskControl(),
  });

  const highRiskCount = (data?.positionRisks ?? []).filter((p) => p.riskLevel === '高').length;

  if (loading) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">加载中...</div></AppPage>;
  if (error) return <AppPage className="flex items-center justify-center"><Card variant="bordered" padding="md" className="max-w-md text-center"><AlertTriangle className="w-8 h-8 text-warning mx-auto mb-3" /><p className="text-sm text-muted-foreground">{error?.message ?? '加载失败'}</p></Card></AppPage>;
  if (!data) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">暂无数据</div></AppPage>;

  return (
    <AppPage className="space-y-5">
      <PageHeader eyebrow="Risk Control" title="风控与仓位管理" description="个股止损止盈、动态仓位控制及系统性风险预警" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="市场VIX" value={data.vix.toFixed(1)} tone={data.vix > 25 ? 'danger' : 'success'} icon={<AlertTriangle className="w-4 h-4" />} />
        <StatCard label="总仓位" value={`${data.totalWeight.toFixed(0)}%`} tone={data.totalWeight > 60 ? 'warning' : 'success'} icon={<PieChart className="w-4 h-4" />} />
        <StatCard label="高风险品种" value={`${highRiskCount} 个`} tone="danger" icon={<ShieldAlert className="w-4 h-4" />} />
        <StatCard label="融资余额" value={`${data.marginBalance.toLocaleString()} 亿`} tone="primary" icon={<TrendingUp className="w-4 h-4" />} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Card variant="bordered" padding="sm" className="text-center">
          <div className="text-xs text-muted-foreground">高风险板块</div>
          <div className="text-2xl font-bold text-danger">{data.sectorRisk.high}</div>
        </Card>
        <Card variant="bordered" padding="sm" className="text-center">
          <div className="text-xs text-muted-foreground">中风险板块</div>
          <div className="text-2xl font-bold text-warning">{data.sectorRisk.medium}</div>
        </Card>
        <Card variant="bordered" padding="sm" className="text-center">
          <div className="text-xs text-muted-foreground">低风险板块</div>
          <div className="text-2xl font-bold text-success">{data.sectorRisk.low}</div>
        </Card>
      </div>

      <Card title="持仓风险明细" subtitle={`ATR止损参考 · 强平线: ${data.forcedLiquidation}%`} variant="bordered" padding="md">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/50 text-xs text-muted-foreground">
                <th className="text-left py-2 font-medium">股票</th>
                <th className="text-right py-2 font-medium">权重</th>
                <th className="text-right py-2 font-medium">止损价</th>
                <th className="text-right py-2 font-medium">现价</th>
                <th className="text-right py-2 font-medium">ATR</th>
                <th className="text-center py-2 font-medium">风险等级</th>
                <th className="text-left py-2 font-medium">操作建议</th>
              </tr>
            </thead>
            <tbody>
              {data.positionRisks.map((p) => (
                <tr key={p.code} className="border-b border-border/30 hover:bg-hover/40 transition-colors">
                  <td className="py-2.5 font-medium">{p.name}<span className="text-xs text-muted-foreground ml-1">{p.code}</span></td>
                  <td className="py-2.5 text-right tabular-nums">{p.weight}%</td>
                  <td className="py-2.5 text-right tabular-nums text-danger">{p.stopLoss.toFixed(2)}</td>
                  <td className="py-2.5 text-right tabular-nums">{p.currentPrice.toFixed(2)}</td>
                  <td className="py-2.5 text-right tabular-nums">{p.atr.toFixed(2)}%</td>
                  <td className="py-2.5 text-center">
                    <Badge variant={p.riskLevel === '高' ? 'danger' : p.riskLevel === '中' ? 'warning' : 'success'}>{p.riskLevel}</Badge>
                  </td>
                  <td className="py-2.5"><Badge variant={ADVICE_CONFIG[p.advice]?.variant ?? 'info'}>{p.advice}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="风控规则" variant="bordered" padding="md">
        <div className="space-y-2 text-sm text-muted-foreground">
          <div className="flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-warning" /> 单票仓位不超过总资金的 20%</div>
          <div className="flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-danger" /> 跌破 ATR × 2 止损位立即离场</div>
          <div className="flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-warning" /> 总仓位超过 60% 时降低杠杆</div>
          <div className="flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-danger" /> 市场 VIX &gt; 30 触发预警，&gt; 40 强制减仓</div>
        </div>
      </Card>
    </AppPage>
  );
};

export default RiskControlPage;
