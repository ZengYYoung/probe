# Java 项目上传功能 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 WebUI 新增上传 Java 项目（zip）功能，使部署在 Render 上的用户能提供自己的 Java 仓给 agent 和代码地图使用。

**Architecture:** 后端新增 `POST /repos/upload`（安全解压 zip 到临时目录）+ `GET /repos` + `GET /repos/{repo_id}`，进程内 store 管理 repo_id→path。前端新增 `stores/repos.ts` 共享 repo 列表，Tasks 页和 CodeMap 页加 `el-upload` + repo 下拉。不改现有端点契约——前端把上传返回的 path 传给现有 `POST /tasks` 和 `/map/*.dot`。

**Tech Stack:** FastAPI（`UploadFile` + `python-multipart`）+ zipfile/zip slip 校验 + Vue 3 + Element Plus `el-upload`。

## Global Constraints

- **不触碰 harness 内核**：`probe/core/`、`probe/llm/`、`probe/tools/`、`probe/guardrail/`、`probe/validators/`、`probe/feedback/`、`probe/codemap/`、`probe/memory/`、`probe/report/` 一律不改。
- **现有端点契约不变**：`POST /tasks`、`GET /tasks/{id}/*`、`POST /tasks/{id}/approve`、`GET /map/*.dot`、`GET /demo` 的请求/响应形状不动（`tests/web/test_app.py` + `tests/web/test_demo_endpoint.py` 须保持绿）。
- **前端无 pytest**：以 `npm run build` 成功为验证门。
- **`make test` 命令不变**。
- **TDD 硬性**：后端任务先红、再绿。
- **代理用中文交流**（用户偏好）。

---

## File Structure

| 文件 | 责任 | 创建/修改 |
|---|---|---|
| `pyproject.toml` | 加 `python-multipart` 依赖 | 修改 |
| `probe/web/app.py` | 新增 repo store + `POST /repos/upload` + `GET /repos` + `GET /repos/{repo_id}` + zip 安全解压 | 修改 |
| `tests/web/test_repos_upload.py` | 上传端点测试（合法 zip / 非 zip / bad magic / zip slip / 超大 / list / get / 404） | 创建 |
| `web-ui/src/stores/repos.ts` | reactive + localStorage repo 列表 | 创建 |
| `web-ui/src/api.ts` | 新增 `uploadRepo` / `listRepos` / `getRepo` + TS 接口 | 修改 |
| `web-ui/src/pages/Tasks.vue` | 加 `el-upload` + repo `el-select` 下拉 | 修改 |
| `web-ui/src/pages/CodeMap.vue` | 加 `el-upload` + repo `el-select` 下拉 | 修改 |
| `README.md` | 运行节加上传功能说明 | 修改 |

---

## Task 1: 后端 — `POST /repos/upload` + `GET /repos` + `GET /repos/{repo_id}`（TDD）

**Files:**
- Modify: `pyproject.toml`（加 `python-multipart`）
- Modify: `probe/web/app.py`（加 repo store + 3 个端点 + zip 安全解压）
- Test: `tests/web/test_repos_upload.py`（创建）

**Interfaces:**
- Produces: `POST /repos/upload`（multipart `file` → `{repo_id, path, name, file_count}`）、`GET /repos`（→ `[{repo_id, name, file_count}]`）、`GET /repos/{repo_id}`（→ `{repo_id, path, name, file_count}`）。

- [ ] **Step 1: 加 `python-multipart` 依赖**

在 `pyproject.toml` 的 `dependencies` 列表加 `"python-multipart"`：

```toml
dependencies = ["pydantic>=2", "httpx", "keyring", "javalang", "fastapi", "uvicorn", "python-multipart"]
```

运行 `pip install -e ".[dev]"` 安装新依赖。

- [ ] **Step 2: 写失败测试 `tests/web/test_repos_upload.py`**

```python
import io
import zipfile

from fastapi.testclient import TestClient
from probe.w.app import create_app
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
```

- [ ] **Step 3: 运行测试验证失败**

Run: `python -m pytest tests/web/test_repos_upload.py -v`
Expected: FAIL（`/repos/upload` 路由不存在 → 404 或 AttributeError）

- [ ] **Step 4: 在 `probe/web/app.py` 实现端点**

在文件顶部 import 区加：

