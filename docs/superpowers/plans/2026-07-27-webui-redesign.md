# Probe WebUI 重设计 + README 重写 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 60 行静态 HTML WebUI 升级为 Vue 3 + Vite + Element Plus 多页应用（任务/地图/HITL/演示四页），新增 `GET /demo` 端点，Dockerfile 改多阶段，并同步重写 README。

**Architecture:** 前端工程 `web-ui/`（仓库根，Python 包树之外）经 Vite 构建输出到 `probe/web/static/`；后端仅在 `probe/web/app.py`（外壳，非内核）加 `/demo` 端点，`demo_mechanisms.py` 重构为 `probe/demo.py` + shim；Dockerfile 多阶段（Node 构建前端 + Python 运行时）；harness 内核（113 测试）不动。

**Tech Stack:** Vue 3 + Vite 5 + Element Plus 2 + Vue Router 4 + TypeScript + d3-graphviz；FastAPI（已有）；pytest（已有，仅后端）。

## Global Constraints

- **Python ≥ 3.12**（`pyproject.toml` 已锁）。
- **不触碰 harness 内核**：`probe/core/`、`probe/llm/`、`probe/tools/`、`probe/guardrail/`、`probe/validators/`、`probe/feedback/`、`probe/codemap/`、`probe/memory/`、`probe/report/` 一律不改。
- **现有端点契约不变**：`POST /tasks`、`GET /tasks/{id}/report`、`GET /tasks/{id}/stream`、`POST /tasks/{id}/approve`、`GET /map/package.dot`、`GET /map/class.dot` 的请求/响应形状不动（`tests/web/test_app.py` 须保持绿）。
- **README 强制章节**（`tests/test_readme_sections.py`）：`## 简介`、`## 安装`、`## 运行`、`## 分发`、`## 目录结构`、`## 安全边界`，且含字符串 `docker run` 与 `make test`。
- **前端无 pytest**：前端任务以 `npm run build` 成功为验证门（TS 编译 + Vite 打包）；harness 内核的 mock-LLM 单测纪律不覆盖前端。
- **`make test` 命令不变**。
- **代理用中文交流**（用户偏好）。

---

## File Structure

