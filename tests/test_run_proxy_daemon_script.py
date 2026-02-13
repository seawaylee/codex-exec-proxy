import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "run_proxy_8045_daemon.sh"


def test_run_proxy_daemon_test_mode_exits_quickly(tmp_path: Path) -> None:
    stdout_path = tmp_path / "stdout.log"
    stderr_path = tmp_path / "stderr.log"

    env = os.environ.copy()
    env.update(
        {
            "OPENAI_BASE_URL": "http://127.0.0.1:1",
            "OPENAI_API_KEY": "dummy-key",
            "LOG_STDOUT_PATH": str(stdout_path),
            "LOG_STDERR_PATH": str(stderr_path),
            "LOG_TRIM_INTERVAL_SECONDS": "1",
            "CODEX_DAEMON_TEST_MODE": "true",
        }
    )

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        check=True,
        timeout=3,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
