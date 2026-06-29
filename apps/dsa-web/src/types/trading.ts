// ============ 交易工作台类型 ============

/** 工作流阶段 */
export type WorkflowPhase =
  | 'pre_market'
  | 'bidding'
  | 'morning_session'
  | 'lunch_break'
  | 'afternoon_session'
  | 'closing_auction'
  | 'post_market';

export interface WorkflowTask {
  id: string;
  name: string;
  description: string;
  phase: WorkflowPhase;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  dependencies: string[];
  result?: string;
  error?: string;
  startedAt?: string;
  completedAt?: string;
}

export interface TradingPlan {
  date: string;
  phase: WorkflowPhase;
  marketAssessment: string;
  sentimentSummary: string;
  sectorFocus: string[];
  tradingBias: 'bullish' | 'bearish' | 'neutral' | 'cautious';
  suggestedPositions: SuggestedPosition[];
  riskWarnings: string[];
  keyEvents: string[];
}

export interface SuggestedPosition {
  code: string;
  name: string;
  action: 'buy' | 'sell' | 'hold' | 'watch';
  positionPct: number;
  entryPriceRange: [number, number];
  stopLoss: number;
  takeProfit: number;
  reason: string;
  strategy: string;
  confidence: number;
}

export interface TradingAlert {
  id: string;
  type: string;
  title: string;
  message: string;
  severity: 'info' | 'warning' | 'danger' | 'critical';
  code?: string;
  price?: number;
  createdAt: string;
  acknowledged: boolean;
}

export interface WorkflowStatus {
  currentPhase: WorkflowPhase;
  phaseProgress: number;
  tasks: WorkflowTask[];
  plan: TradingPlan | null;
  alerts: TradingAlert[];
  activeOrders: number;
  activePositions: number;
}

export interface TradingWorkbenchResponse {
  status: WorkflowStatus;
  serverTime: string;
}
