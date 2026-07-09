"""CodeGraph data models (SPEC §8 CodeMap, secondary depth).

Pure pydantic v2 models describing the Java code map: modules (packages),
types (classes/interfaces with members), and typed edges between them.
No framework memory backend — the graph is built deterministically from
``javalang`` ASTs in :mod:`probe.codemap.builder`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Module(BaseModel):
    """A Java package aggregated from parsed source files."""

    name: str


class Member(BaseModel):
    """A field or method declared inside a :class:`Type`."""

    name: str
    kind: str  # "field" | "method"
    returns: str | None = None


class Type(BaseModel):
    """A class or interface discovered in the repo."""

    name: str
    kind: str  # "class" | "interface" | "enum"
    package: str
    members: list[Member] = Field(default_factory=list)
    extends: str | None = None
    implements: list[str] = Field(default_factory=list)


class Edge(BaseModel):
    """A typed relationship between two types (or a type and a symbol)."""

    kind: str  # extends | implements | imports | associates | depends
    src: str
    dst: str


class CodeGraph(BaseModel):
    """The whole code map: modules (packages), types, and edges."""

    modules: list[Module] = Field(default_factory=list)
    types: list[Type] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
