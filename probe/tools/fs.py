"""Filesystem tools: read/write/patch/list, all fenced by safe_path."""

from __future__ import annotations

from pathlib import Path

from probe.tools.base import Tool, ToolResult, safe_path


class ReadFile(Tool):
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)

    @property
    def name(self) -> str:
        return "read"

    def run(self, params: dict) -> ToolResult:
        path = safe_path(self.repo_root, params["path"])
        if not path.exists():
            return ToolResult(ok=False, stderr=f"not found: {params['path']}")
        return ToolResult(ok=True, stdout=path.read_text(encoding="utf-8"))


class WriteFile(Tool):
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)

    @property
    def name(self) -> str:
        return "write"

    def run(self, params: dict) -> ToolResult:
        path = safe_path(self.repo_root, params["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(params["content"], encoding="utf-8")
        return ToolResult(ok=True)


class PatchFile(Tool):
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)

    @property
    def name(self) -> str:
        return "patch"

    def run(self, params: dict) -> ToolResult:
        path = safe_path(self.repo_root, params["path"])
        content = path.read_text(encoding="utf-8")
        old = params["old"]
        if old not in content:
            return ToolResult(ok=False, stderr="old not found")
        path.write_text(content.replace(old, params["new"]), encoding="utf-8")
        return ToolResult(ok=True)


class ListFiles(Tool):
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)

    @property
    def name(self) -> str:
        return "list"

    def run(self, params: dict) -> ToolResult:
        path = safe_path(self.repo_root, params["path"])
        files = sorted(
            str(p.relative_to(self.repo_root))
            for p in path.rglob("*.java")
            if p.is_file()
        )
        return ToolResult(ok=True, stdout="\n".join(files))
