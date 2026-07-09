"""DOT renderers for CodeGraph (SPEC §8 CodeMap, Task 21).

Pure, deterministic functions that turn a :class:`~probe.codemap.graph.CodeGraph`
into Graphviz DOT strings: a package-level aggregation view and a class-level
view (optionally filtered by package). The :func:`layout` helper shells out to
the ``dot`` binary to produce an image file.
"""

from __future__ import annotations

import subprocess
from collections import OrderedDict
from pathlib import Path

from probe.codemap.graph import CodeGraph, Edge, Type


def _quote(name: str) -> str:
    """Wrap a node/edge identifier in double quotes, escaping inner quotes."""
    return '"' + name.replace('"', '\\"') + '"'


def _type_by_name(types: list[Type]) -> dict[str, Type]:
    return {t.name: t for t in types}


def render_package_dot(graph: CodeGraph) -> str:
    """Render a package-level digraph.

    Nodes are the set of distinct packages seen on types; edges aggregate
    type-level edges to their src/dst packages, dropping self-loops.
    """
    packages: "OrderedDict[str, None]" = OrderedDict()
    for t in graph.types:
        packages.setdefault(t.package, None)

    pkg_of: dict[str, str] = {t.name: t.package for t in graph.types}

    agg_edges: "OrderedDict[tuple[str, str], None]" = OrderedDict()
    for e in graph.edges:
        src_pkg = pkg_of.get(e.src)
        dst_pkg = pkg_of.get(e.dst)
        if src_pkg is None or dst_pkg is None:
            continue
        if src_pkg == dst_pkg:
            continue
        agg_edges.setdefault((src_pkg, dst_pkg), None)

    lines: list[str] = ["digraph G {"]
    for pkg in packages:
        lines.append(f"    {_quote(pkg)} [shape=box];")
    for src_pkg, dst_pkg in agg_edges:
        lines.append(f"    {_quote(src_pkg)} -> {_quote(dst_pkg)};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _edge_style(kind: str) -> str:
    if kind == "implements":
        return " [style=dashed, label=implements]"
    if kind in ("extends", "associates", "depends"):
        return f" [label={kind}]"
    return f" [label={kind}]"


def render_class_dot(graph: CodeGraph, package: str | None = None) -> str:
    """Render a class-level digraph, optionally filtered to one package."""
    types = [t for t in graph.types if package is None or t.package == package]
    names = {t.name for t in types}

    lines: list[str] = ["digraph G {"]
    for t in types:
        lines.append(f"    {_quote(t.name)};")
    for e in graph.edges:
        if e.src not in names:
            continue
        lines.append(f"    {_quote(e.src)} -> {_quote(e.dst)}{_edge_style(e.kind)};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def layout(dot_str: str, out_path: Path, fmt: str = "png") -> Path:
    """Run graphviz ``dot`` to render ``dot_str`` into ``out_path``.

    Raises FileNotFoundError if ``dot`` is not installed, or RuntimeError on
    non-zero exit. Returns the path written.
    """
    out_path = Path(out_path)
    try:
        proc = subprocess.run(
            ["dot", f"-T{fmt}", "-o", str(out_path)],
            input=dot_str,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError("graphviz `dot` binary not found on PATH") from exc
    if proc.returncode != 0:
        raise RuntimeError(
            f"dot exited {proc.returncode}: {proc.stderr.strip()}"
        )
    return out_path
