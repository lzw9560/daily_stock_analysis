import React from 'react';
import { cn } from '../../utils/cn';

interface StatCardProps {
  /** Metric label, such as "Total Return". */
  label: string;
  /** Metric value, including numbers or percentages. */
  value: React.ReactNode;
  /** Supporting text, such as "Up 5% vs last month". */
  hint?: React.ReactNode;
  /** Optional trailing icon. */
  icon?: React.ReactNode;
  /** Tone variant that affects the border color. */
  tone?: 'default' | 'primary' | 'success' | 'warning' | 'danger';
  /** Optional extra className. */
  className?: string;
}

const toneColors = {
  default: 'text-foreground',
  primary: 'text-cyan-600',
  success: 'text-success',
  warning: 'text-warning',
  danger: 'text-danger',
};

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  hint,
  icon,
  tone = 'default',
  className = '',
}) => {
  const textColor = tone === 'default' ? 'text-foreground' : toneColors[tone];
  const bgColor = tone === 'default' ? 'bg-muted/30' : `${tone}-subtle-bg`;
  
  return (
    <div className={cn('rounded-2xl border p-5 shadow-soft-card hover:shadow-md transition-all duration-200 group/card', bgColor, textColor, className)}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground/80">{label}</p>
          <div className="mt-2 text-2xl font-semibold leading-tight">{value}</div>
          {hint ? <div className="mt-2 text-sm text-muted-foreground/70">{hint}</div> : null}
        </div>
        {icon ? (
          <div className="flex-shrink-0 mt-0.5">
            {React.isValidElement(icon) ? React.cloneElement(icon as React.ReactElement<{ className?: string }>, { className: 'h-4 w-4' }) : (
              <div className="h-4 w-4" style={{ color: textColor }}>
                {icon}
              </div>
            )}
          </div>
        ) : null}
      </div>
      <div className="absolute inset-0 rounded-2xl border border-transparent group-hover/card:border-current/30 group-hover/card:shadow-lg transition-all duration-200 pointer-events-none" /> 
    </div>
  );
};
