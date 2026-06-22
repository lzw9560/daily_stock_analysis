import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Activity, Play, Pause, Square, RefreshCw, Plus, Trash2,
  RadioTower, AlertTriangle,
  Zap, Shield, Wifi, WifiOff, Eye,
} from 'lucide-react';
import { Button } from '@/components/common/Button';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import apiClient from '@/api/index';
import { cn } from '@/utils/cn';

// ============================================================
//  类型定义
// ============================================================

interface WatchlistItem {
  code: string;
  name: string;
}

interface StrategyInfo {
  type: string;
  enabled: boolean;
  params: Record<string, number>;
}

interface MonitorStatus {
  status: 'stopped' | 'running' | 'paused' | 'reconnecting' | 'error';
  is_trading_time: boolean;
  watchlist_count: number;
  watchlist: WatchlistItem[];
  strategies_count: number;
  strategies: StrategyInfo[];
  poll_interval: number;
  circuit_breaker: Record<string, string>;
  rounds: number;
  signals_triggered: number;
  errors: number;
  last_poll_time: string | null;
  start_time: string | null;
}

interface DefaultStrategy {
  strategy_type: string;
  signal_type: string;
  enabled: boolean;
  params: Record<string, number>;
  cooldown_seconds: number;
}

// ============================================================
//  API 调用
// ============================================================

const monitorApi = {
  getStatus: () => apiClient.get<MonitorStatus>('/api/v1/position-monitor/status').then(r => r.data),
  start: () => apiClient.post('/api/v1/position-monitor/start').then(r => r.data),
  pause: () => apiClient.post('/api/v1/position-monitor/pause').then(r => r.data),
  resume: () => apiClient.post('/api/v1/position-monitor/resume').then(r => r.data),
  stop: () => apiClient.post('/api/v1/position-monitor/stop').then(r => r.data),
  addStock: (code: string, name: string) =>
    apiClient.post('/api/v1/position-monitor/stocks', { code, name }).then(r => r.data),
  removeStock: (code: string) =>
    apiClient.delete(`/api/v1/position-monitor/stocks/${code}`).then(r => r.data),
  syncWatchlist: () =>
    apiClient.post('/api/v1/position-monitor/stocks/sync-watchlist').then(r => r.data),
  getDefaultStrategies: () =>
    apiClient.get<{ strategies: DefaultStrategy[] }>('/api/v1/position-monitor/strategies/default').then(r => r.data),
  checkTradingTime: () =>
    apiClient.get('/api/v1/position-monitor/trading-time').then(r => r.data),
  sendHeartbeat: () =>
    apiClient.post('/api/v1/position-monitor/heartbeat').then(r => r.data),
  restart: (config?: { poll_interval: number }) =>
    apiClient.post('/api/v1/position-monitor/restart', config).then(r => r.data),
};

// ============================================================
//  状态标记组件
// ============================================================

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  stopped: { label: '已停止', color: 'text-slate-400', bg: 'bg-slate-500/10' },
  running: { label: '监控中', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  paused: { label: '已暂停', color: 'text-amber-400', bg: 'bg-amber-500/10' },
  reconnecting: { label: '重连中', color: 'text-orange-400', bg: 'bg-orange-500/10' },
  error: { label: '异常', color: 'text-red-400', bg: 'bg-red-500/10' },
};

function StatusDot({ status }: { status: string }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.stopped;
  return (
    <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium', config.bg, config.color)}>
      <span className={cn(
        'w-2 h-2 rounded-full',
        status === 'running' && 'bg-emerald-400 animate-pulse',
        status === 'paused' && 'bg-amber-400',
        status === 'reconnecting' && 'bg-orange-400 animate-pulse',
        status === 'error' && 'bg-red-400',
        status === 'stopped' && 'bg-slate-400',
      )} />
      {config.label}
    </span>
  );
}

// ============================================================
//  主页面
// ============================================================

