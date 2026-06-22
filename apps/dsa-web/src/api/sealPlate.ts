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
  EffectiveDateResponse,
  RecommendationResponse,
  RecommendationHistoryList,
  RecommendationDetail,
  WinRateResponse,
  DataSourceHealthResponse,
  MarketHotAnalysisResponse,
  IwenCaiScreeningRequest,
  IwenCaiScreeningResponse,
  ReviewDetailResponse,
  ReviewHistoryListResponse,
  StrategyEvolutionResponse,
  AutoReviewResponse,
  FundFlowResponse,
  MorningTaskResponse,
  EveningTaskResponse,
  StrategyResponse,
  StrategyCandidatesResponse,
  MultiMatchResponse,
  HoldingsResponse,
  StockRiskAnalysisResponse,
  WatchlistResponse,
  WatchlistStatusResponse,
  WatchlistItem,
  RecommendationRecordListResponse,
  WinRateBacktestResponse,
  HistoricalWinRateResponse,
  AvailableDatesResponse,
  ComprehensiveRecommendationResponse,
  WinRateBriefResponse,
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
  getDragonTiger: async (params: { date?: string; minScore?: number } = {}): Promise<DragonTigerList> => {
    const queryParams: Record<string, string | number> = {};
    if (params.date) queryParams.date = params.date;
    if (params.minScore !== undefined) queryParams.min_score = params.minScore;

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

  // ============ 新增：日期 + 推荐 + 胜率 ============

  /**
   * 获取有效日期
   */
  getEffectiveDate: async (): Promise<EffectiveDateResponse> => {
    const response = await apiClient.get<EffectiveDateResponse>(
      '/api/v1/seal-plate/effective-date'
    );
    return toCamelCase<EffectiveDateResponse>(response.data) as EffectiveDateResponse;
  },

  /**
   * 获取建仓推荐
   */
  getRecommendations: async (params: {
    date?: string;
    save?: boolean;
  } = {}): Promise<RecommendationResponse> => {
    const queryParams: Record<string, string | boolean> = {};
    if (params.date) queryParams.date = params.date;
    if (params.save !== undefined) queryParams.save = params.save;

    const response = await apiClient.get<RecommendationResponse>(
      '/api/v1/seal-plate/recommendations',
      { params: queryParams }
    );
    return toCamelCase<RecommendationResponse>(response.data);
  },

  /**
   * 获取推荐历史列表
   */
  getRecommendationHistory: async (limit: number = 30): Promise<RecommendationHistoryList> => {
    const response = await apiClient.get<RecommendationHistoryList>(
      '/api/v1/seal-plate/recommendations/history',
      { params: { limit } }
    );
    return toCamelCase<RecommendationHistoryList>(response.data);
  },

  /**
   * 获取指定日期推荐详情
   */
  getRecommendationDetail: async (date: string): Promise<RecommendationDetail> => {
    const response = await apiClient.get<RecommendationDetail>(
      `/api/v1/seal-plate/recommendations/${date}`
    );
    return toCamelCase<RecommendationDetail>(response.data);
  },

  /**
   * 更新推荐结果（复盘）
   */
  updateRecommendationOutcome: async (
    date: string, code: string,
    data: { outcome: string; actualReturnPct?: number; reviewNote?: string }
  ) => {
    const response = await apiClient.patch(
      `/api/v1/seal-plate/recommendations/${date}/${code}`,
      data
    );
    return response.data;
  },

  /**
   * 获取胜率统计
   */
  getWinRate: async (): Promise<WinRateResponse> => {
    const response = await apiClient.get<WinRateResponse>(
      '/api/v1/seal-plate/win-rate'
    );
    return toCamelCase<WinRateResponse>(response.data);
  },

  // ============ 数据源健康 & 市场热度 ============

  /**
   * 获取数据源健康状态
   */
  getDataSourcesHealth: async (): Promise<DataSourceHealthResponse> => {
    const response = await apiClient.get<DataSourceHealthResponse>(
      '/api/v1/seal-plate/data-sources/health'
    );
    return toCamelCase<DataSourceHealthResponse>(response.data);
  },

  /**
   * 获取市场热度分析
   */
  getMarketHot: async (): Promise<MarketHotAnalysisResponse> => {
    const response = await apiClient.get<MarketHotAnalysisResponse>(
      '/api/v1/seal-plate/market-hot'
    );
    return toCamelCase<MarketHotAnalysisResponse>(response.data);
  },

  /**
   * 问财自然语言选股
   */
  iwencaiScreen: async (request: IwenCaiScreeningRequest): Promise<IwenCaiScreeningResponse> => {
    const response = await apiClient.post<IwenCaiScreeningResponse>(
      '/api/v1/seal-plate/iwencai/screen',
      { query: request.query, top_n: request.topN }
    );
    return toCamelCase<IwenCaiScreeningResponse>(response.data);
  },

  /**
   * 问财获取近期连续涨停股
   */
  getIwenCaiRecentLimitUp: async (days: number = 2) => {
    const response = await apiClient.get(
      '/api/v1/seal-plate/iwencai/recent-limit-up',
      { params: { days } }
    );
    return response.data;
  },

  /**
   * 问财获取强势股
   */
  getIwenCaiStrongStocks: async () => {
    const response = await apiClient.get(
      '/api/v1/seal-plate/iwencai/strong-stocks'
    );
    return response.data;
  },

  // ============ 复盘分析 ============

  /**
   * 获取复盘分析详情
   */
  getReviewDetail: async (date?: string): Promise<ReviewDetailResponse> => {
    const response = await apiClient.get<ReviewDetailResponse>(
      '/api/v1/seal-plate/review',
      { params: date ? { date } : {} }
    );
    return toCamelCase<ReviewDetailResponse>(response.data);
  },

  /**
   * 获取复盘历史列表
   */
  getReviewHistory: async (limit: number = 30): Promise<ReviewHistoryListResponse> => {
    const response = await apiClient.get<ReviewHistoryListResponse>(
      '/api/v1/seal-plate/review/history',
      { params: { limit } }
    );
    return toCamelCase<ReviewHistoryListResponse>(response.data);
  },

  /**
   * 触发自动复盘
   */
  triggerAutoReview: async (date?: string): Promise<AutoReviewResponse> => {
    const response = await apiClient.post<AutoReviewResponse>(
      '/api/v1/seal-plate/review/auto-review',
      { date: date || undefined }
    );
    return toCamelCase<AutoReviewResponse>(response.data);
  },

  /**
   * 获取策略演化时间线
   */
  getStrategyEvolution: async (limit: number = 30): Promise<StrategyEvolutionResponse> => {
    const response = await apiClient.get<StrategyEvolutionResponse>(
      '/api/v1/seal-plate/review/strategy-evolution',
      { params: { limit } }
    );
    return toCamelCase<StrategyEvolutionResponse>(response.data);
  },

  /**
   * 更新复盘备注
   */
  updateReviewNotes: async (date: string, notes: string) => {
    const response = await apiClient.patch(
      `/api/v1/seal-plate/review/${date}/notes`,
      { notes }
    );
    return response.data;
  },

  // ============ 资金流向分析 ============

  /**
   * 获取资金流向分析
   */
  getFundFlowAnalysis: async (date?: string): Promise<FundFlowResponse> => {
    const response = await apiClient.get<FundFlowResponse>(
      '/api/v1/seal-plate/fund-flow',
      { params: date ? { date } : {} }
    );
    return toCamelCase<FundFlowResponse>(response.data);
  },

  /**
   * 手动触发早盘推荐任务
   */
  triggerMorningTask: async (date?: string): Promise<MorningTaskResponse> => {
    const response = await apiClient.post<MorningTaskResponse>(
      '/api/v1/seal-plate/morning-task',
      null,
      { params: date ? { date } : {} }
    );
    return response.data;
  },

  /**
   * 手动触发收盘复盘任务
   */
  triggerEveningTask: async (date?: string): Promise<EveningTaskResponse> => {
    const response = await apiClient.post<EveningTaskResponse>(
      '/api/v1/seal-plate/evening-task',
      null,
      { params: date ? { date } : {} }
    );
    return response.data;
  },

  // ============ 高胜率战法 ============

  /**
   * 获取高胜率战法列表
   */
  getStrategies: async (): Promise<StrategyResponse> => {
    const response = await apiClient.get<StrategyResponse>(
      '/api/v1/seal-plate/strategies'
    );
    return toCamelCase<StrategyResponse>(response.data);
  },

  /**
   * 获取战法匹配的候选标的
   */
  getStrategyCandidates: async (strategyId: string): Promise<StrategyCandidatesResponse> => {
    const response = await apiClient.get<StrategyCandidatesResponse>(
      `/api/v1/seal-plate/strategies/${strategyId}/candidates`
    );
    return toCamelCase<StrategyCandidatesResponse>(response.data);
  },

  /**
   * 获取多战法匹配重点推荐（降低风险敞口）
   */
  getMultiMatchRecommendations: async (date?: string): Promise<MultiMatchResponse> => {
    const queryParams: Record<string, string> = {};
    if (date) queryParams.date = date;

    const response = await apiClient.get<MultiMatchResponse>(
      '/api/v1/seal-plate/strategies/multi-match',
      { params: queryParams }
    );
    return toCamelCase<MultiMatchResponse>(response.data);
  },

  // ============ 持仓 ============

  /**
   * 获取持仓数据
   */
  getHoldings: async (): Promise<HoldingsResponse> => {
    const response = await apiClient.get<HoldingsResponse>(
      '/api/v1/seal-plate/holdings'
    );
    return toCamelCase<HoldingsResponse>(response.data);
  },

  // ============ 个股风险分析 ============

  /**
   * 获取指定标的的风险分析（游资、一日游、封板质量）
   */
  getStockRiskAnalysis: async (stockCode: string, date?: string): Promise<StockRiskAnalysisResponse> => {
    const queryParams: Record<string, string> = {};
    if (date) queryParams.date = date;

    const response = await apiClient.get<StockRiskAnalysisResponse>(
      `/api/v1/seal-plate/stock-risk/${stockCode}`,
      { params: queryParams }
    );
    return toCamelCase<StockRiskAnalysisResponse>(response.data);
  },

  // ============ 自选股 ============

  /**
   * 获取自选股列表
   */
  getWatchlist: async (): Promise<WatchlistResponse> => {
    const response = await apiClient.get<WatchlistResponse>(
      '/api/v1/seal-plate/watchlist'
    );
    return toCamelCase<WatchlistResponse>(response.data);
  },

  /**
   * 获取自选股状态（仅code列表）
   */
  getWatchlistStatus: async (): Promise<WatchlistStatusResponse> => {
    const response = await apiClient.get<WatchlistStatusResponse>(
      '/api/v1/seal-plate/watchlist/status'
    );
    return response.data;
  },

  /**
   * 添加自选股
   */
  addToWatchlist: async (data: {
    code: string;
    name: string;
    source?: string;
    score?: number;
    sector?: string | null;
  }): Promise<WatchlistItem> => {
    const response = await apiClient.post<WatchlistItem>(
      '/api/v1/seal-plate/watchlist',
      {
        code: data.code,
        name: data.name,
        source: data.source || 'manual',
        score: data.score || 0,
        sector: data.sector || null,
      }
    );
    return toCamelCase<WatchlistItem>(response.data);
  },

  /**
   * 从自选中移除
   */
  removeFromWatchlist: async (code: string): Promise<{ status: string; code: string }> => {
    const response = await apiClient.delete(
      `/api/v1/seal-plate/watchlist/${code}`
    );
    return response.data;
  },

  // ============ 推荐建仓管理 ============

  /**
   * 获取推荐建仓记录列表
   */
  getRecommendationRecords: async (params: {
    limit?: number;
    offset?: number;
    dateFrom?: string;
    dateTo?: string;
  } = {}): Promise<RecommendationRecordListResponse> => {
    const queryParams: Record<string, string | number> = {};
    if (params.limit !== undefined) queryParams.limit = params.limit;
    if (params.offset !== undefined) queryParams.offset = params.offset;
    if (params.dateFrom) queryParams.date_from = params.dateFrom;
    if (params.dateTo) queryParams.date_to = params.dateTo;

    const response = await apiClient.get<RecommendationRecordListResponse>(
      '/api/v1/seal-plate/recommendation-records',
      { params: queryParams }
    );
    return toCamelCase<RecommendationRecordListResponse>(response.data);
  },

  /**
   * 获取每日胜率回溯数据
   */
  getWinRateBacktest: async (params: {
    days?: number;
    dateFrom?: string;
    dateTo?: string;
  } = {}): Promise<WinRateBacktestResponse> => {
    const queryParams: Record<string, string | number> = {};
    if (params.days !== undefined) queryParams.days = params.days;
    if (params.dateFrom) queryParams.date_from = params.dateFrom;
    if (params.dateTo) queryParams.date_to = params.dateTo;

    const response = await apiClient.get<WinRateBacktestResponse>(
      '/api/v1/seal-plate/win-rate-backtest',
      { params: queryParams }
    );
    return toCamelCase<WinRateBacktestResponse>(response.data);
  },

  /**
   * 查询特定日期的阶段性胜率
   */
  getHistoricalWinRate: async (targetDate: string, lookbackDays: number = 5): Promise<HistoricalWinRateResponse> => {
    const response = await apiClient.get<HistoricalWinRateResponse>(
      '/api/v1/seal-plate/historical-win-rate',
      { params: { target_date: targetDate, lookback_days: lookbackDays } }
    );
    return toCamelCase<HistoricalWinRateResponse>(response.data);
  },

  /**
   * 获取有推荐记录的日期列表
   */
  getRecommendationDates: async (): Promise<AvailableDatesResponse> => {
    const response = await apiClient.get<AvailableDatesResponse>(
      '/api/v1/seal-plate/recommendation-dates'
    );
    return toCamelCase<AvailableDatesResponse>(response.data);
  },

  // ============ 综合推荐系统 ============

  /**
   * 获取综合推荐仪表盘（10维分析）
   */
  getComprehensiveRecommendations: async (date?: string): Promise<ComprehensiveRecommendationResponse> => {
    const queryParams: Record<string, string> = {};
    if (date) queryParams.date = date;

    const response = await apiClient.get<ComprehensiveRecommendationResponse>(
      '/api/v1/comprehensive',
      { params: queryParams }
    );
    return toCamelCase<ComprehensiveRecommendationResponse>(response.data);
  },

  /**
   * 获取胜率简报
   */
  getWinRateBrief: async (): Promise<WinRateBriefResponse> => {
    const response = await apiClient.get<WinRateBriefResponse>(
      '/api/v1/comprehensive/win-rate-brief'
    );
    return toCamelCase<WinRateBriefResponse>(response.data);
  },

  /**
   * 从仓位管理中移除指定标的
   */
  removePositionStock: async (code: string): Promise<{ success: boolean; code: string; excludedCount: number }> => {
    const response = await apiClient.delete(
      `/api/v1/comprehensive/position/stocks/${code}`
    );
    return response.data;
  },

  /**
   * 获取已排除的仓位标的列表
   */
  getExcludedStocks: async (): Promise<{ excludedCodes: string[]; count: number }> => {
    const response = await apiClient.get(
      '/api/v1/comprehensive/position/stocks/excluded'
    );
    return response.data;
  },

  /**
   * 恢复已排除的仓位标的
   */
  restorePositionStock: async (code: string): Promise<{ success: boolean; code: string }> => {
    const response = await apiClient.delete(
      `/api/v1/comprehensive/position/stocks/excluded/${code}`
    );
    return response.data;
  },
};
