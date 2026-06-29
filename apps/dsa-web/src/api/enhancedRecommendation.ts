import apiClient from './index';
import { toCamelCase } from './utils';

const BASE = '/api/v1/enhanced-recommendation';

// ── Strategy Stats ──────────────────────────────────────────────

export interface StrategyStatItem {
  total: number;
  wins: number;
  losses: number;
  winRate: number;
  avgPlPct: number;
  avgWinPct: number;
  avgLossPct: number;
  profitFactor: number;
  maxDrawdown: number;
  totalPlPct: number;
}

export interface StrategyStatsResponse {
  byStrategy: Record<string, StrategyStatItem>;
  bySignalType: Record<string, StrategyStatItem>;
  bySectors: Record<string, StrategyStatItem>;
  bySentiment: Record<string, StrategyStatItem>;
  byEntryMethod: Record<string, StrategyStatItem>;
  byTimeHorizon: Record<string, StrategyStatItem>;
  totalClosed: number;
}

export function getStrategyStats(params?: {
  startDate?: string;
  endDate?: string;
  minSamples?: number;
}): Promise<StrategyStatsResponse> {
  return apiClient
    .get(`${BASE}/strategy-stats`, { params })
    .then((r) => toCamelCase(r.data));
}

// ── Strategy Ranking ────────────────────────────────────────────

export interface StrategyRankItem {
  strategy: string;
  winRate: number;
  profitFactor: number;
  total: number;
  avgPlPct: number;
  totalPlPct: number;
  maxDrawdown: number;
  compositeScore: number;
}

export function getStrategyRanking(params?: {
  limit?: number;
  minSamples?: number;
}): Promise<StrategyRankItem[]> {
  return apiClient
    .get(`${BASE}/strategy-ranking`, { params })
    .then((r) => toCamelCase(r.data));
}

// ── Strategy Comparison ─────────────────────────────────────────

export function compareStrategies(strategies: string, params?: {
  startDate?: string;
  endDate?: string;
}): Promise<Record<string, any>> {
  return apiClient
    .get(`${BASE}/strategy-comparison`, {
      params: { strategies, ...params },
    })
    .then((r) => toCamelCase(r.data));
}

// ── Win Rate Trend ──────────────────────────────────────────────

export interface WinRateTrendItem {
  index: number;
  winRate: number;
  total: number;
  wins: number;
}

export function getWinRateTrend(params?: {
  days?: number;
  window?: number;
}): Promise<WinRateTrendItem[]> {
  return apiClient
    .get(`${BASE}/win-rate-trend`, { params })
    .then((r) => toCamelCase(r.data));
}

// ── Sentiment ───────────────────────────────────────────────────

export interface SentimentMetrics {
  sentimentScore: number;
  phase: string;
  limitUpCount: number;
  limitDownCount: number;
  sealPlateCount: number;
  brokenSealCount: number;
  sealRate: number;
  highestBoard: number;
  connectivityCount: number;
  advanceCount: number;
  declineCount: number;
  advanceRatio: number;
  northFlow: number;
  mainForceFlow: number;
  turnoverTotal: number;
  turnoverChange: number;
}

export interface SentimentRecommendation {
  action: string;
  positionSuggestion: string;
  riskLevel: string;
  focus: string;
  suitableStrategies: string[];
}

export interface SentimentResponse {
  metrics: SentimentMetrics;
  recommendation: SentimentRecommendation;
}

export function getSentiment(params?: Record<string, any>): Promise<SentimentResponse> {
  return apiClient
    .get(`${BASE}/sentiment`, { params })
    .then((r) => toCamelCase(r.data));
}

// ── Short-term Signals ──────────────────────────────────────────

export interface ShortTermSignal {
  code: string;
  name: string;
  strategy: string;
  signalType: string;
  confidence: number;
  entryPriceRange: number[];
  stopLoss: number;
  takeProfit: number;
  expectedHoldDays: number;
  reason: string;
  riskFactors: string[];
}

export interface ShortTermSignalsResponse {
  signals: ShortTermSignal[];
  total: number;
  byStrategy: Record<string, number>;
}

export function getShortTermSignals(params?: Record<string, any>): Promise<ShortTermSignalsResponse> {
  return apiClient
    .get(`${BASE}/short-term-signals`, { params })
    .then((r) => toCamelCase(r.data));
}

// ── Execution Plan ──────────────────────────────────────────────

export interface ExecutionPlanResponse {
  simulation: any;
  positionSizing: any;
  orderPayload: any;
}

export function getExecutionPlan(params: {
  code: string;
  spot: number;
  vol?: number;
  horizonDays?: number;
  totalCapital?: number;
}): Promise<ExecutionPlanResponse> {
  return apiClient
    .get(`${BASE}/execution-plan`, { params })
    .then((r) => toCamelCase(r.data));
}
