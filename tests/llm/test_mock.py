from probe.llm.base import LLMClient, Action, LLMResponse
from probe.llm.mock import MockLLM


def test_mock_returns_scripted_then_stops():
    r1 = LLMResponse(actions=[Action(type="shell", command="ls")], raw="1", stop_reason="ok")
    r2 = LLMResponse(actions=[], raw="2", stop_reason="end_turn")
    client = MockLLM(script=[r1, r2])
    assert client.complete([], []).actions[0].command == "ls"
    assert client.complete([], []).actions == []   # 第二次
    assert client.complete([], []).actions == []   # 第三次停在末帧
