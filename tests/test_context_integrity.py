# -*- coding: utf-8 -*-
"""Tests for analysis context integrity module."""

import json
import sys
import unittest
from unittest.mock import MagicMock, patch

from src.analysis.context_integrity import (
    CitationNode,
    ContextCompleter,
    ContextIntegrityReport,
    OrphanedCitationDetector,
    validate_comprehensive_data,
    validate_context_integrity,
    ComprehensiveDataValidation,
)


class TestOrphanedCitationDetector(unittest.TestCase):
    """Orphaned citation detection tests."""

    def test_no_orphans_when_sources_available(self) -> None:
        """No orphans detected when all data sources are available."""
        detector = OrphanedCitationDetector(
            available_sources=["quote", "technical", "news", "fundamentals"]
        )
        field_map = {
            "analysis_summary": "当前价格为25.30元，MACD金叉形成",
        }
        orphans = detector.detect(field_map)
        self.assertEqual(len(orphans), 0)

    def test_technical_not_orphaned_with_quote_alternative(self) -> None:
        """Technical references not orphaned when quote is available as alternative."""
        detector = OrphanedCitationDetector(
            available_sources=["quote", "news"]  # quote serves as technical alt
        )
        field_map = {
            "analysis_summary": "MACD金叉形成，RSI值为65，支撑位在20元",
        }
        orphans = detector.detect(field_map)
        self.assertEqual(len(orphans), 0)

    def test_detects_orphan_when_technical_unavailable(self) -> None:
        """Detects orphaned technical citations when NO alternative sources available."""
        detector = OrphanedCitationDetector(
            available_sources=["news"]  # quote not available, no technical alternative
        )
        field_map = {
            "analysis_summary": "MACD金叉形成，RSI值为65",
        }
        orphans = detector.detect(field_map)
        self.assertGreater(len(orphans), 0)
        self.assertTrue(
            any("MACD" in n.content or "RSI" in n.content for n in orphans)
        )

    def test_no_orphan_with_alternative_source(self) -> None:
        """No orphan when alternative source can provide similar data."""
        detector = OrphanedCitationDetector(
            available_sources=["quote", "chip"]  # chip can alt for technical
        )
        field_map = {
            "analysis_summary": "支撑位位于20.5元，压力位在25元",
        }
        orphans = detector.detect(field_map)
        # technical is unavailable but quote/chip are alternatives
        # so should not be orphaned
        self.assertEqual(len(orphans), 0)

    def test_multiple_fields_detection(self) -> None:
        """Correctly detects orphans across multiple fields when no alternatives."""
        detector = OrphanedCitationDetector(
            available_sources=["news"]  # Only news, no technical/quote alternatives
        )
        field_map = {
            "analysis_summary": "MACD背离信号明显，KDJ超买",
            "key_points": "净利润增长30%，PE估值合理",
        }
        orphans = detector.detect(field_map)
        self.assertGreater(len(orphans), 0)


class TestContextCompleter(unittest.TestCase):
    """Context completion tests."""

    def test_complete_orphans_with_available_data(self) -> None:
        """Successfully completes orphaned nodes when data becomes available."""
        nodes = [
            CitationNode(
                field="analysis_summary",
                content="MACD金叉形成",
                referenced_source=["technical"],
                has_context=False,
                missing_context_reason="technical unavailable",
            ),
        ]
        available_data = {"technical": {"ma5": 25, "ma10": 24}}
        fixed, still_orphaned = ContextCompleter.complete_orphaned_nodes(
            nodes, available_data
        )
        self.assertEqual(len(fixed), 1)
        self.assertEqual(len(still_orphaned), 0)
        self.assertTrue(fixed[0].has_context)

    def test_nodes_remain_orphaned_without_data(self) -> None:
        """Nodes stay orphaned when no complementary data available."""
        nodes = [
            CitationNode(
                field="analysis_summary",
                content="MACD金叉形成",
                referenced_source=["technical"],
                has_context=False,
                missing_context_reason="technical unavailable",
            ),
        ]
        available_data = {"quote": {"price": 25}}  # No technical data
        fixed, still_orphaned = ContextCompleter.complete_orphaned_nodes(
            nodes, available_data
        )
        self.assertEqual(len(fixed), 0)
        self.assertEqual(len(still_orphaned), 1)


class TestValidateContextIntegrity(unittest.TestCase):
    """Main integrity validation tests."""

    def test_all_clear_with_available_sources(self) -> None:
        """Returns complete report when all sources available."""
        report = validate_context_integrity(
            field_content_map={
                "analysis_summary": "当前价格25元，MACD金叉",
                "key_points": "换手率5%，量能放大",
            },
            available_sources=["quote", "technical", "news", "fundamentals"],
        )
        self.assertTrue(report.is_complete)
        self.assertEqual(report.data_quality_score, 100.0)

    def test_detects_orphans_with_limited_sources(self) -> None:
        """Detects orphans when sources are limited."""
        report = validate_context_integrity(
            field_content_map={
                "analysis_summary": "MACD金叉，RSI 65，PE 15倍",
            },
            available_sources=["quote"],
        )
        self.assertFalse(report.is_complete)
        self.assertGreater(len(report.orphaned_nodes), 0)


