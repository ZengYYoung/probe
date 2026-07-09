# SPEC.md — Probe: Java 可行性验证 Coding Agent Harness

> 工作代号 **Probe**（可改名）。一个**自实现的 Python coding-agent harness**，面向 Java 代码库：具备正常 coding agent 能力（读写文件、执行 shell、运行构建与测试），并在此之上以**反馈闭环**为重点深入维度——每次代码改动后跑确定性校验流水线，失败被分类后结构化回灌 LLM 驱动自修正，直到全绿或预算耗尽；同一份结构化结果渲染成人可读**可行性报告**辅助审查。次要深度为**代码地图**（包图/类图 + 影响面闭包 + 按需检索），辅助人理解项目代码层级的实现与设计以便修改优化。
>
> 上游权威：`作业要求.md`（通用）+ `AI4SE_Final_Project_A_Coding_Agent_Harness.md`（A 类专属）。本 SPEC 遵循其全部硬纪律，尤其 §A.4：harness 内核自己实现、机制是代码不是提示词、移除真实 LLM 后仍可确定性单测。

---

## 1. 问题陈述

**要解决的问题**：当 LLM 能完成大部分编码"思考"时，一个改动"到底行不行"仍需工程师手动跑构建/测试/lint、逐条读失败、判断影响面、再决定是否采纳。这个过程耗时且易漏。现有 coding agent 多停在"生成代码"，对"客观验证 + 失败可回灌 + 影响可呈现"这层工程做得不扎实，更少把结果结构化地交给人去理解和审查。

**目标用户**：
- 维护 Java 代码库的工程师，想让 agent 不只是"写代码"，而是"改完自己验、验完讲清楚哪儿不行、影响多大"。
- 本课程作业的评审者（验证 harness 内核是自实现、机制可单测）。

**为何值得做**：反馈闭环、影响面分析、代码地图这三件事，每一件都"机制可编码、确定性可验证"——恰好命中 §A.4 的判据，能把"工程师在 AI 协作中的价值"落在代码而非提示词上。它不是 demo：任何接 Java 仓做改动的人都能用它拿到一份"这改动可行吗 + 为何不可行 + 影响多大"的客观凭据。

## 2. 用户故事（INVEST）

1. **US-1 自修正到绿**：作为工程师，我给定一个 failing 测试集与一个 Java 仓，让 Probe 自主改代码直到测试全绿或耗尽预算，并拿到最终可行性报告，以便我不必手动逐条修。（Independent/Valuable/Estimable/Small/Testable）
2. **US-2 危险动作审批**：作为工程师，当 Probe 试图执行危险命令（如 `rm -rf`、`git push --force`、`mvn deploy`）时，它必须暂停等我审批，而非自行执行，以便我守住不可逆操作。（边界清晰，可单测）
3. **US-3 可行性报告**：作为审查者，我阅读 Probe 渲染的可行性报告（失败定位 file:line + 类别 + actual/expected + hint + 影响面），快速判断改动是否可采纳，而不必自己重跑校验。
4. **US-4 代码结构图**：作为新接手代码的工程师，我在 WebUI 点开包图/类图，快速理解项目结构与某模块的设计骨架，以便定位要改的位置。
5. **US-5 影响面缩范围**：作为工程师，Probe 改动若干文件后，只重跑受影响闭包内的测试（而非全量），既省预算又把"影响多大"客观呈现给我。
6. **US-6 安全配 key**：作为新机器用户，我首次运行 Probe 时被引导安全录入 API key（隐藏输入、不进 history），并随时可查看状态/更新/清除（查看不回显明文），以便我不担心 key 泄漏。
7. **US-7 一键运行与分发**：作为外部使用者，我单条 `docker run` 起来 Probe 的 WebUI 并安全配置自己的 key，以便零摩擦试用。

## 3. 功能规约（按模块）

> 每项：输入 / 行为 / 输出 / 边界 / 错误处理。所有"机制"均为代码函数，非提示词。

