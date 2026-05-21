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
  reason: string;
  buySeats: SeatInfo[];
  sellSeats: SeatInfo[];
  netBuy: number;
  date: string;
}

export interface DragonTigerList {
  date: string;
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
