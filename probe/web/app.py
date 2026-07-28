"""WebUI for Probe (Task 25).

A thin FastAPI shell around the agent kernel: it submits tasks, streams
steps, renders CodeMap DOT, and exposes approval. It owns no agent logic —
it only consumes :class:`RunResult` / events and delegates to
:mod:`probe.codemap` for graph rendering. The kernel never imports this
module; the WebUI is a pure consumer.

``create_app(loop_factory=None)`` builds the app. ``loop_factory`` lets
tests inject a fake loop; the default wires a real (best-effort)
:class:`AgentLoop` assembly. All task state is held in-process — this
server is a single-node dev/ops surface, not a clustered service.
"""

from __future__ import annotations

import io
import os
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from probe.codemap.builder import build_graph
from probe.codemap.renderer import render_class_dot, render_package_dot
from probe.config import Config
from probe.core.loop import AgentLoop, RunResult, Task
from probe.core.types import Status
from probe.llm.openai_compat import OpenAICompatibleClient
from probe.tools.registry import ToolRegistry
from probe.validators.compile import CompileValidator
from probe.validators.lint import LintValidator
from probe.validators.pipeline import ValidatorPipeline
from probe.validators.test import TestValidator

_WEB_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _WEB_DIR / "static"

# When a /map endpoint is hit without an explicit ``repo`` query param,
# fall back to the built-in demo repo exposed via this env var (set by
# the Dockerfile to ``/app/demo-repo``). This lets the deployed WebUI
# show package/class graphs out of the box.
_DEMO_REPO_ENV = "PROBE_DEMO_REPO"

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB


def _resolve_repo(repo: str | None) -> Path:
    """Pick the repo path: explicit query param, else ``PROBE_DEMO_REPO``.

    Raises :class:`HTTPException` (400) when neither is available so the
    caller can render the documented error shape.
    """
    if repo:
        return Path(repo)
    env = os.environ.get(_DEMO_REPO_ENV)
    if env:
        return Path(env)
    raise HTTPException(
        status_code=400,
        detail="repo param or PROBE_DEMO_REPO env required",
    )


# ---------------------------------------------------------------------------
# Request/response schemas
# ---------------------------------------------------------------------------


class TaskCreateRequest(BaseModel):
    goal: str
    target_repo: str


class TaskCreateResponse(BaseModel):
    task_id: str


class ApproveRequest(BaseModel):
    approve: bool


class ApproveResponse(BaseModel):
    ok: bool


class AnalyzeRequest(BaseModel):
    target_repo: str


# ---------------------------------------------------------------------------
# Default loop factory — real (best-effort) AgentLoop assembly.
# ---------------------------------------------------------------------------


def _default_loop_factory(repo: str) -> AgentLoop:
    """Wire a real AgentLoop from environment/config.

    Best-effort: if an API key is configured, use the OpenAI-compatible
    client; otherwise the loop still constructs but will fail at LLM time.
    Tests never hit this path — they inject a fake.
    """
    config = Config.load(None, {})
    repo_path = Path(repo)
    llm = OpenAICompatibleClient(
        base_url=os.environ.get("LLM_BASE_URL", ""),
        api_key=os.environ.get("LLM_API_KEY", ""),
        model=config.llm.model,
    )
    registry = ToolRegistry.for_repo(repo_path)
    pipeline = ValidatorPipeline(
        CompileValidator(),
        TestValidator(),
        LintValidator(),
        config,
    )
    return AgentLoop(
        llm=llm,
        registry=registry,
        pipeline=pipeline,
        config=config,
        repo=repo_path,
    )


