import type React from 'react';
import { BarChart3, Sparkles } from 'lucide-react';
import { TabLayout, type TabDef } from './TabLayout';

const TABS: TabDef[] = [
  { key: 'tasks', label: '任务与结果', to: '/backtest', icon: BarChart3 },
  { key: 'optimization', label: '参数优化', to: '/backtest/optimization', icon: Sparkles },
];

export const BacktestLayout: React.FC = () => (
  <TabLayout tabs={TABS} ariaLabel="回测子导航" />
);
