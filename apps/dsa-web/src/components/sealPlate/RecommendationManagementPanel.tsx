import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Target, Calendar, BarChart3,
  Search, RefreshCw, ChevronLeft, ChevronRight, ChevronDown, ChevronRight as ChevronRightIcon,
  Info, AlertTriangle, Star, ExternalLink, Clock, Layers,
} from 'lucide-react';
import { Button } from '@/components/common/Button';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Loading } from '@/components/common/Loading';
import { EmptyState } from '@/components/common/EmptyState';
import { sealPlateApi } from '@/api/sealPlate';
import type {
  RecommendationRecordListResponse, WinRateBacktestResponse,
  HistoricalWinRateResponse, AvailableDatesResponse, RecommendationRecordResponse,
} from '@/types/sealPlate';

type SubTabType = 'records' | 'backtest' | 'history';

export default function RecommendationManagementPanel() {
  const [activeSubTab, setActiveSubTab] = useState<SubTabType>('records');

  return (
    <div className="space-y-6">
      {/* 子Tab导航 */}
      <div className="flex gap-2 border-b border-border overflow-x-auto">
        <button
          className={`flex items-center gap-2 px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
            activeSubTab === 'records'
              ? 'border-blue-500 text-blue-500'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveSubTab('records')}
        >
          <Layers className="w-4 h-4" />
          推荐建仓记录
        </button>
        <button
          className={`flex items-center gap-2 px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
            activeSubTab === 'backtest'
              ? 'border-blue-500 text-blue-500'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveSubTab('backtest')}
        >
          <BarChart3 className="w-4 h-4" />
          每日胜率回溯
        </button>
        <button
          className={`flex items-center gap-2 px-4 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
            activeSubTab === 'history'
              ? 'border-blue-500 text-blue-500'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveSubTab('history')}
        >
          <Calendar className="w-4 h-4" />
          历史胜率查询
        </button>
      </div>

      {/* 子Tab内容 */}
      {activeSubTab === 'records' && <RecommendationRecordsPanel />}
      {activeSubTab === 'backtest' && <WinRateBacktestPanel />}
      {activeSubTab === 'history' && <HistoricalWinRatePanel />}
    </div>
  );
}

// ========================
//  子面板1：推荐建仓记录
// ========================

function RecommendationRecordsPanel() {
  const [data, setData] = useState<RecommendationRecordListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [pageSize] = useState(20);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [expandedCode, setExpandedCode] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, unknown> = {
        limit: pageSize,
        offset: page * pageSize,
      };
      if (dateFrom) (params as Record<string, string>).dateFrom = dateFrom.replace(/-/g, '');
      if (dateTo) (params as Record<string, string>).dateTo = dateTo.replace(/-/g, '');
      const result = await sealPlateApi.getRecommendationRecords(params as any);
      setData(result);
    } catch (err: any) {
      setError(err?.message || '获取推荐记录失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, dateFrom, dateTo]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

  // 按日期分组
  const groupedByDate = useMemo(() => {
    if (!data?.items) return [];
    const groups: Record<string, RecommendationRecordResponse[]> = {};
    for (const item of data.items) {
      if (!groups[item.date]) groups[item.date] = [];
      groups[item.date].push(item);
    }
    return Object.entries(groups).sort((a, b) => b[0].localeCompare(a[0]));
  }, [data]);

  // 统计
  const stats = useMemo(() => {
    if (!data?.items) return { total: 0, settled: 0, won: 0 };
    let settled = 0, won = 0;
    for (const item of data.items) {
      if (item.outcome) settled++;
      if (item.won) won++;
    }
    return {
      total: data.total,
      settled,
      won,
      winRate: settled > 0 ? (won / settled * 100).toFixed(1) : '--',
    };
  }, [data]);

  if (loading && !data) {
    return <Loading label="加载推荐记录..." />;
  }

  if (error) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-2 text-red-500 mb-4">
          <AlertTriangle className="w-5 h-5" />
          <span>{error}</span>
        </div>
        <Button onClick={fetchData} variant="primary">重新加载</Button>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* 筛选栏 */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-muted-foreground" />
          <input
            type="date"
            value={dateFrom}
            onChange={e => { setDateFrom(e.target.value); setPage(0); }}
            className="px-3 py-1.5 bg-background border border-border rounded-lg text-sm"
            placeholder="起始日期"
          />
          <span className="text-muted-foreground text-sm">至</span>
          <input
            type="date"
            value={dateTo}
            onChange={e => { setDateTo(e.target.value); setPage(0); }}
            className="px-3 py-1.5 bg-background border border-border rounded-lg text-sm"
            placeholder="结束日期"
          />
        </div>
        <Button onClick={fetchData} variant="ghost" size="sm">
          <Search className="w-4 h-4 mr-1" />筛选
        </Button>
        {(dateFrom || dateTo) && (
          <Button onClick={() => { setDateFrom(''); setDateTo(''); setPage(0); }} variant="ghost" size="sm">
            清除筛选
          </Button>
        )}
      </div>

      {/* 统计概览 */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-3 text-center">
          <div className="text-2xl font-bold text-blue-500">{stats.total}</div>
          <div className="text-xs text-muted-foreground">总推荐次数</div>
        </Card>
        <Card className="p-3 text-center">
          <div className="text-2xl font-bold text-green-500">{stats.settled}</div>
          <div className="text-xs text-muted-foreground">已结算</div>
        </Card>
        <Card className="p-3 text-center">
          <div className="text-2xl font-bold text-orange-500">{stats.winRate}%</div>
          <div className="text-xs text-muted-foreground">胜率 ({stats.won}赢)</div>
        </Card>
      </div>

      {/* 记录列表（按日期分组） */}
      {groupedByDate.length > 0 ? (
        <div className="space-y-4">
          {groupedByDate.map(([date, items]) => (
            <div key={date}>
              {/* 日期标题 */}
              <div className="flex items-center gap-2 mb-3 sticky top-0 bg-background py-2 z-10">
                <Calendar className="w-4 h-4 text-blue-500" />
                <span className="font-semibold text-sm">{items[0]?.label || date}</span>
                <Badge variant="default" className="text-xs">
                  {items.length}只推荐
                </Badge>
                <Badge variant={
                  items[0]?.sentimentPhase === '退潮期' ? 'danger' :
                  items[0]?.sentimentPhase === '冰点期' ? 'default' :
                  items[0]?.sentimentPhase === '高潮期' ? 'warning' :
                  'success'
                } className="text-xs">
                  {items[0]?.sentimentPhase || '--'}
                </Badge>
              </div>

              {/* 该日期下的推荐列表 */}
              <div className="space-y-2">
                {items.map(rec => (
                  <Card
                    key={`${rec.date}-${rec.code}`}
                    className={`p-3 transition-colors ${
                      rec.outcome === '成功' ? 'border-green-500/20 bg-green-500/5' :
                      rec.outcome === '失败' ? 'border-red-500/20 bg-red-500/5' :
                      ''
                    }`}
                  >
                    {/* 主行 */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <span className="text-xs text-muted-foreground font-mono whitespace-nowrap">
                          <Clock className="w-3 h-3 inline mr-1" />
                          {rec.generatedAt ? new Date(rec.generatedAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '--:--'}
                        </span>
                        {/* 超链接 - 点击跳转详细分析 */}
                        <a
                          href={`/seal-plate?code=${rec.code}`}
                          className="font-bold text-sm hover:text-blue-500 transition-colors flex items-center gap-1 truncate"
                          title={`点击查看 ${rec.name}(${rec.code}) 详细分析`}
                        >
                          {rec.name}
                          <span className="text-xs text-muted-foreground font-mono">{rec.code}</span>
                          <ExternalLink className="w-3 h-3 opacity-50" />
                        </a>
                        <Badge variant={
                          rec.score >= 80 ? 'success' :
                          rec.score >= 70 ? 'warning' : 'default'
                        } className="text-xs whitespace-nowrap">
                          {rec.score}分
                        </Badge>
                        {rec.sector && (
                          <Badge variant="info" className="text-xs truncate max-w-[100px] whitespace-nowrap">
                            {rec.sector}
                          </Badge>
                        )}
                      </div>

                      <div className="flex items-center gap-3 flex-shrink-0">
                        <span className={`text-sm font-medium ${rec.changePct > 0 ? 'text-red-500' : 'text-green-500'}`}>
                          +{rec.changePct.toFixed(2)}%
                        </span>
                        {rec.outcome && (
                          <Badge variant={
                            rec.outcome === '成功' ? 'success' :
                            rec.outcome === '失败' ? 'danger' : 'default'
                          } className="text-xs">
                            {rec.outcome === '成功' ? '✅ 成功' :
                             rec.outcome === '失败' ? '❌ 失败' : '持平'}
                            {rec.actualReturnPct != null && (
                              <span className="ml-1">
                                ({rec.actualReturnPct > 0 ? '+' : ''}{rec.actualReturnPct}%)
                              </span>
                            )}
                          </Badge>
                        )}
                        <button
                          onClick={() => setExpandedCode(expandedCode === rec.code ? null : rec.code)}
                          className="p-1 hover:bg-muted rounded"
                        >
                          {expandedCode === rec.code ? (
                            <ChevronDown className="w-4 h-4 text-muted-foreground" />
                          ) : (
                            <ChevronRightIcon className="w-4 h-4 text-muted-foreground" />
                          )}
                        </button>
                      </div>
                    </div>

                    {/* 展开详情 */}
                    {expandedCode === rec.code && (
                      <div className="mt-3 pl-8 space-y-2 text-sm">
                        <div className="grid grid-cols-4 gap-3">
                          <div>
                            <span className="text-muted-foreground text-xs">封板时间</span>
                            <p>{rec.sealTime || '--'}</p>
                          </div>
                          <div>
                            <span className="text-muted-foreground text-xs">封单金额</span>
                            <p>{rec.sealAmount >= 10000 ? `${(rec.sealAmount/10000).toFixed(1)}亿` : `${rec.sealAmount.toFixed(0)}万`}</p>
                          </div>
                          <div>
                            <span className="text-muted-foreground text-xs">情绪指数</span>
                            <p>{rec.sentimentIndex}</p>
                          </div>
                          <div>
                            <span className="text-muted-foreground text-xs">情绪阶段</span>
                            <Badge variant={
                              rec.sentimentPhase === '退潮期' ? 'danger' :
                              rec.sentimentPhase === '冰点期' ? 'default' : 'success'
                            } className="text-xs">{rec.sentimentPhase}</Badge>
                          </div>
                        </div>
                        {rec.reasons.length > 0 && (
                          <div>
                            <span className="text-muted-foreground text-xs">推荐理由</span>
                            <ul className="mt-1 space-y-0.5">
                              {rec.reasons.map((r, i) => (
                                <li key={i} className="text-xs flex items-start gap-1">
                                  <span className="text-green-500 mt-0.5">•</span>
                                  {r}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {rec.reviewNote && (
                          <div className="p-2 bg-muted/30 rounded">
                            <span className="text-muted-foreground text-xs">复盘备注：</span>
                            <span className="text-xs">{rec.reviewNote}</span>
                          </div>
                        )}
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Target className="w-12 h-12" />}
          title="暂无推荐记录"
          description="还没有生成过建仓推荐"
        />
      )}

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="ghost" size="sm"
            disabled={page === 0}
            onClick={() => setPage(p => p - 1)}
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="text-sm text-muted-foreground">
            第 {page + 1} / {totalPages} 页 (共{data?.total}条)
          </span>
          <Button
            variant="ghost" size="sm"
            disabled={page >= totalPages - 1}
            onClick={() => setPage(p => p + 1)}
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      )}
    </div>
  );
}

// ========================
//  子面板2：每日胜率回溯
// ========================

function WinRateBacktestPanel() {
  const [data, setData] = useState<WinRateBacktestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [expandedDate, setExpandedDate] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await sealPlateApi.getWinRateBacktest({ days });
      setData(result);
    } catch (err: any) {
      setError(err?.message || '获取胜率回溯失败');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading && !data) {
    return <Loading label="计算胜率回溯..." />;
  }

  if (error) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-2 text-red-500 mb-4">
          <AlertTriangle className="w-5 h-5" />
          <span>{error}</span>
        </div>
        <Button onClick={fetchData} variant="primary">重新加载</Button>
      </Card>
    );
  }

  // 计算统计数据
  const winRateDistribution = useMemo(() => {
    if (!data?.dailyRecords) return { high: 0, medium: 0, low: 0 };
    let high = 0, medium = 0, low = 0;
    for (const d of data.dailyRecords) {
      if (d.settledCount === 0) continue;
      if (d.winRate >= 60) high++;
      else if (d.winRate >= 40) medium++;
      else low++;
    }
    return { high, medium, low };
  }, [data]);

  return (
    <div className="space-y-6">
      {/* 控制栏 */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">回溯天数:</span>
          <select
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            className="px-3 py-1.5 bg-background border border-border rounded-lg text-sm"
          >
            <option value={7}>近7天</option>
            <option value={14}>近14天</option>
            <option value={30}>近30天</option>
            <option value={60}>近60天</option>
            <option value={90}>近90天</option>
          </select>
        </div>
        <Button onClick={fetchData} variant="ghost" size="sm">
          <RefreshCw className="w-4 h-4 mr-1" />刷新
        </Button>
      </div>

      {/* 总览统计 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4 text-center">
          <div className="text-3xl font-bold text-blue-500">{data?.totalRecommendations || 0}</div>
          <div className="text-xs text-muted-foreground mt-1">总推荐次数</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-3xl font-bold text-green-500">
            {data?.overallWinRate != null ? `${data.overallWinRate}%` : '--'}
          </div>
          <div className="text-xs text-muted-foreground mt-1">整体胜率</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-3xl font-bold text-orange-500">
            {data?.avgReturn != null ? `${data.avgReturn > 0 ? '+' : ''}${data.avgReturn}%` : '--'}
          </div>
          <div className="text-xs text-muted-foreground mt-1">平均收益</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-3xl font-bold text-purple-500">{data?.totalSettled || 0}</div>
          <div className="text-xs text-muted-foreground mt-1">已结算 ({data?.totalWon || 0}赢)</div>
        </Card>
      </div>

      {/* 胜率分布 */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-3 text-center border-green-500/30 bg-green-500/5">
          <div className="text-lg font-bold text-green-500">{winRateDistribution.high}天</div>
          <div className="text-xs text-muted-foreground">高胜率 (≥60%)</div>
        </Card>
        <Card className="p-3 text-center border-yellow-500/30 bg-yellow-500/5">
          <div className="text-lg font-bold text-yellow-500">{winRateDistribution.medium}天</div>
          <div className="text-xs text-muted-foreground">中等胜率 (40-60%)</div>
        </Card>
        <Card className="p-3 text-center border-red-500/30 bg-red-500/5">
          <div className="text-lg font-bold text-red-500">{winRateDistribution.low}天</div>
          <div className="text-xs text-muted-foreground">低胜率 (&lt;40%)</div>
        </Card>
      </div>

      {/* 最佳/最差日 */}
      {(data?.bestDay || data?.worstDay) && (
        <div className="grid grid-cols-2 gap-4">
          {data.bestDay && (
            <Card className="p-4 border-green-500/30 bg-green-500/5">
              <div className="flex items-center gap-2 mb-2">
                <Star className="w-4 h-4 text-green-500" />
                <span className="font-medium text-green-600">最佳表现日</span>
              </div>
              <div className="space-y-1 text-sm">
                <p><span className="text-muted-foreground">日期：</span>{data.bestDay.date}</p>
                <p><span className="text-muted-foreground">胜率：</span>
                  <span className="text-green-500 font-bold">{data.bestDay.winRate}%</span>
                </p>
                <p><span className="text-muted-foreground">推荐：</span>{data.bestDay.settledCount}只，{data.bestDay.wonCount}只盈利</p>
              </div>
            </Card>
          )}
          {data.worstDay && (
            <Card className="p-4 border-red-500/30 bg-red-500/5">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="w-4 h-4 text-red-500" />
                <span className="font-medium text-red-600">最差表现日</span>
              </div>
              <div className="space-y-1 text-sm">
                <p><span className="text-muted-foreground">日期：</span>{data.worstDay.date}</p>
                <p><span className="text-muted-foreground">胜率：</span>
                  <span className="text-red-500 font-bold">{data.worstDay.winRate}%</span>
                </p>
                <p><span className="text-muted-foreground">推荐：</span>{data.worstDay.settledCount}只，{data.worstDay.wonCount}只盈利</p>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* 每日明细 */}
      {data?.dailyRecords && data.dailyRecords.length > 0 ? (
        <div className="space-y-3">
          <h3 className="font-semibold text-sm flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-blue-500" />
            每日胜率明细
          </h3>

          {/* 可视化胜率条 */}
          <div className="space-y-1">
            {data.dailyRecords.map(record => (
              <div key={record.date}>
                <div
                  className="flex items-center gap-2 py-1.5 px-2 hover:bg-muted/50 rounded cursor-pointer transition-colors"
                  onClick={() => setExpandedDate(expandedDate === record.date ? null : record.date)}
                >
                  <span className="text-xs text-muted-foreground w-[75px] flex-shrink-0">{record.label}</span>
                  {/* 胜率进度条 */}
                  <div className="flex-1 h-6 bg-muted rounded-full overflow-hidden relative">
                    <div
                      className={`h-full rounded-full transition-all ${
                        record.winRate >= 60 ? 'bg-green-500' :
                        record.winRate >= 40 ? 'bg-yellow-500' :
                        record.winRate > 0 ? 'bg-red-500' : 'bg-gray-300'
                      }`}
                      style={{ width: `${Math.max(record.winRate, 2)}%` }}
                    />
                    <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-foreground mix-blend-difference invert">
                      {record.settledCount > 0 ? `${record.winRate}%` : '待结算'}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground w-[60px] text-right flex-shrink-0">
                    {record.wonCount}/{record.settledCount}赢
                  </span>
                  <span className={`text-xs w-[55px] text-right flex-shrink-0 ${
                    record.avgReturn > 0 ? 'text-red-500' : record.avgReturn < 0 ? 'text-green-500' : 'text-muted-foreground'
                  }`}>
                    {record.avgReturn !== 0 ? `${record.avgReturn > 0 ? '+' : ''}${record.avgReturn}%` : '--'}
                  </span>
                  <Badge variant={
                    record.sentimentPhase === '退潮期' ? 'danger' :
                    record.sentimentPhase === '冰点期' ? 'default' :
                    record.sentimentPhase === '高潮期' ? 'warning' : 'success'
                  } className="text-xs flex-shrink-0">
                    {record.sentimentPhase}
                  </Badge>
                  {expandedDate === record.date ? (
                    <ChevronDown className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                  ) : (
                    <ChevronRightIcon className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                  )}
                </div>

                {/* 展开显示当日推荐详情 */}
                {expandedDate === record.date && record.recommendations.length > 0 && (
                  <div className="ml-[85px] mb-2 p-3 bg-muted/30 rounded-lg space-y-2">
                    {record.recommendations.map(rec => (
                      <div key={rec.code} className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{rec.name}</span>
                          <span className="text-xs text-muted-foreground font-mono">{rec.code}</span>
                          <Badge variant="default" className="text-xs">{rec.score}分</Badge>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={rec.changePct > 0 ? 'text-red-500' : 'text-green-500'}>
                            +{rec.changePct.toFixed(2)}%
                          </span>
                          {rec.outcome ? (
                            <Badge variant={rec.won ? 'success' : 'danger'} className="text-xs">
                              {rec.won ? '✅' : '❌'}
                              {rec.actualReturnPct != null && ` ${rec.actualReturnPct > 0 ? '+' : ''}${rec.actualReturnPct}%`}
                            </Badge>
                          ) : (
                            <Badge variant="default" className="text-xs">待结算</Badge>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <EmptyState
          icon={<BarChart3 className="w-12 h-12" />}
          title="暂无胜率数据"
          description="还没有足够的推荐记录进行胜率回溯"
        />
      )}
    </div>
  );
}

// ========================
//  子面板3：历史胜率查询
// ========================

function HistoricalWinRatePanel() {
  const [availableDates, setAvailableDates] = useState<AvailableDatesResponse | null>(null);
  const [selectedDate, setSelectedDate] = useState('');
  const [lookbackDays, setLookbackDays] = useState(5);
  const [data, setData] = useState<HistoricalWinRateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 加载可用日期
  useEffect(() => {
    sealPlateApi.getRecommendationDates().then(setAvailableDates).catch(console.error);
  }, []);

  const fetchHistory = useCallback(async () => {
    if (!selectedDate) return;
    setLoading(true);
    setError(null);
    try {
      const result = await sealPlateApi.getHistoricalWinRate(selectedDate.replace(/-/g, ''), lookbackDays);
      setData(result);
    } catch (err: any) {
      setError(err?.message || '查询失败');
    } finally {
      setLoading(false);
    }
  }, [selectedDate, lookbackDays]);

  // 获取胜率颜色
  const getWinRateColor = (rate: number) => {
    if (rate >= 60) return 'text-green-500';
    if (rate >= 40) return 'text-yellow-500';
    if (rate > 0) return 'text-red-500';
    return 'text-muted-foreground';
  };

  return (
    <div className="space-y-6">
      {/* 查询条件 */}
      <Card className="p-4">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">选择日期：</span>
            <select
              value={selectedDate}
              onChange={e => setSelectedDate(e.target.value)}
              className="px-3 py-2 bg-background border border-border rounded-lg text-sm min-w-[180px]"
            >
              <option value="">-- 请选择日期 --</option>
              {availableDates?.dates.map(d => (
                <option key={d.date} value={`${d.date.slice(0,4)}-${d.date.slice(4,6)}-${d.date.slice(6,8)}`}>
                  {d.label} ({d.count}只推荐
                  {d.winRate != null ? `, 胜率${d.winRate}%` : ''})
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">对比范围：</span>
            <select
              value={lookbackDays}
              onChange={e => setLookbackDays(Number(e.target.value))}
              className="px-3 py-2 bg-background border border-border rounded-lg text-sm"
            >
              <option value={3}>前后3天</option>
              <option value={5}>前后5天</option>
              <option value={7}>前后7天</option>
              <option value={10}>前后10天</option>
              <option value={14}>前后14天</option>
            </select>
          </div>
          <Button onClick={fetchHistory} variant="primary" size="sm" disabled={!selectedDate || loading}>
            <Search className="w-4 h-4 mr-1" />
            查询
          </Button>
        </div>
      </Card>

      {/* 加载状态 */}
      {loading && <Loading label="查询中..." />}

      {/* 错误 */}
      {error && (
        <Card className="p-4 border-red-500/30 bg-red-500/5">
          <div className="flex items-center gap-2 text-red-500">
            <AlertTriangle className="w-4 h-4" />
            {error}
          </div>
        </Card>
      )}

      {/* 查询结果 */}
      {data && !loading && (
        <div className="space-y-6">
          {/* 目标日期详情 */}
          {data.targetDetail ? (
            <Card className="p-4 border-blue-500/30 bg-blue-500/5">
              <div className="flex items-center gap-2 mb-3">
                <Target className="w-5 h-5 text-blue-500" />
                <h3 className="font-semibold text-blue-600">
                  {data.targetDetail.label} 推荐详情
                </h3>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div className="text-center">
                  <div className="text-2xl font-bold">{data.targetDetail.totalCount}</div>
                  <div className="text-xs text-muted-foreground">推荐数量</div>
                </div>
                <div className="text-center">
                  <div className={`text-2xl font-bold ${getWinRateColor(data.targetDetail.winRate)}`}>
                    {data.targetDetail.settledCount > 0 ? `${data.targetDetail.winRate}%` : '--'}
                  </div>
                  <div className="text-xs text-muted-foreground">胜率</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-500">{data.targetDetail.wonCount}</div>
                  <div className="text-xs text-muted-foreground">盈利</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-red-500">{data.targetDetail.lostCount}</div>
                  <div className="text-xs text-muted-foreground">亏损</div>
                </div>
              </div>

              {/* 推荐标的列表 */}
              {data.targetDetail.recommendations.length > 0 && (
                <div className="space-y-2">
                  {data.targetDetail.recommendations.map(rec => (
                    <div
                      key={rec.code}
                      className={`flex items-center justify-between p-2 rounded ${
                        rec.won === true ? 'bg-green-500/10' :
                        rec.won === false ? 'bg-red-500/10' : 'bg-muted/20'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{rec.name}</span>
                        <span className="text-xs text-muted-foreground font-mono">{rec.code}</span>
                        <Badge variant="default" className="text-xs">{rec.score}分</Badge>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">{rec.sector || '--'}</span>
                        {rec.outcome ? (
                          <Badge variant={rec.won ? 'success' : 'danger'} className="text-xs">
                            {rec.won ? '✅ 盈利' : '❌ 亏损'}
                            {rec.actualReturnPct != null && ` ${rec.actualReturnPct > 0 ? '+' : ''}${rec.actualReturnPct}%`}
                          </Badge>
                        ) : (
                          <Badge variant="default" className="text-xs">待结算</Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          ) : (
            <EmptyState
              icon={<Calendar className="w-12 h-12" />}
              title="该日期无推荐记录"
              description="请选择有推荐数据的日期"
            />
          )}

          {/* 趋势图 */}
          {data.trend.length > 0 && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <BarChart3 className="w-5 h-5 text-blue-500" />
                <h3 className="font-semibold">
                  前后 {data.lookbackDays} 天胜率趋势
                </h3>
              </div>

              <div className="space-y-2">
                {data.trend.map(item => (
                  <div
                    key={item.date}
                    className={`flex items-center gap-2 py-1.5 px-3 rounded transition-colors ${
                      item.isTarget ? 'bg-blue-500/10 ring-1 ring-blue-500/30' : 'hover:bg-muted/30'
                    }`}
                  >
                    <span className={`text-xs w-[75px] flex-shrink-0 ${item.isTarget ? 'font-bold text-blue-500' : 'text-muted-foreground'}`}>
                      {item.label}
                      {item.isTarget && ' ★'}
                    </span>
                    {/* 胜率条 */}
                    <div className="flex-1 h-5 bg-muted rounded-full overflow-hidden relative">
                      <div
                        className={`h-full rounded-full transition-all ${
                          item.winRate >= 60 ? 'bg-green-500' :
                          item.winRate >= 40 ? 'bg-yellow-500' :
                          item.winRate > 0 ? 'bg-red-500' : 'bg-gray-300'
                        }`}
                        style={{ width: `${Math.max(item.winRate, 2)}%` }}
                      />
                      <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-foreground mix-blend-difference invert">
                        {item.settled > 0 ? `${item.winRate}%` : '--'}
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground w-[50px] text-right flex-shrink-0">
                      {item.won}/{item.settled}赢
                    </span>
                    <span className="text-xs text-muted-foreground w-[30px] text-right flex-shrink-0">
                      {item.count}只
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* 整体统计 */}
          {data.overallStats && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Info className="w-5 h-5 text-blue-500" />
                <h3 className="font-semibold">整体胜率统计</h3>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <div className="text-xl font-bold">{data.overallStats.totalRecommendations}</div>
                  <div className="text-xs text-muted-foreground">总推荐</div>
                </div>
                <div className="text-center">
                  <div className={`text-xl font-bold ${getWinRateColor(data.overallStats.winRate)}`}>
                    {data.overallStats.winRate}%
                  </div>
                  <div className="text-xs text-muted-foreground">总胜率</div>
                </div>
                <div className="text-center">
                  <div className="text-xl font-bold">
                    {data.overallStats.avgReturn > 0 ? '+' : ''}{data.overallStats.avgReturn}%
                  </div>
                  <div className="text-xs text-muted-foreground">平均收益</div>
                </div>
                <div className="text-center">
                  <div className={`text-xl font-bold ${
                    data.overallStats.trend === 'improving' ? 'text-green-500' :
                    data.overallStats.trend === 'declining' ? 'text-red-500' : 'text-yellow-500'
                  }`}>
                    {data.overallStats.rollingWinRate10}%
                  </div>
                  <div className="text-xs text-muted-foreground">
                    近10笔胜率
                    ({data.overallStats.trend === 'improving' ? '📈上升' :
                      data.overallStats.trend === 'declining' ? '📉下降' : '➡️稳定'})
                  </div>
                </div>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* 无数据提示 */}
      {!data && !loading && !error && (
        <EmptyState
          icon={<Search className="w-12 h-12" />}
          title="选择日期查询"
          description="选择一个日期查看该日的推荐胜率表现及前后趋势对比"
        />
      )}
    </div>
  );
}
