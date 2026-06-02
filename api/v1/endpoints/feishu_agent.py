# -*- coding: utf-8 -*-
"""
飞书智能体（Aily）API 端点

提供与飞书智能体交互的 RESTful API：
- 会话管理（创建/查询）
- 消息发送
- 对话交互（同步 + 流式）
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
#  请求/响应模型
# ============================================================

class ChatRequest(BaseModel):
    """对话请求"""
    message: str = Field(..., description="用户消息内容", min_length=1, max_length=10000)
    session_id: Optional[str] = Field(None, description="会话 ID（不传则创建新会话）")
    max_wait_time: Optional[float] = Field(60.0, description="最大等待时间（秒）", ge=1, le=300)


class ChatResponse(BaseModel):
    """对话响应"""
    session_id: str = Field(..., description="会话 ID")
    reply_text: str = Field(..., description="智能体回复文本")
    status: str = Field("completed", description="运行状态")
    reasoning_content: str = Field("", description="思考过程内容")
    message_count: int = Field(0, description="回复消息数")


class SessionResponse(BaseModel):
    """会话信息"""
    session_id: str = Field(..., description="会话 ID")
    created: bool = Field(False, description="是否新创建")


class MessageItem(BaseModel):
    """消息项"""
    message_id: str
    content: str
    role: str
    content_type: str = "text"
    created_at: int = 0
    status: str = ""
    reasoning_content: str = ""


class MessageListResponse(BaseModel):
    """消息列表响应"""
    session_id: str
    messages: List[MessageItem] = Field(default_factory=list)
    total: int = 0


class SendMessageRequest(BaseModel):
    """发送消息请求"""
    content: str = Field(..., description="消息内容", min_length=1, max_length=10000)
    content_type: str = Field("text", description="内容类型")


class SendMessageResponse(BaseModel):
    """发送消息响应"""
    session_id: str
    message_id: str
    status: str = "sent"


class AgentHealthResponse(BaseModel):
    """智能体健康状态"""
    available: bool
    configured: bool
    app_id_masked: str = ""
    agent_app_id: str = ""


# ============================================================
#  健康检查
# ============================================================

@router.get(
    "/agent/health",
    response_model=AgentHealthResponse,
    tags=["Feishu Agent"],
    summary="智能体健康检查",
)
async def agent_health():
    """检查飞书智能体客户端是否可用"""
    from src.feishu_agent.client import FEISHU_SDK_AVAILABLE
    from src.config import get_config

    config = get_config()
    app_id = getattr(config, "feishu_app_id", None)
    app_secret = getattr(config, "feishu_app_secret", None)
    agent_app_id = getattr(config, "feishu_agent_app_id", None) or ""

    configured = bool(app_id and app_secret)

    return AgentHealthResponse(
        available=FEISHU_SDK_AVAILABLE and configured,
        configured=configured,
        app_id_masked=(app_id[:10] + "***") if app_id else "",
        agent_app_id=agent_app_id[:15] + "***" if agent_app_id else "",
    )


# ============================================================
#  会话管理
# ============================================================

@router.post(
    "/agent/sessions",
    response_model=SessionResponse,
    tags=["Feishu Agent"],
    summary="创建智能体会话",
)
async def create_agent_session():
    """创建新的飞书智能体会话"""
    try:
        from src.feishu_agent.client import get_feishu_agent_client

        client = get_feishu_agent_client()
        if client is None:
            raise HTTPException(status_code=503, detail="飞书智能体客户端不可用")

        session_id = client.create_session()

        return SessionResponse(
            session_id=session_id,
            created=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Feishu Agent API] 创建会话失败: %s", e)
        raise HTTPException(status_code=500, detail=f"创建会话失败: {e}")


@router.get(
    "/agent/sessions/{session_id}",
    tags=["Feishu Agent"],
    summary="查询会话详情",
)
async def get_agent_session(session_id: str):
    """查询指定会话的详情"""
    try:
        from src.feishu_agent.client import get_feishu_agent_client

        client = get_feishu_agent_client()
        if client is None:
            raise HTTPException(status_code=503, detail="飞书智能体客户端不可用")

        session = client.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="会话不存在")

        return {"session": session}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Feishu Agent API] 查询会话失败: %s", e)
        raise HTTPException(status_code=500, detail=f"查询会话失败: {e}")


# ============================================================
#  消息管理
# ============================================================

@router.post(
    "/agent/sessions/{session_id}/messages",
    response_model=SendMessageResponse,
    tags=["Feishu Agent"],
    summary="发送消息到智能体",
)
async def send_agent_message(session_id: str, req: SendMessageRequest):
    """向指定会话发送消息"""
    try:
        from src.feishu_agent.client import get_feishu_agent_client

        client = get_feishu_agent_client()
        if client is None:
            raise HTTPException(status_code=503, detail="飞书智能体客户端不可用")

        message_id = client.send_message(
            session_id=session_id,
            content=req.content,
            content_type=req.content_type,
        )

        return SendMessageResponse(
            session_id=session_id,
            message_id=message_id,
            status="sent",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Feishu Agent API] 发送消息失败: %s", e)
        raise HTTPException(status_code=500, detail=f"发送消息失败: {e}")


@router.get(
    "/agent/sessions/{session_id}/messages",
    response_model=MessageListResponse,
    tags=["Feishu Agent"],
    summary="获取会话消息列表",
)
async def list_agent_messages(
    session_id: str,
    page_size: int = Query(50, ge=1, le=200),
):
    """获取指定会话的消息列表"""
    try:
        from src.feishu_agent.client import get_feishu_agent_client

        client = get_feishu_agent_client()
        if client is None:
            raise HTTPException(status_code=503, detail="飞书智能体客户端不可用")

        messages = client.list_messages(session_id, page_size=page_size)

        return MessageListResponse(
            session_id=session_id,
            messages=[
                MessageItem(
                    message_id=m.message_id,
                    content=m.content,
                    role=m.role,
                    content_type=m.content_type,
                    created_at=m.created_at,
                    status=m.status,
                    reasoning_content=m.reasoning_content,
                )
                for m in messages
            ],
            total=len(messages),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Feishu Agent API] 获取消息列表失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取消息列表失败: {e}")


# ============================================================
#  对话交互
# ============================================================

@router.post(
    "/agent/chat",
    response_model=ChatResponse,
    tags=["Feishu Agent"],
    summary="与智能体对话（同步）",
    description="""
