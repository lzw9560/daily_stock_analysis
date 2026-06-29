# -*- coding: utf-8 -*-
"""情绪周期分析服务 — 量化市场情绪阶段.

核心功能：
1. 情绪指标计算（涨停数、跌停数、炸板率、连板数、赚钱效应、资金流向）
2. 情绪阶段判断（冰点/修复/分化/高潮/退潮）
3. 情绪趋势预测（基于历史数据）
4. 情绪与策略匹配建议
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SentimentEngine:
    """情绪周期分析引擎."""

    # 情绪阶段定义
    PHASE_ICING = "冰点"
    PHASE_RECOVERY = "修复"
    PHASE_DIFFERENTIATION = "分化"
    PHASE_EUPHORIA = "高潮"
    PHASE_DECLINE = "退潮"

    def __init__(self):
        pass

    def compute_sentiment_metrics(
        self,
        limit_up_count: int,
        limit_down_count: int,
        seal_plate_count: int,
        broken_seal_count: int,
        highest_board: int,
        connectivity_count: int,
        advance_count: int,
        decline_count: int,
        north_flow: float,
        main_force_flow: float,
        turnover_total: float,
        turnover_change: float,
    ) -> Dict[str, Any]:
        """计算情绪指标.

        Args:
            limit_up_count: 今日涨停数
            limit_down_count: 今日跌停数
            seal_plate_count: 封板数
            broken_seal_count: 炸板数
            highest_board: 最高连板数
            connectivity_count: 连板股数量
            advance_count: 上涨家数
            decline_count: 下跌家数
            north_flow: 北向资金净流入（亿元）
            main_force_flow: 主力资金净流入（亿元）
            turnover_total: 两市总成交额（亿元）
            turnover_change: 成交额环比变化（%）

        Returns:
            情绪指标字典
        """
        # 封板率
        seal_total = seal_plate_count + broken_seal_count
        seal_rate = (seal_plate_count / seal_total * 100) if seal_total > 0 else 0

        # 赚钱效应
        total_stocks = advance_count + decline_count
        advance_ratio = (advance_count / total_stocks * 100) if total_stocks > 0 else 50

        # 综合情绪分数（0-100）
        score = self._compute_sentiment_score(
            limit_up_count=limit_up_count,
            limit_down_count=limit_down_count,
            seal_rate=seal_rate,
            highest_board=highest_board,
            connectivity_count=connectivity_count,
            advance_ratio=advance_ratio,
            north_flow=north_flow,
            main_force_flow=main_force_flow,
            turnover_change=turnover_change,
        )

        # 情绪阶段
        phase = self._classify_phase(score, limit_up_count, seal_rate, highest_board)

        return {
            "sentiment_score": round(score, 1),
            "phase": phase,
            "limit_up_count": limit_up_count,
            "limit_down_count": limit_down_count,
            "seal_plate_count": seal_plate_count,
            "broken_seal_count": broken_seal_count,
            "seal_rate": round(seal_rate, 1),
            "highest_board": highest_board,
            "connectivity_count": connectivity_count,
            "advance_count": advance_count,
            "decline_count": decline_count,
            "advance_ratio": round(advance_ratio, 1),
            "north_flow": round(north_flow, 1),
            "main_force_flow": round(main_force_flow, 1),
            "turnover_total": round(turnover_total, 1),
            "turnover_change": round(turnover_change, 1),
        }

    def _compute_sentiment_score(
        self,
        limit_up_count: int,
        limit_down_count: int,
        seal_rate: float,
        highest_board: int,
        connectivity_count: int,
        advance_ratio: float,
        north_flow: float,
        main_force_flow: float,
        turnover_change: float,
    ) -> float:
        """综合情绪分数计算.

        权重分配：
        - 涨停数: 25%
        - 封板率: 20%
        - 连板高度: 20%
        - 涨跌比: 15%
        - 资金流向: 10%
        - 成交额变化: 10%
        """
        # 涨停数得分（满分25）
        if limit_up_count >= 80:
            limit_up_score = 25
        elif limit_up_count >= 50:
            limit_up_score = 20
        elif limit_up_count >= 30:
            limit_up_score = 15
        elif limit_up_count >= 20:
            limit_up_score = 10
        else:
            limit_up_score = max(0, limit_up_count / 20 * 10)

        # 封板率得分（满分20）
        seal_score = min(20, seal_rate / 100 * 20)

        # 连板高度得分（满分20）
        if highest_board >= 7:
            board_score = 20
        elif highest_board >= 5:
            board_score = 16
        elif highest_board >= 4:
            board_score = 12
        elif highest_board >= 3:
            board_score = 8
        else:
            board_score = max(0, highest_board * 2)

        # 涨跌比得分（满分15）
        advance_score = min(15, advance_ratio / 100 * 15)

        # 资金流向得分（满分10）
        total_flow = north_flow + main_force_flow
        if total_flow >= 100:
            flow_score = 10
        elif total_flow >= 50:
            flow_score = 8
        elif total_flow >= 0:
            flow_score = 5
        else:
            flow_score = max(0, 5 + total_flow / 20)

        # 成交额变化得分（满分10）
        if turnover_change >= 10:
            turnover_score = 10
        elif turnover_change >= 5:
            turnover_score = 8
        elif turnover_change >= 0:
            turnover_score = 6
        elif turnover_change >= -5:
            turnover_score = 4
        else:
            turnover_score = max(0, 4 + turnover_change / 5)

        return limit_up_score + seal_score + board_score + advance_score + flow_score + turnover_score

    def _classify_phase(
        self,
        score: float,
        limit_up_count: int,
        seal_rate: float,
        highest_board: int,
    ) -> str:
        """情绪阶段判断.

        阶段定义：
        - 冰点: score < 30 或 涨停<20
        - 修复: 30 <= score < 50 且 涨停回升
        - 分化: 50 <= score < 70 且 连板提升
        - 高潮: score >= 70 且 涨停>80
        - 退潮: score下降且跌停增多
        """
        if score < 30 or limit_up_count < 20:
            return self.PHASE_ICING
        elif score >= 70 and limit_up_count >= 80:
            return self.PHASE_EUPHORIA
        elif highest_board >= 5 and seal_rate > 60:
            return self.PHASE_DIFFERENTIATION
        elif score >= 50:
            return self.PHASE_RECOVERY
        else:
            return self.PHASE_DECLINE

    def get_phase_recommendation(self, phase: str) -> Dict[str, Any]:
        """根据情绪阶段给出操作建议.

        Returns:
            {
                "action": "观望/轻仓试错/聚焦主线/持股加仓/减仓清仓",
                "position_suggestion": "0-10%/10-30%/30-50%/50-70%/0-20%",
                "risk_level": "低/中/高/极高",
                "focus": "试错新题材/聚焦主线龙头/持股不动/控制仓位",
            }
        """
        recommendations = {
            self.PHASE_ICING: {
                "action": "观望/试错",
                "position_suggestion": "0-10%",
                "risk_level": "低",
                "focus": "冰点试错新题材，小仓位布局",
                "suitable_strategies": ["首板挖掘", "低吸龙头"],
            },
            self.PHASE_RECOVERY: {
                "action": "轻仓试错",
                "position_suggestion": "10-30%",
                "risk_level": "中低",
                "focus": "关注首板增多信号，聚焦新主线",
                "suitable_strategies": ["首板挖掘", "平台突破"],
            },
            self.PHASE_DIFFERENTIATION: {
                "action": "聚焦主线",
                "position_suggestion": "30-50%",
                "risk_level": "中",
                "focus": "连板高度提升，聚焦主线龙头",
                "suitable_strategies": ["连板接力", "龙头低吸", "N字反击"],
            },
            self.PHASE_EUPHORIA: {
                "action": "持股/加仓",
                "position_suggestion": "50-70%",
                "risk_level": "中高",
                "focus": "持股待涨，适度加仓主线龙头",
                "suitable_strategies": ["连板接力", "反包战法", "均线多头"],
            },
            self.PHASE_DECLINE: {
                "action": "减仓/清仓",
                "position_suggestion": "0-20%",
                "risk_level": "高",
                "focus": "高位股杀跌，控制仓位防守",
                "suitable_strategies": ["空仓观望"],
            },
        }
        return recommendations.get(phase, recommendations[self.PHASE_RECOVERY])

    def predict_trend(
        self,
        recent_scores: List[Tuple[str, float]],
    ) -> str:
        """基于近期情绪分数预测趋势.

        Args:
            recent_scores: [(date_str, score), ...] 最近N天的情绪分数

        Returns:
            "improving" / "stable" / "declining"
        """
        if len(recent_scores) < 3:
            return "stable"

        scores = [s for _, s in recent_scores[-5:]]
        avg_recent = sum(scores[-2:]) / 2 if len(scores) >= 2 else scores[-1]
        avg_prev = sum(scores[:-2]) / max(1, len(scores) - 2)

        if avg_recent > avg_prev + 5:
            return "improving"
        elif avg_recent < avg_prev - 5:
            return "declining"
        else:
            return "stable"
