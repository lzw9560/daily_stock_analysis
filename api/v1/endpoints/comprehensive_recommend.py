"""
综合推荐系统 API 端点

提供完整的推荐服务：
- 综合推荐仪表盘
- 买卖意愿分析
- 短中长期建议
- 板块轮动分析
- 风险评估
- 个股风险剖析
- 动态仓位管理
- 因子监控
- 压力测试
- 仓位标的移除
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, validator

from src.strategy.comprehensive_recommender import ComprehensiveRecommendationEngine
from src.analysis.context_integrity import validate_comprehensive_data

logger = logging.getLogger(__name__)

# 仓位移除排除列表文件路径
EXCLUDED_STOCKS_FILE = Path(__file__).parent.parent.parent.parent / "excluded_position_stocks.json"

router = APIRouter(tags=["综合推荐"])


# ============================================================
#  Response Models (Frontend-friendly camelCase)
# ============================================================

class BuySellAnalysisModel(BaseModel):
    code: str
    name: str
    buy_willingness: int
    sell_willingness: int
    ideal_buy_price: float
    buy_range_low: float
    buy_range_high: float
    stop_loss_price: float
    take_profit_short: float
    take_profit_long: float
    entry_strategy: str
    exit_strategy: str
    buy_signals: list[str]
    sell_signals: list[str]


class TermAdviceModel(BaseModel):
    term: str
    label: str
    action: str
    confidence: str
    target_return_pct: float
    hold_days: str
    strategy_desc: str
    risk_level: str
    key_levels: list[str]


class SectorRotationModel(BaseModel):
    hot_sectors: list[dict]
    cooling_sectors: list[dict]
    next_potential_sectors: list[dict]
    rotation_phase: str
    rotation_score: int
    hot_money_focus: list[str]
    institution_focus: list[str]
    suggestions: list[str]


class RiskAssessmentModel(BaseModel):
    overall_risk_score: int
    overall_risk_level: str
    market_risk: int
    position_risk: int
    sector_concentration_risk: int
    liquidity_risk: int
    sentiment_risk: int
    risk_factors: list[str]
    risk_mitigations: list[str]
    max_recommended_position: float


class IndividualStockRiskModel(BaseModel):
    code: str
    name: str
    risk_score: int
    risk_level: str
    valuation_risk: int
    technical_risk: int
    fund_flow_risk: int
    sentiment_risk: int
    sector_risk: int
    liquidity_risk: int
    black_swan_risk: int
    risk_items: list[dict]
    suggestions: list[str]
    position_limit_pct: float


class DynamicPositionModel(BaseModel):
    total_capital: float
    current_position_pct: float
    target_position_pct: float
    max_position_pct: float
    cash_reserve_pct: float
    stock_weights: list[dict]
    adjustment_reason: str
    rebalancing_needed: bool


class FactorCorrelationModel(BaseModel):
    factor_name: str
    current_value: float
    z_score: float
    correlation_with_market: float
    status: str
    warning_msg: str


class StressTestResultModel(BaseModel):
    scenario: str
    max_drawdown_pct: float
    portfolio_loss_pct: float
    recovery_days_est: int
    circuit_breaker_triggered: bool
    circuit_breaker_level: str
    suggested_action: str
    impact_on_holdings: list[dict]


class ComprehensiveRecommendationResponse(BaseModel):
    """综合推荐主响应"""
    date: str
    label: str
    generated_at: str
    sentiment_index: float
    sentiment_phase: str
    total_limit_up: int
    market_heat_score: int
    fund_sentiment: str
    buy_sell_analyses: list[BuySellAnalysisModel]
    term_advices: list[TermAdviceModel]
    sector_rotation: Optional[SectorRotationModel] = None
    risk_assessment: Optional[RiskAssessmentModel] = None
    individual_stock_risks: list[IndividualStockRiskModel]
    dynamic_position: Optional[DynamicPositionModel] = None
    factor_correlations: list[FactorCorrelationModel]
    stress_test_results: list[StressTestResultModel]
    strategy_adjustments: list[str]
    adjustment_reasons: list[str]
    win_rate_info: dict


class WinRateBriefResponse(BaseModel):
    """胜率简报"""
    total: int = 0
    settled: int = 0
    won: int = 0
    lost: int = 0
    pending: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    rolling_10: float = 0.0
    trend: str = "stable"
    by_sector: dict = Field(default_factory=dict)


# ============================================================
#  API Routes
# ============================================================

@router.get("", response_model=ComprehensiveRecommendationResponse)
async def get_comprehensive_recommendations(
    date: Optional[str] = Query(None, description="日期 YYYYMMDD，默认自动选择"),
):
    """
    获取综合推荐仪表盘

    一次性返回所有推荐维度：
    - 买卖点位与意愿分析
    - 短中长期投资建议
    - 板块轮动分析
    - 整体风险评估
    - 个股风险剖析
    - 动态仓位管理
    - 因子相关性监控
    - 压力测试结果
    - 胜率回溯与策略调整
    """
    from src.seal_plate.date_utils import get_effective_date, get_label_for_date
    from src.seal_plate.seal_plate_service import SealPlateService

    try:
        effective_date = get_effective_date(date)
        date_label = get_label_for_date(effective_date)

        # 获取打板报告
        service = SealPlateService(config={'feishu_enabled': False})
        report = service.run(date=effective_date, force=True)

        if not report:
            return ComprehensiveRecommendationResponse(
                date=effective_date,
                label=date_label,
                generated_at=datetime.now().isoformat(),
                sentiment_index=50,
                sentiment_phase="中性",
                total_limit_up=0,
                market_heat_score=50,
                fund_sentiment="中性",
                buy_sell_analyses=[],
                term_advices=[],
                individual_stock_risks=[],
                factor_correlations=[],
                stress_test_results=[],
                strategy_adjustments=["今日无涨停板数据"],
                adjustment_reasons=[],
                win_rate_info={},
            )

        # 获取资金流向分析
        fund_analysis = None
        try:
            from src.seal_plate.capital_flow_analyzer import CapitalFlowAnalyzer
            analyzer = CapitalFlowAnalyzer()
            fund_analysis = analyzer.analyze(
                hot_sectors=report.sector_hot,
                strong_stocks=list(report.strong_stocks) + list(report.watch_stocks),
                date=effective_date,
            )
        except Exception as e:
            logger.debug("资金流向分析获取失败(非致命): %s", e)

        # 生成综合推荐
        engine = ComprehensiveRecommendationEngine()
        result = engine.generate_comprehensive(
            report=report,
            fund_analysis=fund_analysis,
        )

        # 转换为响应模型
        response = _to_response_model(result)

        # 数据完整性校验（修复可能的前端显示异常）
        response_dict = response.model_dump()
        validation = validate_comprehensive_data(response_dict)
        if validation.issues:
            logger.warning("综合推荐数据校验发现问题: %s", validation.issues)
        if validation.fixed:
            logger.info("综合推荐数据自动修复: %s", validation.fixed)
        # Re-build from validated dict
        response = ComprehensiveRecommendationResponse(**response_dict)

        # 过滤已排除的仓位标的
        if response.dynamic_position:
            dp_dict = response.dynamic_position.model_dump()
            filtered_dp = _filter_excluded_stocks(dp_dict)
            if filtered_dp:
                response.dynamic_position = DynamicPositionModel(**filtered_dp)

        return response

    except Exception as e:
        logger.error("综合推荐生成失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/win-rate-brief", response_model=WinRateBriefResponse)
async def get_win_rate_brief():
    """获取胜率简报（供仪表盘快速显示）"""
    from src.seal_plate.recommendation_log import RecommendationLogStore
    from src.seal_plate.win_rate_tracker import WinRateTracker

    try:
        store = RecommendationLogStore()
        tracker = WinRateTracker(store)
        stats = tracker.compute_stats()

        return WinRateBriefResponse(
            total=stats.total_recommendations,
            settled=stats.settled,
            won=stats.won,
            lost=stats.lost,
            pending=stats.pending,
            win_rate=stats.win_rate,
            avg_return=stats.avg_return,
            rolling_10=stats.rolling_win_rate_10,
            trend=stats.trend,
            by_sector={
                s: {"won": d["won"], "total": d["total"], "rate": d["rate"]}
                for s, d in sorted(
                    stats.by_sector.items(),
                    key=lambda x: x[1]["rate"], reverse=True
                )[:10]
            },
        )
    except Exception as e:
        logger.error("胜率简报获取失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# 股票代码格式校验: 6位数字
_STOCK_CODE_RE = re.compile(r'^\d{6}$')

def _validate_stock_code(code: str) -> str:
    """校验股票代码格式，不合法时抛出 HTTPException"""
    code = code.strip()
    if not _STOCK_CODE_RE.match(code):
        raise HTTPException(
            status_code=422,
            detail=f"无效的股票代码: {code}，应为6位数字",
        )
    return code


# ============================================================
#  Excluded Position Stocks Management
# ============================================================

def _load_excluded_stocks() -> set:
    """加载仓位排除标的列表"""
    if not EXCLUDED_STOCKS_FILE.exists():
        return set()
    try:
        data = json.loads(EXCLUDED_STOCKS_FILE.read_text(encoding="utf-8"))
        return set(data.get("excluded_codes", []))
    except Exception as e:
        logger.warning("加载排除标的列表失败: %s", e)
        return set()


def _save_excluded_stocks(codes: set):
    """保存仓位排除标的列表"""
    EXCLUDED_STOCKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    EXCLUDED_STOCKS_FILE.write_text(
        json.dumps({"excluded_codes": list(codes), "updated_at": datetime.now().isoformat()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _filter_excluded_stocks(dynamic_position: Optional[dict]) -> Optional[dict]:
    """从动态仓位中过滤已排除的标的"""
    if not dynamic_position:
        return None
    excluded = _load_excluded_stocks()
    if not excluded:
        return dynamic_position
    weights = dynamic_position.get("stock_weights", [])
    filtered_weights = [w for w in weights if w.get("code", "") not in excluded]
    if len(filtered_weights) < len(weights):
        dynamic_position["stock_weights"] = filtered_weights
        # 重新计算目标仓位（按比例缩减）
        if weights:
            old_total = sum(w.get("weight_pct", 0) for w in weights)
            new_total = sum(w.get("weight_pct", 0) for w in filtered_weights)
            if old_total > 0:
                ratio = new_total / old_total
                dynamic_position["target_position_pct"] = round(
                    dynamic_position.get("target_position_pct", 30) * ratio, 1
                )
                dynamic_position["cash_reserve_pct"] = round(
                    100 - dynamic_position["target_position_pct"], 1
                )
        if not filtered_weights:
            dynamic_position["rebalancing_needed"] = True
            dynamic_position["adjustment_reason"] = "所有配置标的已被移除"
    return dynamic_position


# ============================================================
#  Helper: Convert dataclass to response model
# ============================================================

def _to_response_model(result) -> ComprehensiveRecommendationResponse:
    return ComprehensiveRecommendationResponse(
        date=result.date,
        label=result.label,
        generated_at=result.generated_at,
        sentiment_index=result.sentiment_index,
        sentiment_phase=result.sentiment_phase,
        total_limit_up=result.total_limit_up,
        market_heat_score=result.market_heat_score,
        fund_sentiment=result.fund_sentiment,
        buy_sell_analyses=[
            BuySellAnalysisModel(**a.__dict__) for a in result.buy_sell_analyses
        ],
        term_advices=[
            TermAdviceModel(**a.__dict__) for a in result.term_advices
        ],
        sector_rotation=(
            SectorRotationModel(**result.sector_rotation.__dict__)
            if result.sector_rotation else None
        ),
        risk_assessment=(
            RiskAssessmentModel(**result.risk_assessment.__dict__)
            if result.risk_assessment else None
        ),
        individual_stock_risks=[
            IndividualStockRiskModel(**r.__dict__) for r in result.individual_stock_risks
        ],
        dynamic_position=(
            DynamicPositionModel(**result.dynamic_position.__dict__)
            if result.dynamic_position else None
        ),
        factor_correlations=[
            FactorCorrelationModel(**f.__dict__) for f in result.factor_correlations
        ],
        stress_test_results=[
            StressTestResultModel(**s.__dict__) for s in result.stress_test_results
        ],
        strategy_adjustments=result.strategy_adjustments,
        adjustment_reasons=result.adjustment_reasons,
        win_rate_info=result.win_rate_info,
    )


# ============================================================
#  Position Stock Management Endpoints
# ============================================================

class RemovePositionStockRequest(BaseModel):
    code: str = Field(..., description="要移除的股票代码")


class ExcludedStocksResponse(BaseModel):
    excluded_codes: list[str]
    count: int


@router.delete("/position/stocks/{code}", summary="移除仓位配置标的")
async def remove_position_stock(code: str):
    """从仓位管理中排除指定标的（下次刷新后不再出现）"""
    try:
        code = _validate_stock_code(code)
        excluded = _load_excluded_stocks()
        excluded.add(code)
        _save_excluded_stocks(excluded)
        return {
            "success": True,
            "code": code,
            "excluded_count": len(excluded),
            "message": f"标的 {code} 已从仓位配置中排除",
        }
    except Exception as e:
        logger.error("移除仓位标的失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/position/stocks/excluded", response_model=ExcludedStocksResponse)
async def get_excluded_position_stocks():
    """获取已排除的仓位标的列表"""
    try:
        excluded = _load_excluded_stocks()
        return ExcludedStocksResponse(
            excluded_codes=list(excluded),
            count=len(excluded),
        )
    except Exception as e:
        logger.error("获取排除列表失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/position/stocks/excluded/{code}", summary="恢复已排除的仓位标的")
async def restore_position_stock(code: str):
    """将已排除的标的重新加入仓位管理"""
    try:
        code = _validate_stock_code(code)
        excluded = _load_excluded_stocks()
        if code in excluded:
            excluded.discard(code)
            _save_excluded_stocks(excluded)
            return {"success": True, "code": code, "message": f"标的 {code} 已恢复"}
        return {"success": False, "code": code, "message": f"标的 {code} 不在排除列表中"}
    except Exception as e:
        logger.error("恢复仓位标的失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/position/stocks/excluded", summary="清空排除列表")
async def clear_excluded_position_stocks():
    """清空所有已排除的仓位标的"""
    try:
        _save_excluded_stocks(set())
        return {"success": True, "message": "排除列表已清空"}
    except Exception as e:
        logger.error("清空排除列表失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
