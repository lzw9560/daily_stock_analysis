# -*- coding: utf-8 -*-
"""交易场景告警类型（交易系统升级 Phase 1）

新增 10 种盘中交易场景告警，覆盖打板/炸板/竞价/资金/板块/情绪等维度。

告警类型:
- bidding_anomaly:     竞价异动（量比>5, 高开>3%）
- limit_up_warning:    涨停预警（涨幅>9.5%且快速拉升）
- seal_break_alert:    炸板预警（封板后打开）
- big_order_inflow:    大单流入（单笔>500万或5分钟>2000万）
- breakout_alert:      突破预警（突破N日高点+放量）
- support_break_alert: 跌破关键支撑
- sector_surge:        板块异动（3只以上涨停）
- sentiment_shift:     情绪转折（封板率大幅变化）
- dragon_tiger_alert:  龙虎榜上榜
- resume_alert:        复牌预警
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ============================================================
# 交易场景告警类型注册
# ============================================================

TRADING_SCENARIO_ALERT_TYPES = frozenset({
    "bidding_anomaly",
    "limit_up_warning",
    "seal_break_alert",
    "big_order_inflow",
    "breakout_alert",
    "support_break_alert",
    "sector_surge",
    "sentiment_shift",
    "dragon_tiger_alert",
    "resume_alert",
})


class TradingAlertSeverity(str, Enum):
    """告警严重级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ============================================================
# 数据模型
# ============================================================

@dataclass
class TradingScenarioAlert:
    """交易场景告警"""

    alert_type: str                      # 告警类型
    stock_code: str                      # 股票代码（可为空表示市场级）
    stock_name: str = ""                 # 股票名称
    severity: TradingAlertSeverity = TradingAlertSeverity.WARNING
    message: str = ""                    # 告警消息
    detail: dict = field(default_factory=dict)  # 详细数据
    triggered_at: datetime = field(default_factory=datetime.now)
    trade_suggestion: str = ""           # 交易建议（如：买入价/止损价）

    def to_dict(self) -> dict:
        return {
            "alert_type": self.alert_type,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "severity": self.severity.value,
            "message": self.message,
            "detail": self.detail,
            "triggered_at": self.triggered_at.isoformat(),
            "trade_suggestion": self.trade_suggestion,
        }


@dataclass
class BiddingAnomalyData:
    """竞价异动数据"""
    stock_code: str
    stock_name: str
    pre_close: float           # 昨收
    bidding_price: float       # 竞价价
    bidding_change_pct: float  # 竞价涨幅
    bidding_volume_ratio: float  # 竞价量比
    bidding_amount: float      # 竞价金额(万)


@dataclass
class LimitUpWarningData:
    """涨停预警数据"""
    stock_code: str
    stock_name: str
    current_price: float
    limit_up_price: float
    change_pct: float          # 当前涨幅
    speed_pct_per_min: float   # 拉升速度(%/分钟)
    volume_ratio: float        # 量比


@dataclass
class SealBreakData:
    """炸板数据"""
    stock_code: str
    stock_name: str
    seal_time: str             # 封板时间
    break_time: str            # 炸板时间
    seal_amount_before: float  # 炸板前封单(万)
    seal_amount_now: float     # 当前封单(万)
    open_count: int            # 累计开板次数


@dataclass
class BigOrderData:
    """大单数据"""
    stock_code: str
    stock_name: str
    order_type: str            # buy/sell
    order_amount: float        # 订单金额(万)
    order_price: float         # 成交价
    order_time: str            # 成交时间
    cumulative_5min: float     # 5分钟累计(万)


@dataclass
class BreakoutData:
    """突破数据"""
    stock_code: str
    stock_name: str
    breakout_price: float      # 突破价格
    n_day_high: float          # N日高点
    n_days: int                # N
    volume_ratio: float        # 突破时量比
    current_volume: float      # 当前成交量


@dataclass
class SectorSurgeData:
    """板块异动数据"""
    sector_name: str
    limit_up_count: int        # 板块内涨停数
    sector_change_pct: float   # 板块涨幅
    net_inflow: float          # 资金净流入(亿)
    leader_stocks: list[str]   # 领涨股


@dataclass
class SentimentShiftData:
    """情绪转折数据"""
    prev_seal_rate: float      # 前封板率
    current_seal_rate: float   # 当前封板率
    prev_limit_up_count: int   # 前涨停数
    current_limit_up_count: int  # 当前涨停数
    shift_direction: str       # up/down
    shift_magnitude: float     # 变化幅度


