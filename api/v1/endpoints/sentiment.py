# -*- coding: utf-8 -*-
"""板块热力图 API 端点 — 包含趋势变化分析与资金流向推测.

提供端点:
- GET /sector-heatmap : 板块热力图数据（含趋势变化、资金流向推测）
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query

from src.services.real_time_data_service import RealTimeDataService
from src.strategies.sector_rotation import SectorAnalyzer, SectorRank

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["板块热力图"])


def _safe_float(value: Any, default: float = 0.0) -> float:
    """安全转换为 float。"""
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


# ============================================================
#  Sector Heatmap Endpoint
# ============================================================

@router.get("/sector-heatmap")
async def get_sector_heatmap():
    """获取板块热力图数据（含趋势变化与资金流向推测）。

    返回结构:
    {
        "generated_at": "2025-06-25T11:30:00",
        "sectors": [
            {
                "sector": "通信设备",
                "strength": 85.2,
                "limit_up_count": 8,
                "change_pct": 4.5,
                "net_inflow": 15.2,
                "mainline": true,
                "trend": "accelerating",       # 趋势变化: accelerating/steady/cooling/reversing
                "trend_score": 12.3,           # 趋势变化幅度（涨跌幅差值）
                "consecutive_days": 3,         # 连续上榜天数
                "flow_prediction": {           # 资金流向推测
                    "direction": "持续流入",
                    "confidence": "高",
                    "reason": "连续3日资金净流入，板块强度持续攀升",
                    "next_day_probability": 0.72
                },
                "stocks": [...]
            }
        ],
        "summary": {
            "total_sectors": 20,
            "up_count": 12,
            "down_count": 8,
            "total_net_inflow": 85.3,
            "hot_money_direction": "科技/通信",
            "market_sentiment": "偏多",
            "rotation_signal": "资金从传统板块流向科技板块"
        },
        "top_inflows": [...],
        "top_outflows": [...],
        "rotations": [...]
    }
    """
    try:
        realtime = RealTimeDataService()
        analyzer = SectorAnalyzer()

        # ── 1. 获取实时数据 ──
        sectors_up, sectors_down = realtime.get_sector_rankings(n=10)
        money_flows = realtime.get_money_flow(top_n=20)
        concepts_up, concepts_down = realtime.get_concept_rankings(n=6)

        # 合并行业板块和概念板块
        all_sectors_raw = list(sectors_up) + list(sectors_down)

        # ── 2. 构建资金流向映射 ──
        flow_map: Dict[str, Dict] = {}
        for f in money_flows:
            name = f.get("name", "")
            if name:
                flow_map[name] = f

        # ── 2.5 合并概念板块数据（丰富板块覆盖范围）──
        # 概念板块与行业板块可能名称不同，作为补充
        concept_names: Dict[str, dict] = {}
        for c in list(concepts_up) + list(concepts_down):
            cname = c.get("name", "") or c.get("sector", "")
            if cname and cname not in flow_map:
                concept_names[cname] = c

        # ── 3. 尝试获取昨日数据做趋势对比 ──
        prev_day_data = _get_previous_day_data(realtime)

        # ── 4. 构建板块排名数据 ──
        sectors_data = []
        for s in all_sectors_raw:
            name = s.get("name", "") or s.get("sector", "")
            if not name:
                continue

            flow_info = flow_map.get(name, {})
            net_inflow = _safe_float(
                flow_info.get("main_net_inflow", 0)
                or flow_info.get("amount", 0)
            )
            change_pct = _safe_float(s.get("change_pct", 0))
            up_count = int(s.get("up_count", 0) or 0)
            total_stocks = int(s.get("stock_count", 0) or max(up_count, 1))
            leader_stocks = s.get("leader_stocks", []) or []

            sectors_data.append({
                "name": name,
                "change_pct": change_pct,
                "net_inflow": net_inflow,
                "total_stocks": total_stocks,
                "up_count": up_count,
                "leader_stocks": leader_stocks,
                # limit_up_count 在步骤 11 中通过涨停池计算
            })

        # 合并概念板块数据（补充行业板块可能遗漏的题材板块）
        for cname, cdata in concept_names.items():
            if not any(sd["name"] == cname for sd in sectors_data):
                c_flow = flow_map.get(cname, {})
                sectors_data.append({
                    "name": cname,
                    "change_pct": _safe_float(cdata.get("change_pct", 0)),
                    "net_inflow": _safe_float(c_flow.get("main_net_inflow", 0) or c_flow.get("amount", 0)),
                    "total_stocks": int(cdata.get("stock_count", 0) or cdata.get("up_count", 0) or 1),
                    "up_count": int(cdata.get("up_count", 0) or 0),
                    "leader_stocks": cdata.get("leader_stocks", []) or [],
                })

        # 按资金活跃度排序取前25: abs(net_inflow) 优先，其次 abs(change_pct)
        sectors_data.sort(key=lambda x: (abs(x["net_inflow"]), abs(x["change_pct"])), reverse=True)
        sectors_data = sectors_data[:25]

        # ── 3.5 获取涨停池用于 limit_up_count 计算 ──
        limit_up_pool = realtime.get_limit_up_pool(n=50)

        # ── 5. 板块强度排名 —— 补充 limit_up_count ──
        # 从涨停池中统计每个板块的涨停数量（支持模糊匹配）
        sector_limit_up: Dict[str, int] = {}
        for lu in limit_up_pool:
            sec_name = lu.get("sector") or lu.get("industry") or ""
            if sec_name:
                sector_limit_up[sec_name] = sector_limit_up.get(sec_name, 0) + 1

        for sd in sectors_data:
            sd_name = sd["name"]
            count = sector_limit_up.get(sd_name, 0)
            # 如果精确匹配为 0，尝试模糊匹配（板块名称包含行业名或行业名包含板块名）
            if count == 0:
                for sec_name, cnt in sector_limit_up.items():
                    if sec_name in sd_name or sd_name in sec_name:
                        count += cnt
            sd["limit_up_count"] = count

        rankings = analyzer.rank_sectors(sectors_data, date=date.today().isoformat())

        # ── 6. 生成热力图数据 ──
        heatmap_data = analyzer.get_sector_heatmap_data(rankings)

        # ── 7. 计算趋势变化 ──
        prev_map: Dict[str, Dict] = {}
        if prev_day_data:
            for ps in prev_day_data:
                prev_map[ps.get("name", "")] = ps

        for item in heatmap_data:
            name = item.get("name", "")
            current_change = item.get("change_pct", 0)
            prev = prev_map.get(name)

            if prev:
                prev_change = _safe_float(prev.get("change_pct", 0))
                prev_inflow = _safe_float(prev.get("net_inflow", 0))
                trend_score = round(current_change - prev_change, 2)

                # 趋势判定
                if trend_score > 1.0:
                    item["trend"] = "accelerating"  # 加速上涨
                elif trend_score > 0.3:
                    item["trend"] = "steady"        # 稳步上行
                elif trend_score > -0.3:
                    item["trend"] = "steady"        # 持平
                elif trend_score > -1.0:
                    item["trend"] = "cooling"       # 降温
                else:
                    item["trend"] = "reversing"     # 转向

                item["trend_score"] = trend_score

                # ── 8. 资金流向推测 ──
                current_inflow = item.get("net_inflow", 0)
                consecutive_days = item.get("consecutive_days", 0)

                flow_prediction = _predict_flow_direction(
                    trend=item["trend"],
                    trend_score=trend_score,
                    current_inflow=current_inflow,
                    prev_inflow=prev_inflow,
                    consecutive_days=consecutive_days,
                    strength=item.get("strength_score", 50),
                )
                item["flow_prediction"] = flow_prediction
            else:
                # 无历史数据时的默认趋势
                item["trend"] = "steady"
                item["trend_score"] = 0.0
                item["flow_prediction"] = {
                    "direction": "首次上榜",
                    "confidence": "低",
                    "reason": "无历史数据，需持续观察",
                    "next_day_probability": 0.5,
                }

        # ── 9. 汇总统计 ──
        up_sectors = [h for h in heatmap_data if h.get("change_pct", 0) > 0]
        down_sectors = [h for h in heatmap_data if h.get("change_pct", 0) < 0]
        total_net_inflow = round(sum(h.get("net_inflow", 0) for h in heatmap_data), 2)

        # 资金流入/流出 TOP
        sorted_by_flow = sorted(heatmap_data, key=lambda h: h.get("net_inflow", 0), reverse=True)
        top_inflows = sorted_by_flow[:5]
        top_outflows = sorted(heatmap_data, key=lambda h: h.get("net_inflow", 0))[:5]

        # 热点资金方向
        if top_inflows:
            hot_money_direction = "/".join([f["name"] for f in top_inflows[:2]])
        else:
            hot_money_direction = "无明显方向"

        # 市场情绪
        if len(up_sectors) >= len(heatmap_data) * 0.6:
            market_sentiment = "偏多"
        elif len(down_sectors) >= len(heatmap_data) * 0.6:
            market_sentiment = "偏空"
        else:
            market_sentiment = "震荡"

        # ── 10. 轮动信号 ──
        rotations = _detect_rotation_signals(heatmap_data, top_inflows, top_outflows)

        # ── 11. 构建 stocks 字段（板块内个股） ──
        for item in heatmap_data:
            sector_name = item.get("name", "")
            sector_stocks = [
                {
                    "code": s.get("code", ""),
                    "name": s.get("name", ""),
                    "change_pct": _safe_float(s.get("change_pct", 0)),
                    "is_leader": s.get("name", "") in [
                        ls.get("name", "") for ls in item.get("leader_stocks", [])
                    ],
                }
                for s in limit_up_pool
                if (s.get("sector") or s.get("industry") or "") == sector_name
            ]
            if not sector_stocks:
                # 兜底：用 leader_stocks 填充
                sector_stocks = [
                    {
                        "code": "",
                        "name": ls.get("name", ""),
                        "change_pct": _safe_float(ls.get("change_pct", 0)),
                        "is_leader": True,
                    }
                    for ls in item.get("leader_stocks", [])[:5]
                ]
            item["stocks"] = sector_stocks[:5]

        # ── 12. 缓存当日数据供下次趋势对比 ──
        _save_heatmap_cache(heatmap_data)

        return {
            "generated_at": datetime.now().isoformat(),
            "sectors": heatmap_data,
            "summary": {
                "total_sectors": len(heatmap_data),
                "up_count": len(up_sectors),
                "down_count": len(down_sectors),
                "total_net_inflow": total_net_inflow,
                "hot_money_direction": hot_money_direction,
                "market_sentiment": market_sentiment,
                "rotation_signal": rotations[0]["description"] if rotations else "无明显轮动",
            },
            "top_inflows": [
                {"name": f["name"], "amount": f["net_inflow"], "change_pct": f["change_pct"]}
                for f in top_inflows
            ],
            "top_outflows": [
                {"name": f["name"], "amount": f["net_inflow"], "change_pct": f["change_pct"]}
                for f in top_outflows
            ],
            "rotations": rotations,
        }

    except Exception as e:
        logger.error("获取板块热力图失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
#  Helper Functions
# ============================================================

def _get_previous_day_data(realtime: RealTimeDataService) -> Optional[List[Dict]]:
    """尝试获取前一交易日的板块数据用于趋势对比。

    策略：从本地 JSON 缓存中读取上一次热力图请求时保存的板块数据。
    缓存文件路径：data/sector_heatmap_cache.json
    """
    try:
        import json as _json
        import os as _os

        cache_file = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))),
            "data", "sector_heatmap_cache.json"
        )

        if not _os.path.exists(cache_file):
            logger.debug("板块热力图缓存文件不存在，无法获取前日数据")
            return None

        with open(cache_file, "r", encoding="utf-8") as f:
            cached = _json.load(f)

        cached_date = cached.get("date", "")
        today_str = date.today().isoformat()

        # 只使用不同日期的缓存（同一天的数据不用于趋势对比）
        if cached_date == today_str:
            logger.debug("缓存日期与今日相同，跳过趋势对比")
            return None

        sectors = cached.get("sectors", [])
        if not sectors:
            return None

        result = []
        for s in sectors:
            result.append({
                "name": s.get("name", ""),
                "change_pct": _safe_float(s.get("change_pct", 0)),
                "net_inflow": _safe_float(s.get("net_inflow", 0)),
                "up_count": int(s.get("up_count", 0) or 0),
                "total_stocks": int(s.get("stock_count", 0) or max(s.get("up_count", 1), 1)),
            })

        logger.info(f"从前日缓存加载板块数据: 日期={cached_date}, 板块数={len(result)}")
        return result

    except Exception as e:
        logger.debug(f"获取前日板块数据失败: {e}")
        return None


def _save_heatmap_cache(heatmap_data: List[Dict]) -> None:
    """将当日的板块热力图数据缓存到本地 JSON 文件，供下次趋势对比使用。"""
    try:
        import json as _json
        import os as _os

        cache_file = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))),
            "data", "sector_heatmap_cache.json"
        )

        cache_data = {
            "date": date.today().isoformat(),
            "generated_at": datetime.now().isoformat(),
            "sectors": [
                {
                    "name": h.get("name", ""),
                    "change_pct": h.get("change_pct", 0),
                    "net_inflow": h.get("net_inflow", 0),
                    "up_count": h.get("up_count", 0),
                    "stock_count": h.get("stock_count", 0),
                }
                for h in heatmap_data
            ],
        }

        _os.makedirs(_os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            _json.dump(cache_data, f, ensure_ascii=False, indent=2)

        logger.info(f"板块热力图数据已缓存: {len(heatmap_data)} 个板块")
    except Exception as e:
        logger.debug(f"缓存板块热力图数据失败: {e}")


def _predict_flow_direction(
    trend: str,
    trend_score: float,
    current_inflow: float,
    prev_inflow: float,
    consecutive_days: int,
    strength: float,
) -> Dict[str, Any]:
    """根据趋势和资金数据推测下一日资金流向。

    Returns:
        {
            "direction": "持续流入" | "可能流入" | "观望" | "可能流出" | "持续流出",
            "confidence": "高" | "中" | "低",
            "reason": "推测理由",
            "next_day_probability": 0.0-1.0
        }
    """
    # 计算流入加速度
    inflow_acceleration = current_inflow - prev_inflow

    # 综合评分（0-100）
    score = 50.0

    # 趋势因素
    if trend == "accelerating":
        score += 20
    elif trend == "steady":
        score += 5
    elif trend == "cooling":
        score -= 15
    elif trend == "reversing":
        score -= 25

    # 趋势幅度因素
    score += trend_score * 3

    # 资金流向因素
    if current_inflow > 10:
        score += 15
    elif current_inflow > 5:
        score += 8
    elif current_inflow > 0:
        score += 3
    elif current_inflow < -10:
        score -= 15
    elif current_inflow < -5:
        score -= 8
    elif current_inflow < 0:
        score -= 3

    # 连续天数因素
    score += min(consecutive_days * 3, 15)

    # 板块强度因素
    if strength >= 80:
        score += 10
    elif strength >= 60:
        score += 5
    elif strength < 40:
        score -= 10

    # 流入加速度
    score += min(inflow_acceleration * 0.5, 10)

    # 归一化到 0-100
    score = max(0, min(100, score))

    # 判断方向
    if score >= 75:
        direction = "持续流入"
        confidence = "高"
    elif score >= 60:
        direction = "可能流入"
        confidence = "中"
    elif score >= 40:
        direction = "观望"
        confidence = "低"
    elif score >= 25:
        direction = "可能流出"
        confidence = "中"
    else:
        direction = "持续流出"
        confidence = "高"

    # 生成理由
    reasons = []
    if trend in ("accelerating", "steady") and current_inflow > 0:
        reasons.append(f"板块趋势向上，资金持续净流入{current_inflow:.1f}亿")
    elif trend in ("cooling", "reversing"):
        reasons.append(f"板块趋势走弱，涨跌幅变化{trend_score:+.2f}%")
    if consecutive_days >= 3:
        reasons.append(f"连续{consecutive_days}日上榜，主线特征明显")
    if inflow_acceleration > 3:
        reasons.append(f"资金流入加速（+{inflow_acceleration:.1f}亿）")
    elif inflow_acceleration < -3:
        reasons.append(f"资金流入减速（{inflow_acceleration:.1f}亿）")
    if strength >= 70:
        reasons.append("板块强度评分较高")
    elif strength < 40:
        reasons.append("板块强度偏弱")

    if not reasons:
        if current_inflow > 0:
            reasons.append(f"当日资金净流入{current_inflow:.1f}亿")
        else:
            reasons.append(f"当日资金净流出{abs(current_inflow):.1f}亿")

    reason = "；".join(reasons)

    # 下一日概率
    next_day_probability = round(score / 100, 2)

    return {
        "direction": direction,
        "confidence": confidence,
        "reason": reason,
        "next_day_probability": next_day_probability,
    }


def _detect_rotation_signals(
    heatmap_data: List[Dict],
    top_inflows: List[Dict],
    top_outflows: List[Dict],
) -> List[Dict[str, Any]]:
    """检测板块轮动信号。

    基于流入TOP和流出TOP的对比，推断资金迁移方向。
    """
    rotations = []

    # 流出板块的特征：跌幅较大 + 资金净流出
    outflow_candidates = [h for h in heatmap_data if h.get("net_inflow", 0) < -3 and h.get("change_pct", 0) < -1]

    # 流入板块的特征：涨幅较大 + 资金净流入
    inflow_candidates = [h for h in heatmap_data if h.get("net_inflow", 0) > 3 and h.get("change_pct", 0) > 1]

    # 生成轮动对
    for out_sector in outflow_candidates[:3]:
        for in_sector in inflow_candidates[:3]:
            if out_sector["name"] != in_sector["name"]:
                flow_amount = min(
                    abs(out_sector.get("net_inflow", 0)),
                    abs(in_sector.get("net_inflow", 0)),
                )
                rotation_score = min(1.0, flow_amount / 20)

                rotations.append({
                    "from_sector": out_sector["name"],
                    "from_change": out_sector.get("change_pct", 0),
                    "from_flow": out_sector.get("net_inflow", 0),
                    "to_sector": in_sector["name"],
                    "to_change": in_sector.get("change_pct", 0),
                    "to_flow": in_sector.get("net_inflow", 0),
                    "flow_amount": round(flow_amount, 1),
                    "rotation_score": round(rotation_score, 2),
                    "description": f"资金从{out_sector['name']}流向{in_sector['name']}",
                    "signal": "high" if rotation_score > 0.6 else ("medium" if rotation_score > 0.3 else "low"),
                })

    # 按轮动得分排序
    rotations.sort(key=lambda r: r["rotation_score"], reverse=True)
    return rotations[:5]
