import httpx
import pytest

from probe.llm.openai_compat import OpenAICompatibleClient


def test_complete_parses_tool_call(monkeypatch):
    def fake_post(self, req, **kw):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "1",
                                    "function": {
                                        "name": "RunShell",
                                        "arguments": '{"command":"ls"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(OpenAICompatibleClient, "_post", fake_post)
    c = OpenAICompatibleClient("http://x", "sk-x", "glm-5.2")
    resp = c.complete([], [])
    assert resp.actions[0].type == "shell"
    assert resp.actions[0].command == "ls"


def test_auth_error_raises(monkeypatch):
    monkeypatch.setattr(
        OpenAICompatibleClient,
        "_post",
        lambda *a, **k: httpx.Response(401, json={"error": "bad key"}),
    )
    with pytest.raises(Exception):
        OpenAICompatibleClient("http://x", "bad", "m").complete([], [])


def test_content_fallback_to_action(monkeypatch):
    # 无 tool_calls 时, content 当作 raw 返回, actions=[]
    monkeypatch.setattr(
        OpenAICompatibleClient,
        "_post",
        lambda *a, **k: httpx.Response(
            200, json={"choices": [{"message": {"content": "done"}}]}
        ),
    )
    c = OpenAICompatibleClient("http://x", "sk", "m")
    r = c.complete([], [])
    assert r.actions == [] and r.raw == "done"
