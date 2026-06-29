import { useState } from 'react';
import {
  TrendingUp, TrendingDown, Activity, Target,
  RefreshCw, Edit3, Trash2, Clock,
  CheckCircle2, XCircle, BarChart3, Eye, Compass,
} from 'lucide-react';
import { Button } from '@/components/common/Button';
import { Badge } from '@/components/common/Badge';
import { EmptyState } from '@/components/common/EmptyState';
import type { RecommendationRecord, CommonalityGroup } from '@/api/recommendationTracking';

interface BoardViewProps {
  records: RecommendationRecord[];
  loading: boolean;
  commonalityGroups: CommonalityGroup[];
  activeTagFilter: string | null;
  onUpdatePrice: (record: RecommendationRecord, price: number) => void;
  onClose: (record: RecommendationRecord) => void;
  onEdit: (record: RecommendationRecord) => void;
  onDelete: (record: RecommendationRecord) => void;
  onDetail: (record: RecommendationRecord) => void;
}

const STATUS_COLUMNS = [
  { key: 'active', label: '持仓中', icon: Clock, color: 'border-amber-500/40 bg-amber-500/5' },
  { key: 'closed', label: '已平仓', icon: CheckCircle2, color: 'border-emerald-500/40 bg-emerald-500/5' },
  { key: 'expired', label: '已过期', icon: XCircle, color: 'border-slate-500/40 bg-slate-500/5' },
] as const;

const signalIcon = (signal: string) => {
  if (signal === 'buy')
    return <TrendingUp className="h-4 w-4 text-emerald-400" />;
  if (signal === 'sell')
    return <TrendingDown className="h-4 w-4 text-red-400" />;
  return <Activity className="h-4 w-4 text-amber-400" />;
};

const signalBg = (signal: string) => {
  if (signal === 'buy') return 'bg-emerald-500/10 border-emerald-500/30';
  if (signal === 'sell') return 'bg-red-500/10 border-red-500/30';
  return 'bg-amber-500/10 border-amber-500/30';
};

function sourceLabel(source: string) {
  const map: Record<string, string> = {
    analysis: '常规分析',
    deep_analysis: '深度分析',
    seal_plate: '打板',
    comprehensive: '综合推荐',
    manual: '手动录入',
  };
  return map[source] || source;
}

function strategyLabel(pattern: string): string {
  if (!pattern) return '-';
  const map: Record<string, string> = {
    '首板': '首板挖掘',
    '连板': '连板接力',
    '低吸': '低吸龙头',
    'N字': 'N字反击',
    '反包': '反包战法',
    '突破': '平台突破',
    '趋势': '趋势跟随',
  };
  return pattern.split('/').map(s => map[s.trim()] || s.trim()).join(' / ');
}

/** 获取某条记录对应的标签（基于共同点分析匹配） */
function getRecordTags(
  record: RecommendationRecord,
  groups: CommonalityGroup[],
) {
  const tags: { key: string; label: string; category: string }[] = [];

  for (const group of groups) {
    for (const tag of group.tags) {
      let match = false;
      switch (group.category) {
        case 'board': {
          const code = String(record.code).padStart(6, '0');
          if (tag.value === '科创板' && code.startsWith('688')) match = true;
          else if (tag.value === '创业板' && (code.startsWith('300') || code.startsWith('301'))) match = true;
          else if (tag.value === '沪市主板' && code.startsWith('60')) match = true;
          else if (tag.value === '深市主板' && code.startsWith('00')) match = true;
          break;
        }
        case 'signal':
          match = record.signal === tag.value;
          break;
        case 'source':
          match = record.source === tag.value;
          break;
        case 'price_range': {
          const p = record.recommendationPrice || 0;
          if (tag.value === '低价股(≤10元)' && p <= 10) match = true;
          else if (tag.value === '中价股(10-30元)' && p > 10 && p <= 30) match = true;
          else if (tag.value === '高价股(30-100元)' && p > 30 && p <= 100) match = true;
          else if (tag.value === '超高价股(>100元)' && p > 100) match = true;
          break;
        }
        default:
          break;
      }
      if (match) {
        tags.push({ key: tag.key, label: tag.label, category: group.category });
      }
    }
  }
  return tags;
}

