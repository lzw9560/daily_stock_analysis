# -*- coding: utf-8 -*-

from __future__ import annotations

import types
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.v1.endpoints.agent import router
from fastapi import FastAPI


app = FastAPI()
app.include_router(router, prefix="/api/v1/agent")
client = TestClient(app)


class _FakeResult:
    success = True
    content = "ok"
    error = None
    total_steps = 3
    total_tokens = 42
    provider = "openai"
    model = "gpt"
    tool_calls_log = []


class _FakeExecutor:
    def chat(self, **kwargs):
        return _FakeResult()


@patch("api.v1.endpoints.agent.get_config")
@patch("api.v1.endpoints.agent._build_executor")
def test_chat_returns_runtime(mock_build_executor, mock_get_config):
    mock_get_config.return_value.is_agent_available.return_value = True
    mock_get_config.return_value.agent_orchestrator_mode = "debate"
    mock_get_config.return_value.agent_arch = "multi"
    mock_build_executor.return_value = _FakeExecutor()

    response = client.post("/api/v1/agent/chat", json={"message": "test", "context": {"stock_code": "600519"}})
    assert response.status_code == 200
    body = response.json()
    assert body["runtime"]["mode"] == "debate"
    assert body["runtime"]["debate"]["stages"] == ["research", "battle", "consensus"]
