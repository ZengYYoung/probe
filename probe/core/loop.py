"""AgentLoop — the harness kernel main loop (SPEC §3 / Task 23).

Self-implemented orchestrator that wires together every Probe subsystem:
LLM → action parse → guardrail → tool dispatch → validator pipeline →
classifier → self-corrector → memory → re-injection → stop policy.

No agent framework is used; the loop is a plain ``while`` driven by an
:class:`LLMClient` (``MockLLM`` in tests, real client in prod). All IO-bearing
dependencies are injected, so the loop is deterministic and offline-testable.
"""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field

from probe.config import Config
from probe.feedback.self_corrector import Decision, SelfCorrector
from probe.guardrail.guardrail import Verdict, guardrail
from probe.guardrail.hitl import Event, State, transition
from probe.llm.base import Action, LLMClient, Message, ToolSpec
from probe.memory.store import Memory
from probe.tools.base import ToolResult
from probe.tools.registry import ToolRegistry
from probe.validators.base import FailureReport
from probe.validators.classifier import classify_report
from probe.core.types import Status


# ---------------------------------------------------------------------------
# Pydantic data models
# ---------------------------------------------------------------------------


class Task(BaseModel):
    """A unit of work handed to :class:`AgentLoop`.

    ``budget`` carries optional overrides; ``max_iterations`` falls back to
    ``config.budgets.max_iterations`` when absent.
    """

    goal: str
    target_repo: str
    budget: dict[str, Any] = Field(default_factory=dict)


class Step(BaseModel):
    """One iteration's worth of loop state, captured for replay/audit."""

    iteration: int
    action: Action
    tool_result: ToolResult
    failure_report: FailureReport | None = None
    decision: Decision | None = None


class RunResult(BaseModel):
    """Terminal output of :meth:`AgentLoop.run`."""

    status: Status
    steps: list[Step] = Field(default_factory=list)
    final_failure_report: FailureReport | None = None
    report_path: str | None = None


# ---------------------------------------------------------------------------
# Reason → Status mapping
# ---------------------------------------------------------------------------


def _map_reason(reason: str) -> Status:
    """Map a :class:`Decision` reason tag to a terminal :class:`Status`."""
    mapping = {
        "SUCCESS": Status.SUCCESS,
        "STOPPED_BUDGET": Status.STOPPED_BUDGET,
        "BLOCKED_NO_PROGRESS": Status.BLOCKED_NO_PROGRESS,
    }
    return mapping.get(reason, Status.ERROR)


def _report_all_pass(report: FailureReport | None) -> bool:
    """True when ``report`` exists, has no failures, and every validator PASS."""
    if report is None:
        return False
    if report.failures:
        return False
    return all(v == "PASS" for v in report.per_validator_status.values())


# ---------------------------------------------------------------------------
# AgentLoop
# ---------------------------------------------------------------------------


GuardrailFn = Callable[[Action, Config], Verdict]
ClassifierFn = Callable[[FailureReport], FailureReport]


