import { useState, useEffect, useCallback } from 'react';
import {
  BriefcaseBusiness, TrendingUp, TrendingDown, ChevronDown, ChevronRight,
  Shield, AlertTriangle, Target, RefreshCw, BarChart3,
  Activity, ArrowRight, Minus, Lightbulb,
} from 'lucide-react';
import { Button } from '@/components/common/Button';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Loading } from '@/components/common/Loading';
import { EmptyState } from '@/components/common/EmptyState';
import { sealPlateApi } from '@/api/sealPlate';
import type { HoldingsResponse, PositionItem, StockRiskAnalysisResponse } from '@/types/sealPlate';

/** 单只持仓的复盘分析数据 */
interface PositionReviewData {
  position: PositionItem;
  riskAnalysis: StockRiskAnalysisResponse | null;
  riskLoading: boolean;
  expanded: boolean;
}

/** 生成操作建议 */
function getOperationAdvice(pos: PositionItem, risk: StockRiskAnalysisResponse | null): {
  action: 'hold' | 'add' | 'reduce' | 'stop_loss' | 'take_profit';
  label: string;
  reason: string;
  urgency: 'low' | 'medium' | 'high';
}[] {
  const costPrice = pos.costPrice || 0;
  const currentPrice = pos.currentPrice || 0;
  const pnlPct = costPrice > 0 ? ((currentPrice - costPrice) / costPrice) * 100 : 0;
  const advice: ReturnType<typeof getOperationAdvice> = [];

  // 止损建议
  if (pnlPct <= -15) {
    advice.push({
      action: 'stop_loss',
      label: '止损清仓',
      reason: `亏损已达${pnlPct.toFixed(1)}%，超过-15%止损线，建议果断止损，避免更大损失`,
      urgency: 'high',
    });
  } else if (pnlPct <= -8) {
    advice.push({
      action: 'reduce',
      label: '减仓观察',
      reason: `亏损${pnlPct.toFixed(1)}%，接近止损线，建议减仓一半控制风险，若继续下跌至-15%则清仓`,
      urgency: 'medium',
    });
  }

  // 止盈建议
  if (pnlPct >= 30) {
    advice.push({
      action: 'take_profit',
      label: '逐步止盈',
      reason: `盈利已达${pnlPct.toFixed(1)}%，建议分批止盈锁定利润，保留部分仓位博取更高收益`,
      urgency: 'medium',
    });
  } else if (pnlPct >= 15 && pnlPct < 30) {
    advice.push({
      action: 'hold',
      label: '持有观察',
      reason: `盈利${pnlPct.toFixed(1)}%，趋势良好，建议继续持有，关注量能变化，跌破成本价3%止损`,
      urgency: 'low',
    });
  }

  // 小幅波动
  if (pnlPct > -5 && pnlPct <= 5) {
    advice.push({
      action: 'hold',
      label: '耐心持有',
      reason: `盈亏${pnlPct.toFixed(1)}%，波动幅度较小，建议保持仓位不变，等待趋势明朗`,
      urgency: 'low',
    });
  }

  // 加仓建议
  if (pnlPct > 5 && pnlPct <= 15 && risk && risk.riskLevel === 'low') {
    advice.push({
      action: 'add',
      label: '可适量加仓',
      reason: `盈利${pnlPct.toFixed(1)}%，风险等级低，可考虑在回调至均线附近时适量加仓`,
      urgency: 'low',
    });
  }

  // 风险提示
  if (risk && risk.riskLevel === 'high') {
    advice.push({
      action: 'reduce',
      label: '风险过高,减仓',
      reason: '风险分析显示高风险等级，建议降低仓位控制风险敞口',
      urgency: 'high',
    });
  }

  return advice;
}

/** 持仓盈亏颜色 */
function getPnlColor(v: number) {
  return v > 0 ? 'text-red-500' : v < 0 ? 'text-green-500' : 'text-muted-foreground';
}

/** 格式化金额 */
function formatMoney(v: number) {
  const abs = Math.abs(v);
  const sign = v >= 0 ? '+' : '-';
  if (abs >= 10000) return `${sign}${(abs / 10000).toFixed(2)}万`;
  return `${sign}${abs.toFixed(2)}`;
}

