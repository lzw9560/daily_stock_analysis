import type React from 'react';
import { cn } from '../../utils/cn';

type InlineAlertVariant = 'info' | 'success' | 'warning' | 'danger';

interface InlineAlertProps {
  title?: string;
  message: React.ReactNode;
  variant?: InlineAlertVariant;
  action?: React.ReactNode;
  className?: string;
}

const variantStyles: Record<InlineAlertVariant, string> = {
  info: 'border-cyan/25 bg-cyan/10 text-cyan-600',
  success: 'border-success/25 bg-success/10 text-success-600',
  warning: 'border-warning/25 bg-warning/10 text-warning-600',
  danger: 'border-danger/25 bg-danger/10 text-danger-600',
};

export const InlineAlert: React.FC<InlineAlertProps> = ({
  title,
  message,
  variant = 'info',
  action,
  className = '',
}) => {
  return (
    <div
      role="alert"
      className={cn('rounded-2xl border px-4 py-3 shadow-soft-card', variantStyles[variant], className)}
    >
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          {title ? <p className="text-sm font-semibold">{title}</p> : null}
          <div className={cn('text-sm', title ? 'mt-1 opacity-90' : 'opacity-90')}>{message}</div>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </div>
  );
};
