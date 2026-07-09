"""Guardrail 纯函数（SPEC §3.8 危险动作拦截）。

确定性纯函数：构造 Action 即可断言，无需 LLM。
- shell: 对 config.guardrails.dangerous_patterns 逐条子串匹配（大小写不敏感）
- 文件类 (read/write/patch/list): 保守静态判定——绝对路径或含 `..` 越界即 block
- 未知 type: block
- 否则 allow
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from probe.config import Config
from probe.llm.base import Action


class Verdict(BaseModel):
    allow: bool
    reason: str = ""


_FILE_ACTIONS = {"read", "write", "patch", "list"}


def guardrail(action: Action, config: Config) -> Verdict:
    """对 action 做确定性危险动作判定。纯函数。"""
    if action.type == "shell":
        command = action.command or ""
        for pat in config.guardrails.dangerous_patterns:
            if pat.lower() in command.lower():
                return Verdict(allow=False, reason=f"dangerous pattern: {pat}")
        return Verdict(allow=True, reason="")

    if action.type in _FILE_ACTIONS:
        path = action.path or ""
        p = Path(path)
        if p.is_absolute() or ".." in p.parts:
            return Verdict(allow=False, reason="path escapes repo")
        return Verdict(allow=True, reason="")

    return Verdict(allow=False, reason="unknown action type")