export default function PositionMonitorPage() {
  const [status, setStatus] = useState<MonitorStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addCode, setAddCode] = useState('');
  const [addName, setAddName] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval>>();
  const [defaultStrategies, setDefaultStrategies] = useState<DefaultStrategy[]>([]);

  // 获取状态
  const fetchStatus = useCallback(async () => {
    try {
      const data = await monitorApi.getStatus();
      setStatus(data);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  // 轮询状态
  useEffect(() => {
    fetchStatus();
    monitorApi.getDefaultStrategies().then(d => setDefaultStrategies(d.strategies)).catch(() => {});
    pollRef.current = setInterval(fetchStatus, 5000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [fetchStatus]);

  // 控制操作
  const handleStart = async () => {
    setLoading(true);
    try { await monitorApi.start(); await fetchStatus(); } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    setLoading(false);
  };

  const handlePause = async () => {
    setLoading(true);
    try { await monitorApi.pause(); await fetchStatus(); } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    setLoading(false);
  };

  const handleResume = async () => {
    setLoading(true);
    try { await monitorApi.resume(); await fetchStatus(); } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    setLoading(false);
  };

  const handleStop = async () => {
    setLoading(true);
    try { await monitorApi.stop(); await fetchStatus(); } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    setLoading(false);
  };

  const handleRestart = async () => {
    setLoading(true);
    try { await monitorApi.restart({ poll_interval: 3 }); await fetchStatus(); } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    setLoading(false);
  };

  // 添加标的
  const handleAddStock = async () => {
    if (!addCode.trim()) return;
    try {
      await monitorApi.addStock(addCode.trim(), addName.trim());
      setAddCode('');
      setAddName('');
      await fetchStatus();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
  };

  // 移除标的
  const handleRemoveStock = async (code: string) => {
    try {
      await monitorApi.removeStock(code);
      await fetchStatus();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
  };

  // 同步自选股
  const handleSyncWatchlist = async () => {
    try {
      await monitorApi.syncWatchlist();
      await fetchStatus();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
  };

  // 心跳测试
  const handleHeartbeat = async () => {
    try {
      await monitorApi.sendHeartbeat();
      alert('飞书心跳发送成功');
    } catch (e: unknown) {
      alert('飞书心跳发送失败: ' + (e instanceof Error ? e.message : String(e)));
    }
  };

  const isRunning = status?.status === 'running';
  const isPaused = status?.status === 'paused';
  const isStopped = status?.status === 'stopped';

  return (
    <div className="space-y-6 p-6 max-w-6xl mx-auto">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-3">
            <RadioTower className="w-7 h-7 text-cyan-400" />
            持仓盘中监控
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            实时监控自选标的行情异动，策略触发时通过飞书即时告警
          </p>
        </div>
        {status && <StatusDot status={status.status} />}
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-red-400/60 hover:text-red-400">✕</button>
        </div>
      )}

      {/* 控制栏 */}
      <Card variant="bordered" className="!p-4">
        <div className="flex items-center gap-3 flex-wrap">
          {isStopped && (
            <Button size="sm" variant="primary" onClick={handleStart} disabled={loading} glow>
              <Play className="w-4 h-4 mr-1.5" /> 启动监控
            </Button>
          )}
          {isRunning && (
            <Button size="sm" variant="secondary" onClick={handlePause} disabled={loading}>
              <Pause className="w-4 h-4 mr-1.5" /> 暂停
            </Button>
          )}
          {isPaused && (
            <Button size="sm" variant="primary" onClick={handleResume} disabled={loading}>
              <Play className="w-4 h-4 mr-1.5" /> 恢复
            </Button>
          )}
          {(isRunning || isPaused) && (
            <Button size="sm" variant="danger-subtle" onClick={handleStop} disabled={loading}>
              <Square className="w-4 h-4 mr-1.5" /> 停止
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={handleRestart} disabled={loading}>
            <RefreshCw className={cn('w-4 h-4 mr-1.5', loading && 'animate-spin')} /> 重启
          </Button>
          <div className="w-px h-6 bg-border mx-1" />
          <Button size="sm" variant="ghost" onClick={handleSyncWatchlist}>
            <RefreshCw className="w-4 h-4 mr-1.5" /> 同步自选股
          </Button>
          <Button size="sm" variant="ghost" onClick={handleHeartbeat}>
            <Zap className="w-4 h-4 mr-1.5" /> 飞书心跳测试
          </Button>
          <Button size="sm" variant="ghost" onClick={fetchStatus}>
            <RefreshCw className="w-4 h-4 mr-1.5" /> 刷新
          </Button>
        </div>
      </Card>

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <StatBox icon={<Activity />} label="轮询次数" value={status?.rounds || 0} color="text-cyan-400" />
        <StatBox icon={<Zap />} label="触发信号" value={status?.signals_triggered || 0} color="text-amber-400" />
        <StatBox icon={<AlertTriangle />} label="异常次数" value={status?.errors || 0} color="text-red-400" />
        <StatBox icon={<Eye />} label="监控标的" value={status?.watchlist_count || 0} color="text-violet-400" />
        <StatBox icon={<Shield />} label="策略数" value={status?.strategies_count || 0} color="text-emerald-400" />
        <StatBox
          icon={status?.is_trading_time ? <Wifi className="text-emerald-400" /> : <WifiOff className="text-slate-500" />}
          label="交易时段"
          value={status?.is_trading_time ? '盘中' : '休市'}
          color={status?.is_trading_time ? 'text-emerald-400' : 'text-slate-400'}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 监控列表 */}
        <Card title="监控标的" subtitle={`${status?.watchlist_count || 0} 只标的`} padding="none">
          {/* 添加栏 */}
          <div className="flex gap-2 px-5 pt-4 pb-3 border-b border-border/50">
            <input
              type="text"
              placeholder="股票代码 (如 600519)"
              value={addCode}
              onChange={e => setAddCode(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAddStock()}
              className="flex-1 bg-card border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-cyan/50"
            />
            <input
              type="text"
              placeholder="名称(可选)"
              value={addName}
              onChange={e => setAddName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAddStock()}
              className="w-32 bg-card border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-cyan/50"
            />
            <Button size="sm" variant="primary" onClick={handleAddStock}>
              <Plus className="w-4 h-4" />
            </Button>
          </div>

          {/* 列表 */}
          <div className="max-h-80 overflow-y-auto">
            {(!status?.watchlist || status.watchlist.length === 0) ? (
              <div className="py-12 text-center text-muted-foreground text-sm">
                暂无监控标的，请添加股票代码或点击"同步自选股"
              </div>
            ) : (
              status.watchlist.map((item, idx) => (
                <div
                  key={item.code}
                  className={cn(
                    'flex items-center gap-3 px-5 py-3 border-b border-border/30 last:border-b-0',
                    'hover:bg-card/50 transition-colors',
                  )}
                >
                  <span className="text-xs text-muted-foreground w-6">{idx + 1}</span>
                  <span className="text-sm font-mono text-foreground">{item.code}</span>
                  <span className="text-sm text-muted-foreground flex-1">{item.name || '—'}</span>
                  <button
                    onClick={() => handleRemoveStock(item.code)}
                    className="text-muted-foreground/40 hover:text-red-400 transition-colors"
                    title="移除"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))
            )}
          </div>
        </Card>

        {/* 策略配置 */}
        <Card title="监控策略" subtitle={`${status?.strategies_count || 0} 条策略`} padding="none">
          <div className="max-h-80 overflow-y-auto">
            {(status?.strategies && status.strategies.length > 0 ? status.strategies : defaultStrategies.map(s => ({
              type: s.strategy_type,
              enabled: s.enabled,
              params: s.params,
            }))).map((strategy) => (
              <div
                key={strategy.type}
                className={cn(
                  'flex items-center gap-3 px-5 py-3 border-b border-border/30 last:border-b-0',
                )}
              >
                <div className={cn(
                  'w-2 h-2 rounded-full',
                  strategy.enabled ? 'bg-emerald-400' : 'bg-slate-600',
                )} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-foreground">
                    {STRATEGY_LABELS[strategy.type] || strategy.type}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {Object.entries(strategy.params || {}).map(([k, v]) => (
                      <span key={k} className="mr-3">{k}: <span className="text-cyan-400">{v}</span></span>
                    ))}
                  </div>
                </div>
                <Badge variant={strategy.enabled ? 'success' : 'default'}>
                  {strategy.enabled ? '启用' : '禁用'}
                </Badge>
              </div>
            ))}
            {(!status?.strategies || status.strategies.length === 0) && defaultStrategies.length === 0 && (
              <div className="py-12 text-center text-muted-foreground text-sm">
                暂无策略配置
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* 运行信息 */}
      {status && (
        <Card title="运行信息" padding="sm">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <InfoItem label="轮询间隔" value={`${status.poll_interval}s`} />
            <InfoItem label="最后轮询" value={status.last_poll_time ? new Date(status.last_poll_time).toLocaleTimeString() : '—'} />
            <InfoItem label="启动时间" value={status.start_time ? new Date(status.start_time).toLocaleString() : '—'} />
            <InfoItem label="熔断状态" value={
              Object.entries(status.circuit_breaker || {}).map(([k, v]) => `${k}:${v}`).join(', ') || '正常'
            } />
          </div>
        </Card>
      )}
    </div>
  );
}

// ============================================================
//  子组件
// ============================================================

function StatBox({ icon, label, value, color }: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <Card variant="bordered" className="!p-3">
      <div className="flex items-center gap-2">
        <span className={cn('w-4 h-4', color)}>{icon}</span>
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <div className={cn('text-xl font-bold mt-1', color)}>{value}</div>
    </Card>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-sm text-foreground font-mono mt-0.5">{value}</div>
    </div>
  );
}

const STRATEGY_LABELS: Record<string, string> = {
  change_threshold: '涨跌幅阈值告警',
  volume_surge: '量比异动告警',
  amplitude_alert: '振幅异常告警',
  turnover_alert: '换手率异常告警',
  price_breakout: '价格突破告警',
  ma_cross: '均线交叉告警',
};
