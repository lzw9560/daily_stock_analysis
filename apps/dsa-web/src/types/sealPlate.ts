// ============ Seal Plate Types ============

export interface SealPlateStockResponse {
  code: string;
  name: string;
  closePrice: number;
  changePct: number;
  limitUpPrice: number;
  turnoverRate: number;
  volume: number;
  amount: number;
  sealAmount: number;
  sealTime: string | null;
  openCount: number;
  sector: string | null;
  reason: string | null;
  score: number;
  plateType: string;
  sealStrength: string;
}

export interface SectorHot {
  sector: string;
  count: number;
}

export interface SealPlateReportResponse {
  date: string;
  generatedAt: string;
  totalLimitUp: number;
  mainBoard: number;
  gem: number;
  star: number;
  strongStocks: SealPlateStockResponse[];
  watchStocks: SealPlateStockResponse[];
  leaderStocks: SealPlateStockResponse[];
  sectorHot: SectorHot[];
  marketSentiment: string;
  sentimentScore: number;
  warnings: string[];
}

export interface SealPlateHistoryItem {
  date: string;
  totalLimitUp: number;
  strongCount: number;
  sentiment: string;
  sentimentScore: number;
}

export interface SealPlateHistoryResponse {
  reports: SealPlateHistoryItem[];
}

export interface SealPlateStatsResponse {
  totalReports: number;
  avgLimitUp: number;
  avgSentiment: number;
}

// ============ 八项标准检查 ============

export interface EightStandardCheck {
  name: string;
  description: string;
  actualValue: string;
  expectedRange: string;
  passed: boolean;
  score: number;
}

export interface EightStandardCheckResult {
  code: string;
  name: string;
  totalScore: number;
  passedCount: number;
  failedCount: number;
  checks: EightStandardCheck[];
  riskLevel: 'low' | 'medium' | 'high';
  suggestion: string;
}

// ============ 情绪周期 ============

export interface SentimentAnalysis {
  sentimentIndex: number;
  phase: string;
  phaseLabel: string;
  suggestedPosition: number;
  positionRange: string;
  strategy: string;
  warning: string | null;
  indicators: Record<string, number>;
}

// ============ 股票池 ============

export interface StockPoolItem {
  code: string;
  name: string;
  score: number;
  changePct: number;
  sealTime: string | null;
  sealAmount: number;
  sector: string | null;
  poolType: 'first_board' | 'continuous' | 'weak_to_strong' | 'reversal';
}

export interface StockPool {
  firstBoardPool: StockPoolItem[];
  continuousPool: StockPoolItem[];
  weakToStrongPool: StockPoolItem[];
  reversalPool: StockPoolItem[];
}

// ============ 龙虎榜 ============

export interface SeatInfo {
  name: string;
  amount: number;
  type: string;
}

export interface DragonTigerItem {
  code: string;
  name: string;
  rank: number;
  reason: string;
  changePct: number;
  closePrice: number;
  volume: number;
  amount: number;
  turnoverRate: number;
  sealAmount: number;
  sealTime: string | null;
  openCount: number;
  score: number;
  sector: string | null;
  buySeats: SeatInfo[];
  sellSeats: SeatInfo[];
  netBuy: number;
  date: string;
}

export interface DragonTigerList {
  date: string;
  totalCount: number;
  items: DragonTigerItem[];
}

// ============ 风险预警 ============

export interface RiskCondition {
  type: string;
  level: 'red' | 'yellow';
  message: string;
}

export interface RiskAlert {
  code: string;
  name: string;
  score: number;
  conditions: RiskCondition[];
  maxLevel: 'red' | 'yellow';
}

export interface RiskAlertsResponse {
  alerts: RiskAlert[];
}

// ============ 新增：日期 + 推荐 + 胜率 ============

export interface EffectiveDateResponse {
  date: string;
  label: string;
  isClosed: boolean;
}

export interface PositionRecResponse {
  code: string;
  name: string;
  score: number;
  rank: number;
  confidence: string;         // 高/中/低
  changePct: number;
  sealTime: string | null;
  sector: string | null;
  sealAmount: number;
  consecutiveDays: number;
  reasons: string[];
  riskWarnings: string[];
  suggestedPositionPct: number;
}

export interface SectorWinRate {
  sector: string;
  won: number;
  total: number;
  rate: number;
}

export interface WinRateResponse {
  totalRecommendations: number;
  settled: number;
  won: number;
  lost: number;
  pending: number;
  winRate: number;
  avgReturn: number;
  maxReturn: number;
  rollingWinRate10: number;
  trend: string;
  bySector: SectorWinRate[];
  byScoreRange: Record<string, { won: number; total: number; rate: number }>;
  strategyAdjustments: string[];
  adjustmentReasons: string[];
}

