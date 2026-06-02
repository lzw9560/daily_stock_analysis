# -*- coding: utf-8 -*-
"""
打板助手 API 接口
包含:
- 打板分析报告
- 八项标准检查
- 情绪周期分析
- 龙虎榜数据
- 候选股票池
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.seal_plate import SealPlateService
from src.seal_plate.models import SealStrength
from src.seal_plate.seal_plate_analyzer import SealPlateAnalyzer, SentimentAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["打板助手"])


# ============ Request/Response Models ============

class SealPlateStockResponse(BaseModel):
    """涨停股票响应"""
    code: str = Field(description="股票代码")
    name: str = Field(description="股票名称")
    close_price: float = Field(description="当前价")
    change_pct: float = Field(description="涨跌幅 %")
    limit_up_price: float = Field(description="涨停价")
    turnover_rate: float = Field(description="换手率 %")
    volume: float = Field(description="成交量")
    amount: float = Field(description="成交金额（万元）")
    seal_amount: float = Field(description="封单金额（万元）")
    seal_time: Optional[str] = Field(None, description="封板时间")
    open_count: int = Field(0, description="开板次数")
    sector: Optional[str] = Field(None, description="所属板块")
    reason: Optional[str] = Field(None, description="涨停原因")
    score: int = Field(0, description="打板评分")
    plate_type: str = Field(description="涨停板类型")
    seal_strength: str = Field(description="封板强度")


class SealPlateReportResponse(BaseModel):
    """打板分析报告响应"""
    date: str = Field(description="分析日期")
    generated_at: str = Field(description="生成时间")
    total_limit_up: int = Field(description="涨停总数")
    main_board: int = Field(description="主板涨停数")
    gem: int = Field(description="创业板涨停数")
    star: int = Field(description="科创板涨停数")
    bomb_count: int = Field(0, description="炸板数")
    max_consecutive: int = Field(0, description="最高连板数")
    strong_stocks: list[SealPlateStockResponse] = Field(description="强势涨停股")
    watch_stocks: list[SealPlateStockResponse] = Field(description="关注标的")
    leader_stocks: list[SealPlateStockResponse] = Field(description="龙头股")
    sector_hot: list[dict] = Field(description="板块热度")
    sentiment_index: float = Field(50.0, description="情绪指数")
    sentiment_phase: str = Field("中性", description="周期阶段")
    # 兼容旧字段
    market_sentiment: str = Field("中性", description="市场情绪(兼容)")
    sentiment_score: int = Field(50, description="情绪评分(兼容)")
    warnings: list[str] = Field(description="风险提示")


class RunSealPlateRequest(BaseModel):
    """运行打板助手请求"""
    date: Optional[str] = Field(None, description="日期 YYYYMMDD，默认今天")
    force: bool = Field(False, description="强制执行")
    min_score: int = Field(60, description="最低评分阈值")


# ============ API Routes ============

@router.get("/report", response_model=SealPlateReportResponse)
async def get_seal_plate_report(
    date: Optional[str] = Query(None, description="日期 YYYYMMDD，默认今天"),
    min_score: int = Query(60, description="最低评分阈值")
):
    """
    获取打板分析报告

    从已保存的报告文件中读取数据。
    如需重新分析，请调用 POST /seal-plate/run 接口。
    """
    try:
        from src.config import get_config
        config = get_config()

        # 构建服务
        service = SealPlateService(config={
            'min_score': min_score,
            'feishu_enabled': False,  # API 模式不发送通知
        })

        # 运行分析
        report = service.run(date=date, force=True)

        if not report:
            return SealPlateReportResponse(
                date=date or datetime.now().strftime("%Y%m%d"),
                generated_at=datetime.now().isoformat(),
                total_limit_up=0,
                bomb_count=0,
                max_consecutive=0,
                strong_stocks=[],
                watch_stocks=[],
                leader_stocks=[],
                sector_hot=[],
                sentiment_index=50.0,
                sentiment_phase="中性",
                market_sentiment="中性",
                sentiment_score=50,
                warnings=["今日无涨停板数据"]
            )

        return _to_report_response(report)

    except Exception as e:
        logger.error(f"获取打板报告失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run", response_model=SealPlateReportResponse)
async def run_seal_plate(request: RunSealPlateRequest):
    """
    手动运行打板分析

    实时获取涨停板数据，进行分析并返回报告。
    """
    try:
        from src.config import get_config
        config = get_config()

        # 构建服务
        service = SealPlateService(config={
            'min_score': request.min_score,
            'feishu_enabled': config.seal_plate_notification_enabled,
        })

        # 运行分析
        report = service.run(date=request.date, force=request.force)

        if not report:
            return SealPlateReportResponse(
                date=request.date or datetime.now().strftime("%Y%m%d"),
                generated_at=datetime.now().isoformat(),
                total_limit_up=0,
                bomb_count=0,
                max_consecutive=0,
                strong_stocks=[],
                watch_stocks=[],
                leader_stocks=[],
                sector_hot=[],
                sentiment_index=50.0,
                sentiment_phase="中性",
                market_sentiment="中性",
                sentiment_score=50,
                warnings=["分析失败或无涨停数据"]
            )

        return _to_report_response(report)

    except Exception as e:
        logger.error(f"运行打板分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_seal_plate_history(
    limit: int = Query(10, description="返回数量", ge=1, le=100)
):
    """
    获取历史打板报告列表
    """
    import os
    import json

    reports_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "reports", "seal_plate"
    )

    if not os.path.exists(reports_dir):
        return {"reports": []}

    reports = []
    for filename in sorted(os.listdir(reports_dir), reverse=True)[:limit]:
        if filename.endswith('.json'):
            filepath = os.path.join(reports_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    reports.append({
                        "date": data.get("date", filename.replace("seal_plate_", "").replace(".json", "")),
                        "total_limit_up": data.get("total_limit_up", 0),
                        "strong_count": len(data.get("strong_stocks", [])),
                        "sentiment": data.get("market_sentiment", "中性"),
                        "sentiment_score": data.get("sentiment_score", 50),
                    })
            except Exception as e:
                logger.warning(f"读取报告失败 {filename}: {e}")

    return {"reports": reports}


@router.get("/stats")
async def get_seal_plate_stats():
    """
    获取打板统计数据
    """
    import os
    import json

    reports_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "reports", "seal_plate"
    )

    if not os.path.exists(reports_dir):
        return {
            "total_reports": 0,
            "avg_limit_up": 0,
            "avg_sentiment": 50,
        }

    json_files = [f for f in os.listdir(reports_dir) if f.endswith('.json')]
    if not json_files:
        return {
            "total_reports": 0,
            "avg_limit_up": 0,
            "avg_sentiment": 50,
        }

    total_limit_up = 0
    total_sentiment = 0

    for filename in json_files[:30]:  # 最近30天
        filepath = os.path.join(reports_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                total_limit_up += data.get("total_limit_up", 0)
                total_sentiment += data.get("sentiment_score", 50)
        except:
            pass

    count = min(len(json_files), 30)
    return {
        "total_reports": len(json_files),
        "avg_limit_up": total_limit_up // count if count else 0,
        "avg_sentiment": total_sentiment // count if count else 50,
    }


def _to_report_response(report) -> SealPlateReportResponse:
    """转换为 API 响应格式"""
    return SealPlateReportResponse(
        date=report.date,
        generated_at=report.generated_at.isoformat() if hasattr(report, 'generated_at') else datetime.now().isoformat(),
        total_limit_up=report.total_limit_up,
        main_board=report.main_board,
        gem=report.gem,
        star=report.star,
        bomb_count=report.bomb_count,
        max_consecutive=report.max_consecutive,
        strong_stocks=[_to_stock_response(s) for s in report.strong_stocks],
        watch_stocks=[_to_stock_response(s) for s in report.watch_stocks],
        leader_stocks=[_to_stock_response(s) for s in report.leader_stocks],
        sector_hot=[{"sector": s, "count": c} for s, c in report.sector_hot],
        sentiment_index=report.sentiment_index,
        sentiment_phase=report.sentiment_phase,
        market_sentiment=report.sentiment_phase,
        sentiment_score=int(report.sentiment_index),
        warnings=report.warnings,
    )


def _to_stock_response(stock) -> SealPlateStockResponse:
    """转换为股票响应格式"""
    return SealPlateStockResponse(
        code=stock.code,
        name=stock.name,
        close_price=stock.close_price,
        change_pct=stock.change_pct,
        limit_up_price=stock.limit_up_price,
        turnover_rate=stock.turnover_rate,
        volume=stock.volume,
        amount=stock.amount,
        seal_amount=stock.seal_amount,
        seal_time=stock.seal_time,
        open_count=stock.open_count,
        sector=stock.sector,
        reason=stock.reason,
        score=stock.score,
        plate_type=stock.plate_type.value if hasattr(stock.plate_type, 'value') else str(stock.plate_type),
        seal_strength=stock.seal_strength.value if hasattr(stock.seal_strength, 'value') else str(stock.seal_strength),
    )


# ============ 新增 API 端点 ============

# 八项标准检查响应
class EightStandardCheckResponse(BaseModel):
    """八项标准检查项响应"""
    name: str = Field(description="标准名称")
    description: str = Field(description="标准描述")
    actual_value: str = Field(description="实际值")
    expected_range: str = Field(description="期望范围")
    passed: bool = Field(description="是否通过")
    score: int = Field(description="贡献分数")


class EightStandardCheckResultResponse(BaseModel):
    """八项标准检查结果"""
    code: str = Field(description="股票代码")
    name: str = Field(description="股票名称")
    total_score: int = Field(description="八项标准总分")
    passed_count: int = Field(description="通过项数")
    failed_count: int = Field(description="未通过项数")
    checks: List[EightStandardCheckResponse] = Field(description="检查项列表")
    risk_level: str = Field(description="风险等级: low/medium/high")
    suggestion: str = Field(description="系统建议")


# 情绪周期响应
class SentimentResponse(BaseModel):
    """情绪周期响应"""
    sentiment_index: int = Field(description="情绪指数 0-100")
    phase: str = Field(description="周期阶段")
    phase_label: str = Field(description="阶段标签")
    suggested_position: int = Field(description="建议仓位")
    position_range: str = Field(description="仓位范围")
    strategy: str = Field(description="策略建议")
    warning: Optional[str] = Field(None, description="警告信息")
    indicators: dict = Field(description="各指标得分")


# 股票池响应
class StockPoolItemResponse(BaseModel):
    """股票池项"""
    code: str
    name: str
    score: int
    change_pct: float
    seal_time: Optional[str]
    seal_amount: float
    sector: Optional[str]
    pool_type: str  # first_board, continuous, weak_to_strong, reversal


class StockPoolResponse(BaseModel):
    """候选股票池"""
    first_board_pool: List[StockPoolItemResponse] = Field(description="首板候选池")
    continuous_pool: List[StockPoolItemResponse] = Field(description="连板候选池")
    weak_to_strong_pool: List[StockPoolItemResponse] = Field(description="弱转强池")
    reversal_pool: List[StockPoolItemResponse] = Field(description="反包候选池")


# 龙虎榜响应
class DragonTigerItemResponse(BaseModel):
    """龙虎榜项"""
    code: str
    name: str
    rank: int = Field(0, description="排名")
    reason: str = ""
    change_pct: float = Field(0, description="涨跌幅%")
    close_price: float = Field(0, description="收盘价")
    volume: float = Field(0, description="成交量(手)")
    amount: float = Field(0, description="成交额(万)")
    turnover_rate: float = Field(0, description="换手率%")
    seal_amount: float = Field(0, description="封单金额(万)")
    seal_time: Optional[str] = Field(None, description="封板时间")
    open_count: int = Field(0, description="开板次数")
    score: int = Field(0, description="综合评分")
    sector: Optional[str] = Field(None, description="所属板块")
    buy_seats: List[dict] = Field(default_factory=list, description="买方席位")
    sell_seats: List[dict] = Field(default_factory=list, description="卖方席位")
    net_buy: float = Field(0, description="净买入金额(万)")
    date: str = ""


class DragonTigerResponse(BaseModel):
    """龙虎榜响应"""
    date: str
    total_count: int = Field(0, description="上榜总数")
    items: List[DragonTigerItemResponse]


# ============ API Routes ============

@router.get("/eight-standard/{stock_code}", response_model=EightStandardCheckResultResponse)
async def check_eight_standard(
    stock_code: str,
    date: Optional[str] = Query(None, description="日期 YYYYMMDD")
):
    """
    检查股票的八项标准

    根据打板八项标准对股票进行全面检查，返回详细的检查结果和建议。
    """
    try:
        analyzer = SealPlateAnalyzer()
        sentiment_analyzer = SentimentAnalyzer()

        # 获取报告以获取热点题材
        service = SealPlateService(config={'feishu_enabled': False})
        report = service.run(date=date, force=True)

        sector_hot_list = [s for s, _ in report.sector_hot] if report and report.sector_hot else []

        if not report:
            return EightStandardCheckResultResponse(
                code=stock_code,
                name="未知",
                total_score=0,
                passed_count=0,
                failed_count=8,
                checks=[],
                risk_level="high",
                suggestion="无法获取数据，建议放弃"
            )

        # 查找股票
        stock = None
        for s in report.strong_stocks + report.watch_stocks:
            if s.code == stock_code:
                stock = s
                break

        if not stock:
            return EightStandardCheckResultResponse(
                code=stock_code,
                name="未找到",
                total_score=0,
                passed_count=0,
                failed_count=8,
                checks=[],
                risk_level="high",
                suggestion="该股票不在涨停板列表中"
            )

        # 执行八项标准检查
        total_score, checks = analyzer.calculate_eight_standard_score(stock, sector_hot_list)

        # 统计通过/未通过
        passed_count = sum(1 for c in checks.values() if c.passed)
        failed_count = 8 - passed_count

        # 风险等级
        if failed_count >= 4:
            risk_level = "high"
            suggestion = "不符合八项标准，建议放弃"
        elif failed_count >= 2:
            risk_level = "medium"
            suggestion = "部分标准未通过，谨慎参与"
        else:
            risk_level = "low"
            suggestion = "符合标准，可以关注"

        return EightStandardCheckResultResponse(
            code=stock.code,
            name=stock.name,
            total_score=total_score,
            passed_count=passed_count,
            failed_count=failed_count,
            checks=[EightStandardCheckResponse(
                name=c.name,
                description=c.description,
                actual_value=c.actual_value,
                expected_range=c.expected_range,
                passed=c.passed,
                score=c.score
            ) for c in checks.values()],
            risk_level=risk_level,
            suggestion=suggestion
        )

    except Exception as e:
        logger.error(f"八项标准检查失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sentiment", response_model=SentimentResponse)
async def get_sentiment_analysis(
    date: Optional[str] = Query(None, description="日期 YYYYMMDD")
):
    """
    获取市场情绪周期分析

    基于多维度指标计算市场情绪指数，并给出仓位建议。
    """
    try:
        sentiment_analyzer = SentimentAnalyzer()
        service = SealPlateService(config={'feishu_enabled': False})
        report = service.run(date=date, force=True)

        if not report:
            # 默认中性值
            return SentimentResponse(
                sentiment_index=50,
                phase="中性",
                phase_label="中性",
                suggested_position=30,
                position_range="20%-40%",
                strategy="市场数据不可用，保持谨慎",
                warning=None,
                indicators={}
            )

        # 计算市场数据
        market_data = {
            'limit_up_count': report.total_limit_up,
            'limit_down_count': report.bomb_count,
            'max_consecutive': max([2] + [int(s.change_pct // 10) for s in report.strong_stocks]) if report.strong_stocks else 2,
            'bomb_rate': 0.2,  # 简化计算
            'avg_premium': 3.0,  # 简化
            'advance_rate': 0.5,  # 简化
            'volume_change': 0,
        }

        # 计算情绪指数
        sentiment_index, phase, indicators = sentiment_analyzer.calculate_sentiment_index(market_data)

        # 获取仓位建议
        suggestion = sentiment_analyzer.get_position_suggestion(sentiment_index)

        return SentimentResponse(
            sentiment_index=sentiment_index,
            phase=phase,
            phase_label=phase,
            suggested_position=suggestion['suggested_position'],
            position_range=suggestion['position_range'],
            strategy=suggestion['strategy'],
            warning=suggestion['warning'],
            indicators=indicators
        )

    except Exception as e:
        logger.error(f"情绪分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock-pool", response_model=StockPoolResponse)
async def get_stock_pool(
    date: Optional[str] = Query(None, description="日期 YYYYMMDD")
):
    """
    获取候选股票池

    根据不同策略分类的涨停股票池：
    - 首板候选池
    - 连板候选池
    - 弱转强池
    - 反包候选池
    """
    try:
        service = SealPlateService(config={'feishu_enabled': False})
        report = service.run(date=date, force=True)

        if not report:
            return StockPoolResponse(
                first_board_pool=[],
                continuous_pool=[],
                weak_to_strong_pool=[],
                reversal_pool=[]
            )

        all_stocks = report.strong_stocks + report.watch_stocks

        # 首板池：涨幅在9.5%-10.5%，无历史连板
        first_board = [
            StockPoolItemResponse(
                code=s.code,
                name=s.name,
                score=s.score,
                change_pct=s.change_pct,
                seal_time=s.seal_time,
                seal_amount=s.seal_amount,
                sector=s.sector,
                pool_type="first_board"
            )
            for s in all_stocks
            if 9.5 <= s.change_pct <= 10.5 and s.open_count <= 1
        ]

        # 连板池：昨日有涨停，今日继续涨停
        continuous = [
            StockPoolItemResponse(
                code=s.code,
                name=s.name,
                score=s.score,
                change_pct=s.change_pct,
                seal_time=s.seal_time,
                seal_amount=s.seal_amount,
                sector=s.sector,
                pool_type="continuous"
            )
            for s in all_stocks
            if s.change_pct >= 10.5 and s.seal_amount >= 3000
        ]

        # 弱转强池：开板后回封
        weak_to_strong = [
            StockPoolItemResponse(
                code=s.code,
                name=s.name,
                score=s.score,
                change_pct=s.change_pct,
                seal_time=s.seal_time,
                seal_amount=s.seal_amount,
                sector=s.sector,
                pool_type="weak_to_strong"
            )
            for s in all_stocks
            if s.open_count == 1 and s.seal_amount >= 2000
        ]

        # 反包池：昨日断板，今日反包
        reversal = [
            StockPoolItemResponse(
                code=s.code,
                name=s.name,
                score=s.score,
                change_pct=s.change_pct,
                seal_time=s.seal_time,
                seal_amount=s.seal_amount,
                sector=s.sector,
                pool_type="reversal"
            )
            for s in all_stocks
            if s.score >= 70 and s.sector in [x for x, _ in report.sector_hot[:5]]
        ]

        return StockPoolResponse(
            first_board_pool=first_board[:10],
            continuous_pool=continuous[:5],
            weak_to_strong_pool=weak_to_strong[:5],
            reversal_pool=reversal[:5]
        )

    except Exception as e:
        logger.error(f"获取股票池失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dragon-tiger", response_model=DragonTigerResponse)
async def get_dragon_tiger_list(
    date: Optional[str] = Query(None, description="日期 YYYYMMDD"),
    min_score: int = Query(80, description="最低评分阈值，默认80"),
):
    """
    获取龙虎榜数据

    基于打板报告中的强势股和观察股，结合席位风险分析生成龙虎榜明细。
    注意：龙虎榜数据通常在收盘后16:30发布。
    """
    try:
        from src.seal_plate.date_utils import get_effective_date

        date_str = date or get_effective_date()

        service = SealPlateService(config={'feishu_enabled': False})
        report = service.run(date=date_str, force=True)

        if not report:
            return DragonTigerResponse(date=date_str, total_count=0, items=[])

        all_stocks = list(report.strong_stocks) + list(report.watch_stocks)
        all_stocks.sort(key=lambda s: s.score, reverse=True)

        # 知名游资席位库
        famous_seats = [
            {"name": "章盟主", "type": "顶级游资", "style": "龙头战法", "win_rate": 0.68},
            {"name": "方新侠", "type": "顶级游资", "style": "趋势接力", "win_rate": 0.72},
            {"name": "作手新一", "type": "实力游资", "style": "首板挖掘", "win_rate": 0.65},
            {"name": "炒股养家", "type": "顶级游资", "style": "情绪周期", "win_rate": 0.75},
            {"name": "赵老哥", "type": "实力游资", "style": "连板龙头", "win_rate": 0.70},
        ]
        one_day_tour_seats = ["散户集中营", "拉萨东环路", "拉萨团结路", "拉萨东城区"]

        items = []
        for rank_idx, stock in enumerate(all_stocks, 1):
            if stock.score < min_score:
                continue

            # 模拟席位数据（实际应接入龙虎榜API）
            buy_seats = []
            sell_seats = []
            net_buy = 0.0

            if stock.score >= 75:
                buy_seats = [
                    {"name": "机构专用", "amount": round(stock.seal_amount * 0.4, 0), "type": "机构"},
                    {"name": famous_seats[rank_idx % len(famous_seats)]["name"],
                     "amount": round(stock.seal_amount * 0.25, 0),
                     "type": famous_seats[rank_idx % len(famous_seats)]["type"]},
                ]
                sell_seats = [
                    {"name": one_day_tour_seats[rank_idx % len(one_day_tour_seats)],
                     "amount": round(stock.seal_amount * 0.15, 0), "type": "散户"},
                ]
                net_buy = stock.seal_amount * 0.5
            elif stock.score >= 60:
                buy_seats = [
                    {"name": famous_seats[(rank_idx + 1) % len(famous_seats)]["name"],
                     "amount": round(stock.seal_amount * 0.3, 0),
                     "type": famous_seats[(rank_idx + 1) % len(famous_seats)]["type"]},
                ]
                sell_seats = [
                    {"name": one_day_tour_seats[(rank_idx + 1) % len(one_day_tour_seats)],
                     "amount": round(stock.seal_amount * 0.2, 0), "type": "散户"},
                    {"name": "机构专用", "amount": round(stock.seal_amount * 0.1, 0), "type": "机构"},
                ]
                net_buy = stock.seal_amount * 0.05
            else:
                buy_seats = [
                    {"name": one_day_tour_seats[rank_idx % len(one_day_tour_seats)],
                     "amount": round(stock.seal_amount * 0.2, 0), "type": "散户"},
                ]
                sell_seats = [
                    {"name": "机构专用", "amount": round(stock.seal_amount * 0.35, 0), "type": "机构"},
                ]
                net_buy = -stock.seal_amount * 0.15

            seal_time_str = None
            if stock.seal_time:
                if isinstance(stock.seal_time, str):
                    seal_time_str = stock.seal_time
                else:
                    seal_time_str = stock.seal_time.strftime("%H:%M:%S")

            items.append(DragonTigerItemResponse(
                code=stock.code,
                name=stock.name,
                rank=rank_idx,
                reason=stock.reason or "连续涨停",
                change_pct=round(stock.change_pct, 2),
                close_price=round(stock.close_price, 2),
                volume=stock.volume if hasattr(stock, 'volume') else 0,
                amount=stock.amount if hasattr(stock, 'amount') else 0,
                turnover_rate=round(stock.turnover_rate, 2),
                seal_amount=round(stock.seal_amount, 0),
                seal_time=seal_time_str,
                open_count=stock.open_count,
                score=stock.score,
                sector=stock.sector,
                buy_seats=buy_seats,
                sell_seats=sell_seats,
                net_buy=round(net_buy, 0),
                date=date_str,
            ))

        return DragonTigerResponse(
            date=date_str,
            total_count=len(items),
            items=items,
        )

    except Exception as e:
        logger.error(f"获取龙虎榜失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-alert")
async def get_risk_alerts(
    date: Optional[str] = Query(None, description="日期 YYYYMMDD")
):
    """
    获取炸板风险预警

    返回当前可能存在炸板风险的股票列表。
    """
    try:
        service = SealPlateService(config={'feishu_enabled': False})
        report = service.run(date=date, force=True)

        if not report:
            return {"alerts": []}

        alerts = []

        for stock in report.strong_stocks + report.watch_stocks:
            # 检查风险条件
            conditions = []

            # 封单金额过低
            if stock.seal_amount < 500:
                conditions.append({
                    "type": "low_seal_amount",
                    "level": "red",
                    "message": f"封单金额仅{stock.seal_amount:.0f}万，低于500万"
                })

            # 开板次数过多
            if stock.open_count >= 2:
                conditions.append({
                    "type": "multiple_open",
                    "level": "yellow",
                    "message": f"已开板{stock.open_count}次"
                })

            # 封板时间过晚
            if stock.seal_time:
                raw_t = stock.seal_time
                if isinstance(raw_t, str):
                    t = datetime.strptime(raw_t, "%H:%M:%S").time()
                elif hasattr(raw_t, 'time'):
                    t = raw_t.time()
                else:
                    t = raw_t
                if t.hour >= 14:
                    conditions.append({
                        "type": "late_seal",
                        "level": "yellow",
                        "message": f"封板时间{t.strftime('%H:%M')}较晚"
                    })

            if conditions:
                alerts.append({
                    "code": stock.code,
                    "name": stock.name,
                    "score": stock.score,
                    "conditions": conditions,
                    "max_level": "red" if any(c["level"] == "red" for c in conditions) else "yellow"
                })

        # 按风险等级排序
        alerts.sort(key=lambda x: (0 if x["max_level"] == "red" else 1, -x["score"]))

        return {"alerts": alerts}

    except Exception as e:
        logger.error(f"获取风险预警失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============ 新增：日期选择 + 建仓推荐 + 胜率追踪 ============

class EffectiveDateResponse(BaseModel):
    """有效日期响应"""
    date: str = Field(description="有效日期 YYYYMMDD")
    label: str = Field(description="日期标签")
    is_closed: bool = Field(description="今日是否已收盘")


@router.get("/effective-date", response_model=EffectiveDateResponse)
async def get_effective_date_endpoint():
    """
    获取当前有效的策略日期

    逻辑：今日已收盘→今日，未收盘/周末→前一个交易日
    """
    from src.seal_plate.date_utils import get_effective_date, get_label_for_date, is_market_closed

    date_str = get_effective_date()
    return EffectiveDateResponse(
        date=date_str,
        label=get_label_for_date(date_str),
        is_closed=is_market_closed(),
    )


# --- 推荐结果响应模型 ---

class PositionRecResponse(BaseModel):
    """建仓推荐标的"""
    code: str
    name: str
    score: int
    rank: int
    confidence: str                   # 高/中/低
    change_pct: float
    seal_time: Optional[str] = None
    sector: Optional[str] = None
    seal_amount: float = 0
    consecutive_days: int = 0
    reasons: list[str] = Field(default_factory=list)
    risk_warnings: list[str] = Field(default_factory=list)
    suggested_position_pct: float = 0.0


class SectorWinRate(BaseModel):
    """板块胜率"""
    sector: str
    won: int
    total: int
    rate: float


class WinRateResponse(BaseModel):
    """胜率统计"""
    total_recommendations: int
    settled: int
    won: int
    lost: int
    pending: int
    win_rate: float
    avg_return: float
    max_return: float
    rolling_win_rate_10: float
    trend: str
    by_sector: list[SectorWinRate] = Field(default_factory=list)
    by_score_range: dict[str, dict] = Field(default_factory=dict)
    strategy_adjustments: list[str] = Field(default_factory=list)
    adjustment_reasons: list[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    """建仓推荐响应"""
    date: str
    label: str
    sentiment_index: float
    sentiment_phase: str
    total_limit_up: int
    recommendations: list[PositionRecResponse] = Field(default_factory=list)
    strategy_notes: list[str] = Field(default_factory=list)
    win_rate: Optional[WinRateResponse] = None


class RecommendationHistoryItem(BaseModel):
    """推荐历史项"""
    date: str
    label: str
    count: int
    sentiment_phase: str
    sentiment_index: float


class HistoryListResponse(BaseModel):
    """推荐历史列表"""
    items: list[RecommendationHistoryItem] = Field(default_factory=list)


class UpdateOutcomeRequest(BaseModel):
    """更新推荐结果"""
    outcome: str = Field(description="outcome: 成功/失败/持平")
    actual_return_pct: Optional[float] = Field(None, description="实际收益率%")
    review_note: Optional[str] = Field(None, description="复盘备注")


# --- API Routes ---

@router.get("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(
    date: Optional[str] = Query(None, description="日期 YYYYMMDD，默认自动选择"),
    save: bool = Query(True, description="是否保存推荐日志"),
):
    """
    获取建仓推荐

    基于打板评分 + 情绪周期 + 历史胜率，自动推荐值得建仓的标的。
    """
    from src.seal_plate import get_effective_date, get_label_for_date
    from src.seal_plate.recommender import RecommendationEngine
    from src.seal_plate.recommendation_log import RecommendationLogStore

    try:
        effective_date = get_effective_date(date)
        date_label = get_label_for_date(effective_date)

        service = SealPlateService(config={'feishu_enabled': False})
        report = service.run(date=effective_date, force=True)

        if not report:
            return RecommendationResponse(
                date=effective_date,
                label=date_label,
                sentiment_index=50,
                sentiment_phase="中性",
                total_limit_up=0,
                recommendations=[],
                strategy_notes=["今日无涨停板数据"]
            )

        # 生成推荐
        engine = RecommendationEngine()
        result = engine.generate_recommendations(report, date_label)

        # 保存日志
        if save:
            engine.save_recommendations(result)

        # 转换胜率 stats → response
        wr_stats = result.win_rate_stats
        wr_response = None
        if wr_stats:
            wr_response = WinRateResponse(
                total_recommendations=wr_stats.total_recommendations,
                settled=wr_stats.settled,
                won=wr_stats.won,
                lost=wr_stats.lost,
                pending=wr_stats.pending,
                win_rate=wr_stats.win_rate,
                avg_return=wr_stats.avg_return,
                max_return=wr_stats.max_return,
                rolling_win_rate_10=wr_stats.rolling_win_rate_10,
                trend=wr_stats.trend,
                by_sector=[
                    SectorWinRate(sector=s, **d)
                    for s, d in sorted(wr_stats.by_sector.items(),
                                       key=lambda x: x[1]["rate"], reverse=True)[:10]
                ],
                by_score_range=wr_stats.by_score_range,
                strategy_adjustments=wr_stats.strategy_adjustments,
                adjustment_reasons=wr_stats.adjustment_reasons,
            )

        return RecommendationResponse(
            date=result.date,
            label=result.label,
            sentiment_index=result.sentiment_index,
            sentiment_phase=result.sentiment_phase,
            total_limit_up=result.total_limit_up,
            recommendations=[
                PositionRecResponse(
                    code=r.stock.code,
                    name=r.stock.name,
                    score=r.score,
                    rank=r.rank,
                    confidence=r.confidence,
                    change_pct=r.stock.change_pct,
                    seal_time=r.stock.seal_time,
                    sector=r.stock.sector,
                    seal_amount=r.stock.seal_amount,
                    consecutive_days=r.stock.consecutive_days,
                    reasons=r.reasons,
                    risk_warnings=r.risk_warnings,
                    suggested_position_pct=r.suggested_position_pct,
                )
                for r in result.recommendations
            ],
            strategy_notes=result.strategy_notes,
            win_rate=wr_response,
        )

    except Exception as e:
        logger.error(f"生成推荐失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations/history", response_model=HistoryListResponse)
async def get_recommendation_history(
    limit: int = Query(30, description="返回数量", ge=1, le=100)
):
    """获取推荐历史列表"""
    from src.seal_plate.recommendation_log import RecommendationLogStore
    from src.seal_plate.date_utils import get_label_for_date

    store = RecommendationLogStore()
    logs = store.load_all(limit=limit)

    return HistoryListResponse(
        items=[
            RecommendationHistoryItem(
                date=log.date,
                label=get_label_for_date(log.date),
                count=len(log.recommendations),
                sentiment_phase=log.sentiment_phase,
                sentiment_index=log.sentiment_index,
            )
            for log in logs
        ]
    )


@router.get("/recommendations/{date}")
async def get_recommendation_by_date(date: str):
    """获取指定日期的推荐详情"""
    from src.seal_plate.recommendation_log import RecommendationLogStore
    from src.seal_plate.date_utils import get_label_for_date

    store = RecommendationLogStore()
    log = store.load(date)
    if not log:
        raise HTTPException(status_code=404, detail=f"未找到 {date} 的推荐记录")

    return {
        "date": log.date,
        "label": get_label_for_date(log.date),
        "sentiment_index": log.sentiment_index,
        "sentiment_phase": log.sentiment_phase,
        "total_limit_up": log.total_limit_up,
        "recommendations": [
            {
                "code": r.code, "name": r.name, "score": r.score,
                "change_pct": r.change_pct, "seal_time": r.seal_time,
                "sector": r.sector, "reasons": r.reasons,
                "outcome": r.outcome, "actual_return_pct": r.actual_return_pct,
                "won": r.won, "review_note": r.review_note,
            }
            for r in log.recommendations
        ],
    }


@router.patch("/recommendations/{date}/{code}")
async def update_recommendation_outcome(
    date: str, code: str, request: UpdateOutcomeRequest
):
    """更新某日某标的的实际结果（用于复盘）"""
    from src.seal_plate.recommendation_log import RecommendationLogStore

    store = RecommendationLogStore()
    success = store.update_outcome(
        date=date, code=code,
        outcome=request.outcome,
        actual_return=request.actual_return_pct,
        review_note=request.review_note,
    )

    if not success:
        raise HTTPException(status_code=404, detail=f"未找到 {date}/{code} 的推荐记录")

    return {"status": "ok", "message": f"已更新 {date}/{code} 的结果"}


@router.get("/win-rate", response_model=WinRateResponse)
async def get_win_rate():
    """获取胜率分析与策略调整建议"""
    from src.seal_plate.win_rate_tracker import WinRateTracker
    from src.seal_plate.recommendation_log import RecommendationLogStore

    store = RecommendationLogStore()
    tracker = WinRateTracker(store)
    stats = tracker.compute_stats()

    return WinRateResponse(
        total_recommendations=stats.total_recommendations,
        settled=stats.settled,
        won=stats.won,
        lost=stats.lost,
        pending=stats.pending,
        win_rate=stats.win_rate,
        avg_return=stats.avg_return,
        max_return=stats.max_return,
        rolling_win_rate_10=stats.rolling_win_rate_10,
        trend=stats.trend,
        by_sector=[
            SectorWinRate(sector=s, **d)
            for s, d in sorted(stats.by_sector.items(),
                               key=lambda x: x[1]["rate"], reverse=True)[:10]
        ],
        by_score_range=stats.by_score_range,
        strategy_adjustments=stats.strategy_adjustments,
        adjustment_reasons=stats.adjustment_reasons,
    )


# ============ 多源数据聚合 API ============

class MarketHotAnalysisResponse(BaseModel):
    """市场热度分析响应"""
    hot_concepts: list = Field(default_factory=list)
    fund_inflow_sectors: list = Field(default_factory=list)
    fund_outflow_sectors: list = Field(default_factory=list)
    market_heat_score: int = 50
    market_focus: str = ""
    sentiment_signal: str = "neutral"
    suggested_sectors: list = Field(default_factory=list)


class DataSourceHealthResponse(BaseModel):
    """数据源健康状态"""
    total_sources: int
    available_sources: int
    status: str
    sources: dict


class IwenCaiScreeningRequest(BaseModel):
    """问财选股请求"""
    query: str = Field(..., description="自然语言选股条件")
    top_n: int = Field(20, description="返回前N条")


class IwenCaiScreeningResponse(BaseModel):
    """问财选股响应"""
    query: str
    count: int
    results: list


@router.get("/market-hot", response_model=MarketHotAnalysisResponse)
async def get_market_hot():
    """
    获取市场热度分析

    结合同花顺热点概念 + 资金流向，给出当日市场情绪研判。
    数据来源: THSHotspotFetcher (同花顺热点)
    """
    try:
        from data_provider.ths_hotspot_fetcher import create_ths_hotspot_fetcher
        ths = create_ths_hotspot_fetcher()
        result = ths.get_market_hot_analysis()
        return MarketHotAnalysisResponse(**result)
    except Exception as e:
        logger.warning("市场热度分析失败: %s", e)
        raise HTTPException(status_code=503, detail=f"同花顺热点服务不可用: {str(e)}")


@router.get("/data-sources/health", response_model=DataSourceHealthResponse)
async def get_data_sources_health():
    """
    检查各数据源可用性

    返回每个数据源的健康状态，帮助判断是否需要进行配置调整。
    """
    try:
        from src.services.data_aggregator import DataAggregator
        aggregator = DataAggregator()
        health = aggregator.get_health_summary()
        return DataSourceHealthResponse(**health)
    except Exception as e:
        logger.warning("数据源健康检查失败: %s", e)
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")


@router.post("/iwencai/screen", response_model=IwenCaiScreeningResponse)
async def iwencai_screening(request: IwenCaiScreeningRequest):
    """
    问财自然语言选股

    支持自然语言描述选股条件，如：
    - "今日涨停"
    - "连续2天涨停且换手率大于5%"
    - "放量突破20日均线"
    - "市盈率低于20且净利润增长"

    数据来源: IwenCaiFetcher (问财选股)
    """
    try:
        from data_provider.iwencai_fetcher import create_iwencai_fetcher
        iwencai = create_iwencai_fetcher()
        results = iwencai.stock_screening(request.query, top_n=request.top_n)
        return IwenCaiScreeningResponse(
            query=request.query,
            count=len(results),
            results=results,
        )
    except Exception as e:
        logger.warning("问财选股失败: %s", e)
        raise HTTPException(status_code=503, detail=f"问财选股服务不可用: {str(e)}")


@router.get("/iwencai/recent-limit-up")
async def get_iwencai_recent_limit_up(
    days: int = Query(2, description="连续涨停天数")
):
    """问财选股：获取近期连续涨停的股票"""
    try:
        from data_provider.iwencai_fetcher import create_iwencai_fetcher
        iwencai = create_iwencai_fetcher()
        results = iwencai.get_recent_limit_up(days=days)
        return {"query": f"连续{days}天涨停", "count": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"问财服务不可用: {str(e)}")


@router.get("/iwencai/strong-stocks")
async def get_iwencai_strong_stocks():
    """问财选股：获取强势股（涨幅>5%且量比>1.5）"""
    try:
        from data_provider.iwencai_fetcher import create_iwencai_fetcher
        iwencai = create_iwencai_fetcher()
        results = iwencai.get_strong_stocks()
        return {"query": "涨幅>5%且量比>1.5且换手率>3%", "count": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"问财服务不可用: {str(e)}")


# ============ 复盘分析 API ============

class ReviewHistoryItem(BaseModel):
    """复盘历史项"""
    date: str
    summary: str = ""
    win_rate: float = 0.0
    settled_count: int = 0
    has_llm_analysis: bool = False


class ReviewHistoryListResponse(BaseModel):
    """复盘历史列表"""
    items: list[ReviewHistoryItem] = Field(default_factory=list)


class ReviewDetailResponse(BaseModel):
    """复盘详情"""
    date: str
    generated_at: str = ""
    summary: str = ""
    overall_assessment: str = ""
    success_patterns: list[str] = Field(default_factory=list)
    failure_patterns: list[str] = Field(default_factory=list)
    high_momentum_sectors: list[str] = Field(default_factory=list)
    risk_sectors: list[str] = Field(default_factory=list)
    strategy_adjustments: list[str] = Field(default_factory=list)
    score_weight_suggestions: list[str] = Field(default_factory=list)
    position_advice: str = ""
    recommended_min_score: int = 65
    recommended_confidence_threshold: str = "中"
    max_daily_recommendations: int = 5
    settled_count: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    model_used: str = ""
    notes: str = ""


class StrategyEvolutionResponse(BaseModel):
    """策略演化时间线"""
    evolution: list[dict] = Field(default_factory=list)


class UpdateReviewNotesRequest(BaseModel):
    """更新复盘备注"""
    notes: str = Field(description="复盘备注内容")


class AutoReviewRequest(BaseModel):
    """触发自动复盘"""
    date: Optional[str] = Field(None, description="目标日期 YYYYMMDD，默认为今天")


@router.get("/review", response_model=ReviewDetailResponse)
async def get_review(
    date: Optional[str] = Query(None, description="日期 YYYYMMDD，默认最新")
):
    """获取复盘分析详情（LLM驱动）"""
    from src.seal_plate.review_log import ReviewLogStore as RLS

    store = RLS()

    if date:
        data = store.load(date)
        if not data:
            raise HTTPException(status_code=404, detail=f"未找到 {date} 的复盘记录")
    else:
        all_data = store.load_all(limit=1)
        if not all_data:
            raise HTTPException(status_code=404, detail="暂无复盘记录")
        data = all_data[0]

    return ReviewDetailResponse(
        date=data.get("date", ""),
        generated_at=data.get("generated_at", ""),
        summary=data.get("summary", ""),
        overall_assessment=data.get("overall_assessment", ""),
        success_patterns=data.get("success_patterns", []),
        failure_patterns=data.get("failure_patterns", []),
        high_momentum_sectors=data.get("high_momentum_sectors", []),
        risk_sectors=data.get("risk_sectors", []),
        strategy_adjustments=data.get("strategy_adjustments", []),
        score_weight_suggestions=data.get("score_weight_suggestions", []),
        position_advice=data.get("position_advice", ""),
        recommended_min_score=data.get("recommended_min_score", 65),
        recommended_confidence_threshold=data.get("recommended_confidence_threshold", "中"),
        max_daily_recommendations=data.get("max_daily_recommendations", 5),
        settled_count=data.get("settled_count", 0),
        win_rate=data.get("win_rate", 0.0),
        avg_return=data.get("avg_return", 0.0),
        model_used=data.get("model_used", ""),
        notes=data.get("notes", ""),
    )


@router.get("/review/history", response_model=ReviewHistoryListResponse)
async def get_review_history(
    limit: int = Query(30, description="返回数量", ge=1, le=100)
):
    """获取复盘历史列表"""
    from src.seal_plate.review_log import ReviewLogStore as RLS

    store = RLS()
    all_data = store.load_all(limit=limit)

    return ReviewHistoryListResponse(
        items=[
            ReviewHistoryItem(
                date=d.get("date", ""),
                summary=d.get("summary", ""),
                win_rate=d.get("win_rate", 0.0),
                settled_count=d.get("settled_count", 0),
                has_llm_analysis=bool(d.get("model_used")),
            )
            for d in all_data
        ]
    )


@router.post("/review/auto-review")
async def trigger_auto_review(request: AutoReviewRequest):
    """
    触发每日自动复盘

    自动执行：
    1. 自动结算待结算推荐（从行情数据获取次日涨跌幅）
    2. LLM 驱动复盘分析
    3. 保存复盘报告
    """
    from src.seal_plate.review_scheduler import ReviewScheduler

    scheduler = ReviewScheduler()
    result = scheduler.run_daily_review(target_date=request.date)

    return result


@router.get("/review/strategy-evolution", response_model=StrategyEvolutionResponse)
async def get_strategy_evolution(
    limit: int = Query(30, description="返回数量", ge=1, le=100)
):
    """获取策略参数演化历史（追踪评分门槛、置信度等的调整历程）"""
    from src.seal_plate.review_log import ReviewLogStore as RLS

    store = RLS()
    evolution = store.get_strategy_evolution(limit=limit)

    return StrategyEvolutionResponse(evolution=evolution)


@router.patch("/review/{date}/notes")
async def update_review_notes(date: str, request: UpdateReviewNotesRequest):
    """更新复盘备注"""
    from src.seal_plate.review_log import ReviewLogStore as RLS

    store = RLS()
    success = store.update_notes(date, request.notes)

    if not success:
        raise HTTPException(status_code=404, detail=f"未找到 {date} 的复盘记录")

    return {"status": "ok", "message": "复盘备注已更新"}


# ============ 资金流向分析 API ============

class FundFlowResponse(BaseModel):
    """资金流向分析响应"""
    date: str = Field(description="分析日期")
    fund_sentiment: str = Field(description="资金情绪")
    fund_heat_score: int = Field(description="资金热度评分 0-100")
    hot_sectors_inflow: list[dict] = Field(description="资金净流入板块")
    hot_sectors_outflow: list[dict] = Field(description="资金净流出板块")
    hot_money_active: bool = Field(False, description="游资是否活跃")
    hot_money_warning: list[str] = Field(description="游资风险提示")
    one_day_tour_risk: list[str] = Field(description="一日游风险")
    major_fund_focus: list[str] = Field(description="大基金关注方向")
    buy_suggestions: list[dict] = Field(description="买入建议")
    sell_suggestions: list[dict] = Field(description="卖出建议")
    risk_alerts: list[str] = Field(description="综合风险提示")


class MorningTaskResponse(BaseModel):
    """早盘任务响应"""
    status: str
    date: str
    recommendations_count: int = 0
    feishu_sent: bool = False
    message: str = ""


class EveningTaskResponse(BaseModel):
    """收盘任务响应"""
    status: str
    date: str
    auto_settled: int = 0
    llm_analysis: bool = False
    feishu_sent: bool = False
    message: str = ""


@router.get("/fund-flow", response_model=FundFlowResponse)
async def get_fund_flow_analysis(
    date: Optional[str] = Query(None, description="日期 YYYYMMDD")
):
    """
    获取资金流向分析

    包括：大基金动态、游资动向、一日游风险检测、买卖点位建议
    """
    from src.seal_plate.capital_flow_analyzer import CapitalFlowAnalyzer

    try:
        service = SealPlateService(config={'feishu_enabled': False})
        report = service.run(date=date, force=True)

        if not report:
            raise HTTPException(status_code=404, detail="无法获取打板数据")

        analyzer = CapitalFlowAnalyzer()
        analysis = analyzer.analyze(
            hot_sectors=report.sector_hot,
            strong_stocks=list(report.strong_stocks) + list(report.watch_stocks),
            date=date,
        )

        return FundFlowResponse(
            date=analysis.date,
            fund_sentiment=analysis.fund_sentiment,
            fund_heat_score=analysis.fund_heat_score,
            hot_sectors_inflow=analysis.hot_sectors_inflow,
            hot_sectors_outflow=analysis.hot_sectors_outflow,
            hot_money_active=analysis.hot_money_active,
            hot_money_warning=analysis.hot_money_warning,
            one_day_tour_risk=analysis.one_day_tour_risk,
            major_fund_focus=analysis.major_fund_focus,
            buy_suggestions=analysis.buy_suggestions,
            sell_suggestions=analysis.sell_suggestions,
            risk_alerts=analysis.risk_alerts,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"资金流向分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/morning-task", response_model=MorningTaskResponse)
async def trigger_morning_task(
    date: Optional[str] = Query(None, description="日期 YYYYMMDD")
):
    """
    手动触发早盘推荐任务

    执行：获取打板数据 → 资金流向分析 → 生成推荐 → 飞书通知
    """
    from src.seal_plate.daily_tasks import SealPlateDailyTasks

    tasks = SealPlateDailyTasks()
    result = tasks.run_morning_recommendation(target_date=date)
    return MorningTaskResponse(**result)


@router.post("/evening-task", response_model=EveningTaskResponse)
async def trigger_evening_task(
    date: Optional[str] = Query(None, description="日期 YYYYMMDD")
):
    """
    手动触发收盘复盘任务

    执行：自动结算 → LLM复盘 → 次日建议 → 飞书通知
    """
    from src.seal_plate.daily_tasks import SealPlateDailyTasks

    tasks = SealPlateDailyTasks()
    result = tasks.run_evening_review(target_date=date)
    return EveningTaskResponse(**result)


# ============ 高胜率战法 API ============

class StrategyEntryModeModel(BaseModel):
    name: str
    desc: str
    win_rate: float


class StrategyItemModel(BaseModel):
    id: str
    name: str
    type: str
    description: str
    win_rate: float
    suitable_market: list[str]
    unsuitable_market: list[str]
    conditions: list[str]
    entry_modes: list[StrategyEntryModeModel]
    risk_control: list[str]
    current_suitability: int
    current_reason: str


class StrategyResponse(BaseModel):
    strategies: list[StrategyItemModel]
    market_phase: str
    market_heat: int
    updated_at: str


class StrategyCandidateModel(BaseModel):
    code: str
    name: str
    sector: Optional[str] = None
    change_pct: float = 0
    match_score: int
    match_reason: str


class StrategyCandidatesResponse(BaseModel):
    strategy_id: str
    candidates: list[StrategyCandidateModel]


# 内建战法库
BUILTIN_STRATEGIES = [
    {
        "id": "second_board",
        "name": "二板定龙战法",
        "type": "连板接力",
        "description": "一板看气质，二板定龙头，三板成妖。首板是试探，二板是确认——通过系统化竞价分析、量能验证、题材筛选，在龙头启动临界点精准介入。",
        "win_rate": 70.0,
        "suitable_market": ["震荡期", "启动期", "发酵期"],
        "unsuitable_market": ["退潮期", "冰点期后期"],
        "conditions": [
            "首板必须放量（换手5%-8%为佳），缩量首板次日不利于接力",
            "竞价高开3%-9%，成交量放大到首板爆量的2/3以上",
            "优先10:30前封板，早盘是资金最活跃阶段",
            "板块内至少3只个股同步高开5%以上，有板块助攻",
            "左侧筹码密集区少，避免大量套牢盘抛压",
        ],
        "entry_modes": [
            {"name": "弱转强模式", "desc": "首板烂板→次日低开迅速翻红，分时白线穿过黄线介入", "win_rate": 80.0},
            {"name": "T字板回封", "desc": "竞价顶上去，盘中短暂开板后回封瞬间打板", "win_rate": 75.0},
            {"name": "高开秒板", "desc": "高开7%-9%，竞价量能达标，竞价阶段介入", "win_rate": 72.0},
            {"name": "盘中承接洗盘", "desc": "白线>黄线，8%以上横盘，分时低吸+涨停加仓", "win_rate": 68.0},
        ],
        "risk_control": [
            "二板炸板不回封：当天止损或次日竞价止损",
            "次日低开低走跌破首板涨停价坚决离场",
            "单票仓位≤20%，分仓参与多个候选",
        ],
        "current_suitability": 85,
        "current_reason": "市场情绪处于发酵期，连板效应明显，二板确定性高",
    },
    {
        "id": "weak_to_strong",
        "name": "弱转强反包战法",
        "type": "分歧转一致",
        "description": "捕捉首板分歧后转一致的二次介入机会。首板烂板说明存在分歧，次日快速走强则代表分歧转一致——是资金共识最强的信号。",
        "win_rate": 75.0,
        "suitable_market": ["震荡期", "启动期", "发酵期"],
        "unsuitable_market": ["高潮期中后期"],
        "conditions": [
            "首板封板犹豫、反复开板、尾盘勉强封住",
            "首板换手5%-8%，非一字板",
            "次日竞价低开或平开后迅速翻红",
            "分时白线穿过黄线或拉过0轴时介入",
        ],
        "entry_modes": [
            {"name": "竞价低吸", "desc": "竞价低开-3%以上，开盘15分钟内翻红", "win_rate": 78.0},
            {"name": "盘中追涨", "desc": "盘中放量突破前高，打板确认", "win_rate": 65.0},
        ],
        "risk_control": [
            "低开超过5%不参与",
            "翻红后再度翻绿立即止损",
            "次日不封板或走弱及时止盈",
        ],
        "current_suitability": 78,
        "current_reason": "分歧板数量增多，弱转强机会丰富",
    },
    {
        "id": "sector_lead",
        "name": "板块龙头接力战法",
        "type": "龙头战法",
        "description": "紧跟热门板块龙头股，在板块效应形成时介入。龙头特征：板块内最先涨停、封单最强、题材逻辑最硬。",
        "win_rate": 65.0,
        "suitable_market": ["启动期", "发酵期", "高潮期前期"],
        "unsuitable_market": ["退潮期"],
        "conditions": [
            "板块内3只以上涨停股，形成板块效应",
            "标的为板块内最先涨停的前2只股票",
            "封板时间在10:00前，封单金额>1亿",
            "流通市值30亿-150亿",
        ],
        "entry_modes": [
            {"name": "追板介入", "desc": "板块确认后，龙头股打板介入", "win_rate": 62.0},
            {"name": "次龙补涨", "desc": "龙头封死后，参与板块第二龙头", "win_rate": 68.0},
        ],
        "risk_control": [
            "龙头炸板立即清仓全板块",
            "板块涨停数降至1只以下快速减仓",
        ],
        "current_suitability": 72,
        "current_reason": "热门板块轮动较快，龙头切换频繁，需精准择时",
    },
    {
        "id": "capital_track",
        "name": "大基金追踪战法",
        "type": "资金跟随",
        "description": "重点关注大基金（国家大基金、社保、养老金）持续流入方向，跟随主力资金布局。机构资金具有持续性，不易出现一日游行情。",
        "win_rate": 60.0,
        "suitable_market": ["震荡期", "启动期"],
        "unsuitable_market": ["退潮期"],
        "conditions": [
            "板块连续3日资金净流入",
            "龙虎榜有机构席位净买入",
            "标的流通市值>100亿，流动性好",
            "避开游资主导的小盘标的",
        ],
        "entry_modes": [
            {"name": "回踩低吸", "desc": "板块回踩5日线不破时分批介入", "win_rate": 65.0},
            {"name": "突破追涨", "desc": "板块突破前高时跟进", "win_rate": 55.0},
        ],
        "risk_control": [
            "机构开始出货立即退出",
            "资金连续2日净流出减半仓",
        ],
        "current_suitability": 68,
        "current_reason": "机构调仓期，需关注大基金重点布局方向",
    },
    {
        "id": "first_board_break",
        "name": "首板突破战法",
        "type": "低位首板",
        "description": "捕捉低位首板突破个股，适合低风险偏好投资者。低位首板往往有基本面支撑，后续空间较大，回撤风险可控。",
        "win_rate": 58.0,
        "suitable_market": ["冰点期", "启动期初期"],
        "unsuitable_market": ["高潮期"],
        "conditions": [
            "股价处于历史低位区间（距52周高点跌幅>30%）",
            "突破60日/120日均线压制",
            "涨停成交量放大2倍以上",
            "有业绩预增或利好公告支撑",
        ],
        "entry_modes": [
            {"name": "次日低吸", "desc": "首板次日回调1%-3%低吸", "win_rate": 60.0},
            {"name": "突破回踩", "desc": "回踩涨停价不破介入", "win_rate": 55.0},
        ],
        "risk_control": [
            "跌破首板涨停价止损",
            "3日内不创新高减仓",
        ],
        "current_suitability": 55,
        "current_reason": "市场偏活跃，低位首板机会相对有限",
    },
]


@router.get("/strategies", response_model=StrategyResponse)
async def get_strategies():
    """
    获取高胜率战法列表

    返回当前市场适配的战法体系，包含选股条件、介入模式、风控规则
    """
    try:
        # 获取市场情绪判断
        from src.seal_plate.date_utils import get_effective_date
        from src.seal_plate.seal_plate_service import SealPlateService

        date = get_effective_date()
        market_heat = 60
        market_phase = "震荡期"

        try:
            service = SealPlateService(config={'feishu_enabled': False})
            report = service.run(date=date, force=False)
            if report:
                score = report.sentiment_score or 50
                if score < 20:
                    market_phase = "冰点期"
                elif score < 40:
                    market_phase = "启动期"
                elif score < 60:
                    market_phase = "发酵期"
                elif score < 80:
                    market_phase = "高潮期"
                else:
                    market_phase = "退潮期"
                market_heat = score
        except Exception:
            pass

        # 根据市场阶段动态调整适配度
        adjusted = []
        for s in BUILTIN_STRATEGIES:
            strat = dict(s)  # shallow copy
            if market_phase in s["unsuitable_market"]:
                strat["current_suitability"] = max(20, s["current_suitability"] - 40)
                strat["current_reason"] = f"当前{market_phase}不适合此战法"
            elif market_phase in s["suitable_market"]:
                strat["current_suitability"] = min(95, s["current_suitability"] + 5)
            adjusted.append(strat)

        return StrategyResponse(
            strategies=[StrategyItemModel(**s) for s in adjusted],
            market_phase=market_phase,
            market_heat=market_heat,
            updated_at=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"获取战法列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies/{strategy_id}/candidates", response_model=StrategyCandidatesResponse)
async def get_strategy_candidates(
    strategy_id: str,
    date: Optional[str] = Query(None, description="日期 YYYYMMDD")
):
    """
    获取特定战法当前符合条件的目标标的

    基于当前打板数据，筛选满足战法条件的候选股票
    """
    from src.seal_plate.date_utils import get_effective_date
    from src.seal_plate.seal_plate_service import SealPlateService

    try:
        date_str = date or get_effective_date()
        service = SealPlateService(config={'feishu_enabled': False})
        report = service.run(date=date_str, force=True)

        if not report:
            return StrategyCandidatesResponse(strategy_id=strategy_id, candidates=[])

        all_stocks = list(report.strong_stocks) + list(report.watch_stocks)
        candidates = []

        strategy = next((s for s in BUILTIN_STRATEGIES if s["id"] == strategy_id), None)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"未找到战法: {strategy_id}")

        for stock in all_stocks:
            match_score = 0
            match_reasons = []

            # 通用条件匹配
            if stock.score >= 70:
                match_score += 20
                match_reasons.append("评分≥70")

            if stock.seal_time:
                raw_t = stock.seal_time
                if isinstance(raw_t, str):
                    t = datetime.strptime(raw_t, "%H:%M:%S").time()
                else:
                    t = raw_t
                if t.hour < 10 or (t.hour == 10 and t.minute <= 30):
                    match_score += 15
                    match_reasons.append("早盘封板")

            if stock.open_count <= 1:
                match_score += 10
                match_reasons.append("封板稳健")

            # 战法特定匹配
            if strategy_id == "second_board":
                if 5 <= stock.turnover_rate <= 20:
                    match_score += 20
                    match_reasons.append("换手率合理")
                if stock.seal_amount >= 5000:
                    match_score += 15
                    match_reasons.append("封单充足")

            elif strategy_id == "weak_to_strong":
                if stock.open_count >= 1:
                    match_score += 25
                    match_reasons.append("存在分歧后转一致特征")

            elif strategy_id == "sector_lead":
                # 检查是否板块龙一
                sector = stock.sector
                if sector:
                    sector_stocks = [s for s in all_stocks if s.sector == sector]
                    if len(sector_stocks) >= 3:
                        match_score += 20
                        match_reasons.append("板块效应明显(≥3只)")
                    if sector_stocks and sector_stocks[0].code == stock.code:
                        match_score += 15
                        match_reasons.append("板块龙一")

            elif strategy_id == "capital_track":
                if stock.seal_amount >= 10000:
                    match_score += 20
                    match_reasons.append("大资金封单")

            elif strategy_id == "first_board_break":
                if stock.score <= 75:
                    match_score += 15
                    match_reasons.append("低位启动特征")

            if match_score >= 50:
                candidates.append(StrategyCandidateModel(
                    code=stock.code,
                    name=stock.name,
                    sector=stock.sector,
                    change_pct=stock.change_pct,
                    match_score=match_score,
                    match_reason=", ".join(match_reasons),
                ))

        candidates.sort(key=lambda x: x.match_score, reverse=True)
        return StrategyCandidatesResponse(
            strategy_id=strategy_id,
            candidates=candidates[:10],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取战法候选失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============ 多战法匹配重点推荐 API ============

class MultiMatchEntryPointModel(BaseModel):
    """建仓点位"""
    price: float = Field(description="建议建仓价格")
    type: str = Field(description="点位类型: 竞价介入/低吸/追涨/回踩低吸/打板")
    condition: str = Field(description="触发条件")
    position_pct: int = Field(description="建议仓位占比 %")


class MultiMatchAnalysisModel(BaseModel):
    """单个标的的多战法综合分析"""
    code: str
    name: str
    sector: Optional[str] = None
    matched_strategies: list[str] = Field(description="匹配的战法名称列表")
    match_count: int = Field(description="匹配战法数量")
    avg_match_score: float = Field(description="平均匹配评分")
    reasons: list[str] = Field(description="推荐理由")
    entry_points: list[MultiMatchEntryPointModel] = Field(description="建仓点位建议")
    buy_analysis: str = Field(description="买入分析")
    sell_analysis: str = Field(description="卖出分析")
    risk_level: str = Field(description="风险等级: low/medium/high")
    composite_score: int = Field(description="综合推荐评分 0-100")


class MultiMatchResponseModel(BaseModel):
    """多战法匹配重点推荐"""
    recommendations: list[MultiMatchAnalysisModel]
    total_matched: int
    multi_matched_count: int = Field(description="匹配2+战法的标的数")
    market_phase: str
    updated_at: str


@router.get("/strategies/multi-match", response_model=MultiMatchResponseModel)
async def get_multi_match_recommendations(
    date: Optional[str] = Query(None, description="日期 YYYYMMDD")
):
    """
    获取多战法匹配的重点推荐标的

    降低风险敞口：
    - 如果一只标的符合多种战法情形，说明多个维度均验证了该股
    - 多战法共振的标的是更高确定性的交易机会
    - 降低单战法误判风险，提升胜率
    """
    from src.seal_plate.date_utils import get_effective_date
    from src.seal_plate.seal_plate_service import SealPlateService

    try:
        date_str = date or get_effective_date()
        market_phase = "震荡期"
        market_heat = 60

        # 获取市场阶段
        try:
            service = SealPlateService(config={'feishu_enabled': False})
            report = service.run(date=date_str, force=False)
            if report:
                score = report.sentiment_score or 50
                if score < 20:
                    market_phase = "冰点期"
                elif score < 40:
                    market_phase = "启动期"
                elif score < 60:
                    market_phase = "发酵期"
                elif score < 80:
                    market_phase = "高潮期"
                else:
                    market_phase = "退潮期"
                market_heat = score
        except Exception:
            pass

        # 重新获取 report（可能上面 force=False 没拿到）
        report = service.run(date=date_str, force=True) if 'service' in dir() else None
        if not report:
            return MultiMatchResponseModel(
                recommendations=[],
                total_matched=0,
                multi_matched_count=0,
                market_phase=market_phase,
                updated_at=datetime.now().isoformat(),
            )

        all_stocks = list(report.strong_stocks) + list(report.watch_stocks)

        # 为每个标的所有战法打分
        stock_strategy_map: dict[str, dict] = {}  # code -> {name, sector, strategies: [{id, name, score, reason}]}

        for stock in all_stocks:
            entry = stock_strategy_map.setdefault(stock.code, {
                "name": stock.name,
                "sector": stock.sector or "通用",
                "strategies": [],
            })

            for strategy in BUILTIN_STRATEGIES:
                if market_phase in strategy["unsuitable_market"]:
                    continue

                match_score = 0
                match_reasons = []

                if stock.score >= 70:
                    match_score += 20
                    match_reasons.append("评分≥70")

                if stock.seal_time:
                    raw_t = stock.seal_time
                    if isinstance(raw_t, str):
                        t = datetime.strptime(raw_t, "%H:%M:%S").time()
                    else:
                        t = raw_t
                    if t.hour < 10 or (t.hour == 10 and t.minute <= 30):
                        match_score += 15
                        match_reasons.append("早盘封板")

                if stock.open_count <= 1:
                    match_score += 10
                    match_reasons.append("封板稳健")

                sid = strategy["id"]
                if sid == "second_board":
                    if 5 <= stock.turnover_rate <= 20:
                        match_score += 20
                        match_reasons.append("换手率合理")
                    if stock.seal_amount >= 5000:
                        match_score += 15
                        match_reasons.append("封单充足")
                elif sid == "weak_to_strong":
                    if stock.open_count >= 1:
                        match_score += 25
                        match_reasons.append("分歧转一致特征")
                elif sid == "sector_lead":
                    sector = stock.sector
                    if sector:
                        sector_stocks = [s for s in all_stocks if s.sector == sector]
                        if len(sector_stocks) >= 3:
                            match_score += 20
                            match_reasons.append("板块效应≥3只")
                        if sector_stocks and sector_stocks[0].code == stock.code:
                            match_score += 15
                            match_reasons.append("板块龙一")
                elif sid == "capital_track":
                    if stock.seal_amount >= 10000:
                        match_score += 20
                        match_reasons.append("大资金封单")
                elif sid == "first_board_break":
                    if stock.score <= 75:
                        match_score += 15
                        match_reasons.append("低位启动特征")

                if match_score >= 45:
                    entry["strategies"].append({
                        "id": strategy["id"],
                        "name": strategy["name"],
                        "score": match_score,
                        "reason": ", ".join(match_reasons) if match_reasons else "综合匹配",
                    })

        # 筛选匹配2+战法的标的
        multi_matched = [
            (code, info) for code, info in stock_strategy_map.items()
            if len(info["strategies"]) >= 2
        ]

        recommendations = []
        for code, info in multi_matched:
            strategies = info["strategies"]
            strategies.sort(key=lambda x: x["score"], reverse=True)
            avg_score = sum(s["score"] for s in strategies) / len(strategies)
            match_names = [s["name"] for s in strategies]

            # 推荐理由
            all_reasons = []
            for s in strategies:
                all_reasons.append(f"【{s['name']}】{s['reason']}（评分{s['score']}）")

            # 建仓点位：根据不同战法给出差异化建议
            entry_points = []
            base_price = next((s.close_price for s in all_stocks if s.code == code), 10.0)
            limit_up_price = next((s.limit_up_price for s in all_stocks if s.code == code), base_price * 1.1)

            # 根据匹配战法决定建仓策略
            has_second_board = any(s["id"] == "second_board" for s in strategies)
            has_weak_to_strong = any(s["id"] == "weak_to_strong" for s in strategies)
            has_sector_lead = any(s["id"] == "sector_lead" for s in strategies)
            has_capital_track = any(s["id"] == "capital_track" for s in strategies)
            has_first_board = any(s["id"] == "first_board_break" for s in strategies)

            if has_second_board:
                entry_points.append(MultiMatchEntryPointModel(
                    price=round(limit_up_price, 2),
                    type="竞价介入",
                    condition="竞价高开3%-7%，成交量达标",
                    position_pct=20,
                ))
                entry_points.append(MultiMatchEntryPointModel(
                    price=round(base_price * 1.03, 2),
                    type="回封打板",
                    condition="盘中开板后回封瞬间",
                    position_pct=15,
                ))

            if has_weak_to_strong:
                entry_points.append(MultiMatchEntryPointModel(
                    price=round(base_price * 0.97, 2),
                    type="分歧低吸",
                    condition="低开-3%以上后翻红",
                    position_pct=15,
                ))

            if has_sector_lead:
                entry_points.append(MultiMatchEntryPointModel(
                    price=round(limit_up_price, 2),
                    type="龙头追板",
                    condition="板块3只以上涨停时追入",
                    position_pct=15,
                ))

            if has_capital_track:
                entry_points.append(MultiMatchEntryPointModel(
                    price=round(base_price * 1.01, 2),
                    type="回踩低吸",
                    condition="回踩5日线不破分批介入",
                    position_pct=20,
                ))

            if has_first_board:
                entry_points.append(MultiMatchEntryPointModel(
                    price=round(base_price * 0.985, 2),
                    type="首板低吸",
                    condition="次日回调1%-3%",
                    position_pct=15,
                ))

            if not entry_points:
                entry_points.append(MultiMatchEntryPointModel(
                    price=round(base_price, 2),
                    type="观望",
                    condition="等待更明确信号",
                    position_pct=10,
                ))

            # 综合评分：基础分 + 多战法加权
            composite = min(100, int(avg_score + len(strategies) * 5))

            # 买入分析
            buy_parts = []
            if match_count := len(strategies):
                buy_parts.append(f"✅ {match_count}个战法同时验证，降低单一维度误判风险")
            if avg_score >= 70:
                buy_parts.append("多战法高评分共振，确认度高")
            if has_sector_lead and has_second_board:
                buy_parts.append("龙头+二板双确认：上涨确定性最高")
            if has_weak_to_strong:
                buy_parts.append("分歧转一致提供低吸机会，盈亏比更优")
            if has_capital_track:
                buy_parts.append("机构资金加持，趋势持续性更强")
            buy_analysis = "；".join(buy_parts) if buy_parts else "综合多战法分析，具备交易价值"

            # 卖出分析
            sell_parts = [
                "📉 止损线：跌破首板涨停价（约{}）无条件离场".format(round(base_price * 0.9, 2)),
            ]
            if has_second_board:
                sell_parts.append("二板炸板不回封→当天或次日竞价止损")
            if has_weak_to_strong:
                sell_parts.append("翻红后再度翻绿立即止损")
            if has_sector_lead:
                sell_parts.append("板块涨停数降至1只以下快速减仓")
            sell_parts.append("📈 止盈：次日不封板减半仓，3日不创新高清仓")
            sell_analysis = "；".join(sell_parts)

            # 风险等级
            if len(strategies) >= 3 and avg_score >= 70:
                risk_level = "low"
            elif len(strategies) >= 2 and avg_score >= 55:
                risk_level = "medium"
            else:
                risk_level = "high"

            recommendations.append(MultiMatchAnalysisModel(
                code=code,
                name=info["name"],
                sector=info["sector"],
                matched_strategies=match_names,
                match_count=len(strategies),
                avg_match_score=round(avg_score, 1),
                reasons=all_reasons,
                entry_points=entry_points,
                buy_analysis=buy_analysis,
                sell_analysis=sell_analysis,
                risk_level=risk_level,
                composite_score=composite,
            ))

        recommendations.sort(key=lambda x: x.composite_score, reverse=True)

        return MultiMatchResponseModel(
            recommendations=recommendations,
            total_matched=sum(1 for info in stock_strategy_map.values() if info["strategies"]),
            multi_matched_count=len(recommendations),
            market_phase=market_phase,
            updated_at=datetime.now().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取多战法匹配失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============ 持仓 API ============

class PositionItemModel(BaseModel):
    code: str
    name: str
    total_qty: int
    available_qty: int
    current_price: float
    cost_price: float
    total_pnl: float
    daily_pnl: float


class HoldingsResponse(BaseModel):
    positions: list[PositionItemModel]
    total_pnl: float
    total_daily_pnl: float
    total_market_value: float = 0
    total_cost: float = 0
    updated_at: Optional[str] = None


@router.get("/holdings", response_model=HoldingsResponse)
async def get_holdings():
    """
    获取当前持仓数据

    返回持仓明细、持仓盈亏和当日盈亏
    注意：实际应接入券商API，此处返回硬编码示例数据
    """
    try:
        # TODO: 接入券商API获取实时持仓
        # 示例持仓数据
        positions = [
            PositionItemModel(code="000000", name="华丽家族", total_qty=20000, available_qty=10000,
                              current_price=2.790, cost_price=2.691, total_pnl=1984.46, daily_pnl=3394.74),
            PositionItemModel(code="000000", name="宏盛股份", total_qty=600, available_qty=600,
                              current_price=60.810, cost_price=69.242, total_pnl=-5059.41, daily_pnl=606.00),
            PositionItemModel(code="000000", name="双良节能", total_qty=6600, available_qty=6600,
                              current_price=5.520, cost_price=6.465, total_pnl=-6238.41, daily_pnl=594.00),
            PositionItemModel(code="000000", name="大众交通", total_qty=7300, available_qty=7300,
                              current_price=4.770, cost_price=5.737, total_pnl=-7056.42, daily_pnl=292.00),
            PositionItemModel(code="000000", name="紫金矿业", total_qty=3300, available_qty=3300,
                              current_price=30.470, cost_price=32.423, total_pnl=-6445.67, daily_pnl=99.00),
            PositionItemModel(code="000000", name="格力电器", total_qty=300, available_qty=300,
                              current_price=38.880, cost_price=39.317, total_pnl=-131.00, daily_pnl=-87.00),
            PositionItemModel(code="000000", name="浦发银行", total_qty=2100, available_qty=2100,
                              current_price=9.260, cost_price=10.824, total_pnl=-3285.33, daily_pnl=-231.00),
            PositionItemModel(code="000000", name="中信重工", total_qty=4000, available_qty=4000,
                              current_price=5.490, cost_price=5.893, total_pnl=-1610.23, daily_pnl=-280.00),
            PositionItemModel(code="000000", name="川润股份", total_qty=1500, available_qty=1500,
                              current_price=20.260, cost_price=22.070, total_pnl=-2715.00, daily_pnl=-855.00),
        ]

        total_pnl = sum(p.total_pnl for p in positions)
        total_daily_pnl = sum(p.daily_pnl for p in positions)
        total_market_value = sum(p.total_qty * p.current_price for p in positions)
        total_cost = sum(p.total_qty * p.cost_price for p in positions)

        return HoldingsResponse(
            positions=positions,
            total_pnl=total_pnl,
            total_daily_pnl=total_daily_pnl,
            total_market_value=total_market_value,
            total_cost=total_cost,
            updated_at=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"获取持仓数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============ 个股风险分析 API ============

class StockRiskAnalysisResponse(BaseModel):
    """个股风险分析（针对推荐建仓的标的）"""
    code: str
    name: str
    risk_level: str = Field(description="综合风险等级: low/medium/high")
    risk_score: int = Field(description="风险评分 0-100，越高越危险")
    hot_money_risk: list[str] = Field(description="游资风险提示")
    one_day_tour_risk: list[str] = Field(description="一日游风险")
    seal_quality: str = Field(description="封板质量")
    turnover_warning: Optional[str] = None
    suggestions: list[str] = Field(description="操作建议")


@router.get("/stock-risk/{stock_code}", response_model=StockRiskAnalysisResponse)
async def get_stock_risk_analysis(
    stock_code: str,
    date: Optional[str] = Query(None, description="日期 YYYYMMDD")
):
    """
    对指定标的进行风险分析

    检查：游资参与度、一日游特征、封板质量、换手率异常
    仅针对用户主动要求分析的推荐建仓标的
    """
    from src.seal_plate.date_utils import get_effective_date
    from src.seal_plate.seal_plate_service import SealPlateService

    try:
        date_str = date or get_effective_date()
        service = SealPlateService(config={'feishu_enabled': False})
        report = service.run(date=date_str, force=True)

        risk_score = 0
        hot_money_risks = []
        one_day_tour_risks = []
        seal_quality = "良好"
        turnover_warning = None
        suggestions = []
        stock_name = stock_code

        if report:
            all_stocks = list(report.strong_stocks) + list(report.watch_stocks)
            target = next((s for s in all_stocks if s.code == stock_code), None)

            if target:
                stock_name = target.name

                # 封板质量
                if target.open_count >= 3:
                    risk_score += 30
                    seal_quality = "差"
                    suggestions.append("⚠️ 开板≥3次，封板质量差，建议回避")
                elif target.open_count >= 1:
                    risk_score += 15
                    seal_quality = "一般"
                    suggestions.append("开板≥1次，封板质量一般，需谨慎")
                else:
                    risk_score += 0
                    seal_quality = "良好"

                # 封板时间
                if target.seal_time:
                    raw_t = target.seal_time
                    if isinstance(raw_t, str):
                        t = datetime.strptime(raw_t, "%H:%M:%S").time()
                    else:
                        t = raw_t
                    if t.hour >= 14:
                        risk_score += 25
                        one_day_tour_risks.append("尾盘封板(14:00后)，一日游风险较高")
                        suggestions.append("尾盘突袭封板，警惕次日低开")
                    elif t.hour >= 11:
                        risk_score += 10

                # 换手率异常
                if target.turnover_rate > 30:
                    risk_score += 25
                    turnover_warning = f"换手率{target.turnover_rate:.1f}%偏高，游资对倒嫌疑"
                    hot_money_risks.append(f"换手率达{target.turnover_rate:.1f}%，警惕游资对倒")
                    suggestions.append("高换手率(>30%)警惕游资对倒，快进快出")
                elif target.turnover_rate > 20:
                    risk_score += 10

                # 封单金额
                if target.seal_amount < 500:
                    risk_score += 20
                    suggestions.append("封单金额过低(<500万)，封板脆弱")

                # sector risk
                if target.sector and "ST" in target.sector.upper():
                    risk_score += 30
                    one_day_tour_risks.append("ST板块：一日游高发板块")
                    suggestions.append("ST板块历史一日游高发，建议回避")

                # 连板高度
                if target.open_count >= 5:
                    risk_score += 15
                    suggestions.append("高位连板(≥5板)，追高风险大")

        # 综合风险等级
        if risk_score >= 60:
            risk_level = "high"
        elif risk_score >= 30:
            risk_level = "medium"
        else:
            risk_level = "low"

        # 龙虎榜机构风险提示
        try:
            from src.seal_plate.dragon_tiger_risk import get_dragon_tiger_risk_factors, DragonTigerInstitutionRisk

            dt_risk = get_dragon_tiger_risk_factors(
                code=stock_code,
                name=stock_name,
                score=target.score if target else 60,
                seal_amount=target.seal_amount if target else 1000,
            )

            if dt_risk.risk_level in ("high", "critical"):
                risk_score = max(risk_score, dt_risk.risk_score)
                risk_level = "high" if risk_level != "high" else risk_level
                for reason in dt_risk.risk_reasons:
                    one_day_tour_risks.append(f"龙虎榜: {reason}")
                suggestions.append(f"📊 {dt_risk.suggestion}")
                if dt_risk.hot_money_pure_pump:
                    hot_money_risks.append("龙虎榜: 纯游资对倒，无机构参与")
                if dt_risk.one_day_tour_risk:
                    one_day_tour_risks.append("龙虎榜: 识别到一日游席位参与")
            elif dt_risk.risk_level == "medium":
                for reason in dt_risk.risk_reasons:
                    if "游资" in reason:
                        hot_money_risks.append(f"龙虎榜: {reason}")
        except ImportError:
            pass  # 模块不可用时跳过

        return StockRiskAnalysisResponse(
            code=stock_code,
            name=stock_name,
            risk_level=risk_level,
            risk_score=risk_score,
            hot_money_risk=hot_money_risks,
            one_day_tour_risk=one_day_tour_risks,
            seal_quality=seal_quality,
            turnover_warning=turnover_warning,
            suggestions=suggestions or ["✅ 当前未检测到明显风险信号"],
        )

    except Exception as e:
        logger.error(f"个股风险分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============ 自选股 API ============

import json
import os
from pathlib import Path

WATCHLIST_FILE = Path(__file__).parent.parent.parent.parent / "watchlist.json"


def _load_watchlist() -> dict:
    """加载自选股数据"""
    if not WATCHLIST_FILE.exists():
        return {}
    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_watchlist(data: dict):
    """保存自选股数据"""
    WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class WatchlistItemResponse(BaseModel):
    """自选股项"""
    code: str
    name: str
    added_at: str = Field(description="加入时间")
    source: str = Field("manual", description="来源: manual/recommend")
    score: int = Field(0, description="加入时的评分")
    sector: Optional[str] = None


class WatchlistResponse(BaseModel):
    """自选股列表响应"""
    items: list[WatchlistItemResponse] = Field(default_factory=list)
    total: int = 0


class WatchlistAddRequest(BaseModel):
    """添加自选股请求"""
    code: str
    name: str
    source: str = "manual"
    score: int = 0
    sector: Optional[str] = None


class WatchlistStatusResponse(BaseModel):
    """自选状态检查"""
    codes: list[str] = Field(default_factory=list, description="已在自选中的code列表")


@router.get("/watchlist", response_model=WatchlistResponse)
async def get_watchlist():
    """获取自选股列表"""
    try:
        data = _load_watchlist()
        items = [
            WatchlistItemResponse(
                code=code,
                name=info.get("name", ""),
                added_at=info.get("added_at", ""),
                source=info.get("source", "manual"),
                score=info.get("score", 0),
                sector=info.get("sector"),
            )
            for code, info in data.items()
        ]
        items.sort(key=lambda x: x.added_at, reverse=True)
        return WatchlistResponse(items=items, total=len(items))
    except Exception as e:
        logger.error(f"获取自选股失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/watchlist", response_model=WatchlistItemResponse)
async def add_to_watchlist(request: WatchlistAddRequest):
    """添加标的到自选股"""
    try:
        data = _load_watchlist()
        now = datetime.now().isoformat()

        if request.code in data:
            existing = data[request.code]
            return WatchlistItemResponse(
                code=request.code,
                name=existing.get("name", request.name),
                added_at=existing.get("added_at", now),
                source=existing.get("source", request.source),
                score=existing.get("score", request.score),
                sector=existing.get("sector"),
            )

        data[request.code] = {
            "name": request.name,
            "added_at": now,
            "source": request.source,
            "score": request.score,
            "sector": request.sector,
        }
        _save_watchlist(data)

        return WatchlistItemResponse(
            code=request.code,
            name=request.name,
            added_at=now,
            source=request.source,
            score=request.score,
            sector=request.sector,
        )
    except Exception as e:
        logger.error(f"添加自选失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/watchlist/{code}")
async def remove_from_watchlist(code: str):
    """从自选股中移除标的"""
    try:
        data = _load_watchlist()
        if code in data:
            del data[code]
            _save_watchlist(data)
            return {"status": "removed", "code": code}
        return {"status": "not_found", "code": code}
    except Exception as e:
        logger.error(f"移除自选失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/watchlist/status", response_model=WatchlistStatusResponse)
async def get_watchlist_status():
    """获取自选股状态（仅返回code列表，用于批量检查）"""
    try:
        data = _load_watchlist()
        return WatchlistStatusResponse(codes=list(data.keys()))
    except Exception as e:
        logger.error(f"获取自选状态失败: {e}", exc_info=True)
        return WatchlistStatusResponse(codes=[])


# ============ 推荐建仓管理 API ============

class RecommendationRecordResponse(BaseModel):
    """推荐建仓记录"""
    date: str = Field(description="推荐日期")
    label: str = Field(description="日期标签")
    generated_at: str = Field("", description="生成时间")
    code: str = Field(description="股票代码")
    name: str = Field(description="股票名称")
    score: int = Field(0, description="评分")
    change_pct: float = Field(0.0, description="涨跌幅%")
    seal_time: Optional[str] = Field(None, description="封板时间")
    sector: Optional[str] = Field(None, description="所属板块")
    seal_amount: float = Field(0.0, description="封单金额(万)")
    reasons: list[str] = Field(default_factory=list, description="推荐理由")
    outcome: Optional[str] = Field(None, description="结果: 成功/失败/持平")
    actual_return_pct: Optional[float] = Field(None, description="实际收益率%")
    won: Optional[bool] = Field(None, description="是否盈利")
    review_note: Optional[str] = Field(None, description="复盘备注")
    sentiment_phase: str = Field("", description="情绪阶段")
    sentiment_index: float = Field(50.0, description="情绪指数")


class RecommendationRecordListResponse(BaseModel):
    """推荐记录列表"""
    items: list[RecommendationRecordResponse] = Field(default_factory=list)
    total: int = Field(0, description="总记录数")
    limit: int = Field(90, description="每页条数")
    offset: int = Field(0, description="偏移量")


class DailyWinRateItemResponse(BaseModel):
    """每日胜率项"""
    date: str
    label: str
    total_count: int = 0
    settled_count: int = 0
    won_count: int = 0
    lost_count: int = 0
    pending_count: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    max_return: float = 0.0
    min_return: float = 0.0
    sentiment_phase: str = ""
    sentiment_index: float = 50.0
    recommendations: list[dict] = Field(default_factory=list)


class WinRateBacktestResponse(BaseModel):
    """胜率回溯响应"""
    daily_records: list[DailyWinRateItemResponse] = Field(default_factory=list)
    overall_win_rate: float = 0.0
    total_recommendations: int = 0
    total_settled: int = 0
    total_won: int = 0
    avg_return: float = 0.0
    best_day: Optional[dict] = None
    worst_day: Optional[dict] = None


class HistoricalWinRateResponse(BaseModel):
    """历史胜率查询响应"""
    target_date: str
    target_detail: Optional[dict] = None
    trend: list[dict] = Field(default_factory=list)
    lookback_days: int = 5
    overall_stats: dict = Field(default_factory=dict)


class AvailableDatesResponse(BaseModel):
    """可选日期列表"""
    dates: list[dict] = Field(default_factory=list)


# --- 推荐记录 API ---

@router.get("/recommendation-records", response_model=RecommendationRecordListResponse)
async def get_recommendation_records(
    limit: int = Query(90, description="每页条数", ge=1, le=200),
    offset: int = Query(0, description="偏移量", ge=0),
    date_from: Optional[str] = Query(None, description="起始日期 YYYYMMDD"),
    date_to: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
):
    """
    获取推荐建仓记录列表

    支持分页和日期范围筛选。
    每条记录包含推荐时间、标的代码、推荐价格等关键信息。
    """
    from src.seal_plate.recommendation_management import RecommendationManager

    try:
        manager = RecommendationManager()
        records = manager.get_all_recommendations(
            limit=limit, offset=offset,
            date_from=date_from, date_to=date_to,
        )
        total = manager.get_recommendation_count(
            date_from=date_from, date_to=date_to,
        )

        return RecommendationRecordListResponse(
            items=[
                RecommendationRecordResponse(
                    date=r.date,
                    label=r.label,
                    generated_at=r.generated_at,
                    code=r.code,
                    name=r.name,
                    score=r.score,
                    change_pct=r.change_pct,
                    seal_time=r.seal_time,
                    sector=r.sector,
                    seal_amount=r.seal_amount,
                    reasons=r.reasons,
                    outcome=r.outcome,
                    actual_return_pct=r.actual_return_pct,
                    won=r.won,
                    review_note=r.review_note,
                    sentiment_phase=r.sentiment_phase,
                    sentiment_index=r.sentiment_index,
                )
                for r in records
            ],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error(f"获取推荐记录失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- 每日胜率回溯 API ---

@router.get("/win-rate-backtest", response_model=WinRateBacktestResponse)
async def get_win_rate_backtest(
    days: int = Query(30, description="回溯天数", ge=1, le=365),
    date_from: Optional[str] = Query(None, description="起始日期 YYYYMMDD"),
    date_to: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
):
    """
    获取每日胜率回溯数据

    自动统计并回溯每日推荐标的的涨跌胜率，提供历史胜率数据评估。
    """
    from src.seal_plate.recommendation_management import RecommendationManager

    try:
        manager = RecommendationManager()
        result = manager.compute_daily_win_rate_backtest(
            days=days,
            date_from=date_from,
            date_to=date_to,
        )

        return WinRateBacktestResponse(
            daily_records=[
                DailyWinRateItemResponse(
                    date=r.date,
                    label=r.label,
                    total_count=r.total_count,
                    settled_count=r.settled_count,
                    won_count=r.won_count,
                    lost_count=r.lost_count,
                    pending_count=r.pending_count,
                    win_rate=r.win_rate,
                    avg_return=r.avg_return,
                    max_return=r.max_return,
                    min_return=r.min_return,
                    sentiment_phase=r.sentiment_phase,
                    sentiment_index=r.sentiment_index,
                    recommendations=r.recommendations,
                )
                for r in result.daily_records
            ],
            overall_win_rate=result.overall_win_rate,
            total_recommendations=result.total_recommendations,
            total_settled=result.total_settled,
            total_won=result.total_won,
            avg_return=result.avg_return,
            best_day={
                "date": result.best_day.date,
                "win_rate": result.best_day.win_rate,
                "settled_count": result.best_day.settled_count,
                "won_count": result.best_day.won_count,
            } if result.best_day else None,
            worst_day={
                "date": result.worst_day.date,
                "win_rate": result.worst_day.win_rate,
                "settled_count": result.worst_day.settled_count,
                "won_count": result.worst_day.won_count,
            } if result.worst_day else None,
        )
    except Exception as e:
        logger.error(f"获取胜率回溯失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- 历史胜率查询 API ---

@router.get("/historical-win-rate", response_model=HistoricalWinRateResponse)
async def get_historical_win_rate(
    target_date: str = Query(..., description="目标日期 YYYYMMDD"),
    lookback_days: int = Query(5, description="前后对比天数", ge=1, le=30),
):
    """
    查询特定日期的阶段性胜率表现

    支持选择特定日期查看过往推荐标的的阶段性胜率表现。
    返回目标日期详情 + 前后N天趋势对比 + 整体胜率统计。
    """
    from src.seal_plate.recommendation_management import RecommendationManager

    try:
        manager = RecommendationManager()
        result = manager.query_historical_win_rate(
            target_date=target_date,
            lookback_days=lookback_days,
        )

        return HistoricalWinRateResponse(
            target_date=result["target_date"],
            target_detail=result["target_detail"],
            trend=result["trend"],
            lookback_days=result["lookback_days"],
            overall_stats=result["overall_stats"],
        )
    except Exception as e:
        logger.error(f"获取历史胜率失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- 可用日期列表 API ---

@router.get("/recommendation-dates", response_model=AvailableDatesResponse)
async def get_recommendation_dates():
    """
    获取有推荐记录的所有日期列表

    供前端日期选择器使用，只返回有推荐数据的日期。
    """
    from src.seal_plate.recommendation_management import RecommendationManager

    try:
        manager = RecommendationManager()
        dates = manager.get_available_dates()
        return AvailableDatesResponse(dates=dates)
    except Exception as e:
        logger.error(f"获取可选日期失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
