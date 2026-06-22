import type React from 'react';
import { ChevronDown } from 'lucide-react';
import { Badge, Card } from '../common';
import { cn } from '../../utils/cn';

type TaskDetailCardShellProps = {
  title: string;
  subtitle?: string;
  badgeLabel?: string;
  badgeVariant?: React.ComponentProps<typeof Badge>['variant'];
  compact?: boolean;
  className?: string;
  children: React.ReactNode;
};

export const TaskDetailCardShell: React.FC<TaskDetailCardShellProps> = ({
  title,
  subtitle,
  badgeLabel,
  badgeVariant = 'default',
  compact = false,
  className = '',
  children,
}) => {
  return (
    <Card
      variant="default"
      padding="sm"
      className={cn(compact ? 'border-border/70 bg-base/60' : 'border-border/70 bg-surface/70', className)}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-foreground">{title}</div>
          {subtitle ? <p className="mt-1 text-xs text-secondary-text">{subtitle}</p> : null}
        </div>
        {badgeLabel ? <Badge variant={badgeVariant}>{badgeLabel}</Badge> : null}
      </div>
      {children}
    </Card>
  );
};

export type TaskDetailDisclosureProps = {
  title: string;
  value?: string;
  children: React.ReactNode;
  className?: string;
  defaultOpen?: boolean;
  ariaLabel?: string;
};

export const TaskDetailDisclosure: React.FC<TaskDetailDisclosureProps> = ({
  title,
  value,
  children,
  className = '',
  defaultOpen = false,
  ariaLabel,
}) => (
  <details className={cn('group/task-detail mt-3 text-xs', className)} open={defaultOpen} aria-label={ariaLabel}>
    <summary className="flex cursor-pointer list-none items-center gap-2 text-muted-text">
      <span>{title}</span>
      {value ? (
        <span className="rounded-full border border-border/50 px-2 py-0.5 text-[11px] text-secondary-text">
          {value}
        </span>
      ) : null}
      <ChevronDown className="h-3.5 w-3.5 transition-transform group-open/task-detail:rotate-180" aria-hidden="true" />
    </summary>
    <div className="mt-2 rounded-xl border border-border/70 bg-base/50 px-3 py-3 text-muted-text">
      {children}
    </div>
  </details>
);

export default TaskDetailCardShell;
