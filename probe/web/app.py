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

import os
import uuid
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
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
        base_url="",
        api_key="",
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
        """Submit a goal against ``target_repo``; run the loop synchronously."""
        task = Task(goal=req.goal, target_repo=req.target_repo)
        loop = loop_factory(req.target_repo)
        result = loop.run(task)
        task_id = uuid.uuid4().hex
        tasks[task_id] = result
        return TaskCreateResponse(task_id=task_id)

    @app.get("/tasks/{task_id}/report")
    def get_report(task_id: str) -> dict:
        """Return the stored :class:`RunResult` for a task as JSON."""
        result = tasks.get(task_id)
        if result is None:
            raise HTTPException(status_code=404, detail="task not found")
        return result.model_dump(mode="json")

    @app.get("/tasks/{task_id}/stream")
    def get_stream(task_id: str) -> dict:
        """Return the step list for a task.

        SSE is simplified to a JSON list per the task spec (``step.dict()``
        style). Each step is serialized via pydantic for stable shape.
        """
        result = tasks.get(task_id)
        if result is None:
            raise HTTPException(status_code=404, detail="task not found")
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

    return app
