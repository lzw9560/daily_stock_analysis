import type React from 'react';
import { cn } from '../../utils/cn';

interface CardProps {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  variant?: 'default' | 'bordered' | 'gradient' | 'glass';
  hoverable?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  /** 添加发光效果（hover 时 cyan glow） */
  glow?: boolean;
  onClick?: React.MouseEventHandler<HTMLDivElement>;
}

const paddingStyles: Record<string, string> = {
  none: '',
  sm: 'p-4',
  md: 'p-5',
  lg: 'p-6',
};

/**
 * Card component with terminal-inspired variants, hover/glow effects.
 *
 * Variants:
 * - default: terminal-card (渐变边框 + 内阴影)
 * - bordered: 同 default
 * - gradient: gradient-border-card (外层渐变边框)
 * - glass: glass-card (毛玻璃效果 + 顶部光泽线)
 */
export const Card: React.FC<CardProps> = ({
  title,
  subtitle,
  children,
  className = '',
  style,
  variant = 'default',
  hoverable = false,
  padding = 'md',
  glow = false,
  onClick,
}) => {
  const hoverClasses = hoverable ? 'terminal-card-hover cursor-pointer' : '';
  const glowClasses = glow ? 'transition-shadow duration-300 hover:shadow-glow-cyan' : '';

if (variant === 'gradient') {
    return (
      <div className={cn('gradient-border-card', glowClasses, className)} style={style} onClick={onClick}>
        <div className={cn('gradient-border-card-inner', paddingStyles[padding])}>
          {(title || subtitle) && (
            <div className="mb-3">
              {subtitle ? <span className="label-uppercase text-sm text-muted-foreground">{subtitle}</span> : null}
              {title ? <h3 className="mt-1 text-lg font-semibold text-foreground">{title}</h3> : null}
            </div>
          )}
          {children}
        </div>
      </div>
    );
  }

if (variant === 'glass') {
    return (
      <div
        style={style}
        className={cn('glass-card', hoverClasses, glowClasses, paddingStyles[padding], className)}
        onClick={onClick}
      >
        {(title || subtitle) && (
          <div className="mb-3">
            {subtitle ? <span className="label-uppercase text-sm text-muted-foreground">{subtitle}</span> : null}
            {title ? <h3 className="mt-1 text-lg font-semibold text-foreground">{title}</h3> : null}
          </div>
        )}
        {children}
      </div>
    );
  }

  return (
    <div
      style={style}
      onClick={onClick}
      className={cn(
        'rounded-2xl',
        'terminal-card',
        hoverClasses,
        glowClasses,
        paddingStyles[padding],
        className
      )}
    >
      {(title || subtitle) && (
        <div className="mb-3">
          {subtitle ? <span className="label-uppercase text-sm text-muted-foreground">{subtitle}</span> : null}
          {title ? <h3 className="mt-1 text-lg font-semibold text-foreground">{title}</h3> : null}
        </div>
      )}
      {children}
    </div>
  );
};
