import type React from 'react';
import {
  TrendingUp, Activity, DollarSign, Zap, TrendingDown,
  ShieldAlert, Lightbulb, Layers, GitBranch, PieChart,
} from 'lucide-react';
import { TabLayout, type TabDef } from './TabLayout';

const TABS: TabDef[] = [
  { key: 'market-trend', label: '大盘走势', to: '/recommendation/market-trend', icon: TrendingUp },
  { key: 'daily-review', label: '每日复盘', to: '/recommendation/daily-review', icon: Activity },
  { key: 'capital-flow', label: '资金与板块热点', to: '/recommendation/capital-flow', icon: DollarSign },
  { key: 'short-term', label: '短线打板标的', to: '/recommendation/short-term', icon: Zap },
  { key: 'mid-long-term', label: '中长线波段建仓', to: '/recommendation/mid-long-term', icon: TrendingDown },
  { key: 'risk-control', label: '风控与仓位管理', to: '/recommendation/risk-control', icon: ShieldAlert },
  { key: 'theme-mining', label: '题材挖掘与龙头定性', to: '/recommendation/theme-mining', icon: Lightbulb },
  { key: 'limit-up-ladder', label: '连板梯队与情绪周期', to: '/recommendation/limit-up-ladder', icon: Layers },
  { key: 'multi-factor-backtest', label: '多因子策略回测', to: '/recommendation/multi-factor-backtest', icon: GitBranch },
  { key: 'position-advice', label: '持仓建议', to: '/recommendation/position-advice', icon: PieChart },
];

export const RecommendationLayout: React.FC = () => (
  <TabLayout tabs={TABS} ariaLabel="推荐系统子导航" />
);
