import type React from 'react';
import { useMemo } from 'react';
import { cn } from '../../utils/cn';

type SparklineProps = {
  data: number[];
  width?: number;
  height?: number;
  color?: 'up' | 'down' | 'neutral';
  className?: string;
};

export const Sparkline: React.FC<SparklineProps> = ({
  data,
  width = 80,
  height = 24,
  color = 'neutral',
  className,
}) => {
  const path = useMemo(() => {
    if (data.length < 2) return '';
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const stepX = width / (data.length - 1);

    const points = data
      .map((val, i) => {
        const x = i * stepX;
        const y = height - ((val - min) / range) * (height - 2) - 1;
        return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
      })
      .join(' ');

    return points;
  }, [data, width, height]);

  const colorMap = {
    up: 'hsl(var(--color-success))',
    down: 'hsl(var(--color-danger))',
    neutral: 'hsl(var(--muted-foreground))',
  };

  const stroke = colorMap[color];
  const lastVal = data[data.length - 1];
  const firstVal = data[0];

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn('overflow-visible', className)}
    >
      {lastVal > firstVal && (
        <linearGradient id={`spark-grad-up-${data.length}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity={0.2} />
          <stop offset="100%" stopColor={stroke} stopOpacity={0} />
        </linearGradient>
      )}
      {lastVal <= firstVal && (
        <linearGradient id={`spark-grad-down-${data.length}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={colorMap.down} stopOpacity={0.2} />
          <stop offset="100%" stopColor={colorMap.down} stopOpacity={0} />
        </linearGradient>
      )}
      <path
        d={path}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {lastVal > firstVal && (
        <path
          d={`${path} L ${width} ${height} L 0 ${height} Z`}
          fill={`url(#spark-grad-up-${data.length})`}
        />
      )}
      {lastVal <= firstVal && (
        <path
          d={`${path} L ${width} ${height} L 0 ${height} Z`}
          fill={`url(#spark-grad-down-${data.length})`}
        />
      )}
    </svg>
  );
};
