import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { TaskPanel } from '../TaskPanel';

beforeEach(() => {
  localStorage.clear();
});

describe('TaskPanel', () => {
  it('shows an execution panel shortcut in the header', () => {
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
          meanReturn: 1.23,
          medianReturn: 1.1,
          p05Return: -2.2,
          p01Return: -3.4,
          var95: 4.5,
          cvar95: 5.6,
          pathsPreview: [1, 2],
          parameters: {},
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
        <TaskPanel
          tasks={[
            {
              taskId: 'task-1',
              stockCode: '600519',
              status: 'processing',
              progress: 25,
              reportType: 'analysis',
              createdAt: '2026-06-14T00:00:00Z',
            },
          ]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText('执行任务卡')).toBeInTheDocument();
    expect(screen.getByText('最近结果 · 仅预览')).toBeInTheDocument();
  });
});
