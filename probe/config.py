"""Config 加载器（SPEC §3.11）。

纯数据载入与校验：从 `probe.yaml`（仓内）+ 环境覆盖构造 `Config`。
未知字段告警不报错；缺字段→用文档化默认值并告警。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


def _warn(msg: str) -> None:
    """告警输出到 stderr，不阻断主循环。"""
    print(f"[probe.config] WARN: {msg}", file=sys.stderr)


class Budgets(BaseModel):
    max_iterations: int = 10
    max_shell_seconds: int = 600
    max_tokens: int = 50000


class Guardrails(BaseModel):
    # SPEC §3.8 危险表全量默认（关键字串列表，子串匹配即视为危险）
    dangerous_patterns: list[str] = Field(default_factory=lambda: [
        "rm -rf",
        "git push --force",
        "git push --force-with-lease",
        "mvn deploy",
        "rm -rf .git",
        ".git/",
        "../../",
        "curl ",
        "wget ",
        "nc ",
        "DROP ",
        "TRUNCATE ",
        "DELETE FROM",
        "sudo ",
    ])
    allowed_paths: list[str] = Field(default_factory=list)


class Validators(BaseModel):
    compile: bool = True
    test: bool = True
    lint: bool = True


class LLM(BaseModel):
    model: str = "deepseek-v4-flash"
    temperature: float = 0.2


class Config(BaseModel):
    budgets: Budgets = Field(default_factory=Budgets)
    guardrails: Guardrails = Field(default_factory=Guardrails)
    validators: Validators = Field(default_factory=Validators)
    llm: LLM = Field(default_factory=LLM)
    no_progress_rounds: int = 3

    @classmethod
    def load(cls, path: Path | None, env: dict[str, str]) -> "Config":
        """从 yaml 文件 + 环境覆盖构造 Config。

        - path=None 或文件缺失→全默认并告警（T18/T23 的无配置入口）。
        - env 中 `PROBE_` 前缀键覆盖对应字段。
        - 缺字段→默认+告警；未知字段→告警不报错。
        """
        data: dict[str, Any] = {}
        if path is None:
            _warn("path=None，使用全默认配置")
        elif not Path(path).exists():
            _warn(f"配置文件 {path} 不存在，使用全默认配置")
        else:
            try:
                raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
            except yaml.YAMLError as e:
                _warn(f"解析 {path} 失败: {e}，使用全默认配置")
                raw = None
            if raw is None:
                _warn(f"{path} 为空，使用全默认配置")
            elif not isinstance(raw, dict):
                _warn(f"{path} 顶层不是 dict，使用全默认配置")
            else:
                data = raw

        config = cls.model_validate(data) if data else cls()

        # env 覆盖（PROBE_ 前缀）
        config._apply_env_overrides(env)
        return config

    def _apply_env_overrides(self, env: dict[str, str]) -> None:
        """应用 PROBE_ 前缀环境变量覆盖。"""
        mapping = {
            "PROBE_MAX_ITERATIONS": ("budgets", "max_iterations", int),
            "PROBE_MAX_SHELL_SECONDS": ("budgets", "max_shell_seconds", int),
            "PROBE_MAX_TOKENS": ("budgets", "max_tokens", int),
            "PROBE_NO_PROGRESS_ROUNDS": ("no_progress_rounds", None, int),
            "PROBE_LLM_MODEL": ("llm", "model", str),
            "PROBE_LLM_TEMPERATURE": ("llm", "temperature", float),
        }
        for key, (section, field, cast) in mapping.items():
            if key in env:
                try:
                    val = cast(env[key])
                except (ValueError, TypeError):
                    _warn(f"环境变量 {key}={env[key]!r} 无法转为 {cast.__name__}，忽略")
                    continue
                if field is None:
                    setattr(self, section, val)
                else:
                    setattr(getattr(self, section), field, val)
