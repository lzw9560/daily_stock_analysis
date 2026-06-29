# -*- coding: utf-8 -*-
"""板块联动与主线识别（交易系统升级 Phase 2）

核心功能:
1. 板块强度打分：涨停数 + 资金流入 + 涨幅 + 个股联动
2. 主线识别：连续2日以上的资金聚集板块
3. 轮动检测：资金从高位板块流向低位板块的信号
4. 板块内选股：在强势板块内筛选个股（板块共振）
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# 数据模型
# ============================================================

@dataclass
class SectorRank:
    """板块排名"""
    sector_name: str
    rank: int
    change_pct: float             # 板块涨跌幅
    limit_up_count: int           # 涨停数
    net_inflow: float             # 资金净流入(亿)
    strength_score: float         # 综合强度分 0-100
    leader_stocks: list = field(default_factory=list)  # 领涨股 [{name, change_pct}] or [name]
    up_count: int = 0              # 板块内上涨家数
    total_stocks: int = 0          # 板块成分股总数
    consecutive_days: int = 0      # 连续上榜天数


@dataclass
class SectorStrength:
    """板块内部强度"""
    sector_name: str
    total_stocks: int             # 板块总股数
    up_count: int                 # 上涨数
    down_count: int               # 下跌数
    limit_up_count: int           # 涨停数
    up_ratio: float               # 上涨比例
    avg_change: float             # 平均涨幅
    internal_resonance: float     # 内部共振度 0-1


@dataclass
class SectorFlow:
    """板块资金流向"""
    sector_name: str
    net_inflow: float             # 净流入(亿)
    main_inflow: float            # 主力净流入(亿)
    retail_inflow: float          # 散户净流入(亿)
    inflow_ratio: float           # 流入占比
    consecutive_inflow_days: int = 0  # 连续流入天数


@dataclass
class HotTheme:
    """热点题材"""
    theme_name: str
    heat_score: float             # 热度 0-100
    related_sectors: list[str]    # 关联板块
    core_stocks: list[str]        # 核心标的
    event_catalyst: str = ""      # 事件催化
    duration_days: int = 1        # 持续天数


@dataclass
class RotationStep:
    """轮动步骤"""
    from_sector: str
    to_sector: str
    from_change: float            # 流出板块涨跌幅
    to_change: float              # 流入板块涨跌幅
    flow_amount: float            # 资金转移量(亿)
    rotation_score: float         # 轮动可信度


# ============================================================
# 板块分析器
# ============================================================

class SectorAnalyzer:
    """板块联动与主线识别分析器"""

    # 加权参数
    WEIGHT_LIMIT_UP_COUNT = 0.35    # 涨停数权重
    WEIGHT_CHANGE_PCT = 0.25        # 涨幅权重
    WEIGHT_NET_INFLOW = 0.25        # 资金流入权重
    WEIGHT_RESONANCE = 0.15         # 个股联动权重

    # 主线判定阈值
    MAINLINE_MIN_DAYS = 2           # 连续上榜天数
    MAINLINE_MIN_STRENGTH = 60      # 最低强度分
    MAINLINE_TOP_N = 3              # 取前N为主线

    def __init__(self):
        self._sector_history: dict[str, list[dict]] = defaultdict(list)
        self._flow_history: dict[str, list[float]] = defaultdict(list)

    # ========================
    #  板块强度排名
    # ========================

    def rank_sectors(
        self,
        sectors_data: list[dict],
        *,
        date: str = "",
    ) -> list[SectorRank]:
        """板块强度排名

        Args:
            sectors_data: [{
                "name": "AI应用",
                "change_pct": 4.5,
                "limit_up_count": 5,
                "net_inflow": 15.0,
                "leader_stocks": ["股票1", "股票2"],
                "total_stocks": 120,
                "up_count": 80,
            }]
            date: 日期

        Returns:
            按强度分降序排列的板块列表
        """
        rankings: list[SectorRank] = []

        for i, sd in enumerate(sectors_data):
            name = sd.get("name", "")
            change_pct = sd.get("change_pct", 0)
            limit_up_count = sd.get("limit_up_count", 0)
            net_inflow = sd.get("net_inflow", 0)
            leader_stocks = sd.get("leader_stocks", [])
            total_stocks = sd.get("total_stocks", 1)
            up_count = sd.get("up_count", 0)

            # 计算个股联动度
            up_ratio = up_count / max(total_stocks, 1)
            resonance = min(1.0, up_ratio + limit_up_count / max(total_stocks, 1) * 3)

            # 综合强度分
            lu_score = min(100, limit_up_count * 15) * self.WEIGHT_LIMIT_UP_COUNT
            change_score = min(100, max(0, change_pct + 5) * 10) * self.WEIGHT_CHANGE_PCT
            inflow_score = min(100, max(0, net_inflow + 10) * 5) * self.WEIGHT_NET_INFLOW
            resonance_score = resonance * 100 * self.WEIGHT_RESONANCE

            strength_score = round(lu_score + change_score + inflow_score + resonance_score, 1)

            # 检查连续上榜天数
            consecutive_days = self._get_consecutive_days(name)

            rankings.append(SectorRank(
                sector_name=name,
                rank=0,  # 稍后排序赋值
                change_pct=change_pct,
                limit_up_count=limit_up_count,
                net_inflow=net_inflow,
                strength_score=strength_score,
                leader_stocks=leader_stocks,
                up_count=up_count,
                total_stocks=total_stocks,
                consecutive_days=consecutive_days,
            ))

        # 排序并分配排名
        rankings.sort(key=lambda r: r.strength_score, reverse=True)
        for i, r in enumerate(rankings):
            r.rank = i + 1

        # 更新历史
        if date:
            for r in rankings:
                self._sector_history[r.sector_name].append({
                    "date": date,
                    "rank": r.rank,
                    "strength_score": r.strength_score,
                })

        return rankings

    # ========================
    #  主线识别
    # ========================

    def identify_mainlines(
        self,
        rankings: list[SectorRank],
    ) -> list[SectorRank]:
        """识别当前市场主线

        条件:
        1. 强度分 >= 60
        2. 连续上榜 >= 2 天（或当日强度分 >= 80）
        3. 取 TOP_N
        """
        mainlines = [
            r for r in rankings
            if r.strength_score >= self.MAINLINE_MIN_STRENGTH
            and (r.consecutive_days >= self.MAINLINE_MIN_DAYS or r.strength_score >= 80)
        ]
        return mainlines[:self.MAINLINE_TOP_N]

    def identify_mainlines_extended(
        self,
        rankings: list[SectorRank],
        *,
        prev_day_data: Optional[dict] = None,
    ) -> dict:
        """识别主线并返回详细信息"""
        mainlines = self.identify_mainlines(rankings)

        result = {
            "mainlines": [{
                "sector_name": m.sector_name,
                "strength_score": m.strength_score,
                "consecutive_days": m.consecutive_days,
                "limit_up_count": m.limit_up_count,
                "leader_stocks": m.leader_stocks[:3],
            } for m in mainlines],
            "count": len(mainlines),
            "market_health": self._assess_market_health(rankings, mainlines),
            "rotation_alert": None,
        }

        # 如果有前日数据，做简要轮动分析
        if prev_day_data:
            prev_sectors = prev_day_data.get("sectors", [])
            if prev_sectors:
                rotations = self.detect_rotation(rankings, prev_sectors)
                if rotations:
                    result["rotation_alert"] = {
                        "from": rotations[0].from_sector,
                        "to": rotations[0].to_sector,
                        "score": rotations[0].rotation_score,
                    }

        return result

    # ========================
    #  轮动检测
    # ========================

    def detect_rotation(
        self,
        current_rankings: list[SectorRank],
        prev_rankings: list[dict],
    ) -> list[RotationStep]:
        """检测板块轮动

        通过对比当日和前日板块排名变化，识别资金轮动方向。
        """
        rotations: list[RotationStep] = []

        # 构建前日排名映射
        prev_map: dict[str, dict] = {}
        for pr in prev_rankings:
            prev_map[pr.get("name", "")] = pr

        current_map = {r.sector_name: r for r in current_rankings}

        # 找出排名变化大的板块对
        for from_name, from_rank in current_map.items():
            prev = prev_map.get(from_name)
            if not prev:
                continue

            prev_rank = prev.get("rank", 99)
            # 排名显著下降的板块（资金流出）
            if prev_rank <= 5 and from_rank.rank >= 10:
                # 找出可能承接资金的板块
                for to_name, to_rank in current_map.items():
                    to_prev = prev_map.get(to_name)
                    if not to_prev:
                        continue
                    to_prev_rank = to_prev.get("rank", 99)
                    # 排名显著上升的板块（资金流入）
                    if to_prev_rank >= 10 and to_rank.rank <= 5:
                        # 计算资金转移估计
                        flow_out = abs(prev.get("net_inflow", 0) - from_rank.net_inflow)
                        flow_in = abs(to_prev.get("net_inflow", 0) - to_rank.net_inflow)
                        flow_est = min(flow_out, flow_in)

                        rotation_score = min(1.0, (
                            (prev_rank - from_rank.rank) / 20 +
                            (to_rank.rank - to_prev_rank) / 20
                        ))

                        rotations.append(RotationStep(
                            from_sector=from_name,
                            to_sector=to_name,
                            from_change=from_rank.change_pct,
                            to_change=to_rank.change_pct,
                            flow_amount=flow_est,
                            rotation_score=round(rotation_score, 2),
                        ))

        rotations.sort(key=lambda r: r.rotation_score, reverse=True)
        return rotations[:3]

    # ========================
    #  板块内选股
    # ========================

    def select_stocks_in_sector(
        self,
        sector_name: str,
        rankings: list[SectorRank],
        limit_up_stocks: list[dict],
    ) -> list[dict]:
        """在强势板块内选股

        Args:
            sector_name: 板块名
            rankings: 板块排名
            limit_up_stocks: 涨停股列表 [{"code": "", "name": "", "sector": "", ...}]

        Returns:
            板块内符合条件的个股列表
        """
        # 找该板块
        sector = next((r for r in rankings if r.sector_name == sector_name), None)
        if not sector:
            return []

        # 筛选属于该板块的涨停股
        candidates = [s for s in limit_up_stocks if s.get("sector") == sector_name]

        # 按封板时间排序
        candidates.sort(key=lambda s: s.get("seal_time", "99:99:99"))

        # 优先选早封板+强封单
        result = []
        for s in candidates:
            seal_amount = s.get("seal_amount", 0)
            seal_time = s.get("seal_time", "")

            score = 0
            if seal_amount >= 10000:
                score += 30
            elif seal_amount >= 5000:
                score += 20
            elif seal_amount >= 2000:
                score += 10

            if seal_time:
                try:
                    parts = seal_time.split(":")
                    hour = int(parts[0])
                    minute = int(parts[1])
                    if hour < 10 or (hour == 10 and minute <= 30):
                        score += 30
                    elif hour < 11:
                        score += 20
                    elif hour < 14:
                        score += 10
                except (ValueError, IndexError):
                    pass

            s["_sector_pick_score"] = score
            result.append(s)

        result.sort(key=lambda s: s["_sector_pick_score"], reverse=True)
        return result[:5]

    # ========================
    #  板块内部强度
    # ========================

    def calculate_internal_strength(
        self,
        sector_name: str,
        stocks: list[dict],
    ) -> SectorStrength:
        """计算板块内部强度"""
        total = len(stocks)
        up = sum(1 for s in stocks if s.get("change_pct", 0) > 0)
        down = sum(1 for s in stocks if s.get("change_pct", 0) < 0)
        limit_up = sum(1 for s in stocks if s.get("change_pct", 0) >= 9.5)
        avg_change = sum(s.get("change_pct", 0) for s in stocks) / max(total, 1)

        up_ratio = up / max(total, 1)
        resonance = up_ratio * 0.6 + (limit_up / max(total, 1)) * 2.0
        resonance = min(1.0, resonance)

        return SectorStrength(
            sector_name=sector_name,
            total_stocks=total,
            up_count=up,
            down_count=down,
            limit_up_count=limit_up,
            up_ratio=round(up_ratio, 2),
            avg_change=round(avg_change, 2),
            internal_resonance=round(resonance, 2),
        )

    # ========================
    #  辅助方法
    # ========================

    def _get_consecutive_days(self, sector_name: str) -> int:
        """计算连续上榜天数"""
        history = self._sector_history.get(sector_name, [])
        # 简化：检查最近的连续记录
        count = 0
        for entry in reversed(history):
            if entry.get("rank", 99) <= 10:
                count += 1
            else:
                break
        return count

    def _assess_market_health(
        self,
        rankings: list[SectorRank],
        mainlines: list[SectorRank],
    ) -> str:
        """评估市场健康度"""
        if not mainlines:
            return "无明显主线，市场散乱"
        top_strength = mainlines[0].strength_score if mainlines else 0
        total_limit_up = sum(r.limit_up_count for r in rankings[:10])

        if top_strength >= 80 and total_limit_up >= 30:
            return "主线明确，赚钱效应强"
        elif top_strength >= 60 and total_limit_up >= 15:
            return "有主线但强度一般，结构性行情"
        elif total_limit_up >= 10:
            return "轮动过快，主线不稳定"
        else:
            return "市场弱势，缺乏做多动力"

    def get_sector_heatmap_data(
        self,
        rankings: list[SectorRank],
    ) -> list[dict]:
        """生成板块热力图数据（供前端使用）"""
        return [{
            "name": r.sector_name,
            "rank": r.rank,
            "strength_score": r.strength_score,
            "change_pct": r.change_pct,
            "limit_up_count": r.limit_up_count,
            "net_inflow": r.net_inflow,
            "consecutive_days": r.consecutive_days,
            "is_mainline": r.strength_score >= self.MAINLINE_MIN_STRENGTH and r.consecutive_days >= self.MAINLINE_MIN_DAYS,
            "leader_stocks": r.leader_stocks,
            "up_count": r.up_count,
            "stock_count": r.total_stocks,
        } for r in rankings[:20]]