export interface RecommendationResponse {
  date: string;
  label: string;
  sentimentIndex: number;
  sentimentPhase: string;
  totalLimitUp: number;
  recommendations: PositionRecResponse[];
  strategyNotes: string[];
  winRate: WinRateResponse | null;
}

export interface RecommendationHistoryItem {
  date: string;
  label: string;
  count: number;
  sentimentPhase: string;
  sentimentIndex: number;
}

export interface RecommendationHistoryList {
  items: RecommendationHistoryItem[];
}

export interface RecommendationDetail {
  date: string;
  label: string;
  sentimentIndex: number;
  sentimentPhase: string;
  totalLimitUp: number;
  recommendations: (PositionRecResponse & {
    outcome: string | null;
    actualReturnPct: number | null;
    won: boolean | null;
    reviewNote: string | null;
  })[];
}

// ============ 数据源健康检查 ============

export interface DataSourceSourceInfo {
  available: boolean;
  successRate: number;
  lastError?: string;
}

export interface DataSourceHealthResponse {
  totalSources: number;
  availableSources: number;
  status: string; // "healthy" | "degraded" | "unhealthy"
  sources: Record<string, DataSourceSourceInfo>;
}

// ============ 市场热度分析 ============

export interface MarketHotAnalysisResponse {
  hotConcepts: { name: string; heat: number; change: number; reason: string }[];
  fundInflowSectors: { name: string; netInflow: number; changePct: number }[];
  fundOutflowSectors: { name: string; netInflow: number; changePct: number }[];
  marketHeatScore: number;
  marketFocus: string;
  sentimentSignal: string;
  suggestedSectors: string[];
}

// ============ 问财选股 ============

export interface IwenCaiScreeningRequest {
  query: string;
  topN: number;
}

export interface IwenCaiScreeningResponse {
  query: string;
  count: number;
  results: Record<string, unknown>[];
}

// ============ 复盘分析 ============

export interface ReviewHistoryItem {
  date: string;
  summary: string;
  winRate: number;
  settledCount: number;
  hasLlmAnalysis: boolean;
}

export interface ReviewHistoryListResponse {
  items: ReviewHistoryItem[];
}

export interface ReviewDetailResponse {
  date: string;
  generatedAt: string;
  summary: string;
  overallAssessment: string;
  successPatterns: string[];
  failurePatterns: string[];
  highMomentumSectors: string[];
  riskSectors: string[];
  strategyAdjustments: string[];
  scoreWeightSuggestions: string[];
  positionAdvice: string;
  recommendedMinScore: number;
  recommendedConfidenceThreshold: string;
  maxDailyRecommendations: number;
  settledCount: number;
  winRate: number;
  avgReturn: number;
  modelUsed: string;
  notes: string;
}

export interface StrategyEvolutionResponse {
  evolution: {
    date: string;
    minScore: number;
    confidence: string;
    maxRecs: number;
    winRate: number;
    summary: string;
    adjustments: string[];
  }[];
}

export interface AutoReviewResponse {
  status: string;
  date: string;
  autoSettled: number;
  llmAnalysis: boolean;
  message: string;
}

// ============ 资金流向分析 ============

export interface BuySuggestion {
  code: string;
  name: string;
  score: number;
  sector: string;
  buyPoint: {
    entryRange: string;
    idealEntry: string;
    strategy: string;
    maxPositionPct: number;
  };
  stopLoss: {
    price: string;
    pct: string;
    rule: string;
  };
  targetPrice: {
    price: string;
    pct: string;
    holdDays: string;
  };
  confidence: string;
}

export interface SellSuggestion {
  code: string;
  name: string;
  reason: string;
  urgency: string;
}

export interface FundFlowResponse {
  date: string;
  fundSentiment: string;
  fundHeatScore: number;
  hotSectorsInflow: { name: string; netInflow: number }[];
  hotSectorsOutflow: { name: string; netInflow: number }[];
  hotMoneyActive: boolean;
  hotMoneyWarning: string[];
  oneDayTourRisk: string[];
  majorFundFocus: string[];
  buySuggestions: BuySuggestion[];
  sellSuggestions: SellSuggestion[];
  riskAlerts: string[];
}

export interface MorningTaskResponse {
  status: string;
  date: string;
  recommendationsCount: number;
  feishuSent: boolean;
  message: string;
}

export interface EveningTaskResponse {
  status: string;
  date: string;
  autoSettled: number;
  llmAnalysis: boolean;
  feishuSent: boolean;
  message: string;
}

// ============ 高胜率战法 ============

export interface StrategyEntryMode {
  name: string;
  desc: string;
  winRate: number;
}

