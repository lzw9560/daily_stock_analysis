# -*- coding: utf-8 -*-
"""历史推荐追踪服务层 — 推荐记录管理、胜率统计、自省总结."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from src.repositories.recommendation_tracking_repo import RecommendationTrackingRepository

logger = logging.getLogger(__name__)


class RecommendationTrackingService:
    """历史推荐追踪服务 — 管理推荐记录生命周期与统计分析."""

    _instance: Optional["RecommendationTrackingService"] = None

    def __new__(cls) -> "RecommendationTrackingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._repo = RecommendationTrackingRepository()
        self._initialized = True

    # ── CRUD ────────────────────────────────────────────────────────────────

    def create_record(
        self,
        code: str,
        trade_date: str,
        recommendation_price: float,
        signal: str = "buy",
        source: str = "analysis",
        source_task_id: Optional[str] = None,
        reason: Optional[str] = None,
        signal_type: str = "technical",
        strategy_pattern: str = "",
        confidence: float = 0.0,
        entry_method: str = "market",
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        sectors: str = "",
        sentiment_phase: str = "",
        expected_hold_days: Optional[int] = None,
        time_horizon: str = "",
    ) -> Dict[str, Any]:
        """创建推荐追踪记录（支持增强分类字段）."""
        record = self._repo.create(
            code=code,
            trade_date=trade_date,
            recommendation_price=recommendation_price,
            current_price=recommendation_price,
            price_deviation_pct=0.0,
            signal=signal,
            source=source,
            source_task_id=source_task_id,
            reason=reason or "",
            status="active",
            signal_type=signal_type,
            strategy_pattern=strategy_pattern,
            confidence=confidence,
            entry_method=entry_method,
            stop_loss=stop_loss,
            take_profit=take_profit,
            sectors=sectors,
            sentiment_phase=sentiment_phase,
            expected_hold_days=expected_hold_days,
            time_horizon=time_horizon,
        )
        logger.info("推荐记录已创建: id=%s code=%s signal=%s strategy=%s", record.id, code, signal, strategy_pattern)
        return self._repo._to_dict(record)

    def get_record(self, record_id: int) -> Optional[Dict[str, Any]]:
        """获取单条记录详情."""
        return self._repo.get_by_id(record_id)

    def update_record(self, record_id: int, **fields) -> Optional[Dict[str, Any]]:
        """更新记录字段."""
        record = self._repo.update(record_id, **fields)
        if not record:
            return None
        return self._repo._to_dict(record)

    def delete_record(self, record_id: int) -> bool:
        """删除记录."""
        return self._repo.delete(record_id)

    def list_records(
        self,
        code: Optional[str] = None,
        status: Optional[str] = None,
        signal: Optional[str] = None,
        source: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """分页查询推荐记录."""
        return self._repo.list_records(
            code=code,
            status=status,
            signal=signal,
            source=source,
            start_date=start_date,
            end_date=end_date,
            page=page,
            limit=limit,
        )

    # ── 统计 ────────────────────────────────────────────────────────────────

    def get_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取推荐胜率与偏差统计."""
        return self._repo.get_stats(start_date=start_date, end_date=end_date)

    # ── 平仓 ────────────────────────────────────────────────────────────────

    def close_record(
        self,
        record_id: int,
        close_price: float,
    ) -> Optional[Dict[str, Any]]:
        """平仓推荐记录，计算盈亏."""
        record_data = self._repo.get_by_id(record_id)
        if not record_data:
            return None
        if record_data["status"] != "active":
            raise RuntimeError(f"记录 {record_id} 状态为 {record_data['status']}，无法平仓")

        rec_price = record_data["recommendation_price"]
        if rec_price == 0:
            raise RuntimeError("推荐价格为0，无法计算盈亏")

        from datetime import datetime

        # 根据 signal 方向计算盈亏
        if record_data["signal"] == "buy":
            pl_pct = (close_price - rec_price) / rec_price * 100
        elif record_data["signal"] == "sell":
            pl_pct = (rec_price - close_price) / rec_price * 100
        else:
            pl_pct = 0

        record = self._repo.update(
            record_id,
            status="closed",
            close_price=close_price,
            close_date=datetime.now(),
            profit_loss_pct=round(pl_pct, 2),
            price_deviation_pct=round(pl_pct, 2),
        )
        if not record:
            return None
        logger.info("推荐记录已平仓: id=%s pl=%s%%", record_id, round(pl_pct, 2))
        return self._repo._to_dict(record)

    # ── 价格更新 ─────────────────────────────────────────────────────────────

    def update_current_price(self, record_id: int, current_price: float) -> Optional[Dict[str, Any]]:
        """更新当前价格并计算偏差."""
        record_data = self._repo.get_by_id(record_id)
        if not record_data:
            return None
        if record_data["status"] != "active":
            raise RuntimeError(f"记录 {record_id} 状态为 {record_data['status']}，无需更新价格")

        rec_price = record_data["recommendation_price"]
        deviation = ((current_price - rec_price) / rec_price * 100) if rec_price != 0 else 0

        record = self._repo.update(
            record_id,
            current_price=current_price,
            price_deviation_pct=round(deviation, 2),
        )
        if not record:
            return None
        return self._repo._to_dict(record)

    # ── LLM 自省总结 ─────────────────────────────────────────────────────────

    def generate_summary(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """基于历史数据生成推荐策略的反思与优化建议.

        使用 LLM 分析胜率、偏差数据，产出自省报告。
        如果 LLM 不可用，则返回规则化摘要。
        """
        stats = self._repo.get_stats(start_date=start_date, end_date=end_date)
        records = self._repo.list_records(
            start_date=start_date, end_date=end_date, limit=200, page=1
        )

        # 构建提示词
        prompt = self._build_summary_prompt(stats, records.get("items", []))

        llm_response = self._call_llm(prompt)

        return {
            "stats": stats,
            "summary": llm_response,
        }

    def _build_summary_prompt(
        self,
        stats: Dict[str, Any],
        records: List[Dict[str, Any]],
    ) -> str:
        """构建 LLM 自省提示词."""
        lines = [
            "你是一位专业的量化交易策略分析师。请基于以下历史推荐数据，",
            "客观分析推荐策略的表现，找出问题并提出优化建议。",
            "",
            "## 整体表现",
            f"- 总推荐数: {stats['total_records']}",
            f"- 已平仓数: {stats['closed_count']}",
            f"- 持仓中: {stats['active_count']}",
            f"- 胜率: {stats['win_rate']}%",
            f"- 胜场: {stats['win_count']} / 负场: {stats['loss_count']}",
            f"- 平均盈亏: {stats['avg_pl_pct']}%",
            f"- 平均盈利: {stats['avg_win_pl_pct']}% / 平均亏损: {stats['avg_loss_pl_pct']}%",
            f"- 最大盈利: {stats['max_win_pct']}% / 最大亏损: {stats['max_loss_pct']}%",
            f"- 盈亏比 (Profit Factor): {stats['profit_factor']}",
            f"- 累计盈亏: {stats['total_pl_pct']}%",
            "",
        ]

        # 按方向分拆
        lines.append("## 按推荐方向")
        by_signal = stats.get("by_signal", {})
        for sig, data in by_signal.items():
            lines.append(f"- {sig}: 共{data['total']}笔, 胜率{data['win_rate']}%, 平均盈亏{data['avg_pl_pct']}%")

        # 按来源分拆
        lines.append("")
        lines.append("## 按推荐来源")
        by_source = stats.get("by_source", {})
        for src, data in by_source.items():
            lines.append(f"- {src}: 共{data['total']}笔, 胜率{data['win_rate']}%, 平均盈亏{data['avg_pl_pct']}%")

        # 活跃持仓偏差
        active_dev = stats.get("active_deviation", [])
        if active_dev:
            lines.append("")
            lines.append("## 当前持仓偏差")
            for d in active_dev[:10]:
                direction = "📈" if d["deviation_pct"] > 0 else "📉"
                lines.append(f"- {d['code']} ({d['trade_date']}): {d['signal']} @ {d['recommendation_price']}, "
                             f"现价 {d['current_price']}, 偏差 {direction}{d['deviation_pct']}%")

        lines.append("")
        lines.append("请从以下维度给出你的分析（每条150字以内）：")
        lines.append("1. **胜率评估**：整体胜率是否合理？与随机选取相比有无显著优势？")
        lines.append("2. **盈亏结构**：盈亏比是否健康？是否存在盈利回吐或亏损扩大的问题？")
        lines.append("3. **方向偏好**：不同方向（做多/做空）表现差异？是否有统计显著的方向偏差？")
        lines.append("4. **来源质量**：哪些推荐来源表现更好？差的来源可能的原因？")
        lines.append("5. **当前持仓评估**：基于当前偏差数据，哪些持仓风险较高？")
        lines.append("6. **优化建议**：基于以上分析，给出3条具体可行的策略优化建议。")

        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM 生成自省总结.

        尝试使用 litellm + 配置的主模型，不可用时回退规则化摘要。
        """
        try:
            import litellm
            from src.config import get_config, get_effective_agent_primary_model

            config = get_config()
            model = get_effective_agent_primary_model(config)
            if not model:
                raise RuntimeError("未配置 Agent 主模型")

            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500,
            )
            content = response.choices[0].message.content if response.choices else ""
            if content and content.strip():
                return content.strip()
        except Exception as exc:
            logger.warning("LLM 自省总结生成失败，回退规则化摘要: %s", exc)

        return self._fallback_summary()

    def _fallback_summary(self) -> str:
        """LLM 不可用时的规则化摘要."""
        stats = self._repo.get_stats()

        if stats["closed_count"] == 0:
            return (
                "目前尚无已平仓推荐记录，无法进行有效的胜率分析。"
                "请先积累足够的已平仓记录后再进行策略反思。"
            )

        parts = [
            f"## 自省总结（规则化生成）\n",
            f"### 1. 胜率评估\n",
            f"当前整体胜率 **{stats['win_rate']}%**（{stats['win_count']}胜/{stats['loss_count']}负）。",
        ]

        if stats["win_rate"] >= 60:
            parts.append("胜率处于良好水平，推荐策略整体有效。")
        elif stats["win_rate"] >= 45:
            parts.append("胜率处于中等水平，建议结合盈亏比进一步评估策略质量。")
        else:
            parts.append("⚠️ 胜率偏低，建议审视推荐逻辑，排查是否存在系统性偏差。")

        parts.append(f"\n### 2. 盈亏结构\n")
        parts.append(f"盈亏比（Profit Factor）为 **{stats['profit_factor']}**。")
        if stats["profit_factor"] >= 2:
            parts.append("盈亏结构优秀，盈利覆盖亏损的能力强。")
        elif stats["profit_factor"] >= 1.2:
            parts.append("盈亏结构尚可，略有盈利优势。")
        else:
            parts.append("⚠️ 盈亏比不理想，亏损幅度接近或超过盈利幅度，需加强止损纪律。")

        parts.append(f"\n平均盈利 **{stats['avg_win_pl_pct']}%**，平均亏损 **{stats['avg_loss_pl_pct']}%**。")
        if abs(stats['avg_win_pl_pct']) > abs(stats['avg_loss_pl_pct']) * 1.5:
            parts.append("盈亏比（平均盈利/平均亏损）较优，策略具有正的期望值。")
        else:
            parts.append("盈亏比偏低，建议收紧止损或提高止盈目标。")

        parts.append(f"\n### 3. 方向偏好\n")
        by_signal = stats.get("by_signal", {})
        for sig, data in by_signal.items():
            if data["total"] > 0:
                parts.append(f"- {sig}: {data['total']}笔, 胜率{data['win_rate']}%, 平均盈亏{data['avg_pl_pct']}%")

        parts.append(f"\n### 4. 来源质量\n")
        by_source = stats.get("by_source", {})
        if by_source:
            best = max(by_source.items(), key=lambda x: x[1]["win_rate"])
            worst = min(by_source.items(), key=lambda x: x[1]["win_rate"])
            parts.append(f"胜率最高来源: **{best[0]}** ({best[1]['win_rate']}%)")
            parts.append(f"胜率最低来源: **{worst[0]}** ({worst[1]['win_rate']}%)")
            if worst[1]["win_rate"] < 40:
                parts.append(f"⚠️ 建议审视 {worst[0]} 来源的推荐逻辑，考虑降低其权重或优化信号过滤条件。")

        parts.append(f"\n### 5. 优化建议\n")
        parts.append("1. **止损纪律**：基于最大亏损 {:.1f}% 的数据，建议设置硬止损位不超过历史最大亏损的 1.2 倍。".format(abs(stats['max_loss_pct'])))
        parts.append("2. **来源权重**：对胜率较高的来源增加推荐权重，对低胜率来源引入二次确认机制。")
        parts.append("3. **持仓滚动**：定期更新当前价格，对偏差超过阈值的持仓及时评估是否需要平仓。")

        return "\n".join(parts)

    # ── 共同点分析 ─────────────────────────────────────────────────────────────

    @staticmethod
    def _classify_board_by_code(code: str) -> str:
        """根据股票代码前缀分类所属板块."""
        code = str(code).zfill(6)
        if code.startswith("688"):
            return "科创板"
        if code.startswith("300") or code.startswith("301"):
            return "创业板"
        if code.startswith("60"):
            return "沪市主板"
        if code.startswith("00"):
            return "深市主板"
        if code.startswith("4") or code.startswith("8") or code.startswith("9"):
            return "北交所"
        return "其他"

    @staticmethod
    def _classify_price_range(price: float) -> str:
        """根据价格分类价格区间."""
        if price <= 10:
            return "低价股(≤10元)"
        if price <= 30:
            return "中价股(10-30元)"
        if price <= 100:
            return "高价股(30-100元)"
        return "超高价股(>100元)"

    @staticmethod
    def _classify_time_window(trade_date: str, records_by_date: Dict[str, List]) -> str:
        """将日期分类到时间窗口."""
        from datetime import datetime, timedelta
        try:
            dt = datetime.strptime(trade_date, "%Y-%m-%d")
            # 本周窗口
            today = datetime.now()
            week_ago = today - timedelta(days=7)
            if dt >= week_ago:
                return "近一周"
            month_ago = today - timedelta(days=30)
            if dt >= month_ago:
                return "近一月"
            # 按月分组
            return dt.strftime("%Y年%m月")
        except (ValueError, TypeError):
            return "未知时间"

    @staticmethod
    def _extract_keywords_from_reasons(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从推荐理由中提取高频关键词."""
        # 预定义的金融/技术关键词库
        keyword_bank = [
            "突破", "放量", "均线", "金叉", "支撑", "回调", "反弹",
            "成交量", "MACD", "RSI", "KDJ", "布林带", "趋势",
            "涨停", "连板", "龙头", "资金流入", "主力", "北向资金",
            "PE", "PB", "ROE", "净利润", "营收", "增长率", "估值",
            "底部", "顶部", "超跌", "新高", "箱体", "震荡",
            "5日线", "10日线", "20日线", "60日线", "年线",
            "热点", "政策", "利好", "业绩", "分红",
            "低吸", "追涨", "止损", "止盈", "仓位",
            "T+0", "波段", "中长线", "短线", "日内",
        ]
        keyword_counts: Dict[str, int] = {}
        for record in records:
            reason = (record.get("reason") or "").strip()
            if not reason:
                continue
            for kw in keyword_bank:
                if kw in reason:
                    keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

        # 取前 10 个高频关键词
        sorted_kw = sorted(keyword_counts.items(), key=lambda x: (-x[1], x[0]))[:10]
        return [
            {
                "key": f"kw_{kw}",
                "label": kw,
                "value": kw,
                "count": cnt,
                "category": "keyword",
            }
            for kw, cnt in sorted_kw
        ]

    def get_commonality(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        tag_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """分析推荐记录间的共同特征.

        从板块归属、信号方向、推荐来源、价格区间、时间窗口、
        理由关键词六个维度挖掘共同点，输出分组标签.
        """
        # 获取所有记录用于分析（最多 500 条）
        result = self._repo.list_records(
            start_date=start_date,
            end_date=end_date,
            page=1,
            limit=500,
        )
        records: List[Dict[str, Any]] = result.get("items", [])

        if not records:
            return {"total_analyzed": 0, "groups": []}

        groups: List[Dict[str, Any]] = []
        tag_id_counter = 0

        def make_tag(key: str, label: str, value: str, count: int, category: str) -> Dict[str, Any]:
            nonlocal tag_id_counter
            tag_id_counter += 1
            return {
                "key": key,
                "label": label,
                "value": value,
                "count": count,
                "category": category,
            }

        # ── 1. 板块归属 ──
        board_counts: Dict[str, int] = {}
        for r in records:
            board = self._classify_board_by_code(r["code"])
            board_counts[board] = board_counts.get(board, 0) + 1
        board_tags = [
            make_tag(f"board_{b}", b, b, cnt, "board")
            for b, cnt in sorted(board_counts.items(), key=lambda x: -x[1])
        ]
        groups.append({
            "category": "board",
            "category_label": "所属板块",
            "tags": board_tags,
        })

        # ── 2. 信号方向 ──
        signal_labels = {"buy": "看多", "sell": "看空", "hold": "观望"}
        signal_counts: Dict[str, int] = {}
        for r in records:
            sig = r.get("signal", "buy")
            signal_counts[sig] = signal_counts.get(sig, 0) + 1
        signal_tags = [
            make_tag(f"signal_{s}", signal_labels.get(s, s), s, cnt, "signal")
            for s, cnt in sorted(signal_counts.items(), key=lambda x: -x[1])
        ]
        groups.append({
            "category": "signal",
            "category_label": "信号方向",
            "tags": signal_tags,
        })

        # ── 3. 推荐来源 ──
        source_labels = {
            "analysis": "常规分析", "deep_analysis": "深度分析",
            "seal_plate": "打板", "comprehensive": "综合推荐", "manual": "手动录入",
        }
        source_counts: Dict[str, int] = {}
        for r in records:
            src = r.get("source", "manual")
            source_counts[src] = source_counts.get(src, 0) + 1
        source_tags = [
            make_tag(f"source_{s}", source_labels.get(s, s), s, cnt, "source")
            for s, cnt in sorted(source_counts.items(), key=lambda x: -x[1])
        ]
        groups.append({
            "category": "source",
            "category_label": "推荐来源",
            "tags": source_tags,
        })

        # ── 4. 价格区间 ──
        price_counts: Dict[str, int] = {}
        for r in records:
            price = r.get("recommendation_price", 0) or 0
            price_range = self._classify_price_range(price)
            price_counts[price_range] = price_counts.get(price_range, 0) + 1
        price_order = ["低价股(≤10元)", "中价股(10-30元)", "高价股(30-100元)", "超高价股(>100元)"]
        price_tags = [
            make_tag(f"price_{pr}", pr, pr, price_counts.get(pr, 0), "price_range")
            for pr in price_order if price_counts.get(pr, 0) > 0
        ]
        groups.append({
            "category": "price_range",
            "category_label": "价格区间",
            "tags": price_tags,
        })

        # ── 5. 时间窗口 ──
        time_counts: Dict[str, int] = {}
        for r in records:
            td = r.get("trade_date", "")
            tw = self._classify_time_window(td, {})
            time_counts[tw] = time_counts.get(tw, 0) + 1
        time_order = ["近一周", "近一月"]
        time_tags = [
            make_tag(f"time_{tw}", tw, tw, time_counts.get(tw, 0), "time_window")
            for tw in time_order if time_counts.get(tw, 0) > 0
        ]
        # 添加月份标签
        for tw, cnt in sorted(time_counts.items(), key=lambda x: -x[1]):
            if tw not in time_order:
                time_tags.append(make_tag(f"time_{tw}", tw, tw, cnt, "time_window"))
        groups.append({
            "category": "time_window",
            "category_label": "时间窗口",
            "tags": time_tags[:8],  # 最多展示 8 个时间标签
        })

        # ── 6. 理由关键词 ──
        keyword_tags = self._extract_keywords_from_reasons(records)
        if keyword_tags:
            groups.append({
                "category": "keyword",
                "category_label": "理由关键词",
                "tags": keyword_tags,
            })

        return {
            "total_analyzed": len(records),
            "groups": groups,
        }
