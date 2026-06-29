import React, { useMemo } from 'react';
import { TrendingDown, Minus, Zap, Flame } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface SectorHeatItem {
  name: string;
  changePct: number; // 涨跌幅百分比
  volume?: number;   // 成交额（亿）
  stockCount?: number;
  /** 趋势变化: accelerating/steady/cooling/reversing */
  trend?: string;
  /** 趋势变化幅度 */
  trendScore?: number;
  /** 是否为主线 */
  mainline?: boolean;
}

interface SectorHeatmapProps {
  items: SectorHeatItem[];
  className?: string;
  maxItems?: number;
  /** 是否显示趋势标记 */
  showTrend?: boolean;
}

/** 趋势配置 */
const TREND_CONFIG: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  accelerating: { icon: <Zap className="w-3 h-3" />, label: '加速', color: 'text-amber-400' },
  steady: { icon: <Minus className="w-3 h-3" />, label: '平稳', color: 'text-muted-foreground' },
  cooling: { icon: <TrendingDown className="w-3 h-3" />, label: '降温', color: 'text-blue-400' },
  reversing: { icon: <TrendingDown className="w-3 h-3" />, label: '转向', color: 'text-danger' },
};

export const SectorHeatmap: React.FC<SectorHeatmapProps> = ({
  items,
  className,
  maxItems = 20,
  showTrend = true,
}) => {
  const displayItems = useMemo(() => {
    return items
      .slice(0, maxItems)
      .sort((a, b) => Math.abs(b.changePct) - Math.abs(a.changePct));
  }, [items, maxItems]);

  const maxAbsChange = useMemo(
    () => Math.max(...displayItems.map((i) => Math.abs(i.changePct)), 1),
    [displayItems]
  );

  const getHeatColor = (changePct: number) => {
    const intensity = Math.abs(changePct) / maxAbsChange;
    if (changePct > 0) {
      return `hsl(var(--success) / ${0.15 + intensity * 0.7})`;
    }
    return `hsl(var(--danger) / ${0.15 + intensity * 0.7})`;
  };

  const getTextColor = (changePct: number) => {
    if (changePct > 2) return 'text-success font-medium';
    if (changePct > 0) return 'text-success/70';
    if (changePct < -2) return 'text-danger font-medium';
    if (changePct < 0) return 'text-danger/70';
    return 'text-muted-foreground';
  };

  if (displayItems.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
        暂无板块数据
      </div>
    );
  }

  return (
    <div className={cn('grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2', className)}>
      {displayItems.map((item) => {
        const trendInfo = item.trend ? TREND_CONFIG[item.trend] : null;
        return (
          <div
            key={item.name}
            className={cn(
              'rounded-lg px-3 py-2.5 text-center transition-all duration-300 hover:scale-[1.03] cursor-default relative',
              'border border-transparent',
              item.mainline && 'ring-1 ring-amber-400/50'
            )}
            style={{
              backgroundColor: getHeatColor(item.changePct),
              borderColor:
                item.changePct > 0
                  ? `hsl(var(--success) / ${0.1 + Math.abs(item.changePct) / maxAbsChange * 0.4})`
                  : `hsl(var(--danger) / ${0.1 + Math.abs(item.changePct) / maxAbsChange * 0.4})`,
            }}
          >
            {/* 主线标记 */}
            {item.mainline && (
              <div className="absolute -top-1 -right-1">
                <Flame className="w-3.5 h-3.5 text-amber-400 drop-shadow-sm" />
              </div>
            )}

            <div className="text-xs font-medium truncate flex items-center justify-center gap-1">
              {item.name}
            </div>
            <div className={cn('mt-0.5 text-sm font-mono font-bold', getTextColor(item.changePct))}>
              {item.changePct > 0 ? '+' : ''}{item.changePct.toFixed(2)}%
            </div>

            {/* 趋势标记 */}
            {showTrend && trendInfo && (
              <div className={cn('flex items-center justify-center gap-0.5 mt-0.5', trendInfo.color)}>
                {trendInfo.icon}
                <span className="text-[10px]">{trendInfo.label}</span>
                {item.trendScore != null && item.trendScore !== 0 && (
                  <span className="text-[9px] ml-0.5">
                    {item.trendScore > 0 ? '+' : ''}{item.trendScore.toFixed(1)}%
                  </span>
                )}
              </div>
            )}

            {item.stockCount != null && (
              <div className="text-[10px] text-muted-foreground mt-0.5">
                {item.stockCount}只
                {item.volume != null ? ` · ${item.volume.toFixed(0)}亿` : ''}
              </div>
            )}
          </div>
        );
      })}
      {items.length > maxItems && (
        <div className="col-span-full text-center text-xs text-muted-foreground pt-1">
          还有 {items.length - maxItems} 个板块未显示
        </div>
      )}
    </div>
  );
};

export default SectorHeatmap;
