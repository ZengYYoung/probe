# Probe WebUI 重设计 + README 重写 设计文档

> 日期：2026-07-27
> 主题：将现有 60 行静态 HTML 的 WebUI 升级为 Vue 3 + Vite + Element Plus 的多页应用，并同步重写 README。
> 约束：不触碰 harness 内核（`probe/core`、`probe/llm`、`probe/tools`、`probe/guardrail`、`probe/validators`、`probe/feedback`、`probe/codemap`、`probe/memory`、`probe/report`），113 个单测保持全绿。

---

## 1. 目标与边界

### 1.1 目标
- 用 Vue 3 + Vite + Element Plus 重写 WebUI 前端，覆盖四个功能页：任务闭环、代码地图、HITL 审批、机制演示。
- 后端 `probe/web/app.py`（WebUI 外壳，非内核）新增 `GET /demo` 端点，包装 `demo_mechanisms.py` 的三个确定性演示。
- 重写 `README.md`，反映新 UI 与构建链变化，同时保留 `tests/test_readme_sections.py` 强制要求的章节与字符串。
- Dockerfile 改为多阶段构建（Node 构建前端 + Python 运行时）。

### 1.2 非目标（YAGNI）
- 不重构 agent 主循环以支持异步 HITL 暂停（`/approve` 仍为"记录决策"语义；真实 HITL 暂停属内核改动，风险高，不在本次范围）。
- 不为前端写 pytest 单测（前端非 harness 内核；CLAUDE.md 的 mock-LLM 单测纪律针对内核机制，`build-image` CI job 验证前端可编译即可）。
- 不改 CI YAML（`unit-test` job 只跑 pytest mock，无需 Node；`build-image` job 已构建 Docker，自动包含前端构建阶段）。
- 不加用户认证/多租户/持久化任务存储（WebUI 仍是单节点 dev/ops 面，进程内存储）。

### 1.3 硬约束（来自测试与配置）
- `tests/test_readme_sections.py` 要求 README 含章节：`## 简介`、`## 安装`、`## 运行`、`## 分发`、`## 目录结构`、`## 安全边界`，且含字符串 `docker run` 与 `make test`。
- `tests/web/test_app.py` 断言现有端点契约（`POST /tasks`、`GET /tasks/{id}/report`、`GET /tasks/{id}/stream`、`POST /tasks/{id}/approve`、`GET /map/package.dot`、`GET /map/class.dot`）——不得改其请求/响应形状。
- `pyproject.toml` 的 `include = ["probe*"]` 只打包 Python 包；前端源码须置于该包树之外。
- `tests/test_demo_mechanisms.py` 须继续通过（`demo_mechanisms.py` 模块导入路径不变或经 shim 保持兼容）。

---

## 2. 架构与构建集成

### 2.1 前端工程位置
`web-ui/` 置于仓库根（与 `probe/`、`tests/` 同级）。Vite 源码完全在 Python 包树之外，`setuptools.packages.find` 不会扫到它。

### 2.2 技术栈
- Vue 3（`<script setup>` SFC）
- Vite 5
- Element Plus（按需引入，`unplugin-vue-components` + `unplugin-auto-import`）
- Vue Router 4（history 模式，base `/`）
- `d3-graphviz`（浏览器内 DOT → SVG 渲染，支持缩放/平移）

### 2.3 构建产物
- `web-ui/vite.config.ts`：`build.outDir = '../probe/web/static'`，`build.emptyOutDir = true`。
- `npm run build` 直接写入 FastAPI 服务的静态目录；本地 `uvicorn` 无需额外拷贝。
- 本地热重载开发：`npm run dev`（Vite :5173），`vite.config.ts` 配 `server.proxy` 把 `/tasks`、`/map`、`/demo`、`/static` 代理到 `http://127.0.0.1:8000`。

