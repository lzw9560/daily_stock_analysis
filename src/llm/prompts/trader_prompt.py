# -*- coding: utf-8 -*-
"""交易员视角 Prompt 模板（交易系统升级 Phase 1）

核心特性:
- 强制结构化 JSON 输出（动作/仓位/入场方式/止盈止损）
- 包含短线战法识别（首板/连板/低吸/N字/反包等）
- 情绪周期上下文注入
- 板块共振检查
- 交易纪律优先级约束
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from json_repair import repair_json

logger = logging.getLogger(__name__)


# ============================================================
# 输出 Schema 定义
# ============================================================

TRADER_OUTPUT_SCHEMA = {
    "action": "buy/sell/hold/wait",
    "position_size": "light(0-20%)/medium(20-50%)/heavy(50-80%)/full",
    "position_pct": 0.0,          # 具体仓位百分比
    "entry_method": "seal_plate/low_suck/breakout/market/limit_order",
    "entry_price_range": {"min": 0.0, "max": 0.0},
    "stop_loss": 0.0,              # 止损价
    "stop_loss_pct": 0.0,          # 止损百分比
    "take_profit": 0.0,            # 止盈价
    "take_profit_rr": 0.0,         # 盈亏比
    "confidence": 0.0,             # 0-1
    "strategy_pattern": "首板/连板/低吸/反包/N字/平台突破/均线多头/涨停敢死队/尾盘偷袭/none",
    "sector_resonance": False,     # 板块共振
    "sentiment_phase": "冰点期/修复期/分化期/高潮期/退潮期/unknown",
    "time_horizon": "日内/1-3天/1-2周/月度",
    "expected_hold_days": 0,
    "reasons": ["理由"],
    "risks": ["风险"],
    "key_levels": {
        "support": [0.0],
        "resistance": [0.0],
    },
    "checklist": {
        "trend_ok": False,
        "volume_ok": False,
        "sentiment_ok": False,
        "risk_ok": False,
        "sector_ok": False,
    },
}


@dataclass
class TraderDecision:
    """交易员决策结果"""

    action: str                          # buy/sell/hold/wait
    position_size: str                   # light/medium/heavy/full
    position_pct: float = 0.0            # 仓位百分比
    entry_method: str = "market"         # seal_plate/low_suck/breakout/market/limit_order
    entry_price_min: float = 0.0
    entry_price_max: float = 0.0
    stop_loss: float = 0.0
    stop_loss_pct: float = 0.0
    take_profit: float = 0.0
    take_profit_rr: float = 0.0
    confidence: float = 0.5
    strategy_pattern: str = "none"
    sector_resonance: bool = False
    sentiment_phase: str = "unknown"
    time_horizon: str = "1-3天"
    expected_hold_days: int = 3
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    support_levels: list[float] = field(default_factory=list)
    resistance_levels: list[float] = field(default_factory=list)
    checklist: dict[str, bool] = field(default_factory=dict)
    raw_response: dict = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        """是否可执行"""
        return self.action in ("buy", "sell") and self.confidence >= 0.5

    @property
    def risk_reward_ratio(self) -> float:
        """盈亏比"""
        if self.stop_loss_pct <= 0 or self.take_profit_rr <= 0:
            return 0.0
        return self.take_profit_rr

    @property
    def summary(self) -> str:
        parts = [
            f"动作: {self.action}",
            f"仓位: {self.position_size}({self.position_pct:.0f}%)",
            f"入场: {self.entry_method} [{self.entry_price_min:.2f}-{self.entry_price_max:.2f}]",
            f"止损: {self.stop_loss:.2f}(-{self.stop_loss_pct:.1f}%)",
            f"止盈: {self.take_profit:.2f}(RR {self.take_profit_rr:.1f}:1)",
            f"战法: {self.strategy_pattern}",
            f"信心: {self.confidence:.0%}",
        ]
        return " | ".join(parts)


# ============================================================
# 交易员 System Prompt
# ============================================================

TRADER_SYSTEM_PROMPT = """你是一个资深A股短线交易员，专精打板、低吸、趋势交易。你需要基于提供的数据给出明确的交易决策。

## 核心原则

### 1. 交易纪律（最高优先级）
- 绝不追高：偏离MA5超过5%时坚决不买入
- 严格止损：每笔交易必须预设止损位，亏损达到止损位立即执行
- 仓位管理：单票仓位不超过总资金30%，总仓位根据情绪周期调整
- 不接飞刀：退潮期不参与高位接力，不补仓亏损股
- 盈亏比要求：止盈位与止损位的盈亏比至少1.5:1

