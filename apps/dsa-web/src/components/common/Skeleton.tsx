import React from 'react';
import { cn } from '../../utils/cn';

interface SkeletonProps {
  className?: string;
  /** 预设形状 */
  variant?: 'text' | 'circular' | 'rectangular';
  /** 自定义宽高 */
  width?: string | number;
  height?: string | number;
}

const variantStyles = {
  text: 'h-4 w-full rounded-md',
  circular: 'rounded-full',
  rectangular: 'rounded-lg',
} as const;

/**
 * 骨架屏组件，用于加载占位。
 *
 * @example
 * <Skeleton variant="text" className="w-48" />
 * <Skeleton variant="circular" width={40} height={40} />
 * <Skeleton variant="rectangular" height={200} />
 */
export const Skeleton: React.FC<SkeletonProps> = ({
  className,
  variant = 'text',
  width,
  height,
}) => {
  return (
    <div
      aria-hidden="true"
      className={cn('skeleton', variantStyles[variant], className)}
      style={{
        width: width ?? undefined,
        height: height ?? undefined,
      }}
    />
  );
};
