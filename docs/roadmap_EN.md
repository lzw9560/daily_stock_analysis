# Phase Roadmap

This document records the project's staged evolution plan. The roadmap is not a guarantee that every item is already implemented; each phase is designed to stay backward-compatible by default and to be enabled through opt-in switches or gates.

## Phase 1: Vectorized Backtesting

- Flow: `TAWrapper` delegation → `VbtEngine` → `GridOptimizer`
- Scale target: 5,000 combinations in `<30s`
- Behavior constraint: zero behavior change by default, opt-in via `BACKTEST_ENGINE_VERSION=v1`
- Focus: backtest engine version isolation, combination search performance, compatibility with existing results

## Phase 2: Multi-Factor Stock Selection

- Factor extraction: `Qlib` `Alpha158/360`
- Model training: rolling `LightGBM`
- Explanation and monitoring: `SHAP` explanations, `IC/IR` decay monitoring
- Enablement: gated by `FACTOR_PIPELINE_ENABLED=false`
- Focus: factor artifact consistency, rolling-window stability, explainability of screening results

### Current Skeleton

- `FACTOR_PIPELINE_ENABLED=false` remains the default, and `ScreeningService` invokes `FactorPipelineService` only when enabled.
- `FactorBackendAdapter` prefers real `Qlib` / `LightGBM` / `SHAP` dependencies and falls back to a deterministic skeleton when they are unavailable.
- Factor summaries are written into `ScreeningCandidate.factor_scores_json`, and the training window, SHAP sample size, Qlib instrument universe, and region are configurable.
- The real backend also returns `traces` so training windows, SHAP sample size, backend selection, and fallback reasons remain inspectable for later debugging and model iteration.
- `/api/v1/screening/records` and `/api/v1/screening/records/{record_id}` now expose the factor pipeline overview, so the frontend/task panel can consume it directly.
- The screening API now exposes `POST /api/v1/screening/factor-pipeline/run` for explicit triggering and `GET /api/v1/screening/records/{record_id}/factor-pipeline` for read-only inspection.

## Phase 3: Agent Debate

- Flow: `Research` (hypothesis) → `Battle` (adversarial) → `Consensus` (scoring)
- Orchestration: 3 independent Skills registered to the orchestrator
- Enablement: `AGENT_ORCHESTRATOR_MODE=debate`
- Storage: SQLite-backed `ExperienceStore`
- Focus: Skill boundaries, reusable debate flow, accumulated experience

## Phase 4: Monte Carlo + Atomic Execution

- Simulation methods: `GBM` / `Heston` / `Bootstrap`
- Path scale: 10k paths
- Risk and sizing: `VaR` stop-loss calibration → `Kelly` sizing
- Execution guarantees: atomic order placement, idempotency keys, `os.replace()` WAL
- Enablement: gated by `EXECUTION_ENABLED=false`
- Focus: execution idempotency, risk boundaries, order consistency

## Constraints

- This roadmap only describes phase goals and enablement boundaries; it does not change current default behavior.
- If a later phase touches API, Web, Desktop, or report structure, the relevant topic docs and changelog will be updated first.
