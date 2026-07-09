"""OpenAI-compatible chat completions client.

Consumes :mod:`probe.llm.base` (``LLMClient`` ABC, ``Message``, ``ToolSpec``,
``Action``, ``LLMResponse``).  All real network I/O is isolated in
:meth:`OpenAICompatibleClient._post` so tests can monkeypatch it without
touching the network.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from probe.llm.base import (
    Action,
    LLMClient,
    LLMResponse,
    Message,
    ToolSpec,
)


class LLMError(RuntimeError):
    """Generic LLM transport/server error (timeout, 5xx after retries)."""


class LLMAuthError(LLMError):
    """Authentication/authorization failure (401/403)."""


# 工具名 -> Action.type 的固定映射表。
_TOOL_TO_ACTION: dict[str, str] = {
    "RunShell": "shell",
    "ReadFile": "read",
    "WriteFile": "write",
    "PatchFile": "patch",
    "ListFiles": "list",
}

# 5xx / 超时重试次数（不含首次调用）。
_MAX_RETRIES = 2
_RETRY_STATUS = {500, 502, 503, 504}
_REQUEST_TIMEOUT = 60.0


class OpenAICompatibleClient(LLMClient):
    """Minimal OpenAI-compatible ``/chat/completions`` client.

    Parameters
    ----------
    base_url:
        API 根地址，如 ``https://open.bigmodel.cn/api/llm``；末尾斜杠会被裁掉。
    api_key:
        ``Authorization: Bearer <api_key>`` 使用的明文 key（由 CredentialStore 提供）。
    model:
        默认模型名，写入请求体的 ``model`` 字段。
    """

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    # ------------------------------------------------------------------
    # 网络隔离点 —— 测试 monkeypatch 此方法即可避免触网
    # ------------------------------------------------------------------
    def _post(self, request_payload: dict[str, Any], **kw: Any) -> httpx.Response:
        """POST ``{base_url}/chat/completions`` 并返回 ``httpx.Response``."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        timeout = kw.get("timeout", _REQUEST_TIMEOUT)
        with httpx.Client(timeout=timeout) as client:
            return client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=request_payload,
            )

    # ------------------------------------------------------------------
    # LLMClient API
    # ------------------------------------------------------------------
    def complete(
        self, messages: list[Message], tools: list[ToolSpec]
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": m.role,
                    **({"content": m.content} if m.content is not None else {}),
                    **({"tool_calls": m.tool_calls} if m.tool_calls else {}),
                }
                for m in messages
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ],
            "tool_choice": "auto",
        }
        if not tools:
            # 无工具时不发送 tools/tool_choice，避免部分后端校验报错。
            payload.pop("tools")
            payload.pop("tool_choice")

        response = self._call_with_retry(payload)
        data = response.json()

        choices = data.get("choices") or []
        if not choices:
            return LLMResponse(actions=[], raw="", stop_reason="")
        msg = choices[0].get("message") or {}
        stop_reason = choices[0].get("finish_reason") or ""

        actions: list[Action] = []
        raw = ""
        tool_calls = msg.get("tool_calls") or []
        if tool_calls:
            for call in tool_calls:
                fn = call.get("function") or {}
                name = fn.get("name", "")
                action_type = _TOOL_TO_ACTION.get(name)
                if action_type is None:
                    # 未知工具名：跳过，不强行构造 Action。
                    continue
                args_raw = fn.get("arguments", "{}")
                try:
                    args = (
                        json.loads(args_raw)
                        if isinstance(args_raw, str)
                        else (args_raw or {})
                    )
                except (json.JSONDecodeError, TypeError):
                    args = {}
                actions.append(_build_action(action_type, args))
            # 有 tool_calls 时 content 通常为 None；保留原样作为 raw。
            content = msg.get("content")
            raw = content if isinstance(content, str) else ""
        else:
            content = msg.get("content")
            raw = content if isinstance(content, str) else (content or "")

        return LLMResponse(actions=actions, raw=raw, stop_reason=stop_reason)

    # ------------------------------------------------------------------
    # 内部：重试 + 错误映射
    # ------------------------------------------------------------------
    def _call_with_retry(self, payload: dict[str, Any]) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = self._post(payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                continue
            if resp.status_code in (401, 403):
                raise LLMAuthError(
                    f"LLM 鉴权失败 ({resp.status_code}): {resp.text}"
                )
            if resp.status_code in _RETRY_STATUS:
                last_exc = LLMError(
                    f"LLM 服务端 {resp.status_code}: {resp.text}"
                )
                continue
            if resp.status_code >= 400:
                raise LLMError(
                    f"LLM 请求失败 ({resp.status_code}): {resp.text}"
                )
            return resp
        raise LLMError(f"LLM 调用重试 {_MAX_RETRIES} 次仍失败: {last_exc}")


def _build_action(action_type: str, args: dict[str, Any]) -> Action:
    """根据 action_type 从参数字典构造 :class:`Action`."""
    if action_type == "shell":
        return Action(type="shell", command=args.get("command"))
    if action_type in ("read", "write", "patch"):
        return Action(
            type=action_type,
            path=args.get("path"),
            params=args,
        )
    if action_type == "list":
        return Action(type="list", path=args.get("path"))
    # 兜底：原样塞进 params。
    return Action(type=action_type, params=args)
