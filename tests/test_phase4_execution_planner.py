# -*- coding: utf-8 -*-

from __future__ import annotations

from api.v1.endpoints.backtest import simulate_phase4
from api.v1.schemas.backtest import MonteCarloSimulationRequest


def test_phase4_simulation_returns_planned_payload():
    request = MonteCarloSimulationRequest(
        symbol='600519',
        side='buy',
        spot=100.0,
        quantity=10,
        horizon_days=10,
        paths=1000,
        model='gbm',
        drift=0.05,
        vol=0.2,
        win_rate=0.55,
        payoff_ratio=1.8,
        max_position_pct=30.0,
        dry_run=True,
        metadata={'seed': 42},
    )
    response = simulate_phase4(request)
    assert response.execution_enabled is False
    assert response.simulation['model'] == 'gbm'
    assert response.sizing['target_position_pct'] >= 0
    assert response.order['symbol'] == '600519'
    assert response.order['dry_run'] is True


def test_phase4_order_payload_is_deterministic():
    from src.services.execution_planner import ExecutionPlanner

    planner = ExecutionPlanner()
    first = planner.plan(
        symbol='600519', side='buy', spot=100.0, quantity=10, dry_run=True, metadata={'seed': 1}
    )
    second = planner.plan(
        symbol='600519', side='buy', spot=100.0, quantity=10, dry_run=True, metadata={'seed': 1}
    )
    assert first['order']['idempotency_key'] == second['order']['idempotency_key']
    assert first['order']['wal_path'] == second['order']['wal_path']
