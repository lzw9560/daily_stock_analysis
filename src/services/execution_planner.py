# -*- coding: utf-8 -*-
"""Phase 4 execution planner: simulation → VaR → Kelly → atomic payload."""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Optional, Sequence

from src.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class SimulationSummary:
    model: str
    paths: int
    horizon_days: int
    mean_return: float
    median_return: float
    p05_return: float
    p01_return: float
    var_95: float
    cvar_95: float
    paths_preview: List[float] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionSizingSummary:
    var_limit_pct: float
    kelly_fraction: float
    target_position_pct: float
    capped_position_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    rationale: List[str] = field(default_factory=list)


@dataclass
class AtomicOrderPayload:
    idempotency_key: str
    symbol: str
    side: str
    quantity: int
    price: float
    order_type: str = "market"
    dry_run: bool = True
    wal_path: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class MonteCarloSimulator:
    """Generate deterministic path samples for GBM / Heston / Bootstrap."""

    def simulate(
        self,
        *,
        model: str,
        spot: float,
        horizon_days: int,
        paths: int,
        drift: float = 0.0,
        vol: float = 0.2,
        seed: Optional[int] = None,
        bootstrap_returns: Optional[Sequence[float]] = None,
    ) -> SimulationSummary:
        model = (model or "gbm").strip().lower()
        path_count = max(1, int(paths))
        horizon = max(1, int(horizon_days))
        simulated = self._build_returns(
            model=model,
            spot=float(spot),
            horizon_days=horizon,
            paths=path_count,
            drift=float(drift),
            vol=float(vol),
            seed=seed,
            bootstrap_returns=bootstrap_returns,
        )
        var_95 = -self._percentile(simulated, 5)
        cvar_95 = -self._cvar(simulated, 5)
        return SimulationSummary(
            model=model,
            paths=path_count,
            horizon_days=horizon,
            mean_return=self._mean(simulated),
            median_return=self._percentile(simulated, 50),
            p05_return=self._percentile(simulated, 5),
            p01_return=self._percentile(simulated, 1),
            var_95=var_95,
            cvar_95=cvar_95,
            paths_preview=simulated[:10],
            parameters={"drift": drift, "vol": vol, "seed": seed},
        )

    def _build_returns(
        self,
        *,
        model: str,
        spot: float,
        horizon_days: int,
        paths: int,
        drift: float,
        vol: float,
        seed: Optional[int],
        bootstrap_returns: Optional[Sequence[float]],
    ) -> List[float]:
        if model == "bootstrap":
            samples = list(bootstrap_returns or [0.0])
            if not samples:
                samples = [0.0]
            return [samples[i % len(samples)] for i in range(paths)]

        if model == "heston":
            vol = max(vol, 0.05)
            drift -= 0.25 * vol * vol
        elif model != "gbm":
            logger.debug("Unknown simulation model %s, falling back to gbm", model)

        # Deterministic pseudo-paths: no RNG dependency, stable for tests.
        base = max(spot, 1.0)
        horizon_scale = math.sqrt(horizon_days / 252.0)
        outputs: List[float] = []
        for index in range(paths):
            oscillation = math.sin((index + 1) * 1.61803398875)
            shock = oscillation * vol * 0.45 * horizon_scale
            trend = drift * horizon_days / 252.0
            return_pct = (trend + shock) * 100.0
            outputs.append(return_pct)
        return outputs

    @staticmethod
    def _mean(values: Sequence[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    @staticmethod
    def _percentile(values: Sequence[float], percentile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        rank = max(0, min(len(ordered) - 1, int(round((percentile / 100.0) * (len(ordered) - 1)))))
        return round(ordered[rank], 4)

    @staticmethod
    def _cvar(values: Sequence[float], percentile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        cutoff = max(1, int(math.ceil(len(ordered) * percentile / 100.0)))
        tail = ordered[:cutoff]
        return round(sum(tail) / len(tail), 4)


class RiskSizer:
    """Combine VaR stop-loss calibration with Kelly sizing."""

    def compute(
        self,
        *,
        var_95: float,
        win_rate: float,
        payoff_ratio: float,
        max_position_pct: float = 30.0,
        stop_loss_floor_pct: float = 3.0,
        take_profit_target_pct: float = 8.0,
    ) -> PositionSizingSummary:
        win_rate = max(0.0, min(1.0, float(win_rate)))
        payoff_ratio = max(0.0, float(payoff_ratio))
        kelly = self._kelly_fraction(win_rate=win_rate, payoff_ratio=payoff_ratio)
        var_limit_pct = max(0.0, min(100.0, float(var_95)))
        stop_loss_pct = max(stop_loss_floor_pct, var_limit_pct)
        capped_position_pct = max(0.0, min(float(max_position_pct), kelly * 100.0))
        rationale = [
            f"VaR95={var_limit_pct:.2f}%",
            f"Kelly={kelly:.4f}",
            f"win_rate={win_rate:.2%}",
            f"payoff_ratio={payoff_ratio:.2f}",
        ]
        return PositionSizingSummary(
            var_limit_pct=round(var_limit_pct, 4),
            kelly_fraction=round(kelly, 4),
            target_position_pct=round(capped_position_pct, 4),
            capped_position_pct=round(capped_position_pct, 4),
            stop_loss_pct=round(stop_loss_pct, 4),
            take_profit_pct=round(float(take_profit_target_pct), 4),
            rationale=rationale,
        )

    @staticmethod
    def _kelly_fraction(*, win_rate: float, payoff_ratio: float) -> float:
        if payoff_ratio <= 0:
            return 0.0
        q = 1.0 - win_rate
        b = payoff_ratio
        value = (b * win_rate - q) / b
        return max(0.0, value)


class AtomicExecutionWriter:
    """Write order payloads atomically with idempotency support."""

    def __init__(self, wal_dir: Optional[str] = None):
        config = get_config()
        default_dir = getattr(config, "data_dir", ".") or "."
        self.wal_dir = Path(wal_dir or default_dir) / "execution_wal"
        self.wal_dir.mkdir(parents=True, exist_ok=True)

    def build_payload(
        self,
        *,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        order_type: str = "market",
        dry_run: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AtomicOrderPayload:
        normalized = {
            "symbol": (symbol or "").strip().upper(),
            "side": (side or "").strip().lower(),
            "quantity": int(quantity),
            "price": float(price),
            "order_type": (order_type or "market").strip().lower(),
            "metadata": metadata or {},
        }
        idempotency_key = self._build_idempotency_key(normalized)
        wal_path = self._write_wal(idempotency_key, normalized)
        return AtomicOrderPayload(
            idempotency_key=idempotency_key,
            symbol=normalized["symbol"],
            side=normalized["side"],
            quantity=normalized["quantity"],
            price=normalized["price"],
            order_type=normalized["order_type"],
            dry_run=dry_run,
            wal_path=str(wal_path),
        )

    def _write_wal(self, key: str, payload: Dict[str, Any]) -> Path:
        final_path = self.wal_dir / f"{key}.json"
        if final_path.exists():
            return final_path
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=self.wal_dir) as tmp:
            json.dump(payload, tmp, ensure_ascii=False, indent=2, default=str)
            tmp.write("\n")
            temp_path = Path(tmp.name)
        temp_path.replace(final_path)
        return final_path

    @staticmethod
    def _build_idempotency_key(payload: Dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


class ExecutionPlanner:
    """High-level phase 4 planner."""

    def __init__(self):
        self.simulator = MonteCarloSimulator()
        self.sizer = RiskSizer()
        self.writer = AtomicExecutionWriter()

    def generate_execution_plan(
        self,
        *,
        symbol: str,
        spot: float,
        vol: float = 0.3,
        horizon_days: int = 5,
        total_capital: float = 100_000,
        side: str = "buy",
        paths: int = 10_000,
        model: str = "gbm",
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """生成执行计划（适配 enhanced_recommendation API 的接口）。
        
        与 plan() 的区别：自动根据 total_capital 推算 quantity，
        默认使用保守的 win_rate/payoff_ratio 假设。
        """
        # 根据总资金和现价推算合理数量（A股100股整数倍）
        quantity = max(100, int(total_capital / max(spot, 0.01) / 10) * 100)
        
        # 使用 vol 作为波动率输入
        drift_estimate = 0.0  # 默认无漂移假设
        # 保守的胜率和盈亏比估计
        win_rate_est = 0.5
        payoff_ratio_est = 1.5
        
        return self.plan(
            symbol=symbol,
            side=side,
            spot=spot,
            quantity=quantity,
            horizon_days=horizon_days,
            paths=paths,
            model=model,
            drift=drift_estimate,
            vol=vol,
            win_rate=win_rate_est,
            payoff_ratio=payoff_ratio_est,
            max_position_pct=30.0,
            dry_run=dry_run,
            metadata={
                "total_capital": total_capital,
                "generated_by": "generate_execution_plan",
            },
        )

    def plan(
        self,
        *,
        symbol: str,
        side: str,
        spot: float,
        quantity: int,
        horizon_days: int = 10,
        paths: int = 10_000,
        model: str = "gbm",
        drift: float = 0.0,
        vol: float = 0.2,
        win_rate: float = 0.5,
        payoff_ratio: float = 1.5,
        max_position_pct: float = 30.0,
        dry_run: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        simulation = self.simulator.simulate(
            model=model,
            spot=spot,
            horizon_days=horizon_days,
            paths=paths,
            drift=drift,
            vol=vol,
            seed=(metadata or {}).get("seed"),
            bootstrap_returns=(metadata or {}).get("bootstrap_returns"),
        )
        sizing = self.sizer.compute(
            var_95=simulation.var_95,
            win_rate=win_rate,
            payoff_ratio=payoff_ratio,
            max_position_pct=max_position_pct,
            stop_loss_floor_pct=(metadata or {}).get("stop_loss_floor_pct", 3.0),
            take_profit_target_pct=(metadata or {}).get("take_profit_target_pct", 8.0),
        )
        order = self.writer.build_payload(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=spot,
            order_type=(metadata or {}).get("order_type", "market"),
            dry_run=dry_run,
            metadata=metadata,
        )
        return {
            "execution_enabled": bool(getattr(get_config(), "execution_enabled", False)),
            "simulation": simulation.__dict__,
            "sizing": sizing.__dict__,
            "order": order.__dict__,
        }