### 2. 战法识别
根据技术面数据识别以下战法形态：
- 首板挖掘：低位首板+板块共振+量价突破
- 连板接力：2-3板龙头+充分换手+板块梯队完整
- 炸板回封：涨停打开后资金回流+封单恢复
- 低吸龙头：龙头股回调至MA10/MA20支撑+缩量企稳
- 反包战法：阴线后阳线完全吃掉前日实体
- N字反击：涨停→回调2-3天→再次涨停
- 平台突破：横盘N日+放量突破+回踩确认
- 均线多头：MA5>MA10>MA20>MA60+缩量回踩
- 涨停敢死队：一字板开板+巨量换手+次日溢价
- 尾盘偷袭：14:30后拉升+量比>3

### 3. 情绪周期适配
- 冰点期：极小仓位试错首板，空仓为主
- 修复期：轻仓参与低位首板和修复机会
- 分化期：聚焦主线龙头，去弱留强
- 高潮期：持股为主，新开仓减半，不追加速板
- 退潮期：果断减仓/清仓，不参与任何接力

### 4. 板块共振要求
- 打板类买入必须要求所属板块有至少2只涨停
- 低吸类买入要求板块处于上升趋势
- 板块退潮时，个股无论多强都应减仓

## 输出格式

必须严格输出以下 JSON 格式，不要输出任何其他内容：

```json
{
    "action": "buy|sell|hold|wait",
    "position_size": "light|medium|heavy|full",
    "position_pct": 15.0,
    "entry_method": "seal_plate|low_suck|breakout|market|limit_order",
    "entry_price_range": {"min": 10.50, "max": 11.00},
    "stop_loss": 9.80,
    "stop_loss_pct": 7.0,
    "take_profit": 13.00,
    "take_profit_rr": 2.5,
    "confidence": 0.75,
    "strategy_pattern": "首板|连板|低吸|反包|N字|平台突破|均线多头|涨停敢死队|尾盘偷袭|none",
    "sector_resonance": true,
    "sentiment_phase": "冰点期|修复期|分化期|高潮期|退潮期",
    "time_horizon": "日内|1-3天|1-2周|月度",
    "expected_hold_days": 3,
    "reasons": [
        "理由1：均线多头排列，MA5>MA10>MA20",
        "理由2：回踩MA10支撑确认，缩量企稳",
        "理由3：所属板块今日3只涨停，共振确认"
    ],
    "risks": [
        "风险1：上方MA60压力位12.50元",
        "风险2：大盘情绪处于分化期，存在轮动风险"
    ],
    "key_levels": {
        "support": [10.00, 9.50],
        "resistance": [12.00, 12.50]
    },
    "checklist": {
        "trend_ok": true,
        "volume_ok": true,
        "sentiment_ok": true,
        "risk_ok": true,
        "sector_ok": true
    }
}
```

## 判定规则

- action=buy 且 confidence>=0.7 → 正常买入
- action=buy 且 confidence<0.7 → 降低仓位到建议的50%
- action=sell → 无论盈亏，执行卖出
- action=hold → 持股不动，但有明确止盈止损
- action=wait → 观望，无仓位
- 所有决策必须给出具体的入场价、止损价、止盈价"""


# ============================================================
# 短线交易员 Prompt（更聚焦打板/短线）
# ============================================================

TRADER_SHORT_TERM_PROMPT = """你是A股短线打板选手，擅长首板挖掘和连板接力。

## 打板规则
1. 封板速度：9:30-10:00封板最佳（+20分），10:00-10:30封板良好（+10分），午后封板一般（-10分）
2. 封单强度：封单>流通市值2%→强封，>1%→正常，<0.5%→弱封
3. 换手率：5-20%最佳，<1%一字板接力难，>25%分歧大
4. 板块共振：所属板块至少2只涨停，有板块龙头更好
5. 连板高度：首板安全性最高，3板以上每增加1板降低20%仓位

## 低吸规则
1. 龙头识别：板块内最早封板+封单最强的标的
2. 回调幅度：龙头首次分歧，回调到MA10（-5~-10%）或MA20（-10~-15%）
3. 企稳信号：缩量止跌+下影线+不再创新低
4. 反弹目标：前高或MA5

## 风控红线
1. 单票最大亏损不超过总资金3%
2. 一日内连续2笔亏损→停止当日交易
3. 周亏损超过5%→下周仓位减半
4. 炸板当日不追回封"""


# ============================================================
# User Prompt 模板
# ============================================================

TRADER_USER_PROMPT_TEMPLATE = """## 股票信息
{stock_info}

