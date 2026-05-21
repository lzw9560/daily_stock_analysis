import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  SealPlateReportResponse,
  SealPlateHistoryResponse,
  SealPlateStatsResponse,
  EightStandardCheckResult,
  SentimentAnalysis,
  StockPool,
  DragonTigerList,
  RiskAlertsResponse,
} from '../types/sealPlate';

// ============ API ============

export const sealPlateApi = {
  /**
   * 获取打板分析报告
   */
  getReport: async (params: {
    date?: string;
    minScore?: number;
  } = {}): Promise<SealPlateReportResponse> => {
    const queryParams: Record<string, string | number> = {};
    if (params.date) queryParams.date = params.date;
    if (params.minScore) queryParams.min_score = params.minScore;

    const response = await apiClient.get<SealPlateReportResponse>(
      '/api/v1/seal-plate/report',
      { params: queryParams }
    );
    return toCamelCase<SealPlateReportResponse>(response.data);
  },

  /**
   * 运行打板分析
   */
  runAnalysis: async (params: {
    date?: string;
    force?: boolean;
    minScore?: number;
  } = {}): Promise<SealPlateReportResponse> => {
    const requestData: Record<string, unknown> = {};
    if (params.date) requestData.date = params.date;
    if (params.force) requestData.force = params.force;
    if (params.minScore) requestData.min_score = params.minScore;

    const response = await apiClient.post<SealPlateReportResponse>(
      '/api/v1/seal-plate/run',
      requestData
    );
    return toCamelCase<SealPlateReportResponse>(response.data);
  },

  /**
   * 获取历史报告列表
   */
  getHistory: async (limit: number = 10): Promise<SealPlateHistoryResponse> => {
    const response = await apiClient.get<SealPlateHistoryResponse>(
      '/api/v1/seal-plate/history',
      { params: { limit } }
    );
    return toCamelCase<SealPlateHistoryResponse>(response.data);
  },

  /**
   * 获取统计数据
   */
  getStats: async (): Promise<SealPlateStatsResponse> => {
    const response = await apiClient.get<SealPlateStatsResponse>(
      '/api/v1/seal-plate/stats'
    );
    return toCamelCase<SealPlateStatsResponse>(response.data);
  },

  /**
   * 检查股票八项标准
   */
  checkEightStandard: async (stockCode: string, date?: string): Promise<EightStandardCheckResult> => {
    const queryParams: Record<string, string> = {};
    if (date) queryParams.date = date;

    const response = await apiClient.get<EightStandardCheckResult>(
      `/api/v1/seal-plate/eight-standard/${stockCode}`,
      { params: queryParams }
    );
    return toCamelCase<EightStandardCheckResult>(response.data);
  },

  /**
   * 获取情绪周期分析
   */
  getSentiment: async (date?: string): Promise<SentimentAnalysis> => {
    const queryParams: Record<string, string> = {};
    if (date) queryParams.date = date;

    const response = await apiClient.get<SentimentAnalysis>(
      '/api/v1/seal-plate/sentiment',
      { params: queryParams }
    );
    return toCamelCase<SentimentAnalysis>(response.data);
  },

  /**
   * 获取候选股票池
   */
  getStockPool: async (date?: string): Promise<StockPool> => {
    const queryParams: Record<string, string> = {};
    if (date) queryParams.date = date;

    const response = await apiClient.get<StockPool>(
      '/api/v1/seal-plate/stock-pool',
      { params: queryParams }
    );
    return toCamelCase<StockPool>(response.data);
  },

  /**
   * 获取龙虎榜
   */
  getDragonTiger: async (date?: string): Promise<DragonTigerList> => {
    const queryParams: Record<string, string> = {};
    if (date) queryParams.date = date;

    const response = await apiClient.get<DragonTigerList>(
      '/api/v1/seal-plate/dragon-tiger',
      { params: queryParams }
    );
    return toCamelCase<DragonTigerList>(response.data);
  },

  /**
   * 获取风险预警
   */
  getRiskAlerts: async (date?: string): Promise<RiskAlertsResponse> => {
    const queryParams: Record<string, string> = {};
    if (date) queryParams.date = date;

    const response = await apiClient.get<RiskAlertsResponse>(
      '/api/v1/seal-plate/risk-alert',
      { params: queryParams }
    );
    return toCamelCase<RiskAlertsResponse>(response.data);
  },
};
