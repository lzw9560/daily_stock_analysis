import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  FederalReserveRateResponse,
  YahooFinanceDataResponse,
  EconomicCalendarEvent,
  MarketDataResponse,
  FinancialStatement,
  StockDividendInfo,
  StockSplitInfo,
  DividendSchedule,
  EarningsCalendar,
  EconomicIndicators,
} from '../types/analysis';

// ==============================================================
// Financial Data API
// ==============================================================

export const financialDataApi = {
  /**
   * 获取美联储利率数据
   * @param startDate 开始日期 (YYYY-MM-DD)
   * @param endDate 结束日期 (YYYY-MM-DD)
   * @param maturityType 债券类型：'Treasury', 'FedFunds', 'LIBOR', 'Eurodollar'
   */
  getFedRates: async (startDate?: string, endDate?: string, maturityType?: string): Promise<FederalReserveRateResponse> => {
    const params = new URLSearchParams();
    if (startDate) params.append('startDate', startDate);
    if (endDate) params.append('endDate', endDate);
    if (maturityType) params.append('maturityType', maturityType);

    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/financial-data/fed-rates?${params.toString()}`
    );
    return toCamelCase<FederalReserveRateResponse>(response.data);
  },

  /**
   * 获取Yahoo Finance股票数据
   * @param stockCode 股票代码，如'AAPL'，'TSLA.W'
   * @param startDate 开始日期 (YYYY-MM-DD)
   * @param endDate 结束日期 (YYYY-MM-DD)
   * @param interval 时间间隔：'1d'，'1h'，'1wk'
   */
  getYahooFinanceData: async (
    stockCode: string,
    startDate: string,
    endDate: string,
    interval: string = '1d'
  ): Promise<YahooFinanceDataResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/financial-data/yahoo/${stockCode}?startDate=${startDate}&endDate=${endDate}&interval=${interval}`
    );
    return toCamelCase<YahooFinanceDataResponse>(response.data);
  },

  /**
   * 获取经济日历事件
   * @param startDate 开始日期 (YYYY-MM-DD)
   * @param endDate 结束日期 (YYYY-MM-DD)
   * @param calendarType 日历类型：'economic'，'financial'，'all'
   */
  getEconomicCalendar: async (
    startDate: string,
    endDate: string,
    calendarType: string = 'economic'
  ): Promise<EconomicCalendarEvent[]> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/financial-data/calendar?startDate=${startDate}&endDate=${endDate}&type=${calendarType}`
    );
    const data = toCamelCase<{ items: EconomicCalendarEvent[] }>(response.data);
    return data.items || [];
  },

  /**
   * 获取市场数据摘要
   * @param market 市场：'us'，'hk'，'cn'，'eu'
   * @param indicatorType 指标类型：'prices'，'volumes'，'all'
   */
  getMarketData: async (market: string, indicatorType: string = 'prices'): Promise<MarketDataResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/financial-data/market/${market}?indicator=${indicatorType}`
    );
    return toCamelCase<MarketDataResponse>(response.data);
  },

  /**
   * 获取股票财务报表
   * @param stockCode 股票代码
   * @param statementType 报表类型：'income'，'balance'，'cashflow'
   */
  getFinancialStatement: async (stockCode: string, statementType: string = 'income'): Promise<FinancialStatement> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/financial-data/stock/${stockCode}/statement?statement=${statementType}`
    );
    return toCamelCase<FinancialStatement>(response.data);
  },

  /**
   * 获取股票分红信息
   * @param stockCode 股票代码
   */
  getStockDividends: async (stockCode: string): Promise<StockDividendInfo> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/financial-data/stock/${stockCode}/dividends`
    );
    return toCamelCase<StockDividendInfo>(response.data);
  },

  /**
   * 获取股票分割信息
   * @param stockCode 股票代码
   */
  getStockSplits: async (stockCode: string): Promise<StockSplitInfo> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/financial-data/stock/${stockCode}/splits`
    );
    return toCamelCase<StockSplitInfo>(response.data);
  },

  /**
   * 获取分红时间表
   * @param startDate 开始日期 (YYYY-MM-DD)
   * @param endDate 结束日期 (YYYY-MM-DD)
   */
  getDividendSchedule: async (startDate: string, endDate: string): Promise<DividendSchedule[]> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/financial-data/dividends?startDate=${startDate}&endDate=${endDate}`
    );
    const data = toCamelCase<{ items: DividendSchedule[] }>(response.data);
    return data.items || [];
  },

  /**
   * 获取财报日历
   * @param startDate 开始日期 (YYYY-MM-DD)
   * @param endDate 结束日期 (YYYY-MM-DD)
   */
  getEarningsCalendar: async (startDate: string, endDate: string): Promise<EarningsCalendar[]> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/financial-data/earnings?startDate=${startDate}&endDate=${endDate}`
    );
    const data = toCamelCase<{ items: EarningsCalendar[] }>(response.data);
    return data.items || [];
  },

  /**
   * 获取经济指标
   * @param indicatorTypes 指标类型数组，如['inflation', 'unemployment', 'gdp']
   * @param startDate 开始日期 (YYYY-MM-DD)
   * @param endDate 结束日期 (YYYY-MM-DD)
   */
  getEconomicIndicators: async (
    indicatorTypes: string[],
    startDate: string,
    endDate: string
  ): Promise<EconomicIndicators> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/financial-data/economic?indicators=${indicatorTypes.join(',')}&startDate=${startDate}&endDate=${endDate}`
    );
    return toCamelCase<EconomicIndicators>(response.data);
  },
};