import asyncio
import logging

import pytest
from fastapi import HTTPException

from app import main
from app.schemas import ChatCompletionRequest, ChatMessage, ResponsesRequest


def test_chat_completions_logs_request_lifecycle(monkeypatch, caplog):
    monkeypatch.setattr(main, "choose_model", lambda _model: ("codex-cli", None))
    monkeypatch.setattr(main, "build_prompt_and_images", lambda _messages: ("prompt", []))

    async def _fake_run_codex_last_message(*_args, **_kwargs):
        return "ok"

    monkeypatch.setattr(main, "run_codex_last_message", _fake_run_codex_last_message)

    req = ChatCompletionRequest(
        model="gpt-5",
        messages=[ChatMessage(role="user", content="hello")],
        stream=False,
    )

    with caplog.at_level(logging.INFO, logger="app.main"):
        response = asyncio.run(main.chat_completions(req))

    assert response.choices[0].message.content == "ok"
    messages = [record.message for record in caplog.records]
    assert any("chat.completions request started" in msg for msg in messages)
    assert any("chat.completions request completed" in msg for msg in messages)


def test_responses_logs_codex_error(monkeypatch, caplog):
    monkeypatch.setattr(main, "choose_model", lambda _model: ("codex-cli", None))
    monkeypatch.setattr(main, "normalize_responses_input", lambda _input: [{"role": "user", "content": "ping"}])
    monkeypatch.setattr(main, "build_prompt_and_images", lambda _messages: ("prompt", []))

    async def _fake_run_codex_last_message(*_args, **_kwargs):
        raise main.CodexError("upstream failed", status_code=502)

    monkeypatch.setattr(main, "run_codex_last_message", _fake_run_codex_last_message)

    req = ResponsesRequest(model="gpt-5", input="ping", stream=False)

    with caplog.at_level(logging.WARNING, logger="app.main"):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(main.responses_endpoint(req))

    assert exc_info.value.status_code == 502
    warnings = [record.message for record in caplog.records if record.levelno >= logging.WARNING]
    assert any("responses request failed" in msg and "status=502" in msg for msg in warnings)
