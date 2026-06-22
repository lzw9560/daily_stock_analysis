# 阶段路线图

本文档记录项目后续的阶段性演进方向。这里的阶段计划是路线图，不是当前已全部落地的承诺；各阶段默认保持向后兼容，优先通过 opt-in 或 gate 开关启用。

## Phase 1：向量化回测

- 目标链路：`TAWrapper` 委托 → `VbtEngine` → `GridOptimizer`
- 目标规模：5000 组合 `<30s`
- 行为约束：默认零行为变更，通过 `BACKTEST_ENGINE_VERSION=v1` opt-in 切换
- 关注点：回测引擎版本隔离、组合搜索性能、既有回测结果兼容性

## Phase 2：多因子选股

- 因子提取：`Qlib` `Alpha158/360`
- 模型训练：`LightGBM` 滚动训练
- 解释与监控：`SHAP` 解释、`IC/IR` 衰减监控
- 启用方式：`FACTOR_PIPELINE_ENABLED=false` gate 控制
- 关注点：因子产物一致性、滚动窗口稳定性、选股结果可解释性

### 当前骨架

- `FACTOR_PIPELINE_ENABLED=false` 默认关闭，开启后由 `ScreeningService` 调用 `FactorPipelineService`。
- `FactorBackendAdapter` 优先探测真实 `Qlib` / `LightGBM` / `SHAP` 依赖；缺失时自动回退到确定性 skeleton。
- 因子摘要会写入 `ScreeningCandidate.factor_scores_json`，训练 / 解释 / IC-IR 监控返回结构化 payload，且训练窗口、SHAP 样本量、Qlib 标的池和 region 都可配置。
- 真实后端会额外返回 `traces`，用于追踪训练窗口、SHAP 样本量、后端选择和回退原因，便于后续排障和模型版本演进。
- `/api/v1/screening/records` 和 `/api/v1/screening/records/{record_id}` 现已返回因子流水线概览，前端/任务面板可直接读取。
- 选股 API 已补 `POST /api/v1/screening/factor-pipeline/run` 显式触发入口，以及 `GET /api/v1/screening/records/{record_id}/factor-pipeline` 的只读查看入口。

## Phase 3：Agent 辩论

- 流程：`Research`（假设）→ `Battle`（对抗）→ `Consensus`（评分）
- 编排方式：3 个独立 Skill 注册到 orchestrator
- 启用方式：`AGENT_ORCHESTRATOR_MODE=debate`
- 存储：`ExperienceStore` 使用 SQLite
- 关注点：Skill 边界、辩论链路可复用性、历史经验沉淀

## Phase 4：蒙特卡洛 + 原子执行

- 仿真方法：`GBM` / `Heston` / `Bootstrap`
- 路径规模：10k paths
- 风控与仓位：`VaR` 止损校准 → `Kelly` 仓位
- 执行保障：原子下单、幂等 key、`os.replace()` WAL
- 启用方式：`EXECUTION_ENABLED=false` gate 控制
- 关注点：执行幂等性、资金风险边界、落单一致性

## 约束说明

- 该路线图只描述阶段目标与启用边界，不改变当前默认行为。
- 若后续阶段涉及 API、Web、Desktop 或报告结构变化，会优先补充对应专题文档与变更日志。

