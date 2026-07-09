from probe.tools.registry import ToolRegistry
from probe.llm.base import Action


def test_dispatch_routes_shell(tmp_repo):
    reg = ToolRegistry.for_repo(tmp_repo)
    r = reg.dispatch(Action(type="shell", command="echo x"))
    assert r.ok and "x" in r.stdout


def test_dispatch_routes_write_read(tmp_repo):
    reg = ToolRegistry.for_repo(tmp_repo)
    assert reg.dispatch(Action(type="write", path="a.txt", params={"content": "hi"})).ok
    assert reg.dispatch(Action(type="read", path="a.txt")).stdout == "hi"


def test_dispatch_routes_list(tmp_repo):
    reg = ToolRegistry.for_repo(tmp_repo)
    reg.dispatch(Action(type="write", path="s/A.java", params={"content": "class A{}"}))
    out = reg.dispatch(Action(type="list", path="s")).stdout
    assert "A.java" in out


def test_unknown_action_blocked(tmp_repo):
    reg = ToolRegistry.for_repo(tmp_repo)
    r = reg.dispatch(Action(type="teleport", params={}))
    assert not r.ok and "unknown" in r.stderr.lower()
