import React from 'react';
import { cn } from '../../utils/cn';

export interface MoneyFlowItem {
  name: string;
  amount: number; // 亿元，正值流入，负值流出
  changePct?: number; // 涨跌幅
}

interface MoneyFlowBarProps {
  items: MoneyFlowItem[];
  maxBars?: number;
  className?: string;
}

export const MoneyFlowBar: React.FC<MoneyFlowBarProps> = ({
  items,
  maxBars = 8,
  className,
}) => {
  const displayItems = items.slice(0, maxBars);
  const maxAmount = Math.max(...displayItems.map((i) => Math.abs(i.amount)), 1);

  if (displayItems.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
        暂无资金流向数据
      </div>
    );
  }

  return (
    <div className={cn('space-y-2', className)}>
      {displayItems.map((item) => {
        const isInflow = item.amount >= 0;
        const widthPct = (Math.abs(item.amount) / maxAmount) * 100;
        return (
          <div key={item.name} className="flex items-center gap-2 text-xs">
            <span className="w-16 flex-shrink-0 truncate text-muted-foreground">
              {item.name}
            </span>
            <div className="relative flex-1 h-6 rounded bg-muted/40 overflow-hidden">
              <div
                className={cn(
                  'absolute top-0 h-full rounded transition-all duration-500 flex items-center',
                  isInflow ? 'left-0 bg-success/70' : 'right-0 bg-danger/70'
                )}
                style={{ width: `${widthPct}%` }}
              >
                {widthPct > 25 && (
                  <span
                    className={cn(
                      'text-[10px] font-mono px-1.5 whitespace-nowrap',
                      isInflow ? 'text-white' : 'text-white'
                    )}
                  >
                    {isInflow ? '+' : ''}{item.amount.toFixed(1)}亿
                  </span>
                )}
              </div>
            </div>
            <span
              className={cn(
                'w-16 flex-shrink-0 text-right font-mono tabular-nums',
                isInflow ? 'text-success' : 'text-danger'
              )}
            >
              {isInflow ? '+' : ''}{item.amount.toFixed(1)}亿
            </span>
            {item.changePct != null && (
              <span
                className={cn(
                  'w-12 flex-shrink-0 text-right font-mono tabular-nums text-[10px]',
                  item.changePct > 0 ? 'text-success/70' : 'text-danger/70'
                )}
              >
                {item.changePct > 0 ? '+' : ''}{item.changePct.toFixed(2)}%
              </span>
            )}
          </div>
        );
      })}
      {items.length > maxBars && (
        <p className="text-xs text-muted-foreground text-center">
          还有 {items.length - maxBars} 个板块未显示
        </p>
      )}
    </div>
  );
};

export default MoneyFlowBar;
