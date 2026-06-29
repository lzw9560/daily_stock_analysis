import type React from 'react';
import { cn } from '../../utils/cn';
import { Badge } from './Badge';

export type SignalInfo = {
  id: string;
  type: 'first_board' | 'consecutive_board' | 'low_suck' | 'n_pattern' | 'breakout';
  typeLabel: string;
  typeEmoji: string;
  symbol: string;
  name: string;
  price: number;
  changePercent: number;
  confidence: number; // 0-100
  buyPriceMin?: number;
  buyPriceMax?: number;
  stopLoss?: number;
  holdDays?: string;
  sectors?: string[];
  reason?: string;
  riskWarning?: string;
  timestamp: string;
};

type SignalCardProps = {
  signal: SignalInfo;
  onExpand?: (id: string) => void;
  isExpanded?: boolean;
  className?: string;
};

function getConfidenceClass(confidence: number): string {
  if (confidence >= 80) return 'confidence-high';
  if (confidence >= 60) return 'confidence-medium';
  return 'confidence-low';
}

function getConfidenceBgClass(confidence: number): string {
  if (confidence >= 80) return 'confidence-high-bg';
  if (confidence >= 60) return 'confidence-medium-bg';
  return 'confidence-low-bg';
}

export const SignalCard: React.FC<SignalCardProps> = ({
  signal,
  onExpand,
  isExpanded = false,
  className,
}) => {
  const isUp = signal.changePercent >= 0;

  return (
    <div
      className={cn(
        'rounded-xl border p-4 transition-all cursor-pointer',
        getConfidenceBgClass(signal.confidence),
        'hover:border-[hsl(var(--primary)/0.4)]',
        className
      )}
      onClick={() => onExpand?.(signal.id)}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{signal.typeEmoji}</span>
          <span className="text-sm font-semibold text-foreground">{signal.typeLabel}</span>
          <span className="text-xs text-muted-foreground">{signal.timestamp}</span>
        </div>
        {/* Confidence bar */}
        <div className="flex items-center gap-1.5">
          <div className="h-2 w-16 rounded-full bg-[hsl(var(--border))] overflow-hidden">
            <div
              className={cn('h-full rounded-full transition-all', getConfidenceClass(signal.confidence))}
              style={{
                width: `${signal.confidence}%`,
                background: signal.confidence >= 80
                  ? 'hsl(var(--color-success))'
                  : signal.confidence >= 60
                    ? 'hsl(var(--color-warning))'
                    : 'hsl(var(--color-danger))',
              }}
            />
          </div>
          <span className={cn('text-xs font-bold', getConfidenceClass(signal.confidence))}>
            {signal.confidence}%
          </span>
        </div>
      </div>

      {/* Stock info */}
      <div className="flex items-center justify-between mb-2">
        <div>
          <span className="text-sm font-mono font-medium text-foreground">{signal.symbol}</span>
          <span className="text-sm text-foreground ml-2">{signal.name}</span>
        </div>
        <span
          className={cn(
            'text-sm font-bold tabular-nums',
            isUp ? 'stock-up' : 'stock-down'
          )}
        >
          {isUp ? '+' : ''}{signal.changePercent.toFixed(1)}%
        </span>
      </div>

      {/* Price & Stop loss */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground mb-2">
        <span>买入: {signal.buyPriceMin}~{signal.buyPriceMax}</span>
        <span>止损: {signal.stopLoss}</span>
        <span>持仓: {signal.holdDays}</span>
      </div>

      {/* Sectors */}
      {signal.sectors && signal.sectors.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {signal.sectors.map((sector) => (
            <Badge key={sector} variant="default" className="text-xs">
              {sector}
            </Badge>
          ))}
        </div>
      )}

      {/* Expanded detail */}
      {isExpanded && (
        <div className="mt-3 pt-3 border-t border-[hsl(var(--border))] animate-slide-in-left">
          {signal.reason && (
            <div className="mb-2">
              <span className="text-xs font-medium text-foreground">买入理由：</span>
              <span className="text-xs text-muted-foreground">{signal.reason}</span>
            </div>
          )}
          {signal.riskWarning && (
            <div>
              <span className="text-xs font-medium text-foreground">风险提示：</span>
              <span className="text-xs text-muted-foreground">{signal.riskWarning}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
