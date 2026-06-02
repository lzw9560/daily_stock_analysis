import { useState, useEffect, useCallback } from 'react';
import {
  Crown, TrendingUp, TrendingDown, RefreshCw, Clock, AlertTriangle,
  Skull, ShieldQuestion, Hash, BarChart3, DollarSign, Activity,
  Timer, Zap
} from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Loading } from '@/components/common/Loading';
import { sealPlateApi } from '@/api/sealPlate';
import type { DragonTigerList as DragonTigerListType, DragonTigerItem } from '@/types/sealPlate';

// 风险游资名单
const RISKY_HOT_MONEY: Record<string, { risk: string; style: string; tags: string[] }> = {
  '章盟主': { risk: 'medium', style: '龙头战法', tags: ['实力游资', '偶尔砸盘'] },
  '方新侠': { risk: 'low', style: '趋势接力', tags: ['顶级游资', '格局好'] },
  '作手新一': { risk: 'medium', style: '首板挖掘', tags: ['实力游资', '快进快出'] },
  '炒股养家': { risk: 'low', style: '情绪周期', tags: ['顶级游资', '格局好'] },
  '赵老哥': { risk: 'medium', style: '连板龙头', tags: ['实力游资', '快进快出'] },
};

const ONE_DAY_TOUR_SEATS = new Set([
  '散户集中营', '拉萨东环路', '拉萨团结路', '拉萨东城区',
]);

function getSeatRisk(name: string): { level: string; label: string; icon: JSX.Element | null } {
  for (const seat of ONE_DAY_TOUR_SEATS) {
    if (name.includes(seat)) {
      return { level: 'danger', label: '一日游', icon: <Skull className="w-3 h-3" /> };
    }
  }
  const info = RISKY_HOT_MONEY[name];
  if (info?.risk === 'medium') {
    return { level: 'warning', label: '快进快出', icon: <ShieldQuestion className="w-3 h-3" /> };
  }
  return { level: 'safe', label: '', icon: null };
}

/** 判断个股是否为低风险（无一日游席位、无快进快出游资） */
function isLowRisk(item: DragonTigerItem): boolean {
  const allSeats = [...item.buySeats, ...item.sellSeats];
  return allSeats.every(s => getSeatRisk(s.name).level === 'safe');
}

// ---- 明细指标卡片 ----

function MetricsRow({ item }: { item: DragonTigerItem }) {
  const changeColor = item.changePct > 0 ? 'text-red-500' : item.changePct < 0 ? 'text-green-500' : 'text-muted-foreground';

  return (
    <div className="grid grid-cols-3 md:grid-cols-5 gap-2 mb-3 p-2.5 bg-muted/20 rounded-lg">
      <div className="text-center">
        <div className="text-xs text-muted-foreground mb-0.5 flex items-center justify-center gap-0.5">
          <Activity className="w-3 h-3" />涨跌幅
        </div>
        <div className={`text-sm font-bold ${changeColor}`}>
          {item.changePct > 0 ? '+' : ''}{item.changePct.toFixed(2)}%
        </div>
      </div>
      <div className="text-center">
        <div className="text-xs text-muted-foreground mb-0.5 flex items-center justify-center gap-0.5">
          <DollarSign className="w-3 h-3" />收盘价
        </div>
        <div className="text-sm font-mono font-medium">
          {item.closePrice.toFixed(2)}
        </div>
      </div>
      <div className="text-center">
        <div className="text-xs text-muted-foreground mb-0.5 flex items-center justify-center gap-0.5">
          <BarChart3 className="w-3 h-3" />换手率
        </div>
        <div className="text-sm font-medium">
          {item.turnoverRate.toFixed(1)}%
        </div>
      </div>
      <div className="text-center">
        <div className="text-xs text-muted-foreground mb-0.5 flex items-center justify-center gap-0.5">
          <Zap className="w-3 h-3" />封单
        </div>
        <div className="text-sm font-medium">
          {item.sealAmount >= 10000
            ? `${(item.sealAmount / 10000).toFixed(1)}亿`
            : `${item.sealAmount.toFixed(0)}万`}
        </div>
      </div>
      <div className="text-center">
        <div className="text-xs text-muted-foreground mb-0.5 flex items-center justify-center gap-0.5">
          <Timer className="w-3 h-3" />封板时间
        </div>
        <div className="text-sm font-mono font-medium">
          {item.sealTime || '--'}
        </div>
      </div>
    </div>
  );
}

