"""Validator base class, Failure/FailureReport models, and signature hash.

Deterministic data model for the feedback loop (SPEC §6). All concrete
validators produce a :class:`FailureReport` whose :func:`signature` is a
stable sha1 over the normalized set of failures, so re-ordering of failures
or non-load-bearing fields never changes the identity of a report.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel, Field


class Category(str, Enum):
    """SPEC §6 failure taxonomy (10 categories)."""

    COMPILE_SYNTAX = "COMPILE_SYNTAX"
    COMPILE_MISSING_SYMBOL = "COMPILE_MISSING_SYMBOL"
    TEST_FAILURE = "TEST_FAILURE"
    TEST_ERROR = "TEST_ERROR"
    TEST_MISSING = "TEST_MISSING"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    LINT_VIOLATION = "LINT_VIOLATION"
    BUILD_CONFIG_ERROR = "BUILD_CONFIG_ERROR"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


class Failure(BaseModel):
    """A single failure emitted by a validator."""

    validator: str
    severity: str
    file: str
    line: int | None
    category: Category
    message: str
    raw: str = ""
    hint: str = ""


class FailureReport(BaseModel):
    """Aggregate output of one validator pass."""

    per_validator_status: dict[str, str] = Field(default_factory=dict)
    failures: list[Failure] = Field(default_factory=list)
    signature: str = ""
    summary: dict[str, int] = Field(default_factory=dict)


class Validator(ABC):
    """Abstract validator: ``run(repo, changed_files?) -> FailureReport``."""

    @abstractmethod
    def run(self, repo: str, changed_files: list[str] | None = None) -> FailureReport:
        """Inspect ``repo`` (optionally scoped to ``changed_files``) and report failures."""
        raise NotImplementedError


def signature(failures: list[Failure]) -> str:
    """Stable sha1 over the normalized, sorted set of failures.

    Only the load-bearing fields (``category|file|line|message``) participate,
    so re-ordering, validator identity, raw output, and hints never affect the
    hash. An empty failure list yields ``sha1("")``.
    """
    lines = sorted(
        f"{f.category.value}|{f.file}|{f.line}|{f.message}" for f in failures
    )
    payload = "\n".join(lines)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()
