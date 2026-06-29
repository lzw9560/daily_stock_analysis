import type React from 'react';
import { cn } from '../../utils/cn';

type PositionSummaryProps = {
  totalAssets: number;
  dailyPnl: number;
  dailyPnlPercent: number;
  totalPnl?: number;
  totalPnlPercent?: number;
  positionCount?: number;
  cashCount?: number;
  winRate?: number;
  className?: string;
};

export const PositionSummary: React.FC<PositionSummaryProps> = ({
  totalAssets,
  dailyPnl,
  dailyPnlPercent,
  totalPnl,
  totalPnlPercent,
  positionCount,
  cashCount,
  winRate,
  className,
}) => {
  const isDailyUp = dailyPnlPercent >= 0;
  const isTotalUp = (totalPnlPercent ?? 0) >= 0;

  return (
    <div className={cn('rounded-xl border border-[hsl(var(--foreground)/0.06)] bg-card/72 p-4', className)}>
      <div className="grid grid-cols-3 gap-4">
        <div>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">总资产</span>
          <div className="text-lg font-bold text-foreground tabular-nums mt-0.5">
            ¥{totalAssets.toLocaleString('zh-CN')}
          </div>
        </div>
        <div>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">今日盈亏</span>
          <div className={cn('text-lg font-bold tabular-nums mt-0.5', isDailyUp ? 'stock-up' : 'stock-down')}>
            {isDailyUp ? '+' : ''}¥{dailyPnl.toLocaleString('zh-CN')} ({isDailyUp ? '+' : ''}{dailyPnlPercent.toFixed(2)}%)
          </div>
        </div>
        <div>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">累计盈亏</span>
          <div className={cn('text-lg font-bold tabular-nums mt-0.5', isTotalUp ? 'stock-up' : 'stock-down')}>
            {totalPnl != null ? (
              <>{isTotalUp ? '+' : ''}¥{totalPnl.toLocaleString('zh-CN')} ({isTotalUp ? '+' : ''}{totalPnlPercent?.toFixed(2) ?? 0}%)</>
            ) : (
              <span className="text-muted-foreground">--</span>
            )}
          </div>
        </div>
      </div>
      {(positionCount != null || winRate != null) && (
        <div className="flex items-center gap-6 mt-3 pt-3 border-t border-[hsl(var(--foreground)/0.05)]">
          {positionCount != null && (
            <span className="text-xs text-muted-foreground">
              持仓: <span className="font-medium text-foreground">{positionCount}只</span>
            </span>
          )}
          {cashCount != null && (
            <span className="text-xs text-muted-foreground">
              空仓: <span className="font-medium text-foreground">{cashCount}天</span>
            </span>
          )}
          {winRate != null && (
            <span className="text-xs text-muted-foreground">
              胜率: <span className={cn('font-medium', winRate >= 50 ? 'stock-up' : 'stock-down')}>{winRate}%</span>
            </span>
          )}
        </div>
      )}
    </div>
  );
};
