"""JSON-backed memory store for Probe decisions and conventions.

纯 JSON 落盘到 ``repo_root/.probe/memory.json``，不接任何框架 memory。
文件不存在或损坏时降级为空状态，绝不抛异常阻断主循环。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Memory:
    """决策与约定的持久化存储。

    结构：``{"decisions": [dict, ...], "conventions": {str: str}}``。
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        self.path = self.repo_root / ".probe" / "memory.json"

    def _load(self) -> dict[str, Any]:
        """读取 JSON；不存在或损坏→空骨架，不抛。"""
        if not self.path.exists():
            return {"decisions": [], "conventions": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"decisions": [], "conventions": {}}
        if not isinstance(data, dict):
            return {"decisions": [], "conventions": {}}
        decisions = data.get("decisions")
        conventions = data.get("conventions")
        if not isinstance(decisions, list):
            data["decisions"] = []
        if not isinstance(conventions, dict):
            data["conventions"] = {}
        return data

    def _save(self, data: dict[str, Any]) -> None:
        """建父目录并写 JSON（indent=2）。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def append_decision(self, decision: dict[str, Any]) -> None:
        data = self._load()
        data["decisions"].append(decision)
        self._save(data)

    def recent(self, n: int) -> list[dict[str, Any]]:
        data = self._load()
        decisions = data["decisions"]
        if n <= 0:
            return []
        return list(decisions[-n:])

    def get_conventions(self) -> dict[str, Any]:
        return self._load()["conventions"]

    def set_convention(self, key: str, value: str) -> None:
        data = self._load()
        data["conventions"][key] = value
        self._save(data)
