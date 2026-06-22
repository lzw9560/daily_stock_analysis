import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  FactorPipelineRecordResponse,
  FactorPipelineTriggerRequest,
  FactorPipelineTriggerResponse,
} from '../types/screening';

export const screeningApi = {
  triggerFactorPipeline: async (params: FactorPipelineTriggerRequest): Promise<FactorPipelineTriggerResponse> => {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/screening/factor-pipeline/run', {
      record_id: params.recordId,
      market: params.market,
      screening_date: params.screeningDate,
    });
    return toCamelCase<FactorPipelineTriggerResponse>(response.data);
  },

  getFactorPipeline: async (recordId: number): Promise<FactorPipelineRecordResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/screening/records/${recordId}/factor-pipeline`);
    return toCamelCase<FactorPipelineRecordResponse>(response.data);
  },
};