# ============================================================
# 告警检测器
# ============================================================

class TradingScenarioDetector:
    """交易场景告警检测器

    负责实时扫描市场数据，检测并生成交易场景告警。
    可独立运行，也可集成到 AlertService 中。
    """

    # ---- 竞价异动 ----
    BIDDING_VOLUME_RATIO_THRESHOLD = 5.0     # 量比>5
    BIDDING_CHANGE_PCT_THRESHOLD = 3.0       # 高开>3%

    # ---- 涨停预警 ----
    LIMIT_UP_PRICE_THRESHOLD = 9.5           # 涨幅>9.5%
    LIMIT_UP_SPEED_THRESHOLD = 2.0           # 拉升速度>2%/分钟

    # ---- 大单 ----
    BIG_ORDER_SINGLE_THRESHOLD = 500         # 单笔>500万
    BIG_ORDER_CUMULATIVE_THRESHOLD = 2000    # 5分钟累计>2000万

    # ---- 突破 ----
    BREAKOUT_VOLUME_MULTIPLIER = 1.5         # 放量1.5倍

    # ---- 板块异动 ----
    SECTOR_SURGE_LIMIT_UP_MIN = 3            # 板块内至少3只涨停

    # ---- 情绪转折 ----
    SENTIMENT_SHIFT_SEAL_RATE = 0.2          # 封板率变化>20%
    SENTIMENT_SHIFT_LIMIT_UP_COUNT = 1.5     # 涨停数变化>1.5倍

    def __init__(self):
        self._alerts: list[TradingScenarioAlert] = []

    # ========================
    #  竞价异动检测
    # ========================

    def detect_bidding_anomaly(self, data: BiddingAnomalyData) -> Optional[TradingScenarioAlert]:
        """检测竞价异动"""
        triggered = False
        reasons: list[str] = []

        if data.bidding_volume_ratio >= self.BIDDING_VOLUME_RATIO_THRESHOLD:
            triggered = True
            reasons.append(f"竞价量比{data.bidding_volume_ratio:.1f}倍(>{self.BIDDING_VOLUME_RATIO_THRESHOLD})")

        if data.bidding_change_pct >= self.BIDDING_CHANGE_PCT_THRESHOLD:
            triggered = True
            reasons.append(f"高开{data.bidding_change_pct:.1f}%(>{self.BIDDING_CHANGE_PCT_THRESHOLD}%)")

        if not triggered:
            return None

        severity = (
            TradingAlertSeverity.CRITICAL
            if data.bidding_change_pct >= 7
            else TradingAlertSeverity.WARNING
        )

        return TradingScenarioAlert(
            alert_type="bidding_anomaly",
            stock_code=data.stock_code,
            stock_name=data.stock_name,
            severity=severity,
            message=f"竞价异动: {'; '.join(reasons)}",
            detail={
                "pre_close": data.pre_close,
                "bidding_price": data.bidding_price,
                "bidding_change_pct": data.bidding_change_pct,
                "bidding_volume_ratio": data.bidding_volume_ratio,
                "bidding_amount": data.bidding_amount,
            },
            trade_suggestion="竞价确认后轻仓参与，注意开盘方向",
        )

    # ========================
    #  涨停预警检测
    # ========================

    def detect_limit_up_warning(self, data: LimitUpWarningData) -> Optional[TradingScenarioAlert]:
        """检测涨停预警"""
        if data.change_pct < self.LIMIT_UP_PRICE_THRESHOLD:
            return None

        severity = TradingAlertSeverity.WARNING
        extra = ""

        if data.speed_pct_per_min >= self.LIMIT_UP_SPEED_THRESHOLD:
            severity = TradingAlertSeverity.CRITICAL
            extra = f" 拉升速度{data.speed_pct_per_min:.1f}%/分钟"

        remaining_pct = max(0, data.limit_up_price - data.current_price)
        remaining_pct = (remaining_pct / data.limit_up_price) * 100 if data.limit_up_price > 0 else 0

        return TradingScenarioAlert(
            alert_type="limit_up_warning",
            stock_code=data.stock_code,
            stock_name=data.stock_name,
            severity=severity,
            message=f"涨停预警: {data.stock_name}涨幅{data.change_pct:.1f}%, "
                    f"距涨停{remaining_pct:.2f}%{extra}",
            detail={
                "current_price": data.current_price,
                "limit_up_price": data.limit_up_price,
                "change_pct": data.change_pct,
                "speed_pct_per_min": data.speed_pct_per_min,
                "volume_ratio": data.volume_ratio,
            },
            trade_suggestion="关注封板力度和板块共振，封板快+板块强可排板",
        )

    # ========================
    #  炸板预警
    # ========================

    def detect_seal_break(self, data: SealBreakData) -> Optional[TradingScenarioAlert]:
        """检测炸板"""
        seal_loss_pct = 0.0
        if data.seal_amount_before > 0:
            seal_loss_pct = (data.seal_amount_before - data.seal_amount_now) / data.seal_amount_before * 100

        severity = (
            TradingAlertSeverity.CRITICAL
            if data.open_count >= 2 or seal_loss_pct >= 50
            else TradingAlertSeverity.WARNING
        )

        suggestion = "观察回封力度和封单恢复情况"
        if data.open_count >= 2:
            suggestion = "多次炸板，建议观望不参与回封"
        elif seal_loss_pct >= 70:
            suggestion = "封单大量撤单，不宜参与"

        return TradingScenarioAlert(
            alert_type="seal_break_alert",
            stock_code=data.stock_code,
            stock_name=data.stock_name,
            severity=severity,
            message=f"炸板预警: {data.stock_name} {data.seal_time}封板, "
                    f"{data.break_time}炸板(第{data.open_count}次), 封单损失{seal_loss_pct:.0f}%",
            detail={
                "seal_time": data.seal_time,
                "break_time": data.break_time,
                "seal_amount_before": data.seal_amount_before,
                "seal_amount_now": data.seal_amount_now,
                "seal_loss_pct": seal_loss_pct,
                "open_count": data.open_count,
            },
            trade_suggestion=suggestion,
        )

    # ========================
    #  大单流入
    # ========================

    def detect_big_order(self, data: BigOrderData) -> Optional[TradingScenarioAlert]:
        """检测大单"""
        triggered = False
        reasons: list[str] = []

        if data.order_amount >= self.BIG_ORDER_SINGLE_THRESHOLD:
            triggered = True
            reasons.append(f"单笔{data.order_amount:.0f}万(>{self.BIG_ORDER_SINGLE_THRESHOLD}万)")

        if data.cumulative_5min >= self.BIG_ORDER_CUMULATIVE_THRESHOLD:
            triggered = True
            reasons.append(f"5分钟累计{data.cumulative_5min:.0f}万(>{self.BIG_ORDER_CUMULATIVE_THRESHOLD}万)")

        if not triggered:
            return None

        direction = "买入" if data.order_type == "buy" else "卖出"
        severity = (
            TradingAlertSeverity.WARNING
            if data.order_type == "buy"
            else TradingAlertSeverity.CRITICAL
        )

        return TradingScenarioAlert(
            alert_type="big_order_inflow",
            stock_code=data.stock_code,
            stock_name=data.stock_name,
            severity=severity,
            message=f"大单{direction}: {'; '.join(reasons)} @ {data.order_price:.2f}",
            detail={
                "order_type": data.order_type,
                "order_amount": data.order_amount,
                "order_price": data.order_price,
                "order_time": data.order_time,
                "cumulative_5min": data.cumulative_5min,
            },
            trade_suggestion=(
                "大单买入可跟随，注意区分对倒和真实买入"
                if data.order_type == "buy"
                else "大单卖出需警惕，检查是否主力出货"
            ),
        )

    # ========================
    #  突破预警
    # ========================

    def detect_breakout(self, data: BreakoutData) -> Optional[TradingScenarioAlert]:
        """检测价格突破"""
        if data.breakout_price < data.n_day_high:
            return None

        severity = TradingAlertSeverity.WARNING
        if data.volume_ratio >= self.BREAKOUT_VOLUME_MULTIPLIER:
            severity = TradingAlertSeverity.CRITICAL
            vol_note = f" 放量{data.volume_ratio:.1f}倍突破"
        else:
            vol_note = " 量能配合一般"

        return TradingScenarioAlert(
            alert_type="breakout_alert",
            stock_code=data.stock_code,
            stock_name=data.stock_name,
            severity=severity,
            message=f"突破预警: {data.stock_name}突破{data.n_days}日高点{data.n_day_high:.2f}, "
                    f"当前{data.breakout_price:.2f}{vol_note}",
            detail={
                "breakout_price": data.breakout_price,
                "n_day_high": data.n_day_high,
                "n_days": data.n_days,
                "volume_ratio": data.volume_ratio,
            },
            trade_suggestion=(
                "放量突破可追入，缩量突破需等回踩确认"
                if data.volume_ratio >= self.BREAKOUT_VOLUME_MULTIPLIER
                else "缩量突破，等回踩确认后再参与"
            ),
        )

    # ========================
    #  跌破支撑
    # ========================

    def detect_support_break(
        self, stock_code: str, stock_name: str,
        current_price: float, support_level: float, support_name: str = ""
    ) -> Optional[TradingScenarioAlert]:
        """检测跌破关键支撑"""
        if current_price >= support_level:
            return None

        break_pct = (support_level - current_price) / support_level * 100

        return TradingScenarioAlert(
            alert_type="support_break_alert",
            stock_code=stock_code,
            stock_name=stock_name,
            severity=TradingAlertSeverity.CRITICAL,
            message=f"跌破支撑: {stock_name}跌破{support_name or '关键支撑'}{support_level:.2f}, "
                    f"当前{current_price:.2f}(跌破{break_pct:.2f}%)",
            detail={
                "current_price": current_price,
                "support_level": support_level,
                "break_pct": break_pct,
                "support_name": support_name,
            },
            trade_suggestion="关键支撑破位，严格执行止损纪律，不建议补仓",
        )

    # ========================
    #  板块异动
    # ========================

    def detect_sector_surge(self, data: SectorSurgeData) -> Optional[TradingScenarioAlert]:
        """检测板块异动"""
        if data.limit_up_count < self.SECTOR_SURGE_LIMIT_UP_MIN:
            return None

        severity = (
            TradingAlertSeverity.CRITICAL
            if data.limit_up_count >= 5
            else TradingAlertSeverity.WARNING
        )

        return TradingScenarioAlert(
            alert_type="sector_surge",
            stock_code="",  # 板块级告警
            stock_name=data.sector_name,
            severity=severity,
            message=f"板块异动: {data.sector_name} {data.limit_up_count}只涨停, "
                    f"涨幅{data.sector_change_pct:.2f}%, 资金净流入{data.net_inflow:.1f}亿",
            detail={
                "sector_name": data.sector_name,
                "limit_up_count": data.limit_up_count,
                "sector_change_pct": data.sector_change_pct,
                "net_inflow": data.net_inflow,
                "leader_stocks": data.leader_stocks,
            },
            trade_suggestion=(
                f"板块共振确认，关注领涨股: {', '.join(data.leader_stocks[:3])}"
                if data.leader_stocks
                else "板块异动确认，关注板块内首板和龙头"
            ),
        )

    # ========================
    #  情绪转折
    # ========================

    def detect_sentiment_shift(self, data: SentimentShiftData) -> Optional[TradingScenarioAlert]:
        """检测情绪转折"""
        seal_rate_change = abs(data.current_seal_rate - data.prev_seal_rate)
        limit_up_ratio = (
            data.current_limit_up_count / max(data.prev_limit_up_count, 1)
            if data.prev_limit_up_count > 0
            else 1.0
        )

        if seal_rate_change < self.SENTIMENT_SHIFT_SEAL_RATE and limit_up_ratio < self.SENTIMENT_SHIFT_LIMIT_UP_COUNT:
            return None

        severity = TradingAlertSeverity.WARNING
        direction = "up" if data.current_seal_rate > data.prev_seal_rate else "down"

        if direction == "up" and seal_rate_change >= 0.3:
            severity = TradingAlertSeverity.CRITICAL
            msg = "情绪快速修复，可积极参与"
        elif direction == "up":
            msg = "情绪回暖，可适度参与"
        elif seal_rate_change >= 0.3:
            severity = TradingAlertSeverity.CRITICAL
            msg = "情绪急速恶化，建议减仓/空仓"
        else:
            msg = "情绪转弱，控制仓位"

        return TradingScenarioAlert(
            alert_type="sentiment_shift",
            stock_code="",
            stock_name="全市场",
            severity=severity,
            message=f"情绪转折: 封板率{data.prev_seal_rate:.1%}→{data.current_seal_rate:.1%} "
                    f"({direction}), 涨停数{data.prev_limit_up_count}→{data.current_limit_up_count}",
            detail={
                "prev_seal_rate": data.prev_seal_rate,
                "current_seal_rate": data.current_seal_rate,
                "prev_limit_up_count": data.prev_limit_up_count,
                "current_limit_up_count": data.current_limit_up_count,
                "shift_direction": direction,
                "shift_magnitude": seal_rate_change,
            },
            trade_suggestion=msg,
        )

    # ========================
    #  龙虎榜上榜
    # ========================

    def detect_dragon_tiger(
        self, stock_code: str, stock_name: str,
        buy_amount: float, sell_amount: float,
        institution_buy: float, institution_sell: float,
        top_buyer: str = "", reason: str = ""
    ) -> Optional[TradingScenarioAlert]:
        """检测龙虎榜上榜"""
        net_buy = buy_amount - sell_amount
        inst_net = institution_buy - institution_sell

        reasons: list[str] = []
        if inst_net > 1000:
            reasons.append(f"机构净买入{inst_net:.0f}万")
        if net_buy > 3000:
            reasons.append(f"整体净买入{net_buy:.0f}万")
        if institution_sell > institution_buy * 2:
            reasons.append(f"机构大幅卖出{institution_sell:.0f}万(警惕)")

        if not reasons:
            return None

        severity = TradingAlertSeverity.WARNING
        if institution_sell > institution_buy * 3:
            severity = TradingAlertSeverity.CRITICAL

        return TradingScenarioAlert(
            alert_type="dragon_tiger_alert",
            stock_code=stock_code,
            stock_name=stock_name,
            severity=severity,
            message=f"龙虎榜: {stock_name} {'; '.join(reasons)}" + (f" ({reason})" if reason else ""),
            detail={
                "buy_amount": buy_amount,
                "sell_amount": sell_amount,
                "institution_buy": institution_buy,
                "institution_sell": institution_sell,
                "net_buy": net_buy,
                "top_buyer": top_buyer,
                "reason": reason,
            },
            trade_suggestion=(
                "机构净买入+游资参与→次日溢价概率高，可关注竞价情况"
                if inst_net > 0
                else "机构净卖出→次日承压概率大，不宜追高"
            ),
        )

    # ========================
    #  复牌预警
    # ========================

    def detect_resume(
        self, stock_code: str, stock_name: str,
        resume_date: str, suspension_reason: str,
        estimated_direction: str  # "up" / "down" / "unknown"
    ) -> Optional[TradingScenarioAlert]:
        """检测复牌"""
        severity = TradingAlertSeverity.WARNING
        if estimated_direction == "up":
            msg = f"复牌: {stock_name} {resume_date}复牌, 停牌原因: {suspension_reason}, 预计补涨"
            suggestion = "关注复牌竞价和开盘方向，补涨可轻仓博弈"
        elif estimated_direction == "down":
            severity = TradingAlertSeverity.CRITICAL
            msg = f"复牌预警: {stock_name} {resume_date}复牌, 停牌原因: {suspension_reason}, 预计补跌"
            suggestion = "预计补跌，不建议参与，持仓者竞价即挂跌停"
        else:
            msg = f"复牌: {stock_name} {resume_date}复牌, 停牌原因: {suspension_reason}"
            suggestion = "方向不明，观察开盘再决定"

        return TradingScenarioAlert(
            alert_type="resume_alert",
            stock_code=stock_code,
            stock_name=stock_name,
            severity=severity,
            message=msg,
            detail={
                "resume_date": resume_date,
                "suspension_reason": suspension_reason,
                "estimated_direction": estimated_direction,
            },
            trade_suggestion=suggestion,
        )

    # ========================
    #  批量检测
    # ========================

    def clear_alerts(self):
        self._alerts.clear()

    def get_alerts(
        self, *, severity_filter: Optional[TradingAlertSeverity] = None
    ) -> list[TradingScenarioAlert]:
        if severity_filter:
            return [a for a in self._alerts if a.severity == severity_filter]
        return list(self._alerts)

    def get_alerts_by_type(self, alert_type: str) -> list[TradingScenarioAlert]:
        return [a for a in self._alerts if a.alert_type == alert_type]

    def get_alerts_by_stock(self, stock_code: str) -> list[TradingScenarioAlert]:
        return [a for a in self._alerts if a.stock_code == stock_code]
