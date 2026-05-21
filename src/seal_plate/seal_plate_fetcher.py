"""
涨停板数据获取服务
基于 SEAL_PLATE_ARCHITECTURE.md v2.1 §2.1

双数据源策略: AKShare（主） + 东方财富 push2 API（备）
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from .models import SealPlateStock

logger = logging.getLogger(__name__)


class SealPlateFetcher:
    """涨停板数据获取器 — 架构文档 §2.1"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def fetch_all(self, date: Optional[str] = None) -> list[SealPlateStock]:
        """
        获取所有涨停板数据

        Args:
            date: 日期 YYYYMMDD，默认今天

        Returns:
            涨停股票列表。容错: 全部不可用返回空列表，不抛异常。
        """
        stocks: list[SealPlateStock] = []

        # 主源: AKShare
        try:
            stocks = self._fetch_from_akshare(date)
            self.logger.info("AKShare 获取到 %d 只涨停股", len(stocks))
        except Exception as exc:
            self.logger.error("AKShare 获取失败: %s", exc)

        # 备用源: 东方财富
        if not stocks:
            try:
                stocks = self._fetch_from_eastmoney(date)
                self.logger.info("东方财富获取到 %d 只涨停股", len(stocks))
            except Exception as exc:
                self.logger.error("东方财富获取失败: %s", exc)

        stocks.sort(key=lambda s: s.score, reverse=True)
        return stocks

    # ========================
    #  AKShare 数据源（主）
    # ========================

    def _fetch_from_akshare(self, date: Optional[str] = None) -> list[SealPlateStock]:
        import akshare as ak

        target = date or datetime.now().strftime("%Y%m%d")

        try:
            df = ak.stock_zt_pool_em(date=target)
        except Exception as exc:
            self.logger.error("AKShare stock_zt_pool_em() 调用失败: %s", exc)
            return []

        stocks: list[SealPlateStock] = []
        for _, row in df.iterrows():
            try:
                code = str(row.get("代码", "")).zfill(6)
                # 涨停价 = 最新价 / (1 + 涨跌幅/100) 反推（近似）
                close_price = float(row.get("最新价", 0))
                change_pct = float(row.get("涨跌幅", 0))
                limit_up_price = round(close_price / (1 + change_pct / 100) * 1.1, 2)

                # 成交额是元，转为万元
                amount_raw = float(row.get("成交额", 0) or 0)
                amount = amount_raw / 10000 if amount_raw > 0 else 0.0

                # 封板资金是元，转为万元
                seal_raw = float(row.get("封板资金", 0) or 0)
                seal_amount = seal_raw / 10000 if seal_raw > 0 else 0.0

                # 流通市值/总市值: 元→亿
                mcap_raw = float(row.get("流通市值", 0) or 0)
                tcap_raw = float(row.get("总市值", 0) or 0)
                market_cap = mcap_raw / 1e8 if mcap_raw > 0 else None
                total_cap = tcap_raw / 1e8 if tcap_raw > 0 else None

                stock = SealPlateStock(
                    code=code,
                    name=str(row.get("名称", "")),
                    close_price=close_price,
                    change_pct=change_pct,
                    limit_up_price=limit_up_price,
                    turnover_rate=float(row.get("换手率", 0) or 0),
                    volume=0.0,
                    amount=amount,
                    sector=str(row.get("所属行业", "")),
                    reason=str(row.get("涨停统计", "") or ""),
                    seal_amount=seal_amount,
                    open_count=int(row.get("炸板次数", 0) or 0),
                    market=self._get_market(code),
                    market_cap=market_cap,
                    total_cap=total_cap,
                    # 封板时间: 优先首次封板时间，格式 092500 → HH:MM:SS
                    seal_time=self._parse_seal_time(
                        row.get("首次封板时间", "")
                        or row.get("最后封板时间", "")
                        or row.get("封板时间", "")
                    ),
                    # 连板天数
                    consecutive_days=self._parse_consecutive_days(
                        row.get("连板数", row.get("连续涨停天数", 0))
                    ),
                )
                stocks.append(stock)
            except Exception as exc:
                self.logger.debug("解析行数据失败: %s", exc)
                continue

        return stocks

    # ========================
    #  东方财富 数据源（备）
    # ========================

    def _fetch_from_eastmoney(self, date: Optional[str] = None) -> list[SealPlateStock]:
        import requests

        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": 1, "pz": 200, "po": 1, "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2, "invt": 2, "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,"
                      "f16,f17,f18,f20,f21,f23,f62,f100,f184,f66,f69",
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "Referer": "https://quote.eastmoney.com/",
        }

        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            resp.encoding = "utf-8"
            data = resp.json()
        except Exception as exc:
            self.logger.error("东方财富请求失败: %s", exc)
            return []

        stocks: list[SealPlateStock] = []
        if not (data.get("data") and data["data"].get("diff")):
            return stocks

        for item in data["data"]["diff"]:
            try:
                change_pct = float(item.get("f3", 0))
                if change_pct < 9.5:
                    continue

                code = str(item.get("f12", ""))
                close_price = float(item.get("f2", 0))
                limit_up_raw = item.get("f15")
                if limit_up_raw and limit_up_raw != "-":
                    limit_up_price = float(limit_up_raw)
                else:
                    limit_up_price = round(close_price * 1.1, 2)

                stock = SealPlateStock(
                    code=code,
                    name=str(item.get("f14", "")),
                    close_price=close_price,
                    change_pct=change_pct,
                    limit_up_price=limit_up_price,
                    turnover_rate=float(item.get("f8", 0) or 0),
                    volume=float(item.get("f5", 0) or 0),
                    amount=float(item.get("f6", 0) or 0) / 10000,
                    sector=str(item.get("f100", "")),
                    market=self._get_market(code),
                )
                stocks.append(stock)
            except (ValueError, KeyError) as exc:
                self.logger.debug("解析东方财富单条失败: %s", exc)
                continue

        return stocks

    # ========================
    #  工具方法
    # ========================

    @staticmethod
    def _get_market(code: str) -> str:
        code = str(code).zfill(6)
        if code.startswith("688"):
            return "科创板"
        if code.startswith("300") or code.startswith("301"):
            return "创业板"
        if code.startswith("6"):
            return "主板"
        if code.startswith("00"):
            return "主板"
        if code.startswith("4") or code.startswith("8"):
            return "北交所"
        return "A股"

    @staticmethod
    def _parse_seal_time(raw) -> str | None:
        """解析封板时间为 HH:MM:SS 字符串"""
        if not raw or str(raw).strip() in ("", "--", "-"):
            return None

        raw = str(raw).strip()

        # 格式1: "092500" (6位无分隔)
        if len(raw) == 6 and raw.isdigit():
            return f"{raw[:2]}:{raw[2:4]}:{raw[4:]}"

        # 格式2: "09:35:12" 或 "09:35"
        if ":" in raw:
            parts = raw.split(":")
            if len(parts) == 2:
                return f"{parts[0]}:{parts[1]}:00"
            if len(parts) == 3:
                return raw

        return raw

    @staticmethod
    def _parse_consecutive_days(raw) -> int:
        """解析连板天数"""
        try:
            return int(float(raw))
        except (ValueError, TypeError):
            return 1  # 默认首板
