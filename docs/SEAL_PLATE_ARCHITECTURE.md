# 打板助手模块架构设计

**版本**: v2.1 | **更新**: 2026-05-21

打板助手负责 A 股涨停板数据获取、质量评分、情绪周期判断及结果输出。核心定位：强调"什么时候不该打"比"什么时候该打"更重要，不做自动交易。

---

## 术语速查

| 术语 | 定义 |
|------|------|
| 打板/炸板/烂板 | 涨停价买入 / 涨停板被打开 / 反复开板封单不坚决 |
| 首板/连板 | 近期第一个涨停 / 连续多日涨停 |
| 一字板 | 开盘即封板，换手率 <1%，筹码高度锁定 |
| 地天板 | 同日从跌停拉升至涨停，极端反转 |
| 封单 | 涨停价上的买入挂单量 |
| 情绪周期 | 冰点 → 启动 → 发酵 → 高潮 → 退潮 |

---

## 1. 模块结构

### 1.1 目录结构

```
src/seal_plate/
├── __init__.py              # 模块导出
├── models.py                # 数据模型
├── seal_plate_fetcher.py    # 多数据源涨停数据获取
├── seal_plate_analyzer.py   # 评分引擎 + 情绪周期分析
├── seal_plate_notifier.py   # 飞书通知推送
└── seal_plate_service.py    # 服务编排入口

api/v1/endpoints/seal_plate.py   # REST API

apps/dsa-web/src/
├── pages/SealPlatePage.tsx        # 主页面
├── api/sealPlate.ts               # API 封装
├── types/sealPlate.ts             # 类型定义
└── components/sealplate/
    ├── SentimentDashboard.tsx      # 情绪仪表盘
    ├── EightStandardChecklist.tsx  # 八项标准检查表
    ├── StockPoolPanel.tsx          # 候选股票池
    ├── RiskAlertPanel.tsx          # 炸板预警
    └── DragonTigerList.tsx         # 龙虎榜
```

### 1.2 组件依赖

```
SealPlateService (编排入口)
    ├── SealPlateFetcher ──▶ 涨停原始数据
    │      ├── AKShare (主)  ── ak.stock_zt_pool_em()
    │      └── 东方财富 API (备) ── 降级容错
    │
    ├── SealPlateAnalyzer ──▶ 评分 + 情绪 + 板型 + 仓位建议
    │
    └── SealPlateNotifier ──▶ Markdown / JSON / 飞书卡片
```

---

## 2. 核心组件

### 2.1 数据获取 (SealPlateFetcher)

| 数据源 | 优先级 | 策略 |
|--------|--------|------|
| AKShare `stock_zt_pool_em()` | 主 | 东方财富涨停板池 |
| 东方财富 push2 API | 备 | 主源超时自动降级 |

**容错**: 主源超时切换备源 → 全部不可用返回空列表，不抛异常。

**关键字段**: `code, name, close_price, change_pct, limit_up_price, turnover_rate, volume, amount, seal_amount, seal_time, open_count, sector, market, reason`

### 2.2 评分引擎 (SealPlateAnalyzer)

核心分析能力：

| 功能 | 说明 |
|------|------|
| **封板质量评分** | 7 维度加权评分 (详见 §3) |
| **情绪周期判断** | 7 项市场指标 → 0-100 情绪指数 → 5 阶段 (详见 §4) |
| **板型分类** | `FIRST`(一字板) / `NORMAL`(普通) / `TURNING`(地天板) |
| **封板强度** | `STRONG` / `NORMAL` / `WEAK` / `BROKEN` |
| **仓位建议** | 冰点 0-10% / 启动 20-30% / 发酵 50-70% / 高潮 30-50% / 退潮 0-10% |

**板型判定**:

| 板型 | 条件 | 策略意义 |
|------|------|---------|
| 一字板 | 开盘即封板，换手率 <1% | 筹码集中，次日溢价高，排板难 |
| 普通板 | 盘中封板 | 需结合评分判断 |
| 地天板 | 跌停→涨停 | 高收益高风险，看次日接力 |

