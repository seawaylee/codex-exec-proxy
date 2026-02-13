import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "trim_log.sh"


def _run_trim(log_file: Path, max_bytes: int, keep_bytes: int) -> None:
    subprocess.run(
        ["bash", str(SCRIPT), str(log_file), str(max_bytes), str(keep_bytes)],
        cwd=ROOT,
        check=True,
    )


def test_trim_log_keeps_file_when_under_limit(tmp_path: Path) -> None:
    log_file = tmp_path / "stderr.log"
    log_file.write_text("hello\n", encoding="utf-8")

    _run_trim(log_file, max_bytes=50, keep_bytes=20)

    assert log_file.read_text(encoding="utf-8") == "hello\n"


def test_trim_log_keeps_tail_when_over_limit(tmp_path: Path) -> None:
    log_file = tmp_path / "stderr.log"
    content = "".join(str(i % 10) for i in range(200))
    log_file.write_text(content, encoding="utf-8")

    _run_trim(log_file, max_bytes=50, keep_bytes=20)

    trimmed = log_file.read_text(encoding="utf-8")
    assert len(trimmed) == 20
    assert trimmed == content[-20:]
