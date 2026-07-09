from probe.codemap.renderer import render_package_dot, render_class_dot
from probe.codemap.graph import CodeGraph, Type, Edge


def test_package_dot_has_nodes():
    g = CodeGraph(modules=[], types=[Type(name="Foo", kind="class", package="com.x", members=[], extends=None, implements=[])], edges=[])
    dot = render_package_dot(g)
    assert "digraph" in dot
    assert "com.x" in dot


def test_package_dot_aggregates_edges():
    g = CodeGraph(modules=[], types=[
        Type(name="Foo", kind="class", package="com.x", members=[], extends=None, implements=[]),
        Type(name="Bar", kind="class", package="com.y", members=[], extends=None, implements=[])],
        edges=[Edge(kind="depends", src="Foo", dst="Bar")])
    dot = render_package_dot(g)
    assert '"com.x" -> "com.y"' in dot or "com.x" in dot and "com.y" in dot


def test_class_dot_has_extends_edge():
    g = CodeGraph(modules=[], types=[Type(name="Foo", kind="class", package="p", members=[], extends="Bar", implements=[])],
        edges=[Edge(kind="extends", src="Foo", dst="Bar")])
    dot = render_class_dot(g)
    assert '"Foo" -> "Bar"' in dot


def test_class_dot_filtered_by_package():
    g = CodeGraph(modules=[], types=[
        Type(name="A", kind="class", package="pkg1", members=[], extends=None, implements=[]),
        Type(name="B", kind="class", package="pkg2", members=[], extends=None, implements=[])],
        edges=[])
    dot = render_class_dot(g, package="pkg1")
    assert '"A"' in dot
    assert '"B"' not in dot