| 文件 | 责任 | 创建/修改 |
|---|---|---|
| `probe/demo.py` | 三个 A.6 演示函数 + 辅助（从 `demo_mechanisms.py` 迁入） | 创建 |
| `demo_mechanisms.py` | 薄 shim，re-export `probe.demo` | 修改 |
| `probe/web/app.py` | 新增 `GET /demo` 端点 | 修改 |
| `tests/web/test_demo_endpoint.py` | `/demo` 端点测试 | 创建 |
| `web-ui/package.json` | 前端依赖与脚本 | 创建 |
| `web-ui/vite.config.ts` | Vite 配置（outDir、Element Plus 自动导入、dev proxy） | 创建 |
| `web-ui/tsconfig.json` | TS 配置 | 创建 |
| `web-ui/index.html` | Vite 入口 HTML | 创建 |
| `web-ui/src/main.ts` | 应用入口（挂载、Element Plus 暗色 CSS、路由） | 创建 |
| `web-ui/src/App.vue` | 布局外壳（侧栏 + 头 + 主区） | 创建 |
| `web-ui/src/router/index.ts` | Vue Router（hash 模式，4 路由） | 创建 |
| `web-ui/src/api.ts` | 后端 API 封装（fetch） | 创建 |
| `web-ui/src/stores/tasks.ts` | 任务历史客户端存储（reactive + localStorage） | 创建 |
| `web-ui/src/pages/Tasks.vue` | 任务页 | 创建 |
| `web-ui/src/pages/CodeMap.vue` | 代码地图页 | 创建 |
| `web-ui/src/pages/Approval.vue` | HITL 审批页 | 创建 |
| `web-ui/src/pages/Demo.vue` | 机制演示页 | 创建 |
| `probe/web/static/.gitkeep` | 占位（static/ 为构建产物，gitignore） | 创建 |
| `probe/web/static/index.html` | 旧 60 行 HTML（被构建产物取代） | 删除（git rm） |
| `Dockerfile` | 多阶段构建 | 修改 |
| `.gitignore` | 增 static/* 与 node_modules/ | 修改 |
| `README.md` | 重写 | 修改 |

---

## Task 1: 重构 demo_mechanisms.py → probe/demo.py + shim

**Files:**
- Create: `probe/demo.py`
- Modify: `demo_mechanisms.py`
- Test: `tests/test_demo_mechanisms.py`（已存在，须保持绿）

**Interfaces:**
- Produces: `probe.demo.demo_guardrail() -> str`、`probe.demo.demo_feedback_loop() -> list`、`probe.demo.demo_no_progress() -> str`（签名与原 `demo_mechanisms.py` 完全一致）。
- `demo_mechanisms.py` 经 `from probe.demo import *` re-export，保持 `import demo_mechanisms as dm` 可达。

- [ ] **Step 1: 创建 `probe/demo.py`，把 `demo_mechanisms.py` 全部函数迁入**

把 `demo_mechanisms.py` 的全部内容（imports + 三个 demo 函数 + 两个辅助 `_test_failure_report`/`_pass_report` + `__main__` 块）原样复制到 `probe/demo.py`，但**去掉** `__main__` 块（shim 保留它）。文件顶部加注释：

```python
"""A.6 机制演示（Task 27）——从 demo_mechanisms.py 迁入 probe 包。

三个确定性演示函数，全用 MockLLM / 构造数据，无网络无 key 无真实 LLM：
1. demo_guardrail()    — 危险动作拦截（纯函数，无 LLM）。
2. demo_feedback_loop() — 注入一次失败后反馈闭环使 agent 改为 patch。
3. demo_no_progress()  — 同一签名 FAIL 连续 K 轮触发 BLOCKED_NO_PROGRESS。
"""
```

- [ ] **Step 2: 把 `demo_mechanisms.py` 改为薄 shim**

```python
"""A.6 机制演示 CLI 入口（shim）。

实际实现已迁入 probe.demo，本文件保留以兼容 `import demo_mechanisms`
与 `python demo_mechanisms.py` 两种用法。
"""
from probe.demo import (  # noqa: F401
    demo_feedback_loop,
    demo_guardrail,
    demo_no_progress,
)

if __name__ == "__main__":
    print("=== demo_guardrail ===")
    print(demo_guardrail())
    print()
    print("=== demo_feedback_loop ===")
    for line in demo_feedback_loop():
        print(line)
    print()
    print("=== demo_no_progress ===")
    print(demo_no_progress())
```

- [ ] **Step 3: 运行现有测试验证不破**

Run: `pytest tests/test_demo_mechanisms.py -v`
Expected: 3 passed

- [ ] **Step 4: 运行全量测试确认无回归**

Run: `make test`
Expected: 全绿（113 + 现有）

- [ ] **Step 5: Commit**

```bash
git add probe/demo.py demo_mechanisms.py
git commit -m "refactor: demo_mechanisms.py 迁入 probe/demo.py, 原文件改 shim"
```

---

## Task 2: 新增 GET /demo 端点 + 测试（TDD）

**Files:**
- Modify: `probe/web/app.py`（在 `create_app` 内加端点）
- Test: `tests/web/test_demo_endpoint.py`（创建）

**Interfaces:**
- Consumes: `probe.demo.demo_guardrail`、`probe.demo.demo_feedback_loop`、`probe.demo.demo_no_progress`（Task 1 产出）。
- Produces: `GET /demo` → `200` JSON `{"guardrail": str, "feedback_loop": list[str], "no_progress": str}`。

- [ ] **Step 1: 写失败测试 `tests/web/test_demo_endpoint.py`**

```python
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/web/test_demo_endpoint.py -v`
Expected: FAIL（`/demo` 路由不存在 → 404）

- [ ] **Step 3: 在 `probe/web/app.py` 的 `create_app` 内加 `/demo` 端点**

在 `map_class_dot` 端点之后、`return app` 之前插入：

```python
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
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/web/test_demo_endpoint.py -v`
Expected: 4 passed

- [ ] **Step 5: 运行 web 全量测试确认无回归**

Run: `pytest tests/web/ -v`
Expected: 全绿（含原 test_app.py）

- [ ] **Step 6: Commit**

```bash
git add probe/web/app.py tests/web/test_demo_endpoint.py
git commit -m "feat(web): 新增 GET /demo 端点包装 A.6 机制演示"
```

---

## Task 3: 脚手架 web-ui/ Vite 工程 + api.ts + static 清理

**Files:**
- Create: `web-ui/package.json`、`web-ui/vite.config.ts`、`web-ui/tsconfig.json`、`web-ui/index.html`、`web-ui/src/main.ts`、`web-ui/src/api.ts`、`web-ui/src/router/index.ts`、`web-ui/src/stores/tasks.ts`、`web-ui/src/App.vue`（最小占位）、`web-ui/src/pages/{Tasks,CodeMap,Approval,Demo}.vue`（最小占位）
- Create: `probe/web/static/.gitkeep`
- Delete: `probe/web/static/index.html`（`git rm`）
- Modify: `.gitignore`

**Interfaces:**
- Produces: 可 `npm install && npm run build` 的 Vite 工程，构建产物落到 `probe/web/static/`；`api.ts` 暴露全部后端调用函数；router 4 路由占位；App.vue 最小布局占位（Task 4 填充）。

- [ ] **Step 1: 创建 `web-ui/package.json`**

```json
{
  "name": "probe-web-ui",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "element-plus": "^2.7.0",
    "@element-plus/icons-vue": "^2.3.0",
    "d3-graphviz": "^5.6.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.2.0",
    "typescript": "^5.4.0",
    "unplugin-vue-components": "^0.27.0",
    "unplugin-auto-import": "^0.17.0",
    "@types/d3-graphviz": "^3.4.0"
  }
}
```

- [ ] **Step 2: 创建 `web-ui/vite.config.ts`**

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import path from 'node:path'

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({ resolvers: [ElementPlusResolver()] }),
    Components({ resolvers: [ElementPlusResolver()] }),
  ],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  build: {
    outDir: path.resolve(__dirname, '../probe/web/static'),
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/tasks': 'http://127.0.0.1:8000',
      '/map': 'http://127.0.0.1:8000',
      '/demo': 'http://127.0.0.1:8000',
      '/static': 'http://127.0.0.1:8000',
    },
  },
})
```

- [ ] **Step 3: 创建 `web-ui/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": false,
    "jsx": "preserve",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "types": ["vite/client"],
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  },
  "include": ["src/**/*.ts", "src/**/*.d.ts", "src/**/*.vue", "vite.config.ts"]
}
```

- [ ] **Step 4: 创建 `web-ui/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Probe WebUI</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 5: 创建 `web-ui/src/main.ts`**

```ts
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import 'element-plus/theme-chalk/dark/css-vars.css'

createApp(App).use(router).mount('#app')
```

