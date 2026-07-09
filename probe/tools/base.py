"""Tool base class, ToolResult, and path-sanding fence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    ok: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


def safe_path(base: Path, target: str | Path) -> Path:
    """Resolve ``target`` relative to ``base`` and refuse escapes outside base."""
    root = Path(base).resolve()
    resolved = Path(base).joinpath(target).resolve()
    if not resolved.is_relative_to(root):
        raise PermissionError("path escapes repo root")
    return resolved


class Tool(ABC):
    """Abstract tool: ``name`` + ``run(params) -> ToolResult``."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def run(self, params: dict) -> ToolResult: ...
