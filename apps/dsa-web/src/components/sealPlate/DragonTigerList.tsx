import { useState, useEffect, useCallback } from 'react';
import { Crown, TrendingUp, TrendingDown, RefreshCw, Clock } from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Loading } from '@/components/common/Loading';
import { sealPlateApi } from '@/api/sealPlate';
import type { DragonTigerList as DragonTigerListType, DragonTigerItem } from '@/types/sealPlate';

function DragonTigerCard({ item }: { item: DragonTigerItem }) {
  return (
    <div className="bg-card hover:bg-card/80 rounded-lg p-4 border border-border/50 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <Crown className="w-4 h-4 text-yellow-500" />
          <span className="font-medium">{item.name}</span>
          <span className="text-sm text-muted-foreground">{item.code}</span>
        </div>
        <Badge
          variant={item.netBuy > 0 ? 'success' : 'danger'}
          className="flex items-center gap-1"
        >
          {item.netBuy > 0 ? (
            <TrendingUp className="w-3 h-3" />
          ) : (
            <TrendingDown className="w-3 h-3" />
          )}
          {item.netBuy >= 0 ? '+' : ''}{item.netBuy.toLocaleString()}万
        </Badge>
      </div>

      <p className="text-xs text-muted-foreground mb-3">{item.reason}</p>

      <div className="grid grid-cols-2 gap-3">
        {/* 买方席位 */}
        <div>
          <p className="text-xs font-medium text-green-600 dark:text-green-400 mb-1">
            买方 ({item.buySeats.length})
          </p>
          <div className="space-y-1">
            {item.buySeats.slice(0, 3).map((seat, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground truncate">{seat.name}</span>
                <span className="text-green-500 font-medium ml-2">
                  +{seat.amount.toLocaleString()}万
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* 卖方席位 */}
        <div>
          <p className="text-xs font-medium text-red-600 dark:text-red-400 mb-1">
            卖方 ({item.sellSeats.length})
          </p>
          <div className="space-y-1">
            {item.sellSeats.slice(0, 3).map((seat, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground truncate">{seat.name}</span>
                <span className="text-red-500 font-medium ml-2">
                  -{seat.amount.toLocaleString()}万
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DragonTigerList() {
  const [dragonTiger, setDragonTiger] = useState<DragonTigerListType | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchDragonTiger = useCallback(async () => {
    setLoading(true);
    try {
      const data = await sealPlateApi.getDragonTiger();
      setDragonTiger(data);
    } catch (error) {
      console.error('获取龙虎榜失败:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDragonTiger();
  }, [fetchDragonTiger]);

  if (loading && !dragonTiger) {
    return (
      <Card>
        <div className="flex items-center justify-center h-48">
          <Loading label="加载龙虎榜..." />
        </div>
      </Card>
    );
  }

  const famousSeats = [
    { name: '章盟主', style: '龙头战法', winRate: '68%' },
    { name: '方新侠', style: '趋势接力', winRate: '72%' },
    { name: '作手新一', style: '首板挖掘', winRate: '65%' },
    { name: '炒股养家', style: '情绪周期', winRate: '75%' },
    { name: '赵老哥', style: '连板龙头', winRate: '70%' },
  ];

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Crown className="w-5 h-5 text-yellow-500" />
          <span className="font-medium">龙虎榜监控</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {dragonTiger?.date || new Date().toLocaleDateString()}
          </span>
          <Button
            size="sm"
            variant="ghost"
            onClick={fetchDragonTiger}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>
      <div className="space-y-4">
        {/* 知名游资席位 */}
        <div className="bg-muted/30 rounded-lg p-3">
          <p className="text-xs font-medium text-muted-foreground mb-2">知名游资席位</p>
          <div className="flex flex-wrap gap-2">
            {famousSeats.map((seat) => (
              <div
                key={seat.name}
                className="bg-background/50 rounded px-2 py-1 text-xs"
              >
                <span className="font-medium">{seat.name}</span>
                <span className="text-muted-foreground ml-1">{seat.style}</span>
                <span className="text-green-500 ml-1">{seat.winRate}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 龙虎榜列表 */}
        {dragonTiger && dragonTiger.items.length > 0 ? (
          <div className="space-y-3">
            {dragonTiger.items.map((item, index) => (
              <DragonTigerCard key={index} item={item} />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            <Crown className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>暂无龙虎榜数据</p>
            <p className="text-xs">龙虎榜通常在收盘后16:30发布</p>
          </div>
        )}

        {/* 说明 */}
        <div className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-3">
          <p className="text-xs text-blue-600 dark:text-blue-400">
            <strong>提示：</strong>龙虎榜数据通常在交易日收盘后16:30左右更新。
            知名游资介入是重要的短线参考指标，但需结合其他因素综合判断。
          </p>
        </div>
      </div>
    </Card>
  );
}
