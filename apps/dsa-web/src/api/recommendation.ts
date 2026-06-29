import apiClient from './index';
import { toCamelCase } from './utils';

// ── 1. 大盘走势 ──────────────────────────────────────────────────

export interface IndexItem {
  name: string;
  code: string;
  price: number;
  change: number;
  changePct: number;
  volume: number;
}

export interface TrendSeries {
  dates: string[];
  price: number[];
  ma5: number[];
  volume: number[];
}

export interface MarketTrendResponse {
  tradeDate: string;
  indices: IndexItem[];
  trend: TrendSeries;
  upCount: number;
  downCount: number;
  totalAmount: string;
  limitUpCount: number;
  limitDownCount?: number;
  dataSource?: string;
  isRealtime?: boolean;
}

// ── 2. 每日复盘 ──────────────────────────────────────────────────

export interface DailyStats {
  upCount: number;
  downCount: number;
  flatCount: number;
  limitUp: number;
  limitDown: number;
  northBoundNet: number;
  marginBalance?: number;
  turnover: number;
  amplitude: number;
}

export interface LhbItem {
  name: string;
  code: string;
  changePct?: number;
  buyAmount?: number;
  sellAmount?: number;
  netAmount?: number;
  reason?: string;
}

export interface BlockTradeData {
  todayCount: number;
  totalAmount?: number;
  topPremium: Array<{ name: string; code: string; premiumRate: number; amount?: number }>;
  topDiscount: Array<{ name: string; code: string; premiumRate: number; amount?: number }>;
}

export interface SectorLeader {
  sector: string;
  changePct: number;
  leader: string;
  leaderChangePct: number;
}

export interface DailyReviewResponse {
  tradeDate: string;
  stats: DailyStats;
  lhbTop: LhbItem[];
  blockTrade?: BlockTradeData;
  sectorLeaders: SectorLeader[];
}

// ── 3. 资金与板块热点 ────────────────────────────────────────────

export interface MoneyFlowItem {
  name: string;
  amount: number;
}

export interface NorthBoundItem {
  name: string;
  code: string;
  netInflow: number;
  direction: string;
}

export interface SectorRotationItem {
  sector: string;
  flowIn: number;
  flowOut: number;
  net: number;
  status: string;
}

export interface CapitalFlowResponse {
  tradeDate: string;
  moneyFlow: MoneyFlowItem[];
  northBound: NorthBoundItem[];
  sectorRotation: SectorRotationItem[];
  totalInflow: number;
  totalOutflow: number;
  todayNorthBound: number;
  totalAmount: string;
}

// ── 4. 短线打板标的 ──────────────────────────────────────────────

export interface ShortTermTarget {
  name: string;
  code: string;
  price: number;
  changePct: number;
  sealStrength: number;
  sealTime: string;
  premiumRate: number;
  rating: string;
  reason: string;
}

export interface ShortTermTargetsResponse {
  tradeDate: string;
  targets: ShortTermTarget[];
  limitUpCount: number;
}

// ── 5. 中长线波段建仓 ────────────────────────────────────────────

export interface MidLongTermPosition {
  name: string;
  code: string;
  price: number;
  targetPrice: number;
  stopLoss: number;
  valuation: string;
  peTtm?: number | null;
  pb?: number | null;
  roe?: number | null;
  trend: string;
  strategy: string;
  score: number;
}

export interface StrategyType {
  name: string;
  desc: string;
  color: string;
  count: number;
}

export interface MidLongTermResponse {
  tradeDate: string;
  positions: MidLongTermPosition[];
  strategies: StrategyType[];
}

// ── 6. 风控与仓位管理 ────────────────────────────────────────────

export interface SectorRisk {
  high: number;
  medium: number;
  low: number;
}

export interface PositionRiskItem {
  name: string;
  code: string;
  weight: number;
  stopLoss: number;
  currentPrice: number;
  atr: number;
  riskLevel: string;
  advice: string;
}

export interface RiskControlResponse {
  tradeDate: string;
  vix: number;
  marginBalance: number;
  marginChange?: number;
  forcedLiquidation: number;
  sectorRisk: SectorRisk;
  positionRisks: PositionRiskItem[];
  totalWeight: number;
}

// ── 7. 题材挖掘与龙头定性 ────────────────────────────────────────

