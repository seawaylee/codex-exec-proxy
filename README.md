# codex-reverse-proxy（精简版）

这是一个 FastAPI 代理，把 OpenAI 兼容接口请求转发给本机 `codex` CLI 执行。

支持接口：
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `GET /healthz`

## 为什么看起来文件多？

核心代码其实很少，主要是这些：
- `app/main.py`：HTTP 接口入口
- `app/codex.py`：调用 Codex CLI
- `app/config.py`：环境变量与默认配置

其余大头是：
- `docs/`：文档
- `tests/`：测试
- `submodules/codex/`：上游 Codex CLI 子模块

## 快速启动

1. 初始化环境

```bash
git submodule update --init --recursive
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. 设置最小环境变量

```bash
export OPENAI_BASE_URL="https://your-openai-compatible-endpoint"
export OPENAI_API_KEY="your-api-key"
```

3. 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

或使用项目脚本（8045 端口）：

```bash
./run_proxy_8045_daemon.sh
```

## 常用配置（环境变量）

- `CODEX_PATH`：`codex` 可执行文件路径
- `CODEX_TIMEOUT`：Codex 执行超时秒数（默认 `120`）
- `CODEX_WORKDIR`：执行工作目录（默认 `/tmp`）
- `CODEX_SANDBOX_MODE`：沙箱模式（默认 `read-only`）
- `CODEX_LOCAL_ONLY`：是否仅允许本地（默认 `false`）

鉴权相关：
- `ENABLE_PROXY_AUTH=true` 开启代理鉴权
- `PROXY_API_KEY=<token>` 设置 Bearer Token

## 最小调用示例

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "hello"}],
    "stream": false
  }'
```

## 常见问题

- 超时：提高 `CODEX_TIMEOUT`（例如 `120` 或更高）
- 404/路由错误：确认请求路径是 `/v1/chat/completions` 或 `/v1/responses`
- 无法找到 `codex`：设置 `CODEX_PATH` 或把 `codex` 加到 `PATH`

## 许可证

MIT
