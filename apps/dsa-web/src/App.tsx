import type React from 'react';
import { useEffect } from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { ApiErrorAlert, Shell } from './components/common';
import {
  PageLoadingFallback,
  RouteOutletBoundary,
  StandaloneRouteBoundary,
} from './components/layout/RouteBoundary';
import { RecommendationLayout } from './components/layout/RecommendationLayout';
import { BacktestLayout } from './components/layout/BacktestLayout';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { useAgentChatStore } from './stores/agentChatStore';
import './App.css';

// ── 页面组件（集中管理于 config/routes.ts） ──
import {
  HomePage, BacktestPage, BacktestOptimizationPage, SettingsPage, LoginPage, NotFoundPage,
  ChatPage, SealPlatePage, PositionMonitorPage, AlertsPage, StockScreeningPage,
  ComprehensiveRecommendationPage, DeepAnalysisPage, RecommendationTrackingPage,
  StrategyOptimizerPage, SectorHeatmapPage,
  MarketTrendPage, DailyReviewPage, CapitalFlowPage, ShortTermTargetsPage,
  MidLongTermPage, RiskControlPage, ThemeMiningPage, LimitUpLadderPage,
  MultiFactorBacktestPage, PositionAdvicePage,
} from './config/routes';

const AppContent: React.FC = () => {
  const location = useLocation();
  const { authEnabled, loggedIn, isLoading, loadError, refreshStatus } = useAuth();

  useEffect(() => {
    useAgentChatStore.getState().setCurrentRoute(location.pathname);
  }, [location.pathname]);

  if (isLoading) {
    return <PageLoadingFallback />;
  }

  if (loadError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-base px-4">
        <div className="w-full max-w-lg">
          <ApiErrorAlert error={loadError} />
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={() => void refreshStatus()}
        >
          重试
        </button>
      </div>
    );
  }

  if (authEnabled && !loggedIn) {
    if (location.pathname === '/login') {
      return (
        <StandaloneRouteBoundary>
          <LoginPage />
        </StandaloneRouteBoundary>
      );
    }
    const redirect = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  if (location.pathname === '/login') {
    return <Navigate to="/" replace />;
  }

  return (
    <Routes>
      <Route
        element={(
          <Shell>
            <RouteOutletBoundary />
          </Shell>
        )}
      >
        <Route path="/" element={<HomePage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/screening" element={<StockScreeningPage />} />
        {/* ── 回测 二级路由（顶部标签栏布局）── */}
        <Route path="/backtest" element={<BacktestLayout />}>
          <Route index element={<BacktestPage />} />
          <Route path="optimization" element={<BacktestOptimizationPage />} />
        </Route>
        <Route path="/seal-plate" element={<SealPlatePage />} />
        <Route path="/comprehensive" element={<ComprehensiveRecommendationPage />} />
        <Route path="/position-monitor" element={<PositionMonitorPage />} />
        <Route path="/deep-analysis" element={<DeepAnalysisPage />} />
        <Route path="/recommendation-tracking" element={<RecommendationTrackingPage />} />
        <Route path="/strategy-optimizer" element={<StrategyOptimizerPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/settings" element={<SettingsPage />} />

        <Route path="/sector-heatmap" element={<SectorHeatmapPage />} />

        {/* ── 推荐系统 二级路由（独立顶部标签栏布局）── */}
        <Route element={<RecommendationLayout />}>
          <Route path="/recommendation/market-trend" element={<MarketTrendPage />} />
          <Route path="/recommendation/daily-review" element={<DailyReviewPage />} />
          <Route path="/recommendation/capital-flow" element={<CapitalFlowPage />} />
          <Route path="/recommendation/short-term" element={<ShortTermTargetsPage />} />
          <Route path="/recommendation/mid-long-term" element={<MidLongTermPage />} />
          <Route path="/recommendation/risk-control" element={<RiskControlPage />} />
          <Route path="/recommendation/theme-mining" element={<ThemeMiningPage />} />
          <Route path="/recommendation/limit-up-ladder" element={<LimitUpLadderPage />} />
          <Route path="/recommendation/multi-factor-backtest" element={<MultiFactorBacktestPage />} />
          <Route path="/recommendation/position-advice" element={<PositionAdvicePage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
};

const App: React.FC = () => {
  return (
    <Router>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </Router>
  );
};

export default App;
