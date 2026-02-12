import asyncio

from app import main
from app.schemas import ChatCompletionRequest, ChatMessage


def test_chat_stream_emits_error_and_done_when_codex_fails(monkeypatch):
    monkeypatch.setattr(main, "choose_model", lambda _model: ("gpt-5.1", None))
    monkeypatch.setattr(main, "build_prompt_and_images", lambda _messages: ("prompt", []))

    async def _fake_run_codex(*_args, **_kwargs):
        yield "partial"
        raise main.CodexError("upstream failed", status_code=502)

    monkeypatch.setattr(main, "run_codex", _fake_run_codex)

    req = ChatCompletionRequest(
        model="gpt",
        messages=[ChatMessage(role="user", content="hello")],
        stream=True,
    )

    response = asyncio.run(main.chat_completions(req))
    assert response.status_code == 200

    async def _collect() -> list[str]:
        chunks: list[str] = []
        async for part in response.body_iterator:
            chunks.append(part.decode("utf-8", errors="ignore"))
        return chunks

    chunks = asyncio.run(_collect())
    merged = "".join(chunks)
    assert "partial" in merged
    assert "\"error\"" in merged
    assert "upstream failed" in merged
    assert "data: [DONE]" in merged
