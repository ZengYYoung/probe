"""MockLLM: deterministic scripted responses for offline unit tests."""

from __future__ import annotations

from .base import LLMClient, LLMResponse, Message, ToolSpec


class MockLLM(LLMClient):
    """Returns scripted LLMResponse entries in order, clamping at the last frame.

    Pure deterministic, no IO. Useful for unit-testing the harness main loop
    and mechanisms without a real LLM or network.
    """

    def __init__(self, script: list[LLMResponse], index: int = 0) -> None:
        if not script:
            raise ValueError("MockLLM requires a non-empty script")
        self.script: list[LLMResponse] = list(script)
        self._i: int = index

    def complete(
        self, messages: list[Message], tools: list[ToolSpec]
    ) -> LLMResponse:
        pos = min(self._i, len(self.script) - 1)
        response = self.script[pos]
        self._i += 1
        return response
