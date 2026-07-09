"""TestValidator: run ``mvn test`` and parse surefire XML reports.

Feedback signal (SPEC §6) for the test stage. Consumes
:mod:`probe.validators.base` and produces raw :class:`Failure` objects whose
category distinguishes assertion failures (``TEST_FAILURE``), test errors
(``TEST_ERROR``), and skipped tests (``TEST_MISSING``).

The runner is injected so tests can run without network/maven.
"""

from __future__ import annotations

import glob
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter

from probe.validators.base import (
    Category,
    Failure,
    FailureReport,
    Validator,
    signature,
)

#: ``mvn test`` — run all unit tests.
TEST_CMD = "mvn test"

#: ``at pkg.Cls.method(File.java:LINE)`` surefire stack frame line.
_JAVA_LINE_RE = re.compile(r"\.java:(\d+)")

#: ``expected [...] but was [...]`` assertion message.
_ASSERT_RE = re.compile(r"expected \[.*?] but was \[.*?]")


class TestValidator(Validator):
    """Test-stage feedback signal."""

    name = "test"

    #: Suppress pytest collection — class name starts with ``Test``.
    __test__ = False

    def __init__(self, runner=None) -> None:
        """``runner`` is ``callable(cmd:str)->(exit_code, stdout, stderr)``.

        If omitted, a default runner shells out via :mod:`subprocess` in the
        repo working directory. Tests inject a stub so no mvn/network is
        needed.
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
            self._runner(TEST_CMD)
        except Exception:
            return FailureReport(
                per_validator_status={"test": "UNAVAILABLE"},
                failures=[],
                signature=signature([]),
                summary={},
            )

        report_dir = os.path.join(repo, "target", "surefire-reports")
        failures: list[Failure] = []
        for xml_path in sorted(glob.glob(os.path.join(report_dir, "TEST-*.xml"))):
            failures.extend(self._parse_file(xml_path))

        status = "PASS" if not failures else "FAIL"
        summary = dict(Counter(f.category.value for f in failures))
        return FailureReport(
            per_validator_status={"test": status},
            failures=failures,
            signature=signature(failures),
            summary=summary,
        )

    @staticmethod
    def _parse_file(xml_path: str) -> list[Failure]:
        failures: list[Failure] = []
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError:
            return failures
        root = tree.getroot()
        suite_name = root.attrib.get("name", "")
        for tc in root.findall("testcase"):
            classname = tc.attrib.get("classname", suite_name)
            file = TestValidator._classname_to_file(classname, suite_name)
            failure_el = tc.find("failure")
            error_el = tc.find("error")
            skipped_el = tc.find("skipped")
            if failure_el is not None:
                failures.append(
                    TestValidator._make_failure(
                        failure_el, file, Category.TEST_FAILURE, classname
                    )
                )
            if error_el is not None:
                failures.append(
                    TestValidator._make_failure(
                        error_el, file, Category.TEST_ERROR, classname
                    )
                )
            if skipped_el is not None:
                raw = (skipped_el.text or "").strip()
                line = TestValidator._extract_line(raw) or TestValidator._extract_line(
                    tc.attrib.get("name", "")
                )
                msg = skipped_el.attrib.get("message") or "skipped"
                failures.append(
                    Failure(
                        validator="test",
                        severity="warning",
                        file=file,
                        line=line,
                        category=Category.TEST_MISSING,
                        message=msg,
                        raw=raw,
                        hint="",
                    )
                )
        return failures

    @staticmethod
    def _make_failure(
        el: ET.Element,
        file: str,
        category: Category,
        classname: str,
    ) -> Failure:
        raw = (el.text or "").strip()
        attrib_msg = el.attrib.get("message")
        if attrib_msg:
            message = attrib_msg
        elif raw:
            first_line = raw.splitlines()[0].strip()
            message = first_line
        else:
            message = el.attrib.get("type", "")
        # Normalize assertion messages: prefer the ``expected [...] but was
        # [...]`` form if present anywhere in the raw text.
        m = _ASSERT_RE.search(raw) or _ASSERT_RE.search(message)
        if m:
            message = m.group(0)
        line = TestValidator._extract_line(raw)
        exc_type = el.attrib.get("type", "")
        hint = exc_type if category == Category.TEST_ERROR else ""
        return Failure(
            validator="test",
            severity="error",
            file=file,
            line=line,
            category=category,
            message=message,
            raw=raw,
            hint=hint,
        )

    @staticmethod
    def _extract_line(text: str) -> int | None:
        if not text:
            return None
        m = _JAVA_LINE_RE.search(text)
        return int(m.group(1)) if m else None

    @staticmethod
    def _classname_to_file(classname: str, suite_name: str) -> str:
        """Best-effort path for a test class.

        ``classname`` is typically the fully-qualified class name
        (``com.x.FooTest``). We convert dots to slashes and append
        ``.java``. Falls back to the testsuite name if empty.
        """
        base = classname or suite_name
        if not base:
            return ""
        inner = base.split("$")[0]
        return inner.replace(".", "/") + ".java"