class AgentLoop:
    """The harness kernel.

    Wires (llm, registry, pipeline, config, repo, memory, classifier,
    self_corrector, guardrail_fn) into a self-contained ``run(task)`` loop.
    Every collaborator is injected, so the loop is pure given its inputs.
    """

    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        pipeline: Any,
        config: Config,
        repo: Any,
        memory: Memory | None = None,
        classifier: ClassifierFn = classify_report,
        self_corrector: SelfCorrector | None = None,
        guardrail_fn: GuardrailFn | None = None,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.pipeline = pipeline
        self.config = config
        self.repo = repo
        self.memory: Memory = memory if memory is not None else Memory(repo)
        self.classifier = classifier
        self.self_corrector: SelfCorrector = (
            self_corrector if self_corrector is not None else SelfCorrector(config)
        )
        self.guardrail_fn: GuardrailFn = guardrail_fn if guardrail_fn is not None else guardrail

    def _build_tools(self) -> list[ToolSpec]:
        """Tool specs advertised to the LLM. Empty here — MockLLM ignores and
        a real client wires its own schema; the loop does not depend on this."""
        return []

    def run(self, task: Task) -> RunResult:
        """Drive the loop to a terminal :class:`Status`.

        Order of operations per iteration (SPEC §3 main loop):

        1. bump ``iter``; if over budget → STOPPED_BUDGET.
        2. call LLM with goal + trailing context fragments.
        3. empty actions → SUCCESS if last report all-PASS else STOPPED_BUDGET.
        4. take first action; guardrail; deny → HITL default-reject → STOPPED_REJECTED.
        5. dispatch tool; run pipeline; classify.
        6. self-corrector decides STOP/CONTINUE.
        7. record step + memory + history; CONTINUE re-injects fragment.
        """
        try:
            return self._run_inner(task)
        except Exception as exc:  # pragma: no cover - defensive terminator
            # Never leak an exception to the caller; collapse to ERROR.
            return RunResult(
                status=Status.ERROR,
                steps=[],
                final_failure_report=None,
                report_path=None,
            )

    def _run_inner(self, task: Task) -> RunResult:
        max_iter: int = int(
            task.budget.get("max_iterations", self.config.budgets.max_iterations)
        )
        history: list[str] = []
        steps: list[Step] = []
        last_report: FailureReport | None = None

        # Seed the conversation with the goal.
        messages: list[Message] = [Message(role="user", content=task.goal)]
        tools = self._build_tools()

        iteration = 0
        while True:
            iteration += 1
            if iteration > max_iter:
                return RunResult(
                    status=Status.STOPPED_BUDGET,
                    steps=steps,
                    final_failure_report=last_report,
                    report_path=None,
                )

            resp = self.llm.complete(messages, tools)

            # LLM yielded no action — terminal.
            if not resp.actions:
                status = (
                    Status.SUCCESS
                    if _report_all_pass(last_report)
                    else Status.STOPPED_BUDGET
                )
                return RunResult(
                    status=status,
                    steps=steps,
                    final_failure_report=last_report,
                    report_path=None,
                )

            # Multi-action frames are simplified to the first action.
            action = resp.actions[0]

            # Guardrail; deny → simulate HITL default-reject.
            verdict = self.guardrail_fn(action, self.config)
            if not verdict.allow:
                self._hitl_reject(action)
                return RunResult(
                    status=Status.STOPPED_REJECTED,
                    steps=steps,
                    final_failure_report=last_report,
                    report_path=None,
                )

            tool_result = self.registry.dispatch(action)

            report = self.pipeline.run(self.repo, changed_files=None)
            report = self.classifier(report)
            last_report = report

            budget_remaining = max_iter - iteration
            decision = self.self_corrector.decide(
                report, history, budget_remaining
            )

            self.memory.append_decision(
                {
                    "iter": iteration,
                    "sig": report.signature,
                    "action": decision.action,
                    "reason": decision.reason,
                }
            )
            history.append(report.signature)

            steps.append(
                Step(
                    iteration=iteration,
                    action=action,
                    tool_result=tool_result,
                    failure_report=report,
                    decision=decision,
                )
            )

            if decision.action == "STOP":
                status = _map_reason(decision.reason)
                return RunResult(
                    status=status,
                    steps=steps,
                    final_failure_report=last_report,
                    report_path=None,
                )

            # CONTINUE — re-inject the feedback fragment for the next round.
            if decision.context_fragment:
                messages.append(Message(role="assistant", content=resp.raw))
                messages.append(
                    Message(role="user", content=decision.context_fragment)
                )

    @staticmethod
    def _hitl_reject(action: Action) -> None:
        """Record the HITL state transitions for a denied action.

        Non-fatal: any ``ValueError`` from an illegal transition is swallowed
        — the deny outcome is already decided by the guardrail.
        """
        try:
            s = transition(State.idle, Event.ActionProposed)
            s = transition(s, Event.NeedsApproval)
            s = transition(s, Event.ApprovalDenied)  # default: deny in tests
            # ``s`` is State.rejected; nothing else to do.
        except ValueError:
            # The reject decision stands regardless of state-machine hiccups.
            pass
