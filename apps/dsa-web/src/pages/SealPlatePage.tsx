import { useState, useEffect, useCallback, useMemo } from 'react';
import { Zap, TrendingUp, AlertTriangle, Flame, Crown, BarChart3, RefreshCw, Filter, Brain, Shield, Layers, Calendar, Target, TrendingDown, CheckCircle, XCircle, Database, ClipboardList, Swords, Star, StarOff, Info } from 'lucide-react';
import { Button } from '@/components/common/Button';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { StatCard } from '@/components/common/StatCard';
import { Loading } from '@/components/common/Loading';
import { EmptyState } from '@/components/common/EmptyState';
import { Tooltip } from '@/components/common/Tooltip';
import { sealPlateApi } from '@/api/sealPlate';
import { StockNameDisplay } from '@/components/common/StockNameDisplay';
import type {
  SealPlateReportResponse, SealPlateStockResponse, SealPlateStatsResponse, SectorHot,
  RecommendationResponse, PositionRecResponse, StockRiskAnalysisResponse
} from '@/types/sealPlate';
import SentimentDashboard from '@/components/sealPlate/SentimentDashboard';
import StockPoolPanel from '@/components/sealPlate/StockPoolPanel';
import DragonTigerList from '@/components/sealPlate/DragonTigerList';
import EightStandardChecklist from '@/components/sealPlate/EightStandardChecklist';
import DataSourcePanel from '@/components/sealPlate/DataSourcePanel';
import ReviewPanel from '@/components/sealPlate/ReviewPanel';
import StrategiesPanel from '@/components/sealPlate/StrategiesPanel';
import CombinedAnalysisPanel from '@/components/sealPlate/CombinedAnalysisPanel';
import RecommendationManagementPanel from '@/components/sealPlate/RecommendationManagementPanel';

// Tab类型
type TabType = 'overview' | 'stockPool' | 'sentiment' | 'dragonTiger' | 'recommend' | 'strategies' | 'dataSources' | 'recommendReview' | 'combinedAnalysis' | 'recommendManagement';

