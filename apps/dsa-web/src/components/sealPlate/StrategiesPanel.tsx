import { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp, Target, Shield, Zap, AlertTriangle,
  BarChart3, Layers, RefreshCw, CheckCircle, ArrowUp,
  Star, Crosshair, TrendingDown, Lightbulb
} from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Loading } from '@/components/common/Loading';
import { sealPlateApi } from '@/api/sealPlate';
import { StockNameDisplay } from '@/components/common/StockNameDisplay';
import type { StrategyResponse, StrategyItem, StrategyCandidate, MultiMatchResponse, MultiMatchAnalysis } from '@/types/sealPlate';

// ---- 内建战法库（前端常量，后端补充动态适配） ----
const BUILTIN_STRATEGIES: StrategyItem[] = [
  {
    id: 'second_board',
    name: '二板定龙战法',
    type: '连板接力',
    description: '一板看气质，二板定龙头，三板成妖。首板是试探，二板是确认——通过系统化竞价分析、量能验证、题材筛选，在龙头启动临界点精准介入。',
    winRate: 70,
    suitableMarket: ['震荡期', '启动期', '发酵期'],
    unsuitableMarket: ['退潮期', '冰点期后期'],
    conditions: [
      '首板必须放量（换手5%-8%为佳），缩量首板次日不利于接力',
      '竞价高开3%-9%，成交量放大到首板爆量的2/3以上',
      '优先10:30前封板，早盘是资金最活跃阶段',
      '板块内至少3只个股同步高开5%以上，有板块助攻',
      '左侧筹码密集区少，避免大量套牢盘抛压',
      '高换手非一字板优先，龙头从分歧中接力走出来更稳',
    ],
    entryModes: [
      { name: '弱转强模式', desc: '首板烂板→次日低开迅速翻红，分时白线穿过黄线介入', winRate: 80 },
      { name: 'T字板回封', desc: '竞价被顶上去，盘中短暂开板后回封瞬间打板', winRate: 75 },
      { name: '高开秒板', desc: '高开7%-9%，竞价量能达标，竞价阶段介入', winRate: 72 },
      { name: '盘中承接洗盘', desc: '白线>黄线，8%以上横盘，分时低吸+涨停加仓', winRate: 68 },
    ],
    riskControl: [
      '二板炸板不回封：当天止损或次日竞价止损',
      '次日低开低走跌破首板涨停价坚决离场',
      '单票仓位≤20%，分仓参与多个候选',
      '避开缩量一字板（后续抛压大）和一致到一致（容易炸板）',
    ],
    currentSuitability: 85,
    currentReason: '市场情绪处于发酵期，连板效应明显，二板确定性高',
  },
  {
    id: 'weak_to_strong',
    name: '弱转强反包战法',
    type: '分歧转一致',
    description: '捕捉首板分歧后转一致的二次介入机会。首板烂板反复炸板说明存在分歧，次日若能快速走强则代表"分歧转一致"——这是资金共识最强的信号。',
    winRate: 75,
    suitableMarket: ['震荡期', '启动期', '发酵期'],
    unsuitableMarket: ['高潮期中后期'],
    conditions: [
      '首板封板犹豫、反复开板、尾盘勉强封住',
      '首板换手5%-8%，非一字板',
      '次日竞价低开或平开后迅速翻红',
      '分时白线穿过黄线或拉过0轴时介入',
      '板块热度持续，有涨停助攻',
    ],
    entryModes: [
      { name: '竞价低吸', desc: '竞价低开-3%以上，开盘后15分钟内翻红', winRate: 78 },
      { name: '盘中追涨', desc: '盘中放量突破前高，打板确认', winRate: 65 },
    ],
    riskControl: [
      '低开超过5%不参与',
      '翻红后再度翻绿立即止损',
      '次日不封板或走弱及时止盈',
    ],
    currentSuitability: 78,
    currentReason: '分歧板数量增多，弱转强机会丰富',
  },
  {
    id: 'sector_lead',
    name: '板块龙头接力战法',
    type: '龙头战法',
    description: '紧跟热门板块龙头股，在板块效应形成时介入。龙头的特征是板块内最先涨停、封单最强、题材逻辑最硬。不对非龙头股抱有幻想。',
    winRate: 65,
    suitableMarket: ['启动期', '发酵期', '高潮期前期'],
    unsuitableMarket: ['退潮期'],
    conditions: [
      '板块内有3只以上涨停股，形成明显板块效应',
      '标的为板块内最先涨停的前2只股票',
      '封板时间在10:00前，封单金额>1亿',
      '题材有持续发酵潜力（政策驱动/事件催化）',
      '流通市值30亿-150亿，适合短线资金进出',
    ],
    entryModes: [
      { name: '追板介入', desc: '板块确认后，龙头股打板介入', winRate: 62 },
      { name: '次龙补涨', desc: '龙头封死后，参与板块第二龙头', winRate: 68 },
    ],
    riskControl: [
      '龙头炸板立即清仓全板块',
      '板块涨停数降至1只以下快速减仓',
      '不可追入板块第三梯队',
    ],
    currentSuitability: 72,
    currentReason: '热门板块轮动较快，龙头切换频繁，需精准择时',
  },
  {
    id: 'capital_track',
    name: '大基金追踪战法',
    type: '资金跟随',
    description: '重点关注大基金（国家大基金、社保、养老金、证金汇金）持续流入方向，跟随主力资金布局。机构资金具有持续性，不易出现一日游行情。',
    winRate: 60,
    suitableMarket: ['震荡期', '启动期'],
    unsuitableMarket: ['退潮期'],
    conditions: [
      '板块连续3日资金净流入',
      '龙虎榜有机构席位净买入',
      '标的流通市值>100亿，流动性好',
      '避开游资主导的小盘标的',
      '优先选择政策支持方向（半导体/新能源/军工等）',
    ],
    entryModes: [
      { name: '回踩低吸', desc: '板块回踩5日线不破时分批介入', winRate: 65 },
      { name: '突破追涨', desc: '板块突破前高时跟进', winRate: 55 },
    ],
    riskControl: [
      '机构开始出货（龙虎榜卖出席位）立即退出',
      '资金连续2日净流出减半仓',
      '基本面恶化无条件离场',
    ],
    currentSuitability: 68,
    currentReason: '机构调仓期，需关注大基金重点布局方向',
  },
  {
    id: 'first_board_break',
    name: '首板突破战法',
    type: '低位首板',
    description: '捕捉低位首板突破的个股，适合低风险偏好的投资者。低位首板往往有基本面支撑，后续空间较大，回撤风险可控。',
    winRate: 58,
    suitableMarket: ['冰点期', '启动期初期'],
    unsuitableMarket: ['高潮期'],
    conditions: [
      '股价处于历史低位区间（距52周高点跌幅>30%）',
      '突破60日/120日均线压制',
      '涨停成交量放大2倍以上',
      '有业绩预增或利好公告支撑',
      '流通市值50亿-200亿',
    ],
    entryModes: [
      { name: '次日低吸', desc: '首板次日回调1%-3%低吸', winRate: 60 },
      { name: '突破回踩', desc: '回踩涨停价不破介入', winRate: 55 },
    ],
    riskControl: [
      '跌破首板涨停价止损',
      '3日内不创新高减仓',
      '成交量迅速萎缩减仓',
    ],
    currentSuitability: 55,
    currentReason: '市场偏活跃，低位首板机会相对有限',
  },
];