const TAG_COLOR_MAP: Record<string, string> = {
  board: 'border-blue-500/30 bg-blue-500/10 text-blue-400',
  signal: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
  source: 'border-purple-500/30 bg-purple-500/10 text-purple-400',
  price_range: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
};

export function BoardView({
  records,
  loading,
  commonalityGroups,
  activeTagFilter,
  onUpdatePrice,
  onClose,
  onEdit,
  onDelete,
  onDetail,
}: BoardViewProps) {
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {STATUS_COLUMNS.map((col) => (
          <div key={col.key} className={`rounded-xl border ${col.color} p-3 min-h-[200px]`}>
            <div className="flex items-center gap-2 mb-3">
              <col.icon className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium text-foreground">{col.label}</span>
            </div>
            <div className="space-y-2">
              {Array.from({ length: 2 }).map((_, i) => (
                <div key={i} className="animate-pulse h-28 bg-hover rounded-lg" />
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <EmptyState
        icon={<BarChart3 className="h-8 w-8 text-muted-foreground" />}
        title="暂无推荐记录"
        description="点击「新建」添加第一条推荐追踪记录"
      />
    );
  }

  // 按状态分组
  const grouped = {
    active: records.filter((r) => r.status === 'active'),
    closed: records.filter((r) => r.status === 'closed'),
    expired: records.filter((r) => r.status === 'expired'),
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {STATUS_COLUMNS.map((col) => {
        const items = grouped[col.key];
        return (
          <div key={col.key}>
            {/* 列头 */}
            <div
              className={`flex items-center justify-between mb-3 px-1`}
            >
              <div className="flex items-center gap-2">
                <col.icon className={`h-4 w-4 ${
                  col.key === 'active' ? 'text-amber-400' :
                  col.key === 'closed' ? 'text-emerald-400' : 'text-muted-foreground'
                }`} />
                <span className="text-sm font-semibold text-foreground">
                  {col.label}
                </span>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {items.length}
                </span>
              </div>
            </div>

            {/* 卡片列表 */}
            <div className={`rounded-xl border ${col.color} p-3 min-h-[200px]`}>
              {items.length === 0 ? (
                <div className="flex items-center justify-center h-32 text-xs text-muted-foreground">
                  暂无记录
                </div>
              ) : (
                <div className="space-y-2">
                  {items.map((r) => {
                    const tags = getRecordTags(r, commonalityGroups);
                    const isConfirming = deleteConfirmId === r.id;

                    return (
                      <div
                        key={r.id}
                        onClick={() => onDetail(r)}
                        className={`rounded-lg border p-3 transition-all hover:shadow-sm cursor-pointer
                          ${signalBg(r.signal)}
                          ${activeTagFilter ? 'opacity-100 ring-1 ring-[hsl(var(--primary))]' : ''}
                        `}
                      >
                        {/* 头部：代码 + 信号 */}
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-1.5">
                            <span className="text-sm font-bold text-foreground">
                              {r.code}
                            </span>
                            {signalIcon(r.signal)}
                          </div>
                          <Badge size="sm" variant="history">
                            {sourceLabel(r.source)}
                          </Badge>
                        </div>

                        {/* 策略战法 */}
                        {r.strategyPattern && (
                          <div className="mb-2">
                            <span className="inline-flex items-center gap-1 text-[10px] text-[hsl(var(--primary))] bg-[hsl(var(--primary))]/8 px-1.5 py-0.5 rounded font-medium">
                              <Compass className="h-2.5 w-2.5" />
                              {strategyLabel(r.strategyPattern)}
                            </span>
                          </div>
                        )}

                        {/* 价格信息 */}
                        <div className="space-y-1 mb-2">
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground">推荐价</span>
                            <span className="text-foreground font-medium">
                              {r.recommendationPrice}
                            </span>
                          </div>
                          {r.currentPrice != null && (
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground">现价</span>
                              <span
                                className={`font-medium ${
                                  (r.priceDeviationPct ?? 0) >= 0
                                    ? 'text-emerald-400'
                                    : 'text-red-400'
                                }`}
                              >
                                {r.currentPrice}
                              </span>
                            </div>
                          )}
                          {r.priceDeviationPct != null && (
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground">偏差</span>
                              <span
                                className={`font-semibold ${
                                  r.priceDeviationPct >= 0
                                    ? 'text-emerald-400'
                                    : 'text-red-400'
                                }`}
                              >
                                {r.priceDeviationPct >= 0 ? '+' : ''}
                                {r.priceDeviationPct}%
                              </span>
                            </div>
                          )}
                          {r.status === 'closed' && r.profitLossPct != null && (
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground">盈亏</span>
                              <span
                                className={`font-semibold ${
                                  r.profitLossPct >= 0
                                    ? 'text-emerald-400'
                                    : 'text-red-400'
                                }`}
                              >
                                {r.profitLossPct >= 0 ? '+' : ''}
                                {r.profitLossPct}%
                              </span>
                            </div>
                          )}
                        </div>

                        {/* 交易日期 */}
                        <div className="text-xs text-muted-foreground mb-2">
                          {r.tradeDate}
                        </div>

                        {/* 共同点标签 */}
                        {tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-2">
                            {tags.slice(0, 3).map((tag) => (
                              <span
                                key={tag.key}
                                className={`inline-block px-1.5 py-0.5 rounded text-[10px] border
                                  ${TAG_COLOR_MAP[tag.category] || 'border-border bg-hover text-muted-foreground'}
                                  ${activeTagFilter === tag.key ? 'ring-1 ring-[hsl(var(--primary))]' : ''}
                                `}
                              >
                                {tag.label}
                              </span>
                            ))}
                            {tags.length > 3 && (
                              <span className="text-[10px] text-muted-foreground">
                                +{tags.length - 3}
                              </span>
                            )}
                          </div>
                        )}

                        {/* 操作按钮 */}
                        <div className="flex items-center gap-1 pt-2 border-t border-border/30" onClick={(e) => e.stopPropagation()}>
                          {r.status === 'active' && (
                            <>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 px-1.5 text-xs"
                                title="更新现价"
                                onClick={() => {
                                  const price = prompt(
                                    '输入当前价格:',
                                    r.currentPrice
                                      ? String(r.currentPrice)
                                      : '',
                                  );
                                  if (price && !isNaN(parseFloat(price))) {
                                    onUpdatePrice(r, parseFloat(price));
                                  }
                                }}
                              >
                                <RefreshCw className="h-3 w-3" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 px-1.5 text-xs"
                                title="平仓"
                                onClick={() => onClose(r)}
                              >
                                <Target className="h-3 w-3" />
                              </Button>
                            </>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-1.5 text-xs"
                            title="查看详情"
                            onClick={() => onDetail(r)}
                          >
                            <Eye className="h-3 w-3" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-1.5 text-xs"
                            title="编辑"
                            onClick={() => onEdit(r)}
                          >
                            <Edit3 className="h-3 w-3" />
                          </Button>
                          {isConfirming ? (
                            <Button
                              variant="danger"
                              size="sm"
                              className="h-7 px-2 text-xs"
                              onClick={() => {
                                onDelete(r);
                                setDeleteConfirmId(null);
                              }}
                            >
                              确认
                            </Button>
                          ) : (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-1.5 text-xs text-muted-foreground hover:text-red-400"
                              title="删除"
                              onClick={() => setDeleteConfirmId(r.id)}
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