export interface ThemeItem {
  name: string;
  hotness: number;
  trend: string;
  persistence: string;
  leaderStock: string;
  leaderChange: number;
  followerCount: number;
  catalyst: string;
  subThemes: string[];
  relatedStocks: string[];
}

export interface ThemeMiningResponse {
  tradeDate: string;
  themes: ThemeItem[];
  activeThemes: number;
  totalFollowers: number;
  mainTheme: string;
  hottestLeader: string;
}

// ── 8. 连板梯队与情绪周期 ────────────────────────────────────────

export interface LadderItem {
  rank: number;
  board: string;
  name: string;
  code: string;
  changePct: number;
  turnover: number;
  sealAmt: number;
  sentiment: string;
  strength: number;
}

export interface EmotionHistoryItem {
  date: string;
  phase: string;
  index: number;
}

export interface EmotionCycle {
  phase: string;
  phaseDesc: string;
  sentimentIndex: number;
  limitUpRatio: number;
  yesterdayPremium: number;
  nextDayRedRate: number;
  history: EmotionHistoryItem[];
}

export interface LimitUpLadderResponse {
  tradeDate: string;
  ladder: LadderItem[];
  emotion: EmotionCycle;
  totalLimitUp: number;
}

// ── 9. 多因子策略回测 ────────────────────────────────────────────

export interface FactorItem {
  name: string;
  ic: number | null;
  ir: number | null;
  rankIc: number | null;
  winRate: number | null;
  sharpe: number | null;
  status: string;
  source?: string;
}

export interface NavItem {
  date: string;
  nav: number;
}

export interface MultiFactorBacktestResponse {
  tradeDate: string;
  factors: FactorItem[];
  navCurve: NavItem[];
}

// ── 10. 持仓建议 ─────────────────────────────────────────────────

export interface PortfolioItem {
  name: string;
  code: string;
  weight: number;
  currentPrice: number;
  costPrice: number;
  pnl: number;
  advice: string;
  adviceReason?: string;
  targetWeight: number;
  diff: number;
  atrPct?: number;
  entrySignals?: string[];
}

export interface PositionAdviceResponse {
  tradeDate: string;
  portfolio: PortfolioItem[];
  totalWeight?: number;
  marketSentimentPhase?: string;
  suggestedTotalPosition?: string;
}

// ── API 方法 ─────────────────────────────────────────────────────

export const recommendationApi = {
  getMarketTrend: () =>
    apiClient.get<MarketTrendResponse>('/api/v1/recommendation/market-trend')
      .then(res => toCamelCase<MarketTrendResponse>(res.data)),

  getDailyReview: () =>
    apiClient.get<DailyReviewResponse>('/api/v1/recommendation/daily-review')
      .then(res => toCamelCase<DailyReviewResponse>(res.data)),

  getCapitalFlow: () =>
    apiClient.get<CapitalFlowResponse>('/api/v1/recommendation/capital-flow')
      .then(res => toCamelCase<CapitalFlowResponse>(res.data)),

  getShortTermTargets: () =>
    apiClient.get<ShortTermTargetsResponse>('/api/v1/recommendation/short-term')
      .then(res => toCamelCase<ShortTermTargetsResponse>(res.data)),

  getMidLongTerm: () =>
    apiClient.get<MidLongTermResponse>('/api/v1/recommendation/mid-long-term')
      .then(res => toCamelCase<MidLongTermResponse>(res.data)),

  getRiskControl: () =>
    apiClient.get<RiskControlResponse>('/api/v1/recommendation/risk-control')
      .then(res => toCamelCase<RiskControlResponse>(res.data)),

  getThemeMining: () =>
    apiClient.get<ThemeMiningResponse>('/api/v1/recommendation/theme-mining')
      .then(res => toCamelCase<ThemeMiningResponse>(res.data)),

  getLimitUpLadder: () =>
    apiClient.get<LimitUpLadderResponse>('/api/v1/recommendation/limit-up-ladder')
      .then(res => toCamelCase<LimitUpLadderResponse>(res.data)),

  getMultiFactorBacktest: () =>
    apiClient.get<MultiFactorBacktestResponse>('/api/v1/recommendation/multi-factor-backtest')
      .then(res => toCamelCase<MultiFactorBacktestResponse>(res.data)),

  getPositionAdvice: () =>
    apiClient.get<PositionAdviceResponse>('/api/v1/recommendation/position-advice')
      .then(res => toCamelCase<PositionAdviceResponse>(res.data)),
};