export default function StrategiesPanel() {
  const [strategies, setStrategies] = useState<StrategyResponse | null>(null);
  const [multiMatch, setMultiMatch] = useState<MultiMatchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedStrategy, setExpandedStrategy] = useState<string | null>('second_board');
  const [candidateLoading, setCandidateLoading] = useState(false);
  const [candidates, setCandidates] = useState<Record<string, StrategyCandidate[]>>({});

  const fetchStrategies = useCallback(async () => {
    setLoading(true);
    try {
      const data = await sealPlateApi.getStrategies();
      setStrategies(data);
    } catch {
      setStrategies({
        strategies: BUILTIN_STRATEGIES,
        marketPhase: '发酵期',
        marketHeat: 62,
        updatedAt: new Date().toISOString(),
      });
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchMultiMatch = useCallback(async () => {
    try {
      const data = await sealPlateApi.getMultiMatchRecommendations();
      setMultiMatch(data);
    } catch {
      setMultiMatch(null);
    }
  }, []);

  useEffect(() => {
    fetchStrategies();
    fetchMultiMatch();
  }, [fetchStrategies, fetchMultiMatch]);

  const fetchCandidates = async (strategyId: string) => {
    if (candidates[strategyId]) return;
    setCandidateLoading(true);
    try {
      const data = await sealPlateApi.getStrategyCandidates(strategyId);
      setCandidates(prev => ({ ...prev, [strategyId]: data.candidates }));
    } catch {
      setCandidates(prev => ({ ...prev, [strategyId]: [] }));
    } finally {
      setCandidateLoading(false);
    }
  };

  const handleExpand = (id: string) => {
    if (expandedStrategy === id) {
      setExpandedStrategy(null);
    } else {
      setExpandedStrategy(id);
      fetchCandidates(id);
    }
  };

  if (loading && !strategies) {
    return (
      <Card>
        <div className="flex items-center justify-center h-48">
          <Loading label="加载策略分析..." />
        </div>
      </Card>
    );
  }

  const allStrategies = strategies?.strategies || BUILTIN_STRATEGIES;
  const marketPhase = strategies?.marketPhase || '发酵期';
  const marketHeat = strategies?.marketHeat || 60;

  const getSuitColor = (s: number) => (s >= 75 ? 'text-green-500' : s >= 60 ? 'text-yellow-500' : 'text-gray-400');
  const getSuitBadge = (s: number): 'success' | 'warning' | 'default' => (s >= 75 ? 'success' : s >= 60 ? 'warning' : 'default');

  return (
    <div className="space-y-6">
      {/* 市场环境总览 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border-blue-500/30 bg-blue-500/5">
          <div className="flex items-center gap-2 text-blue-600 mb-2">
            <BarChart3 className="w-5 h-5" />
            <span className="font-medium">当前市场阶段</span>
          </div>
          <div className="text-2xl font-bold text-blue-600">{marketPhase}</div>
          <p className="text-xs text-muted-foreground mt-1">
            {marketPhase === '退潮期' || marketPhase === '冰点期' ? '⚠️ 控制仓位，低战法适配度' : '✅ 部分战法当前适用'}
          </p>
        </Card>
        <Card className="border-orange-500/30 bg-orange-500/5">
          <div className="flex items-center gap-2 text-orange-600 mb-2">
            <Zap className="w-5 h-5" />
            <span className="font-medium">市场热度</span>
          </div>
          <div className="text-2xl font-bold text-orange-600">{marketHeat}/100</div>
          <p className="text-xs text-muted-foreground mt-1">
            {marketHeat >= 70 ? '热门，注意高位风险' : marketHeat >= 50 ? '中等热度，机会适中' : '偏冷，观望为主'}
          </p>
        </Card>
        <Card className="border-green-500/30 bg-green-500/5">
          <div className="flex items-center gap-2 text-green-600 mb-2">
            <Target className="w-5 h-5" />
            <span className="font-medium">推荐战法</span>
          </div>
          <div className="text-lg font-bold text-green-600">
            {allStrategies.sort((a, b) => b.currentSuitability - a.currentSuitability)[0]?.name || '--'}
          </div>
          <p className="text-xs text-muted-foreground mt-1">当前市场环境下胜率最高的战法</p>
        </Card>
      </div>

      {/* 重点推荐 - 多战法共振标的 */}
      {multiMatch && multiMatch.recommendations.length > 0 && (
        <div className="bg-gradient-to-r from-red-500/5 via-amber-500/5 to-red-500/5 border-2 border-red-500/30 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 bg-red-500/20 rounded-lg flex items-center justify-center">
              <Star className="w-5 h-5 text-red-500" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-red-500">重点推荐 · 多战法共振</h2>
              <p className="text-xs text-muted-foreground">
                多战法同时验证的标的，风险敞口更低，确定性更高（共{multiMatch.recommendations.length}只）
              </p>
            </div>
          </div>

          <div className="space-y-4">
            {multiMatch.recommendations.map((item) => (
              <MultiMatchCard key={item.code} item={item} />
            ))}
          </div>
        </div>
      )}

      {/* 战法列表 */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Layers className="w-5 h-5 text-red-500" />
            高胜率战法展示
          </h2>
          <Button size="sm" variant="ghost" onClick={fetchStrategies} disabled={loading}>
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>

        <div className="space-y-4">
          {allStrategies
            .sort((a, b) => b.currentSuitability - a.currentSuitability)
            .map((strategy) => {
              const isExpanded = expandedStrategy === strategy.id;
              const strategyCandidates = candidates[strategy.id] || [];

              return (
                <Card
                  key={strategy.id}
                  className={`transition-all ${isExpanded ? 'ring-2 ring-red-500/30' : ''}`}
                >
                  {/* 头部 */}
                  <div
                    className="cursor-pointer"
                    onClick={() => handleExpand(strategy.id)}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <Target className="w-5 h-5 text-red-500" />
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-lg">{strategy.name}</span>
                            <Badge variant="info">{strategy.type}</Badge>
                          </div>
                          <p className="text-sm text-muted-foreground mt-0.5">{strategy.description}</p>
                        </div>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <div className="flex items-center gap-2">
                          <span className={`text-xl font-bold ${getSuitColor(strategy.currentSuitability)}`}>
                            {strategy.currentSuitability}%
                          </span>
                          <Badge variant={getSuitBadge(strategy.currentSuitability)}>
                            适配度
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">历史胜率 {strategy.winRate}%</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <CheckCircle className="w-3 h-3 text-green-500" />
                      <span>{strategy.currentReason}</span>
                    </div>
                  </div>

                  {/* 展开内容 */}
                  {isExpanded && (
                    <div className="mt-4 pt-4 border-t border-border space-y-4">
                      {/* 筛选条件 */}
                      <div>
                        <p className="text-sm font-medium mb-2 flex items-center gap-2">
                          <Shield className="w-4 h-4 text-blue-500" />
                          选股条件
                        </p>
                        <ul className="space-y-1">
                          {strategy.conditions.map((c, i) => (
                            <li key={i} className="text-sm flex items-start gap-2">
                              <span className="text-blue-500 mt-1">{i + 1}.</span>
                              <span>{c}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* 介入模式 */}
                      <div>
                        <p className="text-sm font-medium mb-2 flex items-center gap-2">
                          <TrendingUp className="w-4 h-4 text-green-500" />
                          介入模式
                        </p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                          {strategy.entryModes.map((mode, i) => (
                            <div key={i} className="bg-green-500/5 rounded-lg p-3 border border-green-500/20">
                              <div className="flex items-center justify-between mb-1">
                                <span className="font-medium text-sm">{mode.name}</span>
                                <Badge variant="success" className="text-xs">胜率{mode.winRate}%</Badge>
                              </div>
                              <p className="text-xs text-muted-foreground">{mode.desc}</p>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* 风控规则 */}
                      <div>
                        <p className="text-sm font-medium mb-2 flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-orange-500" />
                          风控铁律
                        </p>
                        <ul className="space-y-1">
                          {strategy.riskControl.map((r, i) => (
                            <li key={i} className="text-sm flex items-start gap-2 text-orange-600">
                              <span className="text-orange-500 mt-1">⚠</span>
                              <span>{r}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* 适应当前战法的候选标的 */}
                      <div>
                        <p className="text-sm font-medium mb-2 flex items-center gap-2">
                          <ArrowUp className="w-4 h-4 text-red-500" />
                          当前符合条件的标的
                        </p>
                        {candidateLoading && !strategyCandidates.length ? (
                          <Loading label="筛选标的中..." />
                        ) : strategyCandidates.length > 0 ? (
                          <div className="space-y-2">
                            {strategyCandidates.map((c) => (
                              <div key={c.code} className="bg-background/60 rounded-lg p-3 border border-border/50 hover:border-red-500/30 transition-colors">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-3">
                                    <span className="font-medium">{c.name}</span>
                                    <span className="text-xs text-muted-foreground">{c.code}</span>
                                    <Badge variant="info">{c.sector}</Badge>
                                    {c.changePct !== undefined && (
                                      <span className={c.changePct > 0 ? 'text-red-500 text-xs' : 'text-green-500 text-xs'}>
                                        {c.changePct > 0 ? '+' : ''}{c.changePct}%
                                      </span>
                                    )}
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs text-muted-foreground">{c.matchReason}</span>
                                    <Badge variant="success" className="text-xs">匹配度{c.matchScore}%</Badge>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-muted-foreground py-3 text-center">
                            暂无符合条件的标的，请等待市场环境变化
                          </p>
                        )}
                      </div>

                      {/* 适用/不适用市场环境 */}
                      <div className="flex items-center gap-4 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-1 bg-green-500/10 text-green-600 rounded">适用：</span>
                          {strategy.suitableMarket.map(m => (
                            <Badge key={m} variant="success" className="text-xs">{m}</Badge>
                          ))}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-1 bg-red-500/10 text-red-600 rounded">不适用：</span>
                          {strategy.unsuitableMarket.map(m => (
                            <Badge key={m} variant="danger" className="text-xs">{m}</Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </Card>
              );
            })}
        </div>
      </div>

      {/* 提示信息 */}
      <div className="bg-yellow-500/5 border border-yellow-500/20 rounded-lg p-3">
        <p className="text-xs text-yellow-600 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          <strong>风险提示：</strong>
          以上战法基于历史数据统计，不构成投资建议。短线打板属于高风险交易行为，请根据自身风险承受能力谨慎决策。纪律性才是打板者的"保命符"，没有严格的风控，再高的胜率也会被一次大亏吞噬。
        </p>
      </div>
    </div>
  );
}

// ---- 多战法共振卡片子组件 ----

function MultiMatchCard({ item }: { item: MultiMatchAnalysis }) {
  const riskBadge = item.riskLevel === 'low'
    ? { variant: 'success' as const, text: '低风险' }
    : item.riskLevel === 'medium'
      ? { variant: 'warning' as const, text: '中风险' }
      : { variant: 'danger' as const, text: '高风险' };

  return (
    <Card className="bg-background/80 border-red-500/20 hover:border-red-500/40 transition-colors">
      {/* 头部：标的信息 + 综合评分 */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-red-500/10 rounded-xl flex items-center justify-center">
            <Crosshair className="w-6 h-6 text-red-500" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <StockNameDisplay name={item.name} code={item.code} />
              {item.sector && <Badge variant="info">{item.sector}</Badge>}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-red-500 font-semibold">
                {item.matchCount}个战法共振
              </span>
              <Badge variant={riskBadge.variant}>{riskBadge.text}</Badge>
            </div>
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <div className="flex items-center gap-2">
            <span className={`text-2xl font-bold ${
              item.compositeScore >= 75 ? 'text-red-500' :
              item.compositeScore >= 55 ? 'text-amber-500' : 'text-gray-400'
            }`}>
              {item.compositeScore}
            </span>
            <span className="text-xs text-muted-foreground">分</span>
          </div>
          <Badge variant={item.compositeScore >= 75 ? 'success' : 'warning'}>
            共振推荐
          </Badge>
        </div>
      </div>

      {/* 匹配战法标签 */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        <span className="text-xs text-muted-foreground flex items-center gap-1">
          <Star className="w-3 h-3 text-amber-500" />
          共振战法：
        </span>
        {item.matchedStrategies.map((s) => (
          <Badge key={s} variant="info" className="text-xs">{s}</Badge>
        ))}
      </div>

      {/* 推荐理由 */}
      <div className="mb-4">
        <p className="text-xs font-medium mb-2 flex items-center gap-1.5 text-green-600">
          <Lightbulb className="w-3.5 h-3.5" />
          推荐理由
        </p>
        <ul className="space-y-1">
          {item.reasons.map((r, i) => (
            <li key={i} className="text-sm text-muted-foreground flex items-start gap-1.5">
              <CheckCircle className="w-3.5 h-3.5 text-green-500 mt-0.5 flex-shrink-0" />
              <span>{r}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* 建仓点位 */}
      <div className="mb-4">
        <p className="text-xs font-medium mb-2 flex items-center gap-1.5 text-blue-600">
          <Crosshair className="w-3.5 h-3.5" />
          建仓点位建议
        </p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          {item.entryPoints.map((ep, i) => (
            <div key={i} className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium text-sm">{ep.type}</span>
                <Badge variant="info" className="text-xs">{ep.positionPct}%仓</Badge>
              </div>
              <p className="text-xs font-mono text-blue-600 mb-1">¥{ep.price.toFixed(2)}</p>
              <p className="text-xs text-muted-foreground">{ep.condition}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 买卖分析 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="bg-green-500/5 border border-green-500/20 rounded-lg p-3">
          <p className="text-xs font-medium flex items-center gap-1.5 text-green-600 mb-1.5">
            <TrendingUp className="w-3.5 h-3.5" />
            买入分析
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed">{item.buyAnalysis}</p>
        </div>
        <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
          <p className="text-xs font-medium flex items-center gap-1.5 text-red-600 mb-1.5">
            <TrendingDown className="w-3.5 h-3.5" />
            卖出分析
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed">{item.sellAnalysis}</p>
        </div>
      </div>

      {/* 平均匹配度 */}
      <div className="mt-3 pt-3 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
        <span>多战法平均匹配度</span>
        <div className="flex items-center gap-2">
          <div className="w-32 h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-amber-500 to-red-500 rounded-full transition-all"
              style={{ width: `${item.avgMatchScore}%` }}
            />
          </div>
          <span className="font-mono">{item.avgMatchScore}%</span>
        </div>
      </div>
    </Card>
  );
}
