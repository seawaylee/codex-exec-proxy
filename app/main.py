import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from typing import AsyncIterator, List

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .codex import CodexError, run_codex, run_codex_last_message
from .config import settings
from .deps import rate_limiter, verify_api_key
from .model_registry import (
    choose_model,
    get_available_models,
    initialize_model_registry,
)
from .security import assert_local_only_or_raise
from .prompt import build_prompt_and_images, normalize_responses_input
from .images import save_image_to_temp
from .schemas import (
    ChatChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessageResponse,
    ResponsesRequest,
    ResponsesObject,
    ResponsesMessage,
    ResponsesOutputText,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    logger.addHandler(stdout_handler)

app = FastAPI()

_LOG_PREVIEW_LIMIT = 200


def _now_hhmmss() -> str:
    return datetime.now().strftime("%H%M%S")


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _truncate_text(text: str, limit: int = _LOG_PREVIEW_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...(truncated, total={len(text)})"


def _extract_message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return " ".join(parts)
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text
    return ""


def _build_request_preview(messages: List[dict]) -> str:
    previews: list[str] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = _extract_message_text(item.get("content"))
        if text:
            previews.append(f"{role}:{text}" if role else text)
        if len(" | ".join(previews)) >= _LOG_PREVIEW_LIMIT:
            break
    return _truncate_text(" | ".join(previews))


def _compact_json(payload: dict) -> str:
    filtered = {k: v for k, v in payload.items() if v is not None}
    return json.dumps(filtered, ensure_ascii=False, sort_keys=True, default=str)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    await initialize_model_registry()


@app.get("/v1/models", dependencies=[Depends(rate_limiter), Depends(verify_api_key)])
async def list_models():
    """Return available model list."""
    return {"data": [{"id": model} for model in get_available_models(include_reasoning_aliases=True)]}


@app.post("/v1/chat/completions", dependencies=[Depends(rate_limiter), Depends(verify_api_key)])
async def chat_completions(req: ChatCompletionRequest):
    started_at = time.perf_counter()
    called_at = _now_hhmmss()
    message_dicts = [m.model_dump() for m in req.messages]
    request_params = {
        "model": req.model,
        "stream": req.stream,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "message_count": len(req.messages),
    }

    try:
        model_name, alias_effort = choose_model(req.model)
    except ValueError as e:
        logger.warning(
            "chat.completions request failed status=404 called_at=%s duration_ms=%s request_params=%s error=%s",
            called_at,
            _elapsed_ms(started_at),
            _compact_json(request_params),
            e,
        )
        raise HTTPException(
            status_code=404,
            detail={
                "message": str(e),
                "type": "invalid_request_error",
                "code": "model_not_found",
            },
        )

    prompt, image_urls = build_prompt_and_images(message_dicts)
    x_overrides = req.x_codex.model_dump(exclude_none=True) if req.x_codex else {}
    if alias_effort and "reasoning_effort" not in x_overrides:
        x_overrides["reasoning_effort"] = alias_effort
    overrides = x_overrides or None
    request_params.update(
        {
            "resolved_model": model_name,
            "image_count": len(image_urls),
            "overrides": overrides,
        }
    )
    request_preview = _build_request_preview(message_dicts)
    logger.info(
        "chat.completions request started called_at=%s params=%s request_preview=%s",
        called_at,
        _compact_json(request_params),
        request_preview,
    )

    # Safety gate: only allow danger-full-access when explicitly enabled
    if overrides and overrides.get("sandbox") == "danger-full-access":
        if not settings.allow_danger_full_access:
            raise HTTPException(status_code=400, detail="danger-full-access is disabled by server policy")

    # Enforce local-only model provider when enabled
    if settings.local_only:
        try:
            assert_local_only_or_raise()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    image_paths: List[str] = []
    try:
        for u in image_urls:
            image_paths.append(save_image_to_temp(u))
    except ValueError as e:
        for p in image_paths:
            try:
                os.remove(p)
            except Exception:
                pass
        raise HTTPException(status_code=400, detail=str(e))

    try:
        if req.stream:
            async def event_gen() -> AsyncIterator[bytes]:
                response_chars = 0
                response_preview = ""
                stream_status = 200
                try:
                    async for text in run_codex(prompt, overrides, image_paths, model=model_name):
                        if text:
                            response_chars += len(text)
                            if len(response_preview) < _LOG_PREVIEW_LIMIT:
                                response_preview += text[: _LOG_PREVIEW_LIMIT - len(response_preview)]
                            chunk = {
                                "choices": [
                                    {"delta": {"content": text}, "index": 0, "finish_reason": None}
                                ]
                            }
                            yield f"data: {json.dumps(chunk)}\n\n".encode()
                except CodexError as e:
                    status = getattr(e, "status_code", None) or 500
                    stream_status = status
                    logger.warning(
                        "chat.completions request failed status=%s called_at=%s duration_ms=%s request_params=%s response_chars=%s response_preview=%s error=%s",
                        status,
                        called_at,
                        _elapsed_ms(started_at),
                        _compact_json(request_params),
                        response_chars,
                        _truncate_text(response_preview),
                        e,
                    )
                    err_obj = {
                        "error": {
                            "message": str(e),
                            "type": "server_error" if status >= 500 else "upstream_error",
                            "code": None,
                        }
                    }
                    yield f"data: {json.dumps(err_obj)}\n\n".encode()
                finally:
                    logger.info(
                        "chat.completions request completed status=%s stream=%s duration_ms=%s response_chars=%s response_preview=%s",
                        stream_status,
                        req.stream,
                        _elapsed_ms(started_at),
                        response_chars,
                        _truncate_text(response_preview),
                    )
                    yield b"data: [DONE]\n\n"

            return StreamingResponse(event_gen(), media_type="text/event-stream")
        else:
            final = await run_codex_last_message(prompt, overrides, image_paths, model=model_name)
            logger.info(
                "chat.completions request completed status=200 stream=%s duration_ms=%s response_chars=%s response_preview=%s",
                req.stream,
                _elapsed_ms(started_at),
                len(final),
                _truncate_text(final),
            )
            resp = ChatCompletionResponse(
                choices=[ChatChoice(message=ChatMessageResponse(content=final))]
            )
            return resp
    except CodexError as e:
        status = getattr(e, "status_code", None) or 500
        logger.warning(
            "chat.completions request failed status=%s called_at=%s duration_ms=%s request_params=%s error=%s",
            status,
            called_at,
            _elapsed_ms(started_at),
            _compact_json(request_params),
            e,
        )
        raise HTTPException(
            status_code=status,
            detail={
                "message": str(e),
                "type": "server_error" if status >= 500 else "upstream_error",
                "code": None,
            },
        )
    finally:
        for p in image_paths:
            try:
                os.remove(p)
            except Exception:
                pass


@app.post("/v1/responses", dependencies=[Depends(rate_limiter), Depends(verify_api_key)])
async def responses_endpoint(req: ResponsesRequest):
    started_at = time.perf_counter()
    called_at = _now_hhmmss()
    request_params = {
        "model": req.model,
        "stream": req.stream,
        "reasoning_effort": req.reasoning.effort if req.reasoning else None,
    }

    try:
        model, alias_effort = choose_model(req.model)
    except ValueError as e:
        logger.warning(
            "responses request failed status=404 called_at=%s duration_ms=%s request_params=%s error=%s",
            called_at,
            _elapsed_ms(started_at),
            _compact_json(request_params),
            e,
        )
        raise HTTPException(
            status_code=404,
            detail={
                "message": str(e),
                "type": "invalid_request_error",
                "code": "model_not_found",
            },
        )

    # Normalize input -> messages
    try:
        messages = normalize_responses_input(req.input)
    except ValueError as e:
        logger.warning(
            "responses request failed status=400 called_at=%s duration_ms=%s request_params=%s error=%s",
            called_at,
            _elapsed_ms(started_at),
            _compact_json(request_params),
            e,
        )
        raise HTTPException(status_code=400, detail=str(e))

    overrides = {}
    if alias_effort:
        overrides["reasoning_effort"] = alias_effort
    if req.reasoning and req.reasoning.effort:
        overrides["reasoning_effort"] = req.reasoning.effort

    # Enforce local-only model provider when enabled
    if settings.local_only:
        try:
            assert_local_only_or_raise()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    prompt, image_urls = build_prompt_and_images(messages)

    resp_id = f"resp_{uuid.uuid4().hex}"
    msg_id = f"msg_{uuid.uuid4().hex}"
    created = int(time.time())
    response_model = req.model or model
    codex_overrides = overrides or None
    request_params.update(
        {
            "resolved_model": model,
            "message_count": len(messages),
            "image_count": len(image_urls),
            "codex_overrides": codex_overrides,
        }
    )
    request_preview = _build_request_preview(messages)
    logger.info(
        "responses request started called_at=%s params=%s request_preview=%s",
        called_at,
        _compact_json(request_params),
        request_preview,
    )

    image_paths: List[str] = []
    try:
        for u in image_urls:
            image_paths.append(save_image_to_temp(u))
    except ValueError as e:
        for p in image_paths:
            try:
                os.remove(p)
            except Exception:
                pass
        raise HTTPException(status_code=400, detail=str(e))

    try:
        if req.stream:
            async def event_gen() -> AsyncIterator[bytes]:
                response_chars = 0
                response_preview = ""
                stream_status = 200
                try:
                    created_evt = {
                        "id": resp_id,
                        "object": "response",
                        "created": created,
                        "model": response_model,
                        "status": "in_progress",
                    }
                    yield f"event: response.created\ndata: {json.dumps(created_evt)}\n\n".encode()

                    buf: list[str] = []
                    async for text in run_codex(prompt, codex_overrides, image_paths, model=model):
                        if text:
                            response_chars += len(text)
                            if len(response_preview) < _LOG_PREVIEW_LIMIT:
                                response_preview += text[: _LOG_PREVIEW_LIMIT - len(response_preview)]
                            buf.append(text)
                            delta_evt = {"id": resp_id, "delta": text}
                            yield f"event: response.output_text.delta\ndata: {json.dumps(delta_evt)}\n\n".encode()

                    final_text = "".join(buf)
                    done_evt = {"id": resp_id, "text": final_text}
                    yield f"event: response.output_text.done\ndata: {json.dumps(done_evt)}\n\n".encode()

                    final_obj = ResponsesObject(
                        id=resp_id,
                        created=created,
                        model=response_model,
                        status="completed",
                        output=[
                            ResponsesMessage(
                                id=msg_id,
                                content=[ResponsesOutputText(text=final_text)],
                            )
                        ],
                    ).model_dump()
                    yield f"event: response.completed\ndata: {json.dumps(final_obj)}\n\n".encode()
                except CodexError as e:
                    status = getattr(e, "status_code", None) or 500
                    stream_status = status
                    logger.warning(
                        "responses request failed status=%s called_at=%s duration_ms=%s request_params=%s response_chars=%s response_preview=%s error=%s",
                        status,
                        called_at,
                        _elapsed_ms(started_at),
                        _compact_json(request_params),
                        response_chars,
                        _truncate_text(response_preview),
                        e,
                    )
                    err_evt = {"id": resp_id, "error": {"message": str(e)}}
                    yield f"event: response.error\ndata: {json.dumps(err_evt)}\n\n".encode()
                finally:
                    logger.info(
                        "responses request completed status=%s stream=%s duration_ms=%s response_chars=%s response_preview=%s",
                        stream_status,
                        req.stream,
                        _elapsed_ms(started_at),
                        response_chars,
                        _truncate_text(response_preview),
                    )
                    yield b"data: [DONE]\n\n"

            headers = {
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            }
            return StreamingResponse(event_gen(), media_type="text/event-stream", headers=headers)
        else:
            final = await run_codex_last_message(prompt, codex_overrides, image_paths, model=model)
            logger.info(
                "responses request completed status=200 stream=%s duration_ms=%s response_chars=%s response_preview=%s",
                req.stream,
                _elapsed_ms(started_at),
                len(final),
                _truncate_text(final),
            )
            resp = ResponsesObject(
                id=resp_id,
                created=created,
                model=response_model,
                status="completed",
                output=[
                    ResponsesMessage(
                        id=msg_id,
                        content=[ResponsesOutputText(text=final)],
                    )
                ],
            )
            return resp
    except CodexError as e:
        status = getattr(e, "status_code", None) or 500
        logger.warning(
            "responses request failed status=%s called_at=%s duration_ms=%s request_params=%s error=%s",
            status,
            called_at,
            _elapsed_ms(started_at),
            _compact_json(request_params),
            e,
        )
        raise HTTPException(
            status_code=status,
            detail={
                "message": str(e),
                "type": "server_error" if status >= 500 else "upstream_error",
                "code": None,
            },
        )
    finally:
        for p in image_paths:
            try:
                os.remove(p)
            except Exception:
                pass
