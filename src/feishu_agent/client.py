# -*- coding: utf-8 -*-
"""
===================================
飞书智能体（Aily）客户端
===================================

基于飞书开放平台 Aily API（aily-v1），实现与飞书智能体的核心交互：

1. 创建会话 → POST /open-apis/aily/v1/sessions
2. 发送消息 → POST /open-apis/aily/v1/sessions/{session_id}/messages
3. 创建运行 → POST /open-apis/aily/v1/sessions/{session_id}/runs
4. 轮询运行状态 → GET /open-apis/aily/v1/sessions/{session_id}/runs/{run_id}
5. 获取回复消息 → GET /open-apis/aily/v1/sessions/{session_id}/messages

认证方式：使用 App ID + App Secret 获取 tenant_access_token
（由 lark-oapi SDK 自动管理 token 生命周期）

API 文档：https://open.feishu.cn/document/aily-v1/
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional, List

logger = logging.getLogger(__name__)

# 尝试导入飞书 SDK
try:
    import lark_oapi as lark
    from lark_oapi.api.aily.v1 import (
        CreateAilySessionRequest,
        CreateAilySessionRequestBody,
        CreateAilySessionResponse,
        CreateAilySessionAilyMessageRequest,
        CreateAilySessionAilyMessageRequestBody,
        CreateAilySessionAilyMessageResponse,
        CreateAilySessionRunRequest,
        CreateAilySessionRunRequestBody,
        CreateAilySessionRunResponse,
        GetAilySessionRunRequest,
        GetAilySessionRunResponse,
        ListAilySessionAilyMessageRequest,
        ListAilySessionAilyMessageResponse,
        GetAilySessionRequest,
        GetAilySessionResponse,
        AilyMessage,
    )

    FEISHU_SDK_AVAILABLE = True
except ImportError:
    FEISHU_SDK_AVAILABLE = False
    logger.warning("[Feishu Agent] lark-oapi SDK 未安装，智能体功能不可用")

from src.feishu_agent.exceptions import (
    FeishuAgentError,
    AuthenticationError,
    SessionError,
    MessageError,
    RunError,
    TimeoutError as AgentTimeoutError,
)


@dataclass
class AgentMessage:
    """智能体消息"""
    message_id: str
    session_id: str
    content: str
    content_type: str = "text"
    role: str = ""  # "user" 或 "assistant"
    created_at: int = 0
    status: str = ""
    reasoning_content: str = ""


@dataclass
class AgentResponse:
    """智能体回复结果"""
    session_id: str
    run_id: str
    messages: List[AgentMessage] = field(default_factory=list)
    reply_text: str = ""
    status: str = "completed"
    reasoning_content: str = ""


class FeishuAgentClient:
    """
    飞书智能体（Aily）客户端

    使用方式：
        client = FeishuAgentClient()
        response = client.chat("帮我分析一下600519")
        print(response.reply_text)

    或者直接使用 app_id/app_secret：
        client = FeishuAgentClient(
            app_id="cli_xxx",
            app_secret="xxx",
            agent_app_id="aily_xxx"
        )
    """

    # 默认轮询配置
    DEFAULT_POLL_INTERVAL = 1.0  # 轮询间隔（秒）
    DEFAULT_MAX_WAIT_TIME = 120.0  # 最大等待时间（秒）

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        agent_app_id: Optional[str] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        max_wait_time: float = DEFAULT_MAX_WAIT_TIME,
    ):
        """
        初始化飞书智能体客户端

        Args:
            app_id: 飞书应用 ID（不传则从环境变量 FEISHU_APP_ID 读取）
            app_secret: 飞书应用密钥（不传则从环境变量 FEISHU_APP_SECRET 读取）
            agent_app_id: 智能体应用 ID（不传则从环境变量 FEISHU_AGENT_APP_ID 读取）
            poll_interval: 轮询运行状态的间隔（秒）
            max_wait_time: 等待智能体回复的最大时间（秒）
        """
        if not FEISHU_SDK_AVAILABLE:
            raise ImportError(
                "lark-oapi SDK 未安装，无法使用飞书智能体功能。\n"
                "请运行: pip install lark-oapi"
            )

        from src.config import get_config
        config = get_config()

        # 凭据优先级：参数 > 环境变量 > 配置文件
        self._app_id = app_id or os.getenv("FEISHU_APP_ID") or getattr(config, "feishu_app_id", None)
        self._app_secret = app_secret or os.getenv("FEISHU_APP_SECRET") or getattr(config, "feishu_app_secret", None)
        self._agent_app_id = agent_app_id or os.getenv("FEISHU_AGENT_APP_ID") or getattr(config, "feishu_agent_app_id", None)

        self._poll_interval = poll_interval
        self._max_wait_time = max_wait_time

        # 验证凭据
        if not self._app_id or not self._app_secret:
            raise AuthenticationError(
                "缺少飞书应用凭据，请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET 环境变量"
            )

        # 初始化 SDK 客户端
        # SDK 会自动处理 tenant_access_token 的获取和刷新
        self._client = lark.Client.builder() \
            .app_id(self._app_id) \
            .app_secret(self._app_secret) \
            .log_level(lark.LogLevel.WARNING) \
            .build()

        logger.info(
            "[Feishu Agent] 客户端初始化完成 "
            "(app_id=%s, agent_app_id=%s)",
            self._app_id[:10] + "***" if self._app_id else "None",
            self._agent_app_id[:10] + "***" if self._agent_app_id else "None",
        )

    @property
    def is_configured(self) -> bool:
        """检查是否完整配置"""
        return bool(self._app_id and self._app_secret)

    def _validate_response(self, response, operation: str) -> None:
        """
        验证 SDK 响应是否成功

        Args:
            response: SDK 响应对象
            operation: 操作描述（用于日志）

        Raises:
            FeishuAgentError: 响应失败时抛出对应异常
        """
        if response.success():
            return

        code = response.code
        msg = response.msg or "未知错误"
        log_id = getattr(response, "get_log_id", lambda: "")() or ""

        logger.error(
            "[Feishu Agent] %s 失败: code=%s, msg=%s, log_id=%s",
            operation, code, msg, log_id,
        )

        # 根据错误码分类
        if code in (99991663, 99991664, 99991665, 99991668, 99991669):
            # tenant_access_token 相关错误
            raise AuthenticationError(
                f"{operation}失败: {msg}",
                code=code,
                details=f"log_id={log_id}"
            )
        elif code == 99991672:
            # 应用未开通该 API 权限
            raise AuthenticationError(
                f"应用未开通 Aily API 权限: {msg}",
                code=code,
                details="请在飞书开发者后台开通「智能伙伴」相关权限"
            )
        else:
            raise FeishuAgentError(
                f"{operation}失败: {msg}",
                code=code,
                details=f"log_id={log_id}"
            )

    # ------------------------------------------------------------------ #
    #  会话管理                                                            #
    # ------------------------------------------------------------------ #

    def create_session(
        self,
        channel_context: Optional[str] = None,
        metadata: Optional[str] = None,
    ) -> str:
        """
        创建智能体会话

        Args:
            channel_context: 渠道上下文（JSON 字符串）
            metadata: 自定义元数据（JSON 字符串）

        Returns:
            session_id: 会话 ID

        Raises:
            SessionError: 创建失败
        """
        try:
            body = CreateAilySessionRequestBody.builder()
            if channel_context:
                body.channel_context(channel_context)
            if metadata:
                body.metadata(metadata)

            request = CreateAilySessionRequest.builder() \
                .request_body(body.build()) \
                .build()

            response = self._client.aily.v1.aily_session.create(request)
            self._validate_response(response, "创建会话")

            session_id = response.data.session.id
            logger.info("[Feishu Agent] 会话创建成功: session_id=%s", session_id)
            return session_id

        except FeishuAgentError:
            raise
        except Exception as e:
            logger.error("[Feishu Agent] 创建会话异常: %s", e)
            raise SessionError(f"创建会话异常: {e}") from e

    def get_session(self, session_id: str) -> Optional[dict]:
        """
        查询会话详情

        Args:
            session_id: 会话 ID

        Returns:
            会话信息字典，不存在返回 None
        """
        try:
            request = GetAilySessionRequest.builder() \
                .aily_session_id(session_id) \
                .build()

            response = self._client.aily.v1.aily_session.get(request)
            self._validate_response(response, "查询会话")

            session = response.data.session
            return {
                "id": session.id,
                "created_at": getattr(session, "created_at", None),
                "metadata": getattr(session, "metadata", None),
            }
        except FeishuAgentError as e:
            if e.code == 99991673:  # 会话不存在
                return None
            raise
        except Exception as e:
            logger.error("[Feishu Agent] 查询会话异常: %s", e)
            raise SessionError(f"查询会话异常: {e}") from e

    # ------------------------------------------------------------------ #
    #  消息管理                                                            #
    # ------------------------------------------------------------------ #

    def send_message(
        self,
        session_id: str,
        content: str,
        content_type: str = "text",
        file_ids: Optional[List[str]] = None,
        quote_message_id: Optional[str] = None,
    ) -> str:
        """
        向智能体发送消息

        Args:
            session_id: 会话 ID
            content: 消息内容
            content_type: 内容类型（text/image/file 等）
            file_ids: 附件文件 ID 列表
            quote_message_id: 引用消息 ID

        Returns:
            message_id: 消息 ID

        Raises:
            MessageError: 发送失败
        """
        try:
            body = CreateAilySessionAilyMessageRequestBody.builder() \
                .content(content) \
                .content_type(content_type)

            if file_ids:
                body.file_ids(file_ids)
            if quote_message_id:
                body.quote_message_id(quote_message_id)

            request = CreateAilySessionAilyMessageRequest.builder() \
                .aily_session_id(session_id) \
                .request_body(body.build()) \
                .build()

            response = self._client.aily.v1.aily_session_aily_message.create(request)
            self._validate_response(response, "发送消息")

            message_id = response.data.message.id
            logger.info(
                "[Feishu Agent] 消息发送成功: session_id=%s, message_id=%s",
                session_id, message_id,
            )
            return message_id

        except FeishuAgentError:
            raise
        except Exception as e:
            logger.error("[Feishu Agent] 发送消息异常: %s", e)
            raise MessageError(f"发送消息异常: {e}") from e

    def list_messages(
        self,
        session_id: str,
        page_size: int = 50,
        page_token: Optional[str] = None,
    ) -> List[AgentMessage]:
        """
        获取会话消息列表

        Args:
            session_id: 会话 ID
            page_size: 每页数量
            page_token: 分页标记

        Returns:
            消息列表
        """
        try:
            req_builder = ListAilySessionAilyMessageRequest.builder() \
                .aily_session_id(session_id) \
                .page_size(page_size)
            if page_token:
                req_builder.page_token(page_token)

            request = req_builder.build()
            response = self._client.aily.v1.aily_session_aily_message.list(request)
            self._validate_response(response, "获取消息列表")

            messages = []
            for msg in (response.data.messages or []):
                sender = getattr(msg, "sender", None)
                role = getattr(sender, "sender_type", "user") if sender else "user"

                messages.append(AgentMessage(
                    message_id=msg.id or "",
                    session_id=session_id,
                    content=msg.content or "",
                    content_type=msg.content_type or "text",
                    role=role,
                    created_at=getattr(msg, "created_at", 0) or 0,
                    status=getattr(msg, "status", "") or "",
                    reasoning_content=getattr(msg, "reasoning_content", "") or "",
                ))

            return messages

        except FeishuAgentError:
            raise
        except Exception as e:
            logger.error("[Feishu Agent] 获取消息列表异常: %s", e)
            raise MessageError(f"获取消息列表异常: {e}") from e

    # ------------------------------------------------------------------ #
    #  技能调用（直接调用，无需会话）                                        #
    # ------------------------------------------------------------------ #

    def start_skill(
        self,
        app_id: str,
        skill_id: str,
        skill_input: str,
    ) -> dict:
        """
        直接调用智能体技能（无需创建会话）

        适用场景：单次调用智能体的某个具体技能，获取结果后即结束。
        这是比会话模式更轻量的交互方式。

        Args:
            app_id: 智能体应用 ID（Aily 应用 ID）
            skill_id: 技能 ID
            skill_input: 技能输入内容

        Returns:
            {"output": str, "status": str}

        Raises:
            RunError: 调用失败
        """
        try:
            from lark_oapi.api.aily.v1 import (
                StartAppSkillRequest,
                StartAppSkillRequestBody,
            )

            body = StartAppSkillRequestBody.builder() \
                .input(skill_input) \
                .build()

            request = StartAppSkillRequest.builder() \
                .app_id(app_id) \
                .skill_id(skill_id) \
                .request_body(body) \
                .build()

            response = self._client.aily.v1.app_skill.start(request)
            self._validate_response(response, "调用技能")

            result = {
                "output": response.data.output or "",
                "status": response.data.status or "completed",
            }

            logger.info(
                "[Feishu Agent] 技能调用成功: app_id=%s, skill_id=%s, output_len=%d",
                app_id[:10] + "***", skill_id, len(result["output"]),
            )
            return result

        except FeishuAgentError:
            raise
        except Exception as e:
            logger.error("[Feishu Agent] 调用技能异常: %s", e)
            raise RunError(f"调用技能异常: {e}") from e

    # ------------------------------------------------------------------ #
    #  运行管理                                                            #
    # ------------------------------------------------------------------ #

    def create_run(
        self,
        session_id: str,
        app_id: Optional[str] = None,
        skill_id: Optional[str] = None,
        skill_input: Optional[str] = None,
        metadata: Optional[str] = None,
    ) -> str:
        """
        创建智能体运行（触发 AI 处理会话中的消息）

        Args:
            session_id: 会话 ID
            app_id: 智能体应用 ID（默认使用初始化时的 agent_app_id）
            skill_id: 技能 ID（可选，不传则使用智能体默认行为）
            skill_input: 技能输入（JSON 字符串）
            metadata: 自定义元数据

        Returns:
            run_id: 运行 ID

        Raises:
            RunError: 创建失败
        """
        try:
            effective_app_id = app_id or self._agent_app_id

            body_builder = CreateAilySessionRunRequestBody.builder()
            if effective_app_id:
                body_builder.app_id(effective_app_id)
            if skill_id:
                body_builder.skill_id(skill_id)
            if skill_input:
                body_builder.skill_input(skill_input)
            if metadata:
                body_builder.metadata(metadata)

            request = CreateAilySessionRunRequest.builder() \
                .aily_session_id(session_id) \
                .request_body(body_builder.build()) \
                .build()

            response = self._client.aily.v1.aily_session_run.create(request)
            self._validate_response(response, "创建运行")

            run_id = response.data.run.id
            logger.info(
                "[Feishu Agent] 运行创建成功: session_id=%s, run_id=%s",
                session_id, run_id,
            )
            return run_id

        except FeishuAgentError:
            raise
        except Exception as e:
            logger.error("[Feishu Agent] 创建运行异常: %s", e)
            raise RunError(f"创建运行异常: {e}") from e

    def get_run_status(self, session_id: str, run_id: str) -> dict:
        """
        获取运行状态

        Args:
            session_id: 会话 ID
            run_id: 运行 ID

        Returns:
            运行状态信息字典
            {
                "id": str,
                "status": "queued|in_progress|completed|failed|cancelled",
                "error": dict|None,
                "started_at": int,
                "ended_at": int,
            }

        Raises:
            RunError: 查询失败
        """
        try:
            request = GetAilySessionRunRequest.builder() \
                .aily_session_id(session_id) \
                .aily_session_run_id(run_id) \
                .build()

            response = self._client.aily.v1.aily_session_run.get(request)
            self._validate_response(response, "获取运行状态")

            run = response.data.run
            error_info = None
            if run.error:
                error_info = {
                    "code": getattr(run.error, "code", ""),
                    "message": getattr(run.error, "message", ""),
                }

            return {
                "id": run.id,
                "status": run.status or "unknown",
                "error": error_info,
                "started_at": getattr(run, "started_at", 0) or 0,
                "ended_at": getattr(run, "ended_at", 0) or 0,
            }

        except FeishuAgentError:
            raise
        except Exception as e:
            logger.error("[Feishu Agent] 获取运行状态异常: %s", e)
            raise RunError(f"获取运行状态异常: {e}") from e

    def wait_for_completion(
        self,
        session_id: str,
        run_id: str,
        poll_interval: Optional[float] = None,
        max_wait_time: Optional[float] = None,
    ) -> dict:
        """
        等待智能体运行完成（轮询直到完成或超时）

        Args:
            session_id: 会话 ID
            run_id: 运行 ID
            poll_interval: 轮询间隔（秒），默认使用初始化值
            max_wait_time: 最大等待时间（秒），默认使用初始化值

        Returns:
            最终运行状态

        Raises:
            TimeoutError: 等待超时
            RunError: 运行失败
        """
        interval = poll_interval or self._poll_interval
        max_wait = max_wait_time or self._max_wait_time

        start_time = time.time()
        last_status = ""

        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait:
                raise AgentTimeoutError(
                    f"等待智能体回复超时（已等待 {elapsed:.1f}s）",
                    details=f"session_id={session_id}, run_id={run_id}, last_status={last_status}"
                )

            status = self.get_run_status(session_id, run_id)
            current_status = status["status"]

            if current_status != last_status:
                logger.debug(
                    "[Feishu Agent] 运行状态变更: %s → %s (elapsed=%.1fs)",
                    last_status, current_status, elapsed,
                )
                last_status = current_status

            if current_status in ("completed", "failed", "cancelled"):
                if current_status == "failed":
                    error = status.get("error", {})
                    raise RunError(
                        f"智能体运行失败: {error.get('message', '未知错误')}",
                        code=error.get("code", -1),
                        details=f"session_id={session_id}, run_id={run_id}"
                    )
                elif current_status == "cancelled":
                    raise RunError(
                        "智能体运行被取消",
                        details=f"session_id={session_id}, run_id={run_id}"
                    )
                logger.info(
                    "[Feishu Agent] 运行完成: session_id=%s, run_id=%s, elapsed=%.1fs",
                    session_id, run_id, elapsed,
                )
                return status

            time.sleep(interval)

    # ------------------------------------------------------------------ #
    #  高层 API：一站式对话                                                  #
    # ------------------------------------------------------------------ #

    def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        poll_interval: Optional[float] = None,
        max_wait_time: Optional[float] = None,
    ) -> AgentResponse:
        """
        与智能体对话（一站式方法）

        自动完成：创建会话（如需要）→ 发送消息 → 触发运行 → 等待回复 → 获取结果

        Args:
            message: 用户消息内容
            session_id: 会话 ID（不传则自动创建新会话）
            poll_interval: 轮询间隔（秒）
            max_wait_time: 最大等待时间（秒）

        Returns:
            AgentResponse: 智能体回复

        Raises:
            FeishuAgentError: 交互过程中的任何异常
        """
        try:
            # 1. 确保有会话
            if not session_id:
                session_id = self.create_session()
                logger.info("[Feishu Agent] 自动创建会话: %s", session_id)

            # 2. 发送消息
            msg_id = self.send_message(session_id, message)
            logger.info("[Feishu Agent] 消息已发送: %s", msg_id)

            # 3. 触发智能体运行
            run_id = self.create_run(session_id)
            logger.info("[Feishu Agent] 运行已创建: %s", run_id)

            # 4. 等待运行完成
            status = self.wait_for_completion(
                session_id, run_id,
                poll_interval=poll_interval,
                max_wait_time=max_wait_time,
            )

            # 5. 获取智能体回复
            messages = self.list_messages(session_id)
            assistant_messages = [m for m in messages if m.role != "user"]

            # 合并所有智能体回复
            reply_text = ""
            reasoning = ""
            for msg in assistant_messages:
                if msg.content:
                    reply_text += msg.content + "\n"
                if msg.reasoning_content:
                    reasoning += msg.reasoning_content + "\n"

            reply_text = reply_text.strip()
            reasoning = reasoning.strip()

            logger.info(
                "[Feishu Agent] 对话完成: session_id=%s, reply_len=%d",
                session_id, len(reply_text),
            )

            return AgentResponse(
                session_id=session_id,
                run_id=run_id,
                messages=assistant_messages,
                reply_text=reply_text,
                status=status["status"],
                reasoning_content=reasoning,
            )

        except FeishuAgentError:
            raise
        except Exception as e:
            logger.error("[Feishu Agent] 对话异常: %s", e)
            raise FeishuAgentError(f"智能体对话异常: {e}") from e

    def chat_stream(
        self,
        message: str,
        session_id: Optional[str] = None,
        poll_interval: float = 0.5,
        max_wait_time: float = 120.0,
    ):
        """
        与智能体流式对话（生成器）

        每次 yield 当前的回复文本，直到智能体运行完成。

        Args:
            message: 用户消息内容
            session_id: 会话 ID
            poll_interval: 轮询间隔（秒）
            max_wait_time: 最大等待时间（秒）

        Yields:
            AgentResponse: 智能体回复（每次 yield 都是最新的完整状态）
        """
        try:
            if not session_id:
                session_id = self.create_session()
                logger.info("[Feishu Agent] 自动创建会话(流式): %s", session_id)

            self.send_message(session_id, message)
            run_id = self.create_run(session_id)

            start_time = time.time()
            last_content_len = 0

            while True:
                elapsed = time.time() - start_time
                if elapsed > max_wait_time:
                    # 超时，返回已有内容
                    messages = self.list_messages(session_id)
                    assistant_messages = [m for m in messages if m.role != "user"]
                    reply_text = "\n".join([m.content for m in assistant_messages if m.content]).strip()
                    yield AgentResponse(
                        session_id=session_id,
                        run_id=run_id,
                        messages=assistant_messages,
                        reply_text=reply_text,
                        status="timeout",
                    )
                    return

                # 获取最新消息
                messages = self.list_messages(session_id)
                assistant_messages = [m for m in messages if m.role != "user"]
                reply_text = "\n".join([m.content for m in assistant_messages if m.content]).strip()

                # 如果有新内容，yield
                if len(reply_text) > last_content_len:
                    last_content_len = len(reply_text)
                    yield AgentResponse(
                        session_id=session_id,
                        run_id=run_id,
                        messages=assistant_messages,
                        reply_text=reply_text,
                        status="streaming",
                    )

                # 检查运行状态
                try:
                    status = self.get_run_status(session_id, run_id)
                    if status["status"] in ("completed", "failed", "cancelled"):
                        # 最后一次获取完整消息
                        messages = self.list_messages(session_id)
                        assistant_messages = [m for m in messages if m.role != "user"]
                        reply_text = "\n".join([m.content for m in assistant_messages if m.content]).strip()
                        reasoning = "\n".join([m.reasoning_content for m in assistant_messages if m.reasoning_content]).strip()
                        yield AgentResponse(
                            session_id=session_id,
                            run_id=run_id,
                            messages=assistant_messages,
                            reply_text=reply_text,
                            status=status["status"],
                            reasoning_content=reasoning,
                        )
                        return
                except Exception:
                    pass

                time.sleep(poll_interval)

        except FeishuAgentError:
            raise
        except Exception as e:
            logger.error("[Feishu Agent] 流式对话异常: %s", e)
            raise FeishuAgentError(f"流式对话异常: {e}") from e


# 全局客户端实例（延迟初始化）
_agent_client: Optional[FeishuAgentClient] = None


def get_feishu_agent_client() -> Optional[FeishuAgentClient]:
    """获取全局飞书智能体客户端实例"""
    global _agent_client

    if _agent_client is None and FEISHU_SDK_AVAILABLE:
        try:
            _agent_client = FeishuAgentClient()
        except (AuthenticationError, ImportError) as e:
            logger.warning("[Feishu Agent] 无法创建客户端: %s", e)
            return None

    return _agent_client


def reset_agent_client() -> None:
    """重置全局客户端（主要用于测试）"""
    global _agent_client
    _agent_client = None


# 需要 os 模块（在文件顶部已使用）
import os
