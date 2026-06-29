import type React from 'react';
import { cn } from '../../utils/cn';

type SentimentGaugeProps = {
  value: number; // 0-100
  size?: 'sm' | 'md' | 'lg';
  label?: string;
  phase?: string;
  className?: string;
};

const SIZE_MAP = {
  sm: { w: 80, h: 80, stroke: 6, fontSize: 18 },
  md: { w: 120, h: 120, stroke: 8, fontSize: 28 },
  lg: { w: 160, h: 160, stroke: 10, fontSize: 36 },
};

const PHASE_COLORS: Record<string, string> = {
  '冰点期': 'hsl(var(--color-danger))',
  '修复期': 'hsl(var(--color-warning))',
  '分化期': 'hsl(var(--color-purple))',
  '高潮期': 'hsl(var(--color-success))',
  '退潮期': 'hsl(var(--color-cyan))',
};

function getPhaseColor(phase?: string): string {
  if (!phase) return 'hsl(var(--primary))';
  return PHASE_COLORS[phase] ?? 'hsl(var(--primary))';
}

function getSegmentColor(value: number): string {
  if (value >= 70) return 'hsl(var(--color-success))';
  if (value >= 40) return 'hsl(var(--color-warning))';
  return 'hsl(var(--color-danger))';
}

export const SentimentGauge: React.FC<SentimentGaugeProps> = ({
  value,
  size = 'md',
  label,
  phase,
  className,
}) => {
  const dims = SIZE_MAP[size];
  const radius = (dims.w - dims.stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.min(100, Math.max(0, value));
  const offset = circumference - (progress / 100) * circumference;
  const color = phase ? getPhaseColor(phase) : getSegmentColor(value);

  return (
    <div className={cn('flex flex-col items-center gap-2', className)}>
      <svg
        width={dims.w}
        height={dims.h}
        viewBox={`0 0 ${dims.w} ${dims.h}`}
        className="gauge-ring"
        style={{ filter: `drop-shadow(0 0 8px ${color}44)` }}
      >
        {/* Track */}
        <circle
          cx={dims.w / 2}
          cy={dims.h / 2}
          r={radius}
          fill="none"
          stroke="hsl(var(--border))"
          strokeWidth={dims.stroke}
          strokeLinecap="round"
        />
        {/* Progress */}
        <circle
          cx={dims.w / 2}
          cy={dims.h / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={dims.stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 0.8s ease-out' }}
          transform={`rotate(-90 ${dims.w / 2} ${dims.h / 2})`}
        />
      </svg>
      <div className="absolute text-center" style={{ marginTop: dims.h / 2 - dims.fontSize / 2 }}>
        <span
          className="font-bold tabular-nums"
          style={{ fontSize: dims.fontSize, color }}
        >
          {Math.round(value)}
        </span>
      </div>
      {label && (
        <span className="text-xs text-muted-foreground">{label}</span>
      )}
      {phase && (
        <span
          className="text-xs font-medium px-2 py-0.5 rounded-full"
          style={{ background: `${color}22`, color }}
        >
          {phase}
        </span>
      )}
    </div>
  );
};