**强度分级**:

| 强度 | 条件 | 操作 |
|------|------|------|
| 强封 | 封单 > 市值 2%，开板=0 | 积极参与 |
| 正常 | 封单 > 市值 1%，开板≤1 | 正常仓位 |
| 弱封 | 封单 < 市值 0.5% 或 开板≥2 | 小仓试错 |
| 炸板 | 已开板未回封 | 不追，持仓减仓 |

### 2.3 通知器 (SealPlateNotifier)

推送内容：涨停总数/炸板率、强势 TOP8、龙头股、板块热度 TOP5、风险提示。

**通知控制**: `.env` 中 `SEAL_PLATE_NOTIFICATION_ENABLED` 开关。

### 2.4 服务入口 (SealPlateService)

编排流程：数据获取 → 评分 → 情绪分析 → 龙头识别 → 报告生成 → 通知推送。

```python
service = SealPlateService(config={'min_score': 60, 'feishu_enabled': True})
report = service.run(date='20260517', force=True)
```

---

## 3. 打板评分体系

### 3.1 7 维度加权评分（总分 100）

| 维度 | 权重 | 评分逻辑 |
|------|------|---------|
| 封板强度 | 25% | 封单金额越大越高 |
| 封板时间 | 20% | 越早越好，9:30-9:45 满分 |
| 换手率 | 15% | 1-10% 最佳，两端扣分 |
| 成交金额 | 15% | 越活跃越高 |
| 开板次数 | 10% | 0 次满分，递增扣分 |
| 连续涨停 | 10% | 首板加分，高位连板扣分 |
| 量比 | 5% | 量能配合度 |

### 3.2 评分等级

| 分数 | 等级 | 建议 |
|------|------|------|
| 85-100 | 极佳 | 大仓位参与 |
| 70-84 | 良好 | 正常仓位 |
| 55-69 | 一般 | 小仓试错 |
| 40-54 | 较差 | 观望 |
| 0-39 | 危险 | 不建议 |

评分每 30 秒动态更新，低于 `min_score`(默认 60) 不进入推荐。

---

## 4. 情绪周期分析

### 4.1 五阶段模型

```
冰点期(空仓) → 启动期(试错) → 发酵期(积极参与) → 高潮期(减仓) → 退潮期(空仓)
```

### 4.2 核心指标与权重

| 指标 | 正常范围 | 权重 |
|------|---------|------|
| 涨停家数 | 30-80 家 | 20% |
| 跌停家数(反向) | 0-10 家 | 15% |
| 连板高度 | 3-6 板 | 15% |
| 炸板率(反向) | 15%-30% | 15% |
| 昨日涨停溢价 | +2%~+5% | 15% |
| 连板晋级率 | 40%-60% | 15% |
| 量能变化 | ±10% | 5% |

### 4.3 阶段判定

| 阶段 | 指数 | 特征 |
|------|------|------|
| 冰点期 | 0-20 | 涨停稀少，炸板率高 |
| 启动期 | 21-40 | 首板出现，接力试探 |
| 发酵期 | 41-60 | 赚钱效应扩散，龙头确立 |
| 高潮期 | 61-80 | 涨停潮，散户跑步入场 |
| 退潮期 | 高位回落 | 龙头炸板，溢价转负 |

---

## 5. 打板八项标准

### 5.1 标准清单

系统化决策约束，解决"复盘时清醒、盘中手痒"的人性弱点。

| # | 标准 | 筛选条件 |
|---|------|---------|
| 1 | 流通市值 | 30 亿 – 150 亿 |
| 2 | 换手率 | 5% – 20% |
| 3 | 量能比 | > 前 5 日均量 1.5 倍 |
| 4 | 封板时间 | 10:30 前封板 |
| 5 | 开板次数 | ≤ 1 次 |
| 6 | 封单金额 | > 流通市值 1% |
| 7 | 题材热度 | 属于当日热点 TOP10 |
| 8 | 股价位置 | 低位首板或平台突破 |

### 5.2 强制约束

