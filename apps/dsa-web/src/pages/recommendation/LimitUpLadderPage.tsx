import React, { useEffect } from 'react';
import { Layers, TrendingUp, Zap, Activity, AlertTriangle } from 'lucide-react';
import { AppPage, PageHeader, Card, StatCard, Badge } from '../../components/common';
import { recommendationApi } from '../../api/recommendation';
import { useRecommendationData } from '../../hooks/useRecommendationData';
import type { LimitUpLadderResponse } from '../../api/recommendation';

const PHASE_CONFIG: Record<string, { variant: 'success' | 'warning' | 'danger' | 'info'; color: string }> = {
  '冰点期': { variant: 'danger', color: 'text-danger' },
  '修复期': { variant: 'warning', color: 'text-warning' },
  '分歧期': { variant: 'warning', color: 'text-warning' },
  '启动期': { variant: 'info', color: 'text-primary' },
  '主升期': { variant: 'success', color: 'text-success' },
};

const LimitUpLadderPage: React.FC = () => {
  useEffect(() => { document.title = '连板梯队与情绪周期 - DSA'; }, []);

  const { data, isLoading: loading, error } = useRecommendationData<LimitUpLadderResponse>({
    queryKey: ['recommendation', 'limit-up-ladder'],
    queryFn: () => recommendationApi.getLimitUpLadder(),
  });

  if (loading) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">加载中...</div></AppPage>;
  if (error) return <AppPage className="flex items-center justify-center"><Card variant="bordered" padding="md" className="max-w-md text-center"><AlertTriangle className="w-8 h-8 text-warning mx-auto mb-3" /><p className="text-sm text-muted-foreground">{error?.message ?? '加载失败'}</p></Card></AppPage>;
  if (!data) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">暂无数据</div></AppPage>;

  const { ladder, emotion } = data;
  const phaseConfig = PHASE_CONFIG[emotion.phase] ?? { variant: 'info' as const, color: 'text-primary' };

  return (
    <AppPage className="space-y-5">
      <PageHeader eyebrow="Limit-Up Ladder" title="连板梯队与情绪周期" description="打板高度监控、涨停溢价及市场情绪指标" />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <Card title="当前情绪周期" variant="gradient" padding="md" className="md:col-span-1">
          <div className="text-center space-y-3">
            <div className={`text-4xl font-bold ${phaseConfig.color}`}>{emotion.phase}</div>
            <div className="text-sm text-muted-foreground">{emotion.phaseDesc}</div>
            <div className="flex items-center justify-center gap-2">
              <span className="text-3xl font-bold tabular-nums">{emotion.sentimentIndex}</span>
              <span className="text-xs text-muted-foreground">情绪指数</span>
            </div>
          </div>
        </Card>

        <Card title="情绪周期演变" variant="bordered" padding="md" className="md:col-span-2">
          <div className="space-y-4">
            <div className="flex items-end gap-2 justify-around h-24">
              {emotion.history.map((item) => {
                const pc = PHASE_CONFIG[item.phase] ?? PHASE_CONFIG['分歧期'];
                return (
                  <div key={item.date} className="flex flex-col items-center gap-1 flex-1">
                    <span className={`text-xs font-bold ${pc.color}`}>{item.phase}</span>
                    <div className="w-full bg-muted/20 rounded-t" style={{ height: `${item.index}%`, maxWidth: '40px' }}>
                      <div className={`w-full rounded-t h-full ${item.index >= 60 ? 'bg-success/60' : item.index >= 30 ? 'bg-warning/60' : 'bg-danger/60'}`} />
                    </div>
                    <span className="text-xs text-muted-foreground">{item.date}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="涨停溢价率" value={`${emotion.limitUpRatio}%`} tone="success" icon={<TrendingUp className="w-4 h-4" />} />
        <StatCard label="昨日溢价" value={`${emotion.yesterdayPremium}%`} tone="primary" icon={<Activity className="w-4 h-4" />} />
        <StatCard label="次日红盘率" value={`${emotion.nextDayRedRate}%`} tone="success" icon={<Zap className="w-4 h-4" />} />
        <StatCard label="涨停家数" value={`${data.totalLimitUp} 家`} tone="primary" icon={<Layers className="w-4 h-4" />} />
      </div>

      <Card title="连板梯队" subtitle="按连板数降序" variant="bordered" padding="md">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/50 text-xs text-muted-foreground">
                <th className="text-left py-2 font-medium">排名</th>
                <th className="text-left py-2 font-medium">连板</th>
                <th className="text-left py-2 font-medium">股票</th>
                <th className="text-right py-2 font-medium">涨幅</th>
                <th className="text-right py-2 font-medium">换手率</th>
                <th className="text-right py-2 font-medium">封板资金</th>
                <th className="text-left py-2 font-medium">情绪定性</th>
                <th className="text-right py-2 font-medium">强度</th>
              </tr>
            </thead>
            <tbody>
              {ladder.map((item) => (
                <tr key={item.code} className="border-b border-border/30 hover:bg-hover/40 transition-colors">
                  <td className="py-2.5 text-muted-foreground">{item.rank}</td>
                  <td className="py-2.5"><Badge variant={item.board.includes('8') || item.board.includes('5') ? 'success' : item.board.includes('首') ? 'info' : 'default'}>{item.board}</Badge></td>
                  <td className="py-2.5 font-medium">{item.name}<span className="text-xs text-muted-foreground ml-1">{item.code}</span></td>
                  <td className={`py-2.5 text-right tabular-nums font-medium ${item.changePct > 0 ? 'text-success' : 'text-danger'}`}>+{item.changePct}%</td>
                  <td className="py-2.5 text-right tabular-nums">{item.turnover}%</td>
                  <td className="py-2.5 text-right tabular-nums">{item.sealAmt} 亿</td>
                  <td className="py-2.5 text-xs text-muted-foreground">{item.sentiment}</td>
                  <td className="py-2.5 text-right tabular-nums">
                    <div className="flex items-center justify-end gap-1.5">
                      <div className="w-10 h-1.5 bg-muted/40 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${item.strength >= 80 ? 'bg-success' : item.strength >= 60 ? 'bg-warning' : 'bg-danger'}`} style={{ width: `${item.strength}%` }} />
                      </div>
                      <span className="text-xs">{item.strength}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </AppPage>
  );
};

export default LimitUpLadderPage;
