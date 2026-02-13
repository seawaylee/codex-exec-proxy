"""用于历史对比的手工验证脚本。

包装器中的过滤逻辑已移除；下面样例现在会原样透传。
调试流式输出时可运行此脚本查看 Codex CLI 每行是如何传递的。
"""

samples = [
    "2025/09/15 06:53:40",
    "User instructions:",
    "You are Obsidian Copilot, a helpful assistant...",
    "User: 你叫什么名字？",
    "Assistant:",
    "Assistant: 我是 Obsidian Copilot，很高兴为你服务。",
    "tokens used: 123",
]

for s in samples:
    print(s, "=>", repr(s))
