"""
打板助手数据模型
定义涨停板相关的数据结构

基于 SEAL_PLATE_ARCHITECTURE.md v2.1
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PlateType(Enum):
    """涨停板类型 — 架构文档 §2.2 板型判定"""
    NORMAL = "normal"        # 普通涨停 — 盘中封板
    FIRST = "first"          # 一字涨停 — 开盘即封板，换手率 <1%
    TURNING = "turning"      # 地天板 — 同日跌停→涨停


class SealStrength(Enum):
    """封板强度 — 架构文档 §2.2 强度分级"""
    STRONG = "strong"      # 强封 — 封单>市值2%，开板=0
    NORMAL = "normal"      # 正常 — 封单>市值1%，开板≤1
    WEAK = "weak"          # 弱封 — 封单<市值0.5%或开板≥2
    BROKEN = "broken"      # 炸板 — 已开板未回封


@dataclass
class SealPlateStock:
    """涨停股票数据 — 架构文档 §9 数据模型"""

    # === 基础信息 ===
    code: str               # 股票代码
    name: str               # 股票名称
    close_price: float      # 收盘价/当前价
    change_pct: float       # 涨跌幅 (%)
    limit_up_price: float   # 涨停价
    turnover_rate: float    # 换手率 (%)

    # === 成交量 ===
    volume: float = 0.0     # 成交量（手）
    amount: float = 0.0     # 成交金额（万元）

    # === 封板信息 ===
    seal_amount: float = 0.0       # 封单金额（万元）
    seal_time: str | None = None   # 封板时间 (HH:MM:SS)
    open_count: int = 0            # 开板次数

    # === 关联信息 ===
    sector: str | None = None      # 所属板块
    market: str = "A股"            # 市场
    reason: str | None = None      # 涨停原因

    # === 市值信息 (亿) ===
    market_cap: float | None = None    # 流通市值（亿）
    total_cap: float | None = None     # 总市值（亿）

    # === 评分字段 (Analyzer 填充) ===
    score: int = 0                              # 打板评分 (0-100)
    plate_type: PlateType = PlateType.NORMAL    # 涨停板类型
    seal_strength: SealStrength = SealStrength.NORMAL  # 封板强度
    eight_standard_pass: int = 0                # 八项标准通过数 (0-8)
    risk_level: int = 0                         # 炸板风险级别 (0=无 / 1=黄 / 2=红)

    # === 连续涨停 ===
    consecutive_days: int = 0                   # 连续涨停天数 (1=首板)

    @property
    def seal_time_dt(self) -> datetime | None:
        """封板时间转为 datetime"""
        if not self.seal_time:
            return None
        try:
            return datetime.strptime(self.seal_time, "%H:%M:%S")
        except ValueError:
            return None

    @property
    def is_morning_seal(self) -> bool:
        """是否 10:30 前封板"""
        if dt := self.seal_time_dt:
            t = dt.time()
            return t.hour < 10 or (t.hour == 10 and t.minute <= 30)
        return False

    @property
    def is_first_board(self) -> bool:
        """是否首板"""
        return self.consecutive_days <= 1


@dataclass
class SealPlateReport:
    """打板分析报告 — 架构文档 §9 数据模型"""

    # === 基本信息 ===
    date: str                                               # 分析日期 YYYYMMDD
    generated_at: datetime = field(default_factory=datetime.now)

    # === 统计数据 ===
    total_limit_up: int = 0          # 涨停总数
    main_board: int = 0              # 主板涨停数
    gem: int = 0                     # 创业板涨停数
    star: int = 0                    # 科创板涨停数
    bomb_count: int = 0              # 炸板数
    max_consecutive: int = 0         # 最高连板数

    # === 股票列表 ===
    strong_stocks: list[SealPlateStock] = field(default_factory=list)   # 评分 ≥ 70
    watch_stocks: list[SealPlateStock] = field(default_factory=list)    # 评分 50-69
    leader_stocks: list[SealPlateStock] = field(default_factory=list)   # 各板块龙头
    risk_stocks: list[SealPlateStock] = field(default_factory=list)     # 高风险标的

    # === 板块热度 ===
    sector_hot: list[tuple[str, int]] = field(default_factory=list)     # (板块名, 数量)
    sector_heatmap: dict[str, int] = field(default_factory=dict)        # 板块→涨停数映射

    # === 情绪周期 (架构文档 §4) ===
    sentiment_index: float = 50.0    # 情绪指数 0-100
    sentiment_phase: str = "中性"     # 周期阶段: 冰点期/启动期/发酵期/高潮期/退潮期

    # === 风险提示 ===
    warnings: list[str] = field(default_factory=list)

    # --- 兼容字段 ---
    @property
    def sentiment_score(self) -> int:
        return int(self.sentiment_index)

    @property
    def market_sentiment(self) -> str:
        return self.sentiment_phase

    # ========================
    #  序列化
    # ========================

    def to_markdown(self) -> str:
        """转换为 Markdown 格式 — 架构文档 §7.1"""
        lines: list[str] = []

        # 标题
        lines.append(f"# 📈 打板助手分析报告")
        lines.append(f"")
        lines.append(f"**分析日期**: {self.date}  ")
        lines.append(f"**生成时间**: {self.generated_at.strftime('%H:%M:%S')}")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

        # 市场概况
        lines.append(f"## 📊 市场概况")
        lines.append(f"")
        lines.append(f"| 指标 | 数值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 涨停总数 | {self.total_limit_up} |")
        lines.append(f"| 主板 | {self.main_board} |")
        lines.append(f"| 创业板 | {self.gem} |")
        lines.append(f"| 科创板 | {self.star} |")
        lines.append(f"| 炸板数 | {self.bomb_count} |")
        lines.append(f"| 最高连板 | {self.max_consecutive} 板 |")
        lines.append(f"| 情绪指数 | {self.sentiment_index:.0f} ({self.sentiment_phase}) |")
        lines.append(f"")

        # 强势涨停 TOP8
        if self.strong_stocks:
            lines.append(f"---")
            lines.append(f"")
            lines.append(f"## 🔥 强势涨停 ({len(self.strong_stocks)}只)")
            lines.append(f"")
            lines.append(f"| 股票 | 代码 | 涨停价 | 涨幅 | 封板 | 评分 | 板型 | 封板强度 |")
            lines.append(f"|------|------|--------|------|------|------|------|----------|")
            for stock in self.strong_stocks[:8]:
                seal = stock.seal_time or "盘中"
                plate_label = {
                    PlateType.FIRST: "一字",
                    PlateType.TURNING: "地天",
                    PlateType.NORMAL: "普通",
                }.get(stock.plate_type, "普通")
                strength_label = {
                    SealStrength.STRONG: "强封",
                    SealStrength.NORMAL: "正常",
                    SealStrength.WEAK: "弱封",
                    SealStrength.BROKEN: "炸板",
                }.get(stock.seal_strength, "正常")
                lines.append(
                    f"| {stock.name} | {stock.code} | {stock.limit_up_price:.2f} | "
                    f"+{stock.change_pct:.2f}% | {seal} | {stock.score} | "
                    f"{plate_label} | {strength_label} |"
                )
            lines.append(f"")

        # 龙头股
        if self.leader_stocks:
            lines.append(f"## 👑 龙头股 ({len(self.leader_stocks)}只)")
            lines.append(f"")
            lines.append(f"| 板块 | 龙头 | 代码 | 评分 | 封板 |")
            lines.append(f"|------|------|------|------|------|")
            for stock in self.leader_stocks:
                sector = stock.sector or "其他"
                seal = stock.seal_time or "盘中"
                lines.append(f"| {sector} | {stock.name} | {stock.code} | {stock.score} | {seal} |")
            lines.append(f"")

        # 板块热度
        if self.sector_hot:
            lines.append(f"## 📂 板块热度 TOP5")
            lines.append(f"")
            for sector, count in self.sector_hot[:5]:
                lines.append(f"- **{sector}**: {count}只涨停")
            lines.append(f"")

        # 风险标的
        if self.risk_stocks:
            lines.append(f"## ⚠️ 风险标的 ({len(self.risk_stocks)}只)")
            lines.append(f"")
            for stock in self.risk_stocks:
                lines.append(f"- **{stock.name}**({stock.code}) — "
                           f"八项标准通过 {stock.eight_standard_pass}/8, 评分 {stock.score}")
            lines.append(f"")

        # 风险提示
        if self.warnings:
            lines.append(f"## 🚨 风险提示")
            lines.append(f"")
            for w in self.warnings:
                lines.append(f"- {w}")
            lines.append(f"")

        lines.append(f"---")
        lines.append(f"*本报告仅供参考，不构成投资建议*")
        lines.append(f"")

        return "\n".join(lines)

    def to_feishu_message(self) -> dict:
        """转换为飞书卡片消息 — 架构文档 §7.1"""
        top_stocks = self.strong_stocks[:5]
        stock_lines: list[str] = []
        for stock in top_stocks:
            seal = stock.seal_time or "盘中"
            stock_lines.append(f"• {stock.name}({stock.code}) 封板:{seal} 评分:{stock.score}")

        elements: list[dict] = [
            {
                "tag": "markdown",
                "content": (
                    f"📊 **涨停总数**: {self.total_limit_up} | "
                    f"💥 **炸板**: {self.bomb_count} | "
                    f"🔥 **强势**: {len(self.strong_stocks)}\n"
                    f"💭 **情绪**: {self.sentiment_phase}({self.sentiment_index:.0f}分)"
                )
            },
            {"tag": "hr"},
            {"tag": "markdown", "content": "**🔥 强势涨停**"},
        ]

        if stock_lines:
            elements.append({"tag": "markdown", "content": "\n".join(stock_lines)})

        if self.warnings:
            elements.append({"tag": "hr"})
            elements.append({"tag": "markdown", "content": f"⚠️ {'; '.join(self.warnings[:3])}"})

        elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": "*仅供参考，不构成投资建议*"})

        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"🔥 打板助手 | {self.date}"},
                    "template": "red"
                },
                "elements": elements,
            }
        }

    def _stock_to_dict(self, s: SealPlateStock) -> dict:
        """单个股票序列化"""
        return {
            "code": s.code, "name": s.name,
            "score": s.score, "change_pct": s.change_pct,
            "close_price": s.close_price,
            "seal_time": s.seal_time, "sector": s.sector,
            "reason": s.reason, "plate_type": s.plate_type.value,
            "seal_strength": s.seal_strength.value,
            "eight_standard_pass": s.eight_standard_pass,
            "risk_level": s.risk_level,
            "consecutive_days": s.consecutive_days,
            "turnover_rate": s.turnover_rate,
            "seal_amount": s.seal_amount,
            "market": s.market,
            "market_cap": s.market_cap,
        }

    def to_dict(self) -> dict:
        """转为可 JSON 序列化的字典"""
        return {
            "date": self.date,
            "total_limit_up": self.total_limit_up,
            "main_board": self.main_board,
            "gem": self.gem,
            "star": self.star,
            "bomb_count": self.bomb_count,
            "max_consecutive": self.max_consecutive,
            "sentiment_index": self.sentiment_index,
            "sentiment_phase": self.sentiment_phase,
            "sentiment_score": int(self.sentiment_index),
            "market_sentiment": self.sentiment_phase,
            "strong_stocks": [self._stock_to_dict(s) for s in self.strong_stocks],
            "leader_stocks": [self._stock_to_dict(s) for s in self.leader_stocks],
            "risk_stocks": [self._stock_to_dict(s) for s in self.risk_stocks],
            "watch_stocks": [self._stock_to_dict(s) for s in self.watch_stocks],
            "sector_hot": [{"sector": s, "count": c} for s, c in self.sector_hot],
            "warnings": self.warnings,
        }