## 技术面数据
{technical_data}

## 情绪周期
当前情绪阶段: {sentiment_phase}（指数: {sentiment_score}/100）
{sentiment_detail}

## 板块数据
所属板块: {sector_name}
板块强度: {sector_strength}
板块涨停数: {sector_limit_up_count}
板块涨幅: {sector_change_pct}%

## 资金面
北向资金: {north_flow}
主力资金: {main_force_flow}
大单动向: {big_order_summary}

## 消息面
{news_summary}

## 自选股战法信号
{strategy_signals}

请基于以上数据给出交易决策。"""


# ============================================================
# 辅助函数
# ============================================================

def get_trader_system_prompt(
    *,
    short_term: bool = False,
    market: str = "A股",
) -> str:
    """获取交易员系统 Prompt

    Args:
        short_term: 是否使用短线聚焦版本
        market: 市场类型
    """
    base = TRADER_SHORT_TERM_PROMPT if short_term else TRADER_SYSTEM_PROMPT
    return base


def format_trader_user_prompt(
    *,
    stock_code: str = "",
    stock_name: str = "",
    stock_info: str = "",
    technical_data: str = "",
    sentiment_phase: str = "unknown",
    sentiment_score: int = 50,
    sentiment_detail: str = "",
    sector_name: str = "",
    sector_strength: str = "",
    sector_limit_up_count: int = 0,
    sector_change_pct: float = 0.0,
    north_flow: str = "无数据",
    main_force_flow: str = "无数据",
    big_order_summary: str = "无异常",
    news_summary: str = "无最新消息",
    strategy_signals: str = "无战法信号",
) -> str:
    """格式化交易员 User Prompt"""
    return TRADER_USER_PROMPT_TEMPLATE.format(
        stock_info=stock_info or f"{stock_code} {stock_name}",
        technical_data=technical_data or "无技术面数据",
        sentiment_phase=sentiment_phase,
        sentiment_score=sentiment_score,
        sentiment_detail=sentiment_detail,
        sector_name=sector_name or "未分类",
        sector_strength=sector_strength or "未知",
        sector_limit_up_count=sector_limit_up_count,
        sector_change_pct=sector_change_pct,
        north_flow=north_flow,
        main_force_flow=main_force_flow,
        big_order_summary=big_order_summary,
        news_summary=news_summary,
        strategy_signals=strategy_signals,
    )


def parse_trader_response(response_text: str) -> Optional[TraderDecision]:
    """解析 LLM 返回的交易决策 JSON

    Args:
        response_text: LLM 原始响应文本

    Returns:
        TraderDecision 或 None（解析失败）
    """
    try:
        # 尝试提取 JSON
        json_str = response_text.strip()

        # 移除 markdown 代码块标记
        if json_str.startswith("```"):
            lines = json_str.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            json_str = "\n".join(lines)

        # 使用 json_repair 修复可能的 JSON 格式问题
        repaired = repair_json(json_str)
        data: dict = json.loads(repaired)

        return TraderDecision(
            action=data.get("action", "hold"),
            position_size=data.get("position_size", "light"),
            position_pct=float(data.get("position_pct", 0)),
            entry_method=data.get("entry_method", "market"),
            entry_price_min=float(data.get("entry_price_range", {}).get("min", 0)),
            entry_price_max=float(data.get("entry_price_range", {}).get("max", 0)),
            stop_loss=float(data.get("stop_loss", 0)),
            stop_loss_pct=float(data.get("stop_loss_pct", 0)),
            take_profit=float(data.get("take_profit", 0)),
            take_profit_rr=float(data.get("take_profit_rr", 0)),
            confidence=float(data.get("confidence", 0.5)),
            strategy_pattern=data.get("strategy_pattern", "none"),
            sector_resonance=bool(data.get("sector_resonance", False)),
            sentiment_phase=data.get("sentiment_phase", "unknown"),
            time_horizon=data.get("time_horizon", "1-3天"),
            expected_hold_days=int(data.get("expected_hold_days", 3)),
            reasons=data.get("reasons", []),
            risks=data.get("risks", []),
            support_levels=data.get("key_levels", {}).get("support", []),
            resistance_levels=data.get("key_levels", {}).get("resistance", []),
            checklist=data.get("checklist", {}),
            raw_response=data,
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.warning(f"解析交易决策失败: {e}, raw: {response_text[:200]}...")
        return None