### 3.1 AgentLoop（内核主循环）
- 输入：`Task(goal, target_repo, budget)` + `Config` + `LLMClient`（可注入 mock）。
- 行为：组织上下文 → 调 `LLMClient.complete(messages, tools)` → 解析返回的动作 → `Guardrail` 检查 → 必要时转 HITL → `ToolRegistry` 分发执行 → 收集结果 → 调 `ValidatorPipeline` → 得 `FailureReport` → `SelfCorrector` 决定回灌或停机。
- 输出：`RunResult{status, steps[], final_failure_report, report_path}`，`status ∈ {SUCCESS, STOPPED_BUDGET, BLOCKED_NO_PROGRESS, STOPPED_REJECTED, ERROR}`。
- 边界：迭代上限 N、shell 累计时长上限、token 上限（见 Config）；超出即停。
- 错误处理：LLM 调用异常→重试 K 次后转 `ERROR`；动作解析失败→回灌"格式错误"要求重发；工具异常→捕获并回灌错误信息继续循环。

### 3.2 LLMClient（抽象层）
- 接口：`complete(messages: list[Message], tools: list[ToolSpec]) -> LLMResponse{actions[], raw, stop_reason}`。
- 实现：`MockLLM`（按预设脚本返回动作，确定性，单测用）、`OpenAICompatibleClient`（默认接 `LLM_BASE_URL` + `LLM_API_KEY`，兼容 njusehub glm-5.2 / OpenAI / DeepSeek 等）。
- 边界：不实现重试/退避之外的高层编排；不做 agent runner——只做单次补全。
- 错误处理：HTTP/超时/鉴权失败抛 `LLMError`，由 AgentLoop 决策。

### 3.3 ToolRegistry + 工具
- 工具：`ReadFile`、`WriteFile`、`PatchFile`（unified diff 或行替换）、`ListFiles`、`RunShell`（执行 `mvn`/`javac`/`gradle`/`checkstyle` 等，受 Guardrail 与 working-dir 围栏约束）。
- 输入/输出：每个工具 `(params) -> ToolResult{ok, stdout, stderr, exit_code, meta}`。
- 边界：所有文件操作限定在 `target_repo` 之内（路径规范化后校验，防 `../` 越界）；`RunShell` 命令经 Guardrail。
- 错误处理：路径越界→拒绝；命令超时→`TIMEOUT` 结果回灌。

### 3.4 ValidatorPipeline（重点深度）
- 输入：`target_repo`、`changed_files`（可选，用于缩范围）、`Config`（启用哪些校验器）。
- 行为：顺序跑 `CompileValidator`→`TestValidator`→`LintValidator`；短路规则：`Compile` FAIL 时 `Test` 跳过（无法编译则无测试可跑），`Lint` 总跑（独立于编译）。
- 输出：`FailureReport`（见 §6）。
- 边界：只读不改；每次跑在干净构建状态（先 `mvn clean` 或等价）以防残留；超时按 Config。**初版只深度支持 Maven**；Gradle 走相同 surefire/Test XML 解析但作"尽力而为"（R1）。
- 错误处理：校验器自身崩溃（如 mvn 未安装）→ 该 validator 标 `UNAVAILABLE` 并附原因，不阻断其余。

**校验器解析对象**（Maven 命令；Gradle 等价命令见 §10 R1）：
- Compile：`mvn -q -DskipTests test-compile`（或 `gradle compileTestJava`），解析 javac `file:line: error:` 与 `cannot find symbol`。
- Test：`mvn test`（或 `gradle test`），解析 `target/surefire-reports/TEST-*.xml` 的 `<failure>`/`<error>`/`<skipped>` + 断言文本 + 堆栈首帧。
- Lint：`mvn checkstyle:check`（或 checkstyle jar），解析 checkstyle XML 的 `<file><error line="" column="" severity="" message="" source=""/>`。

