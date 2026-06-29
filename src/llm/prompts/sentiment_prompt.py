# -*- coding: utf-8 -*-
"""情绪视角 Prompt 模板（交易系统升级 Phase 1）

用于 LLM 分析市场情绪周期，输出情绪诊断报告。
"""

from __future__ import annotations


SENTIMENT_SYSTEM_PROMPT = """你是一个A股市场情绪分析师，专精于通过盘面数据判断市场情绪周期阶段。

## 分析框架

### 情绪周期五阶段
1. 冰点期：涨停<20只，炸板率>40%，连板高度≤2，跌停增多
2. 修复期：涨停回升至30-50只，首板增多，炸板率下降
3. 分化期：连板高度提升至3-5板，板块轮动加快，主线开始清晰
4. 高潮期：涨停>80只，连板密集，普涨格局，赚钱效应极强
5. 退潮期：高位股杀跌，跌停增多，炸板率飙升，龙头见顶

### 核心指标权重
- 涨停家数：最直观的情绪指标（权重25%）
- 炸板率/封板率：资金信心指标（权重20%）
- 连板高度：空间高度决定市场风险偏好（权重15%）
- 昨日涨停溢价：赚钱效应直接体现（权重15%）
- 北向资金：外资态度（权重10%）
- 两市成交额：量能是情绪的燃料（权重10%）
- 上涨/下跌家数比：广度指标（权重5%）

### 情绪转折识别
- 冰点→修复：涨停数连续2日回升+首板增多
- 修复→分化：连板高度突破3板+主线板块出现
- 分化→高潮：涨停>80+连板密集+赚钱效应扩散
- 高潮→退潮：高位龙头炸板+涨停数骤降+跌停增多
- 退潮→冰点：涨停<20+连板高度回到2板

## 输出格式

```json
{
    "current_phase": "冰点期/修复期/分化期/高潮期/退潮期",
    "phase_confidence": 0.85,
    "sentiment_score": 45,
    "trend": "升温/降温/持平",
    "key_indicators": {
        "limit_up_count": {"value": 35, "score": 45, "trend": "up"},
        "seal_rate": {"value": 0.72, "score": 65, "trend": "stable"},
        "max_consecutive": {"value": 4, "score": 60, "trend": "up"},
        "bomb_rate": {"value": 0.22, "score": 70, "trend": "down"},
        "prev_day_premium": {"value": 2.5, "score": 55, "trend": "stable"}
    },
    "position_advice": "建议仓位30-50%，聚焦主线龙头",
    "risk_alerts": ["连板高度已达4板，注意高位接力风险"],
    "hot_sectors": ["AI应用", "机器人"],
    "avoid_sectors": ["房地产"],
    "next_phase_prediction": "分化期可能在1-2日内升级为高潮期",
    "summary": "市场处于分化期末段，涨停数稳步回升至35只，封板率72%表现健康..."
}
```"""


SENTIMENT_USER_PROMPT_TEMPLATE = """## 今日市场数据

涨停家数: {limit_up_count}
跌停家数: {limit_down_count}
封板率: {seal_rate:.1%}
炸板率: {bomb_rate:.1%}
最高连板数: {max_consecutive}
连板分布: {connectivity_distribution}
昨日涨停今日溢价: {avg_premium:.1f}%
连板晋级率: {advance_rate:.1%}

上涨家数: {advance_count}
下跌家数: {decline_count}

北向资金净流入: {north_flow}亿
两市成交额: {turnover_total}亿（环比{volume_change:+.1f}%）

## 前一日情绪
前日情绪指数: {prev_score}/100
前日阶段: {prev_phase}

## 今日板块热点
{hot_sectors}

## 龙头股表现
{leader_performance}

请分析当前市场情绪周期。"""


def format_sentiment_user_prompt(
    *,
    limit_up_count: int = 0,
    limit_down_count: int = 0,
    seal_rate: float = 0.0,
    bomb_rate: float = 0.0,
    max_consecutive: int = 0,
    connectivity_distribution: str = "无数据",
    avg_premium: float = 0.0,
    advance_rate: float = 0.0,
    advance_count: int = 0,
    decline_count: int = 0,
    north_flow: float = 0.0,
    turnover_total: float = 0.0,
    volume_change: float = 0.0,
    prev_score: int = 50,
    prev_phase: str = "未知",
    hot_sectors: str = "无数据",
    leader_performance: str = "无数据",
) -> str:
    """格式化情绪分析 User Prompt"""
    return SENTIMENT_USER_PROMPT_TEMPLATE.format(
        limit_up_count=limit_up_count,
        limit_down_count=limit_down_count,
        seal_rate=seal_rate,
        bomb_rate=bomb_rate,
        max_consecutive=max_consecutive,
        connectivity_distribution=connectivity_distribution,
        avg_premium=avg_premium,
        advance_rate=advance_rate,
        advance_count=advance_count,
        decline_count=decline_count,
        north_flow=north_flow,
        turnover_total=turnover_total,
        volume_change=volume_change,
        prev_score=prev_score,
        prev_phase=prev_phase,
        hot_sectors=hot_sectors,
        leader_performance=leader_performance,
    )