```python
import io
import tempfile
import uuid
import zipfile
from pathlib import Path
```

把现有 `from fastapi import FastAPI, HTTPException` 改为：

```python
from fastapi import FastAPI, HTTPException, File, UploadFile
```

在模块级（`_DEMO_REPO_ENV` 常量附近）加：

```python
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB
```

在 `create_app` 函数内，现有 `tasks` / `approvals` store 旁加：

```python
    repos: dict[str, dict] = {}  # repo_id -> {path, name, file_count}
```

在 `GET /demo` 端点之后、`return app` 之前加三个端点：

```python
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
        """列出已上传的 repo（不含 path）。"""
        return [
            {"repo_id": rid, "name": r["name"], "file_count": r["file_count"]}
            for rid, r in repos.items()
        ]

    @app.get("/repos/{repo_id}")
    def get_repo(repo_id: str) -> dict:
        """按 repo_id 取 repo 详情（含 path）。"""
        r = repos.get(repo_id)
        if r is None:
            raise HTTPException(404, "repo not found")
        return {
            "repo_id": repo_id,
            "path": r["path"],
            "name": r["name"],
            "file_count": r["file_count"],
        }
```

- [ ] **Step 5: 运行测试验证通过**

Run: `python -m pytest tests/web/test_repos_upload.py -v`
Expected: 7 passed

- [ ] **Step 6: 运行 web 全量测试确认无回归**

Run: `python -m pytest tests/web/ -v`
Expected: 全绿（含原 test_app.py + test_demo_endpoint.py）

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml probe/web/app.py tests/web/test_repos_upload.py
git commit -m "feat(web): 新增 POST /repos/upload + GET /repos 端点(zip 安全解压 + zip slip 防护)"
```

---

## Task 2: 前端 — `stores/repos.ts` + `api.ts` 新增

**Files:**
- Create: `web-ui/src/stores/repos.ts`
- Modify: `web-ui/src/api.ts`

**Interfaces:**
- Consumes: Task 1 的 `POST /repos/upload` / `GET /repos` / `GET /repos/{repo_id}` 端点。
- Produces: `uploadRepo(file)` / `listRepos()` / `getRepo(repoId)` 函数 + `RepoUploadResp` / `RepoListItem` 接口；`repoStore` reactive 数组 + `addRepo(rec)`。

- [ ] **Step 1: 创建 `web-ui/src/stores/repos.ts`**

```ts
import { reactive, watch } from 'vue'

export interface RepoRecord {
  repo_id: string
  path: string
  name: string
  file_count: number
}

const KEY = 'probe-repos'

function load(): RepoRecord[] {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]') } catch { return [] }
}

export const repoStore = reactive<RepoRecord[]>(load())

watch(repoStore, (v) => {
  localStorage.setItem(KEY, JSON.stringify(v))
})

export function addRepo(rec: RepoRecord) {
  repoStore.unshift(rec)
}
```

- [ ] **Step 2: 在 `web-ui/src/api.ts` 末尾新增上传相关函数**

在文件末尾追加：

```ts
export interface RepoUploadResp { repo_id: string; path: string; name: string; file_count: number }
export interface RepoListItem { repo_id: string; name: string; file_count: number }

