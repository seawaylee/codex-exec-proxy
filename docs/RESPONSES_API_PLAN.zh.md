# Responses API 兼容计划

目标：在现有包装器中提供与 OpenAI Responses API 兼容的 `/v1/responses`，优先保证主流 SDK 可直接接入。

## 1. 目标范围

优先支持：
- `POST /v1/responses` 非流请求
- `POST /v1/responses` 流式请求（SSE）
- 文本输入到文本输出的稳定闭环

暂不优先：
- 复杂工具调用编排
- 严格 token 计费统计
- 多模态高级结构化输出

## 2. 分阶段实施

### 阶段 A：最小非流

输入：
- `model`
- `input`（字符串或简化结构）
- 可选 `reasoning.effort`

输出：
- `response` 对象
- `status=completed`
- `output[0].content[0].text` 返回最终文本

内部路径：
- `input` 归一化为消息列表
- 复用 `chat/completions` 的 prompt 构建与执行逻辑

### 阶段 B：最小流式（SSE）

支持事件：
- `response.created`
- `response.output_text.delta`
- `response.output_text.done`
- `response.completed`
- 异常：`response.error`
- 结束：`data: [DONE]`

兼容要求：
- 采用 `event:` + `data:`
- `data` 使用 JSON

### 阶段 C：兼容扩展

- 扩展 `input` 变体（如 chat-like、`input_text` 数组、`input_image`）
- 更完整的 `usage` 字段策略
- 对齐更多 SDK 细节行为

## 3. 请求与响应映射

请求映射：
- `reasoning.effort` -> `x_codex.reasoning_effort`
- `stream=true` -> SSE 路径

响应映射：
- Codex 文本增量 -> `response.output_text.delta`
- 文本完成 -> `response.output_text.done`
- 最终对象 -> `response.completed`

## 4. 错误与边界

- 模型不可用：返回 404 风格错误对象
- 输入格式错误：返回 400
- 上游鉴权失败：返回 401
- 执行超时：返回 500/504（按现有错误映射策略）

## 5. 与现有能力对齐

- 鉴权：沿用 `PROXY_API_KEY`（可选开关）
- 限流：沿用 `RATE_LIMIT_PER_MINUTE`
- 沙箱与本地限制：沿用 `CODEX_SANDBOX_MODE` 与 `CODEX_LOCAL_ONLY`
- 并发：沿用 `CODEX_MAX_PARALLEL_REQUESTS`

## 6. 验证项

- 非流：SDK 可直接读到 `output[0].content[0].text`
- 流式：事件顺序正确，`[DONE]` 收尾
- 异常：`response.error` 可被客户端捕获
- 模型别名 + reasoning 后缀可正常工作

## 7. 后续优化建议

- 为复杂 `input` 增加更细粒度校验错误信息
- 在日志中补充请求 ID 与执行耗时
- 增加基于 fixture 的跨版本兼容回归测试
