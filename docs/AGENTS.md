# Agents 指南（Codex-Wrapper）

本服务使用 FastAPI 包装 Codex CLI，并提供最小 OpenAI 兼容 API。你可以通过替换 `base_url` 直接复用已有 OpenAI 客户端（Python/JS 等）。

重要：请始终在虚拟环境（venv）中安装 Python 依赖。

## 基础信息

- Base URL：`http://<host>:8000/v1`
- 鉴权：`Authorization: Bearer <PROXY_API_KEY>`（若服务端未配置可不带）
- 模型列表：服务启动时执行 `codex models list` 自动发现；请通过 `GET /v1/models` 获取当前可用模型名
  - 若 CLI 仅暴露部署信息（如 `{"id":"gpt-5","deployment":"codex"}`），包装器会扩展别名（如 `gpt-5-codex`）
  - 支持在模型名后追加 ` minimal` / ` low` / ` medium` / ` high` 指定推理强度
- 子模块：`submodules/codex`
- 支持接口：`/v1/chat/completions` 与最小版 `/v1/responses`（见 `docs/RESPONSES_API_PLAN.zh.md`）

## Codex 认证（OAuth 或 API Key）

- 方案 A：OAuth（ChatGPT 登录）
  - 以服务进程同一 OS 用户执行：`codex login`
  - 结果保存到 `$CODEX_HOME/auth.json`（默认 `~/.codex/auth.json`）
  - 无头环境可用 SSH 端口转发：`ssh -L 1455:localhost:1455 <user>@<host>`，然后在本地打开登录链接
  - 该方案不要求 `OPENAI_API_KEY`

- 方案 B：API Key
  - 执行：`codex login --api-key "<YOUR_OPENAI_API_KEY>"`
  - 需要具备 Responses API 权限的 OpenAI Key
  - 若开启 `CODEX_LOCAL_ONLY=1`，远程 `base_url` 会被拒绝；API Key 场景通常保持 `CODEX_LOCAL_ONLY=0`

说明：
- `CODEX_HOME` 应作为系统环境变量设置，不要写进 `.env`
- `PROXY_API_KEY` 只控制本包装器访问，独立于 Codex 登录

## 支持的 API

- `GET /v1/models`
  - 示例：`{ "data": [{ "id": "o4-mini" }, { "id": "gpt-4.1" }] }`

- `POST /v1/chat/completions`
  - 输入（子集）
    - `model`：可选，默认使用启动时发现的首个模型
    - `messages`：OpenAI 兼容结构（`system`/`user`/`assistant`），用户消息支持 `input_image`
    - `stream`：`true` 时采用 SSE
    - `temperature`、`max_tokens`：接受但当前不生效
  - 输出（非流）
    - `choices[0].message.content` 为最终文本
    - `usage` 目前固定为 0
  - 输出（流/SSE）
    - `Content-Type: text/event-stream`
    - 每段形如 `data: {chunk}`，结束为 `data: [DONE]`

- `POST /v1/responses`
  - 已支持最小兼容（非流/流），事件与字段见 `docs/RESPONSES_API_PLAN.zh.md`

## Python 示例（OpenAI SDK）

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="YOUR_PROXY_API_KEY",  # 若服务端开启了代理鉴权
)

resp = client.chat.completions.create(
    model="o4-mini",
    messages=[
        {"role": "system", "content": "你是一个有帮助的编码助手。"},
        {"role": "user", "content": "打个招呼并结束。"},
    ],
)
print(resp.choices[0].message.content)
```

## Responses API 示例

非流：

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="YOUR_PROXY_API_KEY")
resp = client.responses.create(model="o4-mini", input="说一句你好")
print(resp.output[0].content[0].text)
```

流式（SSE）：

```bash
curl -N \
  -H "Authorization: Bearer $PROXY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"o4-mini","input":"说一句你好","stream":true}' \
  http://localhost:8000/v1/responses
```

最小事件集合：
- `response.created`
- `response.output_text.delta`
- `response.output_text.done`
- `response.completed`
- 错误时：`response.error`，随后 `[DONE]`

## 执行与安全

- Codex 调用形态：`codex exec <PROMPT> -q [--model <...>]`
- `cwd` 被限制为 `CODEX_WORKDIR`
- 限流与 CORS 在 API 层处理（可配置）

## 环境变量（摘要）

