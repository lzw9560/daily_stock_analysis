# -*- coding: utf-8 -*-
"""回测引擎 v2（交易系统升级 Phase 3）

新能力:
- 分钟级K线回测（1min/5min/15min）——打板的生命线
- 组合回测（多股票同时，含仓位分配）
- 费用建模（佣金万三+印花税千一+滑点0.5%）
- Walk-forward 过拟合检测
- 策略归因（按战法类型分类统计胜率/盈亏比）
- 蒙特卡洛稳健性检验（交易序列随机重排）

兼容 v1 接口，新增 v2 专有方法。
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# 配置与数据模型
# ============================================================

@dataclass
class BacktestConfigV2:
    """回测配置 v2"""
    # 费用
    commission_rate: float = 0.0003      # 佣金万三
    stamp_tax_rate: float = 0.0005       # 印花税千一（卖出）
    min_commission: float = 5.0          # 最低佣金
    slippage_pct: float = 0.001          # 滑点0.1%

    # 回测参数
    initial_cash: float = 100000.0
    max_position_pct: float = 0.3        # 单票最大仓位
    max_total_position_pct: float = 0.8  # 总仓位上限
    min_lot: int = 100                   # 最小交易单位（1手=100股）
    bar_frequency: str = "daily"         # daily/1min/5min/15min

    # 止盈止损
    default_stop_loss_pct: float = 0.07  # 默认止损7%
    default_take_profit_pct: float = 0.10  # 默认止盈10%
    use_trailing_stop: bool = True       # 移动止损

    # 过拟合检测
    walk_forward_windows: int = 3        # WFA窗口数
    walk_forward_train_pct: float = 0.7  # 训练集比例
    monte_carlo_iterations: int = 500    # 蒙特卡洛迭代次数

    engine_version: str = "v2"


@dataclass
class Bar:
    """K线数据"""
    date_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    amount: float = 0.0


@dataclass
class PositionV2:
    """持仓（v2）"""
    code: str
    name: str = ""
    side: str = "long"           # long/short
    quantity: int = 0
    avg_cost: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    entry_date: datetime = field(default_factory=datetime.now)
    entry_price: float = 0.0
    entry_reason: str = ""       # 策略/信号名
    trailing_high: float = 0.0   # 移动止损参考高点


@dataclass
class TradeResultV2:
    """单笔交易结果"""
    code: str
    name: str = ""
    entry_date: datetime = field(default_factory=datetime.now)
    exit_date: datetime = field(default_factory=datetime.now)
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: int = 0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    pnl_after_costs: float = 0.0
    holding_bars: int = 0        # 持仓K线数
    max_drawdown_pct: float = 0.0  # 持仓期间最大回撤
    commission: float = 0.0
    stamp_tax: float = 0.0
    slippage_cost: float = 0.0
    exit_reason: str = ""        # stop_loss/take_profit/manual/eof
    signal_type: str = ""        # 首板/连板/低吸/...
    strategy: str = ""


@dataclass
class StrategyAttribution:
    """策略归因分析"""
    strategy_name: str
    total_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    profit_factor: float = 0.0
    avg_holding_bars: float = 0.0
    sharpe_approx: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0


@dataclass
class PortfolioBacktestResult:
    """组合回测结果"""
    initial_cash: float = 100000.0
    final_equity: float = 0.0
    total_return: float = 0.0
    total_return_pct: float = 0.0
    annualized_return: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_pnl: float = 0.0
    total_commission: float = 0.0
    total_stamp_tax: float = 0.0
    total_slippage: float = 0.0
    trades: list[TradeResultV2] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)
    strategy_attributions: list[StrategyAttribution] = field(default_factory=list)
    wfa_results: list[dict] = field(default_factory=list)


# ============================================================
# 回测引擎 v2
# ============================================================

class BacktestEngineV2:
    """回测引擎 v2

    支持:
    - 日线和分钟级K线回测
    - 单股和组合回测
    - 完整费用建模（佣金+印花税+滑点）
    - 移动止损
    - Walk-forward 过拟合检测
    - 策略归因分析
    - 蒙特卡洛稳健性检验
    """

    def __init__(self, config: Optional[BacktestConfigV2] = None):
        self.config = config or BacktestConfigV2()

    # ========================
    #  单股回测
    # ========================

    def backtest_single(
        self,
        bars: list[Bar],
        signals: list[dict],
        *,
        stock_code: str = "",
        stock_name: str = "",
    ) -> list[TradeResultV2]:
        """单股回测

        Args:
            bars: K线序列（按时间升序）
            signals: 信号列表 [{"datetime": dt, "action": "buy/sell", "price": float,
                                 "strategy": "", "stop_loss_pct": 0.07, "take_profit_pct": 0.10}]
            stock_code: 股票代码
            stock_name: 股票名称

        Returns:
            交易结果列表
        """
        if not bars:
            return []

        # 按时间排序
        bars = sorted(bars, key=lambda b: b.date_time)
        signals = sorted(signals, key=lambda s: s.get("datetime", datetime.min))

        results: list[TradeResultV2] = []
        position: Optional[PositionV2] = None
        signal_idx = 0

        for i, bar in enumerate(bars):
            bar_dt = bar.date_time

            # 检查止损/止盈（持仓时）
            if position:
                # 更新移动止损参考高点
                if bar.high > position.trailing_high:
                    position.trailing_high = bar.high

                exit_price = 0.0
                exit_reason = ""

                # 止损检查
                if self.config.use_trailing_stop and position.trailing_high > 0:
                    trailing_stop = position.trailing_high * (1 - self.config.default_stop_loss_pct)
                    if bar.low <= trailing_stop:
                        exit_price = trailing_stop
                        exit_reason = "trailing_stop"
                elif bar.low <= position.stop_loss:
                    exit_price = position.stop_loss
                    exit_reason = "stop_loss"

                # 止盈检查
                if not exit_reason and bar.high >= position.take_profit:
                    exit_price = position.take_profit
                    exit_reason = "take_profit"

                if exit_reason:
                    trade = self._close_position(
                        position, exit_price, exit_reason, bar_dt, i,
                    )
                    results.append(trade)
                    position = None

            # 处理信号
            while signal_idx < len(signals):
                sig = signals[signal_idx]
                sig_dt = sig.get("datetime", datetime.min)
                if sig_dt > bar_dt:
                    break
                signal_idx += 1

                action = sig.get("action", "")
                sig_price = sig.get("price", bar.close)

                if action == "buy" and position is None:
                    stop_loss_pct = sig.get("stop_loss_pct", self.config.default_stop_loss_pct)
                    take_profit_pct = sig.get("take_profit_pct", self.config.default_take_profit_pct)
                    max_pos = sig.get("max_position_pct", self.config.max_position_pct)

                    # 计算买入数量
                    cost_per_share = sig_price * (1 + self.config.commission_rate + self.config.slippage_pct)
                    max_shares = int((self.config.initial_cash * max_pos) / cost_per_share / self.config.min_lot) * self.config.min_lot
                    if max_shares <= 0:
                        continue

                    entry_slippage = sig_price * self.config.slippage_pct
                    actual_price = sig_price + entry_slippage

                    position = PositionV2(
                        code=stock_code,
                        name=stock_name,
                        quantity=max_shares,
                        avg_cost=actual_price,
                        entry_price=sig_price,
                        stop_loss=sig_price * (1 - stop_loss_pct),
                        take_profit=sig_price * (1 + take_profit_pct),
                        entry_date=bar_dt,
                        entry_reason=sig.get("strategy", ""),
                        trailing_high=bar.high,
                    )

                elif action == "sell" and position:
                    trade = self._close_position(
                        position, sig_price, "manual", bar_dt, i,
                    )
                    results.append(trade)
                    position = None

        # 最后一日强制平仓
        if position and bars:
            last_bar = bars[-1]
            trade = self._close_position(
                position, last_bar.close, "eof", last_bar.date_time, len(bars) - 1,
            )
            results.append(trade)

        return results

    def _close_position(
        self,
        pos: PositionV2,
        exit_price: float,
        reason: str,
        exit_dt: datetime,
        bar_index: int,
    ) -> TradeResultV2:
        """平仓并计算交易结果"""
        exit_slippage = exit_price * self.config.slippage_pct
        actual_exit = exit_price - exit_slippage if reason != "eof" else exit_price

        gross_pnl = (actual_exit - pos.entry_price) * pos.quantity
        commission = max(
            (pos.entry_price + actual_exit) * pos.quantity * self.config.commission_rate,
            self.config.min_commission * 2,
        )
        stamp_tax = actual_exit * pos.quantity * self.config.stamp_tax_rate
        slippage_cost = pos.entry_price * pos.quantity * self.config.slippage_pct + exit_slippage * pos.quantity

        pnl_after = gross_pnl - commission - stamp_tax - slippage_cost
        pnl_pct = pnl_after / (pos.entry_price * pos.quantity) * 100 if pos.entry_price > 0 else 0

        return TradeResultV2(
            code=pos.code,
            name=pos.name,
            entry_date=pos.entry_date,
            exit_date=exit_dt,
            entry_price=pos.entry_price,
            exit_price=actual_exit,
            quantity=pos.quantity,
            pnl=gross_pnl,
            pnl_pct=round(gross_pnl / (pos.entry_price * pos.quantity) * 100, 2),
            pnl_after_costs=round(pnl_after, 2),
            holding_bars=bar_index,
            commission=round(commission, 2),
            stamp_tax=round(stamp_tax, 2),
            slippage_cost=round(slippage_cost, 2),
            exit_reason=reason,
            strategy=pos.entry_reason,
        )

    # ========================
    #  组合回测
    # ========================

    def backtest_portfolio(
        self,
        stock_bars: dict[str, list[Bar]],
        stock_signals: dict[str, list[dict]],
        *,
        stock_names: Optional[dict[str, str]] = None,
    ) -> PortfolioBacktestResult:
        """组合回测

        Args:
            stock_bars: {code: [Bar, ...]}
            stock_signals: {code: [signal_dict, ...]}
            stock_names: {code: name}

        Returns:
            PortfolioBacktestResult
        """
        names = stock_names or {}
        all_bars = self._merge_all_bars(stock_bars)
        if not all_bars:
            return PortfolioBacktestResult()

        all_bars.sort(key=lambda b: b.date_time)
        all_signals: dict[str, list[dict]] = {
            code: sorted(sigs, key=lambda s: s.get("datetime", datetime.min))
            for code, sigs in stock_signals.items()
        }

        positions: dict[str, PositionV2] = {}
        trades: list[TradeResultV2] = []
        cash = self.config.initial_cash
        signal_idxs: dict[str, int] = {code: 0 for code in stock_signals}
        equity_curve: list[dict] = []
        peak_equity = cash

        for bar in all_bars:
            bar_dt = bar.date_time

            # 更新持仓止损止盈
            codes_to_close = []
            for code, pos in positions.items():
                # 移动止损
                if bar.high > pos.trailing_high:
                    pos.trailing_high = bar.high

                if self.config.use_trailing_stop and pos.trailing_high > 0:
                    trailing_sl = pos.trailing_high * (1 - self.config.default_stop_loss_pct)
                    if bar.low <= trailing_sl:
                        codes_to_close.append((code, trailing_sl, "trailing_stop"))
                elif bar.low <= pos.stop_loss:
                    codes_to_close.append((code, pos.stop_loss, "stop_loss"))
                elif bar.high >= pos.take_profit:
                    codes_to_close.append((code, pos.take_profit, "take_profit"))

            for code, exit_price, reason in codes_to_close:
                pos = positions.pop(code)
                trade = self._close_position(pos, exit_price, reason, bar_dt, 0)
                trades.append(trade)
                cash += trade.pnl_after_costs + pos.entry_price * pos.quantity

            # 处理各股信号
            for code in stock_signals:
                sigs = all_signals.get(code, [])
                idx = signal_idxs.get(code, 0)
                while idx < len(sigs):
                    sig = sigs[idx]
                    if sig.get("datetime", datetime.min) > bar_dt:
                        break
                    idx += 1

                    action = sig.get("action", "")
                    if action != "buy" or code in positions:
                        continue

                    sig_price = sig.get("price", bar.close)
                    max_pos_pct = sig.get("max_position_pct", self.config.max_position_pct)
                    current_position_value = sum(
                        p.avg_cost * p.quantity for p in positions.values()
                    )
                    available_cash = self.config.initial_cash * self.config.max_total_position_pct - current_position_value + cash - self.config.initial_cash
                    max_cash = min(cash * 0.8, self.config.initial_cash * max_pos_pct)

                    cost_per_share = sig_price * (1 + self.config.commission_rate + self.config.slippage_pct)
                    max_shares = int(min(cash, max_cash) / cost_per_share / self.config.min_lot) * self.config.min_lot
                    if max_shares <= 0:
                        continue

                    entry_slippage = sig_price * self.config.slippage_pct
                    actual_price = sig_price + entry_slippage
                    total_cost = actual_price * max_shares + max(
                        actual_price * max_shares * self.config.commission_rate,
                        self.config.min_commission,
                    )

                    cash -= total_cost
                    positions[code] = PositionV2(
                        code=code,
                        name=names.get(code, ""),
                        quantity=max_shares,
                        avg_cost=actual_price,
                        entry_price=sig_price,
                        stop_loss=sig_price * (1 - sig.get("stop_loss_pct", self.config.default_stop_loss_pct)),
                        take_profit=sig_price * (1 + sig.get("take_profit_pct", self.config.default_take_profit_pct)),
                        entry_date=bar_dt,
                        entry_reason=sig.get("strategy", ""),
                        trailing_high=bar.high,
                    )
                signal_idxs[code] = idx

            # 计算当前权益
            position_value = sum(
                bar.close * p.quantity for p in positions.values()
            )
            total_equity = cash + position_value
            peak_equity = max(peak_equity, total_equity)

            equity_curve.append({
                "datetime": bar_dt.isoformat() if isinstance(bar_dt, datetime) else str(bar_dt),
                "equity": round(total_equity, 2),
                "cash": round(cash, 2),
                "position_value": round(position_value, 2),
                "positions_count": len(positions),
            })

        # 最终强制平仓
        if positions and all_bars:
            last_bar = all_bars[-1]
            for code, pos in list(positions.items()):
                trade = self._close_position(pos, last_bar.close, "eof", last_bar.date_time, 0)
                trades.append(trade)
                cash += trade.pnl_after_costs + pos.entry_price * pos.quantity
                del positions[code]

        # 计算统计
        return self._calculate_portfolio_stats(
            trades, equity_curve, self.config.initial_cash,
        )

    # ========================
    #  统计计算
    # ========================

    def _calculate_portfolio_stats(
        self,
        trades: list[TradeResultV2],
        equity_curve: list[dict],
        initial_cash: float,
    ) -> PortfolioBacktestResult:
        """计算组合回测统计指标"""
        if not trades:
            return PortfolioBacktestResult(initial_cash=initial_cash)

        final_equity = equity_curve[-1]["equity"] if equity_curve else initial_cash
        total_return = final_equity - initial_cash
        total_return_pct = total_return / initial_cash * 100

        # 按天计算年化
        if len(equity_curve) >= 2:
            first_dt = equity_curve[0].get("datetime", "")
            last_dt = equity_curve[-1].get("datetime", "")
            try:
                days = (datetime.fromisoformat(last_dt) - datetime.fromisoformat(first_dt)).days
                if days > 0:
                    annualized = ((final_equity / initial_cash) ** (365 / days) - 1) * 100
                else:
                    annualized = 0.0
            except Exception as e:
                logger.debug("年化收益率计算失败: %s", e)
                annualized = 0.0

        # 最大回撤
        peak = initial_cash
        max_dd = 0.0
        for eq in equity_curve:
            e = eq.get("equity", initial_cash)
            peak = max(peak, e)
            dd = (peak - e) / peak * 100
            max_dd = max(max_dd, dd)

        # 交易统计
        total_trades = len(trades)
        wins = [t for t in trades if t.pnl_after_costs > 0]
        losses = [t for t in trades if t.pnl_after_costs <= 0]
        win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0

        total_wins_pnl = sum(t.pnl_after_costs for t in wins) if wins else 0
        total_losses_pnl = abs(sum(t.pnl_after_costs for t in losses)) if losses else 1
        profit_factor = total_wins_pnl / total_losses_pnl

        avg_trade_pnl = sum(t.pnl_after_costs for t in trades) / total_trades if total_trades > 0 else 0

        total_commission = sum(t.commission for t in trades)
        total_stamp_tax = sum(t.stamp_tax for t in trades)
        total_slippage = sum(t.slippage_cost for t in trades)

        # 策略归因
        attributions = self._strategy_attribution(trades)

        return PortfolioBacktestResult(
            initial_cash=initial_cash,
            final_equity=round(final_equity, 2),
            total_return=round(total_return, 2),
            total_return_pct=round(total_return_pct, 2),
            annualized_return=round(annualized, 2),
            max_drawdown=round(max_dd, 2),
            max_drawdown_pct=round(max_dd, 2),
            total_trades=total_trades,
            win_rate=round(win_rate, 2),
            profit_factor=round(profit_factor, 2),
            avg_trade_pnl=round(avg_trade_pnl, 2),
            total_commission=round(total_commission, 2),
            total_stamp_tax=round(total_stamp_tax, 2),
            total_slippage=round(total_slippage, 2),
            trades=trades,
            equity_curve=equity_curve,
            strategy_attributions=attributions,
        )

    # ========================
    #  策略归因
    # ========================

    def _strategy_attribution(self, trades: list[TradeResultV2]) -> list[StrategyAttribution]:
        """按策略/战法分类统计"""
        groups: dict[str, list[TradeResultV2]] = {}
        for t in trades:
            key = t.strategy or "未分类"
            groups.setdefault(key, []).append(t)

        results = []
        for strategy, group in groups.items():
            n = len(group)
            wins = [t for t in group if t.pnl_after_costs > 0]
            losses = [t for t in group if t.pnl_after_costs <= 0]
            wr = len(wins) / n * 100 if n > 0 else 0

            total_pnl = sum(t.pnl_after_costs for t in group)
            avg_pnl = total_pnl / n if n > 0 else 0
            max_win = max((t.pnl_after_costs for t in group), default=0)
            max_loss = min((t.pnl_after_costs for t in group), default=0)

            total_w = sum(t.pnl_after_costs for t in wins) if wins else 0
            total_l = abs(sum(t.pnl_after_costs for t in losses)) if losses else 1
            pf = total_w / total_l

            avg_hold = sum(t.holding_bars for t in group) / n if n > 0 else 0

            # 最大连续胜/败
            max_cw = max_cl = cur_cw = cur_cl = 0
            for t in sorted(group, key=lambda x: x.entry_date):
                if t.pnl_after_costs > 0:
                    cur_cw += 1
                    cur_cl = 0
                    max_cw = max(max_cw, cur_cw)
                else:
                    cur_cl += 1
                    cur_cw = 0
                    max_cl = max(max_cl, cur_cl)

            results.append(StrategyAttribution(
                strategy_name=strategy,
                total_trades=n,
                win_count=len(wins),
                loss_count=len(losses),
                win_rate=round(wr, 1),
                total_pnl=round(total_pnl, 2),
                avg_pnl=round(avg_pnl, 2),
                max_win=round(max_win, 2),
                max_loss=round(max_loss, 2),
                profit_factor=round(pf, 2),
                avg_holding_bars=round(avg_hold, 1),
                max_consecutive_wins=max_cw,
                max_consecutive_losses=max_cl,
            ))

        return sorted(results, key=lambda a: a.total_pnl, reverse=True)

    # ========================
    #  过拟合检测
    # ========================

    def walk_forward_analysis(
        self,
        bars: list[Bar],
        signal_generator: Callable[[list[Bar]], list[dict]],
    ) -> list[dict]:
        """Walk-forward 分析检测过拟合

        Args:
            bars: 完整K线序列
            signal_generator: 信号生成函数 (bars) -> signals

        Returns:
            [{window: n, train_metrics: {...}, test_metrics: {...}}, ...]
        """
        n = len(bars)
        if n < 100:
            return []

        window_size = n // self.config.walk_forward_windows
        results = []

        for w in range(self.config.walk_forward_windows):
            split = int(window_size * (w + 1) * self.config.walk_forward_train_pct)
            if w > 0:
                split += window_size * w

            train_bars = bars[:split]
            test_bars = bars[split:split + window_size]

            if len(train_bars) < 20 or len(test_bars) < 20:
                continue

            # 训练集信号
            train_signals = signal_generator(train_bars)
            train_trades = self.backtest_single(train_bars, train_signals)
            train_win_rate = (
                sum(1 for t in train_trades if t.pnl_after_costs > 0) / len(train_trades) * 100
                if train_trades else 0
            )

            # 测试集信号（使用训练集参数生成的信号）
            test_signals = signal_generator(test_bars)
            test_trades = self.backtest_single(test_bars, test_signals)
            test_win_rate = (
                sum(1 for t in test_trades if t.pnl_after_costs > 0) / len(test_trades) * 100
                if test_trades else 0
            )

            # 过拟合信号：训练高胜率但测试低胜率
            overfit_warning = train_win_rate > 60 and test_win_rate < 45

            results.append({
                "window": w + 1,
                "train_size": len(train_bars),
                "test_size": len(test_bars),
                "train_win_rate": round(train_win_rate, 1),
                "test_win_rate": round(test_win_rate, 1),
                "train_trades": len(train_trades),
                "test_trades": len(test_trades),
                "overfit_warning": overfit_warning,
                "performance_decay": round(train_win_rate - test_win_rate, 1),
            })

        return results

    # ========================
    #  蒙特卡洛检验
    # ========================

    def monte_carlo_test(
        self,
        trades: list[TradeResultV2],
        iterations: Optional[int] = None,
    ) -> dict:
        """蒙特卡洛稳健性检验

        随机重排交易序列，评估策略稳健性。
        """
        iterations = iterations or self.config.monte_carlo_iterations
        if not trades or len(trades) < 5:
            return {"message": "交易数量不足"}

        pnls = [t.pnl_after_costs for t in trades]
        original_return = sum(pnls)
        original_max_dd = self._calc_max_drawdown(pnls)

        simulated_returns = []
        simulated_max_dds = []
        profitable_runs = 0

        for _ in range(iterations):
            shuffled = random.sample(pnls, len(pnls))
            sim_ret = sum(shuffled)
            sim_dd = self._calc_max_drawdown(shuffled)
            simulated_returns.append(sim_ret)
            simulated_max_dds.append(sim_dd)
            if sim_ret > 0:
                profitable_runs += 1

        avg_return = sum(simulated_returns) / iterations
        avg_max_dd = sum(simulated_max_dds) / iterations
        profit_probability = profitable_runs / iterations * 100

        # 原始收益率在模拟分布中的分位数
        better_than = sum(1 for r in simulated_returns if r <= original_return) / iterations * 100

        return {
            "iterations": iterations,
            "original_return": round(original_return, 2),
            "original_max_dd": round(original_max_dd, 2),
            "avg_simulated_return": round(avg_return, 2),
            "avg_simulated_max_dd": round(avg_max_dd, 2),
            "profit_probability_pct": round(profit_probability, 1),
            "original_percentile": round(better_than, 1),
            "is_robust": profit_probability > 60 and better_than > 50,
            "warning": (
                "策略可能过拟合" if profit_probability < 50
                else "策略表现稳健" if profit_probability > 70
                else "策略表现一般"
            ),
        }

    @staticmethod
    def _calc_max_drawdown(pnls: list[float]) -> float:
        """从盈亏序列计算最大回撤"""
        cumsum = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in pnls:
            cumsum += p
            peak = max(peak, cumsum)
            dd = peak - cumsum
            max_dd = max(max_dd, dd)
        return max_dd

    # ========================
    #  辅助
    # ========================

    @staticmethod
    def _merge_all_bars(
        stock_bars: dict[str, list[Bar]],
    ) -> list[Bar]:
        """合并所有股票的K线时间点（用于组合回测统一时间轴）"""
        all_times: set[datetime] = set()
        for bars in stock_bars.values():
            for b in bars:
                all_times.add(b.date_time)
        # 返回虚拟Bar（仅含时间）
        return [Bar(date_time=t, open=0, high=0, low=0, close=0) for t in sorted(all_times)]

    def bars_from_dicts(
        self, data: list[dict], frequency: str = "daily"
    ) -> list[Bar]:
        """从字典列表创建Bar列表

        Args:
            data: [{"datetime": str/dt, "open": float, "high": float, ...}]
            frequency: daily/1min/5min
        """
        bars = []
        for d in data:
            dt = d.get("datetime") or d.get("date_time") or d.get("date")
            if isinstance(dt, str):
                try:
                    dt = datetime.fromisoformat(dt)
                except ValueError:
                    try:
                        dt = datetime.strptime(dt, "%Y-%m-%d")
                    except ValueError:
                        try:
                            dt = datetime.strptime(dt, "%Y%m%d")
                        except ValueError:
                            continue
            if isinstance(dt, date) and not isinstance(dt, datetime):
                dt = datetime(dt.year, dt.month, dt.day)

            bars.append(Bar(
                date_time=dt,
                open=float(d.get("open", 0)),
                high=float(d.get("high", 0)),
                low=float(d.get("low", 0)),
                close=float(d.get("close", 0)),
                volume=float(d.get("volume", 0)),
                amount=float(d.get("amount", 0)),
            ))
        return sorted(bars, key=lambda b: b.date_time)
