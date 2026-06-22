import { cn } from '@/utils/cn';

interface StockNameDisplayProps {
  /** 股票代码，如 "600519" */
  code: string;
  /** 股票名称 */
  name: string;
  /** 额外 class */
  className?: string;
  /** 代码的 class */
  codeClassName?: string;
  /** 名称的 class */
  nameClassName?: string;
}

/**
 * 统一显示股票代码+名称，名称带背景反色提升可读性
 */
export function StockNameDisplay({
  code,
  name,
  className = '',
  codeClassName = '',
  nameClassName = '',
}: StockNameDisplayProps) {
  return (
    <span className={cn('inline-flex items-center gap-1.5', className)}>
      <span
        className={cn(
          'rounded px-1.5 py-0.5 bg-primary/10 text-primary font-semibold',
          nameClassName,
        )}
      >
        {name}
      </span>
      <span
        className={cn(
          'font-mono text-xs text-muted-foreground',
          codeClassName,
        )}
      >
        {code}
      </span>
    </span>
  );
}
