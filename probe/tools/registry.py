"""ToolRegistry: route Action by type to the matching Tool."""

from __future__ import annotations

from pathlib import Path

from probe.llm.base import Action
from probe.tools.base import Tool, ToolResult
from probe.tools.fs import ListFiles, PatchFile, ReadFile, WriteFile
from probe.tools.shell import RunShell


class ToolRegistry:
    """Holds a set of tools and dispatches Actions by ``action.type``."""

    _ROUTE: dict[str, str] = {
        "shell": "shell",
        "read": "read",
        "write": "write",
        "patch": "patch",
        "list": "list",
    }

    def __init__(self, tools: list[Tool]) -> None:
        self._by_name: dict[str, Tool] = {t.name: t for t in tools}

    @classmethod
    def for_repo(cls, repo_root: Path) -> "ToolRegistry":
        """Wire up the standard FS + Shell toolset for a repo."""
        return cls(
            [
                ReadFile(repo_root),
                WriteFile(repo_root),
                PatchFile(repo_root),
                ListFiles(repo_root),
                RunShell(repo_root),
            ]
        )

    def dispatch(self, action: Action) -> ToolResult:
        tool_name = self._ROUTE.get(action.type)
        if tool_name is None:
            return ToolResult(
                ok=False, stderr=f"unknown action type: {action.type}"
            )
        tool = self._by_name.get(tool_name)
        if tool is None:
            return ToolResult(
                ok=False, stderr=f"unknown action type: {action.type}"
            )

        if action.type == "shell":
            params: dict = {"command": action.command, "cwd": action.params.get("cwd")}
        elif action.type in ("read", "list"):
            params = {"path": action.path}
        elif action.type == "write":
            params = {
                "path": action.path,
                "content": action.params.get("content", ""),
            }
        elif action.type == "patch":
            params = {
                "path": action.path,
                "old": action.params.get("old"),
                "new": action.params.get("new"),
            }
        else:  # pragma: no cover - guarded above
            return ToolResult(
                ok=False, stderr=f"unknown action type: {action.type}"
            )

        return tool.run(params)
