import type React from 'react';
import { cn } from '../../utils/cn';

type TickerItem = {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
};

const DEFAULT_INDICES: TickerItem[] = [
  { symbol: '000001', name: '上证', price: 3356.82, change: 39.25, changePercent: 1.18 },
  { symbol: '399001', name: '深成指', price: 10852.34, change: 82.71, changePercent: 0.77 },
  { symbol: '399006', name: '创业板', price: 2156.47, change: -12.38, changePercent: -0.57 },
];

type MarketTickerProps = {
  indices?: TickerItem[];
  className?: string;
  compact?: boolean;
};

export const MarketTicker: React.FC<MarketTickerProps> = ({
  indices = DEFAULT_INDICES,
  className,
  compact = false,
}) => {
  return (
    <div className={cn('flex items-center gap-3 overflow-x-auto', compact && 'gap-2', className)}>
      {indices.map((index) => {
        const isUp = index.changePercent > 0;
        const isFlat = index.changePercent === 0;
        return (
          <div
            key={index.symbol}
            className={cn('market-ticker-item', compact && 'px-2 py-1')}
          >
            <span className={cn('font-medium text-foreground whitespace-nowrap', compact ? 'text-[11px]' : 'text-xs')}>
              {index.name}
            </span>
            <span className={cn('font-bold tabular-nums text-foreground', compact ? 'text-xs' : 'text-sm')}>
              {index.price.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
            </span>
            <span
              className={cn(
                'font-medium tabular-nums',
                compact ? 'text-[10px]' : 'text-xs',
                isUp ? 'stock-up' : isFlat ? 'stock-flat' : 'stock-down'
              )}
            >
              {isUp ? '+' : ''}{index.changePercent.toFixed(2)}%
            </span>
          </div>
        );
      })}
    </div>
  );
};
