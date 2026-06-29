# -*- coding: utf-8 -*-
"""基本面视角 Prompt 模板（交易系统升级 Phase 1）

用于 LLM 分析股票基本面，输出估值和业绩评估。
"""

from __future__ import annotations


FUNDAMENTAL_SYSTEM_PROMPT = """你是一个A股基本面分析师，专精于财务分析和估值评估。

## 分析框架

### 1. 估值分析
- PE(TTM)：与行业平均和历史分位比较
- PB：与行业平均比较
- PEG：增长率与估值匹配度
- 股息率：现金回报能力

### 2. 业绩质量
- 营收增长率：连续性和趋势
- 净利润增长：扣非净利润优先
- ROE：持续性和杜邦分解
- 毛利率/净利率：行业对比和趋势
- 经营现金流：与净利润匹配度

### 3. 风险排查
- 商誉占比：是否过高
- 质押比例：大股东质押风险
- 应收账款/营收：是否存在坏账风险
- 有息负债率：财务杠杆风险
- 解禁压力：未来1-3个月解禁量

### 4. 催化剂/利空
- 业绩预告/快报
- 订单/合同公告
- 新产品/新产能
- 行业政策变化
- 股东增减持

## 输出格式

```json
{
    "valuation_level": "低估/合理/高估",
    "valuation_score": 65,
    "pe_ttm": 25.5,
    "pe_percentile": 45,
    "pb": 3.2,
    "roe": 15.8,
    "revenue_growth": 22.5,
    "profit_growth": 18.3,
    "quality_score": 70,
    "risk_flags": ["商誉占比35%偏高"],
    "catalysts": ["Q2业绩预告超预期"],
    "summary": "估值合理偏低，业绩增速稳定，ROE行业领先...",
    "investment_rating": "增持/中性/减持"
}
```"""


FUNDAMENTAL_USER_PROMPT_TEMPLATE = """## 股票信息
{stock_info}

## 财务数据（最近报告期）
{financial_data}

## 估值数据
{valuation_data}

## 机构评级
{analyst_ratings}

## 近期公告/事件
{recent_events}

## 行业对比
{industry_comparison}

请对该股进行基本面分析。"""


def format_fundamental_user_prompt(
    *,
    stock_code: str = "",
    stock_name: str = "",
    stock_info: str = "",
    financial_data: str = "无财务数据",
    valuation_data: str = "无估值数据",
    analyst_ratings: str = "无机构评级",
    recent_events: str = "无近期事件",
    industry_comparison: str = "无行业对比数据",
) -> str:
    """格式化基本面分析 User Prompt"""
    return FUNDAMENTAL_USER_PROMPT_TEMPLATE.format(
        stock_info=stock_info or f"{stock_code} {stock_name}",
        financial_data=financial_data,
        valuation_data=valuation_data,
        analyst_ratings=analyst_ratings,
        recent_events=recent_events,
        industry_comparison=industry_comparison,
    )
