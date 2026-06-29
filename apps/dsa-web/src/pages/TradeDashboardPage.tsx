import type React from 'react';
import { useEffect, useState, useCallback } from 'react';
import { Zap, TrendingUp, Activity } from 'lucide-react';
import { AppPage, PageHeader, MarketTicker, PositionSummary, SignalCard, Sparkline, Card } from '../components/common';
import type { SignalInfo } from '../components/common/SignalCard';
import {
  getSentiment,
  getShortTermSignals,
  getStrategyStats,
  type ShortTermSignal,
} from '../api/enhancedRecommendation';

const TradeDashboardPage: React.FC = () => {
  const [expandedSignal, setExpandedSignal] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sentimentData, setSentimentData] = useState<any>(null);
  const [signals, setSignals] = useState<SignalInfo[]>([]);
  const [strategyStats, setStrategyStats] = useState<Record<string, any>>({});

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [sentRes, sigRes, stratRes] = await Promise.all([
        getSentiment(),
        getShortTermSignals(),
        getStrategyStats({ minSamples: 1 }),
      ]);
      setSentimentData(sentRes);
      setSignals(
        (sigRes.signals || []).map((s: ShortTermSignal, i: number) => ({
          id: String(i),
          type: s.signalType === 'seal_plate' ? 'first_board' : s.signalType === 'low_suck' ? 'low_suck' : 'breakout',
          typeLabel: s.strategy,
          typeEmoji: s.signalType === 'seal_plate' ? '⚡' : s.signalType === 'low_suck' ? '📉' : '🚀',
          symbol: s.code,
          name: s.name,
          price: s.entryPriceRange?.[0] || 0,
          changePercent: 0,
          confidence: s.confidence,
          buyPriceMin: s.entryPriceRange?.[0] || 0,
          buyPriceMax: s.entryPriceRange?.[1] || 0,
          stopLoss: s.stopLoss,
          holdDays: String(s.expectedHoldDays) + '天',
          sectors: [(s.reason || '').slice(0, 20)],
          reason: s.reason || '',
          riskWarning: s.riskFactors?.join('，') || '',
          timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        }))
      );
      setStrategyStats(stratRes.byStrategy || {});
    } catch (e) {
      console.error('TradeDashboard load error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    document.title = '交易工作台 - DSA';
    loadData();
    const timer = setInterval(loadData, 30000);
    return () => clearInterval(timer);
  }, [loadData]);

  const handleSignalExpand = useCallback((id: string) => {
    setExpandedSignal((prev) => (prev === id ? null : id));
  }, []);

  const sentimentPhase = sentimentData?.metrics?.phase || '中性';
  const sentimentScore = sentimentData?.metrics?.sentimentScore || 50;
  const limitUpCount = sentimentData?.metrics?.limitUpCount || 0;
  const brokenSealCount = sentimentData?.metrics?.brokenSealCount || 0;
  const northFlow = sentimentData?.metrics?.northFlow || 0;
  const strategyEntries = Object.entries(strategyStats).slice(0, 3);

  if (loading && !sentimentData) {
    return (
      <AppPage className="flex items-center justify-center">
        <div className="text-muted-foreground text-sm">加载中...</div>
      </AppPage>
    );
  }

  return (
    <AppPage className="space-y-4">
      <PageHeader
        eyebrow="Trade Dashboard"
        title="交易工作台"
        description="实时市场监控、信号提醒与持仓管理"
      />

      {/* Market Ticker */}
      <MarketTicker
        indices={[
          { symbol: '000001', name: '上证指数', price: 3356.82, change: 39.25, changePercent: 1.18 },
          { symbol: '399001', name: '深成指', price: 10852.34, change: 82.71, changePercent: 0.77 },
          { symbol: '399006', name: '创业板指', price: 2180.56, change: 15.33, changePercent: 0.71 },
        ]}
      />

      {/* Three-column layout */}
      <div className="trade-dashboard-grid">
        {/* Left column */}
        <div className="space-y-4">
          <Card title="今日计划" padding="sm">
            <div className="space-y-2 text-xs">
              <div className="flex items-center gap-2 p-2 rounded-lg bg-[hsl(var(--primary)/0.05)]">
                <span className="font-mono text-foreground">09:30</span>
                <span className="text-muted-foreground">开盘观察，确认方向</span>
              </div>
              <div className="flex items-center gap-2 p-2 rounded-lg bg-[hsl(var(--primary)/0.05)]">
                <span className="font-mono text-foreground">10:00</span>
                <span className="text-muted-foreground">执行打板策略，关注首板信号</span>
              </div>
              <div className="flex items-center gap-2 p-2 rounded-lg bg-[hsl(var(--primary)/0.05)]">
                <span className="font-mono text-foreground">14:00</span>
                <span className="text-muted-foreground">尾盘低吸信号确认</span>
              </div>
              <div className="flex items-center gap-2 p-2 rounded-lg bg-[hsl(var(--primary)/0.05)]">
                <span className="font-mono text-foreground">15:00</span>
                <span className="text-muted-foreground">收盘复盘，更新计划</span>
              </div>
            </div>
          </Card>

          <Card title="自选股监控" padding="sm">
            <div className="space-y-2">
              {[
                { symbol: '600519', name: '贵州茅台', price: 1520.00, changePercent: 2.39, sparkData: [1485, 1492, 1501, 1510, 1520] },
                { symbol: '000858', name: '五粮液', price: 85.20, changePercent: -1.10, sparkData: [86.5, 86.1, 85.8, 85.5, 85.2] },
                { symbol: '601318', name: '中国平安', price: 42.15, changePercent: 0.84, sparkData: [41.8, 41.9, 42.0, 42.1, 42.15] },
                { symbol: '000001', name: '平安银行', price: 12.58, changePercent: 2.53, sparkData: [12.28, 12.35, 12.42, 12.50, 12.58] },
              ].map((stock) => {
                const isUp = stock.changePercent >= 0;
                return (
                  <div
                    key={stock.symbol}
                    className="flex items-center justify-between p-2 rounded-lg bg-[hsl(var(--foreground)/0.02)] hover:bg-[hsl(var(--foreground)/0.04)] transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-muted-foreground">{stock.symbol}</span>
                        <span className="text-sm font-medium text-foreground truncate">{stock.name}</span>
                      </div>
                      <span className={isUp ? 'stock-up text-sm font-bold' : 'stock-down text-sm font-bold'}>
                        {stock.price.toFixed(2)}
                      </span>
                      <span className={isUp ? 'stock-up text-xs ml-1' : 'stock-down text-xs ml-1'}>
                        {isUp ? '+' : ''}{stock.changePercent.toFixed(1)}%
                      </span>
                    </div>
                    <Sparkline data={stock.sparkData} color={isUp ? 'up' : 'down'} />
                  </div>
                );
              })}
            </div>
          </Card>

          <PositionSummary
            totalAssets={128500}
            dailyPnl={2340}
            dailyPnlPercent={1.85}
            totalPnl={12340}
            totalPnlPercent={10.6}
            positionCount={5}
            cashCount={3}
            winRate={62}
          />
        </div>

        {/* Center column */}
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <Card padding="sm" className="text-center">
              <div className="text-2xl font-bold stock-up tabular-nums">{limitUpCount}</div>
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">涨停</div>
              <div className="text-xs stock-down mt-1">炸板 {brokenSealCount}</div>
            </Card>
            <Card padding="sm" className="text-center">
              <div className="text-2xl font-bold stock-up tabular-nums">{sentimentScore}</div>
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">情绪分数</div>
              <div className="text-xs text-muted-foreground mt-1">{sentimentPhase}</div>
            </Card>
            <Card padding="sm" className="text-center">
              <div className={`text-2xl font-bold tabular-nums ${northFlow >= 0 ? 'stock-up' : 'stock-down'}`}>
                {northFlow >= 0 ? '+' : ''}{northFlow.toFixed(0)}亿
              </div>
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">北向资金</div>
              <div className="text-xs text-muted-foreground mt-1">净流入</div>
            </Card>
          </div>

          <Card title="板块异动" padding="sm">
            <div className="space-y-2">
              <div className="flex items-center justify-between p-2 rounded-lg stock-up-bg">
                <div className="flex items-center gap-2">
                  <Zap className="h-4 w-4 stock-up" />
                  <span className="text-sm font-medium text-foreground">通信板块</span>
                </div>
                <span className="text-xs font-bold stock-up">3涨停 +2.8%</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg stock-up-bg">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 stock-up" />
                  <span className="text-sm font-medium text-foreground">券商板块</span>
                </div>
                <span className="text-xs font-bold stock-up">2涨停 +1.5%</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg stock-down-bg">
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 stock-down" />
                  <span className="text-sm font-medium text-foreground">银行板块</span>
                </div>
                <span className="text-xs font-bold stock-down">-0.8% 资金流出</span>
              </div>
            </div>
          </Card>

          <Card title="策略胜率" padding="sm">
            <div className="flex items-center gap-4">
              {strategyEntries.length > 0 ? (
                strategyEntries.slice(0, 3).map(([name, data]: [string, any]) => (
                  <div key={name} className="flex-1 text-center">
                    <div className="text-lg font-bold stock-up tabular-nums">{data.winRate}%</div>
                    <div className="text-[10px] text-muted-foreground truncate" title={name}>{name}</div>
                  </div>
                ))
              ) : (
                <>
                  <div className="flex-1 text-center">
                    <div className="text-lg font-bold stock-up tabular-nums">65%</div>
                    <div className="text-[10px] text-muted-foreground">打板</div>
                  </div>
                  <div className="flex-1 text-center">
                    <div className="text-lg font-bold stock-up tabular-nums">58%</div>
                    <div className="text-[10px] text-muted-foreground">低吸</div>
                  </div>
                  <div className="flex-1 text-center">
                    <div className="text-lg font-bold stock-up tabular-nums">72%</div>
                    <div className="text-[10px] text-muted-foreground">突破</div>
                  </div>
                </>
              )}
            </div>
          </Card>
        </div>

        {/* Right column */}
        <div className="space-y-4">
          <Card title="实时信号" padding="sm">
            <div className="space-y-3">
              {signals.length > 0 ? (
                signals.map((signal) => (
                  <SignalCard
                    key={signal.id}
                    signal={signal}
                    onExpand={handleSignalExpand}
                    isExpanded={expandedSignal === signal.id}
                    className="animate-signal-pulse"
                  />
                ))
              ) : (
                <div className="text-xs text-muted-foreground text-center py-4">暂无信号</div>
              )}
            </div>
          </Card>

          <Card title="市场快讯" padding="sm">
            <div className="space-y-2 text-xs">
              <div className="p-2 rounded-lg bg-[hsl(var(--foreground)/0.02)]">
                <span className="text-muted-foreground">14:32 </span>
                <span className="text-foreground">政策利好通信行业，多家券商上调评级</span>
              </div>
              <div className="p-2 rounded-lg bg-[hsl(var(--foreground)/0.02)]">
                <span className="text-muted-foreground">14:15 </span>
                <span className="text-foreground">北向资金今日净流入超50亿</span>
              </div>
              <div className="p-2 rounded-lg bg-[hsl(var(--foreground)/0.02)]">
                <span className="text-muted-foreground">13:48 </span>
                <span className="text-foreground">两市成交额突破8000亿</span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Bottom status bar */}
      <div className="flex items-center justify-between text-xs text-muted-foreground py-2 border-t border-[hsl(var(--foreground)/0.06)]">
        <span>
          策略胜率:{' '}
          {strategyEntries.length > 0
            ? strategyEntries.slice(0, 3).map(([n, d]: [string, any]) => `${n}${d.winRate}%`).join(' | ')
            : '打板65% | 低吸58% | 突破72%'}
        </span>
        <span>数据每30秒自动刷新</span>
      </div>
    </AppPage>
  );
};

export default TradeDashboardPage;
