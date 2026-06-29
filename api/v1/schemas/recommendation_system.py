# -*- coding: utf-8 -*-
"""推荐系统页面 API Schema — 10个推荐页面的请求/响应模型."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================================
#  1. 大盘走势 (MarketTrendPage)
# ============================================================================

class IndexItem(BaseModel):
    """指数行情"""
    name: str = Field(..., description="指数名称")
    code: str = Field(..., description="指数代码")
    price: float = Field(..., description="当前点位")
    change: float = Field(..., description="涨跌额")
    change_pct: float = Field(..., description="涨跌幅(%)")
    volume: float = Field(..., description="成交额(亿)")


class TrendSeries(BaseModel):
    """趋势序列"""
    dates: List[str] = Field(default_factory=list, description="日期标签")
    price: List[float] = Field(default_factory=list, description="价格序列")
    ma5: List[float] = Field(default_factory=list, description="MA5序列(前4天为0)")
    volume: List[float] = Field(default_factory=list, description="成交量序列(亿)")


class MarketTrendResponse(BaseModel):
    """大盘走势响应"""
    indices: List[IndexItem] = Field(default_factory=list)
    trend: TrendSeries = Field(default_factory=TrendSeries)
    up_count: int = 0
    down_count: int = 0
    total_amount: str = Field("", description="两市成交额")
    limit_up_count: int = Field(0, description="涨停家数")
    limit_down_count: int = Field(0, description="跌停家数")
    trade_date: str = Field("", description="交易日期")
    data_source: str = Field("db", description="数据来源")
    is_realtime: bool = Field(False, description="是否实时数据")
    data_available: bool = Field(True, description="是否有有效数据")


# ============================================================================
#  2. 每日复盘 (DailyReviewPage)
# ============================================================================

class DailyStats(BaseModel):
    """每日统计"""
    up_count: int = 0
    down_count: int = 0
    flat_count: int = 0
    limit_up: int = 0
    limit_down: int = 0
    north_bound_net: float = Field(0, description="北向资金净流入(亿)")
    margin_balance: Optional[float] = Field(None, description="融资融券余额(亿)")
    turnover: float = Field(0, description="成交额(亿)")
    amplitude: float = Field(0, description="振幅(%)")


class LhbItem(BaseModel):
    """龙虎榜条目"""
    name: str = Field("", description="股票名称")
    code: str = Field("", description="股票代码")
    change_pct: Optional[float] = Field(None, description="涨跌幅(%)")
    buy_amount: Optional[float] = Field(None, description="买入金额(亿)")
    sell_amount: Optional[float] = Field(None, description="卖出金额(亿)")
    net_amount: Optional[float] = Field(None, description="净买入(亿)")
    reason: Optional[str] = Field(None, description="上榜原因")


class BlockTradeItem(BaseModel):
    """大宗交易条目"""
    name: str = Field("", description="股票名称")
    code: str = Field("", description="股票代码")
    premium_rate: float = Field(0, description="溢价率(%)")
    amount: Optional[float] = Field(None, description="成交额(亿)")


class BlockTradeSummary(BaseModel):
    """大宗交易概况"""
    today_count: int = Field(0, description="今日大宗交易笔数")
    total_amount: Optional[float] = Field(None, description="总成交额(亿)")
    top_premium: List[BlockTradeItem] = Field(default_factory=list)
    top_discount: List[BlockTradeItem] = Field(default_factory=list)


class SectorLeader(BaseModel):
    """领涨板块及龙头"""
    sector: str = Field(..., description="板块名称")
    change_pct: float = Field(..., description="涨幅(%)")
    leader: str = Field(..., description="龙头股票")
    leader_change_pct: float = Field(..., description="龙头涨幅(%)")


class DailyReviewResponse(BaseModel):
    """每日复盘响应"""
    trade_date: str = Field("", description="交易日期")
    stats: DailyStats = Field(default_factory=DailyStats)
    lhb_top: List[LhbItem] = Field(default_factory=list)
    block_trade: Optional[BlockTradeSummary] = Field(None, description="大宗交易概况")
    sector_leaders: List[SectorLeader] = Field(default_factory=list)
    data_source: str = Field("db", description="数据来源")
    is_realtime: bool = Field(False, description="是否实时数据")
    data_available: bool = Field(True, description="是否有有效数据")


# ============================================================================
#  3. 资金与板块热点 (CapitalFlowPage)
# ============================================================================

class MoneyFlowItem(BaseModel):
    """板块资金流向"""
    name: str = Field(..., description="板块名称")
    amount: float = Field(..., description="资金净额(亿)")


class NorthBoundItem(BaseModel):
    """北向资金个股流向"""
    name: str = Field("", description="股票名称")
    code: str = Field("", description="股票代码")
    net_inflow: float = Field(0, description="净流入(亿)")
    direction: str = Field("", description="方向: 流入/流出")


class SectorRotationItem(BaseModel):
    """板块轮动"""
    sector: str = Field(..., description="板块名称")
    flow_in: float = Field(..., description="流入(亿)")
    flow_out: float = Field(..., description="流出(亿)")
    net: float = Field(..., description="净额(亿)")
    status: str = Field(..., description="状态: 净流入/净流出")


class CapitalFlowResponse(BaseModel):
    """资金与板块热点响应"""
    trade_date: str = ""
    money_flow: List[MoneyFlowItem] = Field(default_factory=list)
    north_bound: List[NorthBoundItem] = Field(default_factory=list)
    sector_rotation: List[SectorRotationItem] = Field(default_factory=list)
    total_inflow: float = Field(0, description="总净流入(亿)")
    total_outflow: float = Field(0, description="总净流出(亿)")
    today_north_bound: float = Field(0, description="今日北向净额(亿)")
    total_amount: str = Field("", description="两市成交额")
    data_available: bool = Field(True, description="是否有有效数据")


# ============================================================================
#  4. 短线打板标的 (ShortTermTargetsPage)
# ============================================================================

class ShortTermTarget(BaseModel):
    """打板标的"""
    name: str = Field(..., description="股票名称")
    code: str = Field(..., description="股票代码")
    price: float = Field(..., description="现价")
    change_pct: float = Field(..., description="涨幅(%)")
    seal_strength: int = Field(..., description="封板强度(0-100)")
    seal_time: str = Field(..., description="封板时间")
    premium_rate: float = Field(..., description="溢价率(%)")
    rating: str = Field(..., description="评级 S/A/B/C")
    reason: str = Field(..., description="推荐逻辑")


class ShortTermTargetsResponse(BaseModel):
    """短线打板标的响应"""
    trade_date: str = ""
    targets: List[ShortTermTarget] = Field(default_factory=list)
    limit_up_count: int = Field(0, description="今日涨停家数")
    data_available: bool = Field(True, description="是否有有效数据")


# ============================================================================
#  5. 中长线波段建仓 (MidLongTermPage)
# ============================================================================

class MidLongTermPosition(BaseModel):
    """建仓标的"""
    name: str = Field(..., description="股票名称")
    code: str = Field(..., description="股票代码")
    price: float = Field(..., description="现价")
    target_price: float = Field(..., description="目标价")
    stop_loss: float = Field(..., description="止损价")
    valuation: str = Field(..., description="估值区间")
    pe_ttm: Optional[float] = Field(None, description="市盈率TTM")
    pb: Optional[float] = Field(None, description="市净率")
    roe: Optional[float] = Field(None, description="ROE(%)")
    trend: str = Field(..., description="趋势")
    strategy: str = Field(..., description="策略名称")
    score: int = Field(..., description="评分(0-100)")


class StrategyType(BaseModel):
    """策略分布"""
    name: str = Field(..., description="策略名称")
    desc: str = Field(..., description="策略描述")
    color: str = Field(..., description="颜色标识")
    count: int = Field(..., description="标的数量")


class MidLongTermResponse(BaseModel):
    """中长线波段建仓响应"""
    trade_date: str = ""
    positions: List[MidLongTermPosition] = Field(default_factory=list)
    strategies: List[StrategyType] = Field(default_factory=list)


# ============================================================================
#  6. 风控与仓位管理 (RiskControlPage)
# ============================================================================

class SectorRisk(BaseModel):
    """板块风险"""
    high: int = Field(0, description="高风险板块数")
    medium: int = Field(0, description="中风险板块数")
    low: int = Field(0, description="低风险板块数")


class PositionRiskItem(BaseModel):
    """持仓风险"""
    name: str = Field(..., description="股票名称")
    code: str = Field(..., description="股票代码")
    weight: float = Field(..., description="仓位权重(%)")
    stop_loss: float = Field(..., description="止损价")
    current_price: float = Field(..., description="现价")
    atr: float = Field(..., description="ATR值")
    risk_level: str = Field(..., description="风险等级: 高/中/低")
    advice: str = Field(..., description="操作建议")


class RiskControlResponse(BaseModel):
    """风控与仓位管理响应"""
    trade_date: str = ""
    vix: float = Field(0, description="市场VIX")
    margin_balance: float = Field(0, description="融资余额(亿)")
    margin_change: Optional[float] = Field(None, description="融资余额变化(亿)")
    forced_liquidation: float = Field(0, description="强平线(%)")
    sector_risk: SectorRisk = Field(default_factory=SectorRisk)
    position_risks: List[PositionRiskItem] = Field(default_factory=list)
    total_weight: float = Field(0, description="总仓位(%)")


# ============================================================================
#  7. 题材挖掘与龙头定性 (ThemeMiningPage)
# ============================================================================

class ThemeItem(BaseModel):
    """题材"""
    name: str = Field(..., description="题材名称")
    hotness: int = Field(..., description="热度(0-100)")
    trend: str = Field(..., description="趋势阶段")
    persistence: str = Field(..., description="持续性评估")
    leader_stock: str = Field(..., description="龙头股票")
    leader_change: float = Field(..., description="龙头涨幅(%)")
    follower_count: int = Field(..., description="跟风个股数量")
    catalyst: str = Field(..., description="催化剂")
    sub_themes: List[str] = Field(default_factory=list)
    related_stocks: List[str] = Field(default_factory=list)


class ThemeMiningResponse(BaseModel):
    """题材挖掘与龙头定性响应"""
    trade_date: str = ""
    themes: List[ThemeItem] = Field(default_factory=list)
    active_themes: int = Field(0, description="活跃题材数")
    total_followers: int = Field(0, description="跟风个股总数")
    main_theme: str = Field("", description="主线题材")
    hottest_leader: str = Field("", description="最热龙头")
    data_available: bool = Field(True, description="是否有有效数据")


# ============================================================================
#  8. 连板梯队与情绪周期 (LimitUpLadderPage)
# ============================================================================

class LadderItem(BaseModel):
    """连板梯队"""
    rank: int = Field(..., description="排名")
    board: str = Field(..., description="连板数")
    name: str = Field(..., description="股票名称")
    code: str = Field(..., description="股票代码")
    change_pct: float = Field(..., description="涨幅(%)")
    turnover: float = Field(..., description="换手率(%)")
    seal_amt: float = Field(..., description="封板资金(亿)")
    sentiment: str = Field(..., description="情绪定性")
    strength: int = Field(..., description="强度评分")


class EmotionHistoryItem(BaseModel):
    """情绪周期历史"""
    date: str = Field(..., description="日期")
    phase: str = Field(..., description="阶段")
    index: int = Field(..., description="情绪指数")


class EmotionCycle(BaseModel):
    """情绪周期"""
    phase: str = Field(..., description="当前阶段")
    phase_desc: str = Field(..., description="阶段描述")
    sentiment_index: int = Field(..., description="情绪指数(0-100)")
    limit_up_ratio: float = Field(..., description="涨停率(%)")
    yesterday_premium: float = Field(..., description="昨日溢价(%)")
    next_day_red_rate: float = Field(..., description="次日红盘率(%)")
    history: List[EmotionHistoryItem] = Field(default_factory=list)


class LimitUpLadderResponse(BaseModel):
    """连板梯队与情绪周期响应"""
    trade_date: str = ""
    ladder: List[LadderItem] = Field(default_factory=list)
    emotion: EmotionCycle = Field(default_factory=EmotionCycle)
    total_limit_up: int = Field(0, description="总涨停家数")
    data_available: bool = Field(True, description="是否有有效数据")


# ============================================================================
#  9. 多因子策略回测 (MultiFactorBacktestPage)
# ============================================================================

class FactorItem(BaseModel):
    """因子表现"""
    name: str = Field(..., description="因子名称")
    ic: Optional[float] = Field(None, description="IC值")
    ir: Optional[float] = Field(None, description="IR值")
    rank_ic: Optional[float] = Field(None, description="RankIC")
    win_rate: Optional[float] = Field(None, description="胜率(%)")
    sharpe: Optional[float] = Field(None, description="夏普比率")
    status: str = Field(..., description="状态: 有效/失效")
    source: Optional[str] = Field(None, description="数据来源")


class NavItem(BaseModel):
    """净值曲线点"""
    date: str = Field(..., description="日期")
    nav: float = Field(..., description="净值")


class MultiFactorBacktestResponse(BaseModel):
    """多因子策略回测响应"""
    trade_date: str = ""
    factors: List[FactorItem] = Field(default_factory=list)
    nav_curve: List[NavItem] = Field(default_factory=list)


# ============================================================================
#  10. 持仓建议 (PositionAdvicePage)
# ============================================================================

class PortfolioItem(BaseModel):
    """持仓明细"""
    name: str = Field(..., description="股票名称")
    code: str = Field(..., description="股票代码")
    weight: float = Field(..., description="当前权重(%)")
    current_price: float = Field(..., description="现价")
    cost_price: float = Field(..., description="成本价")
    pnl: float = Field(..., description="盈亏(%)")
    advice: str = Field(..., description="操作建议")
    advice_reason: str = Field("", description="建议理由")
    target_weight: float = Field(..., description="目标权重(%)")
    diff: float = Field(..., description="权重偏差(%)")
    atr_pct: float = Field(0, description="ATR波动率(%)")
    entry_signals: List[str] = Field(default_factory=list, description="入场信号")


class PositionAdviceResponse(BaseModel):
    """持仓建议响应"""
    trade_date: str = ""
    portfolio: List[PortfolioItem] = Field(default_factory=list)
    total_weight: float = Field(0, description="总仓位(%)")
    market_sentiment_phase: str = Field("未知", description="市场情绪阶段")
    suggested_total_position: str = Field("30-50%", description="建议总仓位")
