/**
 * Backtest API type definitions
 * Mirrors api/v1/schemas/backtest.py
 */

// ============ Request / Response ============

export interface BacktestRunRequest {
  code?: string;
  force?: boolean;
  evalWindowDays?: number;
  minAgeDays?: number;
  limit?: number;
}

export interface BacktestRunResponse {
  processed: number;
  saved: number;
  completed: number;
  insufficient: number;
  errors: number;
}

export interface BacktestOptimizationRequest {
  code?: string;
  evalWindowDays?: number;
  minAgeDays?: number;
  limit?: number;
}

export interface BacktestOptimizationLogItem {
  id: number;
  code?: string | null;
  evalWindowDays: number;
  engineVersion: string;
  combinations: number;
  scoreKey: string;
  bestScore?: number | null;
  bestParams?: Record<string, unknown> | null;
  bestResult?: Record<string, unknown> | null;
  results: Array<Record<string, unknown>>;
  createdAt?: string | null;
}

export interface BacktestOptimizationResponse {
  combinations: number;
  scoreKey: string;
  best?: Record<string, unknown> | null;
  results: Array<Record<string, unknown>>;
}

export interface BacktestOptimizationOverview {
  latest?: BacktestOptimizationLogItem | null;
  history: BacktestOptimizationLogItem[];
  total: number;
}

export interface MonteCarloSimulationRequest {
  symbol: string;
  side: 'buy' | 'sell';
  spot: number;
  quantity: number;
  horizonDays?: number;
  paths?: number;
  model?: 'gbm' | 'heston' | 'bootstrap';
  drift?: number;
  vol?: number;
  winRate?: number;
  payoffRatio?: number;
  maxPositionPct?: number;
  dryRun?: boolean;
  metadata?: Record<string, unknown>;
}

export interface MonteCarloSimulationSummary {
  model: string;
  paths: number;
  horizonDays: number;
  meanReturn: number;
  medianReturn: number;
  p05Return: number;
  p01Return: number;
  var95: number;
  cvar95: number;
  pathsPreview: number[];
  parameters: Record<string, unknown>;
}

export interface PositionSizingSummary {
  varLimitPct: number;
  kellyFraction: number;
  targetPositionPct: number;
  cappedPositionPct: number;
  stopLossPct: number;
  takeProfitPct: number;
  rationale: string[];
}

export interface AtomicOrderPayload {
  idempotencyKey: string;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  orderType: string;
  dryRun: boolean;
  walPath?: string | null;
  createdAt: string;
}

export interface MonteCarloSimulationResponse {
  executionEnabled: boolean;
  simulation: MonteCarloSimulationSummary;
  sizing: PositionSizingSummary;
  order: AtomicOrderPayload;
}

// ============ Result Item ============

export interface BacktestResultItem {
  analysisHistoryId: number;
  code: string;
  stockName?: string;
  analysisDate?: string;
  evalWindowDays: number;
  engineVersion: string;
  evalStatus: string;
  evaluatedAt?: string;
  operationAdvice?: string;
  trendPrediction?: string;
  positionRecommendation?: string;
  startPrice?: number;
  endClose?: number;
  maxHigh?: number;
  minLow?: number;
  stockReturnPct?: number;
  actualReturnPct?: number;
  actualMovement?: string;
  directionExpected?: string;
  directionCorrect?: boolean;
  outcome?: string;
  stopLoss?: number;
  takeProfit?: number;
  hitStopLoss?: boolean;
  hitTakeProfit?: boolean;
  firstHit?: string;
  firstHitDate?: string;
  firstHitTradingDays?: number;
  simulatedEntryPrice?: number;
  simulatedExitPrice?: number;
  simulatedExitReason?: string;
  simulatedReturnPct?: number;
}

export interface BacktestResultsResponse {
  total: number;
  page: number;
  limit: number;
  items: BacktestResultItem[];
}

// ============ Performance Metrics ============

export interface PerformanceMetrics {
  scope: string;
  code?: string;
  evalWindowDays: number;
  engineVersion: string;
  computedAt?: string;

  totalEvaluations: number;
  completedCount: number;
  insufficientCount: number;
  longCount: number;
  cashCount: number;
  winCount: number;
  lossCount: number;
  neutralCount: number;

  directionAccuracyPct?: number;
  winRatePct?: number;
  neutralRatePct?: number;
  avgStockReturnPct?: number;
  avgSimulatedReturnPct?: number;

  stopLossTriggerRate?: number;
  takeProfitTriggerRate?: number;
  ambiguousRate?: number;
  avgDaysToFirstHit?: number;

  adviceBreakdown: Record<string, unknown>;
  diagnostics: Record<string, unknown>;
}
