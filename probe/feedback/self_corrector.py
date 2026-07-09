"""SelfCorrector — feedback loop closure (SPEC §6 / Task 18).

Deterministic decision policy over a :class:`FailureReport` plus the running
signature history and remaining budget. Produces a :class:`Decision` telling
the orchestrator whether to CONTINUE (re-inject the context fragment) or STOP
(success / budget exhausted / no progress).
"""

from __future__ import annotations

from pydantic import BaseModel

from probe.config import Config
from probe.validators.base import FailureReport


class Decision(BaseModel):
    """Output of :meth:`SelfCorrector.decide`.

    - ``action``: "CONTINUE" (re-inject feedback) or "STOP".
    - ``reason``: short tag — "SUCCESS" | "STOPPED_BUDGET" |
      "BLOCKED_NO_PROGRESS" | "feedback".
    - ``context_fragment``: human-readable failure digest for re-injection.
    """

    action: str
    reason: str = ""
    context_fragment: str = ""


class SelfCorrector:
    """Deterministic feedback-loop stop / continue policy.

    Pure function over (report, history, budget_remaining); no IO, no LLM.
    Stop criteria order (per Task 18 spec):

    1. SUCCESS — every validator PASS and no failures.
    2. STOPPED_BUDGET — budget_remaining <= 0 (and not SUCCESS).
    3. BLOCKED_NO_PROGRESS — the current signature has appeared >= K
       consecutive times within the trailing K history entries.
    4. otherwise CONTINUE with a synthesized context fragment.
    """

    def __init__(self, config: Config) -> None:
        self.K: int = config.no_progress_rounds

    def decide(
        self,
        report: FailureReport,
        history: list[str],
        budget_remaining: int,
    ) -> Decision:
        # 1. Success — all validators PASS and no failures recorded.
        if report.failures == [] and all(
            v == "PASS" for v in report.per_validator_status.values()
        ):
            return Decision(action="STOP", reason="SUCCESS")

        # 2. Budget exhausted.
        if budget_remaining <= 0:
            return Decision(action="STOP", reason="STOPPED_BUDGET")

        # 3. No progress — same signature seen K times in the trailing K
        #    history entries. (history does NOT include the current report's
        #    signature; we compare the current signature against the tail.)
        if self.K > 0 and history[-self.K:].count(report.signature) >= self.K:
            return Decision(action="STOP", reason="BLOCKED_NO_PROGRESS")

        # 4. Continue — synthesize re-injection fragment.
        return Decision(
            action="CONTINUE",
            reason="feedback",
            context_fragment=self._build_fragment(report, budget_remaining),
        )

    @staticmethod
    def _build_fragment(report: FailureReport, budget_remaining: int) -> str:
        lines: list[str] = []
        for f in report.failures:
            lines.append(
                f"{f.file}:{f.line} | {f.category.value} | {f.message} | hint: {f.hint}"
            )
        lines.append(f"remaining budget: {budget_remaining}")
        return "\n".join(lines)
