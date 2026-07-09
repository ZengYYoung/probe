"""LLM abstraction layer: pydantic v2 models + LLMClient ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class Action(BaseModel):
    type: str
    command: str | None = None
    path: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    actions: list[Action] = Field(default_factory=list)
    raw: str = ""
    stop_reason: str = ""


class LLMClient(ABC):
    """Abstract LLM client: maps (messages, tools) -> LLMResponse."""

    @abstractmethod
    def complete(
        self, messages: list[Message], tools: list[ToolSpec]
    ) -> LLMResponse:
        ...
