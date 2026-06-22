import React from 'react';
import { cn } from '../../utils/cn';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /**
   * Core variants (recommended):
   * - primary: 主操作按钮（青色渐变）
   * - secondary: 次要操作（卡片风格）
   * - outline: 描边按钮
   * - ghost: 幽灵按钮（无背景）
   * - gradient: 青色→紫色渐变
   * - danger: 危险操作
   *
   * Legacy variants (mapped to core, will be deprecated):
   * - danger-subtle → outline + danger color
   * - settings-primary → primary
   * - settings-secondary → secondary
   * - action-primary → outline
   * - action-secondary → ghost
   * - home-action-ai → outline
   * - home-action-report → ghost
   */
  variant?:
    | 'primary'
    | 'secondary'
    | 'outline'
    | 'ghost'
    | 'gradient'
    | 'danger'
    | 'danger-subtle'
    | 'settings-primary'
    | 'settings-secondary'
    | 'action-primary'
    | 'action-secondary'
    | 'home-action-ai'
    | 'home-action-report';
  size?: 'xsm' | 'sm' | 'md' | 'lg' | 'xl';
  isLoading?: boolean;
  loadingText?: string;
  glow?: boolean;
}

const SIZE_STYLES = {
  xsm: 'h-6 rounded-lg px-2 text-sm',
  sm: 'h-9 rounded-lg px-3 text-sm',
  md: 'h-10 rounded-xl px-4 text-sm',
  lg: 'h-11 rounded-xl px-5 text-sm',
  xl: 'h-12 rounded-xl px-6 text-sm',
} as const;

// Core variant styles
const VARIANT_STYLES: Record<string, string> = {
  primary:
    'border border-cyan/30 bg-gradient-to-r from-cyan-400 to-purple-500 text-white shadow-lg shadow-cyan/20 hover:scale-[1.02] hover:shadow-xl transition-all duration-300',
  secondary:
    'border border-neutral/30 bg-surface text-foreground shadow-soft-card hover:bg-muted/80 hover:border-neutral',
  outline:
    'border border-cyan/25 bg-transparent text-cyan-600 hover:bg-cyan/10',
  ghost:
    'border border-transparent bg-transparent text-muted-foreground hover:bg-muted/80 hover:text-foreground',
  gradient:
    'border border-cyan/20 bg-gradient-to-r from-cyan-400/80 to-purple-500/80 text-white shadow-lg shadow-purple/20 hover:scale-[1.02] hover:shadow-xl transition-all duration-300',
  danger:
    'border border-danger/40 bg-danger text-destructive-foreground shadow-lg shadow-danger/20 hover:bg-danger/90',
  'danger-subtle':
    'border border-danger/60 bg-danger/10 text-danger hover:bg-danger/15',
  'settings-primary':
    'border border-cyan/30 bg-gradient-to-r from-cyan-400 to-purple-500 text-white shadow-lg shadow-cyan/20 hover:scale-[1.02]',
  'settings-secondary':
    'border border-neutral/30 bg-surface text-foreground shadow-soft-card hover:bg-muted/80',
  'action-primary':
    'border border-cyan/25 bg-[var(--home-action-ai-bg)] text-[var(--home-action-ai-text)] hover:bg-[var(--home-action-ai-hover-bg)]',
  'action-secondary':
    'border border-transparent bg-[var(--home-action-report-bg)] text-[var(--home-action-report-text)] hover:bg-[var(--home-action-report-hover-bg)]',
  'home-action-ai':
    'border border-cyan/25 bg-[var(--home-action-ai-bg)] text-[var(--home-action-ai-text)] hover:bg-[var(--home-action-ai-hover-bg)]',
  'home-action-report':
    'border border-transparent bg-[var(--home-action-report-bg)] text-[var(--home-action-report-text)] hover:bg-[var(--home-action-report-hover-bg)]',
};

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  loadingText = '处理中...',
  glow = false,
  className = '',
  disabled,
  type = 'button',
  ...props
}) => {
  return (
    <button
      type={type}
      aria-busy={isLoading || undefined}
      data-variant={variant}
className={cn(
        'inline-flex cursor-pointer items-center justify-center gap-2 font-medium transition-all duration-300',
        'focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-cyan/15 focus-visible:ring-offset-0',
        'disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50',
        'active:scale-[0.98] hover:shadow-md',
        SIZE_STYLES[size],
        VARIANT_STYLES[variant] ?? VARIANT_STYLES.primary,
        glow && 'shadow-glow-cyan',
        className,
      )}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <span className="flex items-center justify-center gap-2">
          <svg
            className="h-4 w-4 animate-spin text-current"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          {loadingText}
        </span>
      ) : (
        children
      )}
    </button>
  );
};