// ---- 龙虎榜卡片 ----

function DragonTigerCard({ item }: { item: DragonTigerItem }) {
  const buyRisks = item.buySeats.map(s => getSeatRisk(s.name));
  const sellRisks = item.sellSeats.map(s => getSeatRisk(s.name));
  const hasBuyRisk = buyRisks.some(r => r.level !== 'safe');
  const hasSellRisk = sellRisks.some(r => r.level !== 'safe');
  const hasOneDayTour = buyRisks.some(r => r.level === 'danger') || sellRisks.some(r => r.level === 'danger');

  const scoreColor = item.score >= 80 ? 'text-green-500' : item.score >= 60 ? 'text-yellow-500' : 'text-red-500';

  return (
    <div className={`bg-card hover:bg-card/80 rounded-lg p-4 border transition-colors ${
      hasOneDayTour
        ? 'border-orange-500/50 bg-orange-500/[0.03]'
        : hasBuyRisk
          ? 'border-yellow-500/30'
          : 'border-border/50'
    }`}>
      {/* 头部：排名 + 名称 + 评分 */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          {/* 排名标记 */}
          <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
            item.rank <= 3
              ? 'bg-yellow-500/20 text-yellow-500 border border-yellow-500/30'
              : 'bg-muted text-muted-foreground'
          }`}>
            {item.rank}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-medium">{item.name}</span>
              <span className="text-xs text-muted-foreground font-mono">{item.code}</span>
              {item.sector && <Badge variant="info" className="text-xs">{item.sector}</Badge>}
            </div>
            {hasOneDayTour && (
              <Badge variant="danger" className="text-xs mt-1 flex items-center gap-1 w-fit">
                <Skull className="w-3 h-3" />一日游风险
              </Badge>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-xs text-muted-foreground">评分</div>
            <div className={`text-lg font-bold ${scoreColor}`}>{item.score}</div>
          </div>
          <Badge
            variant={item.netBuy > 0 ? 'success' : 'danger'}
            className="flex items-center gap-1"
          >
            {item.netBuy > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
            {item.netBuy >= 0 ? '+' : ''}{item.netBuy.toLocaleString()}万
          </Badge>
        </div>
      </div>

      {/* 明细指标 */}
      <MetricsRow item={item} />

      {/* 上榜理由 */}
      {item.reason && (
        <p className="text-xs text-muted-foreground mb-3 px-1">{item.reason}</p>
      )}

      {/* 买卖席位 */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-xs font-medium text-green-600 mb-1">
            买方 ({item.buySeats.length})
          </p>
          <div className="space-y-1">
            {item.buySeats.length > 0 ? (
              item.buySeats.slice(0, 3).map((seat, i) => {
                const risk = getSeatRisk(seat.name);
                return (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1 truncate">
                      <span className="text-muted-foreground truncate">{seat.name}</span>
                      {risk.icon && (
                        <span className={risk.level === 'danger' ? 'text-orange-500' : 'text-yellow-500'} title={risk.label}>
                          {risk.icon}
                        </span>
                      )}
                    </div>
                    <span className="text-green-500 font-medium ml-2 whitespace-nowrap">
                      +{seat.amount.toLocaleString()}万
                    </span>
                  </div>
                );
              })
            ) : (
              <span className="text-xs text-muted-foreground">无数据</span>
            )}
          </div>
        </div>

        <div>
          <p className="text-xs font-medium text-red-600 mb-1">
            卖方 ({item.sellSeats.length})
          </p>
          <div className="space-y-1">
            {item.sellSeats.length > 0 ? (
              item.sellSeats.slice(0, 3).map((seat, i) => {
                const risk = getSeatRisk(seat.name);
                return (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1 truncate">
                      <span className="text-muted-foreground truncate">{seat.name}</span>
                      {risk.icon && (
                        <span className={risk.level === 'danger' ? 'text-orange-500' : 'text-yellow-500'} title={risk.label}>
                          {risk.icon}
                        </span>
                      )}
                    </div>
                    <span className="text-red-500 font-medium ml-2 whitespace-nowrap">
                      -{seat.amount.toLocaleString()}万
                    </span>
                  </div>
                );
              })
            ) : (
              <span className="text-xs text-muted-foreground">无数据</span>
            )}
          </div>
        </div>
      </div>

      {/* 风险标注汇总 */}
      {(hasBuyRisk || hasSellRisk) && (
        <div className="mt-3 pt-3 border-t border-border/30">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {buyRisks.filter(r => r.level === 'danger').length > 0 && (
              <span className="text-orange-500 flex items-center gap-1">
                <Skull className="w-3 h-3" />
                买方含一日游席位
              </span>
            )}
            {sellRisks.filter(r => r.level === 'danger').length > 0 && (
              <span className="text-orange-500 flex items-center gap-1">
                <Skull className="w-3 h-3" />
                卖方含一日游席位
              </span>
            )}
            {buyRisks.filter(r => r.level === 'warning').length > 0 && (
              <span className="text-yellow-500 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />
                买方含快进快出游资
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---- 主组件 ----

export default function DragonTigerList() {
  const [dragonTiger, setDragonTiger] = useState<DragonTigerListType | null>(null);
  const [loading, setLoading] = useState(true);
  const [showRiskyOnly, setShowRiskyOnly] = useState(false);
  const [showLowRiskOnly, setShowLowRiskOnly] = useState(false);
  const [minScore, setMinScore] = useState(80);

  const fetchDragonTiger = useCallback(async (ms?: number) => {
    setLoading(true);
    try {
      const data = await sealPlateApi.getDragonTiger({ minScore: ms ?? minScore });
      setDragonTiger(data);
    } catch (error) {
      console.error('获取龙虎榜失败:', error);
    } finally {
      setLoading(false);
    }
  }, [minScore]);

  useEffect(() => {
    fetchDragonTiger();
  }, [fetchDragonTiger]);

  const handleMinScoreChange = (newScore: number) => {
    setMinScore(newScore);
    // 等待 state 更新后自动 refetch（由 useEffect 触发）
  };

  // 知名游资库
  const famousSeats = [
    { name: '章盟主', style: '龙头战法', risk: '⚠️中风险', riskColor: 'text-yellow-500', winRate: '68%' },
    { name: '方新侠', style: '趋势接力', risk: '✅低风险', riskColor: 'text-green-500', winRate: '72%' },
    { name: '作手新一', style: '首板挖掘', risk: '⚠️中风险', riskColor: 'text-yellow-500', winRate: '65%' },
    { name: '炒股养家', style: '情绪周期', risk: '✅低风险', riskColor: 'text-green-500', winRate: '75%' },
    { name: '赵老哥', style: '连板龙头', risk: '⚠️中风险', riskColor: 'text-yellow-500', winRate: '70%' },
    { name: '拉萨天团', style: '散户集中', risk: '🔴一日游', riskColor: 'text-red-500', winRate: '42%' },
  ];

  if (loading && !dragonTiger) {
    return (
      <Card>
        <div className="flex items-center justify-center h-48">
          <Loading label="加载龙虎榜..." />
        </div>
      </Card>
    );
  }

  const items = dragonTiger?.items || [];

  return (
    <div className="space-y-6">
      {/* 知名席位速览 */}
      <Card>
        <div className="flex items-center gap-2 mb-3">
          <Crown className="w-5 h-5 text-yellow-500" />
          <span className="font-medium">知名席位监控</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
          {famousSeats.map((seat) => (
            <div
              key={seat.name}
              className="bg-muted/30 rounded-lg p-2.5 text-center"
            >
              <div className="font-medium text-sm">{seat.name}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{seat.style}</div>
              <div className="flex items-center justify-center gap-2 mt-1">
                <span className={`text-xs ${seat.riskColor}`}>{seat.risk}</span>
                <span className="text-xs text-green-500">{seat.winRate}</span>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* 龙虎榜明细 */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Hash className="w-5 h-5 text-yellow-500" />
            <span className="font-medium">龙虎榜明细</span>
            {items.length > 0 && (
              <Badge variant="info">{items.length}只</Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* 最低评分筛选 */}
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-muted-foreground">最低评分:</span>
              <select
                value={minScore}
                onChange={(e) => handleMinScoreChange(Number(e.target.value))}
                className="bg-muted border border-border rounded px-1.5 py-1 text-xs outline-none focus:border-yellow-500/50"
              >
                <option value={50}>50</option>
                <option value={60}>60</option>
                <option value={70}>70</option>
                <option value={80}>80</option>
                <option value={90}>90</option>
              </select>
            </div>
            <button
              className={`text-xs px-2 py-1 rounded border transition-colors ${
                showRiskyOnly
                  ? 'bg-orange-500/10 border-orange-500/30 text-orange-500'
                  : 'bg-muted/30 border-border text-muted-foreground'
              }`}
              onClick={() => { setShowRiskyOnly(!showRiskyOnly); if (!showRiskyOnly) setShowLowRiskOnly(false); }}
            >
              <Skull className="w-3 h-3 inline mr-1" />
              仅看风险标的
            </button>
            <button
              className={`text-xs px-2 py-1 rounded border transition-colors ${
                showLowRiskOnly
                  ? 'bg-green-500/10 border-green-500/30 text-green-500'
                  : 'bg-muted/30 border-border text-muted-foreground'
              }`}
              onClick={() => { setShowLowRiskOnly(!showLowRiskOnly); if (!showLowRiskOnly) setShowRiskyOnly(false); }}
            >
              <ShieldQuestion className="w-3 h-3 inline mr-1" />
              只看低风险
            </button>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {dragonTiger?.date || '--'}
            </span>
            <Button size="sm" variant="ghost" onClick={() => fetchDragonTiger()} disabled={loading}>
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        <div className="space-y-3">
          {items.length > 0 ? (
            items
              .filter(item => {
                if (showRiskyOnly) {
                  return item.buySeats.some(s => {
                    for (const o of ONE_DAY_TOUR_SEATS) {
                      if (s.name.includes(o)) return true;
                    }
                    return s.name in RISKY_HOT_MONEY && RISKY_HOT_MONEY[s.name].risk === 'medium';
                  });
                }
                if (showLowRiskOnly) return isLowRisk(item);
                return true;
              })
              .map((item) => (
                <DragonTigerCard key={item.code} item={item} />
              ))
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <Crown className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>暂无龙虎榜数据</p>
              <p className="text-xs">评分≥{minScore}的标的暂无，请降低阈值或等待龙虎榜发布（16:30后）</p>
              {showLowRiskOnly && <p className="text-xs mt-1 text-green-500">当前筛选：只看低风险（无一日游/游资席位）</p>}
              {showRiskyOnly && <p className="text-xs mt-1 text-orange-500">当前筛选：仅看风险标的</p>}
            </div>
          )}
        </div>

        {/* 图例 */}
        <div className="mt-4 pt-3 border-t border-border flex flex-wrap gap-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <Skull className="w-3 h-3 text-orange-500" />
            <span>= 一日游席位（拉萨天团等，建议回避）</span>
          </div>
          <div className="flex items-center gap-1">
            <AlertTriangle className="w-3 h-3 text-yellow-500" />
            <span>= 快进快出游资（需警惕次日砸盘）</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-green-500 font-bold">✅</span>
            <span>= 稳健机构/格局游资</span>
          </div>
        </div>
      </Card>

      {/* 说明 */}
      <div className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-3">
        <p className="text-xs text-blue-600 dark:text-blue-400 space-y-1">
          <span className="block"><strong>提示：</strong></span>
          <span>• 龙虎榜明细基于打板评分排序，评分越高确定性越强</span>
          <span>• 龙虎榜数据通常在交易日16:30左右更新</span>
          <span className="block">• 🔴一日游席位（拉萨天团等）标的建议回避，次日大概率低开</span>
          <span className="block">• ⚠️快进快出游资参与时，需警惕次日获利了结砸盘风险</span>
          <span className="block">• ✅机构专用/北向资金净买入标的相对稳健</span>
        </p>
      </div>
    </div>
  );
}
