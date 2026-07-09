"""FailureClassifier: pure-function taxonomy mapping failures to categories.

SPEC §6 feedback-loop deep dimension. Cold-start correction: rules are ordered
**specific-first, generic-last** and disambiguated by the ``validator`` field.
:func:`classify` and :func:`classify_report` are pure — no IO, no randomness,
no mutation of their inputs.
"""

from __future__ import annotations

import re

from probe.validators.base import (
    Category,
    Failure,
    FailureReport,
    signature,
)

# Ordered rule table. Each entry:
#   (validator_scope: str | None, pattern: str, category: Category, hint: str)
# validator_scope == None means "applies to any validator".
# First matching rule wins — therefore specific patterns must precede generic
# ones, and validator-scoped rules must precede the catch-all rules that could
# otherwise shadow them.
_RULES: list[tuple[str | None, str, Category, str]] = [
    # --- compile: specific → generic ---
    ("compile", r"cannot find symbol", Category.COMPILE_MISSING_SYMBOL,
     "检查 import/声明"),
    ("compile", r"Could not resolve", Category.DEPENDENCY_MISSING,
     "检查 pom 依赖坐标"),
    ("compile", r"error:", Category.COMPILE_SYNTAX, "语法错误"),
    # --- test: specific → generic ---
    ("test", r"expected.*but was", Category.TEST_FAILURE,
     "断言不符：核对 actual vs expected"),
    ("test", r"AssertionError", Category.TEST_FAILURE, "断言失败"),
    ("test", r"Exception|<error>", Category.TEST_ERROR, "测试抛异常"),
    ("test", r"disabled|skipped", Category.TEST_MISSING, "测试未运行"),
    # --- lint ---
    ("lint", r".", Category.LINT_VIOLATION, "按 checkstyle 规则 id 修正"),
    # --- validator-agnostic catch-alls (last resort) ---
    (None, r"timed?out|timeout", Category.TIMEOUT, "增大超时或缩小范围"),
    (None, r"BUILD.*FAILURE|pom|build\.xml", Category.BUILD_CONFIG_ERROR,
     "检查构建配置"),
]

_COMPILED: list[tuple[str | None, re.Pattern[str], Category, str]] = [
    (scope, re.compile(pattern, re.IGNORECASE | re.DOTALL), cat, hint)
    for scope, pattern, cat, hint in _RULES
]


def classify(failure: Failure) -> tuple[Category, str]:
    """Map a single :class:`Failure` to ``(category, hint)``.

    Pure: does not mutate ``failure``. The first rule whose
    ``validator_scope`` matches ``failure.validator`` (or is ``None``) and
    whose pattern matches ``f"{failure.message} {failure.raw}"`` wins.
    No match → ``(Category.UNKNOWN, failure.message or "No hint available")``.
    """
    haystack = f"{failure.message} {failure.raw}"
    for scope, pattern, cat, hint in _COMPILED:
        if scope is not None and scope != failure.validator:
            continue
        if pattern.search(haystack):
            return cat, hint
    return Category.UNKNOWN, failure.message or "No hint available"


def classify_report(report: FailureReport) -> FailureReport:
    """Return a **new** :class:`FailureReport` with classified failures.

    Pure: neither ``report`` nor any :class:`Failure` inside it is mutated.
    Each failure is deep-copied, classified, then ``signature``/``summary``
    are recomputed. ``per_validator_status`` is carried over unchanged.
    """
    new_failures: list[Failure] = []
    for f in report.failures:
        cat, hint = classify(f)
        new_failures.append(
            Failure(
                validator=f.validator,
                severity=f.severity,
                file=f.file,
                line=f.line,
                category=cat,
                message=f.message,
                raw=f.raw,
                hint=hint,
            )
        )

    summary: dict[str, int] = {}
    for f in new_failures:
        key = f.category.value
        summary[key] = summary.get(key, 0) + 1

    return FailureReport(
        per_validator_status=dict(report.per_validator_status),
        failures=new_failures,
        signature=signature(new_failures),
        summary=summary,
    )
