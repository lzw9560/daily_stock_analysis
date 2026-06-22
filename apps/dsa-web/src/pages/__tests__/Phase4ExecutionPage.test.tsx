import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Phase4ExecutionPage from '../Phase4ExecutionPage';
import { backtestApi } from '../../api/backtest';

vi.mock('../../api/backtest', () => ({
  backtestApi: {
    simulatePhase4: vi.fn(),
  },
}));

vi.mock('../../api/error', () => ({
  getParsedApiError: (error: unknown) => error,
}));

const mockSimulate = vi.mocked(backtestApi.simulatePhase4);

describe('Phase4ExecutionPage', () => {
  it('submits the simulation request and renders output sections', async () => {
    mockSimulate.mockResolvedValueOnce({
      executionEnabled: false,
      simulation: {
        model: 'gbm',
        paths: 10000,
        horizonDays: 10,
        meanReturn: 1.23,
        medianReturn: 1.1,
        p05Return: -2.2,
        p01Return: -3.4,
        var95: 4.5,
        cvar95: 5.6,
        pathsPreview: [1, 2],
        parameters: { drift: 0 },
      },
      sizing: {
        varLimitPct: 4.5,
        kellyFraction: 0.25,
        targetPositionPct: 25,
        cappedPositionPct: 25,
        stopLossPct: 4.5,
        takeProfitPct: 8,
        rationale: ['VaR95=4.50%'],
      },
      order: {
        idempotencyKey: 'abc',
        symbol: '600519',
        side: 'buy',
        quantity: 10,
        price: 100,
        orderType: 'market',
        dryRun: true,
        walPath: '/tmp/wal.json',
        createdAt: '2026-06-14T10:00:00',
      },
    });

    render(<Phase4ExecutionPage />);

    fireEvent.click(screen.getByRole('button', { name: '运行模拟' }));

    await waitFor(() => {
      expect(mockSimulate).toHaveBeenCalledWith(expect.objectContaining({
        symbol: '600519',
        side: 'buy',
        spot: 100,
        quantity: 100,
        dryRun: true,
      }));
    });

    expect(await screen.findByText('执行摘要')).toBeInTheDocument();
    expect(screen.getByText('仿真结果')).toBeInTheDocument();
    expect(screen.getByText('仓位与风控')).toBeInTheDocument();
    expect(screen.getByText('原子下单')).toBeInTheDocument();
  });
});