发送消息给飞书智能体并等待回复。

工作流程：
1. 如果没有提供 session_id，自动创建新会话
2. 发送用户消息到智能体
3. 触发智能体运行
4. 轮询等待智能体回复
5. 返回完整的回复内容
""",
)
async def chat_with_agent(req: ChatRequest):
    """与飞书智能体对话"""
    try:
        from src.feishu_agent.client import get_feishu_agent_client

        client = get_feishu_agent_client()
        if client is None:
            raise HTTPException(status_code=503, detail="飞书智能体客户端不可用")

        response = client.chat(
            message=req.message,
            session_id=req.session_id,
            max_wait_time=req.max_wait_time,
        )

        return ChatResponse(
            session_id=response.session_id,
            reply_text=response.reply_text,
            status=response.status,
            reasoning_content=response.reasoning_content,
            message_count=len(response.messages),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Feishu Agent API] 对话失败: %s", e)
        raise HTTPException(status_code=500, detail=f"对话失败: {e}")


@router.post(
    "/agent/chat/stream",
    tags=["Feishu Agent"],
    summary="与智能体流式对话",
    description="""
与飞书智能体进行流式对话，实时返回生成内容。

使用 Server-Sent Events (SSE) 格式推送数据，
客户端可以通过 EventSource 接收实时回复。
""",
)
async def chat_with_agent_stream(req: ChatRequest):
    """与飞书智能体流式对话"""
    import json
    import asyncio

    try:
        from src.feishu_agent.client import get_feishu_agent_client

        client = get_feishu_agent_client()
        if client is None:
            raise HTTPException(status_code=503, detail="飞书智能体客户端不可用")

        async def event_generator():
            try:
                # 在线程池中运行同步的流式对话
                loop = asyncio.get_event_loop()

                # 1. 确保有会话
                session_id = req.session_id
                if not session_id:
                    session_id = await loop.run_in_executor(None, client.create_session)
                    yield f"data: {json.dumps({'type': 'session_created', 'session_id': session_id}, ensure_ascii=False)}\n\n"

                # 2. 发送消息
                await loop.run_in_executor(
                    None, client.send_message, session_id, req.message
                )
                yield f"data: {json.dumps({'type': 'message_sent', 'session_id': session_id}, ensure_ascii=False)}\n\n"

                # 3. 创建运行
                run_id = await loop.run_in_executor(
                    None, client.create_run, session_id
                )
                yield f"data: {json.dumps({'type': 'run_started', 'run_id': run_id}, ensure_ascii=False)}\n\n"

                # 4. 流式轮询
                import time
                start_time = time.time()
                max_wait = req.max_wait_time or 60.0
                last_content_len = 0

                while True:
                    elapsed = time.time() - start_time
                    if elapsed > max_wait:
                        yield f"data: {json.dumps({'type': 'timeout', 'message': f'等待超时({max_wait}s)'}, ensure_ascii=False)}\n\n"
                        break

                    messages = await loop.run_in_executor(
                        None, client.list_messages, session_id
                    )
                    assistant_messages = [m for m in messages if m.role != "user"]
                    reply_text = "\n".join([m.content for m in assistant_messages if m.content]).strip()

                    if len(reply_text) > last_content_len:
                        last_content_len = len(reply_text)
                        yield f"data: {json.dumps({'type': 'content', 'text': reply_text}, ensure_ascii=False)}\n\n"

                    try:
                        status = await loop.run_in_executor(
                            None, client.get_run_status, session_id, run_id
                        )
                        if status["status"] in ("completed", "failed", "cancelled"):
                            messages = await loop.run_in_executor(
                                None, client.list_messages, session_id
                            )
                            assistant_messages = [m for m in messages if m.role != "user"]
                            final_text = "\n".join([m.content for m in assistant_messages if m.content]).strip()
                            reasoning = "\n".join([m.reasoning_content for m in assistant_messages if m.reasoning_content]).strip()
                            yield f"data: {json.dumps({'type': 'done', 'text': final_text, 'status': status['status'], 'session_id': session_id, 'reasoning': reasoning}, ensure_ascii=False)}\n\n"
                            break
                    except Exception:
                        pass

                    await asyncio.sleep(0.5)

            except Exception as e:
                logger.error("[Feishu Agent API] 流式对话异常: %s", e)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Feishu Agent API] 流式对话失败: %s", e)
        raise HTTPException(status_code=500, detail=f"流式对话失败: {e}")


# ============================================================
#  快捷接口：股票分析
# ============================================================

class StockAnalysisRequest(BaseModel):
    """股票分析请求"""
    code: str = Field(..., description="股票代码", min_length=1, max_length=20)
    question: Optional[str] = Field(None, description="具体问题（不传则默认分析）")
    session_id: Optional[str] = Field(None, description="会话 ID")


@router.post(
    "/agent/analyze-stock",
    response_model=ChatResponse,
    tags=["Feishu Agent"],
    summary="智能体股票分析",
    description="通过飞书智能体分析指定股票",
)
async def analyze_stock(req: StockAnalysisRequest):
    """让智能体分析股票"""
    try:
        from src.feishu_agent.client import get_feishu_agent_client

        client = get_feishu_agent_client()
        if client is None:
            raise HTTPException(status_code=503, detail="飞书智能体客户端不可用")

        if req.question:
            message = f"请分析股票 {req.code}：{req.question}"
        else:
            message = f"请对股票 {req.code} 进行全面分析，包括技术面、基本面和近期走势"

        response = client.chat(
            message=message,
            session_id=req.session_id,
        )

        return ChatResponse(
            session_id=response.session_id,
            reply_text=response.reply_text,
            status=response.status,
            reasoning_content=response.reasoning_content,
            message_count=len(response.messages),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Feishu Agent API] 股票分析失败: %s", e)
        raise HTTPException(status_code=500, detail=f"股票分析失败: {e}")


# ============================================================
#  技能调用（轻量模式）
# ============================================================

class SkillCallRequest(BaseModel):
    """技能调用请求"""
    app_id: str = Field(..., description="智能体应用 ID", min_length=1)
    skill_id: str = Field(..., description="技能 ID", min_length=1)
    input: str = Field(..., description="技能输入内容", min_length=1, max_length=10000)


class SkillCallResponse(BaseModel):
    """技能调用响应"""
    output: str = Field(..., description="技能输出")
    status: str = Field("completed", description="调用状态")


@router.post(
    "/agent/skill",
    response_model=SkillCallResponse,
    tags=["Feishu Agent"],
    summary="直接调用智能体技能",
    description="无需创建会话，直接调用智能体的指定技能并获取结果",
)
async def call_agent_skill(req: SkillCallRequest):
    """直接调用飞书智能体技能"""
    try:
        from src.feishu_agent.client import get_feishu_agent_client

        client = get_feishu_agent_client()
        if client is None:
            raise HTTPException(status_code=503, detail="飞书智能体客户端不可用")

        result = client.start_skill(
            app_id=req.app_id,
            skill_id=req.skill_id,
            skill_input=req.input,
        )

        return SkillCallResponse(
            output=result["output"],
            status=result.get("status", "completed"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[Feishu Agent API] 技能调用失败: %s", e)
        raise HTTPException(status_code=500, detail=f"技能调用失败: {e}")
