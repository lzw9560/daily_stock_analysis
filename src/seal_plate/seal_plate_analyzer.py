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
    """

    # 7 项市场指标权重 — 架构文档 §4.2
    INDICATOR_WEIGHTS = {
        "limit_up_count":   0.20,   # 涨停家数
        "limit_down_count": 0.15,   # 跌停家数（反向）
        "max_consecutive":  0.15,   # 连板高度
        "bomb_rate":        0.15,   # 炸板率（反向）
        "avg_premium":      0.15,   # 昨日涨停溢价
        "advance_rate":     0.15,   # 连板晋级率
        "volume_change":    0.05,   # 量能变化
    }

    # 五阶段阈值 — 架构文档 §4.3
    PHASE_THRESHOLDS = {
        "冰点期": (0, 20),
        "启动期": (21, 40),
        "发酵期": (41, 60),
        "高潮期": (61, 80),
        "退潮期": (81, 100),  # 实际退潮由高位回落判定
    }

    # 仓位建议 — 架构文档 §2.2
    POSITION_RANGES = {
        "冰点期": (0, 10),
        "启动期": (20, 30),
        "发酵期": (50, 70),
        "高潮期": (30, 50),
        "退潮期": (0, 10),
    }

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def calculate_sentiment_index(self, market_data: dict) -> tuple[int, str, dict]:
        """
        计算情绪指数 — 架构文档 §4.2

        Args:
            market_data:
                limit_up_count: 涨停家数
                limit_down_count: 跌停家数
                max_consecutive: 最高连板数
                bomb_rate: 炸板率 (0-1)
                avg_premium: 昨日涨停溢价 (%)
                advance_rate: 连板晋级率 (0-1)
                volume_change: 量能变化 (%)

        Returns:
            (情绪指数 0-100, 周期阶段, 各指标得分)
        """
        scores: dict[str, float] = {}

        # 1. 涨停家数 (20%)
        lu = market_data.get("limit_up_count", 0)
        scores["涨停家数"] = self._norm(lu, 0, 150) * 100

        # 2. 跌停家数 (15%, 反向)
        ld = market_data.get("limit_down_count", 0)
        scores["跌停家数"] = (1 - self._norm(ld, 0, 50)) * 100

        # 3. 连板高度 (15%)
        mh = market_data.get("max_consecutive", 0)
        scores["连板高度"] = self._norm(mh, 1, 10) * 100

        # 4. 炸板率 (15%, 反向)
        br = market_data.get("bomb_rate", 0)
        scores["炸板率"] = (1 - self._norm(br, 0, 0.5)) * 100

        # 5. 昨日涨停溢价 (15%)
        ap = market_data.get("avg_premium", 0)
        scores["昨日溢价"] = self._norm(ap, -5, 10) * 100

        # 6. 连板晋级率 (15%)
        ar = market_data.get("advance_rate", 0)
        scores["晋级率"] = self._norm(ar, 0, 1) * 100

        # 7. 量能变化 (5%)
        vc = market_data.get("volume_change", 0)
        scores["量能变化"] = self._norm(vc, -30, 50) * 100

        # 加权总分
        total = 0.0
        total += scores["涨停家数"]   * self.INDICATOR_WEIGHTS["limit_up_count"]
        total += scores["跌停家数"]   * self.INDICATOR_WEIGHTS["limit_down_count"]
        total += scores["连板高度"]   * self.INDICATOR_WEIGHTS["max_consecutive"]
        total += scores["炸板率"]     * self.INDICATOR_WEIGHTS["bomb_rate"]
        total += scores["昨日溢价"]   * self.INDICATOR_WEIGHTS["avg_premium"]
        total += scores["晋级率"]     * self.INDICATOR_WEIGHTS["advance_rate"]
        total += scores["量能变化"]   * self.INDICATOR_WEIGHTS["volume_change"]

        total = min(100, max(0, int(total)))
        phase = self._get_phase(total)

        return total, phase, {k: int(v) for k, v in scores.items()}

    @staticmethod
    def _norm(value: float, min_val: float, max_val: float) -> float:
        """归一化到 [0, 1]"""
        if max_val == min_val:
            return 0.5
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))

    @classmethod
    def _get_phase(cls, score: int) -> str:
        """根据指数判定阶段"""
        for phase, (lo, hi) in cls.PHASE_THRESHOLDS.items():
            if lo <= score <= hi:
                return phase
        return "中性"

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
            "冰点期": "空仓休息，极小仓位试错首板",
            "启动期": "试错参与空间板、首板一进二",
            "发酵期": "积极参与总龙头和核心股",
            "高潮期": "逐步卖出，兑现利润，不追高",
            "退潮期": "果断空仓，不接飞刀",
        }.get(phase, "观望")

    @staticmethod
    def _get_warning(phase: str, score: int) -> str | None:
        if phase == "高潮期" and score >= 75:
            return "⚠️ 情绪过热，建议逐步减仓"
        if phase == "退潮期":
            return "🔴 情绪退潮，强烈建议空仓"
        if phase == "冰点期" and score <= 10:
            return "❄️ 市场冰点，耐心等待机会"
        return None
