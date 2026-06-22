import type React from 'react';
import { Badge, Button, Card } from '../common';
import type {
  FactorPipelineFactorFamily,
  FactorPipelineMonitoringSummary,
  FactorPipelineSummary,
  FactorPipelineTrainingSummary,
} from '../../types/screening';
import { TaskDetailDisclosure } from '../tasks/TaskDetailCardShell';

interface FactorPipelineSummaryCardProps {
  title: string;
  subtitle?: string;
  factorPipeline: FactorPipelineSummary | null;
  recordId?: number | null;
  onOpen?: () => void;
  onRerun?: () => void;
  loading?: boolean;
  compact?: boolean;
}

const formatPercent = (value: unknown): string | null => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return null;
  }
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
};

const asDisplaySummary = (factorPipeline: FactorPipelineSummary | null): FactorPipelineSummary =>
  factorPipeline || {};

const formatTrainingStatus = (training: FactorPipelineTrainingSummary | undefined): string =>
  training && typeof training.status === 'string' ? training.status : '—';

const renderJson = (value: FactorPipelineTrainingSummary | FactorPipelineMonitoringSummary | FactorPipelineFactorFamily | undefined): string =>
  JSON.stringify(value ?? {}, null, 2);

export const FactorPipelineSummaryCard: React.FC<FactorPipelineSummaryCardProps> = ({
  title,
  subtitle,
  factorPipeline,
  recordId,
  onOpen,
  onRerun,
  loading = false,
  compact = false,
}) => {
  const pipeline = asDisplaySummary(factorPipeline);
  const factorEnabled = Boolean(pipeline.factorPipelineEnabled);
  const status = typeof pipeline.status === 'string' ? pipeline.status : '未加载';
  const backend = typeof pipeline.backend === 'string' ? pipeline.backend : '—';
  const candidateCount = typeof pipeline.candidateCount === 'number' ? pipeline.candidateCount : null;
  const training = pipeline.training || {};
  const monitoring = pipeline.monitoring || {};
  const factorFamily = pipeline.factorFamily || {};
  const topCandidates = Array.isArray(pipeline.topCandidates) ? pipeline.topCandidates.length : null;
  const topFeatures = Array.isArray(pipeline.topCandidates) ? pipeline.topCandidates.slice(0, compact ? 2 : 3) : [];
  const icText = formatPercent(monitoring.ic);
  const irValue = typeof monitoring.ir === 'number' ? monitoring.ir.toFixed(2) : null;
  const decayValue = typeof monitoring.decay === 'number' ? monitoring.decay.toFixed(2) : null;
  const latestRecordId = pipeline.latestRecordId ?? null;
  const latestScreeningDate = pipeline.latestScreeningDate || null;

  return (
    <Card variant="default" padding="md" className={compact ? 'space-y-3' : 'space-y-4'}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-foreground">{title}</div>
          {subtitle ? <p className="mt-1 text-xs text-secondary-text">{subtitle}</p> : null}
        </div>
        <Badge variant={factorEnabled ? 'success' : 'warning'}>{factorEnabled ? '已启用' : '未启用'}</Badge>
      </div>

      <div className={compact ? 'grid gap-2 sm:grid-cols-2 xl:grid-cols-4' : 'grid gap-3 sm:grid-cols-2 xl:grid-cols-4'}>
        <div className="rounded-xl border border-border/70 bg-surface/70 p-3">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-text">状态</div>
          <div className="mt-1 text-sm font-medium text-foreground">{status}</div>
        </div>
        <div className="rounded-xl border border-border/70 bg-surface/70 p-3">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-text">后端</div>
          <div className="mt-1 text-sm font-medium text-foreground">{backend}</div>
        </div>
        <div className="rounded-xl border border-border/70 bg-surface/70 p-3">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-text">候选数</div>
          <div className="mt-1 text-sm font-medium text-foreground">{candidateCount ?? '—'}</div>
        </div>
        <div className="rounded-xl border border-border/70 bg-surface/70 p-3">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-text">Top 候选</div>
          <div className="mt-1 text-sm font-medium text-foreground">{topCandidates ?? '—'}</div>
        </div>
      </div>

      <div className={compact ? 'grid gap-2 lg:grid-cols-3' : 'grid gap-3 lg:grid-cols-3'}>
        <div className="rounded-xl border border-border/70 bg-surface/70 p-3">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-text">训练</div>
          <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-secondary-text">{renderJson(training)}</pre>
        </div>
        <div className="rounded-xl border border-border/70 bg-surface/70 p-3">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-text">监控</div>
          <div className="mt-2 space-y-1 text-xs text-secondary-text">
            <div className="flex items-center justify-between gap-2"><span>IC</span><span className="font-mono">{icText || '—'}</span></div>
            <div className="flex items-center justify-between gap-2"><span>IR</span><span className="font-mono">{irValue || '—'}</span></div>
            <div className="flex items-center justify-between gap-2"><span>衰减</span><span className="font-mono">{decayValue || '—'}</span></div>
          </div>
        </div>
        <div className="rounded-xl border border-border/70 bg-surface/70 p-3">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-text">因子族</div>
          <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-secondary-text">{renderJson(factorFamily)}</pre>
        </div>
      </div>

      <div className="rounded-xl border border-border/70 bg-surface/70 p-3 text-xs text-secondary-text">
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          <span>训练状态：{formatTrainingStatus(training)}</span>
          <span>最新记录：{latestRecordId != null ? `#${latestRecordId}` : '—'}{latestScreeningDate ? ` · ${latestScreeningDate}` : ''}</span>
        </div>
        <TaskDetailDisclosure title="Top Candidates" value={topCandidates != null ? String(topCandidates) : undefined} className="mt-3">
          {topFeatures.length > 0 ? (
            <div className="space-y-1">
              {topFeatures.map((feature, index) => (
                <div key={`${String(feature?.code || feature?.name || index)}-${index}`} className="flex items-center justify-between gap-2 rounded-md bg-base/70 px-2 py-1">
                  <span className="truncate text-[11px] text-secondary-text">{String(feature?.code || feature?.name || `candidate-${index + 1}`)}</span>
                  <span className="font-mono text-[11px] text-secondary-text">{typeof feature?.factor_score === 'number' ? feature.factor_score.toFixed(4) : '—'}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-secondary-text">暂无 Top 候选</div>
          )}
        </TaskDetailDisclosure>
      </div>

      {(onOpen || onRerun) ? (
        <div className="flex flex-wrap gap-2">
          {onOpen ? (
            <Button size="sm" variant="secondary" onClick={onOpen} disabled={recordId == null}>
              查看结果
            </Button>
          ) : null}
          {onRerun ? (
            <Button size="sm" variant="outline" isLoading={loading} loadingText="重跑中..." onClick={onRerun} disabled={recordId == null}>
              重新触发
            </Button>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
};

export default FactorPipelineSummaryCard;