### 3.5 FailureClassifier（重点深度，纯函数）
- 输入：单条 `Failure`（含 `validator` 字段）。
- 行为：按**有序规则表**映射到 `category` + 生成 `hint`。规则模型 = `(validator_scope: str|None, pattern: str, category, hint)`；一条规则匹配当且仅当 `validator_scope is None or validator_scope == failure.validator` **且** `pattern`（正则、大小写不敏感）在 `"{message} {raw}"` 中命中。规则按表内顺序逐一检查，**首条匹配胜出**；无匹配 → `UNKNOWN` + 保留原文。
- **规则优先级（冷启动修正）**：必须先按 `validator` 字段消歧——`validator="test"` 的失败只在 `TEST_*` 类别中匹配，`validator="compile"` 只在 `COMPILE_*`/`DEPENDENCY_MISSING`/`BUILD_CONFIG_ERROR` 中匹配，`validator="lint"` 只在 `LINT_VIOLATION` 中匹配。**更具体的 pattern 必须排在更泛化的 pattern 之前**（例：`expected.*but was` 必须排在 `expected` 之前），避免泛化规则吞掉特化规则。
- 输出：`(category, hint)`，category 见 §6 taxonomy。
- 边界：纯函数，无 LLM、无 IO、无随机；同输入恒同输出；`classify` 与 `classify_report` 均**不得 mutate 入参**（`classify_report` 返回新的 `FailureReport` 与新的 `Failure` 对象）。
- 错误处理：无法分类→`UNKNOWN` + 保留原文，不抛异常。

### 3.6 SelfCorrector（闭环核心，确定性）
- 输入：`FailureReport` + 历史签名 + 剩余预算。
- 行为：把 `FailureReport` **结构化**序列化为 LLM 上下文片段（每条失败给 `file:line + category + actual/expected + hint`，附上轮改动摘要与剩余预算）；计算本轮 `FailureReport` 签名 hash；判停机。
- 输出：`Decision{action: CONTINUE|STOP, reason, context_fragment}`。
- 停机判据（全确定性）：
  - 全 validator `PASS` → `SUCCESS`。
  - 任一预算（迭代数/shell 累计时长/token）耗尽 → `STOPPED_BUDGET`。
  - 连续 `K` 轮签名不变（无进展） → `BLOCKED_NO_PROGRESS`。
  - 人拒绝危险动作 → `STOPPED_REJECTED`。
- 边界：签名只取失败集合的稳定 key（category+file+line+message 归一化），忽略顺序与无关字段。
- 错误处理：历史签名缺失→视为首轮，不触发无进展。

### 3.7 CodeMap（次要深度，自实现）
- 构建输入：`target_repo`。
- 构建：用 Python Java 解析库 `javalang`（属 A.4-A 允许的"解析库"）扫 `.java`，抽取包/类/接口/成员、`extends`/`implements`、字段类型、方法调用边、`import`。产出图 `CodeGraph{modules, types, edges}`，序列化 JSON 落盘；按文件 mtime 增量重解析。
- 检索（`CodeMapRetriever`，纯函数）：
  - `dependents_of(file)` / `dependencies_of(file)`
  - `affected_set(changed_files)`：以"被测类 ← 测试类"映射为锚，沿依赖闭包扩展，返回受影响文件 + 应跑的测试类集合（用于缩范围校验）。映射规则：测试类 `src/test/java/**/*Test.java` 默认对应同包被测类；可由 Config 覆盖。
  - `responsibility_of(package)`：命名启发式推断职责。
- 渲染（`DiagramRenderer`）：
  - 包图：节点=包，边=包间依赖（类级边聚合）。导出 DOT，graphviz `dot` 布局。
  - 类图：节点=类/接口，边=`extends`/`implements`/`associates`/`depends`。导出 DOT。
  - WebUI 前端用 cytoscape 交互式渲染（点包→展开类图；点类→高亮依赖/被依赖）。
- 边界：静态、保守——不做完整 UML 语义（可见性/多重性）、不做动态/反射调用解析、不做布局美学调优。
- 错误处理：单个文件解析失败→记录并跳过，不阻断整体；图缺失→AgentLoop 降级为全量校验并标记。