class TestValidateComprehensiveData(unittest.TestCase):
    """Comprehensive data validation tests."""

    def test_valid_data_passes(self) -> None:
        """Fully valid data passes validation."""
        data = {
            "date": "20260604",
            "label": "周四",
            "sentiment_index": 65,
            "sentiment_phase": "发酵期",
            "total_limit_up": 45,
            "market_heat_score": 70,
            "fund_sentiment": "乐观",
            "buy_sell_analyses": [],
            "term_advices": [],
            "individual_stock_risks": [],
            "factor_correlations": [],
            "stress_test_results": [],
            "strategy_adjustments": [],
            "adjustment_reasons": [],
            "sector_rotation": None,
            "risk_assessment": None,
            "dynamic_position": {
                "total_capital": 100000,
                "current_position_pct": 30,
                "target_position_pct": 30,
                "max_position_pct": 50,
                "cash_reserve_pct": 70,
                "stock_weights": [],
                "adjustment_reason": "",
                "rebalancing_needed": False,
            },
        }
        result = validate_comprehensive_data(data)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.issues), 0)

    def test_fixes_missing_required_fields(self) -> None:
        """Auto-fixes missing required fields."""
        data = {}
        result = validate_comprehensive_data(data)
        self.assertTrue(result.is_valid)  # Should be fixed, not errored
        self.assertIn("date", data)
        self.assertIn("sentiment_index", data)
        self.assertEqual(data["sentiment_index"], 50)

    def test_fixes_non_list_arrays(self) -> None:
        """Fixes array fields that are not lists."""
        data = {
            "date": "20260604",
            "label": "周四",
            "sentiment_index": 50,
            "sentiment_phase": "中性",
            "total_limit_up": 0,
            "market_heat_score": 50,
            "fund_sentiment": "中性",
            "buy_sell_analyses": "not a list",
            "term_advices": "also not a list",
            "individual_stock_risks": None,
        }
        result = validate_comprehensive_data(data)
        self.assertTrue(result.is_valid)
        self.assertIsInstance(data["buy_sell_analyses"], list)
        self.assertIsInstance(data["term_advices"], list)

    def test_clamps_out_of_range_values(self) -> None:
        """Clamps numeric values outside valid range."""
        data = {
            "date": "20260604",
            "label": "周四",
            "sentiment_index": 150,  # should be clamped to 100
            "sentiment_phase": "高潮期",
            "total_limit_up": -5,    # should be clamped to 0
            "market_heat_score": 50,
            "fund_sentiment": "中性",
            "buy_sell_analyses": [],
            "term_advices": [],
            "individual_stock_risks": [],
            "factor_correlations": [],
            "stress_test_results": [],
            "strategy_adjustments": [],
            "adjustment_reasons": [],
        }
        result = validate_comprehensive_data(data)
        self.assertEqual(data["sentiment_index"], 100)
        self.assertEqual(data["total_limit_up"], 0)

    def test_fixes_cash_position_mismatch(self) -> None:
        """Fixes cash reserve + target position mismatch."""
        data = {
            "date": "20260604",
            "label": "周四",
            "sentiment_index": 50,
            "sentiment_phase": "中性",
            "total_limit_up": 0,
            "market_heat_score": 50,
            "fund_sentiment": "中性",
            "buy_sell_analyses": [],
            "term_advices": [],
            "individual_stock_risks": [],
            "factor_correlations": [],
            "stress_test_results": [],
            "strategy_adjustments": [],
            "adjustment_reasons": [],
            "dynamic_position": {
                "current_position_pct": 100,
                "target_position_pct": 100,
                "max_position_pct": 100,
                "cash_reserve_pct": 100,  # Mismatch: 100 + 90 ≠ 100
                "total_capital": 100000,
                "stock_weights": [],
                "adjustment_reason": "",
                "rebalancing_needed": False,
            },
        }
        result = validate_comprehensive_data(data)
        dp = data["dynamic_position"]
        self.assertAlmostEqual(dp["target_position_pct"] + dp["cash_reserve_pct"], 100, delta=0.1)

    def test_fixes_missing_dynamic_position_fields(self) -> None:
        """Auto-fixes missing fields in dynamic_position."""
        data = {
            "date": "20260604", "label": "周四",
            "sentiment_index": 50, "sentiment_phase": "中性",
            "total_limit_up": 0, "market_heat_score": 50,
            "fund_sentiment": "中性",
            "buy_sell_analyses": [], "term_advices": [],
            "individual_stock_risks": [], "factor_correlations": [],
            "stress_test_results": [], "strategy_adjustments": [],
            "adjustment_reasons": [],
            "dynamic_position": {
                "total_capital": 100000,
            },
        }
        result = validate_comprehensive_data(data)
        dp = data["dynamic_position"]
        self.assertIn("stock_weights", dp)
        self.assertIsInstance(dp["stock_weights"], list)


class TestContextIntegrityReport(unittest.TestCase):
    """ContextIntegrityReport dataclass tests."""

    def test_to_dict(self) -> None:
        """to_dict produces correct structure."""
        report = ContextIntegrityReport(
            is_complete=False,
            orphaned_nodes=[CitationNode(field="test", content="test")],
            fixed_nodes=[],
            total_checks=10,
            passed_checks=8,
            data_quality_score=80.0,
        )
        d = report.to_dict()
        self.assertFalse(d["is_complete"])
        self.assertEqual(d["orphaned_count"], 1)
        self.assertEqual(d["total_checks"], 10)
        self.assertEqual(d["data_quality_score"], 80.0)


if __name__ == "__main__":
    unittest.main()
