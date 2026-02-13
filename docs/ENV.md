# 环境变量配置（`.env` 与系统环境）

本项目通过环境变量加载配置，支持 `.env` 文件（`pydantic-settings`）与操作系统环境变量。本文件是服务端配置的权威说明。

## 文件与优先级

- 默认配置文件：仓库根目录 `.env`。
- 覆盖配置文件：在启动前设置系统环境变量 `CODEX_ENV_FILE`（例如 `.env.local`）。
- 优先级：系统环境变量高于 `.env` 文件中的同名变量。

## 核心变量

- `PROXY_API_KEY`：本代理的 Bearer 鉴权令牌（可选，不设置则可无鉴权访问）。
- `RATE_LIMIT_PER_MINUTE`：每个客户端每分钟允许请求数，`0` 表示关闭限流。
- `HOST_UID` / `HOST_GID`：Docker 镜像内 `codex` 用户 UID/GID（默认 `1000`）。当挂载 `$HOME/.codex` 时建议与宿主机一致。
- `CODEX_PATH`：`codex` 可执行文件路径（默认 `codex`）。
- `CODEX_WORKDIR`：Codex 执行工作目录（服务会强制 `cwd` 为该路径）。
  - Codex 会在该目录树内查找 `AGENTS.md`，可在此放置项目级规则。
- `CODEX_CONFIG_DIR`：包装器专用 Codex 配置目录（可选）。
  - 设置后，服务会把该目录作为子进程的 `CODEX_HOME` 并确保目录存在。
  - Docker 环境通常留空以复用挂载的 `${HOME}/.codex`。
- `CODEX_WRAPPER_PROFILE_DIR`：覆盖模板目录（可选），默认 `workspace/codex_profile/`。
  - 若目录内存在 `codex_agents.md` / `codex_config.toml`，启动时会复制到 Codex 主目录。
  - 兼容旧文件名 `agent.md` / `config.toml`，但会打印迁移警告。
- `CODEX_SANDBOX_MODE`：`read-only` | `workspace-write` | `danger-full-access`。
- `CODEX_REASONING_EFFORT`：`minimal` | `low` | `medium` | `high`。
- `CODEX_HIDE_REASONING`：`0/1`，为 `1` 时要求 Codex CLI 隐藏思考输出。
- `CODEX_LOCAL_ONLY`：`0/1`，为 `1` 时拒绝非本地模型提供方 `base_url`。
- `CODEX_ALLOW_DANGER_FULL_ACCESS`：`0/1`，为 `1` 时允许请求 `x_codex.sandbox=danger-full-access`。
- `CODEX_TIMEOUT`：Codex 执行超时（秒，默认 `300`）。
- `CODEX_MAX_PARALLEL_REQUESTS`：Codex 子进程并发上限（默认 `10`，小于 `1` 会被视为 `1`）。
- `CODEX_QUEUE_TIMEOUT_SECONDS`：请求等待可用执行槽位的超时（秒，默认 `30`）。
- `CODEX_ENV_FILE`：要加载的 `.env` 文件名或路径（作为系统环境变量设置）。

## 模型选择

- 服务启动时通过 `codex models list` 自动发现可用模型。
- `GET /v1/models` 返回 CLI 报告的模型名，调用方必须使用这些名字。
- 可在模型名后追加 ` minimal` / ` low` / ` medium` / ` high` 覆盖推理强度。
- 旧变量 `CODEX_MODEL` 已废弃，设置后仅记录警告并被忽略。

## Codex CLI 认证与提供方

- Codex 认证由 CLI 本身处理：`codex login`。
- 凭据保存在 `$CODEX_HOME/auth.json`（默认 `~/.codex/auth.json`）。
- API Key 模式下，Codex CLI 会读取 `OPENAI_API_KEY`（该变量由 Codex 消费，不是本代理消费）。

## Local-Only 约束

当 `CODEX_LOCAL_ONLY=1` 时：
- 服务会检查 `$CODEX_HOME/config.toml` 里的 `model_providers`，以及内置 OpenAI 提供方的 `OPENAI_BASE_URL`。
- 只允许本地地址（`localhost` / `127.0.0.1` / `[::1]` / Unix Socket），其余地址会返回 HTTP 400。

## 危险模式

要允许完全文件/网络访问，必须同时满足：
1. 服务端设置 `CODEX_ALLOW_DANGER_FULL_ACCESS=1`。
2. 请求中显式传入 `x_codex.sandbox: "danger-full-access"`。

若同时启用 `CODEX_LOCAL_ONLY=1`，提供方 `base_url` 仍需是本地地址。

## `.env.example`

可参考仓库根目录 `.env.example` 作为起始模板。