### 3.8 Guardrail（治理，纯函数）
- 输入：`Action{type, command/params}`。
- 行为：匹配危险规则表，返回 `Allow` 或 `Block(reason, needs_approval=True)`。
- 危险表（Config 可覆盖）：`rm -rf`、`git push --force`/`--force-with-lease`、`mvn deploy`/发布命令、删除 `.git`、写 `target_repo` 之外路径、网络外联命令、`DROP`/破坏性 SQL、`sudo`。
- 输出：`Verdict{allow: bool, reason}`。
- 边界：纯函数、确定性、无 LLM；白名单/黑名单均由 Config 提供。
- 错误处理：未知动作类型→`Block(unknown_action)`。

### 3.9 HITLStateMachine（治理，纯函数）
- 状态：`idle → proposing → awaiting_approval → executing → verifying → (blocked | done)`，外加 `rejected` 终态。
- 输入：事件 `ActionProposed`/`ApprovalGranted`/`ApprovalDenied`/`Executed`/`Validated`。
- 输出：新状态 + 是否允许执行。
- 边界：迁移表为常量，纯函数转移；非法迁移→`ERROR`。
- 错误处理：超时未审批（Config）→保持 `awaiting_approval`，可被人取消。

### 3.10 Memory（最低实现，自实现）
- 存储：项目约定（如"测试放 src/test/java"）+ 决策日志（每轮改动摘要 + 失败签名 + 决策）。JSON 文件落 `target_repo/.probe/memory.json`。
- 检索：按任务/时间查询；AgentLoop 注入"最近决策摘要"入上下文。
- 边界：不做向量检索、不做语义检索；只做键值/时间索引。
- 错误处理：读写失败→降级为无记忆，不阻断主循环。

### 3.11 Config（声明式）
- 来源：`probe.yaml`（仓内）+ 环境覆盖。字段：`validators{compile,test,lint}`、`budgets{max_iterations, max_shell_seconds, max_tokens}`、`guardrails{dangerous_patterns[], allowed_paths[]}`、`llm{model, temperature}`、`no_progress_rounds K`。
- 边界：纯数据载入与校验；未知字段告警不报错。
- 错误处理：缺字段→用文档化默认值并告警。

### 3.12 CredentialStore（必做）
- 首选 macOS Keychain（`keyring` 库或 `security` CLI）；`.env` 作 fallback。
- 操作：`set(key, value)`（`getpass` 隐藏录入）、`get(key)`（返回值，但 `status` 命令只回显掩码如 `sk-…abcd`）、`update`、`clear`、`status`。
- 边界：只管 `LLM_API_KEY` 与 `LLM_BASE_URL`；绝不写日志/终端 history/源码。
- 错误处理：Keychain 不可用→退回 `.env` 并明文告警；`.env` 缺失→引导首次录入。

### 3.13 ReportRenderer
- 输入：`FailureReport` + `affected_set` + `CodeGraph`（可选）。
- 行为：渲染人可读可行性报告——失败定位（file:line + category + actual/expected + hint）、影响面（受影响文件/测试数）、结构摘要。
- 输出：Markdown（CLI）+ JSON（WebUI 消费）。
- 边界：纯渲染，无副作用。

### 3.14 WebUI（必做）
- FastAPI 后端 + 静态前端。页面：① 任务提交；② 实时运行轨迹（步骤/工具调用/校验结果流式 SSE）；③ 可行性报告；④ 包图/类图交互（cytoscape）；⑤ HITL 审批弹窗。
- 边界：WebUI 不嵌进 AgentLoop 逻辑，只通过共享 `RunResult`/事件流消费；agent 内核不依赖 WebUI。
- 错误处理：SSE 断连→前端重连拉取快照。

## 4. 非功能性需求

- **性能**：单轮校验（中小 Java 仓）< 配置的超时；影响面闭包计算 < 1s；图构建按仓规模线性，增量更新 < 全量。
- **安全（含凭据威胁模型）**：见 §7。key 不进源码/git/日志/terminal history；`.env` 明文风险与进程环境可读风险须文档化；路径围栏防越界；危险动作护栏 + HITL。
- **可用性**：WebUI 一键起；CLI 子命令 `probe run|report|map|creds|init`；首次运行引导配 key。
- **可观测性**：每步动作/工具调用/校验结果写入结构化日志（不含 key）与 `AGENT_LOG.md`；运行轨迹可回放。