export async function uploadRepo(file: File): Promise<RepoUploadResp> {
  const fd = new FormData()
  fd.append('file', file)
  const r = await fetch(`${base}/repos/upload`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error(`uploadRepo ${r.status}`)
  return r.json()
}

export async function listRepos(): Promise<RepoListItem[]> {
  const r = await fetch(`${base}/repos`)
  if (!r.ok) throw new Error(`listRepos ${r.status}`)
  return r.json()
}

export async function getRepo(repoId: string): Promise<RepoUploadResp> {
  const r = await fetch(`${base}/repos/${repoId}`)
  if (!r.ok) throw new Error(`getRepo ${r.status}`)
  return r.json()
}
```

- [ ] **Step 3: 构建验证**

Run:
```bash
cd web-ui
npm run build
```
Expected: 构建成功。

- [ ] **Step 4: Commit**

```bash
git add web-ui/src/stores/repos.ts web-ui/src/api.ts
git commit -m "feat(web): stores/repos.ts + api.ts 新增 uploadRepo/listRepos/getRepo"
```

---

## Task 3: Tasks 页 — 加 `el-upload` + repo 下拉

**Files:**
- Modify: `web-ui/src/pages/Tasks.vue`

**Interfaces:**
- Consumes: Task 2 的 `uploadRepo` / `repoStore` / `addRepo`。

- [ ] **Step 1: 重写 `web-ui/src/pages/Tasks.vue`**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import { submitTask, getReport, getStream, uploadRepo, type RunResult, type Step } from '@/api'
import { taskStore, addTask, type TaskRecord } from '@/stores/tasks'
import { repoStore, addRepo } from '@/stores/repos'

const goal = ref('')
const targetRepo = ref('')
const submitting = ref(false)
const uploading = ref(false)

const drawerVisible = ref(false)
const current = ref<RunResult | null>(null)
const currentSteps = ref<Step[]>([])
const currentRecord = ref<TaskRecord | null>(null)

const statusType: Record<string, string> = {
  SUCCESS: 'success',
  BLOCKED_NO_PROGRESS: 'danger',
  STOPPED_REJECTED: 'warning',
  STOPPED_BUDGET: 'warning',
  ERROR: 'danger',
}

async function onUpload(file: File) {
  uploading.value = true
  try {
    const resp = await uploadRepo(file)
    addRepo({ repo_id: resp.repo_id, path: resp.path, name: resp.name, file_count: resp.file_count })
    targetRepo.value = resp.path
    ElMessage.success(`已上传: ${resp.name} (${resp.file_count} 文件)`)
  } catch (e) {
    ElMessage.error('上传失败: ' + (e as Error).message)
  } finally {
    uploading.value = false
  }
}

function onRepoSelect(path: string) {
  targetRepo.value = path
}

async function onSubmit() {
  if (!goal.value || !targetRepo.value) {
    ElMessage.warning('请填写 goal 并上传/选择 repo')
    return
  }
  submitting.value = true
  try {
    const resp = await submitTask(goal.value, targetRepo.value)
    addTask({
      task_id: resp.task_id,
      goal: goal.value,
      target_repo: targetRepo.value,
      submitted_at: new Date().toISOString(),
    })
    ElMessage.success(`已提交: ${resp.task_id.slice(0, 8)}…`)
    goal.value = ''
  } catch (e) {
    ElMessage.error('提交失败: ' + (e as Error).message)
  } finally {
    submitting.value = false
  }
}

async function viewDetail(rec: TaskRecord) {
  currentRecord.value = rec
  drawerVisible.value = true
  current.value = null
  currentSteps.value = []
  try {
    const [rep, stream] = await Promise.all([
      getReport(rec.task_id),
      getStream(rec.task_id),
    ])
    current.value = rep
    currentSteps.value = stream.steps
  } catch (e) {
    ElMessage.error('加载详情失败: ' + (e as Error).message)
  }
}
</script>

<template>
  <el-card style="margin-bottom: 16px">
    <template #header>提交任务</template>
    <el-form label-position="top">
      <el-form-item label="目标 (goal)">
        <el-input v-model="goal" type="textarea" :rows="2" placeholder="让测试变绿" />
      </el-form-item>
      <el-form-item label="Java 项目 (上传 zip 或选择已上传)">
        <el-upload
          :auto-upload="true"
          :show-file-list="false"
          accept=".zip"
          :http-request="(opts: any) => onUpload(opts.file)"
        >
          <el-button :icon="Upload" :loading="uploading">上传 zip</el-button>
        </el-upload>
        <el-select
          v-if="repoStore.length"
          v-model="targetRepo"
          placeholder="选择已上传的 repo"
          style="width: 100%; margin-top: 8px"
          @change="onRepoSelect"
        >
          <el-option
            v-for="r in repoStore"
            :key="r.repo_id"
            :label="`${r.name} (${r.file_count} 文件)`"
            :value="r.path"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="或手动输入路径 (本地开发)">
        <el-input v-model="targetRepo" placeholder="/path/to/java-repo" />
      </el-form-item>
      <el-button type="primary" :loading="submitting" @click="onSubmit">提交</el-button>
    </el-form>
  </el-card>

  <el-card>
    <template #header>任务历史</template>
    <el-table :data="taskStore" empty-text="暂无任务">
      <el-table-column label="Task ID" width="140">
        <template #default="{ row }">{{ row.task_id.slice(0, 8) }}…</template>
      </el-table-column>
      <el-table-column prop="goal" label="Goal" show-overflow-tooltip />
      <el-table-column label="提交时间" width="180">
        <template #default="{ row }">{{ new Date(row.submitted_at).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button link type="primary" @click="viewDetail(row)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-drawer v-model="drawerVisible" size="50%" :title="currentRecord?.goal">
    <template v-if="current">
      <el-tag :type="statusType[current.status] || 'info'" style="margin-bottom: 12px">
        {{ current.status }}
      </el-tag>
      <h4>步骤时间线</h4>
      <el-timeline v-if="currentSteps.length">
        <el-timeline-item v-for="s in currentSteps" :key="s.iteration" :timestamp="`iter ${s.iteration}`">
          <div><strong>action:</strong> {{ s.action.type }}</div>
          <div v-if="s.action.path"><strong>path:</strong> {{ s.action.path }}</div>
          <div v-if="s.action.command"><strong>cmd:</strong> {{ s.action.command }}</div>
          <div v-if="s.decision?.reason"><strong>reason:</strong> {{ s.decision.reason }}</div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="无步骤" />
      <h4>最终报告</h4>
      <el-card shadow="never">
        <pre style="white-space: pre-wrap; font-size: 12px">{{ JSON.stringify(current.final_failure_report, null, 2) }}</pre>
      </el-card>
    </template>
    <el-skeleton v-else :rows="5" animated />
  </el-drawer>
</template>
```

- [ ] **Step 2: 构建验证**

Run:
```bash
cd web-ui
npm run build
```
Expected: 构建成功。

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/pages/Tasks.vue
git commit -m "feat(web): Tasks 页加 el-upload + repo 下拉"
```

---

## Task 4: CodeMap 页 — 加 `el-upload` + repo 下拉

**Files:**
- Modify: `web-ui/src/pages/CodeMap.vue`

**Interfaces:**
- Consumes: Task 2 的 `uploadRepo` / `repoStore` / `addRepo`。

- [ ] **Step 1: 重写 `web-ui/src/pages/CodeMap.vue`**

```vue
<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import { graphviz } from 'd3-graphviz'
import { getPackageDot, getClassDot, uploadRepo } from '@/api'
import { repoStore, addRepo } from '@/stores/repos'

const repo = ref('')
const kind = ref<'package' | 'class'>('package')
const pkg = ref('')
const dotSource = ref('')
const loading = ref(false)
const uploading = ref(false)
const graphContainer = ref<HTMLDivElement>()

async function onUpload(file: File) {
  uploading.value = true
  try {
    const resp = await uploadRepo(file)
    addRepo({ repo_id: resp.repo_id, path: resp.path, name: resp.name, file_count: resp.file_count })
    repo.value = resp.path
    ElMessage.success(`已上传: ${resp.name} (${resp.file_count} 文件)`)
    render()
  } catch (e) {
    ElMessage.error('上传失败: ' + (e as Error).message)
  } finally {
    uploading.value = false
  }
}

async function render() {
  loading.value = true
  dotSource.value = ''
  try {
    const dot = kind.value === 'package'
      ? await getPackageDot(repo.value)
      : await getClassDot(repo.value, pkg.value || undefined)
    dotSource.value = dot
    await nextTick()
    if (graphContainer.value) {
      graphviz(graphContainer.value).renderDot(dot)
    }
  } catch (e) {
    ElMessage.error('渲染失败: ' + (e as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  render()
})
</script>

<template>
  <el-card style="margin-bottom: 16px">
    <template #header>代码地图</template>
    <el-form inline>
      <el-form-item label="上传">
        <el-upload
          :auto-upload="true"
          :show-file-list="false"
          accept=".zip"
          :http-request="(opts: any) => onUpload(opts.file)"
        >
          <el-button :icon="Upload" :loading="uploading">上传 zip</el-button>
        </el-upload>
      </el-form-item>
      <el-form-item v-if="repoStore.length" label="已上传">
        <el-select v-model="repo" placeholder="选择 repo" style="width: 240px" @change="render">
          <el-option
            v-for="r in repoStore"
            :key="r.repo_id"
            :label="`${r.name} (${r.file_count})`"
            :value="r.path"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="或路径">
        <el-input v-model="repo" placeholder="留空用内置 demo-repo" style="width: 240px" />
      </el-form-item>
      <el-form-item label="类型">
        <el-radio-group v-model="kind">
          <el-radio value="package">包图</el-radio>
          <el-radio value="class">类图</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="kind === 'class'" label="Package">
        <el-input v-model="pkg" placeholder="com.demo" style="width: 200px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="render">渲染</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-card v-loading="loading">
    <div ref="graphContainer" style="min-height: 400px; text-align: center"></div>
    <el-collapse style="margin-top: 16px">
      <el-collapse-item title="DOT 源码">
        <el-input :model-value="dotSource" type="textarea" :rows="10" readonly />
      </el-collapse-item>
    </el-collapse>
  </el-card>
</template>
```

- [ ] **Step 2: 构建验证**

Run:
```bash
cd web-ui
npm run build
```
Expected: 构建成功。

- [ ] **Step 3: Commit**

```bash
git add web-ui/src/pages/CodeMap.vue
git commit -m "feat(web): CodeMap 页加 el-upload + repo 下拉"
```

---

## Task 5: README — 文档化上传功能

**Files:**
- Modify: `README.md`
- Test: `tests/test_readme_sections.py`（须保持绿）

**Interfaces:**
- Produces: README 运行节新增上传功能说明，保留强制章节与字符串。

- [ ] **Step 1: 在 `README.md` 的 `## 运行` → `### WebUI` 子节末尾加一段**

在 `### WebUI` 子节的"新端点 `GET /demo`..."那行之后，加：

```markdown
上传 Java 项目：在任务页或代码地图页点"上传 zip"按钮，选择一个 `.zip` 压缩的 Java 仓（含 `pom.xml` + 源码）。后端安全解压到临时目录（防 zip slip），返回的 path 自动填入 `target_repo` / `repo` 参数。上传的 repo 在进程内存储，重启后失效（需重新上传）。大小限制 50MB。
```

- [ ] **Step 2: 运行 README 测试验证**

Run: `python -m pytest tests/test_readme_sections.py -v`
Expected: 5 passed

- [ ] **Step 3: 运行全量测试确认无回归**

Run: `python -m pytest -q`
Expected: 全绿（2 个 pre-existing Windows sleep/pwd 失败除外）

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: README 文档化 Java 项目 zip 上传功能"
```

---

## Self-Review

**1. Spec coverage:**
- §1.1 目标（`POST /repos/upload` + `GET /repos` + `GET /repos/{repo_id}` + `stores/repos.ts` + Tasks/CodeMap 上传 + 测试）→ Task 1（后端）+ Task 2（前端 store/api）+ Task 3（Tasks 页）+ Task 4（CodeMap 页）+ Task 5（README）。✓
- §1.2 非目标（不做 git URL / TTL / 持久化 / 异步）→ Global Constraints + 各任务不涉及。✓
- §1.3 硬约束（内核不改 / 端点契约不变 / 前端无 pytest / make test 不变）→ Global Constraints。✓
- §2 后端（repo store / upload 端点 / list / get / zip slip / magic bytes / 大小限制）→ Task 1 Step 4 完整代码。✓
- §3 前端（stores/repos.ts / api.ts / Tasks 页 / CodeMap 页）→ Task 2 + Task 3 + Task 4。✓
- §4 安全（zip slip / 大小 / magic / 临时目录 / path 不泄露到列表）→ Task 1 Step 4 + Step 2 测试覆盖。✓
- §5 测试（7 个测试用例）→ Task 1 Step 2 完整测试代码。✓
- §6 文件清单 → File Structure 表。✓
- §7 风险（进程重启失效 / 大文件超时 / 并发 / python-multipart）→ Task 1 Step 1 加依赖；进程重启失效在 README Task 5 文档化。✓

**2. Placeholder scan:** 无 TBD/TODO。所有代码步骤含完整代码。✓

**3. Type consistency:** `RepoUploadResp`（api.ts）与后端 `{repo_id, path, name, file_count}` 一致；`RepoListItem`（api.ts，无 path）与后端 `GET /repos` 返回 `[{repo_id, name, file_count}]` 一致；`RepoRecord`（stores/repos.ts）含 `repo_id, path, name, file_count` 与 `RepoUploadResp` 一致。✓

无缺口，计划完整。
