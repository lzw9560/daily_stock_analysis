import { useState, useEffect, useCallback } from 'react';
import { Flame, Zap, RefreshCw, TrendingUp, RotateCcw, Filter } from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Loading } from '@/components/common/Loading';
import { sealPlateApi } from '@/api/sealPlate';
import type { StockPool, StockPoolItem } from '@/types/sealPlate';

interface Props {
  onStockSelect?: (code: string) => void;
}

type PoolType = 'first_board' | 'continuous' | 'weak_to_strong' | 'reversal';

const POOL_CONFIG: Record<PoolType, { label: string; icon: typeof Flame; color: string }> = {
  first_board: { label: '首板池', icon: Flame, color: 'text-red-500' },
  continuous: { label: '连板池', icon: Zap, color: 'text-yellow-500' },
  weak_to_strong: { label: '弱转强', icon: TrendingUp, color: 'text-green-500' },
  reversal: { label: '反包池', icon: RotateCcw, color: 'text-blue-500' },
};

function PoolCard({ item, poolType, onClick }: { item: StockPoolItem; poolType: PoolType; onClick?: () => void }) {
  const config = POOL_CONFIG[poolType];
  const Icon = config.icon;

  return (
    <div
      className="bg-card hover:bg-card/80 rounded-lg p-3 border border-border/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${config.color}`} />
          <span className="font-medium">{item.name}</span>
          <span className="text-xs text-muted-foreground">{item.code}</span>
        </div>
        <Badge
          variant={item.score >= 80 ? 'success' : item.score >= 60 ? 'warning' : 'default'}
          className="text-xs"
        >
          {item.score}分
        </Badge>
      </div>
      <div className="flex items-center gap-4 text-sm">
        <span className={item.changePct > 0 ? 'text-red-500' : 'text-green-500'}>
          +{item.changePct.toFixed(2)}%
        </span>
        {item.sector && (
          <span className="text-muted-foreground">{item.sector}</span>
        )}
        <span className="text-muted-foreground">
          封单: {item.sealAmount >= 10000 ? `${(item.sealAmount / 10000).toFixed(1)}亿` : `${item.sealAmount.toFixed(0)}万`}
        </span>
      </div>
    </div>
  );
}

export default function StockPoolPanel({ onStockSelect }: Props) {
  const [stockPool, setStockPool] = useState<StockPool | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<PoolType>('first_board');

  const fetchStockPool = useCallback(async () => {
    setLoading(true);
    try {
      const data = await sealPlateApi.getStockPool();
      setStockPool(data);
    } catch (error) {
      console.error('获取股票池失败:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStockPool();
  }, [fetchStockPool]);

  const getCurrentPoolItems = (): StockPoolItem[] => {
    if (!stockPool) return [];
    switch (activeTab) {
      case 'first_board':
        return stockPool.firstBoardPool;
      case 'continuous':
        return stockPool.continuousPool;
      case 'weak_to_strong':
        return stockPool.weakToStrongPool;
      case 'reversal':
        return stockPool.reversalPool;
      default:
        return [];
    }
  };

  const getPoolCount = (type: PoolType): number => {
    if (!stockPool) return 0;
    switch (type) {
      case 'first_board':
        return stockPool.firstBoardPool.length;
      case 'continuous':
        return stockPool.continuousPool.length;
      case 'weak_to_strong':
        return stockPool.weakToStrongPool.length;
      case 'reversal':
        return stockPool.reversalPool.length;
      default:
        return 0;
    }
  };

  if (loading && !stockPool) {
    return (
      <Card>
        <div className="flex items-center justify-center h-48">
          <Loading label="加载股票池..." />
        </div>
      </Card>
    );
  }

  const currentItems = getCurrentPoolItems();

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Filter className="w-5 h-5" />
          <span className="font-medium">候选股票池</span>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={fetchStockPool}
          disabled={loading}
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>
      <div className="space-y-4">
        {/* 标签页 */}
        <div className="flex gap-2 border-b border-border overflow-x-auto">
          {(Object.keys(POOL_CONFIG) as PoolType[]).map((type) => {
            const config = POOL_CONFIG[type];
            const Icon = config.icon;
            const count = getPoolCount(type);
            return (
              <button
                key={type}
                className={`flex items-center gap-1.5 px-3 py-2 text-sm whitespace-nowrap border-b-2 transition-colors ${
                  activeTab === type
                    ? 'border-primary text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
                onClick={() => setActiveTab(type)}
              >
                <Icon className={`w-4 h-4 ${config.color}`} />
                {config.label}
                {count > 0 && (
                  <Badge variant="default" className="ml-1 text-xs">
                    {count}
                  </Badge>
                )}
              </button>
            );
          })}
        </div>

        {/* 股票列表 */}
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {currentItems.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p>暂无{POOL_CONFIG[activeTab].label}数据</p>
            </div>
          ) : (
            currentItems.map((item) => (
              <PoolCard
                key={item.code}
                item={item}
                poolType={activeTab}
                onClick={() => onStockSelect?.(item.code)}
              />
            ))
          )}
        </div>

        {/* 池说明 */}
        <div className="bg-muted/30 rounded-lg p-3 text-xs space-y-1">
          <p className="font-medium text-muted-foreground">池说明:</p>
          <p>• <strong>首板池</strong>: 昨日首板+今日高开3%+量比&gt;3</p>
          <p>• <strong>连板池</strong>: 昨日连板+竞价封单&gt;5万手</p>
          <p>• <strong>弱转强</strong>: 昨日烂板+今日竞价高开5%+快速拉升</p>
          <p>• <strong>反包池</strong>: 前日断板+今日低开高走+放量</p>
        </div>
      </div>
    </Card>
  );
}
