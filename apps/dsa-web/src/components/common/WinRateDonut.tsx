import React from 'react';
import { cn } from '../../utils/cn';

interface WinRateDonutProps {
  winRate: number; // 0-100
  size?: 'sm' | 'md' | 'lg';
  label?: string;
  sublabel?: string;
  className?: string;
}

const SIZES = {
  sm: { outer: 64, stroke: 6, text: 'text-sm', subtext: 'text-[10px]' },
  md: { outer: 96, stroke: 8, text: 'text-lg', subtext: 'text-xs' },
  lg: { outer: 128, stroke: 10, text: 'text-2xl', subtext: 'text-sm' },
};

export const WinRateDonut: React.FC<WinRateDonutProps> = ({
  winRate,
  size = 'md',
  label = '胜率',
  sublabel,
  className,
}) => {
  const { outer, stroke, text: textClass } = SIZES[size];
  const radius = (outer - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clampedRate = Math.max(0, Math.min(100, winRate));
  const offset = circumference - (clampedRate / 100) * circumference;

  const getColor = () => {
    if (clampedRate >= 70) return 'hsl(var(--success))';
    if (clampedRate >= 50) return 'hsl(var(--warning))';
    return 'hsl(var(--danger))';
  };

  const color = getColor();

  return (
    <div className={cn('flex flex-col items-center', className)}>
      <div className="relative inline-flex items-center justify-center">
        <svg width={outer} height={outer} className="-rotate-90">
          {/* Background circle */}
          <circle
            cx={outer / 2}
            cy={outer / 2}
            r={radius}
            fill="none"
            stroke="hsl(var(--muted) / 0.3)"
            strokeWidth={stroke}
          />
          {/* Progress arc */}
          <circle
            cx={outer / 2}
            cy={outer / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 1s ease-in-out' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn('font-bold tabular-nums', textClass)} style={{ color }}>
            {clampedRate}%
          </span>
        </div>
      </div>
      <span className="mt-1 text-xs text-muted-foreground">{label}</span>
      {sublabel && (
        <span className="text-[10px] text-muted-foreground/70">{sublabel}</span>
      )}
    </div>
  );
};

export default WinRateDonut;
