import { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp, TrendingDown, Activity, Target, Percent,
  Plus, Filter, XCircle, CheckCircle2, Loader2,
  Trash2, RefreshCw, BarChart3, Brain, Edit3,
  AlertTriangle, Clock, LayoutList, Columns3,
  Eye, Zap, Shield, Compass, Thermometer,
} from 'lucide-react';
import { Button } from '@/components/common/Button';
import { Card } from '@/components/common/Card';
import { Input } from '@/components/common/Input';
import { Badge } from '@/components/common/Badge';
import { EmptyState } from '@/components/common/EmptyState';
import { PageHeader } from '@/components/common/PageHeader';
import { Select } from '@/components/common/Select';
import { Pagination } from '@/components/common/Pagination';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { recommendationTrackingApi } from '@/api/recommendationTracking';
import type {
  RecommendationRecord,
  RecommendationStats,
  SummaryResponse,
  CommonalityGroup,
} from '@/api/recommendationTracking';
import { CommonalityTags } from '@/components/recommendation/CommonalityTags';
import { BoardView } from '@/components/recommendation/BoardView';

// ── 信号标签 ────────────────────────────────────────────────────────────────

const SIGNAL_OPTIONS = [
  { value: '', label: '全部方向' },
  { value: 'buy', label: '看多' },
  { value: 'sell', label: '看空' },
  { value: 'hold', label: '观望' },
];

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'active', label: '持仓中' },
  { value: 'closed', label: '已平仓' },
  { value: 'expired', label: '已过期' },
];

const SOURCE_OPTIONS = [
  { value: '', label: '全部来源' },
  { value: 'analysis', label: '常规分析' },
  { value: 'deep_analysis', label: '深度分析' },
  { value: 'seal_plate', label: '打板' },
  { value: 'comprehensive', label: '综合推荐' },
  { value: 'manual', label: '手动录入' },
];

function signalBadge(signal: string) {
  if (signal === 'buy') return <Badge variant="success"><TrendingUp className="h-3 w-3 mr-1" />看多</Badge>;
  if (signal === 'sell') return <Badge variant="danger"><TrendingDown className="h-3 w-3 mr-1" />看空</Badge>;
  return <Badge variant="warning"><Activity className="h-3 w-3 mr-1" />观望</Badge>;
}

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

function entryMethodLabel(method: string): string {
  const map: Record<string, string> = {
    seal_plate: '打板',
    low_suck: '低吸',
    breakout: '突破',
    market: '市价',
    limit_order: '限价',
  };
  return map[method] || method;
}

function sentimentLabel(phase: string): string {
  const map: Record<string, string> = {
    '冰点': '❄️ 冰点',
    '修复': '🌤️ 修复',
    '分化': '⚡ 分化',
    '高潮': '🔥 高潮',
    '退潮': '🌊 退潮',
  };
  return map[phase] || phase;
}

function signalTypeLabel(st: string): string {
  const map: Record<string, string> = {
    technical: '技术面',
    fundamental: '基本面',
    sentiment: '情绪面',
    mixed: '多维度',
  };
  return map[st] || st;
}

// ── 统计卡片 ────────────────────────────────────────────────────────────────

function StatsDashboard({ stats, loading }: { stats: RecommendationStats | null; loading: boolean }) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i} className="animate-pulse h-24"><div /></Card>
        ))}
      </div>
    );
  }
  if (!stats) return null;

  const cards: { label: string; value: string; icon: React.ReactNode; color: string }[] = [
    { label: '总记录', value: String(stats.totalRecords), icon: <BarChart3 className="h-5 w-5" />, color: 'text-blue-400' },
    { label: '持仓中', value: String(stats.activeCount), icon: <Clock className="h-5 w-5" />, color: 'text-amber-400' },
    { label: '已平仓', value: String(stats.closedCount), icon: <CheckCircle2 className="h-5 w-5" />, color: 'text-emerald-400' },
    { label: '胜率', value: `${stats.winRate}%`, icon: <Target className="h-5 w-5" />, color: stats.winRate >= 50 ? 'text-emerald-400' : 'text-red-400' },
    { label: '盈亏比', value: String(stats.profitFactor), icon: <Percent className="h-5 w-5" />, color: stats.profitFactor >= 1.5 ? 'text-emerald-400' : 'text-amber-400' },
    { label: '累计盈亏', value: `${stats.totalPlPct >= 0 ? '+' : ''}${stats.totalPlPct}%`, icon: <Activity className="h-5 w-5" />, color: stats.totalPlPct >= 0 ? 'text-emerald-400' : 'text-red-400' },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
      {cards.map((c, i) => (
        <Card key={i} className="py-3 text-center">
          <div className={`flex justify-center mb-1 ${c.color}`}>{c.icon}</div>
          <p className="text-xs text-muted-foreground">{c.label}</p>
          <p className={`text-lg font-bold ${c.color}`}>{c.value}</p>
        </Card>
      ))}
    </div>
  );
}

