# -*- coding: utf-8 -*-
"""深度分析服务层 — TradingAgents 多Agent投研分析业务逻辑."""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.agent.trading_agents_runner import TradingAgentsRunner
from src.repositories.deep_analysis_repo import DeepAnalysisRepository

logger = logging.getLogger(__name__)

# 深度分析任务超时（秒），默认 20 分钟
_DEEP_ANALYSIS_TIMEOUT = int(os.getenv("DEEP_ANALYSIS_TIMEOUT", "1200"))

# 报告存储目录
_REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"


class DeepAnalysisService:
    """深度分析服务 — 管理分析任务生命周期."""

    _instance: Optional[DeepAnalysisService] = None
    _lock = threading.Lock()

    def __new__(cls) -> DeepAnalysisService:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._repo = DeepAnalysisRepository()
        self._runner = TradingAgentsRunner()
        self._initialized = True

    # ── 公共 API ────────────────────────────────────────────────────────────

    def start_analysis(
        self,
        ticker: str,
        trade_date: str,
        base_url: str = "",
        model: str = "",
    ) -> Dict[str, str]:
        """启动异步分析任务，返回 task_id.
        
        同一标的 + 同一日期只允许一个活跃/已完成任务，重复时抛出 RuntimeError。
        """
        if not self._runner.available:
            raise RuntimeError("TradingAgents-astock 未安装，深度分析不可用")

        # 检查重复：同一标的 + 同一日期已有任务
        existing = self._repo.find_existing_task(ticker, trade_date)
        if existing:
            raise RuntimeError(
                f"标的 {ticker} 在 {trade_date} 已有分析任务（状态: {existing['status']}），"
                f"同一标的每日只能分析一次。请先删除旧任务或等待次日。"
            )

        task_id = uuid.uuid4().hex[:12]

        # 持久化任务
        self._repo.create_task(task_id, ticker, trade_date)
        self._repo.cleanup_expired()

        # 后台线程执行
        thread = threading.Thread(
            target=self._run_analysis,
            args=(task_id, ticker, trade_date, base_url, model),
            daemon=True,
        )
        thread.start()

        logger.info("深度分析任务已启动: task_id=%s ticker=%s", task_id, ticker)
        return {"task_id": task_id, "status": "pending"}

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """查询单个任务状态与结果."""
        return self._repo.get_task(task_id)

    def list_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """列出所有活跃任务."""
        self._repo.cleanup_expired()
        return self._repo.list_tasks(limit=limit)

    def get_pipeline_stages(self) -> List[Dict[str, str]]:
        """获取分析流水线阶段定义."""
        return self._runner.get_pipeline_stages()

    def delete_task(self, task_id: str) -> bool:
        """删除指定任务（含关联报告文件）."""
        # 先查任务获取 report_path
        task = self._repo.get_task(task_id)
        if not task:
            return False

        # 删除报告文件（路径遍历防护）
        report_path = task.get("report_path", "")
        if report_path:
            filepath = (_REPORTS_DIR / report_path).resolve()
            if not filepath.is_relative_to(_REPORTS_DIR.resolve()):
                logger.error("路径遍历尝试被阻止: %s", report_path)
            else:
                try:
                    if filepath.is_file():
                        filepath.unlink()
                        logger.info("已删除报告文件: %s", filepath)
                except Exception:
                    logger.exception("删除报告文件失败: %s", filepath)

        # 从数据库删除
        deleted = self._repo.delete_task(task_id)
        logger.info("深度分析任务已删除: task_id=%s", task_id)
        return deleted

    # ── 内部方法 ────────────────────────────────────────────────────────────

    def _run_analysis(
        self,
        task_id: str,
        ticker: str,
        trade_date: str,
        base_url: str,
        model: str,
    ) -> None:
        """后台线程执行分析."""
        started_at = time.time()
        cancelled = threading.Event()

        def _timeout_killer() -> None:
            """超时后标记任务失败."""
            if not cancelled.wait(_DEEP_ANALYSIS_TIMEOUT):
                logger.error("深度分析任务超时(%ds): task_id=%s", _DEEP_ANALYSIS_TIMEOUT, task_id)
                self._repo.update_task(
                    task_id,
                    status="failed",
                    error=f"任务超时（超过 {_DEEP_ANALYSIS_TIMEOUT}s），可能卡在 tool_call 循环中",
                    elapsed=time.time() - started_at,
                )

        timeout_thread = threading.Thread(target=_timeout_killer, daemon=True)
        timeout_thread.start()

        try:
            self._repo.update_task(task_id, status="running", current_stage="market")

            # 进度回调
            def on_progress(progress: Dict[str, Any]) -> None:
                updates: Dict[str, Any] = {}
                if "stage" in progress:
                    updates["current_stage"] = progress["stage"]
                if "done_stages" in progress:
                    updates["completed_stages"] = progress["done_stages"]
                if "stats" in progress:
                    updates["stats"] = progress["stats"]
                if updates:
                    self._repo.update_task(task_id, **updates)

            # 结果回调
            def on_result(result: Dict[str, Any]) -> None:
                stage_reports = result.get("stage_reports", {})
                signal = result.get("signal", "")
                elapsed = result.get("elapsed", 0)

                self._repo.update_task(
                    task_id,
                    status="completed",
                    signal=signal,
                    stage_reports=stage_reports,
                    elapsed=elapsed,
                )

                # 生成报告文件并保存报告路径
                report_path: Optional[str] = None
                try:
                    report_path = self._save_report(task_id, ticker, trade_date, signal, stage_reports, elapsed)
                    if report_path:
                        self._repo.update_task(task_id, report_path=report_path)
                except Exception:
                    logger.exception("保存深度分析报告失败: task_id=%s", task_id)

                # 发送飞书通知
                try:
                    self._notify_feishu(task_id, ticker, trade_date, signal, stage_reports, elapsed, report_path)
                except Exception:
                    logger.exception("发送深度分析飞书通知失败: task_id=%s", task_id)

                # ── 逻辑闭环：深度分析结果自动同步到推荐追踪 ──
                try:
                    from src.services.logic_closure_service import LogicClosureService

                    closure = LogicClosureService()
                    closure.on_deep_analysis_completed(
                        ticker=ticker,
                        trade_date=trade_date,
                        signal=signal,
                        task_id=task_id,
                        report_path=report_path,
                        auto_create_record=True,
                    )
                except Exception:
                    logger.debug("深度分析逻辑闭环失败（不阻断主流程）: task_id=%s", task_id)

            # 执行分析
            self._runner.run(
                ticker=ticker,
                trade_date=trade_date,
                base_url=base_url,
                model=model,
                on_progress=on_progress,
                on_result=on_result,
            )

            logger.info("深度分析任务完成: task_id=%s", task_id)

        except Exception as exc:
            logger.exception("深度分析任务失败: task_id=%s", task_id)
            self._repo.update_task(
                task_id,
                status="failed",
                error=str(exc),
                elapsed=time.time() - started_at,
            )
        finally:
            cancelled.set()

    # ── 报告生成 ─────────────────────────────────────────────────────────────

    @classmethod
    def _save_report(
        cls,
        task_id: str,
        ticker: str,
        trade_date: str,
        signal: str,
        stage_reports: Dict[str, str],
        elapsed: float,
    ) -> Optional[str]:
        """将深度分析结果保存为 Markdown 报告文件，返回相对路径."""
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        # 生成报告内容
        lines: List[str] = []
        lines.append(f"# 深度分析报告")
        lines.append("")
        lines.append(f"- **股票代码**: {ticker}")
        lines.append(f"- **分析日期**: {trade_date}")
        lines.append(f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- **耗时**: {elapsed:.0f}s")
        lines.append(f"- **任务ID**: {task_id}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(f"## 最终决策")
        lines.append("")
        lines.append(f"> {signal}")
        lines.append("")

        # 各阶段报告
        stage_order = [
            ("market", "📊 技术分析"),
            ("social", "💬 情绪分析"),
            ("news", "📰 新闻舆情"),
            ("fundamentals", "📋 基本面"),
            ("policy", "🏛️ 政策分析"),
            ("hot_money", "🔥 游资追踪"),
            ("lockup", "🔒 解禁监控"),
            ("quality_gate", "✅ 质量门控"),
            ("debate", "⚔️ 多空辩论"),
            ("trader", "💹 交易决策"),
            ("risk", "🛡️ 风控评估"),
            ("pm", "👔 最终决策"),
        ]

        for stage_id, stage_title in stage_order:
            content = stage_reports.get(stage_id, "")
            if not content.strip():
                continue
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append(f"## {stage_title}")
            lines.append("")
            lines.append(content)
            lines.append("")

        report_content = "\n".join(lines)

        # 文件名：deep_analysis_{ticker}_{trade_date}_{task_id}.md
        safe_date = trade_date.replace("-", "")
        filename = f"deep_analysis_{ticker}_{safe_date}_{task_id}.md"
        filepath = _REPORTS_DIR / filename

        filepath.write_text(report_content, encoding="utf-8")
        logger.info("深度分析报告已保存: %s", filepath)

        return filename

    # ── 飞书通知 ─────────────────────────────────────────────────────────────

    @classmethod
    def _notify_feishu(
        cls,
        task_id: str,
        ticker: str,
        trade_date: str,
        signal: str,
        stage_reports: Dict[str, str],
        elapsed: float,
        report_filename: Optional[str] = None,
    ) -> None:
        """发送深度分析完成通知到飞书，包含核心摘要 + 报告链接/附件."""
        try:
            from src.notification_sender.feishu_sender import FeishuSender
            from src.config import get_config
        except ImportError:
            logger.warning("通知服务不可用，跳过飞书通知")
            return

        feishu_url = os.getenv("FEISHU_WEBHOOK_URL", "")
        if not feishu_url:
            logger.debug("FEISHU_WEBHOOK_URL 未配置，跳过飞书通知")
            return

        config = get_config()
        sender = FeishuSender(config)

        # ── 1. 提取信号方向与颜色 ──
        sig_lower = signal.lower()
        if "bullish" in sig_lower or "buy" in sig_lower or "做多" in sig_lower or "看多" in sig_lower:
            direction = "📈 看多"
        elif "bearish" in sig_lower or "sell" in sig_lower or "做空" in sig_lower or "看空" in sig_lower:
            direction = "📉 看空"
        else:
            direction = "➡️ 观望"

        # ── 2. 提取核心摘要 ──
        core_summary = cls._extract_core_summary(signal, stage_reports)

        # ── 3. 提取关键指标 ──
        key_metrics: List[tuple] = []
        key_metrics.append(("股票", ticker))
        key_metrics.append(("日期", trade_date))
        key_metrics.append(("决策", direction))
        key_metrics.append(("耗时", f"{elapsed:.0f}s"))

        # 从最终决策中提取置信度/价格区间等
        pm_report = stage_reports.get("pm", "")
        if pm_report:
            # 尝试提取目标价格
            import re
            price_match = re.search(r"(?:目标价[格]?|price target)[：:\s]*(\d+\.?\d*)", pm_report, re.IGNORECASE)
            if price_match:
                key_metrics.append(("目标价", price_match.group(1)))

        trader_report = stage_reports.get("trader", "")
        if trader_report:
            risk_match = re.search(r"(?:止损|stop[_\s]?loss)[：:\s]*(\d+\.?\d*)", trader_report, re.IGNORECASE)
            if risk_match:
                key_metrics.append(("止损位", risk_match.group(1)))

        # ── 4. 上传报告到第三方存储 ──
        download_url = ""
        if report_filename:
            from src.services.storage_service import upload_report
            report_fullpath = _REPORTS_DIR / report_filename
            if report_fullpath.is_file():
                download_url = upload_report(report_fullpath)

        # ── 5. 尝试上传飞书云文档 ──
        doc_url = ""
        try:
            doc_url = cls._upload_to_feishu_doc(ticker, trade_date, task_id, signal, stage_reports, elapsed)
        except Exception:
            logger.debug("飞书云文档上传失败（非关键），仅发送链接", exc_info=True)

        # ── 6. 构建卡片并发送 ──
        title = f"深度分析报告 - {ticker}"
        if len(title) > 50:
            title = title[:47] + "..."

        # 构建摘要内容
        summary_lines = [
            f"{core_summary}",
            "",
        ]

        # 添加各阶段摘要
        stage_strip = cls._build_stage_strip(stage_reports)
        if stage_strip:
            summary_lines.append(f"**各阶段结论**:")
            summary_lines.append(stage_strip)

        summary = "\n".join(summary_lines)

        try:
            success = sender.send_report_card(
                title=title,
                summary=summary,
                key_metrics=key_metrics,
                signal=signal,
                report_url=download_url,
                doc_url=doc_url,
            )
            if success:
                logger.info("深度分析飞书通知发送成功: task_id=%s ticker=%s", task_id, ticker)
            else:
                logger.warning("深度分析飞书通知发送失败: task_id=%s ticker=%s", task_id, ticker)
        except Exception:
            logger.exception("飞书通知发送异常: task_id=%s", task_id)

    @classmethod
    def _extract_core_summary(
        cls,
        signal: str,
        stage_reports: Dict[str, str],
    ) -> str:
        """从分析结果中提取核心摘要（200字以内）."""
        sig_lower = signal.lower()

        # 优先使用 PM 最终决策（已包含综合判断）
        pm = stage_reports.get("pm", "")
        if pm.strip():
            lines = [l.strip() for l in pm.split("\n") if l.strip()]
            # 跳过纯分隔线和空行
            meaningful = [l for l in lines if not l.startswith("---") and len(l) > 5]
            if meaningful:
                summary = " ".join(meaningful[:3])
                if len(summary) > 300:
                    summary = summary[:297] + "..."
                return summary

        # 回退：使用 trader 决策
        trader = stage_reports.get("trader", "")
        if trader.strip():
            lines = [l.strip() for l in trader.split("\n") if l.strip()]
            meaningful = [l for l in lines if not l.startswith("---") and len(l) > 5]
            if meaningful:
                summary = " ".join(meaningful[:2])
                if len(summary) > 300:
                    summary = summary[:297] + "..."
                return summary

        # 再回退：基于信号构造摘要
        if "bullish" in sig_lower or "buy" in sig_lower:
            return "综合多维度分析，该股呈现看多信号，建议关注买入机会。"
        elif "bearish" in sig_lower or "sell" in sig_lower:
            return "综合多维度分析，该股呈现看空信号，建议谨慎操作。"
        else:
            return "综合多维度分析，该股当前方向不明确，建议观望。"

    @classmethod
    def _build_stage_strip(cls, stage_reports: Dict[str, str]) -> str:
        """构建各阶段一句话结论条."""
        stage_names = {
            "market": "📊 技术面",
            "social": "💬 情绪面",
            "news": "📰 新闻",
            "fundamentals": "📋 基本面",
            "debate": "⚔️ 多空辩论",
            "risk": "🛡️ 风控",
        }
        lines = []
        for stage_id, name in stage_names.items():
            content = stage_reports.get(stage_id, "")
            if not content.strip():
                continue
            # 取第一行有意义的内容
            for raw_line in content.split("\n"):
                line = raw_line.strip()
                if not line or line.startswith("---") or len(line) < 8:
                    continue
                # 清理格式（去除 markdown 标记）
                clean = line.replace("**", "").replace("##", "").replace("###", "").strip()
                if len(clean) > 120:
                    clean = clean[:117] + "..."
                lines.append(f"{name}: {clean}")
                break

        return "\n".join(lines[:6])  # 最多6条

    @classmethod
    def _upload_to_feishu_doc(
        cls,
        ticker: str,
        trade_date: str,
        task_id: str,
        signal: str,
        stage_reports: Dict[str, str],
        elapsed: float,
    ) -> str:
        """将报告上传为飞书云文档，返回文档链接."""
        try:
            from src.feishu_doc import FeishuDocManager
        except ImportError:
            return ""

        doc_mgr = FeishuDocManager()
        if not doc_mgr.is_configured():
            logger.debug("飞书云文档未配置（需 FEISHU_APP_ID/FEISHU_APP_SECRET/FEISHU_FOLDER_TOKEN），跳过")
            return ""

        # 生成完整报告内容
        from datetime import datetime

        lines: List[str] = []
        lines.append(f"# 深度分析报告")
        lines.append("")
        lines.append(f"- **股票代码**: {ticker}")
        lines.append(f"- **分析日期**: {trade_date}")
        lines.append(f"- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- **耗时**: {elapsed:.0f}s")
        lines.append(f"- **任务ID**: {task_id}")
        lines.append("")
        lines.append("---")
        lines.append("")

        sig_lower = signal.lower()
        if "bullish" in sig_lower or "buy" in sig_lower:
            direction = "📈 看多"
        elif "bearish" in sig_lower or "sell" in sig_lower:
            direction = "📉 看空"
        else:
            direction = "➡️ 观望"
        lines.append(f"## 最终决策: {direction}")
        lines.append("")
        lines.append(signal)
        lines.append("")

        stage_order = [
            ("market", "📊 技术分析"),
            ("social", "💬 情绪分析"),
            ("news", "📰 新闻舆情"),
            ("fundamentals", "📋 基本面"),
            ("policy", "🏛️ 政策分析"),
            ("hot_money", "🔥 游资追踪"),
            ("lockup", "🔒 解禁监控"),
            ("quality_gate", "✅ 质量门控"),
            ("debate", "⚔️ 多空辩论"),
            ("trader", "💹 交易决策"),
            ("risk", "🛡️ 风控评估"),
            ("pm", "👔 最终决策"),
        ]

        for stage_id, stage_title in stage_order:
            content = stage_reports.get(stage_id, "")
            if not content.strip():
                continue
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append(f"## {stage_title}")
            lines.append("")
            lines.append(content)
            lines.append("")

        doc_content = "\n".join(lines)
        doc_title = f"深度分析_{ticker}_{trade_date}"

        try:
            doc_url = doc_mgr.create_daily_doc(doc_title, doc_content)
            if doc_url:
                logger.info("深度分析飞书云文档已创建: %s -> %s", doc_title, doc_url)
                return doc_url
            else:
                logger.warning("飞书云文档创建返回空 URL")
        except Exception:
            logger.exception("飞书云文档创建异常")

        return ""
