from os import environ
from pathlib import Path

from fastapi.testclient import TestClient
from probe.web.app import create_app
from probe.core.types import Status
from probe.core.loop import RunResult

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEMO_REPO = _REPO_ROOT / "demo-repo"


class _FakeLoop:
    def __init__(self, repo=None):
        pass

    def run(self, task):
        return RunResult(
            status=Status.SUCCESS,
            steps=[],
            final_failure_report=None,
            report_path=None,
        )


def _client():
    return TestClient(create_app(loop_factory=lambda repo: _FakeLoop()))


def test_submit_and_report(tmp_repo):
    c = _client()
    r = c.post("/tasks", json={"goal": "g", "target_repo": str(tmp_repo)})
    assert r.status_code == 200
    tid = r.json()["task_id"]
    rep = c.get(f"/tasks/{tid}/report")
    assert rep.status_code == 200
    assert rep.json()["status"] == "SUCCESS"


def test_stream_returns_steps(tmp_repo):
    c = _client()
    tid = c.post(
        "/tasks", json={"goal": "g", "target_repo": str(tmp_repo)}
    ).json()["task_id"]
    s = c.get(f"/tasks/{tid}/stream")
    assert s.status_code == 200
    # 步骤列表(可能空), 结构是 list
    assert isinstance(s.json().get("steps", []), list)


def test_package_dot(tmp_repo):
    c = _client()
    resp = c.get("/map/package.dot", params={"repo": str(tmp_repo)})
    assert resp.status_code == 200
    assert "digraph" in resp.text


def test_approve(tmp_repo):
    c = _client()
    tid = c.post(
        "/tasks", json={"goal": "g", "target_repo": str(tmp_repo)}
    ).json()["task_id"]
    r = c.post(f"/tasks/{tid}/approve", json={"approve": True})
    assert r.status_code == 200


def test_package_dot_defaults_to_demo_repo(monkeypatch):
    """repo 缺省、env=PROBE_DEMO_REPO 指向内置 demo-repo 时,
    /map/package.dot 返回 digraph 且含 com.demo 包名。"""
    monkeypatch.setenv("PROBE_DEMO_REPO", str(_DEMO_REPO))
    c = _client()
    resp = c.get("/map/package.dot")
    assert resp.status_code == 200
    assert "digraph" in resp.text
    assert "com.demo" in resp.text


def test_package_dot_400_when_no_repo_no_env(monkeypatch):
    """repo 缺省且 env 未设时返回 400。"""
    monkeypatch.delenv("PROBE_DEMO_REPO", raising=False)
    c = _client()
    resp = c.get("/map/package.dot")
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_class_dot_defaults_to_demo_repo(monkeypatch):
    """repo 缺省、env 指向 demo-repo 时 class.dot 含 Bar 类节点。"""
    monkeypatch.setenv("PROBE_DEMO_REPO", str(_DEMO_REPO))
    c = _client()
    resp = c.get("/map/class.dot")
    assert resp.status_code == 200
    assert "digraph" in resp.text
    assert "Bar" in resp.text
