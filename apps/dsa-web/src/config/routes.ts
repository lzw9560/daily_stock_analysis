/** 路由配置集中管理 — 同时驱动路由注册和页面标题 */
import type React from 'react';
import { lazy } from 'react';

export type RouteMeta = {
  path: string;
  title: string;
  description: string;
  /** 是否为二级子路由（使用 Tab 标签栏布局） */
  isSubRoute?: boolean;
  /** 父级路由路径 */
  parentPath?: string;
};

export type RouteDef = RouteMeta & {
  component: React.LazyExoticComponent<React.ComponentType<unknown>>;
};

export const ROUTES: RouteMeta[] = [
  { path: '/', title: '首页', description: '股票分析与历史报告工作台' },
  { path: '/chat', title: '问股', description: '多轮策略问答与历史会话管理' },
  { path: '/screening', title: '选股', description: 'AlphaSift 智能选股与量化筛选' },
  { path: '/backtest', title: '回测', description: '回测任务与结果浏览' },
  { path: '/backtest/optimization', title: '回测优化', description: '参数扫描、候选对比与历史扫描', isSubRoute: true, parentPath: '/backtest' },
  { path: '/seal-plate', title: '打板', description: '打板推荐、封板分析与股票池管理' },
  { path: '/comprehensive', title: '综合推荐', description: '多维信号聚合与仓位管理' },
  { path: '/alerts', title: '告警', description: '实时告警规则与通知管理' },
  { path: '/position-monitor', title: '持仓监控', description: '实时持仓监控与风险预警' },
  { path: '/deep-analysis', title: '深度分析', description: 'TradingAgents 多Agent投研 — 7位AI分析师深度研判' },
  { path: '/recommendation-tracking', title: '追踪', description: '历史推荐记录追踪、胜率回溯与策略反思' },
  { path: '/strategy-optimizer', title: '优化', description: '自适应参数调优、信号过滤、交易纪律与风险预警' },
  { path: '/settings', title: '设置', description: '系统配置、模型与认证管理' },
  { path: '/sector-heatmap', title: '热力图', description: '板块轮动热力图与情绪分析' },

  // ── 推荐系统 二级菜单 ──
  { path: '/recommendation/market-trend', title: '大盘走势', description: '市场趋势图表 — 指数研判、均线系统与量价分析', isSubRoute: true, parentPath: '/recommendation' },
  { path: '/recommendation/daily-review', title: '每日复盘', description: '当日数据汇总 — 涨跌统计、北向资金与龙虎榜复盘', isSubRoute: true, parentPath: '/recommendation' },
  { path: '/recommendation/capital-flow', title: '资金与板块热点', description: '资金流向分析 — 板块轮动、主力资金与北向资金监控', isSubRoute: true, parentPath: '/recommendation' },
  { path: '/recommendation/short-term', title: '短线打板标的', description: '打板战法选股 — 封板强度、溢价率与短线爆发力评估', isSubRoute: true, parentPath: '/recommendation' },
  { path: '/recommendation/mid-long-term', title: '中长线波段建仓', description: '波段战法建仓 — 趋势确认、估值分位与中线持仓逻辑', isSubRoute: true, parentPath: '/recommendation' },
  { path: '/recommendation/risk-control', title: '风控与仓位管理', description: '个股止损止盈、动态仓位控制及系统性风险预警', isSubRoute: true, parentPath: '/recommendation' },
  { path: '/recommendation/theme-mining', title: '题材挖掘与龙头定性', description: '题材溯源、热点轮动剖析与龙头股生命力评估', isSubRoute: true, parentPath: '/recommendation' },
  { path: '/recommendation/limit-up-ladder', title: '连板梯队与情绪周期', description: '打板高度监控、涨停溢价及市场情绪指标', isSubRoute: true, parentPath: '/recommendation' },
  { path: '/recommendation/multi-factor-backtest', title: '多因子策略回测', description: 'Alpha因子IC/IR表现及策略净值曲线展示', isSubRoute: true, parentPath: '/recommendation' },
  { path: '/recommendation/position-advice', title: '持仓建议', description: '持仓优化操作 — 调仓信号、仓位再平衡与止盈止损', isSubRoute: true, parentPath: '/recommendation' },
];

/** 根据路径快速查找标题 */
export function getRouteTitle(pathname: string): { title: string; description: string } {
  const route = ROUTES.find(r => r.path === pathname);
  return route ?? { title: 'Daily Stock Analysis', description: 'Web workspace' };
}

// ── 页面组件映射（与 App.tsx 同步） ──
export const HomePage = lazy(() => import('@/pages/HomePage'));
export const BacktestPage = lazy(() => import('@/pages/BacktestPage'));
export const BacktestOptimizationPage = lazy(() => import('@/pages/BacktestOptimizationPage'));
export const SettingsPage = lazy(() => import('@/pages/SettingsPage'));
export const LoginPage = lazy(() => import('@/pages/LoginPage'));
export const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'));
export const ChatPage = lazy(() => import('@/pages/ChatPage'));
export const SealPlatePage = lazy(() => import('@/pages/SealPlatePage'));
export const PositionMonitorPage = lazy(() => import('@/pages/PositionMonitorPage'));
export const AlertsPage = lazy(() => import('@/pages/AlertsPage'));
export const StockScreeningPage = lazy(() => import('@/pages/StockScreeningPage'));
export const ComprehensiveRecommendationPage = lazy(() => import('@/pages/ComprehensiveRecommendationPage'));
export const DeepAnalysisPage = lazy(() => import('@/pages/DeepAnalysisPage'));
export const RecommendationTrackingPage = lazy(() => import('@/pages/RecommendationTrackingPage'));
export const StrategyOptimizerPage = lazy(() => import('@/pages/StrategyOptimizerPage'));
export const SectorHeatmapPage = lazy(() => import('@/pages/SectorHeatmapPage'));

// ── 推荐系统子页面 ──
export const MarketTrendPage = lazy(() => import('@/pages/recommendation/MarketTrendPage'));
export const DailyReviewPage = lazy(() => import('@/pages/recommendation/DailyReviewPage'));
export const CapitalFlowPage = lazy(() => import('@/pages/recommendation/CapitalFlowPage'));
export const ShortTermTargetsPage = lazy(() => import('@/pages/recommendation/ShortTermTargetsPage'));
export const MidLongTermPage = lazy(() => import('@/pages/recommendation/MidLongTermPage'));
export const RiskControlPage = lazy(() => import('@/pages/recommendation/RiskControlPage'));
export const ThemeMiningPage = lazy(() => import('@/pages/recommendation/ThemeMiningPage'));
export const LimitUpLadderPage = lazy(() => import('@/pages/recommendation/LimitUpLadderPage'));
export const MultiFactorBacktestPage = lazy(() => import('@/pages/recommendation/MultiFactorBacktestPage'));
export const PositionAdvicePage = lazy(() => import('@/pages/recommendation/PositionAdvicePage'));
