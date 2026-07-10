# Probe

## 简介

Probe 是一个**自实现的 Python coding-agent harness**，面向 Java 代码库。它不依赖任何外部 agent 框架（无 LangChain / AutoGen / smolagents），全部回路（LLM 调用、工具注册、护栏、校验、反馈、记忆）均由本仓手写，因此每一条机制都可被 mock 并被单测覆盖。

设计重心：

- **反馈闭环（首要）**：确定性校验（编译/测试/lint）→ 失败分类（compile/test/lint/none）→ 自修正（同签名连续 K 轮 FAIL 触发 `BLOCKED_NO_PROGRESS`，避免空转）。
- **代码地图（次要）**：基于 `javalang` 解析出包图 / 类图，计算影响闭包，供 agent 在改码前定位受影响范围。
- **安全边界**：API key 不进源码 / git / 日志；危险动作护栏 + HITL；路径围栏 `safe_path`；status 不回显明文 key。

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

WebUI（FastAPI + SSE + 图可视化）：

```bash
uvicorn probe.web.app:create_app --factory
# 浏览器打开 http://127.0.0.1:8000
```

机制演示（A.6，纯 mock，无 key 无网络）：

```bash
python demo_mechanisms.py
```

## 分发

### 获取源码

```bash
git clone https://github.com/ZengYYoung/probe.git
cd probe
```

### Docker

```bash
docker build -t probe .
docker run -p 8000:8000 -v "$PWD/.env:/app/.env:ro" probe
```

容器内 **Keychain 不可用**，因此 key 必须以只读挂载 `.env` 的方式提供（建议本机 `chmod 600 .env`），或在目标机进入容器后执行 `python -m probe init` 录入。`.env` 为明文文件，进程环境可见，**生产环境请使用平台 secrets**（如 Render Environment / Fly Secrets / GitLab CI variables），不要把真实 `.env` 随镜像一起提交。

镜像内置 `demo-repo/`（一个含故意失败测试的小 Maven Java 工程），并设 `PROBE_DEMO_REPO=/app/demo-repo`，因此部署后 `/map/package.dot` 与 `/map/class.dot` 不带 `repo` 参数即可直接渲染内置 demo 仓的结构图。

### Render（推荐：网页连 GitHub 仓，无需 CLI）

1. 注册 https://render.com（免费层即可）。
2. New → **Web Service** → 连接 GitHub 仓 `ZengYYoung/probe`。
3. Runtime 选 **Docker**（Render 自动识别 `Dockerfile`）；端口 `8000`。
4. Environment Variables（可选，仅 `/tasks` 跑真实 agent 时需要）：`LLM_API_KEY`、`LLM_BASE_URL`。
5. Deploy → 得到公网 URL `https://probe-xxxx.onrender.com`。

**本项目线上地址**：https://probe-ho3d.onrender.com

部署后验证：访问根 `/` 见 WebUI；`/map/package.dot` 返回 demo 仓包图；`/map/class.dot?package=com.demo` 返回类图。

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

GitHub Actions（`.github/workflows/ci.yml`）与 `.gitlab-ci.yml` 均含 `unit-test` job，只跑 mock 单测（`pytest -m 'not integration'`），不接触真实 key / LLM；`build-image` job 验证 Docker 构建。

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
├── web/           # FastAPI + SSE + 图可视化 (app.py, static/)
├── cli.py         # argparse 入口: init|run|map|creds
├── config.py      # Config 加载 (.env / 环境变量)
└── credentials.py # CredentialStore (Keychain 优先, .env 回退) + mask
demo_mechanisms.py # A.6 三个确定性机制演示 (纯 mock)
tests/             # 各模块 mock 单测
Dockerfile         # python:3.12-slim + JDK + Maven + graphviz
fly.toml           # Fly.io 部署配置
.env.example       # 环境变量占位 (无真实 key)
```

## 安全边界

- **key 不进源码 / git / 日志**：`.gitignore` 已忽略 `.env`、`.env.*`（保留 `.env.example`）、`.probe/`、`*.key`、`*.pem`。
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

## 第三方依赖与许可证

| 依赖 | 用途 | 许可证 |
|---|---|---|
| pydantic | 配置 / 数据模型 | MIT |
| httpx | LLM HTTP 客户端 | BSD-3-Clause |
| keyring | 本机凭据存储 (Keychain) | MIT |
| javalang | Java 源码解析 | MIT |
| fastapi | WebUI / SSE | MIT |
| uvicorn | ASGI server | BSD-3-Clause |
| cytoscape (js, 经 web/static) | 图可视化前端 | MIT |
| graphviz (系统) | dot 图布局 | CPL-1.0 (Eclipse) |

均为 MIT / BSD / Eclipse CPL 等宽松许可证。