## 5. 系统架构

**组件图**（依赖方向 ↓）：
```
WebUI (FastAPI) ──┐
                   ├─→ AgentLoop ──→ LLMClient (Mock|OpenAICompatible)
                   │      │
                   │      ├─→ ToolRegistry → {ReadFile,WriteFile,PatchFile,ListFiles,RunShell}
                   │      ├─→ Guardrail → HITLStateMachine
                   │      ├─→ ValidatorPipeline → {Compile,Test,Lint}Validators
                   │      │        ↓
                   │      │   FailureReport → FailureClassifier
                   │      │        ↓
                   │      ├─→ SelfCorrector (回灌 + 停机判据)
                   │      ├─→ CodeMap {Retriever, DiagramRenderer}
                   │      ├─→ Memory
                   │      └─→ ReportRenderer
                   │
                   └─→ Config, CredentialStore
```
**数据流**：任务→AgentLoop→LLM 提议动作→Guardrail→[HITL]→Tool 执行→ValidatorPipeline→FailureReport→Classifier→SelfCorrector→(回灌|停机)→ReportRenderer→WebUI/CLI。

**外部依赖**：
- LLM 供应商：OpenAI-compatible 端点（默认 njusehub glm-5.2）。
- 外部工具：`mvn` 或 `gradle`、JDK、`checkstyle`、graphviz `dot`。
- Python 依赖：`javalang`、`keyring`、`fastapi`、`uvicorn`、`pytest`、`httpx`、`pydantic`、`cytoscape`（前端）。

## 6. 数据模型

```
Message{role, content, tool_calls?}
ToolSpec{name, description, input_schema}
Action{type: "shell"|"read"|"write"|"patch"|"list", command?/path?/params?}
ToolResult{ok, stdout, stderr, exit_code, meta}

Failure{
  validator: "compile"|"test"|"lint",
  severity: "error"|"warning",
  file: str, line: int|None,
  category: Category,        # 见下
  message: str, raw: str,
  hint: str
}
FailureReport{
  per_validator_status: {compile: "PASS"|"FAIL"|"UNAVAILABLE", ...},
  failures: list[Failure],
  signature: str,            # 稳定 hash，用于无进展检测
  summary: {category: count}
}

Category (taxonomy):
  COMPILE_SYNTAX | COMPILE_MISSING_SYMBOL | TEST_FAILURE | TEST_ERROR |
  TEST_MISSING | DEPENDENCY_MISSING | LINT_VIOLATION | BUILD_CONFIG_ERROR |
  TIMEOUT | UNKNOWN

CodeGraph{modules: list[Module], types: list[Type], edges: list[Edge]}
Edge{kind: "extends"|"implements"|"associates"|"depends"|"imports"|"calls", src, dst}
RunResult{status, steps: list[Step], final_failure_report, report_path}
Step{iteration, action, tool_result, failure_report?, decision}
```

> 全部数据模型用 **pydantic v2 `BaseModel`**（统一校验与 JSON 序列化，供 WebUI/API 直接消费）；`Category`/`Status`/`State` 用 `str` Enum。`Failure`/`FailureReport` 等值对象不得用 `dataclass` 替代。

## 7. 凭据与分发设计

**凭据存储方案**：`CredentialStore` 首选 macOS Keychain（`keyring` 库）；容器/无 Keychain 环境退回 `.env`（明文，须文档化风险）。
- **录入**：首次运行 `probe init` 用 `getpass` 隐藏输入 `LLM_API_KEY` 与 `LLM_BASE_URL`，写 Keychain。
- **查看**：`probe creds status` 只回显掩码（`sk-…abcd`），不回显明文。
- **更新/清除**：`probe creds update|clear`。
- **威胁模型与对策**：
  | 威胁 | 对策 |
  |---|---|
  | key 进源码/git | `.gitignore` 强制忽略 `.env`/`.probe/`；提交前自查脚本 |
  | key 进 shell history | 不用 `export`；用 `getpass`/Keychain；`RunShell` 不回显含 key 的命令 |
  | `.env` 明文被读 | 文档化"仅 fallback"；推荐 Keychain；`.env` 权限 `600` |
  | 进程环境被同机进程读 | 文档化风险；优先 Keychain 按需读取而非常驻 env |
  | 日志泄漏 | 日志过滤已知 key 字段；不打印 `LLMClient` 请求头 |

