import io
import zipfile

from fastapi.testclient import TestClient
from probe.web.app import create_app
from probe.core.loop import RunResult
from probe.core.types import Status


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


def _make_zip(files: dict[str, str]) -> bytes:
    """构造一个内存 zip，files 为 {filename: content}。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return buf.read()


def test_upload_valid_zip():
    c = _client()
    zip_bytes = _make_zip({
        "pom.xml": "<project></project>",
        "src/Main.java": "class Main {}",
    })
    r = c.post("/repos/upload", files={"file": ("test.zip", zip_bytes, "application/zip")})
    assert r.status_code == 200
    body = r.json()
    assert "repo_id" in body
    assert "path" in body
    assert body["name"] == "test.zip"
    assert body["file_count"] >= 2


def test_upload_non_zip_rejected():
    c = _client()
    r = c.post("/repos/upload", files={"file": ("test.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_upload_bad_magic_rejected():
    c = _client()
    r = c.post("/repos/upload", files={"file": ("fake.zip", b"NOTAZIP" + b"0" * 100, "application/zip")})
    assert r.status_code == 400


def test_upload_zip_slip_rejected():
    c = _client()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil.txt", "malicious")
    r = c.post("/repos/upload", files={"file": ("evil.zip", buf.getvalue(), "application/zip")})
    assert r.status_code == 400
    assert "slip" in r.json()["detail"].lower()


def test_upload_oversized_rejected(monkeypatch):
    from probe.web import app as app_module
    monkeypatch.setattr(app_module, "_MAX_UPLOAD_BYTES", 100)
    c = _client()
    big = b"PK\x03\x04" + b"0" * 200
    r = c.post("/repos/upload", files={"file": ("big.zip", big, "application/zip")})
    assert r.status_code == 413


def test_list_repos():
    c = _client()
    zip_bytes = _make_zip({"pom.xml": "<project/>"})
    c.post("/repos/upload", files={"file": ("a.zip", zip_bytes, "application/zip")})
    r = c.get("/repos")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert "repo_id" in body[0]
    assert "name" in body[0]
    assert "path" not in body[0]  # path 不泄露到列表接口


def test_get_repo():
    c = _client()
    zip_bytes = _make_zip({"pom.xml": "<project/>"})
    up = c.post("/repos/upload", files={"file": ("a.zip", zip_bytes, "application/zip")}).json()
    r = c.get(f"/repos/{up['repo_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["repo_id"] == up["repo_id"]
    assert body["path"] == up["path"]


def test_get_repo_404():
    c = _client()
    r = c.get("/repos/nonexistent")
    assert r.status_code == 404
