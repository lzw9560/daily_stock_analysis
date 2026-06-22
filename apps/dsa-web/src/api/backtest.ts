import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  BacktestOptimizationRequest,
  BacktestOptimizationOverview,
  BacktestOptimizationResponse,
  BacktestRunRequest,
  BacktestRunResponse,
  BacktestResultsResponse,
  MonteCarloSimulationRequest,
  MonteCarloSimulationResponse,
  PerformanceMetrics,
} from '../types/backtest';

// ──── Param builders ────

function perfParams(params: { evalWindowDays?: number; analysisDateFrom?: string; analysisDateTo?: string }) {
  const q: Record<string, string | number> = {};
  if (params.evalWindowDays) q.eval_window_days = params.evalWindowDays;
  if (params.analysisDateFrom) q.analysis_date_from = params.analysisDateFrom;
  if (params.analysisDateTo) q.analysis_date_to = params.analysisDateTo;
  return q;
}

async function safeGetPerformance<T>(url: string, params: Record<string, string | number>): Promise<T | null> {
  try {
    const { data } = await apiClient.get<Record<string, unknown>>(url, { params });
    return toCamelCase<T>(data);
  } catch (err: unknown) {
    const axiosErr = err as { response?: { status?: number } };
    if (axiosErr.response?.status === 404) return null;
    throw err;
  }
}

// ──── API ────

export const backtestApi = {
  run: async (params: BacktestRunRequest = {}): Promise<BacktestRunResponse> => {
    const body: Record<string, unknown> = {};
    if (params.code) body.code = params.code;
    if (params.force) body.force = params.force;
    if (params.evalWindowDays) body.eval_window_days = params.evalWindowDays;
    if (params.minAgeDays != null) body.min_age_days = params.minAgeDays;
    if (params.limit) body.limit = params.limit;
    const { data } = await apiClient.post<Record<string, unknown>>('/api/v1/backtest/run', body);
    return toCamelCase<BacktestRunResponse>(data);
  },

  getResults: async (params: {
    code?: string; evalWindowDays?: number; analysisDateFrom?: string;
    analysisDateTo?: string; page?: number; limit?: number;
  } = {}): Promise<BacktestResultsResponse> => {
    const { code, evalWindowDays, analysisDateFrom, analysisDateTo, page = 1, limit = 20 } = params;
    const q: Record<string, string | number> = { page, limit };
    if (code) q.code = code;
    if (evalWindowDays) q.eval_window_days = evalWindowDays;
    if (analysisDateFrom) q.analysis_date_from = analysisDateFrom;
    if (analysisDateTo) q.analysis_date_to = analysisDateTo;

    const { data } = await apiClient.get<Record<string, unknown>>('/api/v1/backtest/results', { params: q });
    // toCamelCase with deep:true handles items array automatically, no need for double conversion
    const result = toCamelCase<BacktestResultsResponse>(data);
    return result;
  },

  getOverallPerformance: async (params: {
    evalWindowDays?: number; analysisDateFrom?: string; analysisDateTo?: string;
  } = {}): Promise<PerformanceMetrics | null> =>
    safeGetPerformance<PerformanceMetrics>('/api/v1/backtest/performance', perfParams(params)),

  getStockPerformance: async (code: string, params: {
    evalWindowDays?: number; analysisDateFrom?: string; analysisDateTo?: string;
  } = {}): Promise<PerformanceMetrics | null> =>
    safeGetPerformance<PerformanceMetrics>(
      `/api/v1/backtest/performance/${encodeURIComponent(code)}`,
      perfParams(params),
    ),

  optimize: async (params: BacktestOptimizationRequest = {}): Promise<BacktestOptimizationResponse> => {
    const body: Record<string, unknown> = {};
    if (params.code) body.code = params.code;
    if (params.evalWindowDays) body.eval_window_days = params.evalWindowDays;
    if (params.minAgeDays != null) body.min_age_days = params.minAgeDays;
    if (params.limit) body.limit = params.limit;
    const { data } = await apiClient.post<Record<string, unknown>>('/api/v1/backtest/optimize', body);
    return toCamelCase<BacktestOptimizationResponse>(data);
  },

  getOptimizationLogs: async (params: { code?: string; limit?: number } = {}): Promise<BacktestOptimizationOverview> => {
    const q: Record<string, string | number> = { limit: params.limit ?? 20 };
    if (params.code) q.code = params.code;
    const { data } = await apiClient.get<Record<string, unknown>>('/api/v1/backtest/optimize/logs', { params: q });
    return toCamelCase<BacktestOptimizationOverview>(data);
  },

  simulatePhase4: async (params: MonteCarloSimulationRequest): Promise<MonteCarloSimulationResponse> => {
    const body: Record<string, unknown> = {
      symbol: params.symbol,
      side: params.side,
      spot: params.spot,
      quantity: params.quantity,
    };
    if (params.horizonDays != null) body.horizon_days = params.horizonDays;
    if (params.paths != null) body.paths = params.paths;
    if (params.model) body.model = params.model;
    if (params.drift != null) body.drift = params.drift;
    if (params.vol != null) body.vol = params.vol;
    if (params.winRate != null) body.win_rate = params.winRate;
    if (params.payoffRatio != null) body.payoff_ratio = params.payoffRatio;
    if (params.maxPositionPct != null) body.max_position_pct = params.maxPositionPct;
    if (params.dryRun != null) body.dry_run = params.dryRun;
    if (params.metadata) body.metadata = params.metadata;
    const { data } = await apiClient.post<Record<string, unknown>>('/api/v1/backtest/phase4/simulate', body);
    return toCamelCase<MonteCarloSimulationResponse>(data);
  },
};
