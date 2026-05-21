import { useState, useEffect, useCallback } from 'react';
import { Zap, TrendingUp, AlertTriangle, Flame, Crown, BarChart3, RefreshCw, Filter, Brain, Shield, Layers } from 'lucide-react';
import { Button } from '@/components/common/Button';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { StatCard } from '@/components/common/StatCard';
import { Loading } from '@/components/common/Loading';
import { EmptyState } from '@/components/common/EmptyState';
import { sealPlateApi } from '@/api/sealPlate';
import type { SealPlateReportResponse, SealPlateStockResponse, SealPlateStatsResponse, SectorHot } from '@/types/sealPlate';
import SentimentDashboard from '@/components/sealPlate/SentimentDashboard';
import StockPoolPanel from '@/components/sealPlate/StockPoolPanel';
import DragonTigerList from '@/components/sealPlate/DragonTigerList';
import RiskAlertPanel from '@/components/sealPlate/RiskAlertPanel';
import EightStandardChecklist from '@/components/sealPlate/EightStandardChecklist';

// 新增功能Tab
type TabType = 'overview' | 'stockPool' | 'sentiment' | 'dragonTiger' | 'riskAlert';

export default function SealPlatePage() {
  const [report, setReport] = useState<SealPlateReportResponse | null>(null);
  const [stats, setStats] = useState<SealPlateStatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [minScore, setMinScore] = useState(60);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [selectedStock, setSelectedStock] = useState<SealPlateStockResponse | null>(null);
  const [showEightStandard, setShowEightStandard] = useState(false);

  const fetchReport = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const data = await sealPlateApi.runAnalysis({ minScore, force: true });
      setReport(data);
    } catch (err: any) {
      setError(err?.message || '获取打板数据失败');
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [minScore]);

  const fetchStats = useCallback(async () => {
    try {
      const data = await sealPlateApi.getStats();
      setStats(data);
    } catch (err) {
      console.error('获取统计数据失败:', err);
    }
  }, []);

  useEffect(() => {
    fetchReport();
    fetchStats();
  }, [fetchReport, fetchStats]);

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case '乐观': return 'success';
      case '中性': return 'warning';
      case '谨慎': return 'danger';
      default: return 'default';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-500';
    if (score >= 70) return 'text-emerald-500';
    if (score >= 60) return 'text-yellow-500';
    return 'text-gray-500';
  };

  const formatSealTime = (time: string | null) => {
    if (!time) return '--:--';
    try {
      const date = new Date(time);
      return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false });
    } catch {
      return '--:--';
    }
  };

  const StockCard = ({ stock, index }: { stock: SealPlateStockResponse; index: number }) => (
    <div className="bg-card hover:bg-card/80 rounded-lg p-4 border border-border/50 transition-colors">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold">{stock.name}</span>
          <span className="text-sm text-muted-foreground">{stock.code}</span>
          {index < 3 && <Crown className="w-4 h-4 text-yellow-500" />}
        </div>
        <div className={`text-xl font-bold ${getScoreColor(stock.score)}`}>
          {stock.score}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 text-sm mb-3">
        <div className="flex justify-between">
          <span className="text-muted-foreground">涨幅</span>
          <span className={stock.changePct > 0 ? 'text-red-500' : 'text-green-500'}>
            +{stock.changePct.toFixed(2)}%
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">封板时间</span>
          <span>{formatSealTime(stock.sealTime)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">换手率</span>
          <span>{stock.turnoverRate.toFixed(2)}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">封单金额</span>
          <span>{stock.sealAmount >= 10000 ? `${(stock.sealAmount / 10000).toFixed(1)}亿` : `${stock.sealAmount.toFixed(0)}万`}</span>
        </div>
      </div>

      {stock.sector && (
        <Badge variant="info" className="mb-2">
          {stock.sector}
        </Badge>
      )}

      {stock.reason && (
        <p className="text-xs text-muted-foreground line-clamp-2">
          {stock.reason}
        </p>
      )}

      <div className="flex items-center gap-2 mt-2">
        {stock.openCount > 0 && (
          <Badge variant="danger" className="text-xs">
            开板{stock.openCount}次
          </Badge>
        )}
        {stock.score >= 80 && (
          <Badge variant="success" className="text-xs">
            强烈看多
          </Badge>
        )}
      </div>
    </div>
  );

  if (error) {
    return (
      <div className="p-6">
        <Card className="p-6">
          <div className="flex items-center gap-2 text-red-500 mb-4">
            <AlertTriangle className="w-5 h-5" />
            <span>{error}</span>
          </div>
          <Button onClick={() => fetchReport()} variant="primary">
            重新加载
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-red-500/10 rounded-lg">
            <Zap className="w-6 h-6 text-red-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">打板助手</h1>
            <p className="text-sm text-muted-foreground">监控涨停板 · 捕捉龙头股</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">最低评分</span>
            <select
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="px-3 py-2 bg-background border border-border rounded-lg text-sm"
            >
              <option value={50}>50</option>
              <option value={60}>60</option>
              <option value={70}>70</option>
              <option value={80}>80</option>
            </select>
          </div>
          <Button onClick={() => fetchReport()} disabled={loading} variant="primary">
            {loading ? <Loading /> : <RefreshCw className="w-4 h-4 mr-2" />}
            刷新数据
          </Button>
        </div>
      </div>

      {/* 功能Tab导航 */}
      <div className="flex gap-2 border-b border-border overflow-x-auto">
        <button
          className={`flex items-center gap-2 px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
            activeTab === 'overview'
              ? 'border-red-500 text-red-500'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('overview')}
        >
          <Zap className="w-4 h-4" />
          概览
        </button>
        <button
          className={`flex items-center gap-2 px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
            activeTab === 'stockPool'
              ? 'border-red-500 text-red-500'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('stockPool')}
        >
          <Layers className="w-4 h-4" />
          股票池
        </button>
        <button
          className={`flex items-center gap-2 px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
            activeTab === 'sentiment'
              ? 'border-red-500 text-red-500'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('sentiment')}
        >
          <Brain className="w-4 h-4" />
          情绪周期
        </button>
        <button
          className={`flex items-center gap-2 px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
            activeTab === 'dragonTiger'
              ? 'border-red-500 text-red-500'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('dragonTiger')}
        >
          <Crown className="w-4 h-4" />
          龙虎榜
        </button>
        <button
          className={`flex items-center gap-2 px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
            activeTab === 'riskAlert'
              ? 'border-red-500 text-red-500'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('riskAlert')}
        >
          <AlertTriangle className="w-4 h-4" />
          风险预警
        </button>
      </div>

      {/* 八项标准检查弹窗 */}
      {showEightStandard && selectedStock && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-2xl">
            <EightStandardChecklist
              stockCode={selectedStock.code}
              stockName={selectedStock.name}
              onClose={() => setShowEightStandard(false)}
            />
          </div>
        </div>
      )}

      {/* Tab内容区域 */}
      {activeTab === 'overview' && (
        <>
          {/* 概览Tab内容 */}
          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              label="涨停总数"
              value={report?.totalLimitUp || 0}
              icon={<Flame className="w-5 h-5" />}
              hint={stats ? `${(report?.totalLimitUp || 0) - stats.avgLimitUp > 0 ? '+' : ''}${stats.avgLimitUp > 0 ? (report?.totalLimitUp || 0) - stats.avgLimitUp : 0} vs 日均` : undefined}
            />
            <StatCard
              label="强势股"
              value={report?.strongStocks.length || 0}
              icon={<TrendingUp className="w-5 h-5" />}
              hint={`评分>${minScore}`}
            />
            <StatCard
              label="市场情绪"
              value={<><span className={getSentimentColor(report?.marketSentiment || '中性')}>{report?.sentimentScore || 50}</span><span className="text-sm text-muted-foreground">/100</span></>}
              icon={<BarChart3 className="w-5 h-5" />}
              hint={report?.marketSentiment || '中性'}
            />
            <StatCard
              label="龙头股"
              value={report?.leaderStocks.length || 0}
              icon={<Crown className="w-5 h-5" />}
            />
          </div>

          {/* Market Distribution */}
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <div className="p-4 text-center">
                <div className="text-2xl font-bold">{report?.mainBoard || 0}</div>
                <div className="text-sm text-muted-foreground">主板</div>
              </div>
            </Card>
            <Card>
              <div className="p-4 text-center">
                <div className="text-2xl font-bold">{report?.gem || 0}</div>
                <div className="text-sm text-muted-foreground">创业板</div>
              </div>
            </Card>
            <Card>
              <div className="p-4 text-center">
                <div className="text-2xl font-bold">{report?.star || 0}</div>
                <div className="text-sm text-muted-foreground">科创板</div>
              </div>
            </Card>
          </div>

          {/* Warnings */}
          {report?.warnings && report.warnings.length > 0 && (
            <Card className="border-orange-500/50 bg-orange-500/5">
              <div className="flex items-center gap-2 text-orange-500 mb-2">
                <AlertTriangle className="w-5 h-5" />
                <span className="font-medium">风险提示</span>
              </div>
              <ul className="space-y-1">
                {report.warnings.map((warning: string, i: number) => (
                  <li key={i} className="text-sm text-orange-600 dark:text-orange-400">
                    • {warning}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Sector Hot */}
          {report?.sectorHot && report.sectorHot.length > 0 && (
            <Card title="板块热度">
              <div className="flex items-center gap-2 mb-3">
                <Filter className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">当前热点板块</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {report.sectorHot.map((item: SectorHot, i: number) => (
                  <Badge key={i} variant="info" className="text-sm py-1 px-3">
                    {item.sector} ({item.count})
                  </Badge>
                ))}
              </div>
            </Card>
          )}

          {/* Strong Stocks */}
          {report?.strongStocks && report.strongStocks.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Flame className="w-5 h-5 text-red-500" />
                强势涨停 ({report.strongStocks.length}只)
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {report.strongStocks.map((stock: SealPlateStockResponse, index: number) => (
                  <div
                    key={stock.code}
                    className="cursor-pointer"
                    onClick={() => {
                      setSelectedStock(stock);
                      setShowEightStandard(true);
                    }}
                  >
                    <StockCard stock={stock} index={index} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Watch Stocks */}
          {report?.watchStocks && report.watchStocks.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-yellow-500" />
                关注标的 ({report.watchStocks.length}只)
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {report.watchStocks.map((stock: SealPlateStockResponse) => (
                  <div
                    key={stock.code}
                    className="cursor-pointer"
                    onClick={() => {
                      setSelectedStock(stock);
                      setShowEightStandard(true);
                    }}
                  >
                    <StockCard stock={stock} index={-1} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Leader Stocks */}
          {report?.leaderStocks && report.leaderStocks.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Crown className="w-5 h-5 text-yellow-500" />
                龙头股 ({report.leaderStocks.length}只)
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {report.leaderStocks.map((stock: SealPlateStockResponse, index: number) => (
                  <div
                    key={stock.code}
                    className="cursor-pointer"
                    onClick={() => {
                      setSelectedStock(stock);
                      setShowEightStandard(true);
                    }}
                  >
                    <StockCard stock={stock} index={index} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Footer Info */}
          {report && (
            <div className="text-center text-sm text-muted-foreground">
              数据更新时间: {new Date(report.generatedAt).toLocaleString('zh-CN')}
            </div>
          )}
        </>
      )}

      {/* 股票池Tab */}
      {activeTab === 'stockPool' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <StockPoolPanel
            onStockSelect={(code: string) => {
              const stock = [...(report?.strongStocks || []), ...(report?.watchStocks || [])]
                .find(s => s.code === code);
              if (stock) {
                setSelectedStock(stock);
                setShowEightStandard(true);
              }
            }}
          />
          <Card title="打板八项标准">
            <div className="flex items-center gap-2 mb-3">
              <Shield className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">决策纪律检查标准</span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2 p-2 bg-green-500/10 rounded">
                <CheckIcon />
                <span>1. 流通市值 30亿-150亿</span>
              </div>
              <div className="flex items-center gap-2 p-2 bg-green-500/10 rounded">
                <CheckIcon />
                <span>2. 换手率 5%-20%</span>
              </div>
              <div className="flex items-center gap-2 p-2 bg-green-500/10 rounded">
                <CheckIcon />
                <span>3. 量能比 &gt;1.5倍</span>
              </div>
              <div className="flex items-center gap-2 p-2 bg-green-500/10 rounded">
                <CheckIcon />
                <span>4. 封板时间 &lt;10:30</span>
              </div>
              <div className="flex items-center gap-2 p-2 bg-green-500/10 rounded">
                <CheckIcon />
                <span>5. 开板次数 ≤1次</span>
              </div>
              <div className="flex items-center gap-2 p-2 bg-green-500/10 rounded">
                <CheckIcon />
                <span>6. 封单金额 &gt;流通市值1%</span>
              </div>
              <div className="flex items-center gap-2 p-2 bg-green-500/10 rounded">
                <CheckIcon />
                <span>7. 题材热度 TOP10</span>
              </div>
              <div className="flex items-center gap-2 p-2 bg-green-500/10 rounded">
                <CheckIcon />
                <span>8. 股价位置 低位/突破</span>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* 情绪周期Tab */}
      {activeTab === 'sentiment' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <SentimentDashboard />
          <Card title="情绪周期说明">
            <div className="space-y-4 text-sm">
              <div className="space-y-2">
                <p className="font-medium text-blue-500">冰点期 (0-20)</p>
                <p className="text-muted-foreground">空仓休息，极小仓位试错首板</p>
              </div>
              <div className="space-y-2">
                <p className="font-medium text-green-500">启动期 (21-40)</p>
                <p className="text-muted-foreground">试错参与空间板、首板一进二</p>
              </div>
              <div className="space-y-2">
                <p className="font-medium text-emerald-500">发酵期 (41-60)</p>
                <p className="text-muted-foreground">积极参与总龙头和核心股</p>
              </div>
              <div className="space-y-2">
                <p className="font-medium text-orange-500">高潮期 (61-80)</p>
                <p className="text-muted-foreground">逐步卖出，兑现利润，不追高</p>
              </div>
              <div className="space-y-2">
                <p className="font-medium text-red-500">退潮期 (81-100)</p>
                <p className="text-muted-foreground">果断空仓，不接飞刀</p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* 龙虎榜Tab */}
      {activeTab === 'dragonTiger' && (
        <DragonTigerList />
      )}

      {/* 风险预警Tab */}
      {activeTab === 'riskAlert' && (
        <RiskAlertPanel />
      )}

      {/* 空数据提示 */}
      {loading && !report ? (
        <div className="flex items-center justify-center h-64">
          <Loading label="正在获取涨停板数据..." />
        </div>
      ) : !report || report.totalLimitUp === 0 ? (
        <EmptyState
          icon={<Zap className="w-12 h-12" />}
          title="暂无涨停数据"
          description="今日暂无涨停板数据，请稍后再试"
          action={
            <Button onClick={() => fetchReport()} variant="primary">
              重新加载
            </Button>
          }
        />
      ) : null}
    </div>
  );
}

// CheckIcon 组件
function CheckIcon() {
  return (
    <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  );
}
