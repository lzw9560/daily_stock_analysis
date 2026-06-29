import { useState } from 'react';
import { Tags, ChevronDown, ChevronUp, XCircle } from 'lucide-react';
import type { CommonalityGroup } from '@/api/recommendationTracking';

interface CommonalityTagsProps {
  groups: CommonalityGroup[];
  totalAnalyzed: number;
  activeFilter: string | null;
  onFilterChange: (key: string | null) => void;
  loading?: boolean;
}

const CATEGORY_COLORS: Record<string, string> = {
  board: 'border-blue-500/30 bg-blue-500/10 text-blue-400',
  signal: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
  source: 'border-purple-500/30 bg-purple-500/10 text-purple-400',
  price_range: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
  time_window: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-400',
  keyword: 'border-rose-500/30 bg-rose-500/10 text-rose-400',
};

const CATEGORY_ICONS: Record<string, string> = {
  board: '📊',
  signal: '📈',
  source: '🔍',
  price_range: '💰',
  time_window: '📅',
  keyword: '🔑',
};

export function CommonalityTags({
  groups,
  totalAnalyzed,
  activeFilter,
  onFilterChange,
  loading,
}: CommonalityTagsProps) {
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(
    new Set()
  );

  const toggleCategory = (category: string) => {
    setCollapsedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  if (loading) {
    return (
      <div className="animate-pulse space-y-2">
        <div className="h-5 w-48 bg-hover rounded" />
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-6 w-20 bg-hover rounded-full" />
          ))}
        </div>
      </div>
    );
  }

  if (!groups.length) return null;

  return (
    <div className="space-y-4">
      {/* 头部 */}
      <div className="flex items-center gap-2">
        <Tags className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium text-foreground">
          推荐共同点分析
        </span>
        <span className="text-xs text-muted-foreground">
          ({totalAnalyzed}条记录)
        </span>
        {activeFilter && (
          <button
            type="button"
            onClick={() => onFilterChange(null)}
            className="flex items-center gap-1 text-xs text-[hsl(var(--primary))] hover:underline ml-2"
          >
            <XCircle className="h-3 w-3" />
            清除筛选
          </button>
        )}
      </div>

      {/* 标签分组 */}
      <div className="space-y-3">
        {groups.map((group) => {
          const isCollapsed = collapsedCategories.has(group.category);
          const visibleTags = isCollapsed
            ? group.tags.slice(0, 4)
            : group.tags;

          return (
            <div key={group.category}>
              {/* 分组标题 */}
              <button
                type="button"
                onClick={() => toggleCategory(group.category)}
                className="flex items-center gap-1.5 mb-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                <span>{CATEGORY_ICONS[group.category] || '🏷️'}</span>
                <span className="font-medium">{group.categoryLabel}</span>
                {group.tags.length > 4 && (
                  <>
                    {isCollapsed ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronUp className="h-3 w-3" />
                    )}
                    <span className="text-muted-foreground/60">
                      ({group.tags.length})
                    </span>
                  </>
                )}
              </button>

              {/* 标签列表 */}
              <div className="flex flex-wrap gap-1.5">
                {visibleTags.map((tag) => {
                  const isActive = activeFilter === tag.key;
                  const colorClass =
                    CATEGORY_COLORS[tag.category] ||
                    'border-border bg-hover text-muted-foreground';
                  return (
                    <button
                      key={tag.key}
                      type="button"
                      onClick={() =>
                        onFilterChange(isActive ? null : tag.key)
                      }
                      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs
                        border transition-all duration-150 cursor-pointer
                        ${colorClass}
                        ${
                          isActive
                            ? 'ring-2 ring-[hsl(var(--primary))] scale-105'
                            : 'hover:scale-105'
                        }
                      `}
                    >
                      <span className="max-w-[120px] truncate">
                        {tag.label}
                      </span>
                      <span
                        className={`tabular-nums ${
                          isActive ? 'opacity-100' : 'opacity-60'
                        }`}
                      >
                        {tag.count}
                      </span>
                    </button>
                  );
                })}

                {/* 展开/收起按钮 */}
                {isCollapsed && group.tags.length > 4 && (
                  <button
                    type="button"
                    onClick={() => toggleCategory(group.category)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs
                      border border-border bg-hover text-muted-foreground hover:text-foreground transition-colors"
                  >
                    +{group.tags.length - 4} 更多
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