**分发形态**：Docker。
- `Dockerfile`：基于 `python:3.12-slim` + JDK + Maven + graphviz；`docker build` 单条产出镜像。
- `docker run` 单条启动 WebUI（暴露端口）。
- **key 在目标机安全配置**：容器内无 Keychain，**主推挂载只读 `.env`**（`docker run -v "$PWD/.env:/app/.env:ro"`，文件 `chmod 600`）；交互场景可用 `probe init` 录入到容器内临时存储。README 明确容器场景的明文风险与生产建议（用 Docker secrets / Fly secrets 而非挂载明文 `.env`）。
- **已知限制**：macOS Keychain 在容器内不可用；JDK/Maven 版本固定；目标 Java 仓须自行挂载进容器。
- CI 含 `build-image` job。

## 8. 技术选型与理由

- **harness 实现语言：Python**。迭代快、`pytest` 做 TDD 体验最佳、`subprocess` 调 `mvn`/`javac` 自然、`javalang`/`keyring`/`fastapi` 生态成熟；mock LLM 单测最顺手。与目标语言 Java 解耦，校验器通过 subprocess 调 Java 工具链。
- **目标语言：Java**。JUnit surefire XML 结构化、javac 错误格式稳定、checkstyle XML 规范，便于确定性解析与分类；课程项目多 Java，贴实际审查需求。只做一种以保深度。
- **LLM 供应商：OpenAI-compatible 抽象层，默认 njusehub glm-5.2**。复用已有端点与 key，兼容性最广（可换 OpenAI/DeepSeek 等）；抽象层使单测可用 MockLLM 完全离线运行。
- **分发：Docker**。单条 build/run、CI 可构建、环境自洽（JDK/Maven/graphviz 内置）。
- **部署：Fly.io 或 Render**（优先免费额度），提供公网 WebUI URL。
- **重点深入维度：反馈闭环**。最契合 §A.4"机制是代码、可 mock 单测"，闭环真正闭合（失败→分类→回灌→改下一步→无进展检测）。
- **次要深度：代码地图**。直接满足"辅助人理解代码层级"，且存储/检索/渲染全自实现。
- **前端**：WebUI 为必须交付（清单第 9 项），用轻量静态前端 + cytoscape 图渲染；非复杂 UI 项目，按通用要求 §3.4 可豁免 Open Design，但若需 UI 设计系统将补说明。

## 9. 验收标准

- **AC-1（自实现内核）**：`AgentLoop`/`LLMClient`/`ToolRegistry`/`Guardrail`/`HITLStateMachine`/`ValidatorPipeline`/`FailureClassifier`/`SelfCorrector`/`CodeMap`/`Memory`/`Config`/`CredentialStore` 均为本仓代码；不依赖 LangChain/AutoGen/CrewAI/LlamaIndex agent 或任何 agent runner。
- **AC-2（机制可单测）**：上述每个机制在 `MockLLM` 下有确定性单测通过；`make test` 一键跑、无网络无 key。
- **AC-3（机制演示）**：`demo_mechanisms.py` 在 mock LLM 下复现 ①护栏拦截危险动作 ②注入失败触发自修正改下一步 ③无进展检测触发 `BLOCKED_NO_PROGRESS`。
- **AC-4（真实端到端）**：给定一个含 failing 测试的小 Java 仓，真实 LLM 下 Probe 能自主修正到绿或合理停机，并产出可行性报告。
- **AC-5（代码地图）**：包图/类图可交互渲染；`affected_set` 闭包计算与"只跑受影响测试"行为可单测。
- **AC-6（凭据）**：`probe init` 引导录入；`status` 不回显明文；`update`/`clear` 可用；Keychain 不可用时退回 `.env` 并告警。
- **AC-7（分发）**：单条 `docker build` + `docker run` 起来 WebUI；README 写清获取/运行/key 配置/限制。
- **AC-8（WebUI+部署）**：公网可访问 WebUI，含运行轨迹/报告/图/HITL 审批。
- **AC-9（CI）**：`.gitlab-ci.yml` 含 `unit-test` job 且最后一次 pass。

