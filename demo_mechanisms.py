"""A.6 机制演示（Task 27）。

三个确定性演示函数，全用 MockLLM / 构造数据，无网络无 key 无真实 LLM：

1. ``demo_guardrail()``        — 危险动作拦截（纯函数，无 LLM）。
2. ``demo_feedback_loop()``    — 注入一次失败后反馈闭环使 agent 改为 patch。
3. ``demo_no_progress()``      — 同一签名 FAIL 连续 K 轮触发 BLOCKED_NO_PROGRESS。

可直接 ``python demo_mechanisms.py`` 运行，也可 ``import demo_mechanisms`` 调单函数。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from probe.config import Config
from probe.core.loop import AgentLoop, Task
from probe.core.types import Status
from probe.feedback.self_corrector import SelfCorrector
from probe.guardrail.guardrail import guardrail
from probe.llm.base import Action, LLMResponse
from probe.llm.mock import MockLLM
from probe.tools.registry import ToolRegistry
from probe.validators.base import (
    Category,
    Failure,
    FailureReport,
    signature,
)


# ---------------------------------------------------------------------------
# ① Guardrail demo
# ---------------------------------------------------------------------------


def demo_guardrail() -> str:
    """构造一个危险 shell 动作，演示 guardrail 拦截。无 LLM。"""
    action = Action(type="shell", command="rm -rf /")
    config = Config.load(None, {})
    verdict = guardrail(action, config)
    assert not verdict.allow, "guardrail 应当拦截 rm -rf /"
    return f"BLOCKED: {verdict.reason}"


# ---------------------------------------------------------------------------
# ② Feedback loop demo
# ---------------------------------------------------------------------------


def _test_failure_report(sig: str = "fail1") -> FailureReport:
    """构造一个含 TEST_FAILURE 的失败报告（已分类）。"""
    f = Failure(
        validator="test",
        severity="high",
        file="src/CalculatorTest.java",
        line=12,
        category=Category.TEST_FAILURE,
        message="expected: 4 but was: 5",
        raw="AssertionError",
        hint="断言失败",
    )
    return FailureReport(
        per_validator_status={"compile": "PASS", "test": "FAIL", "lint": "PASS"},
        failures=[f],
        signature=sig,
        summary={"TEST_FAILURE": 1},
    )


def _pass_report() -> FailureReport:
    return FailureReport(
        per_validator_status={"compile": "PASS", "test": "PASS", "lint": "PASS"},
        failures=[],
        signature="ok",
        summary={},
    )


def demo_feedback_loop() -> list:
    """注入一次失败 → 反馈闭环 → agent 下一步动作改为 patch。

    - MockLLM 脚本：第 1 轮 write，第 2 轮 patch，第 3 轮空动作收尾。
    - FakePipe：第 1 轮 FAIL（TEST_FAILURE），第 2 轮全 PASS。
    - 收集 AgentLoop 每步动作，返回字符串列表。
    """
    repo = Path(tempfile.mkdtemp(prefix="probe-demo-fb-"))
    actions = [
        LLMResponse(
            actions=[
                Action(
                    type="write",
                    path="src/Calc.java",
                    params={"content": "class Calc {}"},
                )
            ],
            raw="write initial code",
            stop_reason="ok",
        ),
        LLMResponse(
            actions=[
                Action(
                    type="patch",
                    path="src/Calc.java",
                    params={"old": "class Calc {}", "new": "class Calc { int add(){return 4;} }"},
                )
            ],
            raw="patch per feedback",
            stop_reason="ok",
        ),
        LLMResponse(actions=[], raw="done", stop_reason="end_turn"),
    ]

    class FakePipe:
        def __init__(self) -> None:
            self._n = 0

        def run(self, repo, changed_files=None):
            self._n += 1
            if self._n == 1:
                return _test_failure_report()
            return _pass_report()

    loop = AgentLoop(
        llm=MockLLM(actions),
        registry=ToolRegistry.for_repo(repo),
        pipeline=FakePipe(),
        config=Config.load(None, {}),
        repo=repo,
    )
    result = loop.run(
        Task(goal="make CalculatorTest pass", target_repo=str(repo), budget={})
    )

    log = [
        f"step {s.iteration}: action={s.action.type} reason={s.decision.reason if s.decision else ''}"
        for s in result.steps
    ]
    return log


# ---------------------------------------------------------------------------
# ③ No-progress demo
# ---------------------------------------------------------------------------


def demo_no_progress() -> str:
    """同一签名 FAIL 连续 K 轮 → SelfCorrector 触发 BLOCKED_NO_PROGRESS。"""
    config = Config.load(None, {})
    repo = Path(tempfile.mkdtemp(prefix="probe-demo-np-"))

    actions = [
        LLMResponse(
            actions=[Action(type="shell", command="echo retry")],
            raw="",
            stop_reason="ok",
        )
        for _ in range(8)
    ]

    same_report = _test_failure_report(sig="stuck")

    class FakePipe:
        def run(self, repo, changed_files=None):
            # 永远返回同一签名 FAIL
            return same_report.model_copy()

    loop = AgentLoop(
        llm=MockLLM(actions),
        registry=ToolRegistry.for_repo(repo),
        pipeline=FakePipe(),
        config=config,
        repo=repo,
    )
    result = loop.run(
        Task(goal="fix recurring failure", target_repo=str(repo), budget={})
    )
    assert result.status == Status.BLOCKED_NO_PROGRESS, (
        f"expected BLOCKED_NO_PROGRESS, got {result.status}"
    )
    return f"BLOCKED_NO_PROGRESS: stopped after {config.no_progress_rounds} rounds"


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== demo_guardrail ===")
    print(demo_guardrail())
    print()
    print("=== demo_feedback_loop ===")
    for line in demo_feedback_loop():
        print(line)
    print()
    print("=== demo_no_progress ===")
    print(demo_no_progress())
