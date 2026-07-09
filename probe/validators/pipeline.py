"""ValidatorPipeline: run Compile/Test/Lint validators in order with short-circuit.

SPEC §6 feedback aggregation. Compile FAIL short-circuits Test (skipped,
not run); Lint always runs unless disabled in Config. Failures from all
stages are merged and the signature is recomputed over the union so the
report identity is independent of per-validator signatures.
"""

from __future__ import annotations

from collections import Counter

from probe.config import Config
from probe.validators.base import FailureReport, signature


class ValidatorPipeline:
    """Sequence Compile → Test (short-circuit) → Lint, merging reports."""

    def __init__(self, compile_v, test_v, lint_v, config: Config | None = None) -> None:
        self.compile_v = compile_v
        self.test_v = test_v
        self.lint_v = lint_v
        self.config = config if config is not None else Config.load(None, {})

    def run(self, repo: str, changed_files: list[str] | None = None) -> FailureReport:
        status: dict[str, str] = {}
        failures = []

        cr = self.compile_v.run(repo, changed_files)
        status.update(cr.per_validator_status)
        failures.extend(cr.failures)

        if cr.per_validator_status.get("compile") == "FAIL":
            status["test"] = "SKIPPED"
        else:
            tr = self.test_v.run(repo, changed_files)
            status.update(tr.per_validator_status)
            failures.extend(tr.failures)

        if self.config.validators.lint:
            lr = self.lint_v.run(repo, changed_files)
            status.update(lr.per_validator_status)
            failures.extend(lr.failures)
        else:
            status["lint"] = "SKIPPED"

        summary = dict(Counter(f.category.value for f in failures))
        return FailureReport(
            per_validator_status=status,
            failures=failures,
            signature=signature(failures),
            summary=summary,
        )
