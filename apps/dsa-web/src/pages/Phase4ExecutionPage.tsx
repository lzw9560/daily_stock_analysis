import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, BadgeCheck, CalendarDays, Gauge, RotateCcw, ShieldCheck, TriangleAlert, Wallet } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { backtestApi } from '../api/backtest';
import { getParsedApiError } from '../api/error';
import type { ParsedApiError } from '../api/error';
import { ApiErrorAlert, Badge, Card, Collapsible, EmptyState } from '../components/common';
import type { MonteCarloSimulationResponse } from '../types/backtest';
import { getLastExecutionParams, getLatestExecutionResult, saveExecutionResult, saveLastExecutionParams } from '../utils/executionMemory';

const INPUT_CLASS =
  'input-surface input-focus-glow h-11 w-full rounded-xl border bg-transparent px-4 text-sm transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';
const SELECT_CLASS =
  'input-surface input-focus-glow h-11 w-full rounded-xl border bg-transparent px-4 text-sm transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';

function fmtPct(value?: number | null, digits = 2): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value.toFixed(digits)}%`;
}

function fmtNum(value?: number | null, digits = 4): string {
  if (value == null || Number.isNaN(value)) return '--';
  return value.toFixed(digits);
}

function fmtMoney(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return '--';
  return value.toFixed(2);
}

function fmtJson(value: unknown): string {
  if (value == null) return '--';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

type FormState = {
  symbol: string;
  side: 'buy' | 'sell';
  spot: string;
  quantity: string;
  horizonDays: string;
  paths: string;
  model: 'gbm' | 'heston' | 'bootstrap';
  drift: string;
  vol: string;
  winRate: string;
  payoffRatio: string;
  maxPositionPct: string;
  dryRun: boolean;
};

const DEFAULT_FORM: FormState = {
  symbol: '600519',
  side: 'buy',
  spot: '100',
  quantity: '100',
  horizonDays: '10',
  paths: '10000',
  model: 'gbm',
  drift: '0',
  vol: '0.2',
  winRate: '0.55',
  payoffRatio: '1.5',
  maxPositionPct: '30',
  dryRun: true,
};

const metricCardClass = 'rounded-2xl border border-border/60 bg-base/60 p-4';

const Phase4ExecutionPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [result, setResult] = useState<MonteCarloSimulationResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);

  useEffect(() => {
    const symbol = searchParams.get('symbol')?.trim();
    const side = searchParams.get('side')?.trim().toLowerCase();
    const spot = searchParams.get('spot')?.trim();
    const quantity = searchParams.get('quantity')?.trim();
    const horizonDays = searchParams.get('horizonDays')?.trim();
    const paths = searchParams.get('paths')?.trim();
    const model = searchParams.get('model')?.trim().toLowerCase();
    const drift = searchParams.get('drift')?.trim();
    const vol = searchParams.get('vol')?.trim();
    const winRate = searchParams.get('winRate')?.trim();
    const payoffRatio = searchParams.get('payoffRatio')?.trim();
    const maxPositionPct = searchParams.get('maxPositionPct')?.trim();
    const dryRun = searchParams.get('dryRun')?.trim();

    setForm((current) => ({
      ...current,
      symbol: symbol ? symbol.toUpperCase() : current.symbol,
      side: side === 'sell' ? 'sell' : side === 'buy' ? 'buy' : current.side,
      spot: spot ?? current.spot,
      quantity: quantity ?? current.quantity,
      horizonDays: horizonDays ?? current.horizonDays,
      paths: paths ?? current.paths,
      model: model === 'heston' || model === 'bootstrap' ? model : 'gbm',
      drift: drift ?? current.drift,
      vol: vol ?? current.vol,
      winRate: winRate ?? current.winRate,
      payoffRatio: payoffRatio ?? current.payoffRatio,
      maxPositionPct: maxPositionPct ?? current.maxPositionPct,
      dryRun: dryRun == null ? current.dryRun : dryRun !== 'false',
    }));
  }, [searchParams]);

  useEffect(() => {
    const memory = getLastExecutionParams();
    if (Object.keys(memory).length === 0) return;
    setForm((current) => ({ ...current, ...memory }));
  }, []);

  useEffect(() => {
    const latestResult = getLatestExecutionResult(form.symbol);
    if (!latestResult) return;
    setResult(latestResult.response);
  }, [form.symbol]);

  const canSubmit = useMemo(() => {
    return Boolean(form.symbol.trim()) && Number(form.spot) > 0 && Number(form.quantity) > 0;
  }, [form.quantity, form.spot, form.symbol]);

  const updateField = <K extends keyof FormState>(field: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await backtestApi.simulatePhase4({
        symbol: form.symbol.trim(),
        side: form.side,
        spot: Number(form.spot),
        quantity: Number(form.quantity),
        horizonDays: Number(form.horizonDays),
        paths: Number(form.paths),
        model: form.model,
        drift: Number(form.drift),
        vol: Number(form.vol),
        winRate: Number(form.winRate),
        payoffRatio: Number(form.payoffRatio),
        maxPositionPct: Number(form.maxPositionPct),
        dryRun: form.dryRun,
        metadata: {
          source: 'web-execution-panel',
        },
      });
      setResult(response);
      saveLastExecutionParams(form);
      saveExecutionResult({
        savedAt: new Date().toISOString(),
        input: form,
        response,
      });
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const simulation = result?.simulation ?? null;
  const sizing = result?.sizing ?? null;
  const order = result?.order ?? null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan/20 bg-cyan/10 px-3 py-1 text-xs font-medium text-cyan">
            <Gauge className="h-3.5 w-3.5" />
            Phase 4 · 执行面板
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-foreground">蒙特卡洛 + 原子执行</h1>
            <p className="mt-1 max-w-3xl text-sm text-secondary-text">
              先做仿真、VaR 校准和 Kelly 仓位建议，再生成幂等下单载荷与 WAL 轨迹。默认仅预览，不会触发真实执行。
            </p>
          </div>
        </div>
        <Badge variant={result?.executionEnabled ? 'success' : 'warning'} glow>
          {result?.executionEnabled ? 'EXECUTION_ENABLED=true' : 'EXECUTION_ENABLED=false'}
        </Badge>
      </div>

      {error ? <ApiErrorAlert error={error} /> : null}

      <div className="grid gap-6 xl:grid-cols-[1.12fr_0.88fr]">
        <Card variant="gradient" padding="md">
          <form className="space-y-5" onSubmit={handleSubmit}>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <label className="space-y-2 text-sm text-secondary-text">
                <span>标的代码</span>
                <input className={INPUT_CLASS} value={form.symbol} onChange={(event) => updateField('symbol', event.target.value.toUpperCase())} placeholder="600519 / AAPL / 00700.HK" />
              </label>
              <label className="space-y-2 text-sm text-secondary-text">
                <span>方向</span>
                <select className={SELECT_CLASS} value={form.side} onChange={(event) => updateField('side', event.target.value as FormState['side'])}>
                  <option value="buy">买入</option>
                  <option value="sell">卖出</option>
                </select>
              </label>
              <label className="space-y-2 text-sm text-secondary-text">
                <span>当前价格</span>
                <input className={INPUT_CLASS} type="number" step="0.01" min="0" value={form.spot} onChange={(event) => updateField('spot', event.target.value)} />
              </label>
              <label className="space-y-2 text-sm text-secondary-text">
                <span>委托数量</span>
                <input className={INPUT_CLASS} type="number" step="1" min="1" value={form.quantity} onChange={(event) => updateField('quantity', event.target.value)} />
              </label>
              <label className="space-y-2 text-sm text-secondary-text">
                <span>仿真期限（交易日）</span>
                <input className={INPUT_CLASS} type="number" step="1" min="1" value={form.horizonDays} onChange={(event) => updateField('horizonDays', event.target.value)} />
              </label>
              <label className="space-y-2 text-sm text-secondary-text">
                <span>路径数</span>
                <input className={INPUT_CLASS} type="number" step="1" min="1" value={form.paths} onChange={(event) => updateField('paths', event.target.value)} />
              </label>
              <label className="space-y-2 text-sm text-secondary-text">
                <span>模型</span>
                <select className={SELECT_CLASS} value={form.model} onChange={(event) => updateField('model', event.target.value as FormState['model'])}>
                  <option value="gbm">GBM</option>
                  <option value="heston">Heston</option>
                  <option value="bootstrap">Bootstrap</option>
                </select>
              </label>
              <label className="space-y-2 text-sm text-secondary-text">
                <span>年化漂移</span>
                <input className={INPUT_CLASS} type="number" step="0.0001" value={form.drift} onChange={(event) => updateField('drift', event.target.value)} />
              </label>
              <label className="space-y-2 text-sm text-secondary-text">
                <span>年化波动率</span>
                <input className={INPUT_CLASS} type="number" step="0.0001" min="0" value={form.vol} onChange={(event) => updateField('vol', event.target.value)} />
              </label>
              <label className="space-y-2 text-sm text-secondary-text">
                <span>历史胜率</span>
                <input className={INPUT_CLASS} type="number" step="0.0001" min="0" max="1" value={form.winRate} onChange={(event) => updateField('winRate', event.target.value)} />
              </label>
              <label className="space-y-2 text-sm text-secondary-text">
                <span>盈亏比</span>
                <input className={INPUT_CLASS} type="number" step="0.01" min="0.01" value={form.payoffRatio} onChange={(event) => updateField('payoffRatio', event.target.value)} />
              </label>
              <label className="space-y-2 text-sm text-secondary-text">
                <span>仓位上限（%）</span>
                <input className={INPUT_CLASS} type="number" step="0.1" min="0" max="100" value={form.maxPositionPct} onChange={(event) => updateField('maxPositionPct', event.target.value)} />
              </label>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <label className="inline-flex items-center gap-2 rounded-xl border border-border/60 bg-base/60 px-3 py-2 text-sm text-secondary-text">
                <input type="checkbox" checked={form.dryRun} onChange={(event) => updateField('dryRun', event.target.checked)} />
                仅生成计划（dry-run）
              </label>
              <button type="button" className="btn-secondary inline-flex items-center gap-2" onClick={() => setForm(DEFAULT_FORM)}>
                <RotateCcw className="h-4 w-4" />
                重置
              </button>
              <button type="submit" className="btn-primary inline-flex items-center gap-2 disabled:opacity-60" disabled={!canSubmit || isSubmitting}>
                <ArrowRight className="h-4 w-4" />
                {isSubmitting ? '生成中…' : '运行模拟'}
              </button>
            </div>
          </form>
        </Card>

        <Card variant="glass" padding="md" className="space-y-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-cyan" />
            <h2 className="text-base font-semibold text-foreground">执行摘要</h2>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className={metricCardClass}>
              <p className="text-xs text-secondary-text">模拟收益均值</p>
              <p className="mt-1 text-lg font-semibold text-foreground">{fmtPct(simulation?.meanReturn)}</p>
            </div>
            <div className={metricCardClass}>
              <p className="text-xs text-secondary-text">VaR 95</p>
              <p className="mt-1 text-lg font-semibold text-foreground">{fmtPct(simulation?.var95)}</p>
            </div>
            <div className={metricCardClass}>
              <p className="text-xs text-secondary-text">Kelly</p>
              <p className="mt-1 text-lg font-semibold text-foreground">{fmtNum(sizing?.kellyFraction)}</p>
            </div>
            <div className={metricCardClass}>
              <p className="text-xs text-secondary-text">目标仓位</p>
              <p className="mt-1 text-lg font-semibold text-foreground">{fmtPct(sizing?.targetPositionPct)}</p>
            </div>
          </div>
          <div className="rounded-2xl border border-border/60 bg-base/50 p-4 text-sm text-secondary-text">
            <p className="font-medium text-foreground">说明</p>
            <p className="mt-2 leading-6">
              仪表板展示的是计划态结果：仿真分布、风险约束、仓位建议和下单 WAL。实际执行是否开启取决于后端 `EXECUTION_ENABLED` 开关。
            </p>
          </div>
        </Card>
      </div>

      {result ? (
        <div className="grid gap-6 xl:grid-cols-3">
          <Card title="仿真结果" subtitle="Monte Carlo" variant="default" padding="md">
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between"><span className="text-secondary-text">模型</span><span className="font-medium text-foreground">{simulation?.model ?? '--'}</span></div>
              <div className="flex items-center justify-between"><span className="text-secondary-text">路径数</span><span className="font-medium text-foreground">{simulation?.paths ?? '--'}</span></div>
              <div className="flex items-center justify-between"><span className="text-secondary-text">期限</span><span className="font-medium text-foreground">{simulation?.horizonDays ?? '--'} 天</span></div>
              <div className="flex items-center justify-between"><span className="text-secondary-text">中位数</span><span className="font-medium text-foreground">{fmtPct(simulation?.medianReturn)}</span></div>
              <div className="flex items-center justify-between"><span className="text-secondary-text">P05 / P01</span><span className="font-medium text-foreground">{fmtPct(simulation?.p05Return)} / {fmtPct(simulation?.p01Return)}</span></div>
              <div className="flex items-center justify-between"><span className="text-secondary-text">CVaR95</span><span className="font-medium text-foreground">{fmtPct(simulation?.cvar95)}</span></div>
            </div>
            <Collapsible title="参数与路径预览" icon={<CalendarDays className="h-4 w-4" />} className="mt-4">
              <pre className="max-h-72 overflow-auto rounded-xl bg-base/70 p-3 text-xs text-secondary-text">{fmtJson({ parameters: simulation?.parameters, pathsPreview: simulation?.pathsPreview })}</pre>
            </Collapsible>
          </Card>

          <Card title="仓位与风控" subtitle="VaR + Kelly" variant="default" padding="md">
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between"><span className="text-secondary-text">VaR 限额</span><span className="font-medium text-foreground">{fmtPct(sizing?.varLimitPct)}</span></div>
              <div className="flex items-center justify-between"><span className="text-secondary-text">止损</span><span className="font-medium text-foreground">{fmtPct(sizing?.stopLossPct)}</span></div>
              <div className="flex items-center justify-between"><span className="text-secondary-text">止盈</span><span className="font-medium text-foreground">{fmtPct(sizing?.takeProfitPct)}</span></div>
              <div className="flex items-center justify-between"><span className="text-secondary-text">上限后仓位</span><span className="font-medium text-foreground">{fmtPct(sizing?.cappedPositionPct)}</span></div>
            </div>
            <Collapsible title="建议理由" icon={<TriangleAlert className="h-4 w-4" />} className="mt-4">
              <ul className="space-y-2 text-xs text-secondary-text">
                {(sizing?.rationale ?? []).map((item) => <li key={item} className="rounded-xl border border-border/60 bg-base/60 px-3 py-2">{item}</li>)}
              </ul>
            </Collapsible>
          </Card>

          <Card title="原子下单" subtitle="WAL / 幂等" variant="default" padding="md">
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between"><span className="text-secondary-text">幂等 key</span><span className="font-mono text-xs text-foreground break-all text-right">{order?.idempotencyKey ?? '--'}</span></div>
              <div className="flex items-center justify-between"><span className="text-secondary-text">方向</span><span className="font-medium text-foreground">{order?.side ?? '--'}</span></div>
              <div className="flex items-center justify-between"><span className="text-secondary-text">数量</span><span className="font-medium text-foreground">{order?.quantity ?? '--'}</span></div>
              <div className="flex items-center justify-between"><span className="text-secondary-text">价格</span><span className="font-medium text-foreground">{fmtMoney(order?.price)}</span></div>
              <div className="flex items-center justify-between"><span className="text-secondary-text">WAL 路径</span><span className="font-mono text-[11px] text-foreground break-all text-right">{order?.walPath ?? '--'}</span></div>
              <div className="flex items-center justify-between"><span className="text-secondary-text">dry-run</span><Badge variant={order?.dryRun ? 'warning' : 'success'}>{order?.dryRun ? 'true' : 'false'}</Badge></div>
            </div>
            <Collapsible title="完整载荷" icon={<Wallet className="h-4 w-4" />} className="mt-4">
              <pre className="max-h-72 overflow-auto rounded-xl bg-base/70 p-3 text-xs text-secondary-text">{fmtJson({ executionEnabled: result.executionEnabled, simulation: result.simulation, sizing: result.sizing, order: result.order })}</pre>
            </Collapsible>
          </Card>
        </div>
      ) : (
        <EmptyState
          title="等待一次模拟"
          description="填写参数并运行后，这里会展示仿真摘要、仓位建议和原子执行载荷。"
          icon={<BadgeCheck className="h-6 w-6" />}
        />
      )}
    </div>
  );
};

export default Phase4ExecutionPage;
