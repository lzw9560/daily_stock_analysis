"""
打板质量评分引擎 + 情绪周期分析器
基于 SEAL_PLATE_ARCHITECTURE.md v2.1

包含:
- 7 维度加权评分（§3）
- 八项标准检查（§5）
- 情绪周期分析（§4）
- 炸板风险预警（§6）
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Optional

from .models import PlateType, SealPlateReport, SealPlateStock, SealStrength

logger = logging.getLogger(__name__)


# ================================================================
# 八项标准检查项
# ================================================================

@dataclass
class EightStandardCheck:
    """八项标准检查项 — 架构文档 §5.1"""
    name: str
    description: str
    actual_value: str
    expected_range: str
    passed: bool
    score: int
    weight: float = 0.0


# ================================================================
# 评分引擎
# ================================================================

class SealPlateAnalyzer:
    """涨停板分析器 — 架构文档 §2.2 + §3"""

    # 7 维度权重 — 架构文档 §3.1
    WEIGHTS = {
        "seal_strength":   0.25,   # 封板强度
        "seal_time":       0.20,   # 封板时间
        "turnover_rate":   0.15,   # 换手率
        "amount":          0.15,   # 成交金额
        "open_count":      0.10,   # 开板次数
        "consecutive":     0.10,   # 连续涨停
        "volume_ratio":    0.05,   # 量比
    }

    # 评分等级 — 架构文档 §3.2
    GRADE_TABLE = {
        range(85, 101): ("极佳", "大仓位参与"),
        range(70, 85):  ("良好", "正常仓位"),
        range(55, 70):  ("一般", "小仓试错"),
        range(40, 55):  ("较差", "观望"),
        range(0, 40):   ("危险", "不建议"),
    }

    # 八项标准配置 — 架构文档 §5.1
    EIGHT_STANDARDS: dict[str, dict] = {
        "market_cap": {
            "name": "流通市值", "min": 30, "max": 150,
            "weight": 15, "desc": "30亿-150亿范围最佳",
        },
        "turnover_rate": {
            "name": "换手率", "min": 5, "max": 20,
            "weight": 15, "desc": "5%-20%范围最佳",
        },
        "volume_ratio": {
            "name": "量能比", "min": 1.5,
            "weight": 10, "desc": "封板前量能 > 前5日均量1.5倍",
        },
        "seal_time": {
            "name": "封板时间", "hour": 10, "minute": 30,
            "weight": 20, "desc": "10:30前封板最佳",
        },
        "open_count": {
            "name": "开板次数", "max": 1,
            "weight": 10, "desc": "≤1次最佳，0次完美",
        },
        "seal_amount_ratio": {
            "name": "封单金额", "min_ratio": 0.01,
            "weight": 15, "desc": "封单金额 > 流通市值1%",
        },
        "sector_hot": {
            "name": "题材热度",
            "weight": 10, "desc": "属于当日热点题材TOP10",
        },
        "position": {
            "name": "股价位置",
            "weight": 5, "desc": "低位首板或平台突破",
        },
    }

    def __init__(self, min_score: int = 60):
        self.min_score = min_score
        self.logger = logging.getLogger(self.__class__.__name__)

    # ========================
    #  主分析入口
    # ========================

    def analyze(self, stocks: list[SealPlateStock], date: str) -> SealPlateReport:
        """分析涨停板，生成完整报告 — 架构文档 §2.4 流程"""
        if not stocks:
            return SealPlateReport(date=date)

        # 1. 计算每个股票的评分 + 板型 + 强度 + 八项标准
        hot_sectors = self._get_hot_sectors(stocks)
        for stock in stocks:
            stock.plate_type = self._determine_plate_type(stock)
            stock.seal_strength = self._determine_seal_strength(stock)
            stock.score = self._calculate_score(stock)
            # 八项标准通过数
            eight_result = self._check_eight_standards_on_stock(stock, hot_sectors)
            stock.eight_standard_pass = eight_result["pass_count"]
            # 强制约束 — 架构文档 §5.2: ≥3 项未通过 → 评分上限 55
            if eight_result["fail_count"] >= 3:
                stock.score = min(stock.score, 55)

        # 2. 三板以上警告 — 架构文档 §5.2
        for stock in stocks:
            if stock.consecutive_days >= 3:
                stock.risk_level = max(stock.risk_level, 1)

        # 3. 构建报告
        report = SealPlateReport(date=date)
        report.total_limit_up = len(stocks)

        for stock in stocks:
            mkt = stock.market or ""
            if "科创" in mkt:
                report.star += 1
            elif "创业" in mkt:
                report.gem += 1
            else:
                report.main_board += 1

        # 分类
        report.strong_stocks = [s for s in stocks if s.score >= 70]
        report.watch_stocks = [s for s in stocks if 50 <= s.score < 70]
        report.leader_stocks = self._find_leader_stocks(stocks)
        report.risk_stocks = [s for s in stocks if s.eight_standard_pass < 6 or s.risk_level >= 1]

        # 板块热度
        report.sector_hot = self._calculate_sector_hot(stocks)
        report.sector_heatmap = dict(report.sector_hot)

        # 龙虎榜统计
        report.bomb_count = sum(1 for s in stocks if s.seal_strength == SealStrength.BROKEN)
        report.max_consecutive = max((s.consecutive_days for s in stocks), default=0)

        # 风险提示
        report.warnings = self._generate_warnings(stocks)

        return report

    # ========================
    #  7 维度评分（§3.1）
    # ========================

    def _calculate_score(self, stock: SealPlateStock) -> int:
        """7 维度加权评分，总分 100 — 架构文档 §3.1"""
        dims = {
            "seal_strength": self._score_seal_amount(stock.seal_amount),
            "seal_time":     self._score_seal_time(stock.seal_time),
            "turnover_rate": self._score_turnover(stock.turnover_rate),
            "amount":        self._score_amount(stock.amount),
            "open_count":    self._score_open_count(stock.open_count),
            "consecutive":   self._score_consecutive(stock.consecutive_days),
            "volume_ratio":  self._score_volume_ratio(getattr(stock, "volume_ratio", None)),
        }

        total = sum(dims[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        return int(min(100, max(0, total)))

    @staticmethod
    def _score_seal_amount(amount: float) -> float:
        """封单金额评分 — 越大越高"""
        if amount >= 10000: return 100
        if amount >= 5000:  return 85
        if amount >= 2000:  return 70
        if amount >= 1000:  return 55
        if amount >= 500:   return 40
        if amount >= 100:   return 25
        return 10

    @staticmethod
    def _score_seal_time(seal_time: str | None) -> float:
        """封板时间评分 — 越早越高，架构文档 §3.1: 9:30-9:45 满分"""
        if not seal_time:
            return 30
        try:
            dt = datetime.strptime(seal_time, "%H:%M:%S")
            t = dt.time()
        except ValueError:
            return 30

        if t < time(9, 35):   return 100
        if t < time(9, 45):   return 95
        if t < time(10, 0):   return 85
        if t < time(10, 30):  return 70
        if t < time(11, 0):   return 55
        if t < time(13, 0):   return 40
        if t < time(14, 0):   return 25
        return 10

    @staticmethod
    def _score_turnover(rate: float) -> float:
        """换手率评分 — 1-10% 最佳，两端扣分"""
        if rate < 1:       return 40
        if 1 <= rate <= 5:  return 80
        if 5 < rate <= 10:  return 90
        if 10 < rate <= 20: return 70
        return 40

    @staticmethod
    def _score_amount(amount: float) -> float:
        """成交金额评分 — 越活跃越高"""
        if amount >= 50000:  return 100
        if amount >= 20000:  return 85
        if amount >= 10000:  return 70
        if amount >= 5000:   return 55
        if amount >= 1000:   return 40
        return 20

    @staticmethod
    def _score_open_count(count: int) -> float:
        """开板次数评分 — 0 次满分"""
        if count == 0:   return 100
        if count == 1:   return 70
        if count == 2:   return 50
        if count <= 3:   return 30
        return 10

    @staticmethod
    def _score_consecutive(days: int) -> float:
        """连续涨停评分 — 首板加分，高位连板扣分"""
        if days <= 1:      return 85   # 首板最佳
        if days == 2:      return 70
        if days == 3:      return 55
        if days <= 5:      return 35
        return 15

    @staticmethod
    def _score_volume_ratio(ratio: float | None) -> float:
        """量比评分"""
        if ratio is None:
            return 50
        if ratio >= 2.0:   return 100
        if ratio >= 1.5:   return 80
        if ratio >= 1.0:   return 60
        if ratio >= 0.8:   return 40
        return 20

    @staticmethod
    def get_grade(score: int) -> tuple[str, str]:
        """获取评分等级和建议 — 架构文档 §3.2"""
        for rng, (grade, advice) in SealPlateAnalyzer.GRADE_TABLE.items():
            if score in rng:
                return grade, advice
        return "危险", "不建议"

    # ========================
    #  板型 / 强度判定（§2.2）
    # ========================

    @staticmethod
    def _determine_plate_type(stock: SealPlateStock) -> PlateType:
        """板型判定 — 架构文档 §2.2"""
        # 一字板: 换手率 < 1%
        if stock.turnover_rate < 1:
            return PlateType.FIRST

        # 地天板: 开盘极端低位到涨停
        if stock.change_pct >= 9.9 and stock.turnover_rate > 15:
            # 更严谨的判断需要 O/C 数据；简化处理
            return PlateType.TURNING

        return PlateType.NORMAL

    @staticmethod
    def _determine_seal_strength(stock: SealPlateStock) -> SealStrength:
        """封板强度判定 — 架构文档 §2.2 强度分级表"""
        # 炸板: 已开板且未回封
        if stock.open_count > 0 and stock.seal_amount < 100:
            return SealStrength.BROKEN

        # 强封: 封单 > 5000万 且 0次开板
        if stock.seal_amount >= 5000 and stock.open_count == 0:
            return SealStrength.STRONG

        # 弱封: 封单 < 500万 或 开板≥3次
        if stock.seal_amount < 500 or stock.open_count >= 3:
            return SealStrength.WEAK

        # 正常封板
        return SealStrength.NORMAL

    # ========================
    #  龙头识别
    # ========================

    @staticmethod
    def _find_leader_stocks(stocks: list[SealPlateStock]) -> list[SealPlateStock]:
        """按板块找龙头 — 最早封板且强度最高者"""
        from collections import defaultdict

        groups: dict[str, list[SealPlateStock]] = defaultdict(list)
        for stock in stocks:
            sector = stock.sector or "其他"
            groups[sector].append(stock)

        leaders: list[SealPlateStock] = []
        for sector, group in groups.items():
            if len(group) >= 2:
                # 按封板时间升序，封单金额降序
                group.sort(key=lambda s: (
                    s.seal_time or "99:99:99",
                    -s.seal_amount
                ))
                leaders.append(group[0])

        leaders.sort(key=lambda s: s.score, reverse=True)
        return leaders[:5]

    # ========================
    #  板块热度
    # ========================

    @staticmethod
    def _calculate_sector_hot(stocks: list[SealPlateStock]) -> list[tuple[str, int]]:
        sectors = [s.sector for s in stocks if s.sector]
        return Counter(sectors).most_common(10)

    @staticmethod
    def _get_hot_sectors(stocks: list[SealPlateStock], top_n: int = 10) -> list[str]:
        return [s for s, _ in Counter(
            s.sector for s in stocks if s.sector
        ).most_common(top_n)]

    # ========================
    #  情绪计算（辅助）
    # ========================

    @staticmethod
    def _calculate_sentiment_from_stocks(stocks: list[SealPlateStock]) -> tuple[int, str]:
        """从涨停列表估算市场情绪 — 简化版"""
        if not stocks:
            return 50, "中性"

        n = len(stocks)
        strong_ratio = len([s for s in stocks if s.score >= 70]) / n
        morning_ratio = len([s for s in stocks if s.is_morning_seal]) / n
        first_ratio = len([s for s in stocks if s.plate_type == PlateType.FIRST]) / n

        sentiment = 50
        sentiment += strong_ratio * 25
        sentiment += morning_ratio * 20
        sentiment -= first_ratio * 15

        sentiment = int(min(100, max(0, sentiment)))

        if sentiment >= 70:
            phase = "高潮期"
        elif sentiment >= 40:
            phase = "发酵期"
        elif sentiment >= 20:
            phase = "启动期"
        else:
            phase = "冰点期"

        return sentiment, phase

    # ========================
    #  风险提示
    # ========================

    @staticmethod
    def _generate_warnings(stocks: list[SealPlateStock]) -> list[str]:
        warnings: list[str] = []
        n = len(stocks)

        if n > 150:
            warnings.append(f"涨停家数过多({n}只)，警惕情绪高潮")

        broken = [s for s in stocks if s.seal_strength == SealStrength.BROKEN]
        broken_rate = len(broken) / n if n else 0
        if broken_rate > 0.3:
            warnings.append(f"炸板率偏高({len(broken)}/{n}，{broken_rate:.0%})，封板资金谨慎")

        first = [s for s in stocks if s.plate_type == PlateType.FIRST]
        first_rate = len(first) / n if n else 0
        if first_rate > 0.5:
            warnings.append(f"一字板过多({len(first)}只)，接力难度大")

        three_plus = [s for s in stocks if s.consecutive_days >= 3]
        if three_plus:
            warnings.append(f"三板以上共{len(three_plus)}只，高波动风险")

        return warnings

    # ========================
    #  八项标准检查（§5）
    # ========================

    def _check_eight_standards_on_stock(
        self, stock: SealPlateStock, hot_sectors: list[str]
    ) -> dict:
        """对单股执行八项标准检查，返回通过/未通过统计"""
        passed = 0
        failed = 0

        # 1. 流通市值 (用 amount 粗略估算，数据不可用时放行)
        market_cap = getattr(stock, "market_cap", None)
        if market_cap is not None:
            if 30 <= market_cap <= 150:
                passed += 1
            else:
                failed += 1
        else:
            passed += 1  # 无数据 → 放行

        # 2. 换手率: 5%-20%
        if 5 <= stock.turnover_rate <= 20:
            passed += 1
        else:
            failed += 1

        # 3. 量能比
        volume_ratio = getattr(stock, "volume_ratio", None)
        if volume_ratio is not None:
            if volume_ratio >= 1.5:
                passed += 1
            else:
                failed += 1
        else:
            passed += 1  # 无数据 → 放行

        # 4. 封板时间: 10:30 前
        if stock.is_morning_seal:
            passed += 1
        else:
            failed += 1

        # 5. 开板次数: ≤ 1
        if stock.open_count <= 1:
            passed += 1
        else:
            failed += 1

        # 6. 封单金额: > 流通市值 1% (粗略用 5000万 阈值)
        if stock.seal_amount >= 5000:
            passed += 1
        else:
            failed += 1

        # 7. 题材热度: 属于热点 TOP10
        if stock.sector and stock.sector in hot_sectors:
            passed += 1
        else:
            failed += 1

        # 8. 股价位置: 首板或平台突破 (无历史数据时放行)
        if stock.is_first_board:
            passed += 1
        else:
            failed += 1

        return {"pass_count": passed, "fail_count": failed}

    def check_eight_standards(
        self, stock: SealPlateStock, hot_sectors: list[str] | None = None
    ) -> dict[str, EightStandardCheck]:
        """对单股执行八项标准检查（详细版，返回每项结果）"""
        hot_sectors = hot_sectors or []
        checks: dict[str, EightStandardCheck] = {}

        # 1. 流通市值
        market_cap = getattr(stock, "market_cap", None)
        cfg = self.EIGHT_STANDARDS["market_cap"]
        if market_cap is not None:
            ok = cfg["min"] <= market_cap <= cfg["max"]
            checks["market_cap"] = EightStandardCheck(
                name=cfg["name"], description=cfg["desc"],
                actual_value=f"{market_cap}亿", expected_range=f"{cfg['min']}亿-{cfg['max']}亿",
                passed=ok, score=cfg["weight"] if ok else 0, weight=cfg["weight"] / 100,
            )
        else:
            checks["market_cap"] = EightStandardCheck(
                name=cfg["name"], description=cfg["desc"],
                actual_value="数据不可用", expected_range=f"{cfg['min']}亿-{cfg['max']}亿",
                passed=True, score=cfg["weight"], weight=cfg["weight"] / 100,
            )

        # 2. 换手率
        cfg = self.EIGHT_STANDARDS["turnover_rate"]
        ok = cfg["min"] <= stock.turnover_rate <= cfg["max"]
        checks["turnover_rate"] = EightStandardCheck(
            name=cfg["name"], description=cfg["desc"],
            actual_value=f"{stock.turnover_rate:.2f}%", expected_range=f"{cfg['min']}%-{cfg['max']}%",
            passed=ok, score=cfg["weight"] if ok else (10 if stock.turnover_rate < 5 else 5),
            weight=cfg["weight"] / 100,
        )

        # 3. 量能比
        cfg = self.EIGHT_STANDARDS["volume_ratio"]
        volume_ratio = getattr(stock, "volume_ratio", None)
        if volume_ratio is not None:
            ok = volume_ratio >= cfg["min"]
            checks["volume_ratio"] = EightStandardCheck(
                name=cfg["name"], description=cfg["desc"],
                actual_value=f"{volume_ratio:.1f}倍", expected_range=f">{cfg['min']}倍",
                passed=ok, score=cfg["weight"] if ok else 0, weight=cfg["weight"] / 100,
            )
        else:
            checks["volume_ratio"] = EightStandardCheck(
                name=cfg["name"], description=cfg["desc"],
                actual_value="数据不可用", expected_range=f">{cfg['min']}倍",
                passed=True, score=cfg["weight"], weight=cfg["weight"] / 100,
            )

        # 4. 封板时间
        cfg = self.EIGHT_STANDARDS["seal_time"]
        if stock.seal_time:
            try:
                t = datetime.strptime(stock.seal_time, "%H:%M:%S").time()
                ok = t.hour < cfg["hour"] or (t.hour == cfg["hour"] and t.minute <= cfg["minute"])
            except ValueError:
                ok = True
        else:
            ok = True
        checks["seal_time"] = EightStandardCheck(
            name=cfg["name"], description=cfg["desc"],
            actual_value=stock.seal_time or "未知", expected_range=f"<{cfg['hour']}:{cfg['minute']:02d}",
            passed=ok, score=cfg["weight"] if ok else 8, weight=cfg["weight"] / 100,
        )

        # 5. 开板次数
        cfg = self.EIGHT_STANDARDS["open_count"]
        ok = stock.open_count <= cfg["max"]
        checks["open_count"] = EightStandardCheck(
            name=cfg["name"], description=cfg["desc"],
            actual_value=f"{stock.open_count}次", expected_range=f"≤{cfg['max']}次",
            passed=ok, score=cfg["weight"] if stock.open_count == 0 else (7 if ok else 0),
            weight=cfg["weight"] / 100,
        )

        # 6. 封单金额
        cfg = self.EIGHT_STANDARDS["seal_amount_ratio"]
        ok = stock.seal_amount >= 5000
        checks["seal_amount_ratio"] = EightStandardCheck(
            name=cfg["name"], description=cfg["desc"],
            actual_value=f"{stock.seal_amount:.0f}万", expected_range=">5000万(估算1%)",
            passed=ok, score=cfg["weight"] if ok else 0, weight=cfg["weight"] / 100,
        )

        # 7. 题材热度
        cfg = self.EIGHT_STANDARDS["sector_hot"]
        sector_in_hot = bool(hot_sectors and stock.sector in hot_sectors)
        checks["sector_hot"] = EightStandardCheck(
            name=cfg["name"], description=cfg["desc"],
            actual_value=stock.sector or "未分类", expected_range="热点题材TOP10",
            passed=sector_in_hot, score=cfg["weight"] if sector_in_hot else 3,
            weight=cfg["weight"] / 100,
        )

        # 8. 股价位置
        cfg = self.EIGHT_STANDARDS["position"]
        checks["position"] = EightStandardCheck(
            name=cfg["name"], description=cfg["desc"],
            actual_value="首板" if stock.is_first_board else f"{stock.consecutive_days}连板",
            expected_range="首板/突破",
            passed=stock.is_first_board, score=cfg["weight"] if stock.is_first_board else 0,
            weight=cfg["weight"] / 100,
        )

        return checks

    def calculate_eight_standard_score(
        self, stock: SealPlateStock, hot_sectors: list[str] | None = None
    ) -> tuple[int, dict[str, EightStandardCheck]]:
        """计算八项标准综合评分"""
        checks = self.check_eight_standards(stock, hot_sectors)
        total = sum(c.score for c in checks.values())
        return total, checks

    def get_high_risk_stocks(
        self, stocks: list[SealPlateStock], hot_sectors: list[str] | None = None
    ) -> list[dict]:
        """识别高风险股票 — 架构文档 §5.2"""
        high_risk: list[dict] = []
        hot_sectors = hot_sectors or []

        for stock in stocks:
            checks = self.check_eight_standards(stock, hot_sectors)
            fail_count = sum(1 for c in checks.values() if not c.passed)
            if fail_count >= 3:
                failed_items = [c.name for c in checks.values() if not c.passed]
                high_risk.append({
                    "stock": stock,
                    "failed_count": fail_count,
                    "failed_items": failed_items,
                    "risk_level": "red" if fail_count >= 4 else "yellow",
                })

        return sorted(high_risk, key=lambda x: x["failed_count"], reverse=True)


# ================================================================
# 情绪周期分析器 — 架构文档 §4
# ================================================================

class SentimentAnalyzer:
    """情绪周期分析器 — 架构文档 §4

    支持多数据源增强:
    - 基础: 涨停/跌停统计数据（来自 AKShare/东方财富）
    - 增强: 同花顺热点概念热度（来自 THS Hotspot）
    - v2: 封板率/赚钱效应/北向资金/连板分布（交易系统升级 Phase 1）

    v2 新增指标 (INDICATOR_WEIGHTS_V2):
    - seal_rate: 封板率 (8%) — 封板数/(封板数+炸板数)，衡量资金信心
    - south_flow: 北向资金 (8%) — 净流入/流出，外资态度
    - connectivity_score: 连板质量 (5%) — 连板分布均匀度，梯队完整性
    - advance_decline_ratio: 赚钱效应 (7%) — 上涨/下跌家数比
    """

    # 10 项市场指标权重 — v2（交易系统升级 Phase 1）
    # 总和 = 1.0
    INDICATOR_WEIGHTS_V2 = {
        "limit_up_count":         0.15,  # 涨停家数
        "limit_down_count":       0.10,  # 跌停家数（反向）
        "max_consecutive":        0.12,  # 连板高度
        "bomb_rate":              0.10,  # 炸板率（反向）
        "avg_premium":            0.10,  # 昨日涨停溢价
        "advance_rate":           0.10,  # 连板晋级率
        "seal_rate":              0.08,  # 封板率（新增）
        "north_flow":             0.08,  # 北向资金净流入（新增）
        "volume_change":          0.05,  # 量能变化
        "connectivity_score":     0.05,  # 连板分布质量（新增）
        "advance_decline_ratio":  0.07,  # 赚钱效应（新增）
    }

    # v1 兼容权重（保持向后兼容）
    INDICATOR_WEIGHTS = INDICATOR_WEIGHTS_V2

    # 六阶段阈值 — v2（新增"分化期"）
    PHASE_THRESHOLDS = {
        "冰点期": (0, 20),
        "修复期": (21, 40),
        "分化期": (41, 55),
        "高潮期": (56, 80),
        "退潮期": (81, 100),  # 需结合历史趋势判定
    }

    # 仓位建议 — v2（根据阶段调整）
    POSITION_RANGES = {
        "冰点期": (0, 10),
        "修复期": (20, 35),
        "分化期": (30, 50),
        "高潮期": (25, 45),
        "退潮期": (0, 15),
    }

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def calculate_sentiment_index(
        self,
        market_data: dict,
        *,
        prev_score: int | None = None,
        use_v2: bool = True,
    ) -> tuple[int, str, dict]:
        """
        计算情绪指数（自动选择 v1/v2）— 架构文档 §4.2

        Args:
            market_data:
                limit_up_count: 涨停家数
                limit_down_count: 跌停家数
                max_consecutive: 最高连板数
                bomb_rate: 炸板率 (0-1)
                avg_premium: 昨日涨停溢价 (%)
                advance_rate: 连板晋级率 (0-1)
                volume_change: 量能变化 (%)
                seal_rate: 封板率 (0-1) — v2新增
                north_flow: 北向资金净流入(亿) — v2新增
                connectivity_distribution: {2板:n, 3板:n, ...} — v2新增
                advance_count: 上涨家数 — v2新增
                decline_count: 下跌家数 — v2新增
                turnover_total: 两市成交额(亿) — v2新增
            prev_score: 前一日情绪指数，用于退潮判定
            use_v2: 是否使用v2增强指标

        Returns:
            (情绪指数 0-100, 周期阶段, 各指标得分)
        """
        if use_v2 and any(k in market_data for k in ("seal_rate", "north_flow", "advance_count")):
            return self._calculate_v2(market_data, prev_score=prev_score)
        return self._calculate_v1(market_data)

    def _calculate_v1(self, market_data: dict) -> tuple[int, str, dict]:
        """v1 计算逻辑 — 向后兼容"""
        scores: dict[str, float] = {}

        lu = market_data.get("limit_up_count", 0)
        scores["涨停家数"] = self._norm(lu, 0, 150) * 100

        ld = market_data.get("limit_down_count", 0)
        scores["跌停家数"] = (1 - self._norm(ld, 0, 50)) * 100

        mh = market_data.get("max_consecutive", 0)
        scores["连板高度"] = self._norm(mh, 1, 10) * 100

        br = market_data.get("bomb_rate", 0)
        scores["炸板率"] = (1 - self._norm(br, 0, 0.5)) * 100

        ap = market_data.get("avg_premium", 0)
        scores["昨日溢价"] = self._norm(ap, -5, 10) * 100

        ar = market_data.get("advance_rate", 0)
        scores["晋级率"] = self._norm(ar, 0, 1) * 100

        vc = market_data.get("volume_change", 0)
        scores["量能变化"] = self._norm(vc, -30, 50) * 100

        # 兼容旧权重（7项 -> 重新归一化到1.0）
        legacy_weights = {k: self.INDICATOR_WEIGHTS_V2.get(k, 0) for k in [
            "limit_up_count", "limit_down_count", "max_consecutive",
            "bomb_rate", "avg_premium", "advance_rate", "volume_change",
        ]}
        weight_sum = sum(legacy_weights.values()) or 1.0
        total = 0.0
        total += scores["涨停家数"] * legacy_weights["limit_up_count"] / weight_sum
        total += scores["跌停家数"] * legacy_weights["limit_down_count"] / weight_sum
        total += scores["连板高度"] * legacy_weights["max_consecutive"] / weight_sum
        total += scores["炸板率"] * legacy_weights["bomb_rate"] / weight_sum
        total += scores["昨日溢价"] * legacy_weights["avg_premium"] / weight_sum
        total += scores["晋级率"] * legacy_weights["advance_rate"] / weight_sum
        total += scores["量能变化"] * legacy_weights["volume_change"] / weight_sum

        total = min(100, max(0, int(total)))
        phase = self._get_phase(total)
        return total, phase, {k: int(v) for k, v in scores.items()}

    def _calculate_v2(
        self, market_data: dict, *, prev_score: int | None = None
    ) -> tuple[int, str, dict]:
        """v2 增强计算 — 10项指标加权"""
        scores: dict[str, float] = {}

        # 1. 涨停家数 (15%)
        lu = market_data.get("limit_up_count", 0)
        scores["涨停家数"] = self._norm(lu, 0, 150) * 100

        # 2. 跌停家数 (10%, 反向)
        ld = market_data.get("limit_down_count", 0)
        scores["跌停家数"] = (1 - self._norm(ld, 0, 50)) * 100

        # 3. 连板高度 (12%)
        mh = market_data.get("max_consecutive", 0)
        scores["连板高度"] = self._norm(mh, 1, 10) * 100

        # 4. 炸板率 (10%, 反向)
        br = market_data.get("bomb_rate", 0)
        scores["炸板率"] = (1 - self._norm(br, 0, 0.5)) * 100

        # 5. 昨日涨停溢价 (10%)
        ap = market_data.get("avg_premium", 0)
        scores["昨日溢价"] = self._norm(ap, -5, 10) * 100

        # 6. 连板晋级率 (10%)
        ar = market_data.get("advance_rate", 0)
        scores["晋级率"] = self._norm(ar, 0, 1) * 100

        # 7. 封板率 (8%) — 新增：封板数/总涨停数
        sr = market_data.get("seal_rate")
        if sr is not None:
            scores["封板率"] = self._norm(sr, 0.3, 0.95) * 100
        else:
            # 从 bomb_rate 反推：seal_rate = 1 - bomb_rate * 封板数/涨停数 近似
            lu_count = max(lu, 1)
            bomb_est = br if br > 0 else 0.2
            est_seal = 1.0 - bomb_est
            scores["封板率"] = self._norm(est_seal, 0.3, 0.95) * 100

        # 8. 北向资金 (8%) — 新增：北向资金净流入
        nf = market_data.get("north_flow", 0)  # 亿
        scores["北向资金"] = self._norm(nf, -100, 200) * 100

        # 9. 量能变化 (5%)
        vc = market_data.get("volume_change", 0)
        scores["量能变化"] = self._norm(vc, -30, 50) * 100

        # 10. 连板分布质量 (5%) — 新增：评估梯队完整性
        conn_dist = market_data.get("connectivity_distribution", {})
        scores["连板梯队"] = self._calc_connectivity_score(conn_dist)

        # 11. 赚钱效应 (7%) — 新增：上涨/下跌家数比
        ad_ratio = market_data.get("advance_decline_ratio")
        if ad_ratio is None:
            adv = market_data.get("advance_count", 0)
            dec = market_data.get("decline_count", 1)
            ad_ratio = adv / max(dec, 1)
        scores["赚钱效应"] = self._norm(ad_ratio, 0.3, 5.0) * 100

        # 加权总分
        total = 0.0
        key_map = {
            "涨停家数": "limit_up_count",
            "跌停家数": "limit_down_count",
            "连板高度": "max_consecutive",
            "炸板率": "bomb_rate",
            "昨日溢价": "avg_premium",
            "晋级率": "advance_rate",
            "封板率": "seal_rate",
            "北向资金": "north_flow",
            "量能变化": "volume_change",
            "连板梯队": "connectivity_score",
            "赚钱效应": "advance_decline_ratio",
        }
        for label, key in key_map.items():
            if label in scores:
                total += scores[label] * self.INDICATOR_WEIGHTS_V2.get(key, 0)

        total = min(100, max(0, int(total)))
        phase = self._get_phase_v2(total, prev_score=prev_score)

        return total, phase, {k: int(v) for k, v in scores.items()}

    def _calc_connectivity_score(self, conn_dist: dict) -> float:
        """计算连板梯队质量分数 (0-100)"""
        if not conn_dist:
            return 50.0  # 无数据 → 中性
        # 理想梯队：2板最多，3板次之，4板以上递减
        # 有2板+3板→60分，有4板→+15，有5板→+15，有6板以上→+10
        score = 50.0
        has_2 = conn_dist.get(2, 0) > 0
        has_3 = conn_dist.get(3, 0) > 0
        has_4 = conn_dist.get(4, 0) > 0
        has_5 = conn_dist.get(5, 0) > 0
        has_6plus = sum(v for k, v in conn_dist.items() if k >= 6) > 0

        if has_2 and has_3:
            score += 15  # 有2-3板梯队，基本完整
        if has_4:
            score += 12
        if has_5:
            score += 10
        if has_6plus:
            # 高位连板多 → 可能过热
            score += 5
        if not has_2:
            score -= 10  # 无2板 → 梯队断裂
        if not has_3 and not has_4:
            score -= 10  # 缺乏中位连板

        return min(100, max(0, score))

    @staticmethod
    def _norm(value: float, min_val: float, max_val: float) -> float:
        """归一化到 [0, 1]"""
        if max_val == min_val:
            return 0.5
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))

    @classmethod
    def _get_phase(cls, score: int) -> str:
        """根据指数判定阶段（v1兼容）"""
        for phase, (lo, hi) in cls.PHASE_THRESHOLDS.items():
            if lo <= score <= hi:
                return phase
        return "分化期"

    @classmethod
    def _get_phase_v2(cls, score: int, *, prev_score: int | None = None) -> str:
        """v2 阶段判定 — 结合历史趋势识别退潮"""
        # 基础判定
        phase = cls._get_phase(score)

        # 退潮判定：需要从前一日高位回落
        if phase == "退潮期" and prev_score is not None:
            if prev_score >= 56:  # 前一日在高潮或以上
                return "退潮期"
            # 如果前一日不在高位，可能实际只是低分，归类为冰点
            return "冰点期"

        # 如果前一日在高潮期(≥56)且今日降到分化(41-55)，可能是退潮预警
        if phase == "分化期" and prev_score is not None and prev_score >= 56:
            # 高位回落超过15个点 → 退潮确认
            if prev_score - score >= 15:
                return "退潮期"

        return phase

    def get_sentiment_report(self, market_data: dict, *, prev_score: int | None = None) -> dict:
        """生成完整情绪分析报告（供前端/通知使用）

        Returns:
            {
                "score": 情绪指数 0-100,
                "phase": 周期阶段,
                "phase_icon": 阶段图标,
                "indicator_scores": {指标名: 得分},
                "position_suggestion": 仓位建议dict,
                "market_heat": "过冷/偏冷/适中/偏热/过热",
                "key_signals": [关键信号描述],
                "risk_level": "low/medium/high/extreme",
                "summary": 一句话总结,
            }
        """
        score, phase, scores = self.calculate_sentiment_index(
            market_data, prev_score=prev_score, use_v2=True
        )
        position = self.get_position_suggestion(score)

        # 市场热度
        if score <= 20:
            heat = "过冷"
            risk = "low"
        elif score <= 40:
            heat = "偏冷"
            risk = "low"
        elif score <= 55:
            heat = "适中"
            risk = "medium"
        elif score <= 75:
            heat = "偏热"
            risk = "medium"
        else:
            heat = "过热"
            risk = "high"

        # 关键信号
        signals = self._extract_key_signals(scores, phase, market_data)

        # 阶段图标
        phase_icons = {
            "冰点期": "❄️", "修复期": "🌱", "分化期": "⚡",
            "高潮期": "🔥", "退潮期": "📉",
        }

        return {
            "score": score,
            "phase": phase,
            "phase_icon": phase_icons.get(phase, "❓"),
            "indicator_scores": scores,
            "position_suggestion": position,
            "market_heat": heat,
            "risk_level": risk,
            "key_signals": signals,
            "summary": self._generate_summary(score, phase, heat, position),
        }

    def _extract_key_signals(self, scores: dict, phase: str, market_data: dict) -> list[str]:
        """提取关键情绪信号"""
        signals: list[str] = []
        # 涨停信号
        if scores.get("涨停家数", 0) >= 80:
            signals.append("涨停家数活跃(≥80)，市场做多热情高涨")
        elif scores.get("涨停家数", 0) <= 20:
            signals.append("涨停家数低迷(≤20)，观望情绪浓厚")
        # 炸板信号
        if scores.get("炸板率", 100) <= 30:
            signals.append("炸板率偏高，封板资金信心不足")
        # 连板信号
        if scores.get("连板高度", 0) >= 80:
            signals.append(f"空间板高度充足({market_data.get('max_consecutive', '?')}板)")
        # 北向资金
        nf = market_data.get("north_flow", 0)
        if nf >= 50:
            signals.append(f"北向大幅净流入 {nf:.1f}亿")
        elif nf <= -30:
            signals.append(f"北向净流出 {abs(nf):.1f}亿")
        # 赚钱效应
        if scores.get("赚钱效应", 50) >= 75:
            signals.append("赚钱效应强，普涨格局")
        elif scores.get("赚钱效应", 50) <= 25:
            signals.append("赚钱效应弱，亏钱效应明显")
        # 封板率
        if scores.get("封板率", 50) >= 80:
            signals.append("封板率高，打板环境友好")
        return signals

    @staticmethod
    def _generate_summary(score: int, phase: str, heat: str, position: dict) -> str:
        phase_summaries = {
            "冰点期": "市场极度低迷，建议空仓等待，仅极小仓位试错首板",
            "修复期": "情绪逐步回暖，可轻仓参与低位首板和修复机会",
            "分化期": "板块轮动加快，聚焦主线龙头，控制仓位",
            "高潮期": "赚钱效应扩散但风险积聚，逐步兑现利润，不宜追高",
            "退潮期": "高位股杀跌，果断减仓/清仓，保护利润",
        }
        base = phase_summaries.get(phase, "观望为主")
        pos = position.get("position_range", "0%")
        return f"[{heat}] {base}。建议仓位: {pos}"

    def enhance_with_hotspot(
        self, sentiment_data: dict, hotspot_data: Optional[dict] = None
    ) -> dict:
        """
        使用同花顺热点数据增强情绪分析

        Args:
            sentiment_data: 原有的情绪分析结果
            hotspot_data: 来自 THSHotspotFetcher.get_market_hot_analysis()

        Returns:
            增强后的情绪分析结果
        """
        if not hotspot_data:
            return sentiment_data

        enhanced = dict(sentiment_data)

        hot_concepts = hotspot_data.get("hot_concepts", [])
        concept_count = len(hot_concepts)
        enhanced["hot_concepts_count"] = concept_count

        fund_inflow = hotspot_data.get("fund_inflow_sectors", [])
        total_inflow = sum(f.get("net_inflow", 0) for f in fund_inflow)
        enhanced["fund_inflow_intensity"] = total_inflow

        market_heat = hotspot_data.get("market_heat_score", 50)
        enhanced["market_heat_score"] = market_heat
        enhanced["sentiment_signal"] = hotspot_data.get("sentiment_signal", "neutral")

        top_concepts = [c["name"] for c in hot_concepts[:3]]
        enhanced["top_hot_concepts"] = top_concepts

        return enhanced

    def get_position_suggestion(self, score: int, risk_preference: str = "稳健") -> dict:
        """
        仓位建议 — 架构文档 §2.2

        Args:
            score: 情绪指数
            risk_preference: 保守/稳健/激进
        """
        phase = self._get_phase(score)
        min_pct, max_pct = self.POSITION_RANGES.get(phase, (20, 40))

        adj = {"保守": -20, "稳健": 0, "激进": 20}.get(risk_preference, 0)
        suggested_min = max(0, min_pct + adj)
        suggested_max = min(100, max_pct + adj)

        return {
            "phase": phase,
            "sentiment_score": score,
            "suggested_position": (suggested_min + suggested_max) // 2,
            "position_range": f"{suggested_min}%-{suggested_max}%",
            "strategy": self._get_strategy(phase),
            "warning": self._get_warning(phase, score),
        }

    @staticmethod
    def _get_strategy(phase: str) -> str:
        return {
            "冰点期": "空仓休息，极小仓位试错首板。关注逆势抗跌标的",
            "修复期": "轻仓试错空间板、首板一进二。关注率先修复的板块",
            "分化期": "聚焦主线龙头，去弱留强。板块轮动中高抛低吸",
            "高潮期": "逐步卖出，兑现利润。新开仓比例降低，不追加速板",
            "退潮期": "果断空仓/轻仓，不接飞刀。耐心等待冰点信号",
        }.get(phase, "观望为主，等待明确信号")

    @staticmethod
    def _get_warning(phase: str, score: int) -> str | None:
        if phase == "高潮期" and score >= 75:
            return "⚠️ 情绪过热，建议逐步减仓至30%以下"
        if phase == "退潮期":
            return "🔴 情绪退潮确认，强烈建议空仓/轻仓(≤15%)"
        if phase == "冰点期" and score <= 10:
            return "❄️ 市场极度冰点，耐心等待修复信号"
        if phase == "分化期" and score <= 48:
            return "⚡ 分化加剧，去弱留强，控制单票仓位≤20%"
        return None