LoopFactory = Callable[[str], Any]


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(loop_factory: LoopFactory | None = None) -> FastAPI:
    """Build the FastAPI app.

    Args:
        loop_factory: callable ``(repo: str) -> loop`` where ``loop.run(task)``
            returns a :class:`RunResult`. ``None`` → default real assembly.
    """
    if loop_factory is None:
        loop_factory = _default_loop_factory

    app = FastAPI(title="Probe WebUI")

    # In-process task + approval stores. Single-node; not clustered.
    tasks: dict[str, RunResult] = {}
    approvals: dict[str, bool] = {}
    repos: dict[str, dict] = {}  # repo_id -> {path, name, file_count}

    # Serve the static SPA (index.html + assets) under /static.
    if _STATIC_DIR.is_dir():
        app.mount(
            "/static",
            StaticFiles(directory=str(_STATIC_DIR)),
            name="static",
        )

    @app.get("/")
    def index() -> Any:
        """Redirect-ish root: serve the SPA from /static/index.html."""
        from fastapi.responses import FileResponse

        index_path = _STATIC_DIR / "index.html"
        if index_path.is_file():
            return FileResponse(str(index_path))
        raise HTTPException(status_code=404, detail="index.html not found")

    @app.post("/tasks", response_model=TaskCreateResponse)
    def create_task(req: TaskCreateRequest) -> TaskCreateResponse:
        """Submit a goal against ``target_repo``; start the loop in a background
        thread and return ``task_id`` immediately so the frontend can poll."""
        task = Task(goal=req.goal, target_repo=req.target_repo)
        task_id = uuid.uuid4().hex
        # Placeholder while the background thread runs.
        tasks[task_id] = {
            "status": "RUNNING",
            "steps": [],
            "final_failure_report": None,
            "report_path": None,
        }

        def _run_in_background() -> None:
            try:
                loop = loop_factory(req.target_repo)
                result = loop.run(task)
                tasks[task_id] = result
            except Exception:
                tasks[task_id] = {
                    "status": "ERROR",
                    "steps": [],
                    "final_failure_report": None,
                    "report_path": None,
                }

        import threading
        threading.Thread(target=_run_in_background, daemon=True).start()
        return TaskCreateResponse(task_id=task_id)

    @app.get("/tasks/{task_id}/report")
    def get_report(task_id: str) -> dict:
        """Return the stored :class:`RunResult` for a task as JSON.

        While the background thread is running, returns a placeholder dict
        with ``status: "RUNNING"``.
        """
        result = tasks.get(task_id)
        if result is None:
            raise HTTPException(status_code=404, detail="task not found")
        if isinstance(result, dict):
            return result
        return result.model_dump(mode="json")

    @app.get("/tasks/{task_id}/stream")
    def get_stream(task_id: str) -> dict:
        """Return the step list for a task.

        While running, returns an empty step list. After completion, returns
        the full step list serialized via pydantic for stable shape.
        """
        result = tasks.get(task_id)
        if result is None:
            raise HTTPException(status_code=404, detail="task not found")
        if isinstance(result, dict):
            return {"steps": []}
        return {"steps": [s.model_dump(mode="json") for s in result.steps]}

    @app.post("/tasks/{task_id}/approve", response_model=ApproveResponse)
    def approve_task(task_id: str, req: ApproveRequest) -> ApproveResponse:
        """Record a human approval decision for a task."""
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="task not found")
        approvals[task_id] = req.approve
        return ApproveResponse(ok=True)

    @app.get("/map/package.dot", response_class=PlainTextResponse)
    def map_package_dot(repo: str | None = None) -> str:
        """Render the package-level DOT for a repo.

        ``repo`` defaults to ``$PROBE_DEMO_REPO`` so a freshly deployed
        WebUI can render the built-in demo repo without configuration.
        """
        graph = build_graph(_resolve_repo(repo))
        return render_package_dot(graph)

    @app.get("/map/class.dot", response_class=PlainTextResponse)
    def map_class_dot(
        repo: str | None = None, package: str | None = None
    ) -> str:
        """Render the class-level DOT for a repo, optionally one package.

        ``repo`` defaults to ``$PROBE_DEMO_REPO`` (see ``map_package_dot``).
        """
        graph = build_graph(_resolve_repo(repo))
        return render_class_dot(graph, package=package)

    @app.get("/demo")
    def run_demo() -> dict:
        """运行 A.6 三个确定性机制演示（mock，无 key 无网络）。

        包装 probe.demo 的三个函数，供 WebUI 机制演示页调用。
        """
        from probe.demo import (
            demo_feedback_loop,
            demo_guardrail,
            demo_no_progress,
        )

        return {
            "guardrail": demo_guardrail(),
            "feedback_loop": demo_feedback_loop(),
            "no_progress": demo_no_progress(),
        }

    @app.post("/repos/upload")
    async def upload_repo(file: UploadFile = File(...)) -> dict:
        """上传 zip 压缩包，安全解压到临时目录，返回 repo_id + path。"""
        content = await file.read()
        if len(content) > _MAX_UPLOAD_BYTES:
            raise HTTPException(413, "file too large (max 50MB)")
        if not (file.filename or "").lower().endswith(".zip"):
            raise HTTPException(400, "only .zip accepted")
        if content[:4] not in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
            raise HTTPException(400, "not a valid zip (bad magic bytes)")
        repo_id = uuid.uuid4().hex
        dest = Path(tempfile.mkdtemp(prefix=f"probe-repo-{repo_id}-"))
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                for info in zf.infolist():
                    target = (dest / info.filename).resolve()
                    if not target.is_relative_to(dest):
                        raise HTTPException(400, f"zip slip detected: {info.filename}")
                zf.extractall(dest)
        except zipfile.BadZipFile:
            raise HTTPException(400, "corrupt zip")
        # Flatten: if the zip has a single top-level directory (common for
        # IDE-exported zips), lift its contents up to dest so pom.xml /
        # build.gradle lands at the repo root where validators expect it.
        top = [p for p in dest.iterdir() if not p.name.startswith(".")]
        if len(top) == 1 and top[0].is_dir():
            inner = top[0]
            for item in inner.iterdir():
                item.rename(dest / item.name)
            inner.rmdir()
        file_count = sum(1 for p in dest.rglob("*") if p.is_file())
        repos[repo_id] = {
            "path": str(dest),
            "name": file.filename,
            "file_count": file_count,
        }
        return {
            "repo_id": repo_id,
            "path": str(dest),
            "name": file.filename,
            "file_count": file_count,
        }

    @app.get("/repos")
    def list_repos() -> list:
        """列出可用的 repo：内置 demo + 仍然存在的上传 repo。

        过滤掉解压目录已被清理的 stale repo，避免前端显示无法访问的条目。
        """
        result: list[dict] = []

        # Always include the built-in demo repo (always available).
        demo_path = os.environ.get(_DEMO_REPO_ENV)
        if demo_path and Path(demo_path).is_dir():
            result.append({
                "repo_id": "demo",
                "name": "demo-repo (内置)",
                "file_count": sum(1 for p in Path(demo_path).rglob("*") if p.is_file()),
                "path": demo_path,
                "is_demo": True,
            })

        # Include uploaded repos whose temp dirs still exist on disk.
        stale_ids: list[str] = []
        for rid, r in repos.items():
            if Path(r["path"]).is_dir():
                result.append({
                    "repo_id": rid,
                    "name": r["name"],
                    "file_count": r["file_count"],
                    "path": r["path"],
                    "is_demo": False,
                })
            else:
                stale_ids.append(rid)

        # Clean up stale entries from the in-memory store.
        for sid in stale_ids:
            del repos[sid]

        return result

    @app.get("/repos/{repo_id}")
    def get_repo(repo_id: str) -> dict:
        """按 repo_id 取 repo 详情（含 path）。"""
        if repo_id == "demo":
            demo_path = os.environ.get(_DEMO_REPO_ENV)
            if not demo_path or not Path(demo_path).is_dir():
                raise HTTPException(404, "demo repo not available")
            return {
                "repo_id": "demo",
                "path": demo_path,
                "name": "demo-repo (内置)",
                "file_count": sum(1 for p in Path(demo_path).rglob("*") if p.is_file()),
            }
        r = repos.get(repo_id)
        if r is None:
            raise HTTPException(404, "repo not found")
        return {
            "repo_id": repo_id,
            "path": r["path"],
            "name": r["name"],
            "file_count": r["file_count"],
        }

    @app.delete("/repos/{repo_id}")
    def delete_repo(repo_id: str) -> dict:
        """删除 repo：清理解压目录并从内存索引移除。内置 demo 不可删。"""
        if repo_id == "demo":
            raise HTTPException(400, "cannot delete built-in demo repo")
        r = repos.get(repo_id)
        if r is None:
            raise HTTPException(404, "repo not found")
        try:
            shutil.rmtree(r["path"], ignore_errors=True)
        except Exception:
            pass
        del repos[repo_id]
        return {"ok": True, "repo_id": repo_id}

    @app.post("/analyze")
    def analyze(req: AnalyzeRequest) -> dict:
        """直接跑 ValidatorPipeline（compile→test→lint），返回 FailureReport。

        不走 LLM / agent loop —— 纯读代码 + 确定性校验，无需 API key。
        """
        repo_path = Path(req.target_repo)
        if not repo_path.is_dir():
            raise HTTPException(400, f"repo not found: {req.target_repo}")

        config = Config.load(None, {})
        pipeline = ValidatorPipeline(
            CompileValidator(),
            TestValidator(),
            LintValidator(),
            config,
        )
        report = pipeline.run(str(repo_path), changed_files=None)
        return report.model_dump(mode="json")

    return app