export interface StrategyItem {
  id: string;
  name: string;
  type: string;
  description: string;
  winRate: number;
  suitableMarket: string[];
  unsuitableMarket: string[];
  conditions: string[];
  entryModes: StrategyEntryMode[];
  riskControl: string[];
  currentSuitability: number;
  currentReason: string;
}

export interface StrategyCandidate {
  code: string;
  name: string;
  sector: string | null;
  changePct: number;
  matchScore: number;
  matchReason: string;
}

export interface StrategyResponse {
  strategies: StrategyItem[];
  marketPhase: string;
  marketHeat: number;
  updatedAt: string;
}

export interface StrategyCandidatesResponse {
  strategyId: string;
  candidates: StrategyCandidate[];
}

// ============ 多战法匹配重点推荐 ============

export interface MultiMatchEntryPoint {
  price: number;
  type: string;
  condition: string;
  positionPct: number;
}

export interface MultiMatchAnalysis {
  code: string;
  name: string;
  sector: string | null;
  matchedStrategies: string[];
  matchCount: number;
  avgMatchScore: number;
  reasons: string[];
  entryPoints: MultiMatchEntryPoint[];
  buyAnalysis: string;
  sellAnalysis: string;
  riskLevel: 'low' | 'medium' | 'high';
  compositeScore: number;
}

export interface MultiMatchResponse {
  recommendations: MultiMatchAnalysis[];
  totalMatched: number;
  multiMatchedCount: number;
  marketPhase: string;
  updatedAt: string;
}

// ============ 持仓 ============

export interface PositionItem {
  code: string;
  name: string;
  totalQty: number;
  availableQty: number;
  currentPrice: number;
  costPrice: number;
  totalPnl: number;
  dailyPnl: number;
}

export interface HoldingsResponse {
  positions: PositionItem[];
  totalPnl: number;
  totalDailyPnl: number;
  totalMarketValue: number;
  totalCost: number;
  updatedAt?: string;
}

// ============ 个股风险分析 ============

export interface StockRiskAnalysisResponse {
  code: string;
  name: string;
  riskLevel: 'low' | 'medium' | 'high';
  riskScore: number;
  hotMoneyRisk: string[];
  oneDayTourRisk: string[];
  sealQuality: string;
  turnoverWarning: string | null;
  suggestions: string[];
}

// ============ 自选股 ============

export interface WatchlistItem {
  code: string;
  name: string;
  addedAt: string;
  source: string;
  score: number;
  sector: string | null;
}

export interface WatchlistResponse {
  items: WatchlistItem[];
  total: number;
}

export interface WatchlistStatusResponse {
  codes: string[];
}

// ============ 推荐建仓管理 ============

export interface RecommendationRecordResponse {
  date: string;
  label: string;
  generatedAt: string;
  code: string;
  name: string;
  score: number;
  changePct: number;
  sealTime: string | null;
  sector: string | null;
  sealAmount: number;
  reasons: string[];
  outcome: string | null;
  actualReturnPct: number | null;
  won: boolean | null;
  reviewNote: string | null;
  sentimentPhase: string;
  sentimentIndex: number;
}

