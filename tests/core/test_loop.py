import pytest

from probe.core.loop import AgentLoop, Task, RunResult, Step
from probe.core.types import Status
from probe.llm.mock import MockLLM
from probe.llm.base import LLMResponse, Action
from probe.config import Config
from probe.validators.base import FailureReport
from probe.tools.registry import ToolRegistry


def _ok_report():
    return FailureReport(
        per_validator_status={"compile": "PASS", "test": "PASS", "lint": "PASS"},
        failures=[],
        signature="ok",
        summary={},
    )


def _fail_report(sig="fail"):
    return FailureReport(
        per_validator_status={"compile": "FAIL"},
        failures=[],
        signature=sig,
        summary={},
    )


def test_loop_succeeds_when_validators_pass(tmp_repo):
    # MockLLM: write a file then end
    actions = [
        LLMResponse(
            actions=[Action(type="write", path="src/A.java", params={"content": "class A{}"})],
            raw="",
            stop_reason="ok",
        ),
        LLMResponse(actions=[], raw="done", stop_reason="end_turn"),
    ]
    calls = {"n": 0}

    class FakePipe:
        def run(self, repo, changed_files=None):
            calls["n"] += 1
            return _ok_report()

    loop = AgentLoop(
        llm=MockLLM(actions),
        registry=ToolRegistry.for_repo(tmp_repo),
        pipeline=FakePipe(),
        config=Config.load(None, {}),
        repo=tmp_repo,
    )
    res = loop.run(Task(goal="fix", target_repo=str(tmp_repo), budget={}))
    assert res.status == Status.SUCCESS
    assert len(res.steps) >= 1


def test_loop_blocked_no_progress(tmp_repo):
    # same FAIL signature for K=3 consecutive rounds -> BLOCKED_NO_PROGRESS
    actions = [
        LLMResponse(actions=[Action(type="shell", command="echo x")], raw="", stop_reason="ok")
        for _ in range(5)
    ]

    class FakePipe:
        def run(self, repo, changed_files=None):
            return _fail_report("same")  # always same signature

    loop = AgentLoop(
        llm=MockLLM(actions),
        registry=ToolRegistry.for_repo(tmp_repo),
        pipeline=FakePipe(),
        config=Config.load(None, {}),
        repo=tmp_repo,
    )
    res = loop.run(Task(goal="fix", target_repo=str(tmp_repo), budget={}))
    assert res.status == Status.BLOCKED_NO_PROGRESS


def test_loop_budget_exhausted(tmp_repo):
    actions = [
        LLMResponse(actions=[Action(type="shell", command="echo x")], raw="", stop_reason="ok")
        for _ in range(5)
    ]

    class FakePipe:
        def run(self, repo, changed_files=None):
            return _fail_report("vary")

    loop = AgentLoop(
        llm=MockLLM(actions),
        registry=ToolRegistry.for_repo(tmp_repo),
        pipeline=FakePipe(),
        config=Config.load(None, {}),
        repo=tmp_repo,
    )
    res = loop.run(Task(goal="fix", target_repo=str(tmp_repo), budget={"max_iterations": 2}))
    assert res.status == Status.STOPPED_BUDGET


def test_loop_guardrail_blocks_dangerous(tmp_repo):
    actions = [
        LLMResponse(actions=[Action(type="shell", command="rm -rf /")], raw="", stop_reason="ok"),
        LLMResponse(actions=[], raw="end", stop_reason="end_turn"),
    ]

    class FakePipe:
        def run(self, repo, changed_files=None):
            return _ok_report()

    loop = AgentLoop(
        llm=MockLLM(actions),
        registry=ToolRegistry.for_repo(tmp_repo),
        pipeline=FakePipe(),
        config=Config.load(None, {}),
        repo=tmp_repo,
    )
    res = loop.run(Task(goal="g", target_repo=str(tmp_repo), budget={}))
    # dangerous action blocked: not executed, HITL default reject -> STOPPED_REJECTED
    assert res.status == Status.STOPPED_REJECTED
