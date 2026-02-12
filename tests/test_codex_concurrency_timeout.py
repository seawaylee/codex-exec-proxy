import asyncio
from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import codex


def test_concurrency_limiter_times_out_when_all_slots_busy():
    async def _run():
        limiter = codex._CodexConcurrencyLimiter(max_parallel=1, queue_timeout_seconds=0.01)
        async with limiter.slot():
            with pytest.raises(codex.CodexError) as exc_info:
                async with limiter.slot():
                    pass
            assert exc_info.value.status_code == 503

    asyncio.run(_run())


def test_run_codex_last_message_kills_process_on_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(codex.settings, "codex_workdir", str(tmp_path))
    monkeypatch.setattr(codex.settings, "timeout_seconds", 1)
    monkeypatch.setattr(codex, "_build_cmd_and_env", lambda *_, **__: ["codex", "exec"])
    monkeypatch.setattr(codex, "_build_codex_env", lambda: {})
    monkeypatch.setattr(codex, "_WORKDIR_PATH", None)
    monkeypatch.setattr(codex, "_WORKDIR_NEEDS_SKIP_GIT_CHECK", False)

    killed = {"called": False}

    class FakeProcess:
        def __init__(self) -> None:
            self.returncode = None

        async def communicate(self):
            await asyncio.sleep(60)

        async def wait(self):
            self.returncode = -9
            return -9

        def kill(self):
            killed["called"] = True
            self.returncode = -9

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return FakeProcess()

    monkeypatch.setattr(codex.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    with pytest.raises(codex.CodexError) as exc_info:
        asyncio.run(codex.run_codex_last_message("prompt"))

    assert exc_info.value.status_code == 504
    assert killed["called"] is True