### 2.4 Dockerfile（多阶段）
```dockerfile
# Stage 1: 构建前端
FROM node:20-alpine AS frontend
WORKDIR /ui
COPY web-ui/package.json web-ui/package-lock.json* ./
RUN npm ci
COPY web-ui/ ./
RUN mkdir -p /probe/web/static && npm run build
# outDir=../probe/web/static 相对 /ui 解析为 /probe/web/static

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

### 2.5 CI 影响
- `unit-test` job：不变（只跑 `pytest -m 'not integration'`，无需 Node）。
- `build-image` job：不变（已 `docker build`，自动跑多阶段）。
- 无 YAML 改动。

### 2.6 .gitignore 增补
```
probe/web/static/*
!probe/web/static/.gitkeep
web-ui/node_modules/
web-ui/dist/
```

---

## 3. 后端改动（仅 `probe/web/app.py` + 新 `probe/demo.py`）

### 3.1 新 `GET /demo` 端点
```python
@app.get("/demo")
def run_demo() -> dict:
    """运行 A.6 三个确定性机制演示（mock，无 key 无网络）。"""
    from probe.demo import demo_guardrail, demo_feedback_loop, demo_no_progress
    return {
        "guardrail": demo_guardrail(),
        "feedback_loop": demo_feedback_loop(),
        "no_progress": demo_no_progress(),
    }
```

### 3.2 `demo_mechanisms.py` → `probe/demo.py` 重构
- 将 `demo_mechanisms.py` 中三个函数与辅助函数移入 `probe/demo.py`（`probe` 包内，可被 `app.py` 正常 `import`）。
- `demo_mechanisms.py` 改为薄 shim：`from probe.demo import demo_guardrail, demo_feedback_loop, demo_no_progress  # noqa: F401`，保留 `if __name__ == "__main__"` 入口。
- `tests/test_demo_mechanisms.py` 现状是 `import demo_mechanisms as dm`（顶层模块导入）→ shim 保持该导入可用，`dm.demo_guardrail` 等经 re-export 可达。无需改测试。

### 3.3 不改的端点契约
`POST /tasks`、`GET /tasks/{id}/report`、`GET /tasks/{id}/stream`、`POST /tasks/{id}/approve`、`GET /map/package.dot`、`GET /map/class.dot` 的请求参数与响应 JSON 形状一律不变。

---

## 4. UI 布局与页面

### 4.1 整体布局
Element Plus `el-container`：
- `el-aside`：可折叠侧栏，顶部 "Probe" logo + 副标题 "Java 可行性 harness"，下方 `el-menu`（router 模式）四项：任务 / 代码地图 / HITL 审批 / 机制演示。
- `el-container`（纵向）：`el-header`（当前页标题 + GitHub 链接 + 暗色模式 `el-switch`）+ `el-main`（`<router-view>`）。

### 4.2 页面 1：任务（Tasks）
- 提交 `el-form`：`goal`（`el-input` textarea）+ `target_repo`（`el-input`，placeholder 提示可用 demo-repo 路径）→ `POST /tasks`。提交时 `el-button` loading。
- 任务历史 `el-table`：列 = task_id（截断前 8 位 + …）、goal（截断）、status（`el-tag`：SUCCESS=success / BLOCKED_NO_PROGRESS=danger / STOPPED_REJECTED=warning / STOPPED_BUDGET=warning / ERROR=danger）、操作（`el-button` 查看）。
- 详情 `el-drawer`：`el-timeline` 展示 steps（iteration / action.type / decision.reason）+ 最终报告 `el-card`（`final_failure_report` 的 JSON 友好展示）+ status tag。

### 4.3 页面 2：代码地图（CodeMap）
- `el-input` repo 路径（空则后端用 `PROBE_DEMO_REPO`）。
- `el-radio-group` 图类型：包图 / 类图。
- 类图时显示 `el-input` package 过滤（文本输入，无 packages 列表端点）。
- 渲染区：`d3-graphviz` 把 `GET /map/{package|class}.dot` 返回的 DOT 渲染为 SVG，支持缩放/平移。
- 折叠 `el-collapse`：DOT 源码 `el-input`（textarea readonly）供检视。

### 4.4 页面 3：HITL 审批（Approval）
- 顶部 `el-alert`（info）：说明 agent 主循环当前同步执行，此面板用于对已提交任务记录审批决策 + 演示护栏确定性拦截。
- 任务选择 `el-select`（从进程内任务 store 取）→ 展示该任务状态 + 任何被护栏拦截的动作（来自 step 的 decision.reason）。
- 批准 / 拒绝 `el-button` → `POST /tasks/{id}/approve`，body `{approve: true/false}`，响应后 `el-message` 提示。
- 确定性演示卡片：按钮 → 调 `/demo` 的 guardrail 部分 → 展示被拦截的 `rm -rf /` + reason。

### 4.5 页面 4：机制演示（Demo）
- 三个 `el-card`：① 护栏拦截 ② 反馈闭环 ③ 无进展停机。
- "运行全部演示" `el-button` → `GET /demo` → 填充三卡。
- ① 卡：展示 `BLOCKED: <reason>` 文本。
- ② 卡：`el-timeline` 展示 feedback_loop 返回的 step 列表（iteration / action / reason）。
- ③ 卡：展示 `BLOCKED_NO_PROGRESS: stopped after K rounds` 文本 + K 值。

### 4.6 暗色模式
- Element Plus 暗色主题 CSS 变量切换；状态存 `localStorage`。
- `d3-graphviz` 渲染区在暗色下用浅色节点边框适配。

---

## 5. README 重写范围

### 5.1 必须保留（测试强制）
章节标题：`## 简介`、`## 安装`、`## 运行`、`## 分发`、`## 目录结构`、`## 安全边界`。
字符串：`docker run`、`make test`。

### 5.2 改动
- **简介**：补一行说明新 WebUI（Vue 3 + Element Plus，四页：任务/地图/HITL/演示）。
- **安装**：新增前端开发安装（`cd web-ui && npm install`），明确运行时无需 Node（Docker 多阶段已构建）。
- **运行**：扩展 WebUI 子节，文档化四页 + 新 `/demo` 端点；保留 `make test`、`python -m probe ...`、`uvicorn` 命令。
- **分发**：注明 Dockerfile 现为多阶段（Node 构建 + Python 运行时）；保留 `docker run` 命令；Render/Fly 段不变。
- **目录结构**：加 `web-ui/` 条目；注明 `probe/web/static/` 为构建产物（gitignored，保留 `.gitkeep`）。
- **安全边界**：不变。
- 新增 **## WebUI 截图**（位于 运行 之后）：占位，构建后补截图。
- 更新 `.gitignore`（见 2.6）。

---

## 6. 测试

### 6.1 新增
`tests/web/test_demo_endpoint.py`：
- `GET /demo` 返回 200。
- 响应 JSON 含 `guardrail` / `feedback_loop` / `no_progress` 三键。
- `guardrail` 字符串含 `BLOCKED`。
- `no_progress` 字符串含 `BLOCKED_NO_PROGRESS`。
- mock，无 key 无网络，确定性。

### 6.2 保持绿
- `tests/web/test_app.py`：端点契约不变。
- `tests/test_demo_mechanisms.py`：shim 兼容或改导入路径，实现时确认。
- `tests/test_readme_sections.py`：README 保留强制章节与字符串。
- `make test` 命令不变。

### 6.3 前端
无 pytest 覆盖。`build-image` CI job 验证 Vite 构建可编译。

---

## 7. 文件改动清单

| 文件 | 改动 |
|---|---|
| `web-ui/`（新） | Vite 工程：`package.json`、`vite.config.ts`、`index.html`、`src/`（`main.ts`、`App.vue`、`router/index.ts`、`pages/*.vue`、`components/*.vue`、`api.ts`） |
| `probe/web/static/` | 改为构建产物；删除旧 60 行 `index.html`；加 `.gitkeep` |
| `probe/web/app.py` | 新增 `GET /demo` 端点（约 15 行） |
| `probe/demo.py`（新） | 从 `demo_mechanisms.py` 迁入三个演示函数 + 辅助 |
| `demo_mechanisms.py` | 薄 shim：`from probe.demo import *`，保留 `__main__` 入口 |
| `Dockerfile` | 多阶段：加 Node 构建阶段 |
| `.gitignore` | 增 `probe/web/static/*`（保留 `.gitkeep`）、`web-ui/node_modules/`、`web-ui/dist/` |
| `README.md` | 按 §5 重写 |
| `tests/web/test_demo_endpoint.py`（新） | `/demo` 端点测试 |

---

## 8. 风险与未决问题

- **`d3-graphviz` 体积**：约 1.5MB（含 viz.js wasm）。可接受，因 WebUI 是 dev/ops 面，非面向终端用户的高频访问。若体积敏感，后续可换 `viz.js` 精简版。
- **`demo_mechanisms.py` 导入路径**：`tests/test_demo_mechanisms.py` 用 `import demo_mechanisms as dm` 顶层导入。shim（`from probe.demo import *`）保持该导入可达，无需改测试。实现时确认 shim 在 pytest 运行目录下可被 `import demo_mechanisms` 解析（仓库根在 `sys.path`，conftest 已覆盖）。
- **暗色模式与 graphviz**：`d3-graphviz` 渲染的 SVG 默认浅色，暗色下需调 `fill`/`stroke`。实现时用 CSS 变量或 `d3-graphviz` 的 `convertEqualSidedPolygons` 等选项适配；若复杂，首版只做浅色，暗色为后续。
- **Vite 构建产物 gitignore**：`probe/web/static/` 不再进 git，部署靠 Docker 多阶段或本地 `npm run build`。Render 连 GitHub 仓时，Render 的 Docker 构建会跑多阶段，故无需把产物提交。
