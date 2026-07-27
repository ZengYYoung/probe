from fastapi.testclient import TestClient
from probe.web.app import create_app


def _client():
    return TestClient(create_app(loop_factory=lambda repo: _FakeLoop()))


class _FakeLoop:
    def __init__(self, repo=None):
        pass

    def run(self, task):
        from probe.core.loop import RunResult
        from probe.core.types import Status
        return RunResult(
            status=Status.SUCCESS,
            steps=[],
            final_failure_report=None,
            report_path=None,
        )


def test_demo_endpoint_returns_three_keys():
    c = _client()
    r = c.get("/demo")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"guardrail", "feedback_loop", "no_progress"}


def test_demo_guardrail_blocked():
    c = _client()
    r = c.get("/demo")
    assert "BLOCKED" in r.json()["guardrail"]


def test_demo_no_progress_blocked():
    c = _client()
    r = c.get("/demo")
    assert "BLOCKED_NO_PROGRESS" in r.json()["no_progress"]


def test_demo_feedback_loop_is_list():
    c = _client()
    r = c.get("/demo")
    assert isinstance(r.json()["feedback_loop"], list)
