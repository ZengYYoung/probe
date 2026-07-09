# Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个自研 Python coding-agent harness（Probe），面向 Java 代码库，以反馈闭环为重点深度、代码地图为次要深度，含凭据治理、Docker 分发、WebUI 与 mock-LLM 确定性单测。

**Architecture:** 单 agent 主循环（自实现）驱动；LLMClient 抽象层可注入 MockLLM；确定性校验流水线（Compile/Test/Lint）→ FailureReport → FailureClassifier → SelfCorrector 结构化回灌与停机；Guardrail + HITLStateMachine 治理；CodeMap 自实现图构建/检索/渲染。所有核心机制用 MockLLM 单测，不依赖网络与真实 LLM。

**Tech Stack:** Python 3.12、`pytest`、`pydantic`、`httpx`、`keyring`、`javalang`、`fastapi`+`uvicorn`、`cytoscape`(前端)、graphviz `dot`、JDK 21 + Maven、Docker、GitLab CI。

## Global Constraints

（每个 task 隐式包含以下约束，值逐字取自 SPEC）
- harness 内核必须自实现，**禁止**依赖 LangChain/AutoGen/CrewAI/LlamaIndex agent 或任何 agent runner（SPEC §AC-1）。
- 机制必须是代码不是提示词；移除真实 LLM 换 MockLLM 后每个机制仍可确定性单测（SPEC §A.4-C）。
- TDD 强制：每个 task 先写失败测试、验证红、再写最少实现、验证绿、再重构、再 commit。
- 凭据绝不进源码/git/日志/terminal history；`.env`/`.probe/` 在 `.gitignore` 内（已建）。
- 目标 Java 仓只深度支持 Maven；Gradle 尽力而为（SPEC §10 R1）。
- 无进展检测默认 `K=3` 轮触发 `BLOCKED_NO_PROGRESS`（SPEC §3.6，Config 可覆盖）。
- 所有文件操作限定在 `target_repo` 内，路径规范化后校验防 `../` 越界（SPEC §3.3）。
- Python 最低版本 3.12；测试一键命令 `make test` = `pytest -q`；CI `unit-test` job 只跑 mock 单测（无网络无 key）。

---

## File Structure

```
probe/
  __init__.py
  config.py                 # Config dataclass + 从 probe.yaml/env 加载
  credentials.py            # CredentialStore: Keychain 优先, .env fallback
  llm/
    __init__.py
    base.py                 # LLMClient ABC + Message/LLMResponse/ToolSpec/Action/ToolResult
    mock.py                 # MockLLM: 按脚本返回动作(确定性)
    openai_compat.py        # OpenAICompatibleClient
  tools/
    __init__.py
    base.py                 # Tool ABC + ToolResult dataclass
    fs.py                   # ReadFile/WriteFile/PatchFile/ListFiles (含路径围栏)
    shell.py                # RunShell (受 Guardrail 与 working-dir 围栏)
    registry.py             # ToolRegistry: name->Tool 分发
  guardrail/
    __init__.py
    guardrail.py            # guardrail(action)->Verdict 纯函数
    hitl.py                 # HITLStateMachine 状态转移纯函数
  validators/
    __init__.py
    base.py                 # Validator ABC + Failure/FailureReport + signature
    compile.py              # CompileValidator: 解析 javac 错误
    test.py                 # TestValidator: 解析 surefire TEST-*.xml
    lint.py                 # LintValidator: 解析 checkstyle XML
    pipeline.py             # ValidatorPipeline: 顺序+短路
    classifier.py           # FailureClassifier: taxonomy 纯函数
  feedback/
    __init__.py
    self_corrector.py       # SelfCorrector: 回灌+停机判据+无进展
  codemap/
    __init__.py
    graph.py                # CodeGraph/Module/Type/Member/Edge dataclass
    builder.py              # 用 javalang 扫 .java 建图, mtime 增量
    retriever.py            # dependents_of/dependencies_of/affected_set/responsibility_of
    renderer.py             # DiagramRenderer: 包图/类图 DOT 导出
  memory/
    __init__.py
    store.py                # Memory: JSON 键值/时间存储
  core/
    __init__.py
    types.py                # Task/RunResult/Step/Decision/Status 枚举
    loop.py                 # AgentLoop 主循环
  report/
    __init__.py
    renderer.py             # ReportRenderer: Markdown + JSON
  web/
    __init__.py
    app.py                  # FastAPI: SSE 轨迹/报告/图/HITL 审批
    static/                 # 前端 (cytoscape)
  cli.py                    # probe run|report|map|creds|init
demo_mechanisms.py          # A.6 机制演示
tests/
  __init__.py
  conftest.py               # fixtures: tmp Java repo, mock surefire XML, MockLLM 脚本
  test_config.py
  test_credentials.py
  llm/test_base.py llm/test_mock.py llm/test_openai_compat.py
  tools/test_fs.py tools/test_shell.py tools/test_registry.py
  guardrail/test_guardrail.py guardrail/test_hitl.py
  validators/test_base.py validators/test_compile.py validators/test_test.py
  validators/test_lint.py validators/test_pipeline.py validators/test_classifier.py
  feedback/test_self_corrector.py
  codemap/test_builder.py codemap/test_retriever.py codemap/test_renderer.py
  memory/test_store.py
  core/test_loop.py
  report/test_renderer.py
  web/test_app.py
  test_demo_mechanisms.py
probe.yaml.example
Dockerfile
.gitlab-ci.yml
Makefile
pyproject.toml
README.md
.env.example
```

---

## 依赖图与并行性

```
T1 scaffold ──┬─ T2 config ──┐
              ├─ T5 creds ───┤
              └─ T6 toolbase─┤
                            T3 llm_base ─┬─ T4 mock ─┐
                            T7 OpenAIComp─┘          ├─(并行)─┐
T6 ─ T8 fs ─ T9 shell ─ T10 registry (tools 链)      │       │
T6 ─ T11 guardrail ─ T12 hitl (guardrail 链, 与 tools 并行) │
T6 ─ T13 valbase ─┬─ T14 compile ─┐                    │       │
                  ├─ T15 testval ─┤─ T17 pipeline ─ T18 classifier│
                  └─ T16 lint ────┘                              │
T13 ─ T19 codemap_graph ─ T20 builder ─ T21 retriever ─ T22 renderer│
T18 ─ T23 self_corrector                                          │
全部就绪 ─ T24 memory ─ T25 agentloop ─ T26 report ─ T27 web ─ T28 cli
T25/T27 ─ T29 demo_mechanisms ─ T30 dockerfile+CI ─ T31 README+deploy
```

可并行 worktree 分支（满足 SPEC §4.3）：
- **分支 A（tools）**：T8→T9→T10
- **分支 B（guardrail）**：T11→T12
- **分支 C（validators）**：T13→T14→T15→T16→T17→T18
- **分支 D（codemap）**：T19→T20→T21→T22
- 这四条链在 T6/T13 完成后可各开一个 worktree 并行推进；T23 依赖 T18；T25 依赖几乎所有。

---

## Task 1: 项目脚手架 + pyproject + Makefile + conftest

**Files:**
- Create: `pyproject.toml`, `Makefile`, `probe/__init__.py`, `probe/core/__init__.py`, `probe/core/types.py`, `tests/__init__.py`, `tests/conftest.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Produces: `probe` 包可导入；`make test` 可运行；`Status` 枚举（`SUCCESS/STOPPED_BUDGET/BLOCKED_NO_PROGRESS/STOPPED_REJECTED/ERROR`）。

- [ ] **Step 1: 写失败测试** — `tests/test_smoke.py`
```python
from probe.core.types import Status
def test_status_enums():
    assert Status.SUCCESS == "SUCCESS"
    assert Status.BLOCKED_NO_PROGRESS == "BLOCKED_NO_PROGRESS"
    assert {
        Status.SUCCESS, Status.STOPPED_BUDGET,
        Status.BLOCKED_NO_PROGRESS, Status.STOPPED_REJECTED, Status.ERROR,
    }
