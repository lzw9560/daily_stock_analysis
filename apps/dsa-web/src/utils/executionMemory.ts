import { useSyncExternalStore } from 'react';
import type { MonteCarloSimulationResponse } from '../types/backtest';

const LAST_PARAMS_KEY = 'dsa_phase4_execution_last_params';
const RESULT_BY_SYMBOL_PREFIX = 'dsa_phase4_execution_result:';
const LATEST_SYMBOL_KEY = `${RESULT_BY_SYMBOL_PREFIX}__latest__`;

type ExecutionStoreState = {
  lastParams: Partial<ExecutionFormMemory>;
  latestResultBySymbol: Record<string, ExecutionResultMemory>;
  latestSymbol: string | null;
};

export type ExecutionFormMemory = {
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

export type ExecutionResultMemory = {
  savedAt: string;
  input: ExecutionFormMemory;
  response: MonteCarloSimulationResponse;
};

const listeners = new Set<() => void>();

function canUseStorage(): boolean {
  return typeof localStorage !== 'undefined';
}

function normalizeSymbol(symbol?: string | null): string {
  return symbol?.trim().toUpperCase() || '';
}

function readJson<T>(key: string, fallback: T): T {
  if (!canUseStorage()) return fallback;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown): void {
  if (!canUseStorage()) return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore storage failures
  }
}

function readResult(symbol: string): ExecutionResultMemory | null {
  const normalizedSymbol = normalizeSymbol(symbol);
  if (!normalizedSymbol) return null;
  return readJson<ExecutionResultMemory | null>(`${RESULT_BY_SYMBOL_PREFIX}${normalizedSymbol}`, null);
}

function readStoreFromStorage(): ExecutionStoreState {
  const lastParams = readJson<Partial<ExecutionFormMemory>>(LAST_PARAMS_KEY, {});
  const latestSymbol = normalizeSymbol(canUseStorage() ? localStorage.getItem(LATEST_SYMBOL_KEY) : null);
  const latestResultBySymbol: Record<string, ExecutionResultMemory> = {};

  if (latestSymbol) {
    const result = readResult(latestSymbol);
    if (result) {
      latestResultBySymbol[latestSymbol] = result;
    }
  }

  return {
    lastParams,
    latestResultBySymbol,
    latestSymbol: latestSymbol || null,
  };
}

let storeState: ExecutionStoreState = readStoreFromStorage();

function emitChange(): void {
  storeState = readStoreFromStorage();
  listeners.forEach((listener) => listener());
}

export function subscribeExecutionMemory(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getExecutionMemorySnapshot(): ExecutionStoreState {
  return storeState;
}

export function useExecutionMemory(): ExecutionStoreState {
  return useSyncExternalStore(subscribeExecutionMemory, getExecutionMemorySnapshot, getExecutionMemorySnapshot);
}

export function getLastExecutionParams(): Partial<ExecutionFormMemory> {
  return storeState.lastParams;
}

export function saveLastExecutionParams(params: Partial<ExecutionFormMemory>): void {
  storeState = {
    ...storeState,
    lastParams: params,
  };
  writeJson(LAST_PARAMS_KEY, params);
  emitChange();
}

export function getLatestExecutionResult(symbol?: string | null): ExecutionResultMemory | null {
  const normalizedSymbol = normalizeSymbol(symbol);
  if (normalizedSymbol) {
    return storeState.latestResultBySymbol[normalizedSymbol] ?? readResult(normalizedSymbol);
  }

  if (!storeState.latestSymbol) return null;
  return storeState.latestResultBySymbol[storeState.latestSymbol] ?? readResult(storeState.latestSymbol);
}

export function saveExecutionResult(payload: ExecutionResultMemory): void {
  const symbol = normalizeSymbol(payload.input.symbol);
  if (!symbol) return;

  storeState = {
    ...storeState,
    latestSymbol: symbol,
    latestResultBySymbol: {
      ...storeState.latestResultBySymbol,
      [symbol]: payload,
    },
  };
  writeJson(`${RESULT_BY_SYMBOL_PREFIX}${symbol}`, payload);
  writeJson(LATEST_SYMBOL_KEY, symbol);
  emitChange();
}

export function buildExecutionPanelHref(params: Partial<ExecutionFormMemory> & { symbol?: string }): string {
  const query = new URLSearchParams();
  const symbol = normalizeSymbol(params.symbol);
  if (symbol) query.set('symbol', symbol);
  if (params.side) query.set('side', params.side);
  if (params.spot != null) query.set('spot', String(params.spot));
  if (params.quantity != null) query.set('quantity', String(params.quantity));
  if (params.horizonDays != null) query.set('horizonDays', String(params.horizonDays));
  if (params.paths != null) query.set('paths', String(params.paths));
  if (params.model) query.set('model', params.model);
  if (params.drift != null) query.set('drift', String(params.drift));
  if (params.vol != null) query.set('vol', String(params.vol));
  if (params.winRate != null) query.set('winRate', String(params.winRate));
  if (params.payoffRatio != null) query.set('payoffRatio', String(params.payoffRatio));
  if (params.maxPositionPct != null) query.set('maxPositionPct', String(params.maxPositionPct));
  if (params.dryRun != null) query.set('dryRun', String(params.dryRun));
  const qs = query.toString();
  return qs ? `/execution?${qs}` : '/execution';
}
