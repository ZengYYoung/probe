"""LintValidator: run ``mvn checkstyle:check`` and parse the result XML.

Feedback signal (SPEC §6) for the lint stage. Consumes
:mod:`probe.validators.base` and emits :class:`Failure` objects whose category
is :attr:`Category.LINT_VIOLATION`. The runner is injected so tests can run
without network/maven.
"""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from probe.validators.base import (
    Category,
    Failure,
    FailureReport,
    Validator,
    signature,
)

#: ``mvn checkstyle:check`` — run Checkstyle and emit ``target/checkstyle-result.xml``.
LINT_CMD = "mvn checkstyle:check"

#: Where checkstyle writes its findings.
RESULT_PATH = "target/checkstyle-result.xml"


class LintValidator(Validator):
    """Lint-stage feedback signal."""

    name = "lint"

    def __init__(self, runner=None) -> None:
        """``runner`` is ``callable(cmd:str)->(exit_code, stdout, stderr)``.

        If omitted, a default runner shells out via :mod:`subprocess` in the
        repo working directory. Tests inject a stub so no mvn/network is needed.
        """
        self._runner = runner or self._default_runner

    @staticmethod
    def _default_runner(cmd: str) -> tuple[int, str, str]:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def run(self, repo: str, changed_files: list[str] | None = None) -> FailureReport:
        try:
            self._runner(LINT_CMD)
        except Exception:
            return FailureReport(
                per_validator_status={"lint": "UNAVAILABLE"},
                failures=[],
                signature=signature([]),
                summary={},
            )

        result_file = Path(repo) / RESULT_PATH
        if not result_file.exists():
            return FailureReport(
                per_validator_status={"lint": "UNAVAILABLE"},
                failures=[],
                signature=signature([]),
                summary={},
            )

        failures = self._parse(result_file)
        status = "FAIL" if failures else "PASS"
        summary = dict(Counter(f.category.value for f in failures))
        return FailureReport(
            per_validator_status={"lint": status},
            failures=failures,
            signature=signature(failures),
            summary=summary,
        )

    @staticmethod
    def _parse(result_file: Path) -> list[Failure]:
        failures: list[Failure] = []
        tree = ET.parse(result_file)
        root = tree.getroot()
        for file_el in root.findall("file"):
            file_name = file_el.get("name", "")
            for err in file_el.findall("error"):
                line = err.get("line")
                severity = err.get("severity", "error")
                message = err.get("message", "")
                source = err.get("source", "")
                failures.append(
                    Failure(
                        validator="lint",
                        severity=severity,
                        file=file_name,
                        line=int(line) if line is not None else None,
                        category=Category.LINT_VIOLATION,
                        message=message,
                        raw=source,
                        hint=f"规则 {source}" if source else "",
                    )
                )
        return failures
