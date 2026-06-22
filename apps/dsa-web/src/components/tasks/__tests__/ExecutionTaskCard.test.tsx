import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import ExecutionTaskCard from '../ExecutionTaskCard';
import { saveExecutionResult, saveLastExecutionParams } from '../../../utils/executionMemory';

beforeEach(() => {
  localStorage.clear();
});

describe('ExecutionTaskCard', () => {
  it('renders a card with a prefilled execution link and latest summary', () => {
    saveLastExecutionParams({ symbol: '600519', side: 'buy', spot: '100' });
    saveExecutionResult({
      savedAt: '2026-06-14T10:00:00Z',
      input: {
        symbol: '600519',
        side: 'buy',
        spot: '100',
        quantity: '100',
        horizonDays: '10',
        paths: '10000',
        model: 'gbm',
        drift: '0',
        vol: '0.2',
        winRate: '0.55',
        payoffRatio: '1.5',
        maxPositionPct: '30',
        dryRun: true,
      },
      response: {
        executionEnabled: false,
        simulation: {
          model: 'gbm',
          paths: 10000,
          horizonDays: 10,
          meanReturn: 1,
          medianReturn: 1,
          p05Return: -1,
          p01Return: -2,
          var95: 3,
          cvar95: 4,
          pathsPreview: [],
          parameters: {},
        },
        sizing: {
          varLimitPct: 3,
          kellyFraction: 0.2,
          targetPositionPct: 20,
          cappedPositionPct: 20,
          stopLossPct: 3,
          takeProfitPct: 8,
          rationale: [],
        },
        order: {
          idempotencyKey: 'abc',
          symbol: '600519',
          side: 'buy',
          quantity: 100,
          price: 100,
          orderType: 'market',
          dryRun: true,
          walPath: '/tmp/wal.json',
          createdAt: '2026-06-14T10:00:00Z',
        },
      },
    });

    render(
      <MemoryRouter>
        <ExecutionTaskCard
          task={{
            taskId: 'task-1',
            stockCode: '600519',
            status: 'processing',
            progress: 25,
            reportType: 'analysis',
            createdAt: '2026-06-14T00:00:00Z',
          } as never}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: '打开预填执行面板' })).toHaveAttribute(
      'href',
      expect.stringContaining('/execution?symbol=600519'),
    );
    expect(screen.getByText('执行任务卡')).toBeInTheDocument();
    expect(screen.getByText('有缓存')).toBeInTheDocument();
    expect(screen.getByText(/最近一次模拟：VaR95/)).toBeInTheDocument();
  });
});
