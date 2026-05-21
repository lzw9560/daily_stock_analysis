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
    reason: str
    buy_seats: List[dict] = Field(description="买方席位")
    sell_seats: List[dict] = Field(description="卖方席位")
    net_buy: float = Field(description="净买入金额(万)")
    date: str


class DragonTigerResponse(BaseModel):
    """龙虎榜响应"""
    date: str
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
    date: Optional[str] = Query(None, description="日期 YYYYMMDD")
):
    """
    获取龙虎榜数据

    返回当日上榜股票及买卖席位信息。
    注意：龙虎榜数据通常在收盘后16:30发布。
    """
    try:
        # 龙虎榜数据源（实际应接入数据商API）
        # 这里返回模拟数据作为示例
        date_str = date or datetime.now().strftime("%Y%m%d")

        # 知名游资席位库
        famous_seats = [
            {"name": "章盟主", "type": "顶级游资", "style": "龙头战法", "win_rate": 0.68},
            {"name": "方新侠", "type": "顶级游资", "style": "趋势接力", "win_rate": 0.72},
            {"name": "作手新一", "type": "实力游资", "style": "首板挖掘", "win_rate": 0.65},
            {"name": "炒股养家", "type": "顶级游资", "style": "情绪周期", "win_rate": 0.75},
            {"name": "赵老哥", "type": "实力游资", "style": "连板龙头", "win_rate": 0.70},
        ]

        return DragonTigerResponse(
            date=date_str,
            items=[
                DragonTigerItemResponse(
                    code="000000",
                    name="示例股票",
                    reason="涨幅偏离值达7%",
                    buy_seats=[
                        {"name": "章盟主", "amount": 5200, "type": "顶级游资"},
                        {"name": "机构专用", "amount": 2100, "type": "机构"}
                    ],
                    sell_seats=[
                        {"name": "散户集中营", "amount": 1800, "type": "散户"}
                    ],
                    net_buy=5500,
                    date=date_str
                )
            ]
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
                t = stock.seal_time.time() if hasattr(stock.seal_time, 'time') else stock.seal_time
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
