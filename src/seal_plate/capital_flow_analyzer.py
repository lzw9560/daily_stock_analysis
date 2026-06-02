"""
资金流向与主力动态分析器

功能：
1. 大基金/机构/游资动态追踪
2. 资金热点板块识别
3. 一日游行情风险检测
4. 买卖点位建议生成
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


@dataclass
class FundFlowAnalysis:
    """资金流向分析结果"""
    date: str
    # 板块资金流向
    hot_sectors_inflow: list[dict] = field(default_factory=list)     # 资金净流入板块TOP5
    hot_sectors_outflow: list[dict] = field(default_factory=list)    # 资金净流出板块TOP5
    # 主力动向
    major_institution_active: bool = False    # 大机构是否活跃
    hot_money_active: bool = False            # 游资是否活跃
    hot_money_warning: list[str] = field(default_factory=list)       # 游资风险提示
    # 一日游风险
    one_day_tour_risk: list[str] = field(default_factory=list)       # 一日游风险标的
    # 大基金关注
    major_fund_focus: list[str] = field(default_factory=list)        # 大基金关注的板块
    major_fund_stocks: list[str] = field(default_factory=list)       # 大基金持仓标的
    # 买卖点建议
    buy_suggestions: list[dict] = field(default_factory=list)        # 买入建议
    sell_suggestions: list[dict] = field(default_factory=list)       # 卖出建议
    # 风险提示
    risk_alerts: list[str] = field(default_factory=list)             # 综合风险提示
    # 资金情绪
    fund_sentiment: str = "中性"              # 资金情绪: 积极/中性/谨慎
    fund_heat_score: int = 50                 # 资金热度评分 0-100


class CapitalFlowAnalyzer:
    """资金流向分析器
    
    结合多数据源分析主力资金动向，识别大基金/游资/机构行为模式，
    避免一日游行情，提供买卖点位建议。
    """

    # 知名游资席位（需要警惕的）
    UNSTABLE_HOT_MONEY = [
        "章盟主", "方新侠", "作手新一", "赵老哥", "炒股养家",
        "宁波桑田路", "上海溧阳路", "深圳益田路", "佛山无影脚",
        "小鳄鱼", "著名刺客", "欢乐海岸",
    ]

    # 大基金/国家队相关关键词
    MAJOR_FUND_KEYWORDS = [
        "社保基金", "养老金", "证金公司", "汇金公司", "国家大基金",
        "中央汇金", "中国证金", "大基金二期", "大基金一期",
        "国新投资", "诚通金控",
    ]

    # 一日游特征板块（历史上容易一日游）
    ONE_DAY_TOUR_SECTORS = [
        "ST板块", "壳资源", "预亏预减",
    ]

    def __init__(self):
        self._ths_fetcher = None

    @property
    def ths(self):
        if self._ths_fetcher is None:
            from data_provider.ths_hotspot_fetcher import create_ths_hotspot_fetcher
            self._ths_fetcher = create_ths_hotspot_fetcher()
        return self._ths_fetcher

    def analyze(
        self,
        hot_sectors: list[tuple[str, int]],
        strong_stocks: list,
        date: Optional[str] = None,
    ) -> FundFlowAnalysis:
        """
        执行资金流向分析

        Args:
            hot_sectors: 当日板块热度 [(板块名, 涨停数), ...]
            strong_stocks: 强势涨停股列表
            date: 分析日期
        """
        target_date = date or datetime.now().strftime("%Y%m%d")
        result = FundFlowAnalysis(date=target_date)

        # 1. 获取板块资金流向（同花顺数据）
        try:
            fund_flow_data = self.ths.get_sector_fund_flow()
            if fund_flow_data:
                # 资金净流入TOP5
                inflow_sorted = sorted(
                    fund_flow_data, key=lambda x: x.get("net_inflow", 0), reverse=True
                )
                result.hot_sectors_inflow = inflow_sorted[:5]
                # 资金净流出TOP5
                outflow_sorted = sorted(
                    fund_flow_data, key=lambda x: x.get("net_inflow", 0)
                )
                result.hot_sectors_outflow = outflow_sorted[:5]
        except Exception as e:
            logger.debug("获取板块资金流向失败: %s", e)

        # 2. 获取市场热度分析
        try:
            market_hot = self.ths.get_market_hot_analysis()
            if market_hot:
                result.fund_heat_score = market_hot.get("market_heat_score", 50)
                result.fund_sentiment = self._map_sentiment(
                    market_hot.get("sentiment_signal", "neutral")
                )
                # 资金流入板块
                for s in market_hot.get("fund_inflow_sectors", []):
                    if s.get("net_inflow", 0) > 0:
                        result.major_fund_focus.append(s.get("name", ""))
        except Exception as e:
            logger.debug("获取市场热度分析失败: %s", e)

        # 3. 检测一日游风险
        result.one_day_tour_risk = self._detect_one_day_tour(
            hot_sectors, strong_stocks
        )

        # 4. 分析游资动态
        result.hot_money_warning = self._analyze_hot_money(strong_stocks)
        result.hot_money_active = len(result.hot_money_warning) > 0

        # 5. 大机构动向
        result.major_institution_active = self._check_institution_active(
            result.hot_sectors_inflow
        )

        # 6. 生成买卖点建议
        result.buy_suggestions = self._generate_buy_suggestions(
            strong_stocks, hot_sectors, result
        )
        result.sell_suggestions = self._generate_sell_suggestions(
            strong_stocks, result
        )

        # 7. 汇总风险提示
        result.risk_alerts = self._aggregate_risk_alerts(result)

        return result

    def _map_sentiment(self, signal: str) -> str:
        """映射资金情绪信号"""
        mapping = {
            "bullish": "积极",
            "bearish": "谨慎",
            "neutral": "中性",
        }
        return mapping.get(signal, "中性")

    def _detect_one_day_tour(
        self,
        hot_sectors: list[tuple[str, int]],
        strong_stocks: list,
    ) -> list[str]:
        """检测一日游行情风险"""
        risks = []

        # 检查是否有ST板块等一日游高发板块活跃
        sector_names = [s[0] for s in hot_sectors]
        for tour_sector in self.ONE_DAY_TOUR_SECTORS:
            for s in sector_names:
                if tour_sector in s:
                    risks.append(f"⚠️ {s}板块活跃，历史上一日游概率较高")

        # 检查是否有尾盘突袭封板（一日游特征）
        for stock in strong_stocks:
            if hasattr(stock, 'seal_time') and stock.seal_time:
                try:
                    from datetime import datetime as dt
                    t = dt.strptime(str(stock.seal_time), "%H:%M:%S").time() \
                        if isinstance(stock.seal_time, str) else stock.seal_time
                    if t.hour >= 14 and t.minute >= 30:
                        risks.append(
                            f"⚠️ {stock.name}({stock.code})尾盘突袭封板({t.strftime('%H:%M')})，谨防一日游"
                        )
                except Exception:
                    pass

        # 板块涨停数过少，缺乏持续性
        for sector, count in hot_sectors:
            if count == 1:
                risks.append(f"⚠️ {sector}板块仅1只涨停，缺乏板块效应，持续性存疑")

        return risks[:5]  # 最多5条

    def _analyze_hot_money(self, strong_stocks: list) -> list[str]:
        """分析游资动态，识别不稳定资金"""
        warnings = []

        # 通过涨停原因判断是否有游资参与
        for stock in strong_stocks:
            reason = getattr(stock, 'reason', '') or ''
            for hm in self.UNSTABLE_HOT_MONEY:
                if hm in reason:
                    warnings.append(
                        f"⚠️ {stock.name}({stock.code})有游资({hm})参与痕迹，注意快进快出"
                    )

        # 换手率过高（游资对倒特征）
        for stock in strong_stocks:
            turnover = getattr(stock, 'turnover_rate', 0) or 0
            if turnover > 30:
                warnings.append(
                    f"⚠️ {stock.name}({stock.code})换手率{turnover:.1f}%，游资对倒嫌疑"
                )

        return warnings[:5]

    def _check_institution_active(self, inflow_sectors: list[dict]) -> bool:
        """判断大机构是否活跃"""
        if not inflow_sectors:
            return False

        total_inflow = sum(
            s.get("net_inflow", 0) for s in inflow_sectors
        )
        # 主力净流入超过100亿视为机构活跃
        return total_inflow > 100

    def _generate_buy_suggestions(
        self,
        strong_stocks: list,
        hot_sectors: list[tuple[str, int]],
        analysis: FundFlowAnalysis,
    ) -> list[dict]:
        """生成买入点位建议"""
        suggestions = []
        hot_sector_names = {s[0] for s in hot_sectors[:5]}

        for stock in strong_stocks:
            score = getattr(stock, 'score', 0) or 0
            if score < 70:
                continue

            sector = getattr(stock, 'sector', '') or ''

            # 只建议热门板块中的标的
            if sector not in hot_sector_names and sector:
                continue

            buy_point = self._calculate_buy_point(stock)
            if buy_point:
                suggestions.append({
                    "code": getattr(stock, 'code', ''),
                    "name": getattr(stock, 'name', ''),
                    "score": score,
                    "sector": sector,
                    "buy_point": buy_point,
                    "stop_loss": self._calculate_stop_loss(stock),
                    "target_price": self._calculate_target_price(stock),
                    "confidence": "高" if score >= 80 else "中",
                })

        # 按评分排序，取前5
        suggestions.sort(key=lambda x: x["score"], reverse=True)
        return suggestions[:5]

    def _generate_sell_suggestions(
        self, strong_stocks: list, analysis: FundFlowAnalysis
    ) -> list[dict]:
        """生成卖出建议"""
        suggestions = []

        for stock in strong_stocks:
            # 连板过多需要卖出
            consecutive = getattr(stock, 'consecutive_days', 0) or 0
            if consecutive >= 5:
                suggestions.append({
                    "code": getattr(stock, 'code', ''),
                    "name": getattr(stock, 'name', ''),
                    "reason": f"已{consecutive}连板，高位风险积聚，建议逐步减仓",
                    "urgency": "高",
                })
                continue

            # 开板次数多
            open_count = getattr(stock, 'open_count', 0) or 0
            if open_count >= 3:
                suggestions.append({
                    "code": getattr(stock, 'code', ''),
                    "name": getattr(stock, 'name', ''),
                    "reason": f"开板{open_count}次，资金分歧大，建议减仓观望",
                    "urgency": "高",
                })

        return suggestions[:5]

    def _calculate_buy_point(self, stock) -> Optional[dict]:
        """计算买入点位"""
        close_price = getattr(stock, 'close_price', 0) or 0
        limit_up_price = getattr(stock, 'limit_up_price', 0) or 0

        if close_price <= 0 or limit_up_price <= 0:
            return None

        # 次日竞价区间建议
        # 强势股：涨停价附近竞价可参与
        # 一般股：+3%~+5%开盘可关注
        score = getattr(stock, 'score', 0) or 0

        if score >= 80:
            return {
                "entry_range": f"{limit_up_price * 0.97:.2f} - {limit_up_price:.2f}",
                "ideal_entry": f"{limit_up_price * 0.99:.2f}",
                "strategy": "涨停价附近低吸，竞价高开3%以内可参与",
                "max_position_pct": 20,
            }
        else:
            return {
                "entry_range": f"{close_price * 1.01:.2f} - {close_price * 1.03:.2f}",
                "ideal_entry": f"{close_price * 1.02:.2f}",
                "strategy": "高开2%以内可轻仓参与，追高谨慎",
                "max_position_pct": 10,
            }

    def _calculate_stop_loss(self, stock) -> dict:
        """计算止损点位"""
        close_price = getattr(stock, 'close_price', 0) or 0
        if close_price <= 0:
            return {"price": "N/A", "pct": "N/A"}

        return {
            "price": f"{close_price * 0.95:.2f}",
            "pct": "-5%",
            "rule": "跌破5%无条件止损，不抱幻想",
        }

    def _calculate_target_price(self, stock) -> dict:
        """计算目标价位"""
        close_price = getattr(stock, 'close_price', 0) or 0
        consecutive = getattr(stock, 'consecutive_days', 0) or 0
        if close_price <= 0:
            return {"price": "N/A", "pct": "N/A"}

        # 首板目标10%，连板逐步降低预期
        if consecutive <= 1:
            target_pct = 10
        elif consecutive == 2:
            target_pct = 8
        elif consecutive == 3:
            target_pct = 5
        else:
            target_pct = 3

        return {
            "price": f"{close_price * (1 + target_pct / 100):.2f}",
            "pct": f"+{target_pct}%",
            "hold_days": f"{max(1, 5 - consecutive)}-{max(2, 7 - consecutive)}个交易日",
        }

    def _aggregate_risk_alerts(self, analysis: FundFlowAnalysis) -> list[str]:
        """汇总综合风险提示"""
        alerts = []

        # 资金情绪风险
        if analysis.fund_sentiment == "谨慎":
            alerts.append("🔴 当前资金情绪偏谨慎，控制仓位不超过30%")
        elif analysis.fund_sentiment == "中性":
            alerts.append("🟡 资金情绪中性，注意控制仓位50%以内")

        # 游资活跃风险
        if analysis.hot_money_active:
            alerts.append("🟡 游资活跃，注意快进快出，避免追高被套")

        # 大机构不活跃
        if not analysis.major_institution_active:
            alerts.append("🟡 大机构资金不活跃，市场缺乏主线，降低预期收益")

        # 资金流出风险
        if analysis.hot_sectors_outflow:
            top_outflow = analysis.hot_sectors_outflow[0]
            alerts.append(
                f"🔴 {top_outflow.get('name', '')}板块资金大幅流出"
                f"{top_outflow.get('net_inflow', 0):.0f}亿，注意回避"
            )

        # 一日游风险
        alerts.extend(analysis.one_day_tour_risk)

        # 大基金关注提示
        if analysis.major_fund_focus:
            focus_str = "、".join(analysis.major_fund_focus[:3])
            alerts.append(f"💡 大基金关注板块: {focus_str}，可重点关注")

        return alerts

    def format_feishu_message(self, analysis: FundFlowAnalysis) -> str:
        """格式化为飞书消息"""
        lines = [
            f"💰 **资金流向分析** | {analysis.date}",
            f"资金情绪: {analysis.fund_sentiment} | 热度评分: {analysis.fund_heat_score}/100",
            "",
        ]

        # 板块资金流向
        if analysis.hot_sectors_inflow:
            lines.append("📈 **资金净流入TOP3**")
            for i, s in enumerate(analysis.hot_sectors_inflow[:3], 1):
                lines.append(
                    f"  {i}. {s.get('name', '')} +{s.get('net_inflow', 0):.1f}亿"
                )
            lines.append("")

        if analysis.hot_sectors_outflow:
            lines.append("📉 **资金净流出TOP3**")
            for i, s in enumerate(analysis.hot_sectors_outflow[:3], 1):
                lines.append(
                    f"  {i}. {s.get('name', '')} {s.get('net_inflow', 0):.1f}亿"
                )
            lines.append("")

        # 买卖点建议
        if analysis.buy_suggestions:
            lines.append("🎯 **买入点位建议**")
            for s in analysis.buy_suggestions[:3]:
                bp = s["buy_point"]
                lines.append(
                    f"  • {s['name']}({s['code']}) [{s['sector']}] "
                    f"评分{s['score']} | 置信度:{s['confidence']}"
                )
                lines.append(f"    买入区间: {bp['entry_range']}")
                lines.append(f"    止损: {s['stop_loss']['price']}({s['stop_loss']['pct']})")
                lines.append(f"    目标: {s['target_price']['price']}({s['target_price']['pct']})")
            lines.append("")

        # 风险提示
        if analysis.risk_alerts:
            lines.append("⚠️ **风险提示**")
            for alert in analysis.risk_alerts[:5]:
                lines.append(f"  {alert}")
            lines.append("")

        if analysis.hot_money_warning:
            lines.append("🎭 **游资预警**")
            for w in analysis.hot_money_warning[:3]:
                lines.append(f"  {w}")
            lines.append("")

        return "\n".join(lines)
