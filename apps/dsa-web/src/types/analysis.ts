/**
 * Analysis-related type definitions.
 * Aligned with the API schema.
 */

// ============ Request Types ============

export type StockReportType = 'simple' | 'detailed' | 'full' | 'brief';
export type ReportType = StockReportType | 'market_review';

export interface AnalysisRequest {
  stockCode?: string;
  stockCodes?: string[];
  reportType?: StockReportType;
  forceRefresh?: boolean;
  asyncMode?: boolean;
  stockName?: string;
  originalQuery?: string;
  selectionSource?: 'manual' | 'autocomplete' | 'import' | 'image';
  notify?: boolean;
  skills?: string[];
}

export interface MarketReviewRequest {
  sendNotification?: boolean;
}

export interface MarketReviewAccepted {
  status: 'accepted';
  message: string;
  sendNotification: boolean;
  traceId?: string;
  taskId?: string;
}

// ============ Report Types ============

export type ReportLanguage = 'zh' | 'en';

export type MarketPhaseValue =
  | 'premarket'
  | 'intraday'
  | 'lunch_break'
  | 'closing_auction'
  | 'postmarket'
  | 'non_trading'
  | 'unknown';

export interface MarketPhaseSummary {
  market?: string | null;
  phase: MarketPhaseValue;
  marketLocalTime?: string | null;
  sessionDate?: string | null;
  effectiveDailyBarDate?: string | null;
  isTradingDay?: boolean | null;
  isMarketOpenNow?: boolean | null;
  isPartialBar?: boolean | null;
  minutesToOpen?: number | null;
  minutesToClose?: number | null;
  triggerSource?: string | null;
  analysisIntent?: string | null;
  warnings: string[];
}

/** Report metadata */
export interface ReportMeta {
  id?: number;  // Analysis history record ID, present for persisted reports
  queryId: string;
  stockCode: string;
  stockName: string;
  reportType: ReportType;
  reportLanguage?: ReportLanguage;
  createdAt: string;
  currentPrice?: number;
  changePct?: number;
  modelUsed?: string;  // Display-only model snapshot from persisted history; not used for runtime model selection
  marketPhaseSummary?: MarketPhaseSummary | null;
}

/** Sentiment label */
export type SentimentLabel =
  | '极度悲观'
  | '悲观'
  | '中性'
  | '乐观'
  | '极度乐观'
  | 'Very Bearish'
  | 'Bearish'
  | 'Neutral'
  | 'Bullish'
  | 'Very Bullish';

/** Report summary section */
export interface ReportSummary {
  analysisSummary: string;
  operationAdvice: string;
  trendPrediction: string;
  sentimentScore: number;
  sentimentLabel?: SentimentLabel;
}

/** Strategy section */
export interface ReportStrategy {
  idealBuy?: string;
  secondaryBuy?: string;
  stopLoss?: string;
  takeProfit?: string;
}

export interface RelatedBoard {
  name: string;
  code?: string;
  type?: string;
}

export interface SectorRankingItem {
  name: string;
  changePct?: number;
}

export interface SectorRankings {
  top?: SectorRankingItem[];
  bottom?: SectorRankingItem[];
}

export type AnalysisContextPackBlockStatus =
  | 'available'
  | 'missing'
  | 'not_supported'
  | 'fallback'
  | 'stale'
  | 'estimated'
  | 'partial'
  | 'fetch_failed';

export interface AnalysisContextPackOverviewSubject {
  code: string;
  stockName?: string | null;
  market?: string | null;
}

export interface AnalysisContextPackOverviewBlock {
  key: string;
  label: string;
  status: AnalysisContextPackBlockStatus;
  source?: string | null;
  warnings: string[];
  missingReasons: string[];
}

export interface AnalysisContextPackOverviewCounts {
  available: number;
  missing: number;
  notSupported: number;
  fallback: number;
  stale: number;
  estimated: number;
  partial: number;
  fetchFailed: number;
}

export interface AnalysisContextPackOverviewMetadata {
  triggerSource?: string | null;
  newsResultCount?: number | null;
}

export type AnalysisContextPackDataQualityLevel = 'good' | 'usable' | 'limited' | 'poor';

export interface AnalysisContextPackOverviewDataQuality {
  overallScore?: number | null;
  level?: AnalysisContextPackDataQualityLevel | null;
  blockScores: Record<string, number>;
  limitations: string[];
}

export interface AnalysisContextPackOverview {
  packVersion: string;
  createdAt?: string | null;
  subject: AnalysisContextPackOverviewSubject;
  blocks: AnalysisContextPackOverviewBlock[];
  counts: AnalysisContextPackOverviewCounts;
  dataQuality?: AnalysisContextPackOverviewDataQuality | null;
  warnings: string[];
  metadata: AnalysisContextPackOverviewMetadata;
}

/** Details section */
export interface ReportDetails {
  newsContent?: string;
  rawResult?: Record<string, unknown>;
  contextSnapshot?: Record<string, unknown>;
  analysisContextPackOverview?: AnalysisContextPackOverview | null;
  financialReport?: Record<string, unknown>;
  dividendMetrics?: Record<string, unknown>;
  belongBoards?: RelatedBoard[];
  sectorRankings?: SectorRankings;
}

