"""
龙虎榜机构风险分析器

基于龙虎榜席位数据，分析机构/游资买卖行为，
输出机构风险提示指标，帮助推荐系统过滤高风险标的。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DragonTigerInstitutionRisk:
    """龙虎榜机构风险分析结果"""
    code: str
    name: str
    
    # 机构参与度
    has_institution_buy: bool = False      # 机构席位买入
    has_institution_sell: bool = False     # 机构席位卖出
    institution_net_buy: float = 0.0       # 机构净买入额（万元）
    institution_buy_ratio: float = 0.0     # 机构买入占比
    institution_sell_ratio: float = 0.0     # 机构卖出占比
    
    # 游资风险
    hot_money_count: int = 0               # 游资席位数量
    hot_money_buy_ratio: float = 0.0       # 游资买入占比
    hot_money_pure_pump: bool = False      # 纯游资对倒（无机构参与）
    
    # 散户风险
    retail_heavy: bool = False             # 散户席位主导
    one_day_tour_risk: bool = False        # 一日游席位特征
    
    # 综合风险评分（0-100，越高风险越大）
    risk_score: int = 0
    risk_level: str = "low"               # low/medium/high/critical
    risk_reasons: list[str] = field(default_factory=list)
    
    # 操作建议
    suggestion: str = ""


# 知名游资席位（含胜率）
KNOWN_HOT_MONEY = {
    "章盟主": {"type": "顶级游资", "style": "龙头战法", "win_rate": 0.68, "risk_score": 30},
    "方新侠": {"type": "顶级游资", "style": "趋势接力", "win_rate": 0.72, "risk_score": 25},
    "作手新一": {"type": "实力游资", "style": "首板挖掘", "win_rate": 0.65, "risk_score": 35},
    "炒股养家": {"type": "顶级游资", "style": "情绪周期", "win_rate": 0.75, "risk_score": 20},
    "赵老哥": {"type": "实力游资", "style": "连板龙头", "win_rate": 0.70, "risk_score": 30},
    "小鳄鱼": {"type": "实力游资", "style": "趋势加速", "win_rate": 0.62, "risk_score": 35},
    "上塘路": {"type": "一日游游资", "style": "隔日超短", "win_rate": 0.45, "risk_score": 60},
    "文一西路": {"type": "一日游游资", "style": "快速套利", "win_rate": 0.40, "risk_score": 65},
    "上海超短": {"type": "实力游资", "style": "打板套利", "win_rate": 0.55, "risk_score": 45},
}

# 一日游席位特征关键词
ONE_DAY_TOUR_KEYWORDS = [
    "拉萨东环路", "拉萨团结路", "拉萨东城区",
    "上塘路", "文一西路", "上海花园石桥路",
    "国金上海", "华泰厦门"
]


def analyze_dragon_tiger_risk(
    code: str,
    name: str,
    buy_seats: list[dict],
    sell_seats: list[dict],
) -> DragonTigerInstitutionRisk:
    """
    分析龙虎榜数据中的机构风险
    
    Args:
        code: 股票代码
        name: 股票名称
        buy_seats: 买入席位列表 [{"name": "xxx", "amount": 1000.0, "type": "机构"}, ...]
        sell_seats: 卖出席位列表
    
    Returns:
        DragonTigerInstitutionRisk 风险分析结果
    """
    result = DragonTigerInstitutionRisk(code=code, name=name)
    
    # 1. 统计机构买卖
    inst_buy = sum(s["amount"] for s in buy_seats if s.get("type") == "机构")
    inst_sell = sum(s["amount"] for s in sell_seats if s.get("type") == "机构")
    total_buy = sum(s["amount"] for s in buy_seats)
    total_sell = sum(s["amount"] for s in sell_seats)
    
    result.has_institution_buy = inst_buy > 0
    result.has_institution_sell = inst_sell > 0
    result.institution_net_buy = inst_buy - inst_sell
    result.institution_buy_ratio = inst_buy / total_buy if total_buy > 0 else 0
    result.institution_sell_ratio = inst_sell / total_sell if total_sell > 0 else 0
    
    # 2. 统计游资
    hot_money_buy = 0
    hot_money_names = []
    for s in buy_seats:
        s_name = s.get("name", "")
        if s_name in KNOWN_HOT_MONEY or any(
            kw in s_name for kw in ONE_DAY_TOUR_KEYWORDS
        ):
            result.hot_money_count += 1
            hot_money_buy += s["amount"]
            hot_money_names.append(s_name)
    
    result.hot_money_buy_ratio = hot_money_buy / total_buy if total_buy > 0 else 0
    
    # 纯游资对倒（无机构参与）
    if result.hot_money_count >= 2 and not result.has_institution_buy:
        result.hot_money_pure_pump = True
    
    # 3. 检查散户/一日游席位
    for s in buy_seats:
        s_name = s.get("name", "")
        if any(kw in s_name for kw in ONE_DAY_TOUR_KEYWORDS):
            result.one_day_tour_risk = True
            break
    
    if not result.one_day_tour_risk:
        for s in sell_seats:
            s_name = s.get("name", "")
            if any(kw in s_name for kw in ONE_DAY_TOUR_KEYWORDS):
                result.one_day_tour_risk = True
                break
    
    if result.hot_money_buy_ratio > 0.6:
        result.one_day_tour_risk = True
    
    # 4. 综合风险评分
    risk_score = 0
    risk_reasons = []
    
    # 机构净卖出 → 高风险
    if result.institution_net_buy < -1000:
        risk_score += 35
        risk_reasons.append(f"机构净卖出{abs(result.institution_net_buy):.0f}万，机构出货信号")
    elif result.institution_net_buy < -300:
        risk_score += 20
        risk_reasons.append(f"机构小幅净卖出{abs(result.institution_net_buy):.0f}万")
    elif result.institution_net_buy > 500:
        risk_score -= 20
    elif result.institution_net_buy > 100:
        risk_score -= 10
    
    # 纯游资对倒 → 高风险
    if result.hot_money_pure_pump:
        risk_score += 30
        risk_reasons.append(f"纯游资对倒（{', '.join(hot_money_names)}），无机构参与，易一日游")
    
    # 一日游席位 → 高风险
    if result.one_day_tour_risk:
        risk_score += 25
        risk_reasons.append("识别到一日游席位参与，短期波动风险高")
    
    # 高胜率游资 → 加分
    for s_name in hot_money_names:
        if s_name in KNOWN_HOT_MONEY:
            info = KNOWN_HOT_MONEY[s_name]
            if info["win_rate"] >= 0.7:
                risk_score -= 5
                risk_reasons.append(f"顶级游资「{s_name}」买入（历史胜率{info['win_rate']:.0%}），跟随价值高")
    
    # 机构买入占比低+游资占比高 → 风险
    if result.institution_buy_ratio < 0.2 and result.hot_money_buy_ratio > 0.5:
        risk_score += 15
        risk_reasons.append("机构参与度低，游资主导，持续性存疑")
    
    # 5. 确定风险等级
    result.risk_score = max(0, min(100, risk_score))
    result.risk_reasons = risk_reasons
    
    if result.risk_score >= 70:
        result.risk_level = "critical"
        result.suggestion = "⚠️ 龙虎榜机构风险极高，强烈建议回避"
    elif result.risk_score >= 50:
        result.risk_level = "high"
        result.suggestion = "⚠️ 龙虎榜机构风险较高，建议小仓位试错或观望"
    elif result.risk_score >= 30:
        result.risk_level = "medium"
        result.suggestion = "龙虎榜机构风险中等，正常仓位参与，关注机构动向"
    else:
        result.risk_level = "low"
        result.suggestion = "龙虎榜机构风险较低，机构参与积极，可持续关注"
    
    logger.info(
        "龙虎榜风险分析 [%s %s]: 风险分=%d 等级=%s 机构净买=%.0f万 游资=%d席",
        code, name, result.risk_score, result.risk_level,
        result.institution_net_buy, result.hot_money_count
    )
    
    return result


def get_dragon_tiger_risk_factors(
    code: str,
    name: str,
    score: int,
    seal_amount: float,
) -> DragonTigerInstitutionRisk:
    """
    基于评分和封单金额估算龙虎榜机构风险（无实际龙虎榜数据时的估算）
    
    用于在没有实际龙虎榜 API 时，基于已知指标估算风险。
    高分标的通常吸引机构，低分标的通常是游资博弈。
    """
    result = DragonTigerInstitutionRisk(code=code, name=name)
    
    # 基于评分估算机构参与概率
    if score >= 80:
        # 高分标的：假设有机构参与
        result.has_institution_buy = True
        result.institution_net_buy = seal_amount * 0.3
        result.institution_buy_ratio = 0.4
        result.risk_score = max(0, 30 - score // 3)
        result.risk_level = "low"
        result.suggestion = "高分标的，机构参与度预期较高，风险可控"
    elif score >= 65:
        # 中分标的：混合参与
        result.institution_net_buy = seal_amount * 0.1
        result.institution_buy_ratio = 0.2
        result.risk_score = max(0, 50 - score // 2)
        result.risk_level = "medium"
        result.suggestion = "中等评分，需关注机构实际参与程度"
    else:
        # 低分标的：游资主导
        result.hot_money_pure_pump = True
        result.one_day_tour_risk = True
        result.institution_net_buy = -seal_amount * 0.05
        result.risk_score = 60 + (70 - score) // 2
        result.risk_level = "high"
        result.risk_reasons = ["低评分标的，游资博弈为主，风险较高"]
        result.suggestion = "低评分标的，游资主导风险较高，建议观望"
    
    logger.info(
        "龙虎榜风险估算 [%s %s]: 风险分=%d 等级=%s (评分=%d)",
        code, name, result.risk_score, result.risk_level, score
    )
    
    return result
