# 实施计划（FastAPI 包装 Codex CLI）

本项目目标是提供最小 OpenAI 兼容接口，将请求转发到本机 Codex CLI 执行，并确保安全边界可控。

## 1. 目标与完成标准

首发版本聚焦“可用且可控”的最小集合：

- 接口：`/v1/chat/completions`、`/v1/models`、`/v1/responses`
- 同时支持非流与流式（SSE）
- 通过环境变量统一控制沙箱、并发、超时、鉴权与本地限制

完成标准：

- OpenAI SDK 仅替换 `base_url` 后即可调用成功
- 非流与流式路径都可稳定返回
- 失败时返回结构化错误（尽量贴近 OpenAI 风格）
- 关键安全开关（`CODEX_LOCAL_ONLY`、`CODEX_ALLOW_DANGER_FULL_ACCESS`）可验证生效

## 2. 最小兼容规范

### 2.1 `POST /v1/chat/completions`

输入：
- `model`
- `messages`
- `stream`
- 可选扩展：`x_codex`（`sandbox`、`reasoning_effort`、`network_access`）

输出：
- 非流：`choices[0].message.content`
- 流式：SSE `data: {chunk}`，结束 `data: [DONE]`

说明：
- `temperature`、`max_tokens` 可接收但当前不强制生效

### 2.2 `GET /v1/models`

- 启动时运行 `codex models list` 自动发现
- 原样返回可用模型名，并支持 reasoning 后缀别名

### 2.3 `POST /v1/responses`

- 最小兼容：支持 `input`、`model`、`stream`
- 流式事件：`response.created`、`response.output_text.delta`、`response.output_text.done`、`response.completed`

## 3. 架构设计

- `app/main.py`：HTTP 入口、参数校验、SSE 组织
- `app/codex.py`：进程并发控制、执行 `codex exec`、输出规整
- `app/model_registry.py`：模型列表发现与别名处理
- `app/deps.py`：鉴权与限流依赖
- `app/security.py`：本地提供方限制校验

数据流：
1. API 收到请求
2. 选择模型并归一化输入
3. 拼接 prompt / 图片输入
4. 调用 Codex CLI
5. 按非流或流式返回

## 4. 安全与运行边界

- 默认沙箱：`read-only`
- 可编辑模式：`workspace-write`（建议 `network_access=false`）
- 危险模式：`danger-full-access` 需双重开关
  - 服务端：`CODEX_ALLOW_DANGER_FULL_ACCESS=1`
  - 请求端：`x_codex.sandbox="danger-full-access"`

`CODEX_LOCAL_ONLY=1` 时：
- 非本地 `base_url` 直接拒绝（400）
- 检查 `$CODEX_HOME/config.toml` 与内置 OpenAI 提供方配置

## 5. 配置策略

关键变量：
- `PROXY_API_KEY`
- `RATE_LIMIT_PER_MINUTE`
- `CODEX_WORKDIR`
- `CODEX_SANDBOX_MODE`
- `CODEX_REASONING_EFFORT`
- `CODEX_LOCAL_ONLY`
- `CODEX_ALLOW_DANGER_FULL_ACCESS`
- `CODEX_TIMEOUT`
- `CODEX_MAX_PARALLEL_REQUESTS`
- `CODEX_QUEUE_TIMEOUT_SECONDS`

## 6. 错误处理策略

- Codex 进程非 0 退出：转为统一错误 JSON
- 上游 401/限流：尽量映射为对应 HTTP 状态
- 执行超时：返回超时错误并中断子进程
- 客户端断开连接：尽快停止后台执行

## 7. 测试策略

必须覆盖：
- 非流式成功路径
- 流式成功路径
- 模型不可用错误路径
- 鉴权开关路径（有/无 `PROXY_API_KEY`）
- Local-only 拒绝路径
- 并发上限与排队超时路径

建议：
- 对 Codex CLI 输出使用 mock，避免测试依赖真实外部服务

## 8. 迭代路线

阶段 A（已具备）：
- 核心接口打通
- 模型自动发现
- 基础限流与鉴权

阶段 B：
- 完善 `responses` 输入兼容（更多 `input` 结构）
- 增强错误映射与日志可观测性

阶段 C：
- 结构化输出能力预研（在 CLI 能力允许前提下）
- 更细粒度的使用统计与审计

## 9. 运维建议

- 使用非 root 用户运行服务
- 将 `CODEX_WORKDIR` 放在可控目录并做好权限隔离
- 定期清理日志与临时文件
- 对外暴露时务必配合 TLS、网关 ACL 与限流
