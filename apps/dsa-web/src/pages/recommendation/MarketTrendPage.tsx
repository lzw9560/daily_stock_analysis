import React, { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, BarChart3, Activity, AlertTriangle, RefreshCw } from 'lucide-react';
import { AppPage, PageHeader, Card, StatCard } from '../../components/common';
import { recommendationApi } from '../../api/recommendation';
import { usePageCache } from '../../hooks/usePageCache';
import { queryKeys } from '../../lib/queryKeys';
import type { MarketTrendResponse } from '../../api/recommendation';
import { CACHE_PROFILES } from '../../lib/queryClient';

const MarketTrendPage: React.FC = () => {
  useEffect(() => { document.title = '大盘走势 - DSA'; }, []);
  const [selectedIndex, setSelectedIndex] = useState('000001');

  // 使用缓存增强的数据获取：30秒新鲜期，60秒自动后台刷新
  const { data, isLoading, isBackgroundRefreshing, error } = usePageCache<MarketTrendResponse>({
    queryKey: queryKeys.recommendation.marketTrend,
    queryFn: () => recommendationApi.getMarketTrend(),
    listenKeys: [queryKeys.recommendation.all],
    ...CACHE_PROFILES.realtime,
    refetchInterval: 60_000,
    debugName: 'MarketTrendPage',
  });

  const upCount = data?.upCount ?? 0;
  const downCount = data?.downCount ?? 0;

  if (isLoading) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">加载中...</div></AppPage>;

  if (error) return (
    <AppPage className="flex items-center justify-center">
      <Card variant="bordered" padding="md" className="max-w-md text-center">
        <AlertTriangle className="w-8 h-8 text-warning mx-auto mb-3" />
        <p className="text-sm text-muted-foreground">{String(error)}</p>
      </Card>
    </AppPage>
  );

  if (!data) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">暂无数据</div></AppPage>;

  return (
    <AppPage className="space-y-5">
      <PageHeader
        eyebrow="Market Trend"
        title="大盘走势"
        description="市场趋势图表 — 指数研判、均线系统与量价分析"
        actions={
          isBackgroundRefreshing ? (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <RefreshCw className="w-3 h-3 animate-spin" />
              刷新中...
            </span>
          ) : undefined
        }
      />

      {/* 指数卡片网格 */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {data.indices.map((idx) => {
          const price = idx.price ?? 0;
          const changePct = idx.changePct ?? 0;
          const isUp = changePct > 0;
          return (
            <Card
              key={idx.code}
              variant={selectedIndex === idx.code ? 'gradient' : 'bordered'}
              padding="sm"
              className={selectedIndex === idx.code ? 'ring-2 ring-primary/30' : 'cursor-pointer hover:border-primary/30'}
            >
              <div onClick={() => setSelectedIndex(idx.code)} className="space-y-1">
                <div className="text-xs text-muted-foreground">{idx.name}</div>
                <div className="text-lg font-bold tabular-nums">{price.toLocaleString()}</div>
                <div className={`text-xs font-medium ${isUp ? 'text-success' : 'text-danger'}`}>
                  {isUp ? '+' : ''}{changePct.toFixed(2)}%
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="上涨指数" value={`${upCount} 个`} tone="success" icon={<TrendingUp className="w-4 h-4" />} />
        <StatCard label="下跌指数" value={`${downCount} 个`} tone="danger" icon={<TrendingDown className="w-4 h-4" />} />
        <StatCard label="两市成交额" value={data.totalAmount} tone="primary" icon={<BarChart3 className="w-4 h-4" />} />
        <StatCard label="涨停家数" value={`${data.limitUpCount} 家`} tone="success" icon={<Activity className="w-4 h-4" />} />
      </div>

      {/* 图表区域 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card title="均线趋势" subtitle="K线 · MA5 · 成交量" variant="bordered" padding="md">
          <div className="space-y-4">
            <div className="flex items-center gap-4 text-xs">
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-primary inline-block" /> 价格</span>
              <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-warning inline-block" /> MA5</span>
            </div>
            <div className="flex items-end gap-1 h-32">
              {data.trend.dates.map((d, i) => {
                const maxPrice = Math.max(...data.trend.price.filter(p => p != null), 3400);
                const priceVal = data.trend.price[i] ?? 0;
                const ma5Val = data.trend.ma5[i] ?? 0;
                return (
                  <div key={d} className="flex-1 flex flex-col items-center gap-0.5">
                    <div className="flex flex-col items-center w-full" style={{ height: '128px', justifyContent: 'flex-end' }}>
                      <div className="w-full bg-primary/50 rounded-t" style={{ height: `${(priceVal / maxPrice) * 100}%`, maxWidth: '8px' }} />
                      {ma5Val > 0 && (
                        <div className="w-full bg-warning/50 rounded-t" style={{ height: `${(ma5Val / maxPrice) * 100}%`, maxWidth: '8px', marginTop: '-128px' }} />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="flex justify-between text-xs text-muted-foreground">
              {data.trend.dates.filter((_, i) => i % 5 === 0).map(d => <span key={d}>{d}</span>)}
            </div>
          </div>
        </Card>

        <Card title="成交量趋势" subtitle="日均成交量(亿)" variant="bordered" padding="md">
          <div className="flex items-end gap-1 h-32">
            {data.trend.volume.map((v, i) => {
              const maxV = Math.max(...data.trend.volume, 1);
              return (
                <div key={i} className="flex-1 flex flex-col items-center justify-end">
                  <div className="w-full bg-primary/30 rounded-t" style={{ height: `${(v / maxV) * 100}%`, maxWidth: '8px' }} />
                </div>
              );
            })}
          </div>
          <div className="flex justify-between text-xs text-muted-foreground mt-2">
            {data.trend.dates.filter((_, i) => i % 5 === 0).map(d => <span key={d}>{d}</span>)}
          </div>
        </Card>
      </div>
    </AppPage>
  );
};

export default MarketTrendPage;
