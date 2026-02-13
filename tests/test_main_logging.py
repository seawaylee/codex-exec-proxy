import asyncio
import logging
import re
import sys

import pytest
from fastapi import HTTPException

from app import main
from app.schemas import ChatCompletionRequest, ChatMessage, ResponsesRequest


def test_app_main_logger_defaults_to_info_level():
    assert main.logger.getEffectiveLevel() <= logging.INFO


def test_app_main_logger_has_handler_for_info_logs():
    assert len(main.logger.handlers) > 0


def test_app_main_logger_uses_stdout_stream_handler():
    assert any(
        isinstance(handler, logging.StreamHandler) and getattr(handler, "stream", None) is sys.stdout
        for handler in main.logger.handlers
    )


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
    assert any(
        "chat.completions request started" in msg
        and "called_at=" in msg
        and "params=" in msg
        and "request_preview=" in msg
        for msg in messages
    )
    started_msg = next(msg for msg in messages if "chat.completions request started" in msg)
    matched = re.search(r"called_at=(\d{6})\b", started_msg)
    assert matched is not None
    assert any(
        "chat.completions request completed" in msg
        and "duration_ms=" in msg
        and "response_chars=" in msg
        and "response_preview=" in msg
        for msg in messages
    )


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
    assert any(
        "responses request failed" in msg
        and "status=502" in msg
        and "duration_ms=" in msg
        and "request_params=" in msg
        for msg in warnings
    )
