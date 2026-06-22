import { describe, expect, it, vi } from 'vitest';
import apiClient from '../index';
import { backtestApi } from '../backtest';

vi.mock('../index', () => ({
  default: {
    post: vi.fn(),
  },
}));

const mockPost = vi.mocked(apiClient.post);

describe('backtestApi.simulatePhase4', () => {
  it('posts camelCase payload and converts response', async () => {
    mockPost.mockResolvedValueOnce({
      data: {
        execution_enabled: false,
        simulation: {
          model: 'gbm',
          paths: 10000,
          horizon_days: 10,
          mean_return: 1.23,
          median_return: 1.1,
          p05_return: -2.2,
          p01_return: -3.4,
          var_95: 4.5,
          cvar_95: 5.6,
          paths_preview: [1, 2],
          parameters: { drift: 0 },
        },
        sizing: {
          var_limit_pct: 4.5,
          kelly_fraction: 0.25,
          target_position_pct: 25,
          capped_position_pct: 25,
          stop_loss_pct: 4.5,
          take_profit_pct: 8,
          rationale: ['VaR95=4.50%'],
        },
        order: {
          idempotency_key: 'abc',
          symbol: '600519',
          side: 'buy',
          quantity: 10,
          price: 100,
          order_type: 'market',
          dry_run: true,
          wal_path: '/tmp/wal.json',
          created_at: '2026-06-14T10:00:00',
        },
      },
    });

    const response = await backtestApi.simulatePhase4({
      symbol: '600519',
      side: 'buy',
      spot: 100,
      quantity: 10,
      horizonDays: 20,
      paths: 5000,
      model: 'gbm',
      drift: 0.03,
      vol: 0.2,
      winRate: 0.55,
      payoffRatio: 1.8,
      maxPositionPct: 30,
      dryRun: true,
      metadata: { seed: 7 },
    });

    expect(mockPost).toHaveBeenCalledWith('/api/v1/backtest/phase4/simulate', {
      symbol: '600519',
      side: 'buy',
      spot: 100,
      quantity: 10,
      horizon_days: 20,
      paths: 5000,
      model: 'gbm',
      drift: 0.03,
      vol: 0.2,
      win_rate: 0.55,
      payoff_ratio: 1.8,
      max_position_pct: 30,
      dry_run: true,
      metadata: { seed: 7 },
    });
    expect(response.executionEnabled).toBe(false);
    expect(response.order.idempotencyKey).toBe('abc');
    expect(response.simulation.horizonDays).toBe(10);
  });
});
