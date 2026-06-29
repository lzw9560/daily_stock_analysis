import type React from 'react';
import { useEffect, useState, useMemo } from 'react';
import { RefreshCw, ArrowUpDown } from 'lucide-react';
import { AppPage, PageHeader, SignalCard } from '../components/common';
import { cn } from '../utils/cn';
import type { SignalInfo } from '../components/common/SignalCard';
import { getShortTermSignals, type ShortTermSignal } from '../api/enhancedRecommendation';

type FilterType = 'all' | 'first_board' | 'consecutive_board' | 'low_suck' | 'n_pattern' | 'breakout';

const FILTER_OPTIONS: { value: FilterType; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'first_board', label: '打板' },
  { value: 'consecutive_board', label: '连板' },
  { value: 'low_suck', label: '低吸' },
  { value: 'breakout', label: '突破' },
];

const STRATEGY_MAP: Record<string, FilterType> = {
  '首板挖掘': 'first_board',
  '连板接力': 'consecutive_board',
  '低吸龙头': 'low_suck',
  '反包战法': 'low_suck',
  'N字反击': 'n_pattern',
  '平台突破': 'breakout',
  '涨停敢死队': 'first_board',
  '尾盘偷袭': 'breakout',
};

const TYPE_EMOJI: Record<string, string> = {
  first_board: '⚡',
  consecutive_board: '🔥',
  low_suck: '📉',
  breakout: '🚀',
  n_pattern: '📈',
};

const StrategySignalsPage: React.FC = () => {
  const [signals, setSignals] = useState<SignalInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterType>('all');
  const [sortBy, setSortBy] = useState<'confidence' | 'time'>('confidence');

  const loadSignals = async () => {
    setLoading(true);
    try {
      const res = await getShortTermSignals();
      setSignals(
        (res.signals || []).map((s: ShortTermSignal, i: number) => {
          const mappedType = (STRATEGY_MAP[s.strategy] || 'breakout') as SignalInfo['type'];
          return {
            id: String(i),
            type: mappedType,
            typeLabel: s.strategy,
            typeEmoji: TYPE_EMOJI[mappedType] || '📊',
            symbol: s.code,
            name: s.name,
            price: s.entryPriceRange?.[0] || 0,
            changePercent: 0,
            confidence: s.confidence,
            buyPriceMin: s.entryPriceRange?.[0] || 0,
            buyPriceMax: s.entryPriceRange?.[1] || 0,
            stopLoss: s.stopLoss,
            holdDays: String(s.expectedHoldDays) + '天',
            sectors: [],
            reason: s.reason || '',
            riskWarning: s.riskFactors?.join('，') || '',
            timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
          };
        })
      );
    } catch (e) {
      console.error('Signal load error:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    document.title = '战法信号 - DSA';
    loadSignals();
    const timer = setInterval(loadSignals, 60000);
    return () => clearInterval(timer);
  }, []);

  const filteredSignals = useMemo(() => {
    let result = filter === 'all' ? signals : signals.filter((s) => s.type === filter);
    if (sortBy === 'confidence') {
      result = [...result].sort((a, b) => b.confidence - a.confidence);
    }
    return result;
  }, [signals, filter, sortBy]);

  if (loading && signals.length === 0) {
    return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">加载中...</div></AppPage>;
  }

  return (
    <AppPage className="space-y-5">
      <PageHeader eyebrow="Strategy Signals" title="战法信号" description="短线战法实时信号列表 + 筛选" />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setFilter(opt.value)}
              className={cn(
                'px-3 py-1.5 text-xs rounded-full border transition-colors',
                filter === opt.value
                  ? 'bg-primary/10 border-primary text-primary font-medium'
                  : 'border-border text-muted-foreground hover:border-primary/30'
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setSortBy(sortBy === 'confidence' ? 'time' : 'confidence')} className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
            <ArrowUpDown className="h-3 w-3" />
            {sortBy === 'confidence' ? '置信度' : '时间'}
          </button>
          <button onClick={loadSignals} className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
            <RefreshCw className="h-3 w-3" />
            刷新
          </button>
        </div>
      </div>

      <div className="space-y-3">
        {filteredSignals.length > 0 ? (
          filteredSignals.map((signal) => (
            <SignalCard
              key={signal.id}
              signal={signal}
              onExpand={() => {}}
              isExpanded={false}
            />
          ))
        ) : (
          <div className="text-center py-12 text-muted-foreground text-sm">暂无信号</div>
        )}
      </div>
    </AppPage>
  );
};

export default StrategySignalsPage;
