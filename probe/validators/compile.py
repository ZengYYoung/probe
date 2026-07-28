"""CompileValidator: run ``mvn test-compile`` and parse javac errors.

Feedback signal (SPEC §6) for the compilation stage. Consumes
:mod:`probe.validators.base` and produces raw :class:`Failure` objects whose
category is a coarse local guess (``COMPILE_SYNTAX`` vs
``COMPILE_MISSING_SYMBOL``); the T17 classifier refines these later.

The runner is injected so tests can run without network/maven.

Project structure detection: before shelling out to Maven, the validator
locates the Maven root via :func:`probe.validators.project.find_maven_root`.
If ``pom.xml`` is in a subdirectory (common with uploaded zips), Maven runs
there. If no ``pom.xml`` is found at all, a specific, actionable
``BUILD_CONFIG_ERROR`` is returned — instead of letting Maven fail with a
cryptic "no POM" message.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter

from probe.validators.base import (
    Category,
    Failure,
    FailureReport,
    Validator,
    signature,
)
from probe.validators.project import find_maven_root

#: ``mvn -q -DskipTests test-compile`` — compile main+test sources, no tests run.
COMPILE_CMD = "mvn -q -DskipTests test-compile"

#: javac ``[ERROR] file:[line,col] error: message`` line.
_ERROR_RE = re.compile(
    r"\[ERROR\]\s+(?P<file>.*?)[:]\[(?P<line>\d+)[,\d]*\]\s+error:\s+(?P<msg>.*)"
)


class CompileValidator(Validator):
    """Compile-stage feedback signal."""

    name = "compile"

    def __init__(self, runner=None) -> None:
        """``runner`` is ``callable(cmd, cwd)->(exit_code, stdout, stderr)``.

        If omitted, a default runner shells out via :mod:`subprocess` in the
        repo working directory. Tests inject a stub so no mvn/network is
        needed.
        """
        self._runner = runner or self._default_runner

    @staticmethod
    def _default_runner(cmd: str, cwd: str | None = None) -> tuple[int, str, str]:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def run(self, repo: str, changed_files: list[str] | None = None) -> FailureReport:
        maven_dir, reason = find_maven_root(repo)

        if maven_dir is None:
            return self._no_pom_report(reason)

        try:
            exit_code, stdout, stderr = self._runner(COMPILE_CMD, maven_dir)
        except Exception:
            return FailureReport(
                per_validator_status={"compile": "UNAVAILABLE"},
                failures=[],
                signature=signature([]),
                summary={},
            )

        failures = self._parse(stdout + "\n" + stderr)
        status = "PASS" if exit_code == 0 and not failures else "FAIL"

        # Fallback: compile failed but no parseable javac errors (e.g. no
        # pom.xml, dependency resolution failure, Maven not installed).
        # Capture raw output so the agent has feedback and the signature
        # is non-trivial — prevents premature BLOCKED_NO_PROGRESS.
        if status == "FAIL" and not failures:
            raw_output = (stderr + "\n" + stdout).strip()
            failures.append(
                Failure(
                    validator="compile",
                    severity="error",
                    file="",
                    line=0,
                    category=Category.BUILD_CONFIG_ERROR,
                    message=raw_output[:500] or "compile failed (no parseable errors)",
                    raw=raw_output,
                    hint="check pom.xml, project structure, or Maven installation",
                )
            )

        summary = dict(Counter(f.category.value for f in failures))
        return FailureReport(
            per_validator_status={"compile": status},
            failures=failures,
            signature=signature(failures),
            summary=summary,
        )

    @staticmethod
    def _no_pom_report(reason: str) -> FailureReport:
        """Build a specific, actionable BUILD_CONFIG_ERROR when no pom.xml."""
        if reason == "gradle":
            msg = (
                "No pom.xml found but build.gradle detected — "
                "Probe only deeply supports Maven (SPEC §10 R1). "
                "Gradle is best-effort and not fully supported."
            )
            hint = (
                "convert the project to Maven, or ensure the uploaded zip "
                "has pom.xml at the root"
            )
        else:
            msg = (
                "No pom.xml found in the repository. "
                "Probe requires a Maven-managed Java project."
            )
            hint = (
                "ensure the uploaded zip contains pom.xml at the root; "
                "if pom.xml is in a subdirectory, restructure the zip so "
                "pom.xml is at the top level"
            )
        f = Failure(
            validator="compile",
            severity="error",
            file="",
            line=0,
            category=Category.BUILD_CONFIG_ERROR,
            message=msg,
            raw="",
            hint=hint,
        )
        return FailureReport(
            per_validator_status={"compile": "FAIL"},
            failures=[f],
            signature=signature([f]),
            summary={"BUILD_CONFIG_ERROR": 1},
        )

    @staticmethod
    def _parse(stream: str) -> list[Failure]:
        failures: list[Failure] = []
        for line in stream.splitlines():
            m = _ERROR_RE.match(line)
            if not m:
                continue
            msg = m.group("msg").strip()
            category = (
                Category.COMPILE_MISSING_SYMBOL
                if "cannot find symbol" in msg
                else Category.COMPILE_SYNTAX
            )
            failures.append(
                Failure(
                    validator="compile",
                    severity="error",
                    file=m.group("file"),
                    line=int(m.group("line")),
                    category=category,
                    message=msg,
                    raw=line,
                    hint="",
                )
            )
        return failures