export interface RecommendationRecordListResponse {
  items: RecommendationRecordResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface DailyWinRateItemResponse {
  date: string;
  label: string;
  totalCount: number;
  settledCount: number;
  wonCount: number;
  lostCount: number;
  pendingCount: number;
  winRate: number;
  avgReturn: number;
  maxReturn: number;
  minReturn: number;
  sentimentPhase: string;
  sentimentIndex: number;
  recommendations: {
    code: string;
    name: string;
    score: number;
    changePct: number;
    sealTime: string | null;
    sector: string | null;
    reasons: string[];
    outcome: string | null;
    actualReturnPct: number | null;
    won: boolean | null;
    reviewNote: string | null;
  }[];
}

export interface WinRateBacktestResponse {
  dailyRecords: DailyWinRateItemResponse[];
  overallWinRate: number;
  totalRecommendations: number;
  totalSettled: number;
  totalWon: number;
  avgReturn: number;
  bestDay: {
    date: string;
    winRate: number;
    settledCount: number;
    wonCount: number;
  } | null;
  worstDay: {
    date: string;
    winRate: number;
    settledCount: number;
    wonCount: number;
  } | null;
}

export interface HistoricalWinRateResponse {
  targetDate: string;
  targetDetail: {
    date: string;
    label: string;
    totalCount: number;
    settledCount: number;
    wonCount: number;
    lostCount: number;
    pendingCount: number;
    winRate: number;
    sentimentPhase: string;
    sentimentIndex: number;
    recommendations: {
      code: string;
      name: string;
      score: number;
      changePct: number;
      sealTime: string | null;
      sector: string | null;
      reasons: string[];
      outcome: string | null;
      actualReturnPct: number | null;
      won: boolean | null;
      reviewNote: string | null;
    }[];
  } | null;
  trend: {
    date: string;
    label: string;
    count: number;
    settled: number;
    won: number;
    winRate: number;
    isTarget: boolean;
  }[];
  lookbackDays: number;
  overallStats: {
    totalRecommendations: number;
    settled: number;
    won: number;
    lost: number;
    pending: number;
    winRate: number;
    avgReturn: number;
    rollingWinRate10: number;
    trend: string;
  };
}

export interface AvailableDatesResponse {
  dates: {
    date: string;
    label: string;
    count: number;
    settled: number;
    won: number;
    winRate: number | null;
    sentimentPhase: string;
  }[];
}

// ============ 综合推荐系统 ============

export interface BuySellAnalysis {
  code: string;
  name: string;
  buyWillingness: number;
  sellWillingness: number;
  idealBuyPrice: number;
  buyRangeLow: number;
  buyRangeHigh: number;
  stopLossPrice: number;
  takeProfitShort: number;
  takeProfitLong: number;
  entryStrategy: string;
  exitStrategy: string;
  buySignals: string[];
  sellSignals: string[];
}

export interface TermAdvice {
  term: string;
  label: string;
  action: string;
  confidence: string;
  targetReturnPct: number;
  holdDays: string;
  strategyDesc: string;
  riskLevel: string;
  keyLevels: string[];
}

export interface SectorRotation {
  hotSectors: { name: string; count: number; status?: string; heat?: number }[];
  coolingSectors: { name: string; count?: number; netOutflow?: number; status?: string }[];
  nextPotentialSectors: { name: string; historicalWinRate?: number; reason: string }[];
  rotationPhase: string;
  rotationScore: number;
  hotMoneyFocus: string[];
  institutionFocus: string[];
  suggestions: string[];
}

export interface RiskAssessment {
  overallRiskScore: number;
  overallRiskLevel: string;
  marketRisk: number;
  positionRisk: number;
  sectorConcentrationRisk: number;
  liquidityRisk: number;
  sentimentRisk: number;
  riskFactors: string[];
  riskMitigations: string[];
  maxRecommendedPosition: number;
}

export interface IndividualStockRisk {
  code: string;
  name: string;
  riskScore: number;
  riskLevel: string;
  valuationRisk: number;
  technicalRisk: number;
  fundFlowRisk: number;
  sentimentRisk: number;
  sectorRisk: number;
  liquidityRisk: number;
  blackSwanRisk: number;
  riskItems: { type: string; level: string; desc: string }[];
  suggestions: string[];
  positionLimitPct: number;
}

export interface DynamicPosition {
  totalCapital: number;
  currentPositionPct: number;
  targetPositionPct: number;
  maxPositionPct: number;
  cashReservePct: number;
  stockWeights: {
    code: string;
    name: string;
    weightPct: number;
    weight?: number;       // 兼容旧字段名
    suggestedPct?: number;
    suggestion?: string;   // 兼容旧字段名
    confidence?: string;
  }[];
  adjustmentReason: string;
  rebalancingNeeded: boolean;
}

export interface FactorCorrelation {
  factorName: string;
  currentValue: number;
  zScore: number;
  correlationWithMarket: number;
  status: string;
  warningMsg: string;
}

export interface StressTestResult {
  scenario: string;
  maxDrawdownPct: number;
  portfolioLossPct: number;
  recoveryDaysEst: number;
  circuitBreakerTriggered: boolean;
  circuitBreakerLevel: string;
  suggestedAction: string;
  impactOnHoldings: { code: string; name: string; loss: number }[];
}

export interface ComprehensiveRecommendationResponse {
  date: string;
  label: string;
  generatedAt: string;
  sentimentIndex: number;
  sentimentPhase: string;
  totalLimitUp: number;
  marketHeatScore: number;
  fundSentiment: string;
  buySellAnalyses: BuySellAnalysis[];
  termAdvices: TermAdvice[];
  sectorRotation: SectorRotation | null;
  riskAssessment: RiskAssessment | null;
  individualStockRisks: IndividualStockRisk[];
  dynamicPosition: DynamicPosition | null;
  factorCorrelations: FactorCorrelation[];
  stressTestResults: StressTestResult[];
  strategyAdjustments: string[];
  adjustmentReasons: string[];
  winRateInfo: Record<string, unknown>;
}

export interface WinRateBriefResponse {
  total: number;
  settled: number;
  won: number;
  lost: number;
  pending: number;
  winRate: number;
  avgReturn: number;
  rolling10: number;
  trend: string;
  bySector: Record<string, { won: number; total: number; rate: number }>;
}
