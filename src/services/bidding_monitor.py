# -*- coding: utf-8 -*-
"""
早盘集合竞价监控模块 (Pre-market Bidding Monitor)
================================================

功能:
1. 9:15-9:25 监控集合竞价数据（虚拟成交价、匹配量、未匹配量）
2. 9:25 确认开盘价后判断进场信号
3. 通过飞书机器人推送建仓建议 + 止损/止盈点位
4. 支持竞价强度分析（竞价量比、价格趋势、封单力度）

竞价信号判断逻辑:
- 强势信号: 竞价价格持续走高 + 竞价量比 > 3 + 最后3分钟封涨停
- 普通信号: 竞价价格温和上涨 + 竞价量比 1.5-3
- 弱势信号: 竞价价格下跌或量比 < 1
- 风险信号: 竞价最后时刻突然跳水或巨量撤单

使用方式:
    monitor = PreMarketBiddingMonitor()
    monitor.start_monitoring()  # 9:15自动启动
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import requests

from .cache_manager import get_cache

logger = logging.getLogger(__name__)

# 集合竞价时间段
BIDDING_START = dt_time(9, 15)
BIDDING_CONFIRM = dt_time(9, 25)
BIDDING_END = dt_time(9, 30)
PRE_MARKET_ANALYSIS_TIME = dt_time(8, 50)


class BiddingSignalLevel(str, Enum):
    """竞价信号等级"""
    STRONG_BUY = "strong_buy"       # 强势买入
    BUY = "buy"                     # 普通买入
    WATCH = "watch"                 # 关注
    WEAK = "weak"                   # 弱势
    RISK = "risk"                   # 风险回避


@dataclass
class BiddingSnapshot:
    """竞价快照"""
    code: str
    name: str
    timestamp: datetime
    # 竞价数据
    current_price: float = 0.0      # 当前虚拟成交价
    match_volume: float = 0.0       # 匹配量（手）
    unmatch_volume: float = 0.0     # 未匹配量
    pre_close: float = 0.0          # 昨收
    high_price: float = 0.0         # 竞价最高价
    low_price: float = 0.0          # 竞价最低价
    # 计算指标
    price_change_pct: float = 0.0   # 较昨收涨跌幅
    volume_ratio: float = 0.0       # 竞价量比
    bid_strength: float = 0.0       # 竞价强度 0-100


@dataclass
class BiddingSignal:
    """竞价信号"""
    code: str
    name: str
    level: BiddingSignalLevel
    open_price: float               # 9:25 确认开盘价
    pre_close: float
    change_pct: float
    bid_strength: float             # 竞价强度
    # 建仓建议
    entry_price_range: str          # 买入区间
    stop_loss_price: float          # 止损价
    target_price_1: float           # 第一目标价
    target_price_2: float           # 第二目标价
    position_pct: float             # 建议仓位%
    # 描述
    reason: str
    risk_note: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class PreMarketBiddingMonitor:
    """
    早盘集合竞价监控器

    工作流程:
    1. 8:50 - 盘前准备：加载自选股、检查数据源
    2. 9:15 - 开始监控：每10秒拉取竞价数据
    3. 9:25 - 确认信号：分析竞价结果，生成建仓建议
    4. 9:25 - 飞书推送：发送建仓信号到飞书
    """

    # 竞价强度阈值
    STRONG_BID_THRESHOLD = 70       # 强势竞价
    BUY_BID_THRESHOLD = 50          # 买入竞价
    WATCH_BID_THRESHOLD = 30        # 关注竞价

    # 竞价量比阈值
    STRONG_VOL_RATIO = 3.0
    NORMAL_VOL_RATIO = 1.5

    # 止损比例
    STOP_LOSS_PCT = -0.05           # -5%
    TIGHT_STOP_LOSS_PCT = -0.03     # -3%（强势股）

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        watchlist_codes: Optional[List[str]] = None,
    ):
        self._webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK_URL", "")
        self._webhook_secret = webhook_secret or os.getenv("FEISHU_WEBHOOK_SECRET", "")
        self._watchlist: Dict[str, str] = {}
        if watchlist_codes:
            for c in watchlist_codes:
                self._watchlist[c] = ""

        # 竞价历史快照 {code: [BiddingSnapshot, ...]}
        self._bid_history: Dict[str, List[BiddingSnapshot]] = {}
        self._history_lock = threading.Lock()

        # 信号收集
        self._signals: List[BiddingSignal] = []
        self._signals_lock = threading.Lock()

        # 线程控制
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 腾讯行情拉取器
        self._fetcher = None

        # 缓存
        self._cache = get_cache()

        logger.info("竞价监控器初始化: %d 只标的", len(self._watchlist))

    @property
    def fetcher(self):
        if self._fetcher is None:
            from data_provider.tencent_fetcher import TencentFetcher
            self._fetcher = TencentFetcher()
        return self._fetcher

    def set_watchlist(self, codes: Dict[str, str]):
        """设置监控标的"""
        self._watchlist = dict(codes)

    def add_stock(self, code: str, name: str = ""):
        self._watchlist[code] = name

    # ============================================================
    #  时间检查
    # ============================================================

    @staticmethod
    def is_bidding_time() -> bool:
        """是否在集合竞价时段 (9:15-9:30)"""
        now = datetime.now().time()
        return BIDDING_START <= now < BIDDING_END

    @staticmethod
    def is_confirmed_time() -> bool:
        """是否已到竞价确认时间 (>=9:25)"""
        now = datetime.now().time()
        return now >= BIDDING_CONFIRM

    # ============================================================
    #  数据获取
    # ============================================================

    def _fetch_bidding_data(self) -> Dict[str, BiddingSnapshot]:
        """拉取集合竞价数据"""
        if not self._watchlist:
            return {}

        codes = list(self._watchlist.keys())
        snapshots: Dict[str, BiddingSnapshot] = {}
        now = datetime.now()

        try:
            quotes = self.fetcher.get_batch_realtime_quotes(codes)
            for code, quote in quotes.items():
                if not quote.has_basic_data():
                    continue

                pre_close = quote.pre_close or 0
                price = quote.price or 0

                snap = BiddingSnapshot(
                    code=code,
                    name=quote.name or self._watchlist.get(code, ""),
                    timestamp=now,
                    current_price=price,
                    match_volume=quote.volume or 0,
                    unmatch_volume=getattr(quote, 'ask_volume', 0) or 0,
                    pre_close=pre_close,
                    high_price=quote.high or price,
                    low_price=quote.low or price,
                    price_change_pct=((price - pre_close) / pre_close * 100) if pre_close > 0 else 0,
                    volume_ratio=quote.volume_ratio or 0,
                    bid_strength=self._calc_bid_strength(price, pre_close, quote),
                )
                snapshots[code] = snap
        except Exception as e:
            logger.error("获取竞价数据失败: %s", e)

        return snapshots

    def _calc_bid_strength(
        self, price: float, pre_close: float, quote: Any
    ) -> float:
        """计算竞价强度 (0-100)

        综合考量:
        - 价格涨幅 (权重40%): 涨停=满分
        - 竞价量比 (权重35%): 量比>3=满分
        - 价格趋势 (权重25%): 持续走高=满分
        """
        if pre_close <= 0:
            return 0.0

        # 价格涨幅评分 (0-40)
        change_pct = (price - pre_close) / pre_close * 100
        price_score = min(40, max(0, change_pct / 10 * 40))

        # 量比评分 (0-35)
        vol_ratio = quote.volume_ratio or 0
        vol_score = min(35, vol_ratio / 3.0 * 35)

        # 价格趋势评分 (0-25): 基于 high/low 与 current price 的关系
        high = quote.high or price
        low = quote.low or price
        if high > low:
            position = (price - low) / (high - low) if high > low else 0.5
        else:
            position = 0.5
        trend_score = position * 25

        return round(price_score + vol_score + trend_score, 1)

    # ============================================================
    #  信号判断
    # ============================================================

    def _analyze_signals(
        self, snapshots: Dict[str, BiddingSnapshot]
    ) -> List[BiddingSignal]:
        """分析竞价数据，生成交易信号"""
        signals: List[BiddingSignal] = []

        for code, snap in snapshots.items():
            level, reason, risk = self._judge_bidding_level(snap)

            if level in (BiddingSignalLevel.STRONG_BUY, BiddingSignalLevel.BUY):
                signal = self._build_buy_signal(snap, level, reason, risk)
                signals.append(signal)
            elif level == BiddingSignalLevel.RISK:
                signal = self._build_risk_signal(snap, reason, risk)
                signals.append(signal)

        # 按竞价强度排序
        signals.sort(key=lambda s: s.bid_strength, reverse=True)
        return signals

    def _judge_bidding_level(
        self, snap: BiddingSnapshot
    ) -> Tuple[BiddingSignalLevel, str, str]:
        """判断竞价信号等级"""
        reasons = []
        risks = []

        strength = snap.bid_strength
        change_pct = snap.price_change_pct
        vol_ratio = snap.volume_ratio

        # 涨停竞价
        if change_pct >= 9.8:
            reasons.append(f"竞价涨停(+{change_pct:.1f}%)")
            if vol_ratio >= self.STRONG_VOL_RATIO:
                return (BiddingSignalLevel.STRONG_BUY,
                        f"竞价涨停封板，量比{vol_ratio:.1f}，强势确认",
                        "注意开盘后是否开板")
            else:
                return (BiddingSignalLevel.BUY,
                        f"竞价涨停但量比不足({vol_ratio:.1f})，谨慎参与",
                        "量比不足，关注开盘后资金承接")

        # 强势竞价 (涨幅>5%)
        if change_pct >= 5 and strength >= self.STRONG_BID_THRESHOLD:
            reasons.append(f"竞价强势上涨+{change_pct:.1f}%")
            return (BiddingSignalLevel.STRONG_BUY,
                    f"竞价高开{change_pct:.1f}%，竞价强度{strength:.0f}，积极建仓",
                    "")

        # 温和竞价 (涨幅2-5%)
        if 2 <= change_pct < 5 and strength >= self.BUY_BID_THRESHOLD:
            reasons.append(f"竞价温和上涨+{change_pct:.1f}%")
            return (BiddingSignalLevel.BUY,
                    f"竞价高开{change_pct:.1f}%，竞价强度{strength:.0f}，可建仓",
                    "注意开盘后是否持续走强")

        # 关注级别
        if strength >= self.WATCH_BID_THRESHOLD:
            return (BiddingSignalLevel.WATCH,
                    f"竞价强度{strength:.0f}，关注开盘走势",
                    "")

        # 风险信号: 竞价大幅下跌
        if change_pct <= -3:
            return (BiddingSignalLevel.RISK,
                    f"竞价低开{change_pct:.1f}%，竞价弱势",
                    "低开幅度较大，建议观望，不急于进场")

        # 风险信号: 竞价量比异常低
        if vol_ratio < 0.5 and change_pct > 0:
            risks.append(f"竞价量比仅{vol_ratio:.1f}，资金关注度低")

        return (BiddingSignalLevel.WEAK, "竞价无明显信号", "")

    def _build_buy_signal(
        self, snap: BiddingSnapshot, level: BiddingSignalLevel,
        reason: str, risk: str,
    ) -> BiddingSignal:
        """构建买入信号（含止损止盈）"""
        price = snap.current_price
        pre_close = snap.pre_close

        # 止损价
        if level == BiddingSignalLevel.STRONG_BUY:
            stop_loss = round(price * (1 + self.TIGHT_STOP_LOSS_PCT), 2)
        else:
            stop_loss = round(price * (1 + self.STOP_LOSS_PCT), 2)

        # 目标价
        target_1 = round(price * 1.05, 2)   # +5%
        target_2 = round(price * 1.10, 2)   # +10%（涨停）

        # 仓位建议
        if level == BiddingSignalLevel.STRONG_BUY:
            position = 20.0
        else:
            position = 10.0

        # 买入区间: 开盘价 ±1%
        entry_low = round(price * 0.99, 2)
        entry_high = round(price * 1.01, 2)

        return BiddingSignal(
            code=snap.code,
            name=snap.name,
            level=level,
            open_price=price,
            pre_close=pre_close,
            change_pct=snap.price_change_pct,
            bid_strength=snap.bid_strength,
            entry_price_range=f"{entry_low}-{entry_high}",
            stop_loss_price=stop_loss,
            target_price_1=target_1,
            target_price_2=target_2,
            position_pct=position,
            reason=reason,
            risk_note=risk,
        )

    def _build_risk_signal(
        self, snap: BiddingSnapshot, reason: str, risk: str,
    ) -> BiddingSignal:
        """构建风险回避信号"""
        return BiddingSignal(
            code=snap.code,
            name=snap.name,
            level=BiddingSignalLevel.RISK,
            open_price=snap.current_price,
            pre_close=snap.pre_close,
            change_pct=snap.price_change_pct,
            bid_strength=snap.bid_strength,
            entry_price_range="不建议买入",
            stop_loss_price=0,
            target_price_1=0,
            target_price_2=0,
            position_pct=0,
            reason=reason,
            risk_note=risk,
        )

    # ============================================================
    #  飞书推送
    # ============================================================

    def send_feishu_bidding_report(
        self, signals: List[BiddingSignal]
    ) -> bool:
        """发送竞价分析报告到飞书"""
        if not self._webhook_url:
            logger.warning("飞书 Webhook 未配置，跳过竞价推送")
            return False

        buy_signals = [s for s in signals
                       if s.level in (BiddingSignalLevel.STRONG_BUY, BiddingSignalLevel.BUY)]
        risk_signals = [s for s in signals if s.level == BiddingSignalLevel.RISK]

        elements: list[dict] = []

        # 标题
        date_str = datetime.now().strftime("%Y-%m-%d")
        elements.append({
            "tag": "markdown",
            "content": f"📊 **{date_str} 早盘竞价分析报告**\n"
                       f"监控标的: {len(self._watchlist)}只 | "
                       f"买入信号: {len(buy_signals)}只 | "
                       f"风险回避: {len(risk_signals)}只",
        })
        elements.append({"tag": "hr"})

        # 买入信号
        if buy_signals:
            lines = ["🟢 **建仓信号**\n"]
            for i, sig in enumerate(buy_signals, 1):
                emoji = "🔥" if sig.level == BiddingSignalLevel.STRONG_BUY else "📈"
                lines.append(
                    f"{i}. {emoji} **{sig.name}**({sig.code})\n"
                    f"   开盘价: {sig.open_price:.2f} | "
                    f"竞价涨幅: {sig.change_pct:+.2f}%\n"
                    f"   买入区间: {sig.entry_price_range}\n"
                    f"   止损: {sig.stop_loss_price:.2f}({self.TIGHT_STOP_LOSS_PCT*100 if sig.level == BiddingSignalLevel.STRONG_BUY else self.STOP_LOSS_PCT*100:+.0f}%) | "
                    f"目标: {sig.target_price_1:.2f}/{sig.target_price_2:.2f}\n"
                    f"   仓位: {sig.position_pct:.0f}% | "
                    f"竞价强度: {sig.bid_strength:.0f}/100"
                )
                if sig.risk_note:
                    lines.append(f"   ⚠️ {sig.risk_note}")
            elements.append({"tag": "markdown", "content": "\n".join(lines)})
            elements.append({"tag": "hr"})

        # 风险回避
        if risk_signals:
            lines = ["🔴 **风险回避**\n"]
            for sig in risk_signals:
                lines.append(
                    f"• {sig.name}({sig.code}): {sig.reason}"
                )
            elements.append({"tag": "markdown", "content": "\n".join(lines)})
            elements.append({"tag": "hr"})

        elements.append({
            "tag": "markdown",
            "content": "*⚠️ 以上为AI竞价分析，不构成投资建议。集合竞价数据波动大，请结合盘面确认。*",
        })

        card = {
            "header": {
                "title": {"tag": "plain_text", "content": f"🔔 早盘竞价 | {date_str}"},
                "template": "red",
            },
            "elements": elements,
        }

        return self._send_feishu(card)

    def _send_feishu(self, card: dict) -> bool:
        """发送飞书消息"""
        payload = {"msg_type": "interactive", "card": card}
        try:
            resp = requests.post(
                self._webhook_url, json=payload, timeout=15,
            )
            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == 0:
                    logger.info("竞价报告飞书推送成功")
                    return True
            logger.error("飞书推送失败: %s", resp.text[:200])
            return False
        except Exception as e:
            logger.error("飞书推送异常: %s", e)
            return False

    # ============================================================
    #  监控循环
    # ============================================================

    def _monitor_loop(self):
        """竞价监控主循环"""
        logger.info("竞价监控线程启动")

        confirmed_sent = False  # 9:25 是否已发送确认信号

        while not self._stop_event.is_set():
            now = datetime.now().time()

            # 不在竞价时段 → 等待
            if not self.is_bidding_time():
                if now >= BIDDING_END:
                    logger.info("竞价时段已结束")
                    break
                time.sleep(10)
                continue

            try:
                # 拉取竞价数据
                snapshots = self._fetch_bidding_data()

                # 存入历史
                with self._history_lock:
                    for code, snap in snapshots.items():
                        if code not in self._bid_history:
                            self._bid_history[code] = []
                        self._bid_history[code].append(snap)

                # 9:25 确认信号
                if self.is_confirmed_time() and not confirmed_sent:
                    logger.info("9:25 竞价确认，开始分析信号...")
                    signals = self._analyze_signals(snapshots)

                    with self._signals_lock:
                        self._signals = signals

                    # 飞书推送
                    if signals:
                        self.send_feishu_bidding_report(signals)
                        logger.info(
                            "竞价信号推送完成: 买入%d只, 风险%d只",
                            sum(1 for s in signals if s.level in (
                                BiddingSignalLevel.STRONG_BUY,
                                BiddingSignalLevel.BUY,
                            )),
                            sum(1 for s in signals if s.level == BiddingSignalLevel.RISK),
                        )

                    confirmed_sent = True

            except Exception as e:
                logger.error("竞价监控异常: %s", e)

            # 每10秒拉取一次
            time.sleep(10)

        logger.info("竞价监控线程结束")

    # ============================================================
    #  生命周期
    # ============================================================

    def start_monitoring(self):
        """启动竞价监控"""
        if self._thread and self._thread.is_alive():
            logger.warning("竞价监控已在运行")
            return

        if not self._watchlist:
            logger.warning("监控标的为空")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="BiddingMonitor",
            daemon=True,
        )
        self._thread.start()
        logger.info("竞价监控已启动: %d只标的", len(self._watchlist))

    def stop_monitoring(self):
        """停止竞价监控"""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        logger.info("竞价监控已停止")

    def get_signals(self) -> List[BiddingSignal]:
        """获取当前信号"""
        with self._signals_lock:
            return list(self._signals)

    def get_bid_history(self, code: str) -> List[BiddingSnapshot]:
        """获取某只股票的竞价历史"""
        with self._history_lock:
            return list(self._bid_history.get(code, []))

    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        return {
            "is_bidding_time": self.is_bidding_time(),
            "is_confirmed": self.is_confirmed_time(),
            "watchlist_count": len(self._watchlist),
            "signals_count": len(self._signals),
            "signals": [
                {
                    "code": s.code,
                    "name": s.name,
                    "level": s.level.value,
                    "open_price": s.open_price,
                    "change_pct": s.change_pct,
                    "bid_strength": s.bid_strength,
                }
                for s in self._signals
            ],
        }


# ============================================================
#  全局单例
# ============================================================

_bidding_monitor: Optional[PreMarketBiddingMonitor] = None
_bidding_lock = threading.Lock()


def get_bidding_monitor() -> PreMarketBiddingMonitor:
    global _bidding_monitor
    with _bidding_lock:
        if _bidding_monitor is None:
            _bidding_monitor = PreMarketBiddingMonitor()
        return _bidding_monitor


def reset_bidding_monitor():
    global _bidding_monitor
    with _bidding_lock:
        if _bidding_monitor is not None:
            try:
                _bidding_monitor.stop_monitoring()
            except Exception as e:
                logger.debug("竞价监控器停止失败: %s", e)
        _bidding_monitor = None
