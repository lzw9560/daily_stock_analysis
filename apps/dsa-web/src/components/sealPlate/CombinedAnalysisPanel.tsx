import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Zap, Target, Swords, TrendingUp, AlertTriangle,
  Star, Crown, RefreshCw, ChevronDown, ChevronRight,
  Lightbulb, Info, ArrowRight, Calendar,
} from 'lucide-react';
import { Button } from '@/components/common/Button';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Loading } from '@/components/common/Loading';
import { EmptyState } from '@/components/common/EmptyState';
import { sealPlateApi } from '@/api/sealPlate';
import type {
  PositionRecResponse, WinRateResponse, StrategyItem, MultiMatchAnalysis,
} from '@/types/sealPlate';

/** 综合推荐结果 */
interface CombinedResult {
  strategies: StrategyItem[];
  multiMatch: MultiMatchAnalysis[];
  winRate: WinRateResponse | null;
  recommendations: PositionRecResponse[];
  generatedAt: string;
}

export default function CombinedAnalysisPanel() {
  const [data, setData] = useState<CombinedResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedStrategy, setExpandedStrategy] = useState<string | null>(null);
  const [expandedMulti, setExpandedMulti] = useState<string | null>(null);

  const fetchCombined = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [strategiesRes, multiRes, winRateRes, recRes] = await Promise.all([
        sealPlateApi.getStrategies(),
        sealPlateApi.getMultiMatchRecommendations(),
        sealPlateApi.getWinRate(),
        sealPlateApi.getRecommendations(),
      ]);

      setData({
        strategies: strategiesRes.strategies,
        multiMatch: multiRes.recommendations,
        winRate: winRateRes,
        recommendations: recRes.recommendations,
        generatedAt: new Date().toISOString(),
      });
    } catch (err: any) {
      setError(err?.message || '获取综合分析数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCombined();
  }, [fetchCombined]);

  /** 多战法共振 + 推荐建仓的综合评分 */
  const combinedRankings = useMemo(() => {
    if (!data) return [];

    const { multiMatch, recommendations } = data;
    const recMap = new Map(recommendations.map(r => [r.code, r]));

    const items = multiMatch.map(mm => {
      const rec = recMap.get(mm.code);
      // 综合评分：战法匹配度 40% + 推荐评分 60%
      const compositeScore = rec
        ? Math.round(mm.avgMatchScore * 0.4 + rec.score * 0.6)
        : Math.round(mm.avgMatchScore);

      return {
        ...mm,
        recommendation: rec || null,
        compositeScore,
      };
    });

    // 将只有推荐但没有多战法匹配的也加入
    recommendations.forEach(rec => {
      if (!multiMatch.some(mm => mm.code === rec.code)) {
        items.push({
          code: rec.code,
          name: rec.name,
          sector: rec.sector,
          matchedStrategies: [],
          matchCount: 0,
          avgMatchScore: 0,
          reasons: rec.reasons,
          entryPoints: [],
          buyAnalysis: rec.reasons.join('；'),
          sellAnalysis: '',
          riskLevel: 'medium' as const,
          compositeScore: rec.score,
          recommendation: rec,
        });
      }
    });

    return items.sort((a, b) => b.compositeScore - a.compositeScore);
  }, [data]);

  /** 获取时间描述 */
  const getTimeDesc = (isoString: string) => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);

    if (diffMin < 1) return '刚刚更新';
    if (diffMin < 60) return `${diffMin}分钟前更新`;
    const diffHour = Math.floor(diffMin / 60);
    if (diffHour < 24) return `${diffHour}小时前更新`;
    return date.toLocaleString('zh-CN');
  };

  const getRiskBadge = (level: string) => {
    switch (level) {
      case 'low': return <Badge variant="success">低风险</Badge>;
      case 'medium': return <Badge variant="warning">中风险</Badge>;
      case 'high': return <Badge variant="danger">高风险</Badge>;
      default: return <Badge>未知</Badge>;
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 85) return 'text-green-500';
    if (score >= 75) return 'text-emerald-500';
    if (score >= 65) return 'text-yellow-500';
    return 'text-gray-500';
  };

  if (loading) return <Loading label="正在加载综合分析数据..." />;
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-4">
        <AlertTriangle className="w-12 h-12 text-red-500" />
        <p className="text-red-500">{error}</p>
        <Button onClick={fetchCombined}>重试</Button>
      </div>
    );
  }

  if (!data) {
    return <EmptyState title="暂无分析数据" description="请先执行早盘推荐任务" />;
  }

  const highMatch = combinedRankings.filter(c => c.matchCount >= 2);
  const singleMatch = combinedRankings.filter(c => c.matchCount === 1);
  const noMatch = combinedRankings.filter(c => c.matchCount === 0);

  return (
    <div className="space-y-6 py-4">
      {/* 标题栏 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Zap className="w-5 h-5 text-yellow-500" />
            综合推荐分析
            <Badge variant="info" className="text-xs">战法+建仓</Badge>
          </h2>
          <p className="text-sm text-muted-foreground flex items-center gap-1 mt-1">
            <Calendar className="w-3.5 h-3.5" />
            数据{getTimeDesc(data.generatedAt)}
          </p>
        </div>
        <Button size="sm" variant="ghost" onClick={fetchCombined}>
          <RefreshCw className="w-4 h-4 mr-1" />
          刷新
        </Button>
      </div>

      {/* 胜率概览 */}
      {data.winRate && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card className="p-3 text-center">
            <p className="text-xs text-muted-foreground">总胜率</p>
            <p className="text-xl font-bold text-green-500">
              {(data.winRate.winRate * 100).toFixed(1)}%
            </p>
          </Card>
          <Card className="p-3 text-center">
            <p className="text-xs text-muted-foreground">近10笔胜率</p>
            <p className="text-xl font-bold text-blue-500">
              {(data.winRate.rollingWinRate10 * 100).toFixed(1)}%
            </p>
          </Card>
          <Card className="p-3 text-center">
            <p className="text-xs text-muted-foreground">平均收益</p>
            <p className={`text-xl font-bold ${data.winRate.avgReturn >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {data.winRate.avgReturn >= 0 ? '+' : ''}{data.winRate.avgReturn.toFixed(2)}%
            </p>
          </Card>
          <Card className="p-3 text-center">
            <p className="text-xs text-muted-foreground">趋势</p>
            <p className="text-xl font-bold text-yellow-500">
              {data.winRate.trend === 'improving' ? '📈 上升' : data.winRate.trend === 'declining' ? '📉 下降' : '➡️ 稳定'}
            </p>
          </Card>
        </div>
      )}

      {/* 策略调整建议 */}
      {data.winRate?.strategyAdjustments && data.winRate.strategyAdjustments.length > 0 && (
        <Card className="p-4 bg-yellow-50/50 dark:bg-yellow-950/20 border-yellow-200">
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-2">
            <Lightbulb className="w-4 h-4 text-yellow-500" />
            策略调整建议
          </h3>
          <ul className="space-y-1">
            {data.winRate.strategyAdjustments.map((adj, i) => (
              <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                <ArrowRight className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-yellow-500" />
                {adj}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* 高胜率板块 */}
      {data.winRate?.bySector && data.winRate.bySector.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
            <Crown className="w-4 h-4 text-yellow-500" />
            板块胜率排行
          </h3>
          <div className="flex flex-wrap gap-2">
            {data.winRate.bySector
              .sort((a, b) => b.rate - a.rate)
              .slice(0, 8)
              .map(s => (
                <Badge
                  key={s.sector}
                  variant={s.rate >= 0.6 ? 'success' : s.rate >= 0.4 ? 'warning' : 'danger'}
                >
                  {s.sector}: {(s.rate * 100).toFixed(0)}% ({s.won}/{s.total})
                </Badge>
              ))}
          </div>
        </div>
      )}

      {/* 多战法共振标的（重点推荐） */}
      {highMatch.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-3">
            <Target className="w-5 h-5 text-red-500" />
            多战法共振标的
            <Badge variant="danger" className="text-xs">重点推荐</Badge>
          </h3>
          <div className="space-y-3">
            {highMatch.map(item => (
              <CombinedCard
                key={item.code}
                item={item}
                expanded={expandedMulti === item.code}
                onToggle={() => setExpandedMulti(expandedMulti === item.code ? null : item.code)}
                getScoreColor={getScoreColor}
                getRiskBadge={getRiskBadge}
              />
            ))}
          </div>
        </div>
      )}

      {/* 单战法匹配 */}
      {singleMatch.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-3">
            <Swords className="w-5 h-5 text-blue-500" />
            单战法匹配标的
          </h3>
          <div className="space-y-3">
            {singleMatch.map(item => (
              <CombinedCard
                key={item.code}
                item={item}
                expanded={expandedMulti === item.code}
                onToggle={() => setExpandedMulti(expandedMulti === item.code ? null : item.code)}
                getScoreColor={getScoreColor}
                getRiskBadge={getRiskBadge}
              />
            ))}
          </div>
        </div>
      )}

      {/* 推荐建仓（无战法匹配） */}
      {noMatch.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-3">
            <TrendingUp className="w-5 h-5 text-purple-500" />
            推荐建仓（评分入选）
          </h3>
          <div className="space-y-3">
            {noMatch.map(item => (
              <CombinedCard
                key={item.code}
                item={item}
                expanded={expandedMulti === item.code}
                onToggle={() => setExpandedMulti(expandedMulti === item.code ? null : item.code)}
                getScoreColor={getScoreColor}
                getRiskBadge={getRiskBadge}
              />
            ))}
          </div>
        </div>
      )}

      {combinedRankings.length === 0 && (
        <EmptyState title="暂无推荐标的" description="当前无符合条件的综合推荐" />
      )}

      {/* 高胜率战法总览 */}
      {data.strategies.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-3">
            <Swords className="w-5 h-5 text-orange-500" />
            已激活战法 ({data.strategies.length})
          </h3>
          <div className="space-y-2">
            {data.strategies
              .sort((a, b) => b.currentSuitability - a.currentSuitability)
              .map(strategy => (
                <Card key={strategy.id} className="p-3">
                  <div
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => setExpandedStrategy(expandedStrategy === strategy.id ? null : strategy.id)}
                  >
                    <div className="flex items-center gap-3">
                      <span className={`text-lg font-semibold ${strategy.currentSuitability >= 70 ? 'text-green-500' : strategy.currentSuitability >= 50 ? 'text-yellow-500' : 'text-red-500'}`}>
                        {strategy.name}
                      </span>
                      <Badge variant="info" className="text-xs">{strategy.type}</Badge>
                      <span className="text-sm text-muted-foreground">
                        胜率 {(strategy.winRate * 100).toFixed(0)}%
                      </span>
                      <Badge variant={strategy.currentSuitability >= 70 ? 'success' : strategy.currentSuitability >= 50 ? 'warning' : 'danger'}>
                        适配度 {strategy.currentSuitability}%
                      </Badge>
                    </div>
                    {expandedStrategy === strategy.id ? (
                      <ChevronDown className="w-4 h-4" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    )}
                  </div>
                  {expandedStrategy === strategy.id && (
                    <div className="mt-3 pt-3 border-t border-border/30 space-y-2">
                      <p className="text-sm text-muted-foreground">{strategy.description}</p>
                      <div className="text-sm">
                        <span className="text-muted-foreground">适配原因：</span>
                        {strategy.currentReason}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <span className="text-xs text-muted-foreground">适用市场：</span>
                        {strategy.suitableMarket.map((m, i) => (
                          <Badge key={i} variant="success" className="text-xs">{m}</Badge>
                        ))}
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">选股条件：</p>
                        <ul className="space-y-0.5">
                          {strategy.conditions.map((c, i) => (
                            <li key={i} className="text-xs flex items-start gap-1">
                              <Info className="w-3 h-3 mt-0.5 flex-shrink-0 text-blue-500" />
                              {c}
                            </li>
                          ))}
                        </ul>
                      </div>
                      {strategy.entryModes.length > 0 && (
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">介入模式：</p>
                          {strategy.entryModes.map((em, i) => (
                            <div key={i} className="flex items-center gap-2 text-xs ml-2">
                              <span>{em.name}</span>
                              <Badge variant="info" className="text-xs">胜率 {(em.winRate * 100).toFixed(0)}%</Badge>
                              <span className="text-muted-foreground">{em.desc}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">风控铁律：</p>
                        {strategy.riskControl.map((rc, i) => (
                          <Badge key={i} variant="warning" className="text-xs mr-1 mb-1">{rc}</Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** 单个综合推荐卡片 */
function CombinedCard({
  item,
  expanded,
  onToggle,
  getScoreColor,
  getRiskBadge,
}: {
  item: any;
  expanded: boolean;
  onToggle: () => void;
  getScoreColor: (score: number) => string;
  getRiskBadge: (level: string) => React.ReactNode;
}) {
  return (
    <Card className="p-4 hover:bg-card/60 transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1">
            <span className="font-semibold text-base">{item.name}</span>
            <span className="text-sm text-muted-foreground font-mono">{item.code}</span>
            {item.matchCount >= 2 && <Crown className="w-4 h-4 text-yellow-500" />}
            {item.sector && (
              <Badge variant="info" className="text-xs">{item.sector}</Badge>
            )}
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <Star className="w-3.5 h-3.5" />
              综合评分：
              <span className={`font-bold ${getScoreColor(item.compositeScore)}`}>
                {item.compositeScore}
              </span>
            </span>
            {item.matchCount > 0 && (
              <span className="flex items-center gap-1">
                <Swords className="w-3.5 h-3.5" />
                匹配{item.matchCount}个战法
              </span>
            )}
            {getRiskBadge(item.riskLevel)}
          </div>
          {item.matchedStrategies.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {item.matchedStrategies.map((s: string, i: number) => (
                <Badge key={i} variant="success" className="text-xs">{s}</Badge>
              ))}
            </div>
          )}
        </div>
        <button onClick={onToggle} className="p-1 hover:bg-card rounded">
          {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-border/30 space-y-3">
          {/* 推荐理由 */}
          {item.reasons.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1">战法匹配理由：</p>
              <ul className="space-y-0.5">
                {item.reasons.map((r: string, i: number) => (
                  <li key={i} className="text-sm flex items-start gap-1">
                    <ArrowRight className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-blue-500" />
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 建仓分析 */}
          {item.buyAnalysis && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1">建仓分析：</p>
              <p className="text-sm bg-green-50/50 dark:bg-green-950/20 p-2 rounded border border-green-200">
                {item.buyAnalysis}
              </p>
            </div>
          )}

          {/* 卖出分析 */}
          {item.sellAnalysis && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1">卖出分析：</p>
              <p className="text-sm bg-red-50/50 dark:bg-red-950/20 p-2 rounded border border-red-200">
                {item.sellAnalysis}
              </p>
            </div>
          )}

          {/* 建仓点位（来自多战法） */}
          {item.entryPoints && item.entryPoints.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1">建仓点位：</p>
              <div className="space-y-1">
                {item.entryPoints.map((ep: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 text-sm bg-card/50 p-1.5 rounded">
                    <Badge variant={ep.type === 'ideal' ? 'success' : 'warning'} className="text-xs">
                      {ep.price.toFixed(2)}
                    </Badge>
                    <span className="text-muted-foreground">{ep.condition}</span>
                    <Badge variant="info" className="text-xs">仓位 {ep.positionPct}%</Badge>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 推荐详情（如果有） */}
          {item.recommendation && (
            <div className="bg-blue-50/50 dark:bg-blue-950/20 p-3 rounded border border-blue-200">
              <p className="text-xs font-semibold mb-1">推荐详情：</p>
              <div className="text-sm space-y-0.5">
                <p>置信度：{item.recommendation.confidence}</p>
                <p>建议仓位：{item.recommendation.suggestedPositionPct}%</p>
                {item.recommendation.riskWarnings.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {item.recommendation.riskWarnings.map((w: string, i: number) => (
                      <Badge key={i} variant="warning" className="text-xs">{w}</Badge>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
