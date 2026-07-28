# Probe

## 简介

Probe 是一个 **Java 代码分析工具**，通过读取项目源码并调用 DeepSeek LLM 生成结构化分析报告。同时提供代码地图可视化（包图/类图）和确定性机制演示。

核心功能：
- **代码报告**：上传 Java 项目 zip 或选择内置 demo，自动采集全部源码发给 DeepSeek，返回包含项目概述、代码结构、问题发现、改进建议的分析报告。支持自定义提示词。
- **代码地图**：基于 `javalang` 解析 Java 源码，渲染包图/类图（d3-graphviz），支持 package 过滤。
- **机制演示**：一键运行三大确定性机制（护栏拦截 / 反馈闭环 / 无进展停机），纯 mock 无需 key。

WebUI 基于 Vue 3 + Vite + Element Plus，三个页面：**代码报告**（选 repo → 分析 → markdown 报告）、**代码地图**（包图/类图交互渲染）、**机制演示**（A.6 三大确定性机制）。

> 线上地址：https://probe-rgw2.onrender.com

## 安装

需要 Python ≥ 3.12，以及系统级 **JDK + Maven + graphviz**（校验器用，图布局用 `graphviz`）。

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

前端开发（仅改 WebUI 时需要，运行时无需 Node——Docker 多阶段已构建）：

```bash
cd web-ui
npm install
npm run dev      # Vite 热重载 :5173
```

## 运行

单测（mock，无网络无 key）：

```bash
make test
```

### WebUI

启动：

```bash
uvicorn probe.web.app:create_app --factory
# 浏览器打开 http://127.0.0.1:8000/#/report
```

三个页面：
- **代码报告** (`/#/report`)：选择 repo（内置 demo 或上传 zip），点击「分析」，查看 LLM 生成的 markdown 报告。可展开自定义提示词输入框补充分析要求。
- **代码地图** (`/#/map`)：渲染包图/类图（d3-graphviz），支持 package 过滤，可展开 DOT 源码。repo 留空时用内置 demo-repo。
- **机制演示** (`/#/demo`)：一键运行 A.6 三大确定性机制（护栏拦截 / 反馈闭环 / 无进展停机），纯 mock 无 key。

上传 Java 项目：在代码报告页或代码地图页点「上传 zip」按钮，选择一个 `.zip` 压缩的 Java 仓。后端安全解压到临时目录（防 zip slip），返回的 path 自动填入选项。上传的 repo 在进程内存储，重启后失效（需重新上传）。大小限制 50MB。

内置 demo-repo 随 Docker 镜像或本地开发环境自动可用，无需上传。

### API

`POST /analyze` — 读取项目源码，发给 DeepSeek LLM，返回分析报告：

```bash
curl -X POST http://localhost:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"target_repo": "/path/to/java-repo", "prompt": "重点关注安全问题"}'
```

响应：`{"report": "### 1. 项目概述\n..."}`（markdown 格式）。

`GET /repos` — 列出可用 repo（内置 demo + 上传的 repo）。

`POST /repos/upload` — 上传 zip，返回 `repo_id` + `path`。

`GET /map/package.dot` / `GET /map/class.dot` — 代码地图 DOT 源码。

`GET /demo` — 机制演示 JSON。

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
docker run -p 8000:8000 \
  -e LLM_API_KEY=your-deepseek-key \
  probe
```

镜像内置 `demo-repo/`（一个含故意失败测试的小 Maven Java 工程），并设 `PROBE_DEMO_REPO=/app/demo-repo`，因此部署后 `/#/report` 与 `/#/map` 可直接使用内置 demo。

### Render

**本项目线上地址**：https://probe-rgw2.onrender.com

需在 Render Dashboard 设置环境变量：
- `LLM_API_KEY` — DeepSeek API key

默认 `LLM_BASE_URL` 已配置为 `https://api.deepseek.com`，模型为 `deepseek-v4-flash`。

### CI

GitHub Actions（`.github/workflows/ci.yml`）含 `unit-test` job，只跑 mock 单测，不接触真实 key / LLM。

## 目录结构

```
probe/
├── core/          # AgentLoop、Task、Status —— 闭环主循环（保留，报告模式不使用）
├── llm/           # LLM 抽象(base) + mock + OpenAI 兼容客户端（接入 DeepSeek）
├── tools/         # 工具注册表 + fs(读写/路径围栏) + shell
├── guardrail/     # 危险动作护栏 + HITL 确认
├── validators/    # 编译/测试/lint 校验 + pipeline + 失败分类 + 项目结构检测
├── feedback/      # SelfCorrector：同签名连续 FAIL 触发 BLOCKED_NO_PROGRESS
├── codemap/       # builder(解析 Java) + graph + renderer(包图/类图 dot) + retriever
├── memory/        # 会话记忆 store
├── report/        # 运行报告渲染
├── demo.py        # A.6 三个确定性机制演示
├── web/           # FastAPI + 图可视化 (app.py, static/)
│   └── static/    # Vite 构建产物（gitignored）
├── cli.py         # argparse 入口
├── config.py      # Config 加载 (默认 deepseek-v4-flash)
└── credentials.py # CredentialStore (Keychain 优先, .env 回退)
web-ui/            # Vue 3 + Vite + Element Plus 前端
demo_mechanisms.py # A.6 演示 CLI 入口
tests/             # 各模块 mock 单测
Dockerfile         # 多阶段: node + python
.env.example       # 环境变量占位
```

## 安全边界

- **key 不进源码 / git / 日志**：`.gitignore` 忽略 `.env`、`.env.*`、`.probe/`、`*.key`、`*.pem`。
- **路径围栏**：所有文件操作限定在 `target_repo` 之内（路径规范化后校验，防 `../` 越界）。
- **危险动作护栏**：识别到危险命令（`rm -rf` / `git push --force` / 写入仓库外路径等）时拦截。
- **zip slip 防护**：上传 zip 解压时校验每个文件路径，防止路径穿越攻击。
- **CI 只跑 mock 单测**：`unit-test` job 不解密、不注入真实 key。

## 已知限制

- LLM 分析报告依赖 DeepSeek API 可用性；API key 未配置时 `/analyze` 返回 502。
- 源码采集有大小限制（单文件 50KB，总量 300KB），超大项目会截断。
- 代码地图的 `javalang` 对 Java 新语法（records / sealed / 模式匹配等）可能解析不全。
- 上传的 repo 存储在进程内临时目录，重启后失效。

## 第三方依赖与许可证

| 依赖 | 用途 | 许可证 |
|---|---|---|
| pydantic | 配置 / 数据模型 | MIT |
| httpx | LLM HTTP 客户端 | BSD-3-Clause |
| keyring | 本机凭据存储 (Keychain) | MIT |
| javalang | Java 源码解析 | MIT |
| fastapi | WebUI API | MIT |
| uvicorn | ASGI server | BSD-3-Clause |
| vue / element-plus / vite | WebUI 前端 | MIT |
| marked | Markdown 渲染 | MIT |
| d3-graphviz | 浏览器内 DOT 渲染 | BSD-3-Clause |
| graphviz (系统) | dot 图布局 | CPL-1.0 (Eclipse) |

均为 MIT / BSD / Eclipse CPL 等宽松许可证。
