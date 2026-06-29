import React, { useEffect, useMemo, useState } from 'react';
import { Lightbulb, TrendingUp, Zap, Search, AlertTriangle } from 'lucide-react';
import { AppPage, PageHeader, Card, StatCard, Badge } from '../../components/common';
import { recommendationApi } from '../../api/recommendation';
import { useRecommendationData } from '../../hooks/useRecommendationData';
import type { ThemeMiningResponse } from '../../api/recommendation';

const HOTNESS_CONFIG: Record<string, string> = {
  '主升浪': 'success',
  '二次启动': 'info',
  '初升段': 'info',
  '蓄势': 'warning',
  '预热': 'warning',
  '退潮': 'danger',
  '概念期': 'info',
};

const ThemeMiningPage: React.FC = () => {
  useEffect(() => { document.title = '题材挖掘与龙头定性 - DSA'; }, []);

  const { data, isLoading: loading, error } = useRecommendationData<ThemeMiningResponse>({
    queryKey: ['recommendation', 'theme-mining'],
    queryFn: () => recommendationApi.getThemeMining(),
  });
  const [search, setSearch] = useState('');

  const filteredThemes = useMemo(() => {
    if (!data) return [];
    if (!search.trim()) return data.themes;
    const q = search.toLowerCase();
    return data.themes.filter(
      (t) => t.name.toLowerCase().includes(q) || t.leaderStock.toLowerCase().includes(q) || t.subThemes.some((s) => s.toLowerCase().includes(q))
    );
  }, [data, search]);

  if (loading) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">加载中...</div></AppPage>;
  if (error) return <AppPage className="flex items-center justify-center"><Card variant="bordered" padding="md" className="max-w-md text-center"><AlertTriangle className="w-8 h-8 text-warning mx-auto mb-3" /><p className="text-sm text-muted-foreground">{error?.message ?? '加载失败'}</p></Card></AppPage>;
  if (!data) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">暂无数据</div></AppPage>;

  return (
    <AppPage className="space-y-5">
      <PageHeader eyebrow="Theme Mining" title="题材挖掘与龙头定性" description="题材溯源、热点轮动剖析与龙头股生命力评估" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="活跃题材" value={`${data.activeThemes} 个`} tone="success" icon={<Lightbulb className="w-4 h-4" />} />
        <StatCard label="跟风个股" value={`${data.totalFollowers} 个`} tone="primary" icon={<TrendingUp className="w-4 h-4" />} />
        <StatCard label="主线题材" value={data.mainTheme} tone="primary" icon={<Zap className="w-4 h-4" />} />
        <StatCard label="最热龙头" value={data.hottestLeader} tone="success" icon={<TrendingUp className="w-4 h-4" />} />
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="搜索题材、龙头..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-border/60 bg-card text-sm outline-none focus:border-primary/40 transition-colors"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filteredThemes.map((t) => (
          <Card key={t.name} variant="bordered" padding="md">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm">{t.name}</span>
                  <Badge variant={HOTNESS_CONFIG[t.trend] as 'success' | 'info' | 'warning' | 'danger'}>{t.trend}</Badge>
                </div>
                <span className="text-xs text-muted-foreground">{t.persistence}</span>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">热度</span>
                <div className="flex-1 h-2 bg-muted/20 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${t.hotness >= 80 ? 'bg-success' : t.hotness >= 50 ? 'bg-warning' : 'bg-danger'}`} style={{ width: `${t.hotness}%` }} />
                </div>
                <span className="text-xs font-medium tabular-nums">{t.hotness}</span>
              </div>

              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground text-xs">龙头:</span>
                <span className="font-medium">{t.leaderStock}</span>
                <span className={`text-xs ${t.leaderChange > 0 ? 'text-success' : 'text-danger'}`}>{t.leaderChange > 0 ? '+' : ''}{t.leaderChange}%</span>
                <span className="text-xs text-muted-foreground">| 跟风 {t.followerCount} 只</span>
              </div>

              <div className="text-xs text-muted-foreground">
                <span className="text-foreground font-medium">催化剂: </span>
                {t.catalyst}
              </div>

              <div className="flex flex-wrap gap-1.5">
                {t.subThemes.map((st) => (
                  <span key={st} className="px-2 py-0.5 rounded-md bg-primary/10 text-xs text-primary">{st}</span>
                ))}
              </div>

              <div className="flex flex-wrap gap-1">
                {t.relatedStocks.map((rs) => (
                  <span key={rs} className="px-1.5 py-0.5 rounded bg-muted/40 text-xs text-muted-foreground">{rs}</span>
                ))}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </AppPage>
  );
};

export default ThemeMiningPage;
