# 仓库协作指南

## 语言
- 在本仓库中，助手回复与新增文档默认使用中文。

## 项目结构与模块划分
- `app/`：FastAPI 服务主体。
  - `main.py` 暴露 `/v1/chat/completions` 与 `/v1/responses`。
  - `codex.py` 负责调用 Codex CLI。
  - 其余模块处理配置、数据结构与安全策略。
- `docs/`：产品与运维文档。
- `submodules/codex`：上游 Codex CLI 子模块；克隆后运行 `git submodule update --init --recursive`。
- `workspace/`：手工实验区（如 `test_filter.py`）；进入主分支前应迁移为正式测试。

## 构建、测试与开发命令
- `python3 -m venv .venv && source .venv/bin/activate`：创建并激活虚拟环境。
- `pip install -r requirements.txt`：安装 FastAPI、uvicorn 及依赖。
- `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`：本地热更新启动。
- `pytest`：运行测试；新增测试优先放在 `tests/`。

## 代码风格与命名
- 遵循 PEP 8，4 空格缩进。
- 函数使用 `snake_case`，Pydantic 模型使用 `PascalCase`。
- 保持异步边界清晰：FastAPI 异步端点调用 `app.codex` 中的辅助函数。
- 涉及安全行为（如沙箱约束）时，补充类型标注与简短注释。
- 提交前使用 `black` 或等效格式化工具；避免在功能变更中混入纯格式化改动。

## 测试要求
- 为 `app.main` 覆盖流式与非流式路径。
- 模拟 Codex CLI 响应，避免测试依赖外部网络。
- 测试文件命名 `test_<feature>.py`，fixture 命名 `<scope>_<name>`。
- 修改请求解析、提示词拼装、沙箱校验时必须补回归测试。

## 提交与 PR 规范
- 提交信息简洁、祈使句，推荐前缀：`feat:`、`docs:`、`chore:`。
- PR 需说明场景、验证方式（`pytest` / 本地 uvicorn 验证）和配置影响（如 `CODEX_ALLOW_DANGER_FULL_ACCESS`）。

## 安全与配置建议
- `.env` 中的敏感信息不要入库；新增变量需更新 `docs/ENV.md`。
- 若改动涉及沙箱开关（`CODEX_ALLOW_DANGER_FULL_ACCESS`、`CODEX_LOCAL_ONLY`），需在 PR 中明确默认行为与风险。
- 扩展 Codex CLI 集成时，确认与 `~/.codex/config.toml` 兼容，并补充迁移说明。