- `PROXY_API_KEY`：本代理鉴权（可选）
- `CODEX_WORKDIR`：Codex 工作目录
- `CODEX_PATH`：`codex` 可执行路径
- `CODEX_SANDBOX_MODE`：`read-only` / `workspace-write` / `danger-full-access`
- `CODEX_REASONING_EFFORT`：`minimal` / `low` / `medium` / `high`
- `CODEX_LOCAL_ONLY`：`0/1`
- `CODEX_ALLOW_DANGER_FULL_ACCESS`：`0/1`
- `CODEX_TIMEOUT`：执行超时秒数（默认 300）
- `RATE_LIMIT_PER_MINUTE`：每分钟请求数上限
- `CODEX_ENV_FILE`：加载 `.env` 路径（启动前以系统环境变量设置）

未在请求中给出的 `x_codex` 字段会回落到服务端默认值。

## 运行模式建议（本地优先）

- 默认建议：`sandbox=read-only`
- 推荐编辑模式：`sandbox=workspace-write` 且 `network_access=false`
- 完全开放模式：`sandbox=danger-full-access`（仅在隔离可信环境启用）

CLI 示例：

```bash
codex exec "..." -q --config sandbox_mode='read-only'

codex exec "..." -q \
  --config sandbox_mode='workspace-write' \
  --config sandbox_workspace_write='{ network_access = false }'

codex exec "..." -q --config sandbox_mode='danger-full-access'
```

## 推理强度建议

- 默认：`medium`
- `high`：多文件重构、需求不清晰场景
- `medium`：常规实现与修复
- `low/minimal`：小改动、命令执行类任务

## Local-Only 约束

当 `CODEX_LOCAL_ONLY=1` 时：
- 仅允许本地 `base_url`（`localhost` / `127.0.0.1` / `[::1]` / unix）
- 服务会检查 `$CODEX_HOME/config.toml` 中 `model_providers` 与内置 OpenAI 的 `OPENAI_BASE_URL`
- 非本地地址会被拒绝（HTTP 400）

## `x_codex` 扩展字段

为保持 OpenAI 兼容，支持可选扩展字段：

```json
{
  "model": "codex-cli",
  "messages": [{ "role": "user", "content": "..." }],
  "x_codex": {
    "sandbox": "workspace-write",
    "reasoning_effort": "high",
    "network_access": false
  }
}
```

## 子模块工作流

- 位置：`submodules/codex`
- 首次拉取：`git submodule update --init --recursive`
- 更新到最新：

```bash
git submodule update --remote submodules/codex
```

## 已知限制

- 暂不支持 tool/function calling 与音频
- 暂无严格 token 计量
- CLI 输出格式可能变化，包装器做了 JSON + 文本双路径兼容

## 故障排查

- 401：检查 `PROXY_API_KEY` 与请求头
- 500（含超时）：简化提示词或提高 `CODEX_TIMEOUT`
- 429：触发限流，调整 `RATE_LIMIT_PER_MINUTE`
- 流式输出出现 CLI banner / MCP 报错：
  - 非流使用 `codex exec --json --output-last-message` 更干净
  - 流式会透传 CLI 输出，可在 Codex profile 中自行裁剪
  - 若是 MCP 未配置导致，检查并精简 `~/.codex/config.toml` 中 `mcp_servers`

## Codex TOML 配置

- 路径：`$CODEX_HOME/config.toml`（默认 `~/.codex/config.toml`）
- 示例：`docs/examples/codex-config.example.toml`

```bash
mkdir -p ~/.codex
cp docs/examples/codex-config.example.toml ~/.codex/config.toml
```

- API Key 模式需设置 `OPENAI_API_KEY`；OAuth 模式不需要
- 可通过 `tools.web_search = true` 启用 Web 搜索
  - 若启用 web_search，`reasoning_effort="minimal"` 可能被上游拒绝（400）
  - 建议改用 `low` / `medium` / `high`
- MCP 服务通过 `mcp_servers.<id>` 定义
- 若需隔离本 API 专用配置，可在 `.env` 设置 `CODEX_CONFIG_DIR`

## AGENTS 模板

- 可将 `docs/examples/AGENTS.example.md` 复制到全局或项目目录：

```bash
# 全局默认规则
cp docs/examples/AGENTS.example.md ~/.codex/AGENTS.md

# 项目规则
cp docs/examples/AGENTS.example.md AGENTS.md
```

## 包装器启动覆盖目录

- 默认目录：`workspace/codex_profile/`
- 模板文件：`codex_agents.sample.md` / `codex_config.sample.toml`
- 将模板复制为 `codex_agents.md` / `codex_config.toml` 后，启动时会覆盖 Codex 主目录对应文件
- 若只存在其中一个文件，则仅复制该文件
- 旧文件名（`agent.md`、`config.toml`）仍可用，但会触发迁移警告
