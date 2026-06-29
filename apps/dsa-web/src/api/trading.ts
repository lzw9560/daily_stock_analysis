import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  TradingWorkbenchResponse,
  TradingPlan,
  WorkflowTask,
  TradingAlert,
} from '../types/trading';

export const tradingApi = {
  /** 获取交易工作台状态 */
  getWorkbenchStatus: async (): Promise<TradingWorkbenchResponse> => {
    const response = await apiClient.get<TradingWorkbenchResponse>(
      '/api/v1/trading/workbench/status'
    );
    return toCamelCase<TradingWorkbenchResponse>(response.data);
  },

  /** 获取今日交易计划 */
  getTradingPlan: async (date?: string): Promise<TradingPlan> => {
    const response = await apiClient.get<TradingPlan>(
      '/api/v1/trading/plan',
      { params: date ? { date } : {} }
    );
    return toCamelCase<TradingPlan>(response.data);
  },

  /** 执行工作流阶段 */
  executePhase: async (phase: string): Promise<{ tasks: WorkflowTask[] }> => {
    const response = await apiClient.post<{ tasks: WorkflowTask[] }>(
      '/api/v1/trading/workbench/execute',
      { phase }
    );
    return toCamelCase<{ tasks: WorkflowTask[] }>(response.data);
  },

  /** 获取实时告警 */
  getAlerts: async (params?: {
    severity?: string;
    acknowledged?: boolean;
    limit?: number;
  }): Promise<{ alerts: TradingAlert[] }> => {
    const response = await apiClient.get<{ alerts: TradingAlert[] }>(
      '/api/v1/trading/alerts',
      { params }
    );
    return toCamelCase<{ alerts: TradingAlert[] }>(response.data);
  },

  /** 确认告警 */
  acknowledgeAlert: async (alertId: string): Promise<void> => {
    await apiClient.post(`/api/v1/trading/alerts/${alertId}/acknowledge`);
  },
};