/** 行动图标映射 */
function getActionIcon(action: string) {
  switch (action) {
    case 'stop_loss': return <AlertTriangle className="w-4 h-4 text-red-500" />;
    case 'take_profit': return <Target className="w-4 h-4 text-green-500" />;
    case 'add': return <TrendingUp className="w-4 h-4 text-green-500" />;
    case 'reduce': return <TrendingDown className="w-4 h-4 text-orange-500" />;
    default: return <Minus className="w-4 h-4 text-blue-500" />;
  }
}

/** 行动颜色 */
function getActionBadgeColor(urgency: string) {
  switch (urgency) {
    case 'high': return 'danger';
    case 'medium': return 'warning';
    default: return 'default';
  }
}

export default function PositionReviewPanel() {
  const [holdings, setHoldings] = useState<HoldingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [positionsData, setPositionsData] = useState<PositionReviewData[]>([]);
  const [showAll, setShowAll] = useState(false);

  /** 加载持仓数据 */
  const fetchHoldings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await sealPlateApi.getHoldings();
      setHoldings(data);
      setPositionsData(
        data.positions.map((p: PositionItem) => ({
          position: p,
          riskAnalysis: null,
          riskLoading: false,
          expanded: false,
        })),
      );
    } catch {
      // 降级使用本地数据
      const fallback: HoldingsResponse = {
        positions: [],
        totalPnl: 0,
        totalDailyPnl: 0,
        totalMarketValue: 0,
        totalCost: 0,
      };
      setHoldings(fallback);
      setPositionsData([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHoldings();
  }, [fetchHoldings]);

  /** 展开/收起个股复盘 */
  const toggleExpand = useCallback(async (idx: number) => {
    setPositionsData((prev) => {
      const next = [...prev];
      const item = next[idx];
      const newExpanded = !item.expanded;
      next[idx] = { ...item, expanded: newExpanded };

      // 首次展开时加载风险分析
      if (newExpanded && !item.riskAnalysis && !item.riskLoading) {
        next[idx] = { ...next[idx], riskLoading: true };
        // 异步加载风险分析
        sealPlateApi
          .getStockRiskAnalysis(item.position.code)
          .then((risk) => {
            setPositionsData((current) => {
              const updated = [...current];
              updated[idx] = { ...updated[idx], riskAnalysis: risk, riskLoading: false };
              return updated;
            });
          })
          .catch(() => {
            setPositionsData((current) => {
              const updated = [...current];
              updated[idx] = { ...updated[idx], riskAnalysis: null, riskLoading: false };
              return updated;
            });
          });
      }

      return next;
    });
  }, []);

  const positions = positionsData || [];

  // 统计
  const totalMarketValue = positions.reduce((s, d) => s + d.position.totalQty * d.position.currentPrice, 0);
  const totalPnl = holdings?.totalPnl || 0;
  const totalDailyPnl = holdings?.totalDailyPnl || 0;
  const winCount = positions.filter((d) => d.position.totalPnl > 0).length;
  const lossCount = positions.filter((d) => d.position.totalPnl < 0).length;

  // 按盈亏金额降序排列
  const sorted = [...positions].sort((a, b) => b.position.totalPnl - a.position.totalPnl);
  const displayed = showAll ? sorted : sorted.slice(0, 10);

  if (loading && !holdings) {
    return <Loading label="正在加载持仓复盘数据..." />;
  }

  if (!holdings || positions.length === 0) {
    return (
      <EmptyState
        icon={<BriefcaseBusiness className="w-12 h-12" />}
        title="暂无持仓数据"
        description="请先在持仓管理中添加交易记录，系统将自动生成复盘分析"
        action={
          <Button onClick={fetchHoldings} variant="outline">
            <RefreshCw className="w-4 h-4 mr-2" />
            刷新
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* 持仓概况卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card className="text-center p-4">
          <div className="text-xs text-muted-foreground mb-1">持仓总数</div>
          <div className="text-2xl font-bold">{positions.length}<span className="text-sm font-normal">只</span></div>
          <div className="text-xs text-muted-foreground mt-1">
            盈{winCount}/亏{lossCount}
          </div>
        </Card>
        <Card className="text-center p-4">
          <div className="text-xs text-muted-foreground mb-1">总市值</div>
          <div className="text-2xl font-bold">{totalMarketValue > 0 ? `${(totalMarketValue / 10000).toFixed(2)}` : '--'}<span className="text-sm font-normal">万</span></div>
        </Card>
        <Card className={`text-center p-4 ${totalPnl > 0 ? 'bg-red-500/5' : totalPnl < 0 ? 'bg-green-500/5' : ''}`}>
          <div className="text-xs text-muted-foreground mb-1">持仓盈亏</div>
          <div className={`text-2xl font-bold ${getPnlColor(totalPnl)}`}>
            {formatMoney(totalPnl)}
          </div>
        </Card>
        <Card className={`text-center p-4 ${totalDailyPnl > 0 ? 'bg-red-500/5' : totalDailyPnl < 0 ? 'bg-green-500/5' : ''}`}>
          <div className="text-xs text-muted-foreground mb-1">当日盈亏</div>
          <div className={`text-2xl font-bold ${getPnlColor(totalDailyPnl)}`}>
            {totalDailyPnl >= 0 ? '+' : ''}{totalDailyPnl.toFixed(2)}
          </div>
        </Card>
        <Card className="text-center p-4">
          <div className="text-xs text-muted-foreground mb-1">盈亏率</div>
          <div className="text-2xl font-bold">
            <span className={totalPnl >= 0 ? 'text-red-500' : 'text-green-500'}>
              {totalMarketValue > 0 ? `${(totalPnl / Math.abs(totalMarketValue) * 100).toFixed(2)}` : '--'}
            </span>
            <span className="text-sm font-normal">%</span>
          </div>
        </Card>
      </div>

      {/* 全局操作建议 */}
      <Card className="border-blue-500/30 bg-blue-500/5">
        <div className="flex items-center gap-2 text-blue-600 mb-3">
          <Lightbulb className="w-5 h-5" />
          <span className="font-medium">持仓策略总览</span>
        </div>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">盈利标的</span>
            <span className="text-red-500 font-medium">{winCount}只 ({positions.length > 0 ? (winCount / positions.length * 100).toFixed(0) : 0}%)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">亏损标的</span>
            <span className="text-green-500 font-medium">{lossCount}只 ({positions.length > 0 ? (lossCount / positions.length * 100).toFixed(0) : 0}%)</span>
          </div>
          <div className="pt-2 mt-2 border-t border-border text-muted-foreground leading-relaxed">
            {lossCount > winCount * 2 ? (
              '⚠️ <strong>警示：</strong>亏损标的大幅超过盈利标的，建议全面审查持仓，对亏损超15%的标的执行止损纪律，保住本金是第一原则。'
            ) : lossCount > winCount ? (
              '⚠️ <strong>关注：</strong>亏损标的略多于盈利标的，建议逐一检视亏损原因（追高/板块轮动/基本面变化），对有改善预期的持有，明确走弱的及时止损。'
            ) : winCount >= lossCount * 2 ? (
              '✅ <strong>良好：</strong>持仓表现优异，盈利标的占比高。建议保持当前策略，关注止盈纪律，不要让盈利变亏损。'
            ) : (
              '📊 <strong>中性：</strong>持仓结构相对均衡。展开下方各股详情，查看具体操作建议。'
            )}
          </div>
        </div>
      </Card>

      {/* 持仓明细列表 */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-blue-500" />
            个股持仓复盘
            <Badge variant="info" className="text-xs">{positions.length}只</Badge>
          </h2>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="ghost" onClick={fetchHoldings} disabled={loading}>
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        <div className="space-y-3">
          {displayed.map((data, _idx) => {
            const originalIdx = positions.indexOf(data);
            const p = data.position;
            const pnlPct = p.costPrice > 0 ? ((p.currentPrice - p.costPrice) / p.costPrice * 100) : 0;
            const dailyPnlPct = p.costPrice > 0 && p.totalQty > 0
              ? (p.dailyPnl / (p.totalQty * p.costPrice) * 100)
              : 0;
            const advice = getOperationAdvice(p, data.riskAnalysis);

            return (
              <div key={`${p.code}-${originalIdx}`}>
                {/* 摘要行 */}
                <button
                  className="w-full text-left"
                  onClick={() => toggleExpand(originalIdx)}
                >
                  <Card className={`hover:bg-accent/10 transition-colors cursor-pointer ${
                    pnlPct > 10 ? 'border-red-500/20 bg-red-500/[0.02]' :
                    pnlPct < -10 ? 'border-green-500/20 bg-green-500/[0.02]' :
                    ''
                  }`}>
                    <div className="flex items-center gap-3 p-4">
                      {/* 展开箭头 */}
                      <span className="text-muted-foreground flex-shrink-0">
                        {data.expanded
                          ? <ChevronDown className="w-4 h-4" />
                          : <ChevronRight className="w-4 h-4" />
                        }
                      </span>

                      {/* 基本信息 */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold truncate">{p.name || p.code}</span>
                          <span className="text-xs text-muted-foreground font-mono flex-shrink-0">{p.code}</span>
                          <Badge variant="default" className="text-xs flex-shrink-0">
                            {p.availableQty > 0
                              ? `${p.totalQty.toLocaleString()} / ${p.availableQty.toLocaleString()}`
                              : `${p.totalQty.toLocaleString()}`
                            }
                          </Badge>
                        </div>

                        <div className="grid grid-cols-4 gap-x-4 gap-y-0.5 mt-1.5 text-xs">
                          <div>
                            <span className="text-muted-foreground">现价: </span>
                            <span className="font-mono">{p.currentPrice?.toFixed(3) || '--'}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">成本: </span>
                            <span className="font-mono text-muted-foreground">{p.costPrice?.toFixed(3) || '--'}</span>
                          </div>
                          <div>
                            <span className={getPnlColor(p.totalPnl)}>
                              持仓盈亏: {formatMoney(p.totalPnl)}
                            </span>
                          </div>
                          <div>
                            <span className={getPnlColor(p.dailyPnl)}>
                              当日: {p.dailyPnl >= 0 ? '+' : ''}{p.dailyPnl.toFixed(2)}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* 盈亏百分比 */}
                      <div className="text-right flex-shrink-0">
                        <div className={`text-lg font-bold ${getPnlColor(pnlPct)}`}>
                          {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                        </div>
                        <div className={`text-xs ${getPnlColor(dailyPnlPct)}`}>
                          当日 {dailyPnlPct >= 0 ? '+' : ''}{dailyPnlPct.toFixed(2)}%
                        </div>
                      </div>
                    </div>
                  </Card>
                </button>

                {/* 展开详情 */}
                {data.expanded && (
                  <div className="ml-8 mt-2 space-y-4">
                    {/* 趋势分析 */}
                    <Card className="border-l-4 border-l-blue-500 bg-blue-500/5 p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <Activity className="w-4 h-4 text-blue-600" />
                        <span className="font-medium text-sm">走势分析与持仓诊断</span>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {/* 成本位置 */}
                        <div className="bg-muted/30 rounded-lg p-3 text-center">
                          <div className="text-xs text-muted-foreground mb-1">成本位</div>
                          <div className="text-sm font-mono">{p.costPrice?.toFixed(3) || '--'}</div>
                        </div>
                        <div className="bg-muted/30 rounded-lg p-3 text-center">
                          <div className="text-xs text-muted-foreground mb-1">现价</div>
                          <div className="text-sm font-mono">{p.currentPrice?.toFixed(3) || '--'}</div>
                        </div>
                        <div className="bg-muted/30 rounded-lg p-3 text-center">
                          <div className="text-xs text-muted-foreground mb-1">距成本</div>
                          <div className={`text-sm font-bold ${getPnlColor(pnlPct)}`}>
                            {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                          </div>
                        </div>
                        <div className="bg-muted/30 rounded-lg p-3 text-center">
                          <div className="text-xs text-muted-foreground mb-1">持仓市值</div>
                          <div className="text-sm font-medium">
                            {((p.totalQty * p.currentPrice) / 10000).toFixed(2)}万
                          </div>
                        </div>
                      </div>
                    </Card>

                    {/* 操作建议 */}
                    {advice.length > 0 && (
                      <Card className="border-l-4 border-l-green-500 bg-green-500/5 p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <Target className="w-4 h-4 text-green-600" />
                          <span className="font-medium text-sm">持仓操作建议</span>
                        </div>
                        <div className="space-y-2">
                          {advice.map((item, i) => (
                            <div key={i} className="flex items-start gap-3 p-3 bg-muted/30 rounded-lg">
                              <span className="mt-0.5 flex-shrink-0">
                                {getActionIcon(item.action)}
                              </span>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="font-medium text-sm">{item.label}</span>
                                  <Badge variant={getActionBadgeColor(item.urgency)} className="text-xs">
                                    {item.urgency === 'high' ? '紧急' : item.urgency === 'medium' ? '关注' : '参考'}
                                  </Badge>
                                </div>
                                <p className="text-xs text-muted-foreground mt-1">{item.reason}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </Card>
                    )}

                    {/* 风险分析 */}
                    <Card className="border-l-4 border-l-orange-500 bg-orange-500/5 p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <Shield className="w-4 h-4 text-orange-600" />
                        <span className="font-medium text-sm">风险分析</span>
                      </div>
                      {data.riskLoading ? (
                        <Loading label="加载风险分析中..." />
                      ) : data.riskAnalysis ? (
                        <div className="space-y-3">
                          {/* 风险等级 */}
                          <div className="flex items-center gap-3">
                            <span className="text-xs text-muted-foreground">综合风险</span>
                            <Badge variant={
                              data.riskAnalysis.riskLevel === 'high' ? 'danger' :
                              data.riskAnalysis.riskLevel === 'medium' ? 'warning' : 'success'
                            }>
                              {data.riskAnalysis.riskLevel === 'high' ? '🔴 高风险' :
                               data.riskAnalysis.riskLevel === 'medium' ? '🟡 中风险' : '🟢 低风险'}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              评分 {data.riskAnalysis.riskScore}/100
                            </span>
                          </div>

                          {/* 封板质量 */}
                          <div>
                            <span className="text-xs text-muted-foreground">封板质量：</span>
                            <span className={
                              data.riskAnalysis.sealQuality === '差' ? 'text-red-500' :
                              data.riskAnalysis.sealQuality === '一般' ? 'text-yellow-500' : 'text-green-500'
                            }>{data.riskAnalysis.sealQuality || '--'}</span>
                          </div>

                          {/* 换手率警告 */}
                          {data.riskAnalysis.turnoverWarning && (
                            <p className="text-xs text-red-500">⚠️ {data.riskAnalysis.turnoverWarning}</p>
                          )}

                          {/* 游资风险 */}
                          {data.riskAnalysis.hotMoneyRisk?.length > 0 && (
                            <div className="p-2 bg-yellow-500/10 rounded border border-yellow-500/20">
                              <p className="text-xs font-medium text-yellow-600 mb-1">⚡ 游资风险</p>
                              {data.riskAnalysis.hotMoneyRisk.map((r, i) => (
                                <p key={i} className="text-xs text-yellow-600">• {r}</p>
                              ))}
                            </div>
                          )}

                          {/* 一日游风险 */}
                          {data.riskAnalysis.oneDayTourRisk?.length > 0 && (
                            <div className="p-2 bg-orange-500/10 rounded border border-orange-500/20">
                              <p className="text-xs font-medium text-orange-600 mb-1">🔴 一日游风险</p>
                              {data.riskAnalysis.oneDayTourRisk.map((r, i) => (
                                <p key={i} className="text-xs text-orange-600">• {r}</p>
                              ))}
                            </div>
                          )}

                          {/* 建议 */}
                          {data.riskAnalysis.suggestions?.length > 0 && (
                            <div className="p-2 bg-blue-500/10 rounded border border-blue-500/20">
                              <p className="text-xs font-medium text-blue-600 mb-1">📋 操作建议</p>
                              {data.riskAnalysis.suggestions.map((s, i) => (
                                <p key={i} className="text-xs text-blue-600">• {s}</p>
                              ))}
                            </div>
                          )}
                        </div>
                      ) : (
                        <p className="text-xs text-muted-foreground">
                          暂无可用的风险分析数据，请点击刷新按钮获取最新数据
                        </p>
                      )}
                    </Card>
                  </div>
                )}
              </div>
            );
          })}

          {/* 显示更多 */}
          {positions.length > 10 && !showAll && (
            <div className="text-center py-4">
              <Button variant="outline" onClick={() => setShowAll(true)}>
                显示全部 {positions.length} 只标的
                <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          )}
          {showAll && positions.length > 10 && (
            <div className="text-center py-4">
              <Button variant="ghost" onClick={() => setShowAll(false)}>
                收起，仅显示前10只
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* 更新时间 */}
      {holdings?.updatedAt && (
        <div className="text-center text-xs text-muted-foreground">
          数据更新时间: {new Date(holdings.updatedAt).toLocaleString('zh-CN')}
        </div>
      )}
    </div>
  );
}
