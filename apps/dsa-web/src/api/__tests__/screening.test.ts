import { describe, expect, it, vi } from 'vitest';

vi.mock('../index', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('../utils', () => ({
  toCamelCase: (value: unknown) => value,
}));

import apiClient from '../index';
import { alphasiftApi } from '../alphasift';

describe('alphasift screening factor pipeline api', () => {
  it('exposes factor pipeline helpers', async () => {
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({ data: { recordId: 1, factorPipeline: { status: 'completed', backend: 'qlib', candidateCount: 5 } } })
      .mockResolvedValueOnce({ data: { recordId: 1, factorPipeline: { status: 'completed', backend: 'qlib', candidateCount: 5 } } });
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        status: 'completed',
        recordId: 1,
        factorPipelineEnabled: true,
        factorFamily: { alpha158: 158 },
        training: { model: 'lightgbm' },
        monitoring: { ic: 0.12 },
      },
    });

    await expect(alphasiftApi.getFactorPipeline(1)).resolves.toMatchObject({ recordId: 1 });
    await expect(alphasiftApi.triggerFactorPipeline({ recordId: 1, market: 'cn', screeningDate: '2024-01-01' })).resolves.toMatchObject({
      status: 'completed',
      factorPipelineEnabled: true,
    });

    expect(apiClient.get).toHaveBeenNthCalledWith(1, '/api/v1/screening/records/1/factor-pipeline');
    expect(apiClient.post).toHaveBeenCalledWith('/api/v1/screening/factor-pipeline/run', {
      record_id: 1,
      market: 'cn',
      screening_date: '2024-01-01',
    });
  });
});
