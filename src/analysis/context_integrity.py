# -*- coding: utf-8 -*-
"""
===================================
Analysis Context Integrity Module
===================================

职责：
1. 检测报告中脱离上下文的孤立数据引用（OrphanedCitationDetector）
2. 自动补全缺失的关联上下文（auto_complete_citation_context）
3. 上下文完整性校验（validate_context_integrity）
4. 综合推荐数据状态校验（validate_comprehensive_data）

确保报告具备完整的数据溯源链路，避免孤立引用导致的信息断裂。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
#  Data Models
# ============================================================

@dataclass
class CitationNode:
    """报告中的数据引用节点"""
    field: str                          # 引用的字段路径，如 "analysis_summary"
    content: str                        # 引用内容
    referenced_source: List[str] = field(default_factory=list)  # 引用的数据源key
    has_context: bool = True            # 是否有完整上下文
    missing_context_reason: str = ""    # 缺失原因


@dataclass
class ContextIntegrityReport:
    """上下文完整性检测报告"""
    is_complete: bool = True
    orphaned_nodes: List[CitationNode] = field(default_factory=list)
    fixed_nodes: List[CitationNode] = field(default_factory=list)
    total_checks: int = 0
    passed_checks: int = 0
    data_quality_score: float = 100.0    # 0-100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_complete": self.is_complete,
            "orphaned_count": len(self.orphaned_nodes),
            "fixed_count": len(self.fixed_nodes),
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "data_quality_score": self.data_quality_score,
            "orphaned_fields": [
                {"field": n.field, "reason": n.missing_context_reason}
                for n in self.orphaned_nodes
            ],
        }


# ============================================================
#  Citation context patterns — 需要数据支持的论述关键词
# ============================================================

CITATION_PATTERNS = [
    # 价格引用
    (r'(?:当前|现价|最新价|收盘价)[\s:：]?(?:约|大约|在|为)?[\s]?(\d+\.?\d*)', "quote.price"),
    (r'(?:均价|平均成本|持仓成本)[\s:：]?(?:约|大约|在|为)?[\s]?(\d+\.?\d*)', "chip.avg_cost"),
    (r'MA\d+\s*[均线]?\s*(?:位于|在|为|处于)?\s*(\d+\.?\d*)', "technical.ma"),
    (r'(?:支撑位|支撑|底部)[\s:：]?(?:约|大约|在|为)?[\s]?(\d+\.?\d*)', "technical.support"),
    (r'(?:压力位|阻力位|顶部)[\s:：]?(?:约|大约|在|为)?[\s]?(\d+\.?\d*)', "technical.resistance"),

    # 技术指标引用
    (r'换手率[\s:：]?(?:约|大约|为)?[\s]?(\d+\.?\d*)%', "quote.turnover"),
    (r'(?:成交量|量能|放量|缩量)', "volume"),
    (r'RSI\s*(?:值|指标)?[\s:：]?(?:约|大约|为)?[\s]?(\d+\.?\d*)', "technical.rsi"),
    (r'MACD[\s]*(?:金叉|死叉|背离)', "technical.macd"),
    (r'KDJ[\s]*(?:金叉|死叉|超买|超卖)', "technical.kdj"),
    (r'(?:布林|BOLL)[\s]*(?:上轨|中轨|下轨)', "technical.boll"),

    # 新闻/消息引用
    (r'(?:据报道|消息称|新闻显示|公告|财报|季报|年报)', "news"),
    (r'(?:净利润|营收|ROE|PE|PB|估值)[\s:：]?(?:约|大约|为)?[\s]?(\d+\.?\d*)', "fundamentals"),
    (r'(?:游资|机构|北向资金|主力|大单)', "fund_flow"),

    # 板块引用
    (r'(?:板块|行业|概念)[\s:：]?(?:属于|归属|是)?[\s]?[\u4e00-\u9fff]+', "sector"),
]

# 数据源 → 需要检查的引用模式索引
SOURCE_PATTERN_MAP: Dict[str, List[int]] = {
    "quote": [0, 1, 5],
    "chip": [1],
    "technical": [2, 3, 4, 6, 7, 8, 9],
    "news": [10],
    "fundamentals": [11],
    "fund_flow": [12],
    "sector": [13],
}


# ============================================================
#  Orphaned Citation Detector
# ============================================================

class OrphanedCitationDetector:
    """检测报告中脱离上下文的孤立数据引用"""

    def __init__(self, available_sources: Optional[List[str]] = None):
        """
        Args:
            available_sources: 可用的数据源列表，如 ["quote", "technical", "news"]
        """
        self.available_sources = available_sources or []

    def detect(self, field_content_map: Dict[str, str]) -> List[CitationNode]:
        """
        检测所有字段中的孤立引用

        Args:
            field_content_map: {field_path: content_text} 映射

        Returns:
            孤立引用节点列表
        """
        orphaned: List[CitationNode] = []

        for field, content in field_content_map.items():
            if not content or not isinstance(content, str):
                continue

            nodes = self._detect_or_phans_in_text(field, content)
            orphaned.extend(nodes)

        return orphaned

    def _detect_or_phans_in_text(self, field: str, text: str) -> List[CitationNode]:
        """在单段文本中检测孤立引用"""
        orphaned: List[CitationNode] = []

        for pattern, source_key in CITATION_PATTERNS:
            matches = re.findall(pattern, text)
            if not matches:
                continue

            # 检查对应的数据源是否可用
            base_source = source_key.split(".")[0]  # technical.ma → technical
            if base_source in self.available_sources:
                continue  # 数据源可用，不算孤立

            # 检查是否有替代数据源可用
            if self._has_alternative_source(source_key):
                continue

            node = CitationNode(
                field=field,
                content=text[:200],
                referenced_source=[source_key],
                has_context=False,
                missing_context_reason=f"引用数据源 {source_key} 不可用，"
                                      f"可用数据源: {self.available_sources}",
            )
            orphaned.append(node)

        return orphaned

    def _has_alternative_source(self, source_key: str) -> bool:
        """检查是否有替代数据源可以提供类似信息"""
        base = source_key.split(".")[0]
        alternatives = {
            "technical": ["quote", "chip"],
            "chip": ["quote"],
            "fundamentals": ["news"],
            "news": ["fundamentals"],
            "fund_flow": ["quote"],
            "volume": ["quote"],
            "sector": ["news"],
        }
        # 注意: 专用技术指标（如MACD/RSI/KDJ）被quote替代后，
        # 在orphaned检测中算作具有替代源，不再标记为孤立引用。
        # 但补全质量依赖于实际可用的quote数据。如有完整技术数据源可用则不需要替代。
        for alt in alternatives.get(base, []):
            if alt in self.available_sources:
                return True
        return False


# ============================================================
#  Auto Context Completion
# ============================================================

class ContextCompleter:
    """自动补全缺失的关联上下文"""

    @staticmethod
    def complete_orphaned_nodes(
        nodes: List[CitationNode],
        available_data: Dict[str, Any],
    ) -> Tuple[List[CitationNode], List[CitationNode]]:
        """
        尝试补全孤立节点的上下文

        Args:
            nodes: 检测出的孤立节点
            available_data: 可用的数据 {source_key: data}

        Returns:
            (fixed_nodes, still_orphaned) — 修复的节点和仍然孤立的节点
        """
        fixed: List[CitationNode] = []
        still_orphaned: List[CitationNode] = []

        for node in nodes:
            completed = False
            for source_key in node.referenced_source:
                base = source_key.split(".")[0]
                if base in available_data and available_data[base] is not None:
                    node.has_context = True
                    node.missing_context_reason = ""
                    node.referenced_source.append(
                        f"{base}(auto-completed from {available_data[base]})"
                    )
                    fixed.append(node)
                    completed = True
                    break

            if not completed:
                still_orphaned.append(node)

        return fixed, still_orphaned


# ============================================================
#  Main Integrity Validation
# ============================================================

def validate_context_integrity(
    field_content_map: Dict[str, str],
    available_sources: List[str],
    available_data: Optional[Dict[str, Any]] = None,
) -> ContextIntegrityReport:
    """
    完整的上下文完整性校验

    Args:
        field_content_map: 各字段的文本内容
        available_sources: 可用的数据源列表
        available_data: 可用的实际数据（用于自动补全）

    Returns:
        ContextIntegrityReport
    """
    report = ContextIntegrityReport()

    # Step 1: 检测孤立引用
    detector = OrphanedCitationDetector(available_sources)
    orphaned = detector.detect(field_content_map)
    report.total_checks = len(field_content_map)

    if not orphaned:
        report.passed_checks = report.total_checks
        report.data_quality_score = 100.0
        return report

    # Step 2: 尝试自动补全
    completer = ContextCompleter()
    fixed, still_orphaned = completer.complete_orphaned_nodes(
        orphaned, available_data or {},
    )

    report.fixed_nodes = fixed
    report.orphaned_nodes = still_orphaned
    report.is_complete = len(still_orphaned) == 0
    report.passed_checks = report.total_checks - len(still_orphaned)

    # Step 3: 计算质量分
    if report.total_checks > 0:
        report.data_quality_score = round(
            (report.passed_checks / report.total_checks) * 100, 1
        )

    logger.info(
        "Context integrity check: %d checks, %d passed, %d orphaned, %d fixed",
        report.total_checks, report.passed_checks,
        len(report.orphaned_nodes), len(report.fixed_nodes),
    )

    return report


# ============================================================
#  Comprehensive Recommendation Data Validation
# ============================================================

@dataclass
class ComprehensiveDataValidation:
    """综合推荐数据校验结果"""
    is_valid: bool
    issues: List[Dict[str, str]] = field(default_factory=list)
    fixed: List[Dict[str, str]] = field(default_factory=list)


def validate_comprehensive_data(data: Dict[str, Any]) -> ComprehensiveDataValidation:
    """
    验证综合推荐数据的完整性，检查可能引起前端渲染异常的问题

    校验项:
    1. 必填字段是否存在
    2. 数组字段是否为list类型
    3. 数值字段范围是否合理
    4. 可选字段的null安全
    """
    issues: List[Dict[str, str]] = []
    fixed: List[Dict[str, str]] = []

    # Required top-level fields
    required_fields = [
        "date", "label", "sentiment_index", "sentiment_phase",
        "total_limit_up", "market_heat_score", "fund_sentiment",
    ]
    for field in required_fields:
        if field not in data or data[field] is None:
            issues.append({"field": field, "issue": "missing_required", "severity": "warning"})
            # Auto-fix with defaults
            fix_value = _get_default_for_field(field)
            if fix_value is not None:
                data[field] = fix_value
                fixed.append({"field": field, "action": f"set_default={fix_value}"})

    # Array fields must be list
    array_fields = [
        "buy_sell_analyses", "term_advices", "individual_stock_risks",
        "factor_correlations", "stress_test_results",
        "strategy_adjustments", "adjustment_reasons",
    ]
    for field in array_fields:
        if field in data and not isinstance(data[field], list):
            issues.append({"field": field, "issue": "not_a_list", "severity": "warning"})
            data[field] = []
            fixed.append({"field": field, "action": "reset_to_empty_list"})
        elif field not in data:
            data[field] = []
            fixed.append({"field": field, "action": "init_empty_list"})

    # Numeric range validation
    numeric_ranges = {
        "sentiment_index": (0, 100),
        "market_heat_score": (0, 100),
        "total_limit_up": (0, 10000),
    }
    for field, (min_val, max_val) in numeric_ranges.items():
        if field in data and isinstance(data[field], (int, float)):
            if data[field] < min_val:
                data[field] = min_val
                fixed.append({"field": field, "action": f"clamped_to_min={min_val}"})
            elif data[field] > max_val:
                data[field] = max_val
                fixed.append({"field": field, "action": f"clamped_to_max={max_val}"})

    # Optional fields null-safety: ensure they're at least None not missing
    optional_fields = [
        "sector_rotation", "risk_assessment", "dynamic_position",
        "generated_at", "win_rate_info",
    ]
    for field in optional_fields:
        if field not in data:
            data[field] = None

    # Dynamic position validation (most likely to cause display issues)
    if data.get("dynamic_position") and isinstance(data["dynamic_position"], dict):
        dp = data["dynamic_position"]
        dp_required = [
            "current_position_pct", "target_position_pct",
            "max_position_pct", "cash_reserve_pct", "total_capital",
            "stock_weights",
        ]
        for field in dp_required:
            if field not in dp or dp[field] is None:
                issues.append({
                    "field": f"dynamic_position.{field}",
                    "issue": "missing_in_dynamic_position",
                    "severity": "warning",
                })
                fix_value = _get_dp_default(field)
                if fix_value is not None:
                    dp[field] = fix_value
                    fixed.append({
                        "field": f"dynamic_position.{field}",
                        "action": f"set_default={fix_value}",
                    })

        # Ensure stock_weights is a list
        if not isinstance(dp.get("stock_weights"), list):
            issues.append({"field": "dynamic_position.stock_weights", "issue": "not_a_list", "severity": "error"})
            dp["stock_weights"] = []
            fixed.append({"field": "dynamic_position.stock_weights", "action": "reset_to_empty_list"})

        # Range checks
        for pct_field in ["current_position_pct", "target_position_pct", "max_position_pct", "cash_reserve_pct"]:
            if pct_field in dp and isinstance(dp[pct_field], (int, float)):
                if dp[pct_field] < 0:
                    dp[pct_field] = 0
                    fixed.append({"field": f"dynamic_position.{pct_field}", "action": "clamped_to_0"})
                elif dp[pct_field] > 100:
                    dp[pct_field] = 100
                    fixed.append({"field": f"dynamic_position.{pct_field}", "action": "clamped_to_100"})

        # Logic check: cash_reserve + target_position should ≈ 100
        if isinstance(dp.get("target_position_pct"), (int, float)) and \
           isinstance(dp.get("cash_reserve_pct"), (int, float)):
            if abs(dp["target_position_pct"] + dp["cash_reserve_pct"] - 100) > 1:
                issues.append({
                    "field": "dynamic_position.position_cash_mismatch",
                    "issue": f"target={dp['target_position_pct']}% + cash={dp['cash_reserve_pct']}% ≠ 100%",
                    "severity": "warning",
                })
                # Auto-fix
                dp["cash_reserve_pct"] = 100 - dp["target_position_pct"]
                fixed.append({"field": "dynamic_position.cash_reserve_pct", "action": "auto_corrected"})

    return ComprehensiveDataValidation(
        is_valid=len([i for i in issues if i.get("severity") == "error"]) == 0,
        issues=issues,
        fixed=fixed,
    )


def _get_default_for_field(field: str) -> Any:
    """获取字段的默认值"""
    defaults = {
        "date": "",
        "label": "未知",
        "sentiment_index": 50,
        "sentiment_phase": "中性",
        "total_limit_up": 0,
        "market_heat_score": 50,
        "fund_sentiment": "中性",
    }
    return defaults.get(field)


def _get_dp_default(field: str) -> Any:
    """获取动态仓位的默认值"""
    defaults = {
        "current_position_pct": 0.0,
        "target_position_pct": 30.0,
        "max_position_pct": 50.0,
        "cash_reserve_pct": 70.0,
        "total_capital": 100000.0,
        "stock_weights": [],
    }
    return defaults.get(field)
