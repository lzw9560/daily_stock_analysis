# -*- coding: utf-8 -*-
"""
持仓盘中监控引擎

核心功能：
1. 轮询腾讯财经实时行情（3s/轮）
2. 策略评估 + 信号触发
3. 飞书 Webhook 实时告警
4. 异常处理 + 断线重连（指数退避）
5. 交易时段智能启停（9:15-15:00）
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from data_provider.tencent_fetcher import TencentFetcher
from data_provider.realtime_types import CircuitBreaker

from .feishu_alert import PositionMonitorFeishuSender
from .strategies import (
    BaseStrategy,
    TriggerSignal,
    create_strategies,
    get_default_strategies,
)

logger = logging.getLogger(__name__)

# 交易时段定义（北京时间）
TRADING_SESSIONS = [
    # 早盘集合竞价 + 连续竞价
    (dt_time(9, 15), dt_time(11, 30)),
    # 午盘
    (dt_time(13, 0), dt_time(15, 0)),
]

WATCHLIST_FILE = Path(__file__).parent.parent.parent / "watchlist.json"


class MonitorStatus:
    """监控状态枚举"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class PositionMonitorEngine:
    """
    持仓盘中监控引擎

    生命周期：
    1. start()  → 启动监控线程
    2. pause()  → 暂停（保留状态）
    3. resume() → 恢复
    4. stop()   → 完全停止
    """

    def __init__(
        self,
        poll_interval: float = 3.0,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        strategies: Optional[List[Dict[str, Any]]] = None,
        watchlist_codes: Optional[List[str]] = None,
    ):
        """
        Args:
            poll_interval: 轮询间隔（秒），默认 3s
            webhook_url: 飞书 Webhook URL
            webhook_secret: 飞书签名密钥
            strategies: 策略配置列表，默认使用内置策略
            watchlist_codes: 监控标的列表，默认从 watchlist.json 加载
        """
        self.poll_interval = poll_interval
        self._status = MonitorStatus.STOPPED
        self._status_lock = threading.Lock()

        # 数据源
        self._fetcher = TencentFetcher()
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,     # 连续失败5次熔断
            cooldown_seconds=60.0,   # 冷却60s
            half_open_max_calls=2,
        )

        # 飞书发送器
        webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK_URL", "")
        webhook_secret = webhook_secret or os.getenv("FEISHU_WEBHOOK_SECRET", "")
        self._sender = PositionMonitorFeishuSender(
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )

        # 策略
        strategy_configs = strategies or get_default_strategies()
        self._strategies: List[BaseStrategy] = create_strategies(strategy_configs)
        logger.info("已加载 %d 条监控策略", len(self._strategies))

        # 监控标的
        self._watchlist: Dict[str, str] = {}  # {code: name}
        if watchlist_codes:
            self._watchlist = {c: "" for c in watchlist_codes}
        self._load_watchlist_from_file()

        # 线程
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 统计
        self._stats = {
            "rounds": 0,
            "signals_triggered": 0,
            "errors": 0,
            "last_poll_time": None,
            "start_time": None,
        }
        self._stats_lock = threading.Lock()

    # ============================================================
    #  自选股加载
    # ============================================================

    def _load_watchlist_from_file(self):
        """从 watchlist.json 加载自选股"""
        if not WATCHLIST_FILE.exists():
            logger.warning("watchlist.json 不存在，使用默认标的")
            return

        try:
            import json
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for code, info in data.items():
                        if code not in self._watchlist:
                            self._watchlist[code] = info.get("name", "")
                    logger.info(
                        "从 watchlist.json 加载了 %d 只标的",
                        len(self._watchlist),
                    )
        except Exception as e:
            logger.error("加载 watchlist.json 失败: %s", e)

    def add_stock(self, code: str, name: str = ""):
        """动态添加监控标的"""
        self._watchlist[code] = name

    def remove_stock(self, code: str):
        """动态移除监控标的"""
        self._watchlist.pop(code, None)

    def set_watchlist(self, codes: Dict[str, str]):
        """设置完整监控列表"""
        self._watchlist = dict(codes)

    # ============================================================
    #  交易时段检查
    # ============================================================

    @staticmethod
    def is_trading_time() -> bool:
        """检查当前是否在交易时段内"""
        now = datetime.now().time()
        for start, end in TRADING_SESSIONS:
            if start <= now <= end:
                return True
        return False

    # ============================================================
    #  核心轮询循环
    # ============================================================

    def _poll_loop(self):
        """监控主循环（运行在独立线程中）"""
        logger.info("监控线程启动，标的数: %d，轮询间隔: %.1fs",
                     len(self._watchlist), self.poll_interval)

        self._set_status(MonitorStatus.RUNNING)
        with self._stats_lock:
            self._stats["start_time"] = datetime.now().isoformat()

        retry_count = 0
        max_retry_delay = 60  # 最大重试间隔 60s

        while not self._stop_event.is_set():
            # 检查是否暂停
            if self._status == MonitorStatus.PAUSED:
                time.sleep(1)
                continue

            # 交易时段检查
            if not self.is_trading_time():
                if retry_count == 0:
                    logger.debug("非交易时段，等待中...")
                time.sleep(30)  # 非交易时段慢速等待
                continue

            try:
                # 熔断检查
                if not self._circuit_breaker.is_available("tencent"):
                    logger.warning("腾讯行情数据源处于熔断状态，跳过本轮")
                    time.sleep(self.poll_interval * 2)
                    continue

                # 拉取行情
                signals = self._fetch_and_evaluate()
                retry_count = 0  # 成功后重置

                # 发送信号
                if signals:
                    self._sender.send_batch_signals(signals)
                    with self._stats_lock:
                        self._stats["signals_triggered"] += len(signals)

                with self._stats_lock:
                    self._stats["rounds"] += 1
                    self._stats["last_poll_time"] = datetime.now().isoformat()

            except Exception as e:
                retry_count += 1
                logger.error("轮询异常 (第%d次): %s", retry_count, e)
                self._circuit_breaker.record_failure("tencent", str(e))
                with self._stats_lock:
                    self._stats["errors"] += 1

                # 指数退避
                delay = min(self.poll_interval * (2 ** min(retry_count, 5)), max_retry_delay)
                logger.info("退避等待 %.1fs 后重试", delay)
                self._set_status(MonitorStatus.RECONNECTING)
                time.sleep(delay)
                self._set_status(MonitorStatus.RUNNING)
                continue

            # 正常间隔
            time.sleep(self.poll_interval)

        self._set_status(MonitorStatus.STOPPED)
        logger.info("监控线程已停止")

    def _fetch_and_evaluate(self) -> List[TriggerSignal]:
        """获取行情并评估策略"""
        if not self._watchlist:
            return []

        codes = list(self._watchlist.keys())

        try:
            quotes = self._fetcher.get_batch_realtime_quotes(codes)
        except Exception as e:
            logger.error("获取行情数据失败: %s", e)
            self._circuit_breaker.record_failure("tencent", str(e))
            return []

        if not quotes:
            self._circuit_breaker.record_inconclusive("tencent")
            return []

        self._circuit_breaker.record_success("tencent")

        # 补充名称
        for code, quote in quotes.items():
            if quote.name and code in self._watchlist and not self._watchlist[code]:
                self._watchlist[code] = quote.name

        # 策略评估
        signals: List[TriggerSignal] = []
        for code, quote in quotes.items():
            if not quote.has_basic_data():
                continue

            name = self._watchlist.get(code, quote.name or code)
            quote_dict = {
                "price": quote.price,
                "change_pct": quote.change_pct,
                "change_amount": quote.change_amount,
                "volume": quote.volume,
                "volume_ratio": quote.volume_ratio,
                "turnover_rate": quote.turnover_rate,
                "amplitude": quote.amplitude,
                "open_price": quote.open_price,
                "high": quote.high,
                "low": quote.low,
                "pre_close": quote.pre_close,
            }

            try:
                for strategy in self._strategies:
                    if not strategy.config.enabled:
                        continue

                    signal = strategy.evaluate_with_cooldown(code, name, quote_dict)
                    if signal:
                        signals.append(signal)
                        logger.info(
                            "触发信号: %s %s %s",
                            code, signal.strategy_type.value, signal.message,
                        )
            except Exception as e:
                logger.error("策略评估异常 (%s): %s", code, e)

        return signals

    # ============================================================
    #  生命周期管理
    # ============================================================

    def start(self):
        """启动监控"""
        if self._status == MonitorStatus.RUNNING:
            logger.warning("监控已在运行中")
            return

        if not self._watchlist:
            logger.warning("监控标的为空，请先添加自选股")

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="PositionMonitor",
            daemon=True,
        )
        self._thread.start()
        logger.info("监控已启动")

        # 可选：发送启动心跳
        if self._sender._webhook_url:
            try:
                self._sender.send_heartbeat()
            except Exception:
                pass

    def pause(self):
        """暂停监控"""
        self._set_status(MonitorStatus.PAUSED)
        logger.info("监控已暂停")

    def resume(self):
        """恢复监控"""
        if self._status == MonitorStatus.PAUSED:
            self._set_status(MonitorStatus.RUNNING)
            logger.info("监控已恢复")

    def stop(self):
        """停止监控"""
        self._stop_event.set()
        self._set_status(MonitorStatus.STOPPED)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        logger.info("监控已停止")

    def _set_status(self, status: str):
        with self._status_lock:
            self._status = status

    # ============================================================
    #  状态查询
    # ============================================================

    @property
    def status(self) -> str:
        with self._status_lock:
            return self._status

    @property
    def is_trading(self) -> bool:
        return self.is_trading_time()

    def get_status(self) -> Dict[str, Any]:
        """获取完整监控状态"""
        with self._stats_lock:
            stats = dict(self._stats)
        return {
            "status": self.status,
            "is_trading_time": self.is_trading_time(),
            "watchlist_count": len(self._watchlist),
            "watchlist": [
                {"code": c, "name": n} for c, n in self._watchlist.items()
            ],
            "strategies_count": len(self._strategies),
            "strategies": [
                {
                    "type": s.strategy_type.value,
                    "enabled": s.config.enabled,
                    "params": s.config.params,
                }
                for s in self._strategies
            ],
            "poll_interval": self.poll_interval,
            "circuit_breaker": self._circuit_breaker.get_status(),
            **stats,
        }


# ============================================================
#  全局单例
# ============================================================

_engine_instance: Optional[PositionMonitorEngine] = None
_engine_lock = threading.Lock()


def get_monitor_engine() -> PositionMonitorEngine:
    """获取监控引擎单例"""
    global _engine_instance
    with _engine_lock:
        if _engine_instance is None:
            _engine_instance = PositionMonitorEngine()
        return _engine_instance


def reset_monitor_engine():
    """重置监控引擎（用于测试或重配置）"""
    global _engine_instance
    with _engine_lock:
        if _engine_instance is not None:
            try:
                _engine_instance.stop()
            except Exception:
                pass
        _engine_instance = None