## 10. 风险与未决问题

- **R1 mvn/gradle 双构建系统**：初版只深度支持 Maven，Gradle 作"尽力而为"（解析相同 surefire/Test XML）。SPEC 标注，避免承诺过宽。
- **R2 javalang 维护性与 Java 新语法**：`javalang` 对 records/密封类等新语法可能解析不全→降级跳过该文件并告警，不阻断。
- **R3 影响面闭包过保守或过大**：静态依赖闭包可能漏动态调用或多报→明确"保守优先，多跑不漏"，文档化。
- **R4 LLM 不遵循结构化反馈**：反馈闭环依赖 LLM 据结构化 `FailureReport` 决策；若 LLM 忽略→靠无进展检测兜底转人，不硬撑。
- **R5 容器内 Keychain 不可用**：已设计 `.env` 退回与明文风险文档化；未决——是否支持容器 secrets（如 Docker secrets / Fly secrets）作为更优路径，实现阶段决定。
- **R6 CI 平台**：通用要求 §4.7/4.8 写 GitHub Actions，清单第 6 项要 `.gitlab-ci.yml` + `unit-test` job 且走 NJU Git。**未决**：以 NJU GitLab 为主仓 + `.gitlab-ci.yml`，GitHub 镜像另配 Actions；待向助教澄清后回填 `CLAUDE.md`。
- **R7 范围蔓延**：代码地图易越做越深（完整 UML/动态分析）。以 §3.7 边界为硬约束。

## 11. 领域与机制设计（A.5 专属）

**领域（coding）的四类机制**：
- **动作/工具**：读写文件、Patch、列目录、RunShell（mvn/javac/gradle/checkstyle）。→ §3.3。
- **客观反馈信号**：Compile/Test/Lint 的结构化产物（javac 错误行、surefire XML、checkstyle XML），客观、确定、可回灌。→ §3.4–3.5。
- **危险动作**：`rm -rf`、`git push --force`、`mvn deploy`、删 `.git`、路径越界、网络外联、破坏性 SQL、`sudo`。→ §3.8–3.9。
- **记忆**：项目约定 + 决策日志（JSON，键值/时间索引，自实现，不接框架 memory）；代码地图作为结构化"代码库知识"按需载入。→ §3.7、§3.10。

**重点维度与为何**：反馈闭环。理由——它天然由代码构成（校验器=解析器、分类器=纯函数、停机=hash 比较），闭环真正闭合且多轮自修正可观测，最契合 §A.4-C"移除 LLM 后仍可单测"。次要维度选代码地图，因为它把"按需提供上下文而非全量载入"也落成确定性代码（影响闭包 + 检索），同样可 mock 单测，并直接满足用户"辅助人理解代码层级"诉求。

**机制如何编码实现（呼应 §A.4）**：
- 反馈信号 = `ValidatorPipeline`（解析产物→填 `FailureReport`）+ `FailureClassifier`（纯函数分类）+ `SelfCorrector`（结构化回灌 + 确定性停机）。非提示词"让 LLM 自检"。
- 危险动作拦截 = `Guardrail(action)` 纯函数 + `HITLStateMachine` 状态转移表。非提示词"提醒 LLM 注意安全"。
- 记忆 = `Memory` JSON 存储 + `CodeMapRetriever` 闭包/检索纯函数。非框架 memory。
- **判据自检**：移除真实 LLM 换 `MockLLM` 后，AgentLoop 仍可被驱动跑完整闭环（MockLLM 按脚本提议动作）、ValidatorPipeline 喂构造 surefire XML、Classifier 喂构造 raw、SelfCorrector 喂构造 `FailureReport`、Guardrail 喂构造 Action、CodeMap 喂构造 AST——每个机制均有确定性单测，满足 §A.4-C。