export default function SealPlatePage() {
  const [report, setReport] = useState<SealPlateReportResponse | null>(null);
  const [stats, setStats] = useState<SealPlateStatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [minScore, setMinScore] = useState(80);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [selectedStock, setSelectedStock] = useState<SealPlateStockResponse | null>(null);
  const [showEightStandard, setShowEightStandard] = useState(false);

  // 日期选择
  const [effectiveDate, setEffectiveDate] = useState<string>('');
  const [dateLabel, setDateLabel] = useState<string>('');
  const [selectedDate, setSelectedDate] = useState<string>('');

  // 推荐
  const [recommendations, setRecommendations] = useState<RecommendationResponse | null>(null);
  const [recLoading, setRecLoading] = useState(false);

  // 复盘更新
  const [updatingOutcome, setUpdatingOutcome] = useState<string | null>(null);

  // 自选股
  const [watchlistCodes, setWatchlistCodes] = useState<Set<string>>(new Set());
  const [watchlistAdding, setWatchlistAdding] = useState<string | null>(null);

  const fetchReport = useCallback(async (date?: string, showLoading = true) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const data = await sealPlateApi.runAnalysis({ minScore, force: true, date });
      setReport(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [minScore]);

  const fetchEffectiveDate = useCallback(async () => {
    try {
      const data = await sealPlateApi.getEffectiveDate();
      setEffectiveDate(data.date);
      setDateLabel(data.label);
      if (!selectedDate) {
        setSelectedDate(data.date);
      }
    } catch (err) {
      console.error('获取有效日期失败:', err);
    }
  }, [selectedDate]);

  const fetchRecommendations = useCallback(async (date?: string) => {
    setRecLoading(true);
    try {
      const data = await sealPlateApi.getRecommendations({ date, save: true });
      setRecommendations(data);
    } catch (err) {
      console.error('获取推荐失败:', err);
    } finally {
      setRecLoading(false);
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const data = await sealPlateApi.getStats();
      setStats(data);
    } catch (err) {
      console.error('获取统计数据失败:', err);
    }
  }, []);

  const fetchWatchlistStatus = useCallback(async () => {
    try {
      const data = await sealPlateApi.getWatchlistStatus();
      setWatchlistCodes(new Set(data.codes));
    } catch {
      // 静默失败
    }
  }, []);

  const handleAddToWatchlist = useCallback(async (code: string, name: string, score: number, sector: string | null) => {
    setWatchlistAdding(code);
    try {
      await sealPlateApi.addToWatchlist({ code, name, score, sector, source: 'recommend' });
      setWatchlistCodes(prev => new Set([...prev, code]));
    } catch {
      // 静默失败
    } finally {
      setWatchlistAdding(null);
    }
  }, []);

  const handleRemoveFromWatchlist = useCallback(async (code: string) => {
    try {
      await sealPlateApi.removeFromWatchlist(code);
      setWatchlistCodes(prev => {
        const next = new Set(prev);
        next.delete(code);
        return next;
      });
    } catch {
      // 静默失败
    }
  }, []);

  useEffect(() => {
    fetchEffectiveDate();
    fetchWatchlistStatus();
  }, [fetchEffectiveDate, fetchWatchlistStatus]);

  useEffect(() => {
    if (effectiveDate) {
      fetchReport(selectedDate || effectiveDate);
      fetchStats();
    }
  }, [effectiveDate]);

  useEffect(() => {
    if (activeTab === 'recommend' && effectiveDate) {
      fetchRecommendations(selectedDate || effectiveDate);
    }
  }, [activeTab, effectiveDate, selectedDate]);

  const handleDateChange = (newDate: string) => {
    setSelectedDate(newDate);
    fetchReport(newDate);
  };

  const handleUpdateOutcome = async (date: string, code: string, outcome: string) => {
    setUpdatingOutcome(code);
    try {
      await sealPlateApi.updateRecommendationOutcome(date, code, {
        outcome,
        actualReturnPct: outcome === '成功' ? 10 : outcome === '失败' ? -5 : 0,
      });
      // 刷新推荐
      fetchRecommendations(selectedDate || effectiveDate);
    } catch (err) {
      console.error('更新结果失败:', err);
    } finally {
      setUpdatingOutcome(null);
    }
  };

  // 按评分降序排列的股票列表
  const sortedStrongStocks = useMemo(
    () => [...(report?.strongStocks || [])].sort((a, b) => b.score - a.score),
    [report?.strongStocks],
  );
  const sortedWatchStocks = useMemo(
    () => [...(report?.watchStocks || [])].sort((a, b) => b.score - a.score),
    [report?.watchStocks],
  );
  const sortedLeaderStocks = useMemo(
    () => [...(report?.leaderStocks || [])].sort((a, b) => b.score - a.score),
    [report?.leaderStocks],
  );

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

  const StockCard = ({ stock, index }: { stock: SealPlateStockResponse; index: number }) => {
    const sealStrengthLabel = stock.sealStrength === 'strong' ? '强势封板' : stock.sealStrength === 'medium' ? '一般封板' : stock.sealStrength === 'weak' ? '弱势封板' : '未知';
    const plateTypeLabel = stock.plateType === 'main' ? '主板' : stock.plateType === 'gem' ? '创业板' : stock.plateType === 'star' ? '科创板' : stock.plateType;

    return (
      <Tooltip
        content={
          <div className="space-y-1.5 min-w-[200px]">
            <div className="flex items-center gap-2 font-semibold text-sm">
              <StockNameDisplay name={stock.name} code={stock.code} />
            </div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
              <span className="text-muted-foreground">成交量:</span>
              <span>{stock.volume >= 10000 ? `${(stock.volume / 10000).toFixed(1)}万手` : `${stock.volume.toFixed(0)}手`}</span>
              <span className="text-muted-foreground">成交额:</span>
              <span>{stock.amount >= 100000000 ? `${(stock.amount / 100000000).toFixed(2)}亿` : `${(stock.amount / 10000).toFixed(0)}万`}</span>
              <span className="text-muted-foreground">封板强度:</span>
              <span className={stock.sealStrength === 'strong' ? 'text-green-500' : stock.sealStrength === 'weak' ? 'text-red-500' : 'text-yellow-500'}>{sealStrengthLabel}</span>
              <span className="text-muted-foreground">板块:</span>
              <span>{plateTypeLabel || '--'}</span>
            </div>
            {stock.reason && (
              <div className="pt-1.5 border-t border-border/30">
                <p className="text-muted-foreground leading-relaxed">{stock.reason}</p>
              </div>
            )}
          </div>
        }
        side="top"
      >
        <div className="bg-card hover:bg-card/80 rounded-lg p-4 border border-border/50 transition-colors cursor-pointer">
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <StockNameDisplay name={stock.name} code={stock.code} />
              {index < 3 && <Crown className="w-4 h-4 text-yellow-500 flex-shrink-0" />}
            </div>
            <div className={`text-xl font-bold flex-shrink-0 ml-2 ${getScoreColor(stock.score)}`}>
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
            <Badge variant="info" className="mb-2 truncate max-w-full">
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
            <span className="text-xs text-muted-foreground ml-auto flex items-center gap-0.5">
              <Info className="w-3 h-3" />悬停详情
            </span>
          </div>
        </div>
      </Tooltip>
    );
  };

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
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-red-500/10 rounded-lg">
            <Zap className="w-6 h-6 text-red-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">打板助手</h1>
            <p className="text-sm text-muted-foreground">监控涨停板 · 捕捉龙头股</p>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {/* 日期选择 */}
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-muted-foreground" />
            <input
              type="date"
              value={selectedDate
                ? `${selectedDate.slice(0,4)}-${selectedDate.slice(4,6)}-${selectedDate.slice(6,8)}`
                : effectiveDate
                  ? `${effectiveDate.slice(0,4)}-${effectiveDate.slice(4,6)}-${effectiveDate.slice(6,8)}`
                  : ''}
              onChange={(e) => {
                const d = e.target.value.replace(/-/g, '');
                handleDateChange(d);
              }}
              max={new Date().toISOString().split('T')[0]}
              className="px-3 py-2 bg-background border border-border rounded-lg text-sm"
            />
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              {dateLabel && `(${dateLabel})`}
            </span>
          </div>

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
          <Button onClick={() => fetchReport(selectedDate)} disabled={loading} variant="primary">
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
            activeTab === 'recommend'
              ? 'border-red-500 text-red-500'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('recommend')}
        >
          <Target className="w-4 h-4" />
          推荐建仓
        </button>
        <button
          className={`flex items-center gap-2 px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
            activeTab === 'strategies'
              ? 'border-red-500 text-red-500'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('strategies')}
        >
          <Swords className="w-4 h-4" />
          高胜率战法
        </button>
        <button
          className={`flex items-center gap-2 px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
            activeTab === 'dataSources'
              ? 'border-red-500 text-red-500'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('dataSources')}
        >
          <Database className="w-4 h-4" />
          数据源
        </button>
        <button
          className={`flex items-center gap-2 px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
            activeTab === 'recommendReview'
              ? 'border-red-500 text-red-500'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('recommendReview')}
        >
          <ClipboardList className="w-4 h-4" />
          推荐复盘
        </button>
        <button
          className={`flex items-center gap-2 px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
            activeTab === 'combinedAnalysis'
              ? 'border-red-500 text-red-500'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('combinedAnalysis')}
        >
          <Zap className="w-4 h-4" />
          战法共振
        </button>
        <button
          className={`flex items-center gap-2 px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
            activeTab === 'recommendManagement'
              ? 'border-blue-500 text-blue-500'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('recommendManagement')}
        >
          <BarChart3 className="w-4 h-4" />
          推荐管理
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

          {/* Strong Stocks - 按评分降序 */}
          {sortedStrongStocks.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Flame className="w-5 h-5 text-red-500" />
                强势涨停 ({sortedStrongStocks.length}只)
                <span className="text-xs text-muted-foreground font-normal ml-1">按评分排序</span>
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {sortedStrongStocks.map((stock: SealPlateStockResponse, index: number) => (
                  <div
                    key={stock.code}
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

          {/* Watch Stocks - 按评分降序 */}
          {sortedWatchStocks.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-yellow-500" />
                关注标的 ({sortedWatchStocks.length}只)
                <span className="text-xs text-muted-foreground font-normal ml-1">按评分排序</span>
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {sortedWatchStocks.map((stock: SealPlateStockResponse) => (
                  <div
                    key={stock.code}
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

          {/* Leader Stocks - 按评分降序 */}
          {sortedLeaderStocks.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Crown className="w-5 h-5 text-yellow-500" />
                龙头股 ({sortedLeaderStocks.length}只)
                <span className="text-xs text-muted-foreground font-normal ml-1">按评分排序</span>
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {sortedLeaderStocks.map((stock: SealPlateStockResponse, index: number) => (
                  <div
                    key={stock.code}
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

      {/* 推荐建仓Tab */}
      {activeTab === 'recommend' && (
        <div className="space-y-6">
          {/* 加载中 */}
          {recLoading && (
            <div className="flex items-center justify-center h-64">
              <Loading label="正在分析推荐建仓标的..." />
            </div>
          )}

          {/* 胜率总览 */}
          {recommendations?.winRate && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                label="总推荐笔数"
                value={recommendations.winRate.totalRecommendations}
                icon={<Target className="w-5 h-5" />}
              />
              <StatCard
                label="胜率"
                value={<span className={recommendations.winRate.winRate >= 50 ? 'text-green-500' : 'text-red-500'}>
                  {recommendations.winRate.winRate}%
                </span>}
                icon={<TrendingUp className="w-5 h-5" />}
                hint={`${recommendations.winRate.won}赢/${recommendations.winRate.lost}输`}
              />
              <StatCard
                label="近10笔胜率"
                value={<span className={recommendations.winRate.rollingWinRate10 >= 50 ? 'text-green-500' : 'text-yellow-500'}>
                  {recommendations.winRate.rollingWinRate10}%
                </span>}
                icon={<BarChart3 className="w-5 h-5" />}
                hint={`趋势: ${trendLabel(recommendations.winRate.trend)}`}
              />
              <StatCard
                label="平均收益"
                value={`${recommendations.winRate.avgReturn > 0 ? '+' : ''}${recommendations.winRate.avgReturn}%`}
                icon={recommendations.winRate.avgReturn >= 0 ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
                hint={`最高+${recommendations.winRate.maxReturn}%`}
              />
            </div>
          )}

          {/* 策略调整建议 */}
          {recommendations?.strategyNotes && recommendations.strategyNotes.length > 0 && (
            <Card className="border-blue-500/30 bg-blue-500/5">
              <div className="flex items-center gap-2 text-blue-500 mb-3">
                <Brain className="w-5 h-5" />
                <span className="font-medium">策略调整建议（基于连续复盘）</span>
              </div>
              <ul className="space-y-1">
                {recommendations.strategyNotes.map((note, i) => (
                  <li key={i} className="text-sm text-blue-600 dark:text-blue-400">
                    {note}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* 情绪周期标识 */}
          <div className="flex items-center gap-2">
            <Badge variant={sentimentBadge(recommendations?.sentimentPhase || '')}>
              情绪: {recommendations?.sentimentPhase || '--'}
            </Badge>
            <Badge variant="default">
              涨停: {recommendations?.totalLimitUp || 0}只
            </Badge>
          </div>

          {/* 买卖点策略说明 */}
          <Card className="border-green-500/30 bg-green-500/5">
            <div className="flex items-center gap-2 text-green-600 mb-3">
              <TrendingUp className="w-5 h-5" />
              <span className="font-medium">买卖策略指引</span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex items-start gap-2">
                <span className="text-green-500 mt-0.5">💰</span>
                <div>
                  <p className="font-medium text-green-700">买入原则</p>
                  <p className="text-muted-foreground">关注大基金/机构资金持续流入板块，竞价高开2%以内可轻仓参与，涨停价附近低吸为主。早盘10:30前封板为佳，尾盘突袭封板回避。</p>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-red-500 mt-0.5">🛑</span>
                <div>
                  <p className="font-medium text-red-700">卖出原则</p>
                  <p className="text-muted-foreground">5连板以上逐步减仓，开板≥3次资金分歧大应减仓。跌破5%无条件止损，不抱幻想。高换手率（{'>'}30%）警惕游资对倒。</p>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-yellow-500 mt-0.5">⚠️</span>
                <div>
                  <p className="font-medium text-yellow-700">风险规避</p>
                  <p className="text-muted-foreground">避开ST板块、壳资源等一日游高发板块。游资主导的标的快进快出，不与游资共舞。资金持续流出板块及时止损离场。</p>
                </div>
              </div>
            </div>
          </Card>

          {/* 推荐标的列表 */}
          {recommendations?.recommendations && recommendations.recommendations.length > 0 ? (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Target className="w-5 h-5 text-red-500" />
                今日建仓推荐 ({recommendations.recommendations.length}只)
              </h2>

              {recommendations.recommendations.map((rec: PositionRecResponse) => (
                <RecommendationCard
                  key={rec.code}
                  rec={rec}
                  date={recommendations.date}
                  updating={updatingOutcome === rec.code}
                  onUpdateOutcome={handleUpdateOutcome}
                  isInWatchlist={watchlistCodes.has(rec.code)}
                  watchlistAdding={watchlistAdding}
                  onAddToWatchlist={handleAddToWatchlist}
                  onRemoveFromWatchlist={handleRemoveFromWatchlist}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<Target className="w-12 h-12" />}
              title="暂无建仓推荐"
              description={recommendations ? "当前市场环境不符合推荐条件，请等待更好的时机" : "正在分析中..."}
            />
          )}
        </div>
      )}

      {/* 数据源Tab */}
      {activeTab === 'dataSources' && (
        <DataSourcePanel />
      )}

      {/* 高胜率战法Tab */}
      {activeTab === 'strategies' && (
        <StrategiesPanel />
      )}

      {/* 推荐复盘Tab */}
      {activeTab === 'recommendReview' && (
        <ReviewPanel />
      )}

      {/* 战法共振Tab - 战法+建仓合并分析 */}
      {activeTab === 'combinedAnalysis' && (
        <CombinedAnalysisPanel />
      )}

      {/* 推荐管理Tab - 记录/回溯/历史查询 */}
      {activeTab === 'recommendManagement' && (
        <RecommendationManagementPanel />
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

// 胜率趋势标签
function trendLabel(trend: string): string {
  switch (trend) {
    case 'improving': return '📈 上升';
    case 'declining': return '📉 下降';
    default: return '➡️ 稳定';
  }
}

// 情绪周期 Badge 颜色
function sentimentBadge(phase: string): 'info' | 'success' | 'warning' | 'danger' | 'default' {
  switch (phase) {
    case '冰点期': return 'default';
    case '启动期': return 'info';
    case '发酵期': return 'success';
    case '高潮期': return 'warning';
    case '退潮期': return 'danger';
    default: return 'default';
  }
}

// 推荐卡片组件
function RecommendationCard({
  rec, date, updating, onUpdateOutcome,
  isInWatchlist, watchlistAdding, onAddToWatchlist, onRemoveFromWatchlist
}: {
  rec: PositionRecResponse;
  date: string;
  updating: boolean;
  onUpdateOutcome: (date: string, code: string, outcome: string) => void;
  isInWatchlist: boolean;
  watchlistAdding: string | null;
  onAddToWatchlist: (code: string, name: string, score: number, sector: string | null) => void;
  onRemoveFromWatchlist: (code: string) => void;
}) {
  const [showRisk, setShowRisk] = useState(false);
  const [riskLoading, setRiskLoading] = useState(false);
  const [riskAnalysis, setRiskAnalysis] = useState<StockRiskAnalysisResponse | null>(null);

  const handleRiskAnalysis = async () => {
    if (riskAnalysis) {
      setShowRisk(!showRisk);
      return;
    }
    setRiskLoading(true);
    setShowRisk(true);
    try {
      const data = await sealPlateApi.getStockRiskAnalysis(rec.code, date);
      setRiskAnalysis(data);
    } catch {
      setRiskAnalysis(null);
    } finally {
      setRiskLoading(false);
    }
  };

  return (
    <Card className={rec.confidence === '高'
      ? 'border-green-500/30 bg-green-500/5'
      : rec.confidence === '中'
        ? 'border-yellow-500/30 bg-yellow-500/5'
        : ''}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-sm font-mono text-muted-foreground">#{rec.rank}</span>
          <div>
            <div className="flex items-center gap-2">
              <StockNameDisplay name={rec.name} code={rec.code} />
            </div>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant={rec.confidence === '高' ? 'success' : rec.confidence === '中' ? 'warning' : 'default'}>
                置信度: {rec.confidence}
              </Badge>
              <Badge variant="info">
                评分: {rec.score}
              </Badge>
              {rec.sector && <Badge variant="default">{rec.sector}</Badge>}
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm text-muted-foreground">建议仓位</div>
          <div className="text-xl font-bold text-green-500">{rec.suggestedPositionPct}%</div>
        </div>
      </div>

      {/* 推荐理由 */}
      <div className="mb-3">
        <div className="text-xs text-muted-foreground mb-1 font-medium">推荐理由</div>
        <ul className="space-y-0.5">
          {rec.reasons.map((reason, i) => (
            <li key={i} className="text-sm flex items-start gap-1">
              <span className="text-green-500 mt-1">•</span>
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* 风险提示 */}
      {rec.riskWarnings.length > 0 && (
        <div className="mb-3 p-2 bg-orange-500/10 rounded">
          <div className="text-xs text-orange-500 mb-1 font-medium">⚠️ 风险提示</div>
          <ul className="space-y-0.5">
            {rec.riskWarnings.map((w, i) => (
              <li key={i} className="text-xs text-orange-600 dark:text-orange-400">• {w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* 快速数据 */}
      <div className="grid grid-cols-4 gap-2 text-xs mb-3">
        <div>
          <span className="text-muted-foreground">涨幅</span>
          <span className="ml-1 text-red-500">+{rec.changePct.toFixed(2)}%</span>
        </div>
        <div>
          <span className="text-muted-foreground">封板</span>
          <span className="ml-1">{rec.sealTime || '--'}</span>
        </div>
        <div>
          <span className="text-muted-foreground">封单</span>
          <span className="ml-1">{rec.sealAmount >= 10000 ? `${(rec.sealAmount/10000).toFixed(1)}亿` : `${rec.sealAmount.toFixed(0)}万`}</span>
        </div>
        <div>
          <span className="text-muted-foreground">连板</span>
          <span className="ml-1">{rec.consecutiveDays}板</span>
        </div>
      </div>

      {/* 深度风险分析（可展开） */}
      <div className="mb-3">
        <Button
          size="sm"
          variant="ghost"
          onClick={handleRiskAnalysis}
          className="text-xs"
        >
          <AlertTriangle className="w-3 h-3 mr-1" />
          {showRisk && riskAnalysis ? '收起风险分析' : '深度风险分析（游资/一日游/封板质量）'}
        </Button>
        {showRisk && (
          <div className="mt-2 p-3 bg-muted/30 rounded-lg border border-border/50">
            {riskLoading ? (
              <Loading label="分析中..." />
            ) : riskAnalysis ? (
              <div className="space-y-3 text-xs">
                {/* 风险等级标识 */}
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">综合风险：</span>
                  <Badge variant={riskAnalysis.riskLevel === 'high' ? 'danger' : riskAnalysis.riskLevel === 'medium' ? 'warning' : 'success'}>
                    {riskAnalysis.riskLevel === 'high' ? '🔴 高风险' : riskAnalysis.riskLevel === 'medium' ? '🟡 中风险' : '🟢 低风险'}
                  </Badge>
                  <span className="text-muted-foreground">评分 {riskAnalysis.riskScore}/100</span>
                </div>

                {/* 封板质量 */}
                <div>
                  <span className="text-muted-foreground">封板质量：</span>
                  <span className={
                    riskAnalysis.sealQuality === '差' ? 'text-red-500' :
                    riskAnalysis.sealQuality === '一般' ? 'text-yellow-500' : 'text-green-500'
                  }>{riskAnalysis.sealQuality}</span>
                </div>

                {/* 游资风险 */}
                {riskAnalysis.hotMoneyRisk.length > 0 && (
                  <div className="p-2 bg-yellow-500/10 rounded border border-yellow-500/20">
                    <p className="font-medium text-yellow-600 mb-1">⚡ 游资风险</p>
                    {riskAnalysis.hotMoneyRisk.map((r, i) => (
                      <p key={i} className="text-yellow-600">• {r}</p>
                    ))}
                  </div>
                )}

                {/* 一日游风险 */}
                {riskAnalysis.oneDayTourRisk.length > 0 && (
                  <div className="p-2 bg-orange-500/10 rounded border border-orange-500/20">
                    <p className="font-medium text-orange-600 mb-1">🔴 一日游风险</p>
                    {riskAnalysis.oneDayTourRisk.map((r, i) => (
                      <p key={i} className="text-orange-600">• {r}</p>
                    ))}
                  </div>
                )}

                {/* 换手率警告 */}
                {riskAnalysis.turnoverWarning && (
                  <p className="text-red-500">⚠️ {riskAnalysis.turnoverWarning}</p>
                )}

                {/* 操作建议 */}
                <div className="p-2 bg-blue-500/10 rounded border border-blue-500/20">
                  <p className="font-medium text-blue-600 mb-1">📋 操作建议</p>
                  {riskAnalysis.suggestions.map((s, i) => (
                    <p key={i} className="text-blue-600">• {s}</p>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">分析失败，请稍后重试</p>
            )}
          </div>
        )}
      </div>

      {/* 复盘操作 */}
      <div className="flex items-center gap-2 pt-2 border-t border-border">
        <span className="text-xs text-muted-foreground">复盘标记:</span>
        <Button
          size="sm"
          variant="primary"
          onClick={() => onUpdateOutcome(date, rec.code, '成功')}
          disabled={updating}
        >
          <CheckCircle className="w-3 h-3 mr-1" />成功
        </Button>
        <Button
          size="sm"
          variant="danger"
          onClick={() => onUpdateOutcome(date, rec.code, '失败')}
          disabled={updating}
        >
          <XCircle className="w-3 h-3 mr-1" />失败
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onUpdateOutcome(date, rec.code, '持平')}
          disabled={updating}
        >
          持平
        </Button>

        {/* 自选股操作 */}
        <div className="ml-auto">
          {isInWatchlist ? (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onRemoveFromWatchlist(rec.code)}
              className="text-amber-500 hover:text-red-500"
              title="已加入自选，点击取消关注"
            >
              <Star className="w-3.5 h-3.5 mr-1 fill-amber-500" />
              <span className="text-xs">已关注</span>
            </Button>
          ) : (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onAddToWatchlist(rec.code, rec.name, rec.score, rec.sector)}
              disabled={watchlistAdding === rec.code}
              className="text-muted-foreground hover:text-amber-500"
              title="一键加入自选"
            >
              {watchlistAdding === rec.code ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 mr-1 animate-spin" />
                  <span className="text-xs">添加中</span>
                </>
              ) : (
                <>
                  <StarOff className="w-3.5 h-3.5 mr-1" />
                  <span className="text-xs">加入自选</span>
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
