# -*- coding: utf-8 -*-
"""模拟交易/实盘对接层（交易系统升级 Phase 4）

提供统一的交易执行桥接层:
- Phase 1: 模拟盘（dry_run），完全在系统内模拟
- Phase 2: API对接（ptrade/vnpy/同花顺）
- Phase 3: 实盘（人工确认后执行）

设计目标:
- 模拟盘与实盘共用相同接口
- 记录完整交易流水
- 支持盈亏曲线追踪
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 数据类型
# ============================================================

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"          # 市价
    LIMIT = "limit"            # 限价
    SEAL_PLATE = "seal_plate"  # 排板


class OrderStatus(str, Enum):
    PENDING = "pending"        # 待提交
    SUBMITTED = "submitted"    # 已提交
    PARTIAL = "partial"        # 部分成交
    FILLED = "filled"          # 全部成交
    CANCELLED = "cancelled"    # 已撤单
    REJECTED = "rejected"      # 被拒
    EXPIRED = "expired"        # 过期


class BrokerType(str, Enum):
    DRY_RUN = "dry_run"        # 模拟盘
    PTRADE = "ptrade"          # 同花顺Ptrade
    VNPY = "vnpy"              # VNPY
    EASTMONEY = "eastmoney"    # 东方财富


@dataclass
class Order:
    """委托单"""
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    stock_code: str = ""
    stock_name: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: int = 0           # 数量（股）
    price: float = 0.0          # 委托价
    filled_quantity: int = 0    # 已成交数量
    filled_price: float = 0.0   # 成交均价
    status: OrderStatus = OrderStatus.PENDING
    strategy: str = ""          # 策略来源
    signal_id: str = ""         # 信号ID
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    commission: float = 0.0     # 手续费
    stamp_tax: float = 0.0      # 印花税
    error_message: str = ""

    @property
    def is_buy(self) -> bool:
        return self.side == OrderSide.BUY

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def total_cost(self) -> float:
        """总成本（含费用）"""
        if self.side == OrderSide.BUY:
            return self.filled_price * self.filled_quantity + self.commission
        return self.filled_price * self.filled_quantity - self.commission - self.stamp_tax


@dataclass
class Position:
    """持仓"""
    stock_code: str
    stock_name: str = ""
    quantity: int = 0           # 持仓数量
    avg_cost: float = 0.0       # 持仓均价
    current_price: float = 0.0  # 当前价
    market_value: float = 0.0   # 市值
    unrealized_pnl: float = 0.0 # 浮动盈亏
    unrealized_pnl_pct: float = 0.0  # 浮动盈亏%
    strategy: str = ""          # 策略来源
    entry_date: str = ""        # 入场日期
    stop_loss: float = 0.0      # 止损价
    take_profit: float = 0.0    # 止盈价
    holding_days: int = 0       # 持仓天数

    @property
    def is_profitable(self) -> bool:
        return self.unrealized_pnl > 0


@dataclass
class AccountInfo:
    """账户信息"""
    total_assets: float = 0.0        # 总资产
    available_cash: float = 0.0      # 可用资金
    frozen_cash: float = 0.0         # 冻结资金
    market_value: float = 0.0        # 持仓市值
    total_pnl: float = 0.0           # 累计盈亏
    total_pnl_pct: float = 0.0       # 累计盈亏%
    daily_pnl: float = 0.0           # 当日盈亏
    daily_pnl_pct: float = 0.0       # 当日盈亏%
    position_count: int = 0          # 持仓数量
    max_drawdown: float = 0.0        # 最大回撤
    win_rate: float = 0.0            # 历史胜率


@dataclass
class TradeRecord:
    """交易记录"""
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    stock_code: str = ""
    stock_name: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: int = 0
    price: float = 0.0
    pnl: float = 0.0              # 盈亏
    pnl_pct: float = 0.0          # 盈亏%
    commission: float = 0.0
    stamp_tax: float = 0.0
    strategy: str = ""
    entry_date: str = ""
    exit_date: str = ""
    holding_days: int = 0
    exit_reason: str = ""         # 止损/止盈/主动平仓
    traded_at: datetime = field(default_factory=datetime.now)


# ============================================================
# 交易桥接层
# ============================================================

class TradingBroker:
    """交易执行桥接层

    Usage:
        broker = TradingBroker(broker_type=BrokerType.DRY_RUN, initial_cash=100000)
        broker.submit_order("600519", OrderSide.BUY, 100, 1800, OrderType.MARKET)
        broker.get_positions()
        broker.get_account()
    """

    # 费用参数
    COMMISSION_RATE = 0.0003      # 佣金万三
    STAMP_TAX_RATE = 0.0005       # 印花税千一（卖出）
    MIN_COMMISSION = 5.0          # 最低佣金
    SLIPPAGE_PCT = 0.001          # 模拟滑点0.1%

    def __init__(
        self,
        broker_type: BrokerType = BrokerType.DRY_RUN,
        initial_cash: float = 100000.0,
        **kwargs,
    ):
        self.broker_type = broker_type
        self._initial_cash = initial_cash
        self._available_cash = initial_cash
        self._frozen_cash = 0.0
        self._positions: dict[str, Position] = {}
        self._orders: list[Order] = []
        self._trade_history: list[TradeRecord] = []
        self._daily_pnl_history: list[float] = []
        self._max_assets = initial_cash

    # ========================
    #  下单
    # ========================

    def submit_order(
        self,
        stock_code: str,
        side: OrderSide,
        quantity: int,
        price: float,
        order_type: OrderType = OrderType.MARKET,
        *,
        stock_name: str = "",
        strategy: str = "",
        signal_id: str = "",
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
    ) -> Order:
        """提交委托单

        Args:
            stock_code: 股票代码
            side: 买卖方向
            quantity: 数量（股）
            price: 委托价
            order_type: 委托类型
            stock_name: 股票名
            strategy: 策略名
            signal_id: 信号ID
            stop_loss: 止损价（买入时设置）
            take_profit: 止盈价（买入时设置）

        Returns:
            Order
        """
        order = Order(
            stock_code=stock_code,
            stock_name=stock_name,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            strategy=strategy,
            signal_id=signal_id,
        )

        # 资金检查（买入）
        if side == OrderSide.BUY:
            estimated_cost = price * quantity * (1 + self.COMMISSION_RATE + self.SLIPPAGE_PCT)
            estimated_cost = max(estimated_cost, price * quantity + self.MIN_COMMISSION)
            if estimated_cost > self._available_cash:
                order.status = OrderStatus.REJECTED
                order.error_message = f"资金不足: 需要{estimated_cost:.2f}, 可用{self._available_cash:.2f}"
                self._orders.append(order)
                return order

        # 持仓检查（卖出）
        if side == OrderSide.SELL:
            pos = self._positions.get(stock_code)
            if not pos or pos.quantity < quantity:
                order.status = OrderStatus.REJECTED
                order.error_message = f"持仓不足: 需要{quantity}股, 持有{pos.quantity if pos else 0}股"
                self._orders.append(order)
                return order

        # 模拟成交（dry_run 模式直接成交）
        if self.broker_type == BrokerType.DRY_RUN:
            self._execute_dry_run(order, stop_loss, take_profit)
        else:
            order.status = OrderStatus.SUBMITTED

        self._orders.append(order)
        return order

    def _execute_dry_run(
        self, order: Order, stop_loss: float = 0.0, take_profit: float = 0.0
    ):
        """模拟盘执行"""
        # 滑点模拟
        if order.side == OrderSide.BUY:
            fill_price = order.price * (1 + self.SLIPPAGE_PCT)
        else:
            fill_price = order.price * (1 - self.SLIPPAGE_PCT)

        # 手续费
        commission = max(fill_price * order.quantity * self.COMMISSION_RATE, self.MIN_COMMISSION)
        # 印花税（仅卖出）
        stamp_tax = fill_price * order.quantity * self.STAMP_TAX_RATE if order.side == OrderSide.SELL else 0

        order.filled_quantity = order.quantity
        order.filled_price = fill_price
        order.commission = commission
        order.stamp_tax = stamp_tax
        order.status = OrderStatus.FILLED
        order.updated_at = datetime.now()

        if order.side == OrderSide.BUY:
            total_cost = fill_price * order.quantity + commission
            self._available_cash -= total_cost
            self._frozen_cash += total_cost  # 模拟冻结

            # 更新持仓
            if order.stock_code in self._positions:
                pos = self._positions[order.stock_code]
                total_cost_existing = pos.avg_cost * pos.quantity
                new_total = total_cost_existing + total_cost
                pos.quantity += order.quantity
                pos.avg_cost = new_total / pos.quantity if pos.quantity > 0 else 0
            else:
                self._positions[order.stock_code] = Position(
                    stock_code=order.stock_code,
                    stock_name=order.stock_name,
                    quantity=order.quantity,
                    avg_cost=fill_price,
                    current_price=fill_price,
                    market_value=fill_price * order.quantity,
                    strategy=order.strategy,
                    entry_date=datetime.now().strftime("%Y%m%d"),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )

            self._frozen_cash -= total_cost  # 解冻

        else:  # SELL
            total_received = fill_price * order.quantity - commission - stamp_tax
            self._available_cash += total_received

            # 更新持仓
            pos = self._positions.get(order.stock_code)
            if pos:
                pnl = (fill_price - pos.avg_cost) * order.quantity - commission - stamp_tax
                pnl_pct = (fill_price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost > 0 else 0

                pos.quantity -= order.quantity
                if pos.quantity <= 0:
                    del self._positions[order.stock_code]
                else:
                    pos.market_value = pos.current_price * pos.quantity

                # 记录交易
                self._trade_history.append(TradeRecord(
                    stock_code=order.stock_code,
                    stock_name=order.stock_name,
                    side=order.side,
                    quantity=order.quantity,
                    price=fill_price,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    commission=commission,
                    stamp_tax=stamp_tax,
                    strategy=order.strategy,
                    entry_date=pos.entry_date,
                    exit_date=datetime.now().strftime("%Y%m%d"),
                    holding_days=self._calc_holding_days(pos.entry_date),
                ))

    # ========================
    #  撤单
    # ========================

    def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        for order in self._orders:
            if order.order_id == order_id and order.status in (
                OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL
            ):
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.now()
                return True
        return False

    # ========================
    #  查询
    # ========================

    def get_positions(self) -> list[Position]:
        """获取持仓列表"""
        return list(self._positions.values())

    def get_position(self, stock_code: str) -> Optional[Position]:
        return self._positions.get(stock_code)

    def get_orders(
        self, *, status: Optional[OrderStatus] = None
    ) -> list[Order]:
        """获取委托列表"""
        if status:
            return [o for o in self._orders if o.status == status]
        return list(self._orders)

    def get_trade_history(self) -> list[TradeRecord]:
        return list(self._trade_history)

    def get_account(self) -> AccountInfo:
        """获取账户信息"""
        total_market_value = sum(p.market_value for p in self._positions.values())
        total_assets = self._available_cash + total_market_value

        # 累计盈亏
        total_pnl = total_assets - self._initial_cash
        total_pnl_pct = total_pnl / self._initial_cash * 100 if self._initial_cash > 0 else 0

        # 当日盈亏
        daily_pnl = self._daily_pnl_history[-1] if self._daily_pnl_history else 0.0

        # 最大回撤
        self._max_assets = max(self._max_assets, total_assets)
        max_drawdown = (self._max_assets - total_assets) / self._max_assets * 100 if self._max_assets > 0 else 0

        # 胜率
        trades = self._trade_history
        wins = sum(1 for t in trades if t.pnl > 0)
        win_rate = wins / len(trades) * 100 if trades else 0

        return AccountInfo(
            total_assets=total_assets,
            available_cash=self._available_cash,
            frozen_cash=self._frozen_cash,
            market_value=total_market_value,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            daily_pnl=daily_pnl,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            position_count=len(self._positions),
        )

    def get_pnl_curve(self) -> list[dict]:
        """获取盈亏曲线（模拟每日快照）"""
        curve: list[dict] = []
        running_pnl = 0.0
        for i, (trade_date, records) in enumerate(self._get_daily_trades().items()):
            day_pnl = sum(r.pnl for r in records)
            running_pnl += day_pnl
            total = self._initial_cash + running_pnl
            curve.append({
                "date": trade_date,
                "daily_pnl": day_pnl,
                "cumulative_pnl": running_pnl,
                "total_assets": total,
                "return_pct": running_pnl / self._initial_cash * 100,
            })
        return curve

    # ========================
    #  持仓更新（供定时任务调用）
    # ========================

    def update_position_prices(self, prices: dict[str, float]):
        """更新持仓现价

        Args:
            prices: {stock_code: current_price}
        """
        for code, price in prices.items():
            pos = self._positions.get(code)
            if pos:
                pos.current_price = price
                pos.market_value = price * pos.quantity
                pos.unrealized_pnl = (price - pos.avg_cost) * pos.quantity
                pos.unrealized_pnl_pct = (
                    (price - pos.avg_cost) / pos.avg_cost * 100
                    if pos.avg_cost > 0 else 0
                )
                # 更新持仓天数
                if pos.entry_date:
                    try:
                        entry = datetime.strptime(pos.entry_date, "%Y%m%d").date()
                        pos.holding_days = (date.today() - entry).days
                    except ValueError:
                        pass

    def check_stop_conditions(self) -> list[Order]:
        """检查止盈止损条件，返回触发的订单"""
        triggered: list[Order] = []
        for code, pos in list(self._positions.items()):
            if pos.stop_loss > 0 and pos.current_price <= pos.stop_loss:
                logger.warning(f"止损触发: {code} 现价{pos.current_price} <= 止损{pos.stop_loss}")
                order = self.submit_order(
                    code, OrderSide.SELL, pos.quantity, pos.current_price,
                    OrderType.MARKET, stock_name=pos.stock_name,
                    strategy="stop_loss",
                )
                triggered.append(order)
            elif pos.take_profit > 0 and pos.current_price >= pos.take_profit:
                logger.info(f"止盈触发: {code} 现价{pos.current_price} >= 止盈{pos.take_profit}")
                order = self.submit_order(
                    code, OrderSide.SELL, pos.quantity, pos.current_price,
                    OrderType.MARKET, stock_name=pos.stock_name,
                    strategy="take_profit",
                )
                triggered.append(order)
        return triggered

    # ========================
    #  辅助
    # ========================

    @staticmethod
    def _calc_holding_days(entry_date_str: str) -> int:
        try:
            entry = datetime.strptime(entry_date_str, "%Y%m%d").date()
            return (date.today() - entry).days
        except (ValueError, TypeError):
            return 0

    def _get_daily_trades(self) -> dict[str, list[TradeRecord]]:
        """按日分组交易记录"""
        from collections import defaultdict
        daily: dict[str, list[TradeRecord]] = defaultdict(list)
        for t in self._trade_history:
            day_key = t.traded_at.strftime("%Y%m%d")
            daily[day_key].append(t)
        return dict(daily)

    def reset(self):
        """重置账户"""
        self._available_cash = self._initial_cash
        self._frozen_cash = 0.0
        self._positions.clear()
        self._orders.clear()
        self._trade_history.clear()
        self._daily_pnl_history.clear()
        self._max_assets = self._initial_cash