- [ ] **Step 6: 创建 `web-ui/src/api.ts`（全部后端调用）**

```ts
const base = ''

export interface TaskCreateResp { task_id: string }
export interface Step {
  iteration: number
  action: { type: string; command?: string; path?: string; params?: Record<string, unknown> }
  tool_result?: { ok?: boolean; output?: string; error?: string }
  failure_report?: unknown
  decision?: { action?: string; reason?: string; context_fragment?: string } | null
}
export interface RunResult {
  status: string
  steps: Step[]
  final_failure_report?: unknown
  report_path?: string | null
}
export interface DemoResp {
  guardrail: string
  feedback_loop: string[]
  no_progress: string
}

export async function submitTask(goal: string, target_repo: string): Promise<TaskCreateResp> {
  const r = await fetch(`${base}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal, target_repo }),
  })
  if (!r.ok) throw new Error(`submitTask ${r.status}`)
  return r.json()
}

export async function getReport(taskId: string): Promise<RunResult> {
  const r = await fetch(`${base}/tasks/${taskId}/report`)
  if (!r.ok) throw new Error(`getReport ${r.status}`)
  return r.json()
}

export async function getStream(taskId: string): Promise<{ steps: Step[] }> {
  const r = await fetch(`${base}/tasks/${taskId}/stream`)
  if (!r.ok) throw new Error(`getStream ${r.status}`)
  return r.json()
}

export async function approveTask(taskId: string, approve: boolean): Promise<{ ok: boolean }> {
  const r = await fetch(`${base}/tasks/${taskId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approve }),
  })
  if (!r.ok) throw new Error(`approveTask ${r.status}`)
  return r.json()
}

export async function getPackageDot(repo: string): Promise<string> {
  const r = await fetch(`${base}/map/package.dot?repo=${encodeURIComponent(repo)}`)
  if (!r.ok) throw new Error(`getPackageDot ${r.status}`)
  return r.text()
}

export async function getClassDot(repo: string, pkg?: string): Promise<string> {
  let url = `${base}/map/class.dot?repo=${encodeURIComponent(repo)}`
  if (pkg) url += `&package=${encodeURIComponent(pkg)}`
  const r = await fetch(url)
  if (!r.ok) throw new Error(`getClassDot ${r.status}`)
  return r.text()
}

export async function getDemo(): Promise<DemoResp> {
  const r = await fetch(`${base}/demo`)
  if (!r.ok) throw new Error(`getDemo ${r.status}`)
  return r.json()
}
```

- [ ] **Step 7: 创建 `web-ui/src/router/index.ts`**

```ts
import { createRouter, createWebHashHistory } from 'vue-router'
import Tasks from '@/pages/Tasks.vue'
import CodeMap from '@/pages/CodeMap.vue'
import Approval from '@/pages/Approval.vue'
import Demo from '@/pages/Demo.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/tasks' },
    { path: '/tasks', name: 'tasks', component: Tasks },
    { path: '/map', name: 'map', component: CodeMap },
    { path: '/approval', name: 'approval', component: Approval },
    { path: '/demo', name: 'demo', component: Demo },
  ],
})

export default router
```

- [ ] **Step 8: 创建 `web-ui/src/stores/tasks.ts`（客户端任务历史）**

```ts
import { reactive, watch } from 'vue'

export interface TaskRecord {
  task_id: string
  goal: string
  target_repo: string
  submitted_at: string
}

const KEY = 'probe-tasks'

function load(): TaskRecord[] {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]') } catch { return [] }
}

export const taskStore = reactive<TaskRecord[]>(load())

watch(taskStore, (v) => {
  localStorage.setItem(KEY, JSON.stringify(v))
})

export function addTask(rec: TaskRecord) {
  taskStore.unshift(rec)
}
```

- [ ] **Step 9: 创建最小占位 `web-ui/src/App.vue`**

```vue
<script setup lang="ts">
</script>

<template>
  <router-view />
</template>
```

- [ ] **Step 10: 创建四个最小占位页面**

`web-ui/src/pages/Tasks.vue`：
```vue
<template><div>Tasks</div></template>
```
`web-ui/src/pages/CodeMap.vue`：
```vue
<template><div>CodeMap</div></template>
```
`web-ui/src/pages/Approval.vue`：
```vue
<template><div>Approval</div></template>
```
`web-ui/src/pages/Demo.vue`：
```vue
<template><div>Demo</div></template>
```

- [ ] **Step 11: 清理旧 static，加 .gitkeep，更新 .gitignore**

```bash
git rm probe/web/static/index.html
```

创建 `probe/web/static/.gitkeep`（空文件）。

在 `.gitignore` 末尾追加：
```
# 前端构建产物与依赖
probe/web/static/*
!probe/web/static/.gitkeep
web-ui/node_modules/
web-ui/dist/
```

- [ ] **Step 12: 安装依赖并构建验证**

Run:
```bash
cd web-ui
npm install
npm run build
```
Expected: 构建成功，`probe/web/static/` 下生成 `index.html` + `assets/`。

- [ ] **Step 13: 验证后端服务能加载新前端**

Run（另一终端）:
```bash
uvicorn probe.web.app:create_app --factory
```
浏览器打开 `http://127.0.0.1:8000/`，应见 "Tasks" 占位文字（hash 路由 `/#/tasks`）。

- [ ] **Step 14: 运行后端测试确认无回归**

Run: `make test`
Expected: 全绿（前端无 pytest，后端不受影响）

- [ ] **Step 15: Commit**

```bash
git add web-ui/ probe/web/static/.gitkeep .gitignore
git commit -m "feat(web): 脚手架 web-ui/ Vite 工程(Vue3+ElementPlus), 清理旧 static"
```

> 注：`web-ui/package-lock.json` 生成后也应 `git add` 加入提交（保证 Docker `npm ci` 可重现）。

---

## Task 4: App.vue 布局外壳（侧栏 + 头 + 暗色模式）

**Files:**
- Modify: `web-ui/src/App.vue`

**Interfaces:**
- Produces: 完整布局外壳，侧栏 `el-menu` 跳转 4 路由，头部含 GitHub 链接 + 暗色 `el-switch`。

- [ ] **Step 1: 重写 `web-ui/src/App.vue`**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  Document,
  Share,
  Warning,
  Cpu,
  Moon,
  Sunny,
} from '@element-plus/icons-vue'

const route = useRoute()
const isDark = ref(false)

function applyDark(v: boolean) {
  document.documentElement.classList.toggle('dark', v)
  localStorage.setItem('probe-dark', String(v))
}

function toggleDark(v: boolean) {
  isDark.value = v
  applyDark(v)
}

onMounted(() => {
  const saved = localStorage.getItem('probe-dark') === 'true'
  isDark.value = saved
  applyDark(saved)
})

const menus = [
  { index: '/tasks', label: '任务', icon: Document },
  { index: '/map', label: '代码地图', icon: Share },
  { index: '/approval', label: 'HITL 审批', icon: Warning },
  { index: '/demo', label: '机制演示', icon: Cpu },
]
</script>

<template>
  <el-container style="height: 100vh">
    <el-aside width="220px" style="background: #001529">
      <div style="padding: 20px 16px; color: #fff; font-size: 18px; font-weight: 600">
        Probe
      </div>
      <div style="padding: 0 16px 16px; color: #8c8c8c; font-size: 12px">
        Java 可行性 harness
      </div>
      <el-menu
        :default-active="route.path"
        router
        background-color="#001529"
        text-color="#bfbfbf"
        active-text-color="#409eff"
      >
        <el-menu-item v-for="m in menus" :key="m.index" :index="m.index">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--el-border-color)">
        <span style="font-size: 16px; font-weight: 500">
          {{ menus.find(m => m.index === route.path)?.label || 'Probe' }}
        </span>
        <div style="display: flex; align-items: center; gap: 16px">
          <el-link href="https://github.com/ZengYYoung/probe" target="_blank" type="primary">
            GitHub
          </el-link>
          <el-switch
            :model-value="isDark"
            @update:model-value="toggleDark"
            :active-action-icon="Moon"
            :inactive-action-icon="Sunny"
          />
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
```

- [ ] **Step 2: 构建验证**

Run:
```bash
cd web-ui
npm run build
```
Expected: 构建成功。

- [ ] **Step 3: 浏览器验证**

Run: `uvicorn probe.web.app:create_app --factory`（若未起）
打开 `http://127.0.0.1:8000/`，应见侧栏 + 头 + 暗色开关；点击侧栏项切换路由；暗色开关切换主题。