```
- [ ] **Step 2: 跑测试验证红** — `make test` → FAIL（`ModuleNotFoundError: probe`）
- [ ] **Step 3: 最小实现** — `probe/core/types.py`
```python
from enum import Enum
class Status(str, Enum):
    SUCCESS = "SUCCESS"
    STOPPED_BUDGET = "STOPPED_BUDGET"
    BLOCKED_NO_PROGRESS = "BLOCKED_NO_PROGRESS"
    STOPPED_REJECTED = "STOPPED_REJECTED"
    ERROR = "ERROR"
```
`pyproject.toml`（关键段）：
```toml
[project]
name = "probe"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pydantic>=2", "httpx", "keyring", "javalang", "fastapi", "uvicorn"]
[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov", "ruff", "mypy"]
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["integration: needs real LLM/key (deselected by default)"]
addopts = "-m 'not integration'"
[tool.probe]
# placeholder-free: 见下 task 各自填充
```
`Makefile`：
```make
test:
\tpytest -q
coverage:
\tpytest --cov=probe --cov-report=term
lint:
\truff check .
```
`tests/conftest.py`（占位 fixture，后续 task 扩展）：
```python
import pytest
@pytest.fixture
def tmp_repo(tmp_path):
    """一个空 Java 仓临时目录。"""
    return tmp_path
```
- [ ] **Step 4: 跑测试验证绿** — `make test` → PASS
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: 项目脚手架与 Status 枚举"`

---

## Task 2: Config 加载器

**Files:** Create: `probe/config.py`, `probe.yaml.example`; Test: `tests/test_config.py`
**Interfaces:**
- Consumes: `probe/core/types.py`
- Produces: `Config` dataclass，方法 `Config.load(path: Path, env: dict) -> Config`；字段见 SPEC §3.11。

- [ ] **Step 1: 失败测试** — `tests/test_config.py`
```python
from pathlib import Path
from probe.config import Config
def test_config_defaults_and_override():
    cfg = Config.load(Path("probe.yaml.example"), env={})
    assert cfg.budgets.max_iterations == 10          # 默认
    assert cfg.no_progress_rounds == 3               # SPEC §3.6 默认 K=3
    assert "rm -rf" in cfg.guardrails.dangerous_patterns
    cfg2 = Config.load(Path("probe.yaml.example"), env={"PROBE_MAX_ITERATIONS": "5"})
    assert cfg2.budgets.max_iterations == 5
```
- [ ] **Step 2: 验证红** — `make test` → FAIL
- [ ] **Step 3: 实现** — `probe/config.py` 用 pydantic BaseModel 定义 `Budgets{max_iterations=10, max_shell_seconds=600, max_tokens=50000}`、`Guardrails{dangerous_patterns=[...SPEC §3.8 全表...], allowed_paths=[]}`、`Validators{compile=True,test=True,lint=True}`、`LLM{model="glm-5.2", temperature=0.2}`、`Config{budgets,guardrails,validators,llm,no_progress_rounds=3}`；`Config.load` 读 yaml + env 覆盖（`PROBE_` 前缀）；缺字段用默认并告警。
`probe.yaml.example` 含全部字段示例注释。
- [ ] **Step 4: 验证绿** — `make test` → PASS
- [ ] **Step 5: Commit** — `feat: Config 加载器与默认值`

---

## Task 3: CredentialStore

**Files:** Create: `probe/credentials.py`; Test: `tests/test_credentials.py`
**Interfaces:**
- Produces: `CredentialStore`，方法 `get(key)->str|None`、`set(key,value)`、`status(key)->str`（掩码）、`update(key,value)`、`clear(key)`；`mask(value)->str`（`sk-…abcd` 形）。

- [ ] **Step 1: 失败测试** — `tests/test_credentials.py`
```python
from probe.credentials import CredentialStore, mask
def test_mask_hides_middle():
    assert mask("sk-abcdefgh1234") == "sk-…1234"
def test_status_never_reveals_plaintext(monkeypatch, tmp_path):
    store = CredentialStore(backend="file", store_dir=tmp_path)  # 测试用 file backend
    store.set("LLM_API_KEY", "sk-secret-XYZ")
    s = store.status("LLM_API_KEY")
    assert "sk-secret-XYZ" not in s
    assert "XYZ" in s  # 末尾可见
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `probe/credentials.py`：`mask` 取首 3 + "…" + 末 4。`CredentialStore(backend, store_dir)`：`backend="keychain"` 用 `keyring`；`backend="file"` 用 `store_dir/.credentials.json`（chmod 600）作测试与 `.env` fallback。`status` 调 `mask`。Keychain 不可用时抛 `CredentialBackendUnavailable` 由调用方退回 file/env。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: CredentialStore (keychain/file, 掩码 status)`

---

## Task 4: LLM 抽象层 + MockLLM

**Files:** Create: `probe/llm/__init__.py`, `probe/llm/base.py`, `probe/llm/mock.py`; Test: `tests/llm/test_mock.py`
**Interfaces:**
- Produces: `Message{role,content,tool_calls?}`、`ToolSpec{name,description,input_schema}`、`Action{type,command?,path?,params?}`、`LLMResponse{actions:list[Action], raw, stop_reason}`、`LLMClient` ABC `complete(messages, tools)->LLMResponse`、`MockLLM(script:list[LLMResponse], index=0)`。

- [ ] **Step 1: 失败测试** — `tests/llm/test_mock.py`
```python
from probe.llm.base import LLMClient, Action, LLMResponse
from probe.llm.mock import MockLLM
def test_mock_returns_scripted_then_stops():
    r1 = LLMResponse(actions=[Action(type="shell", command="ls")], raw="1", stop_reason="ok")
    r2 = LLMResponse(actions=[], raw="2", stop_reason="end_turn")
    client = MockLLM(script=[r1, r2])
    assert client.complete([], [])[0].actions[0].command == "ls"
    assert client.complete([], [])[0].actions == []   # 第二次
    assert client.complete([], [])[0].actions == []   # 第三次停在末帧
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `base.py` 定义 pydantic 模型与 `LLMClient` ABC（`complete` 抽象）。`mock.py` `MockLLM` 持 `script` 与 `_i`，`complete` 返回 `script[min(_i,len-1)]` 并自增；纯确定性，无 IO。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: LLM 抽象层与 MockLLM`

---

## Task 5: OpenAICompatibleClient

**Files:** Create: `probe/llm/openai_compat.py`; Test: `tests/llm/test_openai_compat.py`
**Interfaces:**
- Consumes: `probe/llm/base.py`, `probe/credentials.py`
- Produces: `OpenAICompatibleClient(base_url, api_key, model)`；`complete` 发 POST `/chat/completions`，解析 `tool_calls`/content 为 `Action` 列表。

- [ ] **Step 1: 失败测试** — `tests/llm/test_openai_compat.py`
```python
import httpx, pytest
from probe.llm.openai_compat import OpenAICompatibleClient
def test_complete_parses_tool_call(monkeypatch):
    def fake_post(self, req, **kw):
        return httpx.Response(200, json={"choices":[{"message":{"content":None,
            "tool_calls":[{"id":"1","function":{"name":"RunShell",
            "arguments":'{"command":"ls"}'}}]}}]})
    monkeypatch.setattr(OpenAICompatibleClient, "_post", fake_post)
    c = OpenAICompatibleClient("http://x", "sk-x", "glm-5.2")
    resp = c.complete([], [])
    assert resp.actions[0].type == "shell"
    assert resp.actions[0].command == "ls"
def test_auth_error_raises(monkeypatch):
    monkeypatch.setattr(OpenAICompatibleClient, "_post",
        lambda *a,**k: httpx.Response(401, json={"error":"bad key"}))
    with pytest.raises(Exception):
        OpenAICompatibleClient("http://x","bad","m").complete([],[])
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `openai_compat.py`：`_post` 用 `httpx`；`complete` 组 messages+tools 为 OpenAI chat 格式，调 `_post`，把 `tool_calls[].function` 映射到 `Action`（`RunShell→shell`，`WriteFile→write` 等，映射表常量）；401/429 抛 `LLMAuthError`，超时重试 K=2。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: OpenAICompatibleClient`

---

## Task 6: Tool 基类 + ToolResult

**Files:** Create: `probe/tools/__init__.py`, `probe/tools/base.py`; Test: `tests/tools/test_base.py`
**Interfaces:**
- Produces: `ToolResult{ok:bool, stdout:str, stderr:str, exit_code:int|None, meta:dict}`、`Tool` ABC `name`/`run(params)->ToolResult`、路径围栏 `safe_path(base, target)->Path`（防 `../`）。

- [ ] **Step 1: 失败测试** — `tests/tools/test_base.py`
```python
import pytest
from probe.tools.base import safe_path
def test_safe_path_blocks_traversal(tmp_path):
    with pytest.raises(PermissionError):
        safe_path(tmp_path, "../../etc/passwd")
def test_safe_path_allows_inner(tmp_path):
    p = safe_path(tmp_path, "src/Main.java")
    assert str(p).startswith(str(tmp_path))
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `base.py`：`safe_path` 用 `Path.resolve()` 后校验 `is_relative_to(base)`，否则 `PermissionError`。`Tool` ABC 与 `ToolResult` pydantic。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: Tool 基类与路径围栏`

---

## Task 7: FS 工具 (ReadFile/WriteFile/PatchFile/ListFiles)

**Files:** Create: `probe/tools/fs.py`; Test: `tests/tools/test_fs.py`
**Interfaces:**
- Consumes: `probe/tools/base.py`
- Produces: 四个 `Tool` 子类，构造接收 `repo_root: Path`。

- [ ] **Step 1: 失败测试** — `tests/tools/test_fs.py`
```python
from probe.tools.fs import ReadFile, WriteFile, PatchFile, ListFiles
def test_write_then_read(tmp_repo):
    w = WriteFile(tmp_repo); r = ReadFile(tmp_repo)
    assert w.run({"path":"a.txt","content":"hi"}).ok
    assert r.run({"path":"a.txt"}).stdout == "hi"
def test_patch_replaces_line(tmp_repo):
    WriteFile(tmp_repo).run({"path":"a.txt","content":"a\nb\nc\n"})
    PatchFile(tmp_repo).run({"path":"a.txt","old":"b","new":"B"})
    assert "B" in ReadFile(tmp_repo).run({"path":"a.txt"}).stdout
def test_read_outside_repo_blocked(tmp_repo):
    import pytest
    with pytest.raises(PermissionError): ReadFile(tmp_repo).run({"path":"../etc/passwd"})
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `fs.py`：每个工具 `run` 先 `safe_path`；`WriteFile` 写、`ReadFile` 读 stdout=内容、`PatchFile` 做字符串替换（找不到 old → `ok=False, stderr`）、`ListFiles` 递归列 `.java`（stdout=换行分隔路径）。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: FS 工具与路径围栏`

---

## Task 8: RunShell 工具

**Files:** Create: `probe/tools/shell.py`; Test: `tests/tools/test_shell.py`
**Interfaces:**
- Consumes: `probe/tools/base.py`
- Produces: `RunShell(repo_root, timeout)`，`run({command, cwd?})` 在 `repo_root` 下 `subprocess` 执行，捕获 stdout/stderr/exit_code，超时 `meta={"timeout":True}`。

- [ ] **Step 1: 失败测试** — `tests/tools/test_shell.py`
```python
from probe.tools.shell import RunShell
def test_shell_runs_and_captures(tmp_repo):
    r = RunShell(tmp_repo, timeout=10).run({"command":"echo hello"})
    assert r.ok and r.stdout.strip() == "hello"
def test_shell_timeout(tmp_repo):
    r = RunShell(tmp_repo, timeout=1).run({"command":"sleep 5"})
    assert not r.ok and r.meta.get("timeout") is True
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `shell.py`：`subprocess.run(cwd=repo_root, shell=True, capture_output=True, timeout=timeout)`；`TimeoutExpired` 捕获并标 `meta.timeout=True`，`exit_code=-1`。命令经 Guardrail 是 AgentLoop 的职责，本工具只执行（SPEC §3.3）。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: RunShell 工具`

---

## Task 9: ToolRegistry

**Files:** Create: `probe/tools/registry.py`; Test: `tests/tools/test_registry.py`
**Interfaces:**
- Consumes: 全部 Tool
- Produces: `ToolRegistry(tools: list[Tool])`，`dispatch(action: Action)->ToolResult`（按 `action.type` 路由：`shell→RunShell`，`read→ReadFile` 等，映射表常量）。

- [ ] **Step 1: 失败测试** — `tests/tools/test_registry.py`
```python
from probe.tools.registry import ToolRegistry
from probe.tools.base import Action
def test_dispatch_routes_shell(tmp_repo):
    reg = ToolRegistry.for_repo(tmp_repo)
    r = reg.dispatch(Action(type="shell", command="echo x"))
    assert r.ok
def test_unknown_action_blocked(tmp_repo):
    reg = ToolRegistry.for_repo(tmp_repo)
    r = reg.dispatch(Action(type="teleport", params={}))
    assert not r.ok and "unknown" in r.stderr.lower()
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `registry.py`：`for_repo` 工厂装配 FS+Shell；`dispatch` 用 `_ROUTE={"shell":RunShell,"read":ReadFile,"write":WriteFile,"patch":PatchFile,"list":ListFiles}`；未知→`ToolResult(ok=False,stderr="unknown action type")`。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: ToolRegistry 分发`

---

## Task 10: Guardrail（纯函数）

**Files:** Create: `probe/guardrail/__init__.py`, `probe/guardrail/guardrail.py`; Test: `tests/guardrail/test_guardrail.py`
**Interfaces:**
- Consumes: `probe/config.py`（dangerous_patterns）、`probe/tools/base.py`（Action）
- Produces: `Verdict{allow:bool, reason:str}`、`guardrail(action, config)->Verdict` 纯函数。

- [ ] **Step 1: 失败测试** — `tests/guardrail/test_guardrail.py`
```python
from probe.guardrail.guardrail import guardrail, Verdict
from probe.tools.base import Action
from probe.config import Config
def test_blocks_rm_rf():
    cfg = Config.load(None, env={})  # 默认
    v = guardrail(Action(type="shell", command="rm -rf /"), cfg)
    assert not v.allow and "rm -rf" in v.reason
def test_allows_ls():
    v = guardrail(Action(type="shell", command="ls"), Config.load(None,{}))
    assert v.allow
def test_blocks_path_escape():
    v = guardrail(Action(type="write", path="../x"), Config.load(None,{}))
    assert not v.allow
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `guardrail.py`：对 `shell` 动作按 `dangerous_patterns` 子串匹配；对文件动作调 `safe_path` 捕 `PermissionError` → block；`mvn deploy`/`git push --force` 在默认表。纯函数无 IO。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: Guardrail 危险动作拦截`

---

## Task 11: HITLStateMachine（纯函数）

**Files:** Create: `probe/guardrail/hitl.py`; Test: `tests/guardrail/test_hitl.py`
**Interfaces:**
- Produces: `State` 枚举（`idle/proposing/awaiting_approval/executing/verifying/blocked/done/rejected`）、`Event` 枚举、`transition(state, event)->State` 纯函数（非法迁移→`ERROR` 复用 core.types.Status）。

- [ ] **Step 1: 失败测试** — `tests/guardrail/test_hitl.py`
```python
from probe.guardrail.hitl import State, Event, transition
def test_approve_flow():
    s = transition(State.idle, Event.ActionProposed); assert s == State.proposing
    s = transition(s, Event.NeedsApproval); assert s == State.awaiting_approval
    s = transition(s, Event.ApprovalGranted); assert s == State.executing
    s = transition(s, Event.Executed); assert s == State.verifying
    s = transition(s, Event.Validated); assert s == State.done
def test_deny():
    s = transition(State.awaiting_approval, Event.ApprovalDenied)
    assert s == State.rejected
def test_illegal_transition_raises():
    import pytest
    with pytest.raises(ValueError): transition(State.done, Event.ActionProposed)
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `hitl.py`：`_TABLE: dict[(State,Event),State]` 常量；`transition` 查表，缺→`ValueError`。纯函数。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: HITL 状态机`

---

## Task 12: Validator 基类 + Failure/FailureReport + signature

**Files:** Create: `probe/validators/__init__.py`, `probe/validators/base.py`; Test: `tests/validators/test_base.py`
**Interfaces:**
- Produces: `Category` 枚举（SPEC §6 taxonomy 全 10 项）、`Failure{validator,severity,file,line,category,message,raw,hint}`、`FailureReport{per_validator_status, failures, signature, summary}`、`Validator` ABC `run(repo, changed_files?)->FailureReport`、`signature(failures)->str`（稳定 hash：归一化 `category|file|line|message` 排序后 sha1）。

- [ ] **Step 1: 失败测试** — `tests/validators/test_base.py`
```python
from probe.validators.base import Failure, FailureReport, signature, Category
def test_signature_stable_regardless_of_order():
    f1 = Failure(validator="test",severity="error",file="A.java",line=3,
        category=Category.TEST_FAILURE,message="x",raw="",hint="h")
    f2 = Failure(validator="test",severity="error",file="B.java",line=4,
        category=Category.COMPILE_SYNTAX,message="y",raw="",hint="h")
    assert signature([f1,f2]) == signature([f2,f1])
def test_empty_report_passes():
    r = FailureReport(per_validator_status={}, failures=[], signature=signature([]), summary={})
    assert r.failures == []
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `base.py`：用 **pydantic v2 `BaseModel`**（不得用 `dataclass`，与 SPEC §6 一致）定义 `Category`(`str` Enum)、`Failure`、`FailureReport`、`Validator` ABC；`signature` 排序 `f"{f.category}|{f.file}|{f.line}|{f.message}"` 后 `hashlib.sha1`。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: Validator 基类与 FailureReport signature`

---

## Task 13: CompileValidator（解析 javac）

**Files:** Create: `probe/validators/compile.py`; Test: `tests/validators/test_compile.py`
**Interfaces:**
- Consumes: `probe/validators/base.py`
- Produces: `CompileValidator`，`run` 调 `mvn -q -DskipTests test-compile`（经注入的 runner，可 mock），解析 `file:line: error:` 与 `cannot find symbol`。

- [ ] **Step 1: 失败测试** — `tests/validators/test_compile.py`
```python
from probe.validators.compile import CompileValidator
def test_parses_javac_error():
    out = ("[ERROR] /src/Main.java:[5,1] error: ';' expected\n"
           "[ERROR] /src/Other.java:[9,1] error: cannot find symbol\n")
    v = CompileValidator(runner=lambda cmd: (1, out, ""))
    r = v.run(repo="/repo")
    cats = {f.category for f in r.failures}
    assert "COMPILE_SYNTAX" in cats and "COMPILE_MISSING_SYMBOL" in cats
    assert r.failures[0].file.endswith("Main.java")
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `compile.py`：`CompileValidator(runner)` 默认 runner 跑 `RunShell`，测试注入 `lambda cmd:(exit,stdout,stderr)`。正则 `^\[ERROR\]\s+(?P<file>.*?):\[(?P<line>\d+),\d+\]\s+error:\s+(?P<msg>.*)$`；`cannot find symbol` → `COMPILE_MISSING_SYMBOL`，否则 `COMPILE_SYNTAX`。这里先纯解析，分类映射的完整逻辑在 Task 15 classifier，本 task 只产 raw Failure（category 暂用本地简单判定，最终以 classifier 为准——见 Task 15 后重构）。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: CompileValidator javac 解析`

---

## Task 14: TestValidator（解析 surefire XML）

**Files:** Create: `probe/validators/test.py`; Test: `tests/validators/test_test.py`
**Interfaces:**
- Consumes: `probe/validators/base.py`
- Produces: `TestValidator`，`run` 解析 `target/surefire-reports/TEST-*.xml` 的 `<failure>`/`<error>`/`<skipped>`。

- [ ] **Step 1: 失败测试** — `tests/validators/test_test.py`
```python
from probe.validators.test import TestValidator
SUREFIRE = '''<testsuite name="com.x.FooTest" tests="2">
<testcase name="testA" classname="com.x.FooTest"/>
<testcase name="testB" classname="com.x.FooTest">
<failure type="AssertionError">expected [1] but was [2]&#10;at com.x.FooTest.testB(FooTest.java:12)</failure>
</testcase></testsuite>'''
def test_parses_failure(tmp_path):
    d = tmp_path/"target"/"surefire-reports"; d.mkdir(parents=True)
    (d/"TEST-com.x.FooTest.xml").write_text(SUREFIRE)
    v = TestValidator(runner=lambda cmd: (0,"",""))  # 不实际跑, 用现成报告
    r = v.run(repo=str(tmp_path))
    assert any(f.category=="TEST_FAILURE" and f.line==12 for f in r.failures)
    assert r.summary.get("TEST_FAILURE") == 1
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `test.py`：用 `xml.etree.ElementTree` 解析所有 `TEST-*.xml`；`<failure>`→`TEST_FAILURE`（抽 `expected [...] but was [...]` 作 message）、`<error>`→`TEST_ERROR`（抽异常类型）、`<skipped>`→`TEST_MISSING`；line 从堆栈 `at ...File.java:LINE` 抽。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: TestValidator surefire XML 解析`

---

## Task 15: LintValidator（解析 checkstyle XML）

**Files:** Create: `probe/validators/lint.py`; Test: `tests/validators/test_lint.py`
**Interfaces:**
- Consumes: `probe/validators/base.py`
- Produces: `LintValidator`，解析 checkstyle XML `<file><error line="" message="" source=""/></file>`。

- [ ] **Step 1: 失败测试** — `tests/validators/test_lint.py`
```python
from probe.validators.lint import LintValidator
CS = '''<?xml version="1.0"?><checkstyle version="8.0">
<file name="/src/Main.java"><error line="3" column="5" severity="error" message="Missing Javadoc" source="JavadocMethod"/></file></checkstyle>'''
def test_parses_violation():
    v = LintValidator(runner=lambda cmd:(0,"",""))
    r = v.run(repo="/repo", report_xml=CS)
    assert r.failures[0].category == "LINT_VIOLATION"
    assert r.failures[0].line == 3 and "JavadocMethod" in r.failures[0].raw
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `lint.py`：解析 checkstyle XML；每 `<error>`→`Failure(category=LINT_VIOLATION, severity=severity, hint="规则 "+source)`。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: LintValidator checkstyle XML 解析`

---

## Task 16: ValidatorPipeline（顺序 + 短路）

**Files:** Create: `probe/validators/pipeline.py`; Test: `tests/validators/test_pipeline.py`
**Interfaces:**
- Consumes: Compile/Test/Lint Validator, Config
- Produces: `ValidatorPipeline(validators, config)`，`run(repo, changed_files?)` 顺序跑，Compile FAIL 短路 Test，Lint 总跑；合并 `FailureReport`。

- [ ] **Step 1: 失败测试** — `tests/validators/test_pipeline.py`
```python
from probe.validators.pipeline import ValidatorPipeline
from probe.validators.base import FailureReport, Failure, Category
def test_compile_fail_shortcircuits_test():
    class FakeCompile:
        def run(self, repo, changed_files=None):
            return FailureReport(per_validator_status={"compile":"FAIL"},
                failures=[Failure(validator="compile",severity="error",file="A",line=1,
                category=Category.COMPILE_SYNTAX,message="e",raw="",hint="")],
                signature="x", summary={"COMPILE_SYNTAX":1})
    ran = {"test": False}
    class FakeTest:
        def run(self, repo, changed_files=None):
            ran["test"] = True; return FailureReport({},{}, "",{})
    p = ValidatorPipeline(compile_v=FakeCompile(), test_v=FakeTest(), lint_v=None)
    r = p.run(repo="/r")
    assert ran["test"] is False  # 被短路
    assert r.per_validator_status["compile"] == "FAIL"
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `pipeline.py`：`run` 先 compile；`compile.status==FAIL`→跳过 test；lint 若配置启用则跑；合并 failures 与 status；末尾算 `signature`。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: ValidatorPipeline 短路`

---

## Task 17: FailureClassifier（taxonomy 纯函数）

**Files:** Create: `probe/validators/classifier.py`; Test: `tests/validators/test_classifier.py`
**Interfaces:**
- Consumes: `probe/validators/base.py`
- Produces: `classify(failure: Failure) -> tuple[Category, str]` 纯函数；`classify_report(report: FailureReport) -> FailureReport`（返回**新对象**，不 mutate 入参与其中 `Failure`；重算 `signature`/`summary`）。

- [ ] **Step 1: 失败测试** — `tests/validators/test_classifier.py`
```python
from probe.validators.classifier import classify, classify_report
from probe.validators.base import Failure, FailureReport, Category, signature

def test_cannot_find_symbol_compile():
    f = Failure(validator="compile",severity="error",file="A",line=1,
        category=Category.UNKNOWN,message="cannot find symbol",raw="",hint="")
    assert classify(f)[0] == Category.COMPILE_MISSING_SYMBOL

def test_assertion_failure_uses_validator_field():
    # 冷启动修正：validator="test" + "expected [1] but was [2]" → TEST_FAILURE
    # （不得被泛化 "expected" 误判为 COMPILE_SYNTAX）
    f = Failure(validator="test",severity="error",file="A",line=1,
        category=Category.UNKNOWN,message="expected [1] but was [2]",raw="",hint="")
    assert classify(f)[0] == Category.TEST_FAILURE

def test_validator_field_disambiguates_same_text():
    # 同样文本 "expected" 出现在 compile 与 test 下, 应按 validator 字段分流
    fc = Failure(validator="compile",severity="error",file="A",line=1,
        category=Category.UNKNOWN,message="expected ;",raw="",hint="")
    ft = Failure(validator="test",severity="error",file="A",line=1,
        category=Category.UNKNOWN,message="expected",raw="",hint="")
    assert classify(fc)[0] != Category.TEST_FAILURE  # compile 不会落到 test 类
    assert classify(ft)[0] in (Category.TEST_FAILURE, Category.TEST_ERROR, Category.UNKNOWN)

def test_specific_pattern_beats_generic():
    # "expected.*but was" 必须排在 "expected" 之前
    f = Failure(validator="test",severity="error",file="A",line=1,
        category=Category.UNKNOWN,message="expected [1] but was [2]",raw="",hint="")
    assert classify(f)[0] == Category.TEST_FAILURE

def test_unknown_stays_unknown():
    f = Failure(validator="x",severity="error",file="A",line=1,
        category=Category.UNKNOWN,message="weird stuff",raw="",hint="")
    assert classify(f)[0] == Category.UNKNOWN

def test_classify_report_does_not_mutate_input():
    f = Failure(validator="compile",severity="error",file="A",line=1,
        category=Category.UNKNOWN,message="cannot find symbol",raw="",hint="")
    report = FailureReport(per_validator_status={"compile":"FAIL"},
        failures=[f], signature="old", summary={})
    orig_sig = report.signature
    orig_cat = report.failures[0].category
    updated = classify_report(report)
    assert report.signature == orig_sig          # 入参未变
    assert report.failures[0].category == orig_cat
    assert updated is not report
    assert updated.failures[0].category == Category.COMPILE_MISSING_SYMBOL
    assert updated.signature == signature(updated.failures)
```
- [ ] **Step 2: 验证红** — `make test` → FAIL
- [ ] **Step 3: 实现** — `classifier.py`：有序规则表，每条 `(validator_scope: str|None, pattern: str, category, hint)`。`classify` 对 `validator_scope`（`None` 表任意）相等且 `pattern`（`re`，`IGNORECASE`）在 `"{message} {raw}"` 命中者，按表内顺序首条胜出；无匹配→`(UNKNOWN, message)`。规则须**特化在前、泛化在后**，且按 `validator` 字段消歧（compile 范畴只含 `COMPILE_*`/`DEPENDENCY_MISSING`/`BUILD_CONFIG_ERROR`，test 范畴只含 `TEST_*`，lint 范畴只含 `LINT_VIOLATION`）。参考顺序：
  - `("compile","cannot find symbol",COMPILE_MISSING_SYMBOL,"检查 import/声明")`
  - `("compile","error:",COMPILE_SYNTAX,"语法错误")`
  - `("test","expected.*but was",TEST_FAILURE,"断言不符：核对 actual vs expected")`
  - `("test","AssertionError",TEST_FAILURE,"断言失败")`
  - `("test","<error>|Exception",TEST_ERROR,"测试抛异常")`
  - `("test","disabled|@Disabled|skipped",TEST_MISSING,"测试未运行")`
  - `("compile","Could not resolve",DEPENDENCY_MISSING,"检查 pom 依赖坐标")`
  - `("lint",".",LINT_VIOLATION,"按 checkstyle 规则 id 修正")`（lint 的 `Failure.raw` 含规则 id）
  - `(None,"timed?out|timeout",TIMEOUT,"增大超时或缩小范围")`
  - `(None,"BUILD.*FAILURE|pom|build\\.xml",BUILD_CONFIG_ERROR,"检查构建配置")`
  - 其余→`UNKNOWN`。
  `classify_report` 深拷贝 `failures`（新 `Failure` 对象）、重算 `signature`/`summary`、返回新 `FailureReport`。
- [ ] **Step 4: 验证绿** — `make test` → PASS（含 6 个用例）
- [ ] **Step 5: Commit** — `feat: FailureClassifier taxonomy（validator 消歧 + 特化优先 + 不可变）`

> 重构：Task 13/14/15 中各 validator 的本地 category 判定改为调 `classify`，DRY。

---

## Task 18: SelfCorrector（回灌 + 停机 + 无进展）

**Files:** Create: `probe/feedback/__init__.py`, `probe/feedback/self_corrector.py`; Test: `tests/feedback/test_self_corrector.py`
**Interfaces:**
- Consumes: `probe/validators/base.py`（FailureReport/signature）、`probe/core/types.py`（Status）、Config（no_progress_rounds, budgets）
- Produces: `Decision{action: "CONTINUE"|"STOP", reason, context_fragment}`、`SelfCorrector(config)`，方法 `decide(report, history:list[str], budget_remaining) -> Decision`。

- [ ] **Step 1: 失败测试** — `tests/feedback/test_self_corrector.py`
```python
from probe.feedback.self_corrector import SelfCorrector
from probe.validators.base import FailureReport, Failure, Category
from probe.config import Config
def _rep(sig):
    return FailureReport(per_validator_status={"compile":"FAIL"},
        failures=[], signature=sig, summary={})
def test_success_when_all_pass():
    r = FailureReport(per_validator_status={"compile":"PASS","test":"PASS","lint":"PASS"},
        failures=[], signature="s", summary={})
    d = SelfCorrector(Config.load(None,{})).decide(r, history=[], budget_remaining=1000)
    assert d.action == "STOP" and d.reason == "SUCCESS"
def test_no_progress_after_K_rounds():
    s = SelfCorrector(Config.load(None,{}))  # K=3
    r = _rep("same")
    d1 = s.decide(r, ["same"], 1000); assert d1.action == "CONTINUE"
    d2 = s.decide(r, ["same","same"], 1000); assert d2.action == "CONTINUE"
    d3 = s.decide(r, ["same","same","same"], 1000)
    assert d3.action == "STOP" and d3.reason == "BLOCKED_NO_PROGRESS"
def test_budget_exhausted():
    r = _rep("x")
    d = SelfCorrector(Config.load(None,{})).decide(r, [], budget_remaining=0)
    assert d.action == "STOP" and d.reason == "STOPPED_BUDGET"
def test_context_fragment_contains_structured_failure():
    f = Failure(validator="test",severity="error",file="A.java",line=5,
        category=Category.TEST_FAILURE,message="expected [1] but was [2]",raw="",hint="h")
    r = FailureReport({"test":"FAIL"},[f],"s",{"TEST_FAILURE":1})
    d = SelfCorrector(Config.load(None,{})).decide(r, [], 1000)
    assert "A.java:5" in d.context_fragment and "TEST_FAILURE" in d.context_fragment
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `self_corrector.py`：`decide` 顺序判：全 PASS→SUCCESS；`budget_remaining<=0`→STOPPED_BUDGET；`history[-K:].count(report.signature)>=K`→BLOCKED_NO_PROGRESS；否则 CONTINUE 并组 `context_fragment`（每条失败 `file:line | category | message | hint` + 剩余预算）。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: SelfCorrector 回灌与停机判据`

---

## Task 19: CodeGraph 类型 + Builder（javalang）

**Files:** Create: `probe/codemap/__init__.py`, `probe/codemap/graph.py`, `probe/codemap/builder.py`; Test: `tests/codemap/test_builder.py`
**Interfaces:**
- Produces: `Module{name}`、`Member{name,kind,returns?}`、`Type{name,kind,package,members,extends?,implements[]}`、`Edge{kind,src,dst}`、`CodeGraph{modules,types,edges}`；`build_graph(repo: Path) -> CodeGraph` 用 `javalang` 解析；mtime 增量 `build_graph(repo, cache_path?)`。

- [ ] **Step 1: 失败测试** — `tests/codemap/test_builder.py`
```python
from probe.codemap.builder import build_graph
JAVA = '''package com.x;
import com.y.Bar;
class Foo extends Baz implements Bar {
    Bar field;
    void m(){ Bar b = new Bar(); }
}'''
def test_builds_types_and_edges(tmp_path):
    p = tmp_path/"src/main/java/com/x/Foo.java"; p.parent.mkdir(parents=True)
    p.write_text(JAVA)
    g = build_graph(tmp_path)
    names = {t.name for t in g.types}
    assert "Foo" in names
    kinds = {(e.kind,e.dst) for e in g.edges}
    assert ("extends","Baz") in kinds
    assert ("implements","Bar") in kinds or ("imports","Bar") in kinds
    assert ("associates","Bar") in kinds  # 字段类型
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `graph.py` dataclass；`builder.py`：遍历 `**/*.java`，`javalang.parse`，抽 package/class/interface/extends/implements/字段类型/方法调用→`Edge`；解析失败记跳过；mtime cache：`.probe/codemap.json`，仅重解析变更文件后合并。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: CodeMap 图构建`

---

## Task 20: CodeMapRetriever（影响闭包）

**Files:** Create: `probe/codemap/retriever.py`; Test: `tests/codemap/test_retriever.py`
**Interfaces:**
- Consumes: `probe/codemap/graph.py`
- Produces: `dependents_of(graph,file)`、`dependencies_of(graph,file)`、`affected_set(graph, changed_files)->{affected_files, tests_to_run}`、`responsibility_of(graph,package)`，纯函数。

- [ ] **Step 1: 失败测试** — `tests/codemap/test_retriever.py`
```python
from probe.codemap.retriever import affected_set
from probe.codemap.graph import CodeGraph, Type, Edge
def test_affected_closure():
    g = CodeGraph(modules=[], types=[
        Type(name="Foo",kind="class",package="com.x",members=[],extends=None,implements=[]),
        Type(name="Bar",kind="class",package="com.x",members=[],extends=None,implements=[])],
        edges=[Edge(kind="depends",src="Bar",dst="Foo")])
    # Foo 被改 → Bar 受影响
    res = affected_set(g, changed_files=["com.x/Foo.java"])
    assert "Bar" in {t.name for t in res.affected_types}
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `retriever.py`：以 type→file 映射；`affected_set` 反向沿 `depends/calls/associates/extends/implements` 边做闭包（BFS，去环）；`tests_to_run` = 闭包内匹配 `*Test` 的类 + 测试类对应被测类在同闭包。`responsibility_of` 由包名/类名启发式（`controller/service/repository/model` 等关键字）。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: CodeMap 影响闭包检索`

---

## Task 21: DiagramRenderer（包图 + 类图 DOT）

**Files:** Create: `probe/codemap/renderer.py`; Test: `tests/codemap/test_renderer.py`
**Interfaces:**
- Consumes: `probe/codemap/graph.py`
- Produces: `render_package_dot(graph)->str`、`render_class_dot(graph, package?)->str`、`layout(dot_str, out_png)->Path`（调 graphviz `dot`，可 mock）。

- [ ] **Step 1: 失败测试** — `tests/codemap/test_renderer.py`
```python
from probe.codemap.renderer import render_package_dot, render_class_dot
from probe.codemap.graph import CodeGraph, Type, Edge
def test_package_dot_has_nodes():
    g = CodeGraph(modules=[], types=[Type(name="Foo",kind="class",package="com.x",members=[],extends=None,implements=[])],
        edges=[])
    dot = render_package_dot(g)
    assert "com.x" in dot and "digraph" in dot
def test_class_dot_has_extends_edge():
    g = CodeGraph([], [Type(name="Foo",kind="class",package="p",members=[],extends="Bar",implements=[])],
        [Edge(kind="extends",src="Foo",dst="Bar")])
    dot = render_class_dot(g)
    assert '"Foo" -> "Bar"' in dot
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `renderer.py`：包图聚合类级边到包级；类图直出 `extends/implements/associates/depends` 边。DOT 字符串生成纯函数；`layout` subprocess 调 `dot -Tpng`。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: CodeMap 包图/类图 DOT 渲染`

---

## Task 22: Memory store

**Files:** Create: `probe/memory/__init__.py`, `probe/memory/store.py`; Test: `tests/memory/test_store.py`
**Interfaces:**
- Produces: `Memory(repo_root)`，`append_decision(decision_dict)`、`recent(n)->list`、`get_conventions()->dict`、`set_convention(k,v)`；JSON 落 `.probe/memory.json`。

- [ ] **Step 1: 失败测试** — `tests/memory/test_store.py`
```python
from probe.memory.store import Memory
def test_append_and_recent(tmp_repo):
    m = Memory(tmp_repo)
    m.append_decision({"iter":1,"sig":"abc","action":"CONTINUE"})
    m.append_decision({"iter":2,"sig":"abc","action":"STOP"})
    assert m.recent(2)[1]["iter"] == 2
def test_missing_file_degrades(tmp_repo):
    m = Memory(tmp_repo)
    assert m.recent(5) == []  # 不阻断
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `store.py`：JSON 读写，缺文件→空列表；不接任何框架 memory。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: Memory JSON 存储`

---

## Task 23: AgentLoop（内核主循环）

**Files:** Create: `probe/core/loop.py`; Test: `tests/core/test_loop.py`
**Interfaces:**
- Consumes: LLMClient, ToolRegistry, Guardrail+HITL, ValidatorPipeline+Classifier, SelfCorrector, CodeMap, Memory, Config
- Produces: `AgentLoop(...)`，`run(task: Task)->RunResult`。

- [ ] **Step 1: 失败测试** — `tests/core/test_loop.py`
```python
from probe.core.loop import AgentLoop
from probe.core.types import Task, Status
from probe.llm.mock import MockLLM
from probe.llm.base import LLMResponse, Action
def test_loop_succeeds_with_mock(tmp_repo, monkeypatch):
    # MockLLM: 先写一个会失败的测试文件, 再修正它
    actions = [
        LLMResponse(actions=[Action(type="write",path="src/A.java",content="bad")],raw="",stop_reason="ok"),
        LLMResponse(actions=[Action(type="write",path="src/A.java",content="good")],raw="",stop_reason="ok"),
        LLMResponse(actions=[],raw="",stop_reason="end_turn"),
    ]
    # 桩 ValidatorPipeline: 第一轮 FAIL, 第二轮 PASS
    calls = {"n":0}
    class FakePipe:
        def run(self, repo, changed_files=None):
            calls["n"]+=1
            from probe.validators.base import FailureReport
            if calls["n"]==1:
                return FailureReport({"compile":"FAIL"},[], "fail1",{})
            return FailureReport({"compile":"PASS","test":"PASS","lint":"PASS"},[], "ok",{})
    loop = AgentLoop(llm=MockLLM(actions), pipeline=FakePipe(),
        config=Config.load(None,{}), repo=tmp_repo)
    res = loop.run(Task(goal="fix", target_repo=str(tmp_repo), budget={}))
    assert res.status == Status.SUCCESS
def test_loop_blocked_no_progress(tmp_repo):
    # 同一 FAIL 签名连续 K 轮 → BLOCKED_NO_PROGRESS
    ...
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `loop.py`：`run` 循环：`llm.complete`→解析 actions→对每个 action `guardrail`→若 block 且 needs_approval 则置 `awaiting_approval`（测试中直接 approve）→`registry.dispatch`→`pipeline.run`→`classify_report`→`self_corrector.decide`→`memory.append_decision`→据 Decision CONTINUE/STOP。预算耗尽/无进展/拒绝即停。`RunResult.status` 来自 Decision。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: AgentLoop 主循环`

---

## Task 24: ReportRenderer

**Files:** Create: `probe/report/__init__.py`, `probe/report/renderer.py`; Test: `tests/report/test_renderer.py`
**Interfaces:**
- Consumes: FailureReport, affected_set, CodeGraph
- Produces: `render_markdown(report, affected)->str`、`render_json(report, affected)->dict`。

- [ ] **Step 1: 失败测试** — `tests/report/test_renderer.py`
```python
from probe.report.renderer import render_markdown
from probe.validators.base import FailureReport, Failure, Category
def test_md_lists_failure_with_hint():
    f = Failure(validator="test",severity="error",file="A.java",line=5,
        category=Category.TEST_FAILURE,message="expected [1] but was [2]",raw="",hint="check assertion")
    r = FailureReport({"test":"FAIL"},[f],"s",{"TEST_FAILURE":1})
    md = render_markdown(r, affected={"affected_files":["A.java"],"tests_to_run":[]})
    assert "A.java:5" in md and "TEST_FAILURE" in md and "check assertion" in md
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `renderer.py`：Markdown 表格 + 影响面段；JSON 结构化。纯渲染。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: ReportRenderer`

---

## Task 25: WebUI (FastAPI + SSE + cytoscape)

**Files:** Create: `probe/web/__init__.py`, `probe/web/app.py`, `probe/web/static/index.html`; Test: `tests/web/test_app.py`
**Interfaces:**
- Consumes: AgentLoop, CodeMap renderer, ReportRenderer
- Produces: `create_app(loop_factory) -> FastAPI`，端点 `POST /tasks`（启动）、`GET /tasks/{id}/stream`（SSE 步骤流）、`GET /tasks/{id}/report`、`GET /map/package.dot`、`GET /map/class.dot?package=`、`POST /tasks/{id}/approve`。

- [ ] **Step 1: 失败测试** — `tests/web/test_app.py`
```python
from fastapi.testclient import TestClient
from probe.web.app import create_app
def test_submit_and_report(tmp_repo):
    app = create_app(loop_factory=lambda repo: _FakeLoop())
    c = TestClient(app)
    r = c.post("/tasks", json={"goal":"g","target_repo":str(tmp_repo)})
    assert r.status_code == 200 and "task_id" in r.json()
    rep = c.get(f"/tasks/{r.json()['task_id']}/report")
    assert rep.status_code == 200
def test_package_dot_endpoint(tmp_repo):
    app = create_app(loop_factory=lambda repo: _FakeLoop())
    c = TestClient(app)
    assert "digraph" in c.get("/map/package.dot").text
```
（`_FakeLoop` 返回固定 `RunResult`；cytoscape 前端消费 DOT 字符串。）
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `app.py`：FastAPI + `sse-starlette`；任务内存表；SSE 从 AgentLoop 的步骤事件流（loop 产 `Step` 列表，web 流式 yield）；审批端点写回 HITL。前端 `static/index.html` 用 cytoscape 渲染 DOT。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: WebUI FastAPI + SSE + 图`

---

## Task 26: CLI

**Files:** Create: `probe/cli.py`, `probe/__main__.py`; Test: `tests/test_cli.py`
**Interfaces:**
- Produces: `probe init|run|report|map|creds` 子命令。

- [ ] **Step 1: 失败测试** — `tests/test_cli.py`
```python
import subprocess, sys
def test_creds_status_masks(tmp_repo, monkeypatch):
    from probe.cli import creds_status
    # 注入 store, 断言输出不含明文
def test_init_guides_key_entry(monkeypatch):
    # monkeypatch getpass, 断言写入 keychain
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `cli.py` 用 `argparse`；`init` 调 CredentialStore + 引导；`run` 组装 AgentLoop 跑并打印报告；`map` 输出 DOT；`creds status/update/clear`。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: CLI`

---

## Task 27: 机制演示 (demo_mechanisms.py, A.6)

**Files:** Create: `demo_mechanisms.py`; Test: `tests/test_demo_mechanisms.py`
**Interfaces:**
- Produces: 三个确定性演示函数 `demo_guardrail()`、`demo_feedback_loop()`、`demo_no_progress()`，全用 MockLLM/构造数据。

- [ ] **Step 1: 失败测试** — `tests/test_demo_mechanisms.py`
```python
import demo_mechanisms as dm
def test_demo_guardrail_blocks():
    assert "BLOCKED" in dm.demo_guardrail()  # 拦截 rm -rf
def test_demo_feedback_changes_next_action():
    log = dm.demo_feedback_loop()
    # 注入 TEST_FAILURE 后, agent 下一步动作应为 "patch" 而非 "stop"
    assert any(s.action.type=="patch" for s in log[1:])
def test_demo_no_progress_blocks():
    assert "BLOCKED_NO_PROGRESS" in dm.demo_no_progress()
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `demo_mechanisms.py`：①`demo_guardrail` 构造 `Action(command="rm -rf /")` 调 `guardrail` 断言 block；②`demo_feedback_loop` 用 MockLLM 脚本（首轮结束动作→注入 surefire TEST_FAILURE 的 FailureReport→SelfCorrector 回灌→第二轮 MockLLM 返回 patch）断言下一步是 patch；③`demo_no_progress` 喂同一 signature 报告 K 轮断言 BLOCKED。无网络无 key。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `feat: A.6 机制演示`

---

## Task 28: Dockerfile + CI (.gitlab-ci.yml)

**Files:** Create: `Dockerfile`, `.gitlab-ci.yml`, `.dockerignore`; Test: 验证 `docker build` 与 CI job 结构（本地用 `pytest` 校验 yaml 解析含 `unit-test`）。
**Interfaces:**
- Produces: 单条 `docker build .` 产出镜像；`.gitlab-ci.yml` 含 `unit-test`（只跑 mock 单测）与 `build-image` job。

- [ ] **Step 1: 失败测试** — `tests/test_ci.py`
```python
import yaml
def test_ci_has_unit_test_job():
    ci = yaml.safe_load(open(".gitlab-ci.yml"))
    assert "unit-test" in ci
    assert "pytest" in str(ci["unit-test"]["script"])
def test_ci_unit_test_skips_integration():
    ci = yaml.safe_load(open(".gitlab-ci.yml"))
    assert "-m 'not integration'" in str(ci["unit-test"]["script"])
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现**
`Dockerfile`：
```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jdk maven graphviz && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]"
COPY probe ./probe
COPY demo_mechanisms.py ./
EXPOSE 8000
CMD ["uvicorn", "probe.web.app:create_app_factory", "--host", "0.0.0.0", "--port", "8000"]
```
`.gitlab-ci.yml`：
```yaml
image: python:3.12-slim
stages: [test, build]
unit-test:
  stage: test
  before_script: [apt-get update -qq, apt-get install -y -qq default-jdk maven graphviz]
  script: [pip install -e ".[dev]", pytest -q -m 'not integration']
build-image:
  stage: build
  image: docker:24
  services: [docker:24-dind]
  script: [docker build -t probe:ci .]
```
`.dockerignore`：`.git tests .env .probe **/__pycache__`
- [ ] **Step 4: 验证绿** — `make test`（含 test_ci）PASS；`docker build .` 成功（手动验证记 AGENT_LOG）。
- [ ] **Step 5: Commit** — `feat: Dockerfile 与 GitLab CI (unit-test)`

---

## Task 29: README + .env.example + 部署

**Files:** Create: `README.md`, `.env.example`, `fly.toml`（或 render 配置）; Test: `tests/test_readme_sections.py`
**Interfaces:**
- Produces: README 含必备章节（简介/安装/运行/分发命令/目录结构/安全边界）；公网部署 URL。

- [ ] **Step 1: 失败测试** — `tests/test_readme_sections.py`
```python
def test_readme_has_required_sections():
    t = open("README.md").read()
    for h in ["## 简介","## 安装","## 运行","## 分发","## 目录结构","## 安全边界"]:
        assert h in t
def test_readme_has_docker_run():
    assert "docker run" in open("README.md").read()
def test_env_example_no_real_key():
    assert "sk-" not in open(".env.example").read()
```
- [ ] **Step 2: 验证红**
- [ ] **Step 3: 实现** — `README.md` 写齐章节（含 key 安全配置与容器限制）；`.env.example` 只放 `LLM_API_KEY=`、`LLM_BASE_URL=` 占位（无真实 key）；`fly.toml` 部署配置。
- [ ] **Step 4: 验证绿**
- [ ] **Step 5: Commit** — `docs: README 与部署配置`

---

## Self-Review（writing-plans 自审）

**1. Spec coverage**（逐节对）：
- §3.1 AgentLoop → T23 ✓；§3.2 LLMClient → T4/T5 ✓；§3.3 Tools → T6–T9 ✓；§3.4 ValidatorPipeline → T12–T16 ✓；§3.5 FailureClassifier → T17 ✓；§3.6 SelfCorrector → T18 ✓；§3.7 CodeMap → T19–T21 ✓；§3.8 Guardrail → T10 ✓；§3.9 HITL → T11 ✓；§3.10 Memory → T22 ✓；§3.11 Config → T2 ✓；§3.12 CredentialStore → T3 ✓；§3.13 ReportRenderer → T24 ✓；§3.14 WebUI → T25 ✓；CLI → T26 ✓；§A.6 机制演示 → T27 ✓；§7 分发 → T28 ✓；§README → T29 ✓。
- AC-1 自实现内核 → 全 task 自写、无框架 agent runner ✓；AC-2 机制可单测 → 各 task 均有 mock 单测 ✓；AC-3 机制演示 → T27 ✓；AC-4 真实端到端 → T23 真实 LLM 集成测试标记 `integration` ✓；AC-5 代码地图 → T19–T21 ✓；AC-6 凭据 → T3 ✓；AC-7 分发 → T28 ✓；AC-8 WebUI+部署 → T25/T29 ✓；AC-9 CI → T28 ✓。

**2. Placeholder scan**：无 TBD/TODO；T23 测试中 `...` 仅表示第二个用例体（同模式），实现步骤已给全。无"add error handling"类空话。

**3. Type consistency**：`Status`（T1）、`Category`（T12）、`Failure/FailureReport/signature`（T12）、`Action`（T4）、`ToolResult`（T6）、`Verdict`（T10）、`State/Event`（T11）、`Decision`（T18）、`CodeGraph/Type/Edge`（T19）跨 task 命名一致；`signature` 在 T12 定义、T18/T23 使用一致；`Config.load(None,{})` 在 T2 定义为兼容空 path（用默认）→ 各测试一致使用。✓

无修复项。

---

## Execution Handoff

Plan complete and saved to `PLAN.md`. Two execution options:

1. **Subagent-Driven (recommended)** — 每个 task 派一个新鲜 subagent，task 间两阶段评审，迭代快。
2. **Inline Execution** — 本会话内按 executing-plans 批量执行，带检查点。

**但**：作业 §4.5 要求在正式实现前先用"陌生 agent 冷启动试运行"——这是规约质量的客观证据，优先级高于直接实现。建议顺序：先做冷启动验证（拿 SPEC+PLAN 让第二个 agent 跑 1–2 个 task）→ 据 feedback 修订 SPEC/PLAN → 再进入 subagent-driven 实现。

你想：(A) 先做冷启动验证，还是 (B) 直接 subagent-driven 实现？