/** Full analysis report */
export interface AnalysisReport {
  meta: ReportMeta;
  summary: ReportSummary;
  strategy?: ReportStrategy;
  details?: ReportDetails;
}

// ============ Analysis Result Types ============

export type RunDiagnosticStatus = 'normal' | 'degraded' | 'failed' | 'unknown';

export type RunDiagnosticComponentStatus =
  | 'ok'
  | 'degraded'
  | 'failed'
  | 'unknown'
  | 'not_configured'
  | 'skipped';

export interface RunDiagnosticComponent {
  key: string;
  label: string;
  status: RunDiagnosticComponentStatus;
  message: string;
  details?: Record<string, unknown>;
}

export interface RunDiagnosticSummary {
  traceId?: string;
  taskId?: string;
  queryId?: string;
  stockCode?: string;
  triggerSource?: string;
  status: RunDiagnosticStatus;
  statusLabel: string;
  reason: string;
  components: Record<string, RunDiagnosticComponent>;
  copyText: string;
}

/** Sync analysis response */
export interface AnalysisResult {
  queryId: string;
  traceId?: string;
  stockCode: string;
  stockName: string;
  report: AnalysisReport;
  diagnosticSummary?: RunDiagnosticSummary;
  createdAt: string;
}

/** Async task accepted response */
export interface TaskAccepted {
  taskId: string;
  traceId?: string;
  status: 'pending' | 'processing';
  message?: string;
}

export interface BatchTaskAcceptedItem {
  taskId: string;
  traceId?: string;
  stockCode: string;
  status: 'pending' | 'processing';
  message?: string;
}

export interface BatchDuplicateTaskItem {
  stockCode: string;
  existingTaskId: string;
  message: string;
}

export interface BatchTaskAcceptedResponse {
  accepted: BatchTaskAcceptedItem[];
  duplicates: BatchDuplicateTaskItem[];
  message: string;
}

export type AnalyzeAsyncResponse = TaskAccepted | BatchTaskAcceptedResponse;

export type AnalyzeResponse = AnalysisResult | AnalyzeAsyncResponse;

/** Task status */
export interface TaskStatus {
  taskId: string;
  traceId?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress?: number;
  result?: AnalysisResult;
  marketReviewReport?: string;
  error?: string;
  stockName?: string;
  originalQuery?: string;
  selectionSource?: string;
  skills?: string[];
}

import type { FactorPipelineSummary } from './screening';
import type { AgentRuntime } from '../api/agent';

/** Task details used by task list and SSE events */
export interface TaskInfo {
  taskId: string;
  traceId?: string;
  stockCode: string;
  stockName?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  message?: string;
  reportType: string;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  error?: string;
  originalQuery?: string;
  selectionSource?: string;
  factorPipeline?: FactorPipelineSummary;
  runtime?: AgentRuntime;
}

/** Task list response */
export interface TaskListResponse {
  total: number;
  pending: number;
  processing: number;
  tasks: TaskInfo[];
}

/** Duplicate task error response */
export interface DuplicateTaskError {
  error: 'duplicate_task';
  message: string;
  stockCode: string;
  existingTaskId: string;
}

// ============ History Types ============

/** History item summary */
export interface HistoryItem {
  id: number;  // Record primary key ID, always present for persisted history items
  queryId: string;  // Linked analysis query ID
  stockCode: string;
  stockName?: string;
  reportType?: ReportType;
  trendPrediction?: string;
  analysisSummary?: string;
  sentimentScore?: number;
  operationAdvice?: string;
  currentPrice?: number;
  changePct?: number;
  volumeRatio?: number;
  turnoverRate?: number;
  modelUsed?: string;  // Display-only model snapshot from persisted history; runtime provider/model/base URL still come from analyzer configuration
  createdAt: string;
}

export type StockHistoryRange = 'all' | '30d' | '90d';

export interface StockHistoryFilters {
  range: StockHistoryRange;
  model: string;
  sort: 'desc' | 'asc';
}

/** History list response */
export interface HistoryListResponse {
  total: number;
  page: number;
  limit: number;
  items: HistoryItem[];
}

/** News item */
export interface NewsIntelItem {
  title: string;
  snippet: string;
  url: string;
}

/** News response */
export interface NewsIntelResponse {
  total: number;
  items: NewsIntelItem[];
}

/** History filter parameters */
export interface HistoryFilters {
  stockCode?: string;
  startDate?: string;
  endDate?: string;
}

/** History pagination parameters */
export interface HistoryPagination {
  page: number;
  limit: number;
}

// ============ Error Types ============

export interface ApiError {
  error: string;
  message: string;
  detail?: Record<string, unknown>;
}

// ============ Helper Functions ============

