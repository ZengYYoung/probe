"""CodeMap impact-closure retrieval (SPEC §8, Task 20).

Pure functions over :class:`probe.codemap.graph.CodeGraph` for computing
dependent types, dependency types, the affected (reverse-closure) set of
types reachable from a set of changed files, and a coarse responsibility
label for a package. Deterministic and side-effect free.
"""

from __future__ import annotations

import os
from pydantic import BaseModel, Field

from probe.codemap.graph import CodeGraph


class AffectedResult(BaseModel):
    """Outcome of an impact-closure computation."""

    affected_types: list[str] = Field(default_factory=list)
    tests_to_run: list[str] = Field(default_factory=list)


def _type_name_from_file(path: str) -> str:
    """Extract the Java class name from a changed-file path.

    Accepts ``com.x/Foo.java`` or ``Foo.java`` form: strip directory, strip
    ``.java`` extension. The remaining basename is the public type name.
    """
    base = path.rsplit("/", 1)[-1]
    if base.endswith(".java"):
        base = base[: -len(".java")]
    return base


def dependents_of(graph: CodeGraph, type_name: str) -> list[str]:
    """All types that point to ``type_name`` (edge.dst == type_name)."""
    seen: list[str] = []
    for edge in graph.edges:
        if edge.dst == type_name and edge.src not in seen:
            seen.append(edge.src)
    return seen


def dependencies_of(graph: CodeGraph, type_name: str) -> list[str]:
    """All types that ``type_name`` points to (edge.src == type_name)."""
    seen: list[str] = []
    for edge in graph.edges:
        if edge.src == type_name and edge.dst not in seen:
            seen.append(edge.dst)
    return seen


def affected_set(graph: CodeGraph, changed_files: list[str]) -> AffectedResult:
    """BFS reverse closure over typed edges starting from changed types.

    A changed file names a seed type. We then iteratively expand: for every
    edge whose ``dst`` is already in the closure, add its ``src``. All edge
    kinds (depends/associates/extends/implements/calls/...) are traversed in
    the reverse direction, since a change to ``dst`` may affect ``src``.
    """
    closure: set[str] = set()
    for path in changed_files:
        name = _type_name_from_file(path)
        if name:
            closure.add(name)

    # Iterate to fixpoint.
    changed = True
    while changed:
        changed = False
        for edge in graph.edges:
            if edge.dst in closure and edge.src not in closure:
                closure.add(edge.src)
                changed = True

    affected_types = sorted(closure)

    tests_to_run = [
        name for name in affected_types if name.endswith("Test") or "Test" in name
    ]

    return AffectedResult(
        affected_types=affected_types,
        tests_to_run=tests_to_run,
    )


def responsibility_of(graph: CodeGraph, package: str) -> str:
    """Coarse responsibility heuristic from package/type keywords."""
    # Gather candidate text: package name plus the names of types in it.
    type_names = [t.name for t in graph.types if t.package == package]
    text = (package + " " + " ".join(type_names)).lower()

    if "controller" in text or "ctrl" in text:
        return "Controller 层"
    if "service" in text:
        return "Service 层"
    if "repository" in text or "repo" in text or "dao" in text:
        return "Repository 层"
    if "model" in text or "entity" in text or "dto" in text:
        return "Model 层"
    if "util" in text:
        return "工具层"
    return "未识别"