// ── 详细统计面板 ────────────────────────────────────────────────────────────

function DetailStats({ stats, loading }: { stats: RecommendationStats | null; loading: boolean }) {
  const [expanded, setExpanded] = useState(false);
  if (loading || !stats) return null;

  return (
    <div className="mb-6">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm text-secondary-text hover:text-foreground transition-colors mb-2"
      >
        <BarChart3 className="h-4 w-4" />
        详细数据
        <span className="text-xs text-muted-foreground">{expanded ? '收起' : '展开'}</span>
      </button>

      {expanded && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* 盈亏分布 */}
          <Card className="p-4">
            <h4 className="text-sm font-semibold text-foreground mb-3">盈亏分布</h4>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-muted-foreground">胜场/负场</span>
                <span><span className="text-emerald-400">{stats.winCount}胜</span> / <span className="text-red-400">{stats.lossCount}负</span></span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">平均盈利</span>
                <span className="text-emerald-400">+{stats.avgWinPlPct}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">平均亏损</span>
                <span className="text-red-400">{stats.avgLossPlPct}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">最大盈利</span>
                <span className="text-emerald-400">+{stats.maxWinPct}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">最大亏损</span>
                <span className="text-red-400">{stats.maxLossPct}%</span>
              </div>
            </div>
          </Card>

          {/* 按方向 */}
          <Card className="p-4">
            <h4 className="text-sm font-semibold text-foreground mb-3">按方向统计</h4>
            <div className="space-y-2 text-xs">
              {Object.entries(stats.bySignal || {}).map(([sig, d]) => d.total > 0 && (
                <div key={sig} className="flex justify-between items-center">
                  <span className="text-muted-foreground">
                    {sig === 'buy' ? '📈 看多' : sig === 'sell' ? '📉 看空' : '➡️ 观望'}
                  </span>
                  <span>
                    {d.total}笔 | 胜率 <span className={d.winRate >= 50 ? 'text-emerald-400' : 'text-red-400'}>{d.winRate}%</span> | 平均 <span className={d.avgPlPct >= 0 ? 'text-emerald-400' : 'text-red-400'}>{d.avgPlPct}%</span>
                  </span>
                </div>
              ))}
            </div>
          </Card>

          {/* 按来源 */}
          <Card className="p-4">
            <h4 className="text-sm font-semibold text-foreground mb-3">按来源统计</h4>
            <div className="space-y-2 text-xs">
              {Object.entries(stats.bySource || {}).map(([src, d]) => d.total > 0 && (
                <div key={src} className="flex justify-between items-center">
                  <span className="text-muted-foreground">{sourceLabel(src)}</span>
                  <span>
                    {d.total}笔 | 胜率 <span className={d.winRate >= 50 ? 'text-emerald-400' : 'text-red-400'}>{d.winRate}%</span> | 平均 <span className={d.avgPlPct >= 0 ? 'text-emerald-400' : 'text-red-400'}>{d.avgPlPct}%</span>
                  </span>
                </div>
              ))}
            </div>
          </Card>

          {/* 活跃持仓偏差 */}
          <Card className="p-4">
            <h4 className="text-sm font-semibold text-foreground mb-3">当前持仓偏差</h4>
            {stats.activeDeviation.length === 0 ? (
              <p className="text-xs text-muted-foreground">无活跃持仓</p>
            ) : (
              <div className="space-y-2 text-xs max-h-48 overflow-y-auto">
                {stats.activeDeviation.map((d) => (
                  <div key={d.id} className="flex justify-between items-center">
                    <span className="text-muted-foreground">{d.code} ({d.tradeDate})</span>
                    <span className={d.deviationPct >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                      {d.deviationPct >= 0 ? '+' : ''}{d.deviationPct}%
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

// ── 新增/编辑弹窗 ────────────────────────────────────────────────────────────

function RecordModal({
  open,
  onClose,
  onSave,
  loading,
  editing,
}: {
  open: boolean;
  onClose: () => void;
  onSave: (data: {
    code: string;
    tradeDate: string;
    recommendationPrice: number;
    signal: string;
    source: string;
    reason: string;
    sourceTaskId?: string;
  }) => void;
  loading: boolean;
  editing: RecommendationRecord | null;
}) {
  const [code, setCode] = useState('');
  const [tradeDate, setTradeDate] = useState('');
  const [price, setPrice] = useState('');
  const [signal, setSignal] = useState('buy');
  const [source, setSource] = useState('manual');
  const [reason, setReason] = useState('');
  const [sourceTaskId, setSourceTaskId] = useState('');

  useEffect(() => {
    if (!open) return;
    if (editing) {
      setCode(editing.code);
      setTradeDate(editing.tradeDate);
      setPrice(String(editing.recommendationPrice));
      setSignal(editing.signal);
      setSource(editing.source);
      setReason(editing.reason);
      setSourceTaskId(editing.sourceTaskId || '');
    } else {
      setCode('');
      setTradeDate(new Date().toISOString().slice(0, 10));
      setPrice('');
      setSignal('buy');
      setSource('manual');
      setReason('');
      setSourceTaskId('');
    }
  }, [open, editing]);

  if (!open) return null;

  const handleSubmit = () => {
    if (!code.trim() || !tradeDate || !price) return;
    onSave({
      code: code.trim(),
      tradeDate,
      recommendationPrice: parseFloat(price),
      signal,
      source,
      reason: reason.trim(),
      sourceTaskId: sourceTaskId.trim() || undefined,
    });
  };

  const valid = code.trim() && tradeDate && parseFloat(price) > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md mx-4 bg-card border border-border/60 rounded-2xl shadow-2xl p-6">
        <h3 className="text-lg font-semibold text-foreground mb-4">
          {editing ? '编辑记录' : '新增推荐记录'}
        </h3>
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-secondary-text mb-1">股票代码</label>
            <Input
              placeholder="如 000001"
              value={code}
              onChange={e => setCode(e.target.value.toUpperCase())}
              className="w-full"
              disabled={!!editing}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-secondary-text mb-1">交易日期</label>
            <Input
              type="date"
              value={tradeDate}
              onChange={e => setTradeDate(e.target.value)}
              className="w-full"
              disabled={!!editing}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-secondary-text mb-1">推荐价格</label>
            <Input
              type="number"
              step="0.01"
              placeholder="0.00"
              value={price}
              onChange={e => setPrice(e.target.value)}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-secondary-text mb-1">方向</label>
            <Select
              value={signal}
              onChange={setSignal}
              options={[
                { value: 'buy', label: '看多' },
                { value: 'sell', label: '看空' },
                { value: 'hold', label: '观望' },
              ]}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-secondary-text mb-1">来源</label>
            <Select
              value={source}
              onChange={setSource}
              options={[
                { value: 'manual', label: '手动录入' },
                { value: 'analysis', label: '常规分析' },
                { value: 'deep_analysis', label: '深度分析' },
                { value: 'seal_plate', label: '打板' },
                { value: 'comprehensive', label: '综合推荐' },
              ]}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-secondary-text mb-1">来源任务ID (可选)</label>
            <Input
              placeholder="关联任务ID"
              value={sourceTaskId}
              onChange={e => setSourceTaskId(e.target.value)}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-secondary-text mb-1">推荐理由</label>
            <Input
              placeholder="简述推荐理由..."
              value={reason}
              onChange={e => setReason(e.target.value)}
              className="w-full"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={!valid || loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
            {editing ? '保存' : '创建'}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── 平仓弹窗 ────────────────────────────────────────────────────────────────

function CloseModal({
  open,
  onClose,
  onConfirm,
  loading,
  record,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: (closePrice: number) => void;
  loading: boolean;
  record: RecommendationRecord | null;
}) {
  const [closePrice, setClosePrice] = useState('');

  useEffect(() => {
    if (open) {
      setClosePrice(record?.currentPrice ? String(record.currentPrice) : '');
    }
  }, [open, record]);

  if (!open || !record) return null;

  const valid = parseFloat(closePrice) > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-sm mx-4 bg-card border border-border/60 rounded-2xl shadow-2xl p-6">
        <h3 className="text-lg font-semibold text-foreground mb-2">平仓确认</h3>
        <p className="text-sm text-secondary-text mb-4">
          平仓 {record.code}，推荐价 {record.recommendationPrice}
        </p>
        <div>
          <label className="block text-xs font-medium text-secondary-text mb-1">平仓价格</label>
          <Input
            type="number"
            step="0.01"
            value={closePrice}
            onChange={e => setClosePrice(e.target.value)}
            className="w-full"
          />
        </div>
        <div className="flex justify-end gap-2 mt-6">
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={() => onConfirm(parseFloat(closePrice))} disabled={!valid || loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
            确认平仓
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── 详情弹窗 ────────────────────────────────────────────────────────────────

function DetailModal({
  open,
  onClose,
  record,
}: {
  open: boolean;
  onClose: () => void;
  record: RecommendationRecord | null;
}) {
  if (!open || !record) return null;

  const profitColor = (record.profitLossPct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-lg mx-4 max-h-[85vh] overflow-y-auto bg-card border border-border/60 rounded-2xl shadow-2xl p-6">
        {/* 头部 */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              record.signal === 'buy' ? 'bg-emerald-500/15' : record.signal === 'sell' ? 'bg-red-500/15' : 'bg-amber-500/15'
            }`}>
              {record.signal === 'buy' ? (
                <TrendingUp className="h-5 w-5 text-emerald-400" />
              ) : record.signal === 'sell' ? (
                <TrendingDown className="h-5 w-5 text-red-400" />
              ) : (
                <Activity className="h-5 w-5 text-amber-400" />
              )}
            </div>
            <div>
              <h3 className="text-lg font-bold text-foreground">{record.code}</h3>
              <p className="text-xs text-muted-foreground">{record.tradeDate}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors">
            <XCircle className="h-5 w-5" />
          </button>
        </div>

        {/* 状态标签行 */}
        <div className="flex flex-wrap gap-2 mb-5">
          <Badge
            variant={record.status === 'active' ? 'success' : record.status === 'closed' ? 'info' : 'default'}
          >
            {record.status === 'active' ? '持仓中' : record.status === 'closed' ? '已平仓' : '已过期'}
          </Badge>
          {signalBadge(record.signal)}
          <Badge variant="history">{sourceLabel(record.source)}</Badge>
          {record.strategyPattern && (
            <Badge variant="outline" className="border-[hsl(var(--primary))]/40 text-[hsl(var(--primary))]">
              <Compass className="h-3 w-3 mr-1" />
              {strategyLabel(record.strategyPattern)}
            </Badge>
          )}
        </div>

        {/* 价格信息 */}
        <div className="bg-hover rounded-xl p-4 mb-4">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">价格信息</h4>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-muted-foreground">推荐价格</p>
              <p className="text-sm font-semibold text-foreground">{record.recommendationPrice}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">当前价格</p>
              <p className={`text-sm font-semibold ${(record.priceDeviationPct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {record.currentPrice != null ? record.currentPrice : '-'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">价格偏差</p>
              <p className={`text-sm font-semibold ${(record.priceDeviationPct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {record.priceDeviationPct != null ? `${record.priceDeviationPct >= 0 ? '+' : ''}${record.priceDeviationPct}%` : '-'}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">止盈/止损</p>
              <p className="text-sm font-semibold text-foreground">
                {record.takeProfit != null ? <span className="text-emerald-400">+{record.takeProfit}</span> : '-'}
                {' / '}
                {record.stopLoss != null ? <span className="text-red-400">{record.stopLoss}</span> : '-'}
              </p>
            </div>
            {record.status === 'closed' && (
              <>
                <div>
                  <p className="text-xs text-muted-foreground">平仓价格</p>
                  <p className="text-sm font-semibold text-foreground">{record.closePrice ?? '-'}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">盈亏</p>
                  <p className={`text-sm font-bold ${profitColor}`}>
                    {record.profitLossPct != null ? `${record.profitLossPct >= 0 ? '+' : ''}${record.profitLossPct}%` : '-'}
                  </p>
                </div>
              </>
            )}
          </div>
        </div>

        {/* 策略信息 */}
        <div className="bg-hover rounded-xl p-4 mb-4">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Zap className="h-3.5 w-3.5" />策略信息
          </h4>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-muted-foreground">策略战法</p>
              <p className="text-sm font-medium text-foreground">{strategyLabel(record.strategyPattern)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">信号类型</p>
              <p className="text-sm font-medium text-foreground">{signalTypeLabel(record.signalType)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">买入方式</p>
              <p className="text-sm font-medium text-foreground">{entryMethodLabel(record.entryMethod)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">置信度</p>
              <div className="flex items-center gap-1.5">
                <div className="flex-1 h-1.5 bg-border/50 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-[hsl(var(--primary))] transition-all"
                    style={{ width: `${record.confidence}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-foreground tabular-nums">{record.confidence}%</span>
              </div>
            </div>
          </div>
        </div>

        {/* 情绪与持仓 */}
        <div className="bg-hover rounded-xl p-4 mb-4">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Thermometer className="h-3.5 w-3.5" />情绪与持仓
          </h4>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-muted-foreground">情绪阶段</p>
              <p className="text-sm font-medium text-foreground">{sentimentLabel(record.sentimentPhase) || '-'}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">时间周期</p>
              <p className="text-sm font-medium text-foreground">{record.timeHorizon || '-'}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">预计持仓天数</p>
              <p className="text-sm font-medium text-foreground">{record.expectedHoldDays != null ? `${record.expectedHoldDays}天` : '-'}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">所属板块</p>
              <p className="text-sm font-medium text-foreground">{record.sectors || '-'}</p>
            </div>
          </div>
        </div>

        {/* 推荐理由 */}
        <div className="bg-hover rounded-xl p-4 mb-4">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Shield className="h-3.5 w-3.5" />推荐理由
          </h4>
          <p className="text-sm text-secondary-text leading-relaxed">{record.reason || '暂无'}</p>
        </div>

        {/* 来源与时间 */}
        <div className="text-xs text-muted-foreground space-y-1">
          <div className="flex justify-between">
            <span>来源任务ID</span>
            <span className="text-foreground/70">{record.sourceTaskId || '-'}</span>
          </div>
          <div className="flex justify-between">
            <span>创建时间</span>
            <span className="text-foreground/70">{record.createdAt}</span>
          </div>
          <div className="flex justify-between">
            <span>更新时间</span>
            <span className="text-foreground/70">{record.updatedAt}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── 主页面 ───────────────────────────────────────────────────────────────────

export default function RecommendationTrackingPage() {
  const [records, setRecords] = useState<RecommendationRecord[]>([]);
  const [stats, setStats] = useState<RecommendationStats | null>(null);
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [statsLoading, setStatsLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // 视图模式
  const [viewMode, setViewMode] = useState<'list' | 'board'>('list');

  // 共同点分析
  const [commonalityGroups, setCommonalityGroups] = useState<CommonalityGroup[]>([]);
  const [commonalityTotal, setCommonalityTotal] = useState(0);
  const [commonalityLoading, setCommonalityLoading] = useState(false);
  const [activeTagFilter, setActiveTagFilter] = useState<string | null>(null);

  // 筛选
  const [filterCode, setFilterCode] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterSignal, setFilterSignal] = useState('');
  const [filterSource, setFilterSource] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const limit = 20;

  // 弹窗
  const [showModal, setShowModal] = useState(false);
  const [editingRecord, setEditingRecord] = useState<RecommendationRecord | null>(null);
  const [modalLoading, setModalLoading] = useState(false);

  // 平仓弹窗
  const [showCloseModal, setShowCloseModal] = useState(false);
  const [closingRecord, setClosingRecord] = useState<RecommendationRecord | null>(null);
  const [closeLoading, setCloseLoading] = useState(false);

  // 删除确认
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // 自省总结展开
  const [showSummary, setShowSummary] = useState(false);

  // 详情弹窗
  const [detailRecord, setDetailRecord] = useState<RecommendationRecord | null>(null);

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    try {
      const data = await recommendationTrackingApi.listRecords({
        code: filterCode || undefined,
        status: filterStatus || undefined,
        signal: filterSignal || undefined,
        source: filterSource || undefined,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
        page,
        limit,
      });
      setRecords(data.items);
      setTotal(data.total);
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string } }; message?: string };
      setErrorMsg(apiErr.response?.data?.detail || apiErr.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [filterCode, filterStatus, filterSignal, filterSource, startDate, endDate, page]);

  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const data = await recommendationTrackingApi.getStats(
        startDate || undefined,
        endDate || undefined,
      );
      setStats(data);
    } catch {
      // ignore
    } finally {
      setStatsLoading(false);
    }
  }, [startDate, endDate]);

  const fetchCommonality = useCallback(async () => {
    setCommonalityLoading(true);
    try {
      const data = await recommendationTrackingApi.getCommonality(
        startDate || undefined,
        endDate || undefined,
      );
      setCommonalityGroups(data.groups);
      setCommonalityTotal(data.totalAnalyzed);
    } catch {
      // ignore
    } finally {
      setCommonalityLoading(false);
    }
  }, [startDate, endDate]);

  useEffect(() => {
    fetchRecords();
    fetchStats();
    fetchCommonality();
  }, [fetchRecords, fetchStats, fetchCommonality]);

  // 新建/编辑
  const handleSave = async (data: {
    code: string;
    tradeDate: string;
    recommendationPrice: number;
    signal: string;
    source: string;
    reason: string;
    sourceTaskId?: string;
  }) => {
    setModalLoading(true);
    setErrorMsg(null);
    try {
      if (editingRecord) {
        await recommendationTrackingApi.updateRecord(editingRecord.id, data);
      } else {
        await recommendationTrackingApi.createRecord(data);
      }
      setShowModal(false);
      setEditingRecord(null);
      fetchRecords();
      fetchStats();
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string } }; message?: string };
      setErrorMsg(apiErr.response?.data?.detail || apiErr.message || '保存失败');
    } finally {
      setModalLoading(false);
    }
  };

  // 删除
  const handleDelete = async (id: number) => {
    setDeleteLoading(true);
    try {
      await recommendationTrackingApi.deleteRecord(id);
      setDeleteConfirmId(null);
      fetchRecords();
      fetchStats();
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string } }; message?: string };
      setErrorMsg(apiErr.response?.data?.detail || apiErr.message || '删除失败');
    } finally {
      setDeleteLoading(false);
    }
  };

  // 平仓
  const handleClose = async (closePrice: number) => {
    if (!closingRecord) return;
    setCloseLoading(true);
    try {
      await recommendationTrackingApi.closeRecord(closingRecord.id, closePrice);
      setShowCloseModal(false);
      setClosingRecord(null);
      fetchRecords();
      fetchStats();
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string } }; message?: string };
      setErrorMsg(apiErr.response?.data?.detail || apiErr.message || '平仓失败');
    } finally {
      setCloseLoading(false);
    }
  };

  // 快速更新价格
  const handleUpdatePrice = async (record: RecommendationRecord, price: number) => {
    try {
      await recommendationTrackingApi.updatePrice(record.id, price);
      fetchRecords();
    } catch {
      // ignore
    }
  };

  // 生成总结
  const handleGenerateSummary = async () => {
    setSummaryLoading(true);
    setShowSummary(true);
    try {
      const data = await recommendationTrackingApi.generateSummary(
        startDate || undefined,
        endDate || undefined,
      );
      setSummary(data);
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string } }; message?: string };
      setErrorMsg(apiErr.response?.data?.detail || apiErr.message || '生成总结失败');
    } finally {
      setSummaryLoading(false);
    }
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <PageHeader
        title="追踪"
        description="追踪历史推荐记录，回溯计算胜率，自动生成策略反思与优化建议"
        actions={
          <div className="flex items-center border border-border rounded-lg overflow-hidden">
            <button
              type="button"
              onClick={() => setViewMode('list')}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                viewMode === 'list'
                  ? 'bg-[hsl(var(--primary))] text-primary-foreground'
                  : 'bg-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <LayoutList className="h-3.5 w-3.5 inline mr-1" />
              列表
            </button>
            <button
              type="button"
              onClick={() => setViewMode('board')}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                viewMode === 'board'
                  ? 'bg-[hsl(var(--primary))] text-primary-foreground'
                  : 'bg-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <Columns3 className="h-3.5 w-3.5 inline mr-1" />
              看板
            </button>
          </div>
        }
      />

      {/* 共同点分析 */}
      <Card className="p-4">
        <CommonalityTags
          groups={commonalityGroups}
          totalAnalyzed={commonalityTotal}
          activeFilter={activeTagFilter}
          onFilterChange={(key) => {
            setActiveTagFilter(key);
            setPage(1);
          }}
          loading={commonalityLoading}
        />
      </Card>

      {/* 统计面板 */}
      <StatsDashboard stats={stats} loading={statsLoading} />
      <DetailStats stats={stats} loading={statsLoading} />

      {/* 操作栏 */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-end">
        <div className="flex-1 min-w-0">
          <label className="block text-xs font-medium text-secondary-text mb-1">股票代码</label>
          <Input
            placeholder="筛选代码"
            value={filterCode}
            onChange={e => { setFilterCode(e.target.value.toUpperCase()); setPage(1); }}
            className="w-full"
          />
        </div>
        <div className="w-full sm:w-32">
          <label className="block text-xs font-medium text-secondary-text mb-1">方向</label>
          <Select value={filterSignal} onChange={v => { setFilterSignal(v); setPage(1); }} options={SIGNAL_OPTIONS} />
        </div>
        <div className="w-full sm:w-32">
          <label className="block text-xs font-medium text-secondary-text mb-1">状态</label>
          <Select value={filterStatus} onChange={v => { setFilterStatus(v); setPage(1); }} options={STATUS_OPTIONS} />
        </div>
        <div className="w-full sm:w-36">
          <label className="block text-xs font-medium text-secondary-text mb-1">来源</label>
          <Select value={filterSource} onChange={v => { setFilterSource(v); setPage(1); }} options={SOURCE_OPTIONS} />
        </div>
        <div className="w-full sm:w-36">
          <label className="block text-xs font-medium text-secondary-text mb-1">开始日期</label>
          <Input type="date" value={startDate} onChange={e => { setStartDate(e.target.value); setPage(1); }} className="w-full" />
        </div>
        <div className="w-full sm:w-36">
          <label className="block text-xs font-medium text-secondary-text mb-1">结束日期</label>
          <Input type="date" value={endDate} onChange={e => { setEndDate(e.target.value); setPage(1); }} className="w-full" />
        </div>
        <div className="flex gap-2 flex-shrink-0">
          <Button onClick={() => { setEditingRecord(null); setShowModal(true); }}>
            <Plus className="h-4 w-4 mr-1.5" />
            新建
          </Button>
          <Button variant="outline" onClick={handleGenerateSummary} disabled={summaryLoading}>
            {summaryLoading ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : <Brain className="h-4 w-4 mr-1.5" />}
            自省
          </Button>
        </div>
      </div>

      {/* 错误提示 */}
      {errorMsg && (
        <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/8 px-3 py-2">
          <AlertTriangle className="h-4 w-4 text-red-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-xs text-red-400">{errorMsg}</p>
          </div>
          <button type="button" onClick={() => setErrorMsg(null)} className="text-muted-foreground hover:text-foreground flex-shrink-0">
            <XCircle className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* 记录展示区域 */}
      {viewMode === 'board' ? (
        <BoardView
          records={records}
          loading={loading}
          commonalityGroups={commonalityGroups}
          activeTagFilter={activeTagFilter}
          onUpdatePrice={handleUpdatePrice}
          onClose={(r) => { setClosingRecord(r); setShowCloseModal(true); }}
          onEdit={(r) => { setEditingRecord(r); setShowModal(true); }}
          onDelete={(r) => { setDeleteConfirmId(r.id); }}
          onDetail={(r) => setDetailRecord(r)}
        />
      ) : loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-[hsl(var(--primary))]" />
        </div>
      ) : records.length === 0 ? (
        <EmptyState
          icon={<Filter className="h-8 w-8 text-muted-foreground" />}
          title="暂无推荐记录"
          description="点击「新建」添加第一条推荐追踪记录，或调整筛选条件"
        />
      ) : (
        <div className="space-y-2">
          {records.map((r) => {
            const isConfirmingDelete = deleteConfirmId === r.id;
            return (
              <Card key={r.id} className="transition-all hover:bg-hover/30 cursor-pointer" onClick={() => setDetailRecord(r)}>
                <div className="flex items-center gap-3">
                  <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${
                    r.signal === 'buy' ? 'bg-emerald-500/15' : r.signal === 'sell' ? 'bg-red-500/15' : 'bg-amber-500/15'
                  }`}>
                    {r.signal === 'buy' ? (
                      <TrendingUp className="h-5 w-5 text-emerald-400" />
                    ) : r.signal === 'sell' ? (
                      <TrendingDown className="h-5 w-5 text-red-400" />
                    ) : (
                      <Activity className="h-5 w-5 text-amber-400" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-foreground">{r.code}</p>
                      <span className="text-xs text-muted-foreground">{r.tradeDate}</span>
                      {signalBadge(r.signal)}
                      <Badge
                        variant={r.status === 'active' ? 'success' : r.status === 'closed' ? 'info' : 'default'}
                        size="sm"
                      >
                        {r.status === 'active' ? '持仓中' : r.status === 'closed' ? '已平仓' : '已过期'}
                      </Badge>
                      <Badge variant="history" size="sm">{sourceLabel(r.source)}</Badge>
                      {r.strategyPattern && (
                        <span className="text-xs text-[hsl(var(--primary))] bg-[hsl(var(--primary))]/8 px-1.5 py-0.5 rounded font-medium">
                          <Compass className="h-3 w-3 inline mr-0.5" />
                          {strategyLabel(r.strategyPattern)}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-xs text-muted-foreground">
                        推荐价: <span className="text-foreground font-medium">{r.recommendationPrice}</span>
                      </span>
                      {r.currentPrice != null && (
                        <span className="text-xs text-muted-foreground">
                          现价: <span className={`font-medium ${
                            (r.priceDeviationPct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                          }`}>{r.currentPrice}</span>
                        </span>
                      )}
                      {r.priceDeviationPct != null && (
                        <span className={`text-xs font-medium ${r.priceDeviationPct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {r.priceDeviationPct >= 0 ? '+' : ''}{r.priceDeviationPct}%
                        </span>
                      )}
                      {r.status === 'closed' && r.profitLossPct != null && (
                        <span className={`text-xs font-semibold ${r.profitLossPct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {r.profitLossPct >= 0 ? '盈利' : '亏损'} {r.profitLossPct >= 0 ? '+' : ''}{r.profitLossPct}%
                        </span>
                      )}
                      {r.reason && (
                        <span className="text-xs text-muted-foreground truncate max-w-[240px]" title={r.reason}>
                          {r.reason}
                        </span>
                      )}
                    </div>
                  </div>
                  {/* 操作按钮 */}
                  <div className="flex items-center gap-1 flex-shrink-0" onClick={e => e.stopPropagation()}>
                    {r.status === 'active' && (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          title="更新现价"
                          onClick={() => {
                            const price = prompt('输入当前价格:', r.currentPrice ? String(r.currentPrice) : '');
                            if (price && !isNaN(parseFloat(price))) {
                              handleUpdatePrice(r, parseFloat(price));
                            }
                          }}
                        >
                          <RefreshCw className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          title="平仓"
                          onClick={() => { setClosingRecord(r); setShowCloseModal(true); }}
                        >
                          <Target className="h-3.5 w-3.5" />
                        </Button>
                      </>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      title="查看详情"
                      onClick={() => setDetailRecord(r)}
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      title="编辑"
                      onClick={() => { setEditingRecord(r); setShowModal(true); }}
                    >
                      <Edit3 className="h-3.5 w-3.5" />
                    </Button>
                    {isConfirmingDelete ? (
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => handleDelete(r.id)}
                        disabled={deleteLoading}
                      >
                        {deleteLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : '确认'}
                      </Button>
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeleteConfirmId(r.id)}
                        className="text-muted-foreground hover:text-red-400"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* 分页 - 仅列表视图 */}
      {viewMode === 'list' && totalPages > 1 && (
        <div className="flex justify-center mt-6">
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={setPage}
          />
        </div>
      )}

      {/* 自省总结 */}
      {showSummary && (
        <Card className="p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <Brain className="h-4 w-4 text-[hsl(var(--primary))]" />
              策略自省总结
            </h3>
            <Button variant="ghost" size="sm" onClick={() => setShowSummary(false)}>
              <XCircle className="h-4 w-4" />
            </Button>
          </div>
          {summaryLoading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-[hsl(var(--primary))] mb-3" />
              <p className="text-sm text-muted-foreground">LLM 正在分析历史数据并生成反思建议...</p>
            </div>
          ) : summary ? (
            <div className="prose prose-sm prose-invert max-w-none
              prose-headings:text-foreground prose-headings:font-semibold
              prose-h2:text-base prose-h2:mt-5 prose-h2:mb-3
              prose-h3:text-sm prose-h3:mt-4 prose-h3:mb-2
              prose-p:leading-relaxed prose-p:mb-3 prose-p:text-secondary-text
              prose-strong:text-foreground
              prose-li:text-secondary-text prose-li:my-1
            ">
              <Markdown remarkPlugins={[remarkGfm]}>{summary.summary}</Markdown>
            </div>
          ) : (
            <EmptyState
              icon={<Brain className="h-8 w-8 text-muted-foreground" />}
              title="暂无总结"
              description="点击「自省」按钮生成分析"
            />
          )}
        </Card>
      )}

      {/* 弹窗 */}
      <RecordModal
        open={showModal}
        onClose={() => { setShowModal(false); setEditingRecord(null); }}
        onSave={handleSave}
        loading={modalLoading}
        editing={editingRecord}
      />

      <CloseModal
        open={showCloseModal}
        onClose={() => { setShowCloseModal(false); setClosingRecord(null); }}
        onConfirm={handleClose}
        loading={closeLoading}
        record={closingRecord}
      />

      <DetailModal
        open={detailRecord !== null}
        onClose={() => setDetailRecord(null)}
        record={detailRecord}
      />
    </div>
  );
}
