"""Build a :class:`CodeGraph` from ``.java`` files via ``javalang``.

Deterministic, LLM-free: feed it a constructed AST and assert on the
emitted types/edges. Supports mtime-based incremental caching so
unchanged files are reused across runs.
"""

from __future__ import annotations

import json
from pathlib import Path

import javalang
from javalang.tree import (
    ClassCreator,
    ClassDeclaration,
    EnumDeclaration,
    FieldDeclaration,
    InterfaceDeclaration,
    MethodInvocation,
    MethodDeclaration,
)

from probe.codemap.graph import CodeGraph, Edge, Member, Module, Type

# Built-in / common JDK symbols that add no structural signal as an
# "associates" edge. Filtering them is optional per SPEC; we keep the
# noise down for primitives and the most ubiquitous boxed types.
_BUILTINS = {
    "void",
    "int",
    "long",
    "short",
    "byte",
    "char",
    "boolean",
    "double",
    "float",
    "String",
    "Object",
    "Integer",
    "Long",
    "Short",
    "Byte",
    "Character",
    "Boolean",
    "Double",
    "Float",
    "var",
}


def _short(path: str) -> str:
    """Last segment of a dotted import path (``com.y.Bar`` -> ``Bar``)."""
    return path.rsplit(".", 1)[-1]


def _parse_file(contents: str) -> tuple[list[Type], list[Edge]]:
    """Parse one Java source string into types + edges.

    Any parse error propagates to the caller (build_graph swallows it).
    """
    tree = javalang.parse.parse(contents)
    package = tree.package.name if tree.package else ""
    edges: list[Edge] = []

    # imports -> edges; src is empty (file-level), we will also re-emit per
    # type below so callers can ask "who imports Bar". The file-level edge
    # uses each top-level type name as src for richness.
    imported = [_short(i.path) for i in tree.imports]

    types: list[Type] = []
    decls = list(tree.filter(ClassDeclaration)) + list(
        tree.filter(InterfaceDeclaration)
    ) + list(tree.filter(EnumDeclaration))
    seen_names: set[str] = set()
    for _, decl in decls:
        if isinstance(decl, ClassDeclaration):
            kind = "class"
        elif isinstance(decl, InterfaceDeclaration):
            kind = "interface"
        else:
            kind = "enum"
        name = decl.name

        members: list[Member] = []
        # FieldDeclaration / MethodDeclaration live under decl.body
        body = getattr(decl, "body", []) or []
        for member in body:
            if isinstance(member, FieldDeclaration):
                ftype = member.type.name if member.type else None
                for d in member.declarators:
                    members.append(Member(name=d.name, kind="field", returns=ftype))
                    if ftype and ftype not in _BUILTINS:
                        edges.append(Edge(kind="associates", src=name, dst=ftype))
            elif isinstance(member, MethodDeclaration):
                rtype = member.return_type.name if member.return_type else None
                members.append(
                    Member(name=member.name, kind="method", returns=rtype)
                )
                if rtype and rtype not in _BUILTINS:
                    edges.append(Edge(kind="associates", src=name, dst=rtype))

        sup = decl.extends.name if getattr(decl, "extends", None) else None
        if sup:
            edges.append(Edge(kind="extends", src=name, dst=sup))
        impls = [i.name for i in (decl.implements or [])]
        for i in impls:
            edges.append(Edge(kind="implements", src=name, dst=i))

        for imp in imported:
            edges.append(Edge(kind="imports", src=name, dst=imp))

        # depends: new X() and method invocations in method bodies
        for _, cc in decl.filter(ClassCreator):
            tgt = cc.type.name if cc.type else None
            if tgt and tgt not in _BUILTINS:
                edges.append(Edge(kind="depends", src=name, dst=tgt))
        for _, mi in decl.filter(MethodInvocation):
            tgt = mi.qualifier or None
            # qualifier is the receiver expression text (e.g. "b"); we only
            # capture symbolic deps when the qualifier is a simple type-ish
            # name. Skip bare receivers — they add noise without signal.
            if tgt and tgt not in _BUILTINS and tgt[0].isupper():
                edges.append(Edge(kind="depends", src=name, dst=tgt))

        if name not in seen_names:
            seen_names.add(name)
            types.append(
                Type(
                    name=name,
                    kind=kind,
                    package=package,
                    members=members,
                    extends=sup,
                    implements=impls,
                )
            )

    return types, edges


def build_graph(repo: Path, cache_path: Path | None = None) -> CodeGraph:
    """Scan ``repo`` for ``.java`` files and return a :class:`CodeGraph`.

    When ``cache_path`` is given, per-file mtime is used to skip
    re-parsing unchanged files; the cache is a JSON dict keyed by file
    path with ``{mtime, types, edges}`` entries.
    """
    repo = Path(repo)
    cache: dict[str, dict] = {}
    if cache_path and Path(cache_path).exists():
        try:
            cache = json.loads(Path(cache_path).read_text())
        except (json.JSONDecodeError, OSError):
            cache = {}

    all_types: list[Type] = []
    all_edges: list[Edge] = []
    new_cache: dict[str, dict] = {}

    java_files = sorted(repo.rglob("*.java"))
    for fpath in java_files:
        key = str(fpath)
        try:
            mtime = fpath.stat().st_mtime
        except OSError:
            continue
        cached = cache.get(key)
        if cached and cached.get("mtime") == mtime:
            file_types = [Type(**t) for t in cached["types"]]
            file_edges = [Edge(**e) for e in cached["edges"]]
        else:
            try:
                contents = fpath.read_text(encoding="utf-8", errors="replace")
                file_types, file_edges = _parse_file(contents)
            except Exception:
                # Parse error / unreadable: skip without crashing.
                new_cache[key] = {"mtime": mtime, "types": [], "edges": []}
                continue
        new_cache[key] = {
            "mtime": mtime,
            "types": [t.model_dump() for t in file_types],
            "edges": [e.model_dump() for e in file_edges],
        }
        all_types.extend(file_types)
        all_edges.extend(file_edges)

    # Modules: one per distinct package (empty string included).
    packages: dict[str, Module] = {}
    for t in all_types:
        packages.setdefault(t.package, Module(name=t.package))
    modules = list(packages.values())

    if cache_path is not None:
        try:
            Path(cache_path).write_text(json.dumps(new_cache))
        except OSError:
            pass

    return CodeGraph(modules=modules, types=all_types, edges=all_edges)
