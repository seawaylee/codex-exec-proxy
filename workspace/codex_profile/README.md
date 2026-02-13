# Codex 配置覆盖目录

- `codex_agents.sample.md` 和 `codex_config.sample.toml` 是模板文件。
- 实际生效内容请放在本目录下：`codex_agents.md`、`codex_config.toml`。
- 仅当这些文件存在时，服务启动才会覆盖 Codex 主目录中的 `AGENTS.md` 与 `config.toml`。
- 如果只放了其中一个文件，只会复制存在的那个。
- 为兼容历史命名，仍会读取旧文件名（`agent.md` / `config.toml`），但启动时会给出迁移警告。

为了避免提交个人配置，`.gitignore` 已忽略 `codex_agents.md` / `codex_config.toml`（以及旧名称）。
