import type React from 'react';
import { cn } from '../../utils/cn';

type BoardLevel = {
  boards: number;
  count: number;
  stocks: string[];
};

type BoardLadderProps = {
  levels: BoardLevel[];
  className?: string;
};

export const BoardLadder: React.FC<BoardLadderProps> = ({
  levels,
  className,
}) => {
  const maxCount = Math.max(...levels.map((l) => l.count), 1);

  return (
    <div className={cn('space-y-1.5', className)}>
      {levels.map((level) => (
        <div key={level.boards} className="flex items-center gap-3">
          <span className="text-xs font-bold text-foreground w-10 text-right tabular-nums">
            {level.boards}板
          </span>
          <div className="flex-1 h-6 rounded-md bg-[hsl(var(--border)/0.3)] overflow-hidden relative">
            <div
              className="h-full rounded-md"
              style={{
                width: `${(level.count / maxCount) * 100}%`,
                background: level.boards >= 4
                  ? 'hsl(var(--color-success))'
                  : level.boards >= 3
                    ? 'hsl(var(--color-warning))'
                    : 'hsl(var(--primary))',
                opacity: 0.7,
                transition: 'width 0.5s ease-out',
              }}
            />
            <span className="absolute inset-0 flex items-center px-2 text-xs font-medium text-foreground">
              {level.count}
            </span>
          </div>
          <span className="text-[10px] text-muted-foreground w-32 truncate">
            {level.stocks.slice(0, 3).join('、')}
            {level.stocks.length > 3 && ` 等${level.stocks.length}只`}
          </span>
        </div>
      ))}
    </div>
  );
};
