import { beforeEach, describe, expect, it } from 'vitest';
import {
  buildExecutionPanelHref,
  getExecutionMemorySnapshot,
  getLatestExecutionResult,
  getLastExecutionParams,
  saveExecutionResult,
  saveLastExecutionParams,
  useExecutionMemory,
} from '../executionMemory';

beforeEach(() => {
  localStorage.clear();
});

describe('executionMemory', () => {
  it('persists last params and latest result per symbol', () => {
    saveLastExecutionParams({ symbol: '600519', side: 'buy', spot: '100' });
    expect(getLastExecutionParams()).toMatchObject({ symbol: '600519', side: 'buy', spot: '100' });

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

    expect(getLatestExecutionResult('600519')?.response.order.symbol).toBe('600519');
    expect(getExecutionMemorySnapshot().latestSymbol).toBe('600519');
  });

  it('builds a prefilled execution href', () => {
    expect(
      buildExecutionPanelHref({
        symbol: '600519',
        side: 'buy',
        spot: '100',
        quantity: '100',
        horizonDays: '10',
        model: 'gbm',
        dryRun: true,
      }),
    ).toContain('/execution?symbol=600519');
  });

  it('exposes a sync store snapshot through the hook contract', () => {
    const snapshot = useExecutionMemory();
    expect(snapshot.latestSymbol).toBeNull();
    expect(snapshot.lastParams).toEqual({});
  });
});