/** Get sentiment label by score */
export const getSentimentLabel = (score: number, language: ReportLanguage = 'zh'): SentimentLabel => {
  if (language === 'en') {
    if (score <= 20) return 'Very Bearish';
    if (score <= 40) return 'Bearish';
    if (score <= 60) return 'Neutral';
    if (score <= 80) return 'Bullish';
    return 'Very Bullish';
  }
  if (score <= 20) return '极度悲观';
  if (score <= 40) return '悲观';
  if (score <= 60) return '中性';
  if (score <= 80) return '乐观';
  return '极度乐观';
};

/** Get sentiment color by score */
export const getSentimentColor = (score: number): string => {
  if (score <= 20) return '#ef4444'; // red-500
  if (score <= 40) return '#f97316'; // orange-500
  if (score <= 60) return '#eab308'; // yellow-500
  if (score <= 80) return '#22c55e'; // green-500
  return '#10b981'; // emerald-500
};

// ==============================================================
// Financial Data Types - Federal Reserve & Yahoo Finance
// ==============================================================

export interface FederalReserveRatePoint {
  date: string;
  value: number;
  maturity: string;
  unit: string;
}

export interface FederalReserveRateResponse {
  series: FederalReserveRatePoint[];
  metadata: {
    source: 'FRED' | 'FederalReserve';
    lastUpdated: string;
    maturityTypes: string[];
    currency: string;
  };
}

export interface YahooFinanceQuote {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  adjustedClose?: number;
}

export interface YahooFinanceMetadata {
  symbol: string;
  currency: string;
  exchangeName: string;
  instrumentType: string;
  firstTradeDate: number;
  regularMarketTime: number;
  hasPrePostMarketData: boolean;
  gmtoffset: number;
  timezone: string;
  exchangeTimezoneName: string;
  regularMarketPrice: number;
  fiftyTwoWeekHigh: number;
  fiftyTwoWeekLow: number;
  regularMarketDayHigh: number;
  regularMarketDayLow: number;
  regularMarketVolume: number;
  marketCap?: number;
  beta?: number;
  trailingPE?: number;
  forwardPE?: number;
  dividendRate?: number;
  dividendYield?: number;
}

export interface YahooFinanceDataResponse {
  chart: {
    result: Array<{
      meta: YahooFinanceMetadata;
      timestamp: number[];
      indicators: {
        quote: Array<{
          open: number[];
          high: number[];
          low: number[];
          close: number[];
          volume: number[];
        }>;
        adjclose?: Array<{
          adjclose: number[];
        }>;
      };
    }>;
    error: unknown | null;
  };
}

export interface EconomicCalendarEvent {
  date: string;
  time?: string;
  country: string;
  currency: string;
  event: string;
  actual?: string;
  forecast?: string;
  previous?: string;
  importance: 'low' | 'medium' | 'high';
  unit?: string;
}

export interface MarketDataPoint {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  marketCap?: number;
  high?: number;
  low?: number;
  open?: number;
  previousClose?: number;
  timestamp: string;
}

export interface MarketDataResponse {
  market: string;
  timestamp: string;
  data: MarketDataPoint[];
  summary: {
    totalVolume: number;
    averageChange: number;
    gainers: number;
    losers: number;
    unchanged: number;
  };
}

export interface FinancialStatement {
  symbol: string;
  period: 'annual' | 'quarterly';
  statementType: 'income' | 'balance' | 'cashflow';
  currency: string;
  data: Record<string, Record<string, number | string | null>>;
  metadata: {
    source: string;
    lastUpdated: string;
    fiscalYearEnd: string;
  };
}

export interface StockDividendInfo {
  symbol: string;
  dividends: Array<{
    date: string;
    amount: number;
    type: 'regular' | 'special' | 'stock';
    currency: string;
  }>;
  metadata: {
    source: string;
    lastUpdated: string;
  };
}

export interface StockSplitInfo {
  symbol: string;
  splits: Array<{
    date: string;
    ratio: string;
    numerator: number;
    denominator: number;
  }>;
  metadata: {
    source: string;
    lastUpdated: string;
  };
}

export interface DividendSchedule {
  symbol: string;
  companyName: string;
  exDate: string;
  payDate: string;
  amount: number;
  currency: string;
  yield?: number;
  type: 'regular' | 'special';
}

export interface EarningsCalendar {
  symbol: string;
  companyName: string;
  date: string;
  time?: string;
  epsEstimate?: number;
  epsActual?: number;
  revenueEstimate?: number;
  revenueActual?: number;
  surprise?: number;
  surprisePercent?: number;
}

export interface EconomicIndicator {
  name: string;
  date: string;
  value: number;
  unit: string;
  frequency: 'daily' | 'weekly' | 'monthly' | 'quarterly';
  category: 'inflation' | 'employment' | 'gdp' | 'consumer' | 'housing' | 'manufacturing' | 'trade' | 'monetary';
}

export interface EconomicIndicators {
  indicators: EconomicIndicator[];
  metadata: {
    source: 'FRED' | 'BLS' | 'BEA' | 'FederalReserve';
    lastUpdated: string;
    dateRange: { start: string; end: string };
  };
}
