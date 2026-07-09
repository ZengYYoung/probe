from probe.codemap.retriever import dependents_of, dependencies_of, affected_set, responsibility_of
from probe.codemap.graph import CodeGraph, Type, Edge
def _g():
    return CodeGraph(modules=[], types=[
        Type(name="Foo",kind="class",package="com.x",members=[],extends=None,implements=[]),
        Type(name="Bar",kind="class",package="com.x",members=[],extends=None,implements=[]),
        Type(name="Baz",kind="class",package="com.x",members=[],extends="Bar",implements=[]),
        Type(name="FooTest",kind="class",package="com.x",members=[],extends=None,implements=[]),
        ], edges=[
        Edge(kind="depends",src="Bar",dst="Foo"),
        Edge(kind="associates",src="FooTest",dst="Foo"),  # 测试类依赖被测类
        ])
def test_dependents_of():
    assert "Bar" in dependents_of(_g(), "Foo")
    assert "FooTest" in dependents_of(_g(), "Foo")
def test_dependencies_of():
    assert "Foo" in dependencies_of(_g(), "Bar")
def test_affected_set_closure():
    res = affected_set(_g(), changed_files=["com.x/Foo.java"])
    assert "Bar" in res.affected_types
    assert "FooTest" in res.affected_types   # 闭包扩展到测试类
    assert "FooTest" in res.tests_to_run
def test_responsibility_of():
    g = CodeGraph(modules=[], types=[Type(name="UserController",kind="class",package="com.app.ctrl",members=[],extends=None,implements=[])], edges=[])
    r = responsibility_of(g, "com.app.ctrl")
    assert "controller" in r.lower() or "controller" in r
