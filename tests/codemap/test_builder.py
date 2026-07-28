from probe.codemap.builder import build_graph

JAVA = """package com.x;
import com.y.Bar;
class Foo extends Baz implements Bar {
    Bar field;
    void m(){ Bar b = new Bar(); }
}
"""


def test_builds_types_and_edges(tmp_path):
    p = tmp_path / "src/main/java/com/x/Foo.java"
    p.parent.mkdir(parents=True)
    p.write_text(JAVA)
    g = build_graph(tmp_path)
    names = {t.name for t in g.types}
    assert "Foo" in names
    kinds = {(e.kind, e.dst) for e in g.edges}
    assert ("extends", "Baz") in kinds
    assert ("implements", "Bar") in kinds or ("imports", "Bar") in kinds
    assert ("associates", "Bar") in kinds  # 字段类型


def test_parse_error_skipped(tmp_path):
    p = tmp_path / "src/Broken.java"
    p.parent.mkdir(parents=True)
    p.write_text("class Broken { {")  # 语法错
    g = build_graph(tmp_path)
    assert all(t.name != "Broken" for t in g.types)  # 跳过不崩


def test_interface_not_silently_dropped(tmp_path):
    """Regression: InterfaceDeclaration has no ``implements`` attribute;
    accessing ``decl.implements`` crashed and the file was silently skipped."""
    p = tmp_path / "src/IFetch.java"
    p.parent.mkdir(parents=True)
    p.write_text("package com.x; public interface IFetch { void fetch(); }")
    g = build_graph(tmp_path)
    names = {t.name for t in g.types}
    assert "IFetch" in names
    iface = next(t for t in g.types if t.name == "IFetch")
    assert iface.kind == "interface"


def test_incremental_cache(tmp_path):
    p = tmp_path / "src/A.java"
    p.parent.mkdir(parents=True)
    p.write_text("class A {}")
    cache = tmp_path / "cache.json"
    g1 = build_graph(tmp_path, cache_path=cache)
    assert {t.name for t in g1.types} == {"A"}
    assert cache.exists()
    # 不改文件再跑, 应复用缓存, 结果一致
    g2 = build_graph(tmp_path, cache_path=cache)
    assert {t.name for t in g2.types} == {"A"}
    # 改文件
    p.write_text("class ARenamed {}")
    import os
    import time

    g3 = build_graph(tmp_path, cache_path=cache)
    assert "ARenamed" in {t.name for t in g3.types}
