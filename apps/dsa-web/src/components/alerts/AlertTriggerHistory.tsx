import type React from 'react';
import { Activity } from 'lucide-react';
import { Badge, Card, EmptyState, Loading } from '../common';
import type { AlertTriggerItem } from '../../types/alerts';
import { formatDateTime } from '../../utils/format';

const statusLabel: Record<string, string> = {
  triggered: '已触发',
  skipped: '已跳过',
  degraded: '降级',
  failed: '失败',
};

function statusVariant(status: string): 'success' | 'warning' | 'danger' | 'default' {
  if (status === 'triggered') return 'success';
  if (status === 'skipped' || status === 'degraded') return 'warning';
  if (status === 'failed') return 'danger';
  return 'default';
}

function formatNullable(value?: string | number | null): string {
  if (value === null || value === undefined || value === '') return '--';
  return String(value);
}

interface AlertTriggerHistoryProps {
  triggers: AlertTriggerItem[];
  isLoading?: boolean;
}

export const AlertTriggerHistory: React.FC<AlertTriggerHistoryProps> = ({ triggers, isLoading = false }) => {
  return (
    <Card title="触发历史" subtitle="评估记录" variant="bordered" padding="md">
      {isLoading ? <Loading label="正在加载触发历史" /> : null}
      {!isLoading && triggers.length === 0 ? (
        <EmptyState
          icon={<Activity className="h-6 w-6" />}
          title="暂无触发历史"
          description="后台评估会记录 triggered、skipped、degraded 和 failed 状态；正常未触发不会写入历史。"
        />
      ) : null}
      {!isLoading && triggers.length > 0 ? (
        <div className="relative">
          {/* 时间线视图 */}
          <div className="relative pl-6 space-y-0">
            {/* Vertical line */}
            <div className="absolute left-[11px] top-3 bottom-3 w-px bg-border/60" />
            {triggers.map((trigger) => (
              <div key={trigger.id} className="relative pb-4 last:pb-0">
                {/* Timeline dot */}
                <div
                  className={`absolute -left-[19px] top-2 w-3 h-3 rounded-full border-2 border-background ${
                    trigger.status === 'triggered'
                      ? 'bg-success'
                      : trigger.status === 'failed'
                      ? 'bg-danger'
                      : trigger.status === 'degraded'
                      ? 'bg-warning'
                      : 'bg-muted-foreground'
                  }`}
                />

                {/* Card-like timeline item */}
                <div className="rounded-lg border border-border/40 bg-card/60 p-3 hover:bg-card/80 transition-colors">
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-2">
                      <Badge variant={statusVariant(trigger.status)}>
                        {statusLabel[trigger.status] ?? trigger.status}
                      </Badge>
                      <span className="font-mono text-sm font-medium">{trigger.target}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {formatDateTime(trigger.dataTimestamp ?? trigger.triggeredAt)}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                    <div>
                      <span className="text-muted-foreground">观察值</span>
                      <p className="font-mono">{formatNullable(trigger.observedValue)}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">阈值</span>
                      <p className="font-mono">{formatNullable(trigger.threshold)}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">数据源</span>
                      <p>{formatNullable(trigger.dataSource)}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">原因</span>
                      <p className="truncate">{trigger.reason || trigger.diagnostics || '--'}</p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
          {/* Show count */}
          <p className="mt-3 text-center text-xs text-muted-foreground">
            共 {triggers.length} 条触发记录
          </p>
        </div>
      ) : null}
    </Card>
  );
};
