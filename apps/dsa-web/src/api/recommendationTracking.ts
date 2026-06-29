import apiClient from './index';
import { toCamelCase } from './utils';

export interface RecommendationRecord {
  id: number;
  code: string;
  tradeDate: string;
  recommendationTime: string;
  signal: 'buy' | 'sell' | 'hold';
  recommendationPrice: number;
  currentPrice: number | null;
  priceDeviationPct: number | null;
  status: 'active' | 'closed' | 'expired';
  closePrice: number | null;
  closeDate: string | null;
  profitLossPct: number | null;
  source: string;
  sourceTaskId: string | null;
  reason: string;
  notes: string;
  createdAt: string;
  updatedAt: string;
  // 交易信号增强字段
  signalType: string;
  strategyPattern: string;
  confidence: number;
  entryMethod: string;
  stopLoss: number | null;
  takeProfit: number | null;
  sectors: string;
  sentimentPhase: string;
  expectedHoldDays: number | null;
  timeHorizon: string;
}

export interface RecommendationListResponse {
  total: number;
  page: number;
  limit: number;
  items: RecommendationRecord[];
}

export interface SignalStat {
  total: number;
  wins: number;
  winRate: number;
  avgPlPct: number;
}

export interface SourceStat {
  total: number;
  wins: number;
  winRate: number;
  avgPlPct: number;
}

export interface ActiveDeviationItem {
  id: number;
  code: string;
  tradeDate: string;
  signal: string;
  recommendationPrice: number;
  currentPrice: number;
  deviationPct: number;
}

export interface RecommendationStats {
  totalRecords: number;
  activeCount: number;
  closedCount: number;
  winRate: number;
  winCount: number;
  lossCount: number;
  avgPlPct: number;
  avgWinPlPct: number;
  avgLossPlPct: number;
  maxWinPct: number;
  maxLossPct: number;
  profitFactor: number;
  totalPlPct: number;
  bySignal: Record<string, SignalStat>;
  bySource: Record<string, SourceStat>;
  activeDeviation: ActiveDeviationItem[];
}

export interface SummaryResponse {
  stats: RecommendationStats;
  summary: string;
}

export interface CreateRecordParams {
  code: string;
  tradeDate: string;
  recommendationPrice: number;
  signal?: string;
  source?: string;
  sourceTaskId?: string;
  reason?: string;
}

export interface ListRecordsParams {
  code?: string;
  status?: string;
  signal?: string;
  source?: string;
  startDate?: string;
  endDate?: string;
  page?: number;
  limit?: number;
  tagFilter?: string;
}

// ── 共同点分析 ──────────────────────────────────────────────────

export interface CommonalityTag {
  key: string;
  label: string;
  value: string;
  count: number;
  category: string;
}

export interface CommonalityGroup {
  category: string;
  categoryLabel: string;
  tags: CommonalityTag[];
}

export interface CommonalityResponse {
  totalAnalyzed: number;
  groups: CommonalityGroup[];
}

export const recommendationTrackingApi = {
  /** 创建推荐记录 */
  createRecord: (params: CreateRecordParams) =>
    apiClient.post<RecommendationRecord>('/api/v1/recommendation-tracking/records', params)
      .then(res => toCamelCase<RecommendationRecord>(res.data)),

  /** 查询列表 */
  listRecords: (params: ListRecordsParams = {}) =>
    apiClient.get<RecommendationListResponse>('/api/v1/recommendation-tracking/records', { params })
      .then(res => toCamelCase<RecommendationListResponse>(res.data)),

  /** 获取单条详情 */
  getRecord: (id: number) =>
    apiClient.get<RecommendationRecord>(`/api/v1/recommendation-tracking/records/${id}`)
      .then(res => toCamelCase<RecommendationRecord>(res.data)),

  /** 更新记录 */
  updateRecord: (id: number, updates: Record<string, unknown>) =>
    apiClient.put<RecommendationRecord>(`/api/v1/recommendation-tracking/records/${id}`, updates)
      .then(res => toCamelCase<RecommendationRecord>(res.data)),

  /** 删除记录 */
  deleteRecord: (id: number) =>
    apiClient.delete<{ message: string; recordId: string }>(`/api/v1/recommendation-tracking/records/${id}`)
      .then(res => res.data),

  /** 平仓 */
  closeRecord: (id: number, closePrice: number) =>
    apiClient.post<RecommendationRecord>(`/api/v1/recommendation-tracking/records/${id}/close`, { close_price: closePrice })
      .then(res => toCamelCase<RecommendationRecord>(res.data)),

  /** 更新当前价格 */
  updatePrice: (id: number, currentPrice: number) =>
    apiClient.post<RecommendationRecord>(`/api/v1/recommendation-tracking/records/${id}/price`, { current_price: currentPrice })
      .then(res => toCamelCase<RecommendationRecord>(res.data)),

  /** 获取统计数据 */
  getStats: (startDate?: string, endDate?: string) =>
    apiClient.get<RecommendationStats>('/api/v1/recommendation-tracking/stats', {
      params: { start_date: startDate, end_date: endDate },
    }).then(res => toCamelCase<RecommendationStats>(res.data)),

  /** 生成自省总结 */
  generateSummary: (startDate?: string, endDate?: string) =>
    apiClient.post<SummaryResponse>('/api/v1/recommendation-tracking/summary', {
      start_date: startDate,
      end_date: endDate,
    }).then(res => toCamelCase<SummaryResponse>(res.data)),

  /** 获取推荐共同点分析 */
  getCommonality: (startDate?: string, endDate?: string, tagFilter?: string) =>
    apiClient.get<CommonalityResponse>('/api/v1/recommendation-tracking/commonality', {
      params: { start_date: startDate, end_date: endDate, tag_filter: tagFilter },
    }).then(res => toCamelCase<CommonalityResponse>(res.data)),
};