- [ ] **Step 4: Commit**

```bash
git add web-ui/src/App.vue
git commit -m "feat(web): App.vue 布局外壳(侧栏+头+暗色模式)"
```

---

## Task 5: 任务页 Tasks.vue

**Files:**
- Modify: `web-ui/src/pages/Tasks.vue`

**Interfaces:**
- Consumes: `api.ts` 的 `submitTask`/`getReport`/`getStream`；`stores/tasks.ts` 的 `taskStore`/`addTask`。
- Produces: 任务提交表单 + 历史表格 + 详情抽屉（步骤时间线 + 报告 + status tag）。

- [ ] **Step 1: 重写 `web-ui/src/pages/Tasks.vue`**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { submitTask, getReport, getStream, type RunResult, type Step } from '@/api'
import { taskStore, addTask, type TaskRecord } from '@/stores/tasks'

const goal = ref('')
const targetRepo = ref('')
const submitting = ref(false)

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

async function onSubmit() {
  if (!goal.value || !targetRepo.value) {
    ElMessage.warning('请填写 goal 与 target_repo')
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
      <el-form-item label="目标仓库路径 (target_repo)">
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

- [ ] **Step 3: 浏览器验证**

起 `uvicorn`，打开 `/#/tasks`，见提交表单 + 空历史表格；提交一个任务（需配好 LLM key，否则后端报错——这是预期，前端应弹 error message）。

- [ ] **Step 4: Commit**

```bash
git add web-ui/src/pages/Tasks.vue
git commit -m "feat(web): 任务页(提交+历史+详情抽屉)"
```

---

## Task 6: 代码地图页 CodeMap.vue（d3-graphviz）

**Files:**
- Modify: `web-ui/src/pages/CodeMap.vue`

**Interfaces:**
- Consumes: `api.ts` 的 `getPackageDot`/`getClassDot`。
- Produces: 包图/类图切换 + package 过滤 + d3-graphviz 渲染 + DOT 源码折叠。

- [ ] **Step 1: 重写 `web-ui/src/pages/CodeMap.vue`**

```vue
<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { graphviz } from 'd3-graphviz'
import { getPackageDot, getClassDot } from '@/api'

const repo = ref('')
const kind = ref<'package' | 'class'>('package')
const pkg = ref('')
const dotSource = ref('')
const loading = ref(false)
const graphContainer = ref<HTMLDivElement>()

async function render() {
  if (!repo.value) {
    ElMessage.warning('请填写 repo 路径（或留空使用内置 demo-repo）')
  }
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
      <el-form-item label="Repo">
        <el-input v-model="repo" placeholder="留空用内置 demo-repo" style="width: 320px" />
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
Expected: 构建成功。若 `d3-graphviz` ESM 报错，在 `vite.config.ts` 的 `build.rollupOptions` 加 `external: []` 或在 `optimizeDeps.include` 加 `'d3-graphviz'`；若仍失败，回退方案：`index.html` 加 `<script src="https://unpkg.com/viz.js@2.1.2/viz.js"></script>`，组件内 `declare global { const Viz: (dot: string) => string }` 后 `graphContainer.value.innerHTML = Viz(dot)`。

- [ ] **Step 3: 浏览器验证**

起 `uvicorn`（设 `PROBE_DEMO_REPO` 指向 demo-repo），打开 `/#/map`，repo 留空 → 渲染 demo 仓包图；切类图、填 `com.demo` → 渲染类图；展开 DOT 源码。

- [ ] **Step 4: Commit**

```bash
git add web-ui/src/pages/CodeMap.vue
git commit -m "feat(web): 代码地图页(d3-graphviz 渲染包图/类图)"
```

---

## Task 7: HITL 审批页 Approval.vue

**Files:**
- Modify: `web-ui/src/pages/Approval.vue`

**Interfaces:**
- Consumes: `api.ts` 的 `approveTask`/`getDemo`；`stores/tasks.ts` 的 `taskStore`。
- Produces: 说明 alert + 任务选择 + 批准/拒绝 + 护栏确定性演示。

- [ ] **Step 1: 重写 `web-ui/src/pages/Approval.vue`**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { approveTask, getDemo } from '@/api'
import { taskStore } from '@/stores/tasks'

const selectedTaskId = ref('')
const guardrailResult = ref('')
const loading = ref(false)

async function onApprove(approve: boolean) {
  if (!selectedTaskId.value) {
    ElMessage.warning('请先选择任务')
    return
  }
  loading.value = true
  try {
    await approveTask(selectedTaskId.value, approve)
    ElMessage.success(approve ? '已批准' : '已拒绝')
  } catch (e) {
    ElMessage.error('操作失败: ' + (e as Error).message)
  } finally {
    loading.value = false
  }
}

async function runGuardrailDemo() {
  loading.value = true
  try {
    const d = await getDemo()
    guardrailResult.value = d.guardrail
  } catch (e) {
    ElMessage.error('演示失败: ' + (e as Error).message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-alert
    type="info"
    :closable="false"
    style="margin-bottom: 16px"
    title="说明"
    description="agent 主循环当前同步执行，此面板用于对已提交任务记录审批决策，并演示护栏对危险动作的确定性拦截。"
  />

  <el-card style="margin-bottom: 16px">
    <template #header>任务审批</template>
    <el-form inline>
      <el-form-item label="任务">
        <el-select v-model="selectedTaskId" placeholder="选择任务" style="width: 320px">
          <el-option
            v-for="t in taskStore"
            :key="t.task_id"
            :label="`${t.task_id.slice(0, 8)}… ${t.goal}`"
            :value="t.task_id"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="success" :loading="loading" @click="onApprove(true)">批准</el-button>
        <el-button type="danger" :loading="loading" @click="onApprove(false)">拒绝</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-card>
    <template #header>护栏确定性演示</template>
    <el-button type="primary" :loading="loading" @click="runGuardrailDemo">
      运行 rm -rf / 拦截演示
    </el-button>
    <el-alert
      v-if="guardrailResult"
      type="error"
      :closable="false"
      style="margin-top: 16px"
      :title="guardrailResult"
    />
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

- [ ] **Step 3: 浏览器验证**

起 `uvicorn`，打开 `/#/approval`，见说明 alert + 空任务选择 + 护栏演示卡；点"运行 rm -rf / 拦截演示" → 红色 alert 显示 `BLOCKED: ...`。

- [ ] **Step 4: Commit**

```bash
git add web-ui/src/pages/Approval.vue
git commit -m "feat(web): HITL 审批页(任务选择+批准/拒绝+护栏演示)"
```

---

## Task 8: 机制演示页 Demo.vue

**Files:**
- Modify: `web-ui/src/pages/Demo.vue`

**Interfaces:**
- Consumes: `api.ts` 的 `getDemo`。
- Produces: 三卡片（护栏/反馈闭环/无进展）+ 运行全部按钮 + 反馈闭环时间线。

- [ ] **Step 1: 重写 `web-ui/src/pages/Demo.vue`**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getDemo, type DemoResp } from '@/api'

const loading = ref(false)
const result = ref<DemoResp | null>(null)

async function runAll() {
  loading.value = true
  result.value = null
  try {
    result.value = await getDemo()
  } catch (e) {
    ElMessage.error('演示失败: ' + (e as Error).message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-card style="margin-bottom: 16px">
    <el-button type="primary" :loading="loading" @click="runAll">运行全部演示</el-button>
    <span style="margin-left: 12px; color: var(--el-text-color-secondary); font-size: 12px">
      纯 mock，无 key 无网络，确定性可复现
    </span>
  </el-card>

  <el-row :gutter="16" v-if="result">
    <el-col :span="8">
      <el-card>
        <template #header>① 护栏拦截</template>
        <el-alert type="error" :closable="false" :title="result.guardrail" />
      </el-card>
    </el-col>
    <el-col :span="8">
      <el-card>
        <template #header>② 反馈闭环</template>
        <el-timeline v-if="result.feedback_loop.length">
          <el-timeline-item v-for="(line, i) in result.feedback_loop" :key="i" :timestamp="`step ${i + 1}`">
            {{ line }}
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="无步骤" />
      </el-card>
    </el-col>
    <el-col :span="8">
      <el-card>
        <template #header>③ 无进展停机</template>
        <el-alert type="warning" :closable="false" :title="result.no_progress" />
      </el-card>
    </el-col>
  </el-row>
  <el-skeleton v-else-if="loading" :rows="6" animated />
</template>
```

- [ ] **Step 2: 构建验证**

Run:
```bash
cd web-ui
npm run build
```
Expected: 构建成功。

- [ ] **Step 3: 浏览器验证**

起 `uvicorn`，打开 `/#/demo`，点"运行全部演示" → 三卡片填充：① 红色 BLOCKED ② 时间线展示 write→patch→done ③ 黄色 BLOCKED_NO_PROGRESS。

- [ ] **Step 4: Commit**

```bash
git add web-ui/src/pages/Demo.vue
git commit -m "feat(web): 机制演示页(三卡片+反馈闭环时间线)"
```

---

## Task 9: Dockerfile 多阶段构建

**Files:**
- Modify: `Dockerfile`

**Interfaces:**
- Consumes: `web-ui/`（Task 3-8 产出）。
- Produces: 多阶段 Dockerfile，Stage 1 Node 构建前端 → Stage 2 Python 运行时含构建产物。

- [ ] **Step 1: 重写 `Dockerfile`**

```dockerfile
# Stage 1: 构建前端
FROM node:20-alpine AS frontend
WORKDIR /ui
COPY web-ui/package*.json ./
RUN npm install
COPY web-ui/ ./
RUN mkdir -p /probe/web/static && npm run build

# Stage 2: Python 运行时
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jdk maven graphviz && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/default-java
WORKDIR /app
COPY --from=frontend /probe/web/static ./probe/web/static
COPY pyproject.toml ./
COPY probe ./probe
COPY demo_mechanisms.py ./
COPY demo-repo ./demo-repo
ENV PROBE_DEMO_REPO=/app/demo-repo
RUN pip install --no-cache-dir -e ".[dev]"
EXPOSE 8000
CMD ["uvicorn", "probe.web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 本地构建验证（若 Docker daemon 运行）**

Run:
```bash
docker build -t probe .
```
Expected: 构建成功。若 daemon 未运行，跳过此步，依赖 CI `build-image` job 验证。

- [ ] **Step 3: 运行验证（若构建成功）**

Run:
```bash
docker run -p 8000:8000 probe
```
打开 `http://127.0.0.1:8000/`，应见完整 WebUI（侧栏 + 四页可切换）。

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "feat(docker): Dockerfile 改多阶段(Node 构建前端 + Python 运行时)"
```

---

## Task 10: README 重写

**Files:**
- Modify: `README.md`
- Test: `tests/test_readme_sections.py`（须保持绿）

**Interfaces:**
- Produces: 反映新 UI + 构建链的 README，保留强制章节与字符串。

- [ ] **Step 1: 重写 `README.md`**

完整内容如下（保留所有强制章节标题与字符串）：

````markdown
# Probe

## 简介

Probe 是一个**自实现的 Python coding-agent harness**，面向 Java 代码库。它不依赖任何外部 agent 框架（无 LangChain / AutoGen / smolagents），全部回路（LLM 调用、工具注册、护栏、校验、反馈、记忆）均由本仓手写，因此每一条机制都可被 mock 并被单测覆盖。

设计重心：
- **反馈闭环（首要）**：确定性校验（编译/测试/lint）→ 失败分类（compile/test/lint/none）→ 自修正（同签名连续 K 轮 FAIL 触发 `BLOCKED_NO_PROGRESS`，避免空转）。
- **代码地图（次要）**：基于 `javalang` 解析出包图 / 类图，计算影响闭包，供 agent 在改码前定位受影响范围。
- **安全边界**：API key 不进源码 / git / 日志；危险动作护栏 + HITL；路径围栏 `safe_path`；status 不回显明文 key。

WebUI 基于 Vue 3 + Vite + Element Plus，含四个页面：**任务**（提交 + 历史 + 步骤时间线）、**代码地图**（包图/类图 d3-graphviz 渲染）、**HITL 审批**（任务批准/拒绝 + 护栏演示）、**机制演示**（A.6 三大确定性机制）。

> 适用场景：在 Maven 管理的 Java 仓上做"让测试变绿"等可验证任务。Gradle 仅尽力而为。

## 安装

需要 Python ≥ 3.12，以及系统级 **JDK + Maven + graphviz**（校验器跑 `mvn`，图布局用 `graphviz`）。

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

macOS 示例（系统依赖）：

```bash
brew install openjdk@17 maven graphviz
```

前端开发（仅改 WebUI 时需要，运行时无需 Node——Docker 多阶段已构建）：

```bash
cd web-ui
npm install
npm run dev      # Vite 热重载 :5173, 代理 /tasks /map /demo 到 :8000
```

## 运行

单测（mock，无网络无 key）：

```bash
make test
```

配置 LLM key（首次运行引导会隐藏录入，使用 `getpass`，存入 Keychain；无 Keychain 时回退 `.env`）：

```bash
python -m probe init
```

跑一个任务（agent 闭环 + 反馈 + 自修正）：

```bash
python -m probe run --goal "让测试变绿" --repo /path/to/java-repo
```

生成代码地图（包图 / 类图 + 影响闭包）：

```bash
python -m probe map --repo /path/to/java-repo
```

### WebUI

启动：

```bash
uvicorn probe.web.app:create_app --factory
# 浏览器打开 http://127.0.0.1:8000/#/tasks
```

四个页面：
- **任务** (`/#/tasks`)：提交 goal + target_repo，查看历史任务的步骤时间线与最终报告。
- **代码地图** (`/#/map`)：渲染包图/类图（d3-graphviz），支持 package 过滤，可展开 DOT 源码。repo 留空时用内置 demo-repo。
- **HITL 审批** (`/#/approval`)：对已提交任务记录批准/拒绝决策；一键演示护栏对 `rm -rf /` 的确定性拦截。
- **机制演示** (`/#/demo`)：一键运行 A.6 三大确定性机制（护栏拦截 / 反馈闭环 / 无进展停机），纯 mock 无 key。

新端点 `GET /demo` 返回 `{guardrail, feedback_loop, no_progress}` JSON，供演示页调用。

机制演示（A.6，纯 mock，无 key 无网络，CLI 版）：

```bash
python demo_mechanisms.py
```

## WebUI 截图

> 部署后访问线上地址体验：https://probe-ho3d.onrender.com

- 任务页：提交表单 + 历史表格 + 详情抽屉（步骤时间线）。
- 代码地图：包图/类图 d3-graphviz 渲染 + DOT 源码折叠。
- HITL 审批：任务选择 + 批准/拒绝 + 护栏拦截演示。
- 机制演示：三卡片 + 反馈闭环时间线。

## 分发

### 获取源码

```bash
git clone https://github.com/ZengYYoung/probe.git
cd probe
```

### Docker

Dockerfile 为**多阶段构建**：Stage 1 用 `node:20-alpine` 构建前端（Vite → `probe/web/static/`），Stage 2 用 `python:3.12-slim` 装 JDK + Maven + graphviz 并运行 uvicorn。

```bash
docker build -t probe .
docker run -p 8000:8000 -v "$PWD/.env:/app/.env:ro" probe
```

容器内 **Keychain 不可用**，因此 key 必须以只读挂载 `.env` 的方式提供（建议本机 `chmod 600 .env`），或在目标机进入容器后执行 `python -m probe init` 录入。`.env` 为明文文件，进程环境可见，**生产环境请使用平台 secrets**（如 Render Environment / Fly Secrets / GitLab CI variables），不要把真实 `.env` 随镜像一起提交。

镜像内置 `demo-repo/`（一个含故意失败测试的小 Maven Java 工程），并设 `PROBE_DEMO_REPO=/app/demo-repo`，因此部署后 `/#/map` 与 `/map/package.dot` 不带 `repo` 参数即可直接渲染内置 demo 仓的结构图。

### Render（推荐：网页连 GitHub 仓，无需 CLI）

1. 注册 https://render.com（免费层即可）。
2. New → **Web Service** → 连接 GitHub 仓 `ZengYYoung/probe`。
3. Runtime 选 **Docker**（Render 自动识别 `Dockerfile`，多阶段构建自动执行）；端口 `8000`。
4. Environment Variables（可选，仅 `/#/tasks` 跑真实 agent 时需要）：`LLM_API_KEY`、`LLM_BASE_URL`。
5. Deploy → 得到公网 URL `https://probe-xxxx.onrender.com`。

**本项目线上地址**：https://probe-ho3d.onrender.com

部署后验证：访问根 `/` 见 WebUI；`/#/map` 渲染 demo 仓包图；`/#/demo` 运行三大机制演示。

### Fly.io（备选：有 CLI）

`fly.toml` 已配置：

```toml
app = "probe"
[build]
  dockerfile = "Dockerfile"
[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0
```

部署：

```bash
fly deploy
fly secrets set LLM_API_KEY=... LLM_BASE_URL=...   # 推荐，优于挂载 .env
```

### CI

GitHub Actions（`.github/workflows/ci.yml`）与 `.gitlab-ci.yml` 均含 `unit-test` job，只跑 mock 单测（`pytest -m 'not integration'`），不接触真实 key / LLM；`build-image` job 验证 Docker 多阶段构建（含前端 Vite 构建）。

## 目录结构

```
probe/
├── core/          # AgentLoop、Task、Status —— 闭环主循环
├── llm/           # LLM 抽象(base) + mock + OpenAI 兼容客户端
├── tools/         # 工具注册表 + fs(读写/路径围栏 safe_path) + shell
├── guardrail/     # 危险动作护栏 + HITL 确认
├── validators/    # 编译/测试/lint 校验 + pipeline + 失败分类 classifier
├── feedback/      # SelfCorrector：同签名连续 FAIL 触发 BLOCKED_NO_PROGRESS
├── codemap/       # builder(解析 Java) + graph + renderer(包图/类图 dot) + retriever(影响闭包)
├── memory/        # 会话记忆 store
├── report/        # 运行报告渲染
├── demo.py        # A.6 三个确定性机制演示（probe 包内，供 /demo 端点调用）
├── web/           # FastAPI + SSE + 图可视化 (app.py, static/)
│   └── static/    # Vite 构建产物（gitignored，保留 .gitkeep）
├── cli.py         # argparse 入口: init|run|map|creds
├── config.py      # Config 加载 (.env / 环境变量)
└── credentials.py # CredentialStore (Keychain 优先, .env 回退) + mask
web-ui/            # Vue 3 + Vite + Element Plus 前端工程（构建输出到 probe/web/static/）
demo_mechanisms.py # A.6 演示 CLI 入口（shim → probe.demo）
tests/             # 各模块 mock 单测
Dockerfile         # 多阶段: node:20-alpine 构建前端 + python:3.12-slim 运行时
fly.toml           # Fly.io 部署配置
.env.example       # 环境变量占位 (无真实 key)
```

## 安全边界

- **key 不进源码 / git / 日志**：`.gitignore` 已忽略 `.env`、`.env.*`（保留 `.env.example`）、`.probe/`、`*.key`、`*.pem`、`probe/web/static/*`（构建产物）、`web-ui/node_modules/`。
- **`.env` 明文风险**：`.env` 是明文文件，对进程环境可见，对同主机其它用户可能可读（建议 `chmod 600`）。容器内 Keychain 不可用，故容器场景必须挂载 `.env` 或用平台 secrets；**生产用 secrets**。
- **路径围栏 `safe_path`**：所有文件工具调用经 `safe_path` 校验，禁止越出 `--repo` 根目录的路径操作。
- **危险动作护栏 + HITL**：识别到危险命令（`rm -rf` / `git push --force` / 写入仓库外路径等）时拦截并要求人工确认（HITL）。
- **首次运行引导隐藏录入**：`probe init` 使用 `getpass.getpass`，终端不回显。
- **status 不回显明文**：`probe creds` 仅打印 `mask()` 后的形如 `sk-…abcd` 的掩码。
- **CI 只跑 mock 单测**：`unit-test` job 不解密、不注入真实 key，集成测试带 `integration` marker 默认被 deselect。

## 已知限制

- 构建系统深度支持 **Maven**；Gradle 仅尽力而为（调 `./gradlew` 但不解析依赖图）。
- `javalang` 对 Java 新语法（records / sealed / 模式匹配等）可能解析不全，遇此会退化为尽力而为的文本级处理。
- CI `unit-test` job 只跑 mock 单测；真实 LLM 闭环需本地或部署环境手动验证。
- 反馈闭环的 `BLOCKED_NO_PROGRESS` 阈值 K 为可调常量，过小会过早放弃，过大可能空转烧 token。
- WebUI 任务历史为客户端 localStorage 存储（进程内后端无任务列表端点）；agent 主循环同步执行，HITL 审批为"记录决策"语义，真实异步暂停属未来增强。

## 第三方依赖与许可证

| 依赖 | 用途 | 许可证 |
|---|---|---|
| pydantic | 配置 / 数据模型 | MIT |
| httpx | LLM HTTP 客户端 | BSD-3-Clause |
| keyring | 本机凭据存储 (Keychain) | MIT |
| javalang | Java 源码解析 | MIT |
| fastapi | WebUI / SSE | MIT |
| uvicorn | ASGI server | BSD-3-Clause |
| vue / element-plus / vite | WebUI 前端 | MIT |
| d3-graphviz | 浏览器内 DOT 渲染 | BSD-3-Clause |
| graphviz (系统) | dot 图布局 | CPL-1.0 (Eclipse) |

均为 MIT / BSD / Eclipse CPL 等宽松许可证。
````

- [ ] **Step 2: 运行 README 测试验证**

Run: `pytest tests/test_readme_sections.py -v`
Expected: 5 passed（含 `test_readme_has_required_sections`、`test_readme_has_docker_run`、`test_readme_has_make_test`、`test_env_example_no_real_key`、`test_fly_toml_exists`）

- [ ] **Step 3: 运行全量测试确认无回归**

Run: `make test`
Expected: 全绿

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: 重写 README(Vue3 WebUI 四页 + 多阶段 Docker + /demo 端点)"
```

---

## Self-Review

**1. Spec coverage:**
- §1 目标（Vue3+Vite+ElementPlus 四页 + /demo 端点 + Dockerfile 多阶段 + README 重写）→ Task 3-8（前端）、Task 2（/demo）、Task 9（Dockerfile）、Task 10（README）。✓
- §1.2 非目标（不重构内核、前端无 pytest、不改 CI YAML）→ Global Constraints + 各任务验证门。✓
- §1.3 硬约束（README 章节、端点契约、pyproject 打包、demo 导入）→ Global Constraints + Task 1（shim）、Task 2（不改契约）、Task 10（README 测试）。✓
- §2 架构（web-ui/ 位置、Vite outDir、Dockerfile 多阶段、CI 不变、.gitignore）→ Task 3（scaffold + .gitignore）、Task 9（Dockerfile）。✓
- §3 后端（/demo 端点、demo.py 重构）→ Task 1 + Task 2。✓
- §4 UI（布局 + 四页 + 暗色模式）→ Task 4（外壳）、Task 5-8（四页）。✓
- §5 README（强制章节 + 改动）→ Task 10。✓
- §6 测试（/demo 测试 + 保持绿 + 前端无 pytest）→ Task 2 Step 1 + 各前端任务构建验证。✓
- §7 文件清单 → File Structure 表。✓
- §8 风险（d3-graphviz 体积、demo 导入、暗色 graphviz、Vite 产物 gitignore）→ Task 6 Step 2（d3-graphviz 回退方案）、Task 1（shim）、Task 3（.gitignore）。✓

**2. Placeholder scan:** 无 TBD/TODO。Task 6 Step 2 含 d3-graphviz ESM 回退方案（具体代码），非占位。✓

**3. Type consistency:** `api.ts` 的 `DemoResp.feedback_loop: string[]` 与 `demo_feedback_loop() -> list`（list[str]）一致；`Step.decision` 可空与 `Decision | None` 一致；`RunResult.status: string` 与后端 `Status(str, Enum)` 的 `.value` 一致。✓

无缺口，计划完整。
