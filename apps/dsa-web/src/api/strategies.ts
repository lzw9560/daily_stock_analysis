import apiClient from './index';
import { toCamelCase } from './utils';

export type SignalType = 'buy' | 'sell' | 'alert';
export type EntryMethod = 'market' | 'limit' | 'breakout' | 'pullback' | 'bidding';

export interface StrategySignal {
  id: string;
  code: string;
  name: string;
  strategy: string;
  strategyName: string;
  signalType: SignalType;
  entryMethod: EntryMethod;
  confidence: number;
  entryPrice: number;
  currentPrice: number;
  stopLoss: number;
  takeProfit: number;
  maxPositionPct: number;
  sector: string;
  sentimentPhase: string;
  reason: string;
  riskLevel: 'low' | 'medium' | 'high';
  createdAt: string;
}

export interface StrategyScanRequest {
  strategies?: string[];
  minConfidence?: number;
  sector?: string;
  signalType?: SignalType;
}

export interface StrategyPerformance {
  strategy: string;
  strategyName: string;
  totalSignals: number;
  winRate: number;
  avgPnl: number;
  profitFactor: number;
  maxDrawdown: number;
  sharpeRatio: number;
  lastMonthWinRate: number;
}

export interface StrategySignalsResponse {
  signals: StrategySignal[];
  total: number;
  strategies: StrategyPerformance[];
}

export const strategiesApi = {
  /** 扫描策略信号 */
  scanSignals: async (params?: StrategyScanRequest): Promise<StrategySignalsResponse> => {
    const response = await apiClient.post<StrategySignalsResponse>(
      '/api/v1/strategies/scan',
      params || {}
    );
    return toCamelCase<StrategySignalsResponse>(response.data);
  },

  /** 获取策略绩效 */
  getPerformance: async (): Promise<{ strategies: StrategyPerformance[] }> => {
    const response = await apiClient.get<{ strategies: StrategyPerformance[] }>(
      '/api/v1/strategies/performance'
    );
    return toCamelCase<{ strategies: StrategyPerformance[] }>(response.data);
  },

  /** 获取板块轮动数据 */
  getSectorRotation: async (): Promise<{
    sectors: { sector: string; strength: number; rank: number; stocks: string[] }[];
    mainline: string[];
    rotationSignals: { from: string; to: string; confidence: number }[];
  }> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/strategies/sector-rotation'
    );
    return toCamelCase(response.data) as unknown as {
      sectors: { sector: string; strength: number; rank: number; stocks: string[] }[];
      mainline: string[];
      rotationSignals: { from: string; to: string; confidence: number }[];
    };
  },
};
