import apiClient from './index';
import { toCamelCase } from './utils';
import type { SentimentAnalysis } from '../types/sealPlate';

export interface SentimentDashboardResponse {
  current: SentimentAnalysis;
  history: SentimentHistoryPoint[];
  phaseDistribution: PhaseDistribution;
  indicatorRadar: IndicatorRadarItem[];
  keySignals: string[];
}

export interface SentimentHistoryPoint {
  date: string;
  sentimentIndex: number;
  phase: string;
  phaseLabel: string;
}

export interface PhaseDistribution {
  phases: { phase: string; label: string; count: number; ratio: number }[];
}

export interface IndicatorRadarItem {
  name: string;
  value: number;
  weight: number;
  description: string;
}

export interface SectorStockBrief {
  code: string;
  name: string;
  changePct: number;
  isLeader: boolean;
}

export interface FlowPrediction {
  direction: string;
  confidence: string;
  reason: string;
  nextDayProbability: number;
}

export interface SectorHeatmapItem {
  sector: string;
  strength: number;
  limitUpCount: number;
  changePct: number;
  netInflow: number;
  mainline: boolean;
  trend: 'accelerating' | 'steady' | 'cooling' | 'reversing';
  trendScore: number;
  consecutiveDays: number;
  flowPrediction: FlowPrediction;
  stocks: SectorStockBrief[];
}

export interface SectorHeatmapSummary {
  totalSectors: number;
  upCount: number;
  downCount: number;
  totalNetInflow: number;
  hotMoneyDirection: string;
  marketSentiment: string;
  rotationSignal: string;
}

export interface TopFlowItem {
  name: string;
  amount: number;
  changePct: number;
}

export interface RotationSignal {
  fromSector: string;
  fromChange: number;
  fromFlow: number;
  toSector: string;
  toChange: number;
  toFlow: number;
  flowAmount: number;
  rotationScore: number;
  description: string;
  signal: 'high' | 'medium' | 'low';
}

export interface SectorHeatmapResponse {
  generatedAt: string;
  sectors: SectorHeatmapItem[];
  summary: SectorHeatmapSummary;
  topInflows: TopFlowItem[];
  topOutflows: TopFlowItem[];
  rotations: RotationSignal[];
}

export const sentimentApi = {
  /** 获取情绪看板数据 */
  getDashboard: async (date?: string): Promise<SentimentDashboardResponse> => {
    const response = await apiClient.get<SentimentDashboardResponse>(
      '/api/v1/sentiment/dashboard',
      { params: date ? { date } : {} }
    );
    return toCamelCase<SentimentDashboardResponse>(response.data);
  },

  /** 获取情绪历史 */
  getHistory: async (params: {
    days?: number;
  } = {}): Promise<{ history: SentimentHistoryPoint[] }> => {
    const response = await apiClient.get<{ history: SentimentHistoryPoint[] }>(
      '/api/v1/sentiment/history',
      { params }
    );
    return toCamelCase<{ history: SentimentHistoryPoint[] }>(response.data);
  },

  /** 获取板块热力图数据（含趋势变化、资金流向推测） */
  getSectorHeatmap: async (): Promise<SectorHeatmapResponse> => {
    const response = await apiClient.get<SectorHeatmapResponse>(
      '/api/v1/sentiment/sector-heatmap'
    );
    return toCamelCase<SectorHeatmapResponse>(response.data);
  },
};