| 通过情况 | 系统行为 |
|---------|---------|
| 全部通过 | 评分正常计算 |
| 1-2 项未通过 | 黄色警告 |
| ≥3 项未通过 | 红色警告，评分上限锁定 55 分 |
| 三板以上 | 无论是否通过，弹窗警告 |

---

## 6. 炸板风险预警

对已封板股票实时监控，满足任一条件触发：

| # | 条件 | 级别 |
|---|------|------|
| C1 | 封单 5 分钟减少 >30% | 🟡 黄色 |
| C2 | 单笔 >5000 手卖单 | 🟡 黄色 |
| C3 | 同板块龙头炸板 | 🔴 红色 |
| C4 | 大盘 5 分钟急跌 >0.5% | 🔴 红色 |
| C5 | 涨停打开且 3 分钟未回封 | 🔴 红色 |
| C6 | 封单 < 流通市值 0.3% | 🔴 红色 |

**响应**: 黄色 → 密切关注准备减仓；红色 → 建议立即减仓或清仓 + 可设价格提醒。

---

## 7. 数据输出

### 7.1 输出格式

| 格式 | 路径 | 用途 |
|------|------|------|
| Markdown | `reports/seal_plate/seal_plate_YYYYMMDD.md` | 人工复盘 |
| JSON | `reports/seal_plate/seal_plate_YYYYMMDD.json` | 量化对接 |
| 飞书卡片 | Webhook 推送 | 移动端实时通知 |

### 7.2 REST API

| 端点 | 说明 |
|------|------|
| `GET /api/v1/seal-plate/report?date=YYYYMMDD` | 分析报告 |
| `GET /api/v1/seal-plate/sentiment` | 情绪周期数据 |
| `GET /api/v1/seal-plate/stock-pool` | 候选股票池 |
| `GET /api/v1/seal-plate/checklist/{code}` | 八项标准检查详情 |
| `GET /api/v1/seal-plate/stocks` | 涨停股票列表 |

---

## 8. 使用方式

### 命令行

```bash
python main.py --seal-plate-only --force-run        # 独立运行
python main.py --seal-plate                          # 组合运行
python main.py --seal-plate-only --seal-min-score 70 # 调整阈值
python main.py --seal-plate-only --no-notify         # 禁用通知
python main.py --webui-only                          # 启动 Web 界面
```

### 配置 (.env)

```bash
SEAL_PLATE_ENABLED=true
SEAL_PLATE_MIN_SCORE=60
SEAL_PLATE_NOTIFICATION_ENABLED=true
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

### Python API

```python
from src.seal_plate import SealPlateService

service = SealPlateService(config={'min_score': 60, 'feishu_enabled': True})
report = service.run(date='20260521', force=True)

# 关键字段
report.total_limit_up       # 涨停总数
report.sentiment_index      # 情绪指数
report.sentiment_phase      # 周期阶段
report.strong_stocks        # 强势标的列表
report.leader_stocks        # 龙头股列表
report.risk_stocks          # 风险标的列表
```

---

## 9. 数据模型

```python
@dataclass
class SealPlateStock:
    code: str; name: str; close_price: float; change_pct: float
    limit_up_price: float; turnover_rate: float; volume: float
    amount: float; seal_amount: float; seal_time: str
    open_count: int; sector: str; market: str; reason: str
    # 评分字段 (Analyzer 填充)
    score: int = 0; plate_type: PlateType = PlateType.NORMAL
    seal_strength: SealStrength = SealStrength.NORMAL
    eight_standard_pass: int = 0; risk_level: int = 0

@dataclass
class SealPlateReport:
    date: str; total_limit_up: int
    strong_stocks: list; leader_stocks: list; risk_stocks: list
    sentiment_index: float; sentiment_phase: str
    sector_heatmap: dict; bomb_count: int; max_consecutive: int

class PlateType(Enum):
    NORMAL = "normal"; FIRST = "first"; TURNING = "turning"

class SealStrength(Enum):
    STRONG = "strong"; NORMAL = "normal"; WEAK = "weak"; BROKEN = "broken"
```
