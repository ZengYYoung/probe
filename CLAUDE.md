# CLAUDE.md — 项目一致性基准

> 本文件是本项目（AI4SE 期末项目 · A · Coding Agent Harness）的一致性基准。
> 任何会话、任何 subagent 在动手前都应先读本文件，确保不偏离下列硬性纪律。
> 上游权威文件：`作业要求.md`（通用要求）+ `AI4SE_Final_Project_A_Coding_Agent_Harness.md`（A 类专属）。本文件是它们的提炼与执行约束，冲突以上游为准。

---

## 1. 项目本质

交付一个**由我自己编码实现的 Coding Agent Harness**。

- 核心等式：**Agent = LLM + Harness**。LLM 只决定"下一步做什么"；其余（组织上下文、调用、解析、分发、回灌、治理、记忆、停机）都是工程，必须落在我的代码里。
- 命题：用 Superpowers（一个现成 harness）去**造另一个 harness**，并对其工程化全过程负责。
- 关注点：当 LLM 能完成大部分编码时，工程师的价值落在 harness 这层（治理 / 反馈 / 上下文 / 安全 / 分发），而非提示词。

## 2. 不可妥协的硬纪律（直接关系评分）

### 2.1 Harness 内核必须自己实现（A.4-A）
**必须自己实现**：
- agent 主循环：组织上下文 → 调用 LLM → 解析动作 → 分发执行 → 回灌结果 → 停机判断。
- 可注入 mock 的 **LLM 抽象层**（mock 用于离线测试，也可接真实供应商）。

**允许使用底层零件**：LLM 供应商单次对话补全 API、HTTP 库、向量库、解析库。

**禁止**：把项目建在现成 agent 编排框架的高层循环之上——`LangChain AgentExecutor`、`AutoGen`、`CrewAI`、`LlamaIndex agent`、或某编码智能体 SDK 自带的 agent runner。把这些零件组装成"循环 + 治理 + 反馈"必须由我的代码完成。

> 澄清界线：开发工具（Claude Code / Codex / Cursor / Gemini CLI 等 + Superpowers 的 subagent / Skill / hooks / memory / 内置工具）是**辅助我写代码**的，鼓励充分使用。约束只针对**交付的 harness 内核**：那部分必须是我的代码，不能让宿主框架代替我所构建的机器运转。

### 2.2 机制必须是代码，不是提示词（A.4-B）
- 反馈信号 = 我写的**校验器 / 传感器**（解析产物 → 客观判定 → 回灌循环），不是"让 LLM 自检"的一句提示。
- 危险动作拦截 = 我写的**护栏**函数（识别 → 拦截 → 要求人工确认），不是"提醒 LLM 注意安全"的一句提示。
- 对照样例：`guardrail(Action(command="rm -rf /"))` 必须可被断言拦截，且无需真实 LLM 即每次成立。

### 2.3 判据：移除真实 LLM 后还能用单测验证（A.4-C）
- harness 每个核心机制（工具分发、治理拦截、反馈回灌、记忆读写、停机），替换为 mock / stub LLM 后，**仍能用确定性单测验证** —— 才算我编码实现的机制。
- 一旦离开真实 LLM 就无法测试的"机制"（本质是依赖 LLM 智能的提示词）**不计入** harness 实现工作量。
- 配置文件 / 规则文件 / 技能 / 提示词文件都属于"内容物"，不计入 harness 实现工作量。

### 2.4 基础完整 + 一个维度深入（A.4-D）
六维度（决策 / 工具 / 记忆 / 治理 / 反馈 / 配置）都要有**可运行的最低实现**——缺一项 harness 不成立。但**选一个机制密集维度深入**作为主要贡献，不要六维都浅尝。
- 建议重点：**治理**（护栏 / 沙箱 / HITL 状态机 / 范围围栏）、**反馈闭环**（确定性校验器 + 失败分类 + 多轮自修正）、**扩展**（工具分发 / 多 agent 编排）。
- 若以记忆 / 上下文工程为重点，存储与检索必须自己实现，不得直接接框架自带 memory。
- **本项目重点维度**：[待 brainstorming 阶段确定并回填此处]

### 2.5 必须设计的四类机制（A.3）
在 SPEC 中明确回答：
- **动作 / 工具**：读写文件、执行 shell、运行构建与测试。
- **客观反馈信号**：运行测试 / lint / 类型检查，客观、确定、可回灌。
- **危险动作**：删库、危险 shell、对外发布等，须暂停交人工审批，边界明确。
- **记忆**：跨会话记项目约定 / 历史决策 / 代码库知识，按需提供而非全量载入。

## 3. Superpowers 工作流（七步，必须如实遵循）

`brainstorming` → `writing-plans` → `using-git-worktrees` → `subagent-driven-development` / `executing-plans` → `test-driven-development` → `requesting-code-review` → `finishing-a-development-branch`

- **在 SPEC 与 PLAN 完成并通过冷启动验证之前，禁止编写任何实现代码。**
- 允许合理偏离，但偏离必须记入 `AGENT_LOG.md` 并解释。
- TDD 硬性：先红、再绿、再重构。不接受"先写实现再补测试"。
- 每个 task 派一个**新鲜 subagent** 完成单一任务；每 task 后做**两阶段评审**（先 spec 合规 → 再代码质量），Critical issue 必须修复才进下一 task。
- 每个独立功能 / 大模块开一个 git worktree，对应一个 PR。

## 4. 冷启动验证（最关键的客观证据）

正式实现前，用**与主开发 agent 不同类型**的第二个 agent，在**全新 session、不导入任何会话 / memory、仅给 SPEC + PLAN、不补充口头解释**的前提下，让它从 PLAN 选 1–2 个 task 自主推进 1–2 小时，并明确"遇到不确定即暂停询问，而非凭猜测继续"。
- 记录到 `SPEC_PROCESS.md`：第二个 agent 在哪里暂停提问、暴露了哪些 spec 缺陷、做出哪些与原意不一致的解读、产出差距、据此对 SPEC/PLAN 做的修订（附关键 diff）。

## 5. 凭据 / API Key 安全（3.1 必做）

- key **绝不**硬编码进源码、**绝不**进 git（含历史）、**绝不**写日志 / 终端 history / 明文配置。
- 至少一种安全存储：macOS Keychain / Windows Credential Manager / Linux Secret Service / KMS / 带主密码的加密文件。
- 环境变量须经 `.env` 加载（非 `export`，避免进 shell history），并在 SPEC 说明 `.env` 明文 + 进程环境可见的风险。
- 首次运行**引导安全录入**（隐藏输入），可查看 / 更新 / 清除（查看时不回显明文）。
- SPEC 安全一节须写明凭据威胁模型与对策。

## 6. 分发（3.2 必做）

回答"别人如何获取并运行，且如何安全配置自己的 key"。任选一种或多种：容器镜像 / 原生二进制 / 包管理器。
- README 必须写清：获取方式、运行命令、key 在目标机的安全配置、已知限制（平台 / 架构 / 依赖前提）。
- CI 须包含相应构建步骤。
- **本项目分发形态**：[待 brainstorming 阶段确定并回填]

## 7. WebUI 与部署（硬要求）

- 最终交付清单第 9 项：**必须提供应用可访问的 WebUI 接口** + 线上部署 URL。
- 即便核心是 CLI harness，也要包一层 WebUI 供公网访问。
- 可选 Vercel / Render / Railway / Fly.io / 阿里云 / 腾讯云（优先免费额度，控制成本）；README 写部署架构与 CI/CD。

## 8. 测试与 CI

- **harness 核心机制必须有 mock / stub LLM 驱动的确定性单测**，不依赖网络与真实 LLM（A.6）。
- **机制演示**（A.6）：mock LLM 下确定性复现 ① 治理护栏拦截危险动作；② 注入一次失败，反馈闭环使 agent 收到反馈并改变下一步；③ 重点维度的一个确定性行为。可以是测试用例或可重复脚本。
- 必须有**一键运行测试**命令（`make test` 或等价），覆盖核心功能。
- CI 必须配置，每次 push 自动跑测试；若选容器分发，CI 还须构建镜像。

### ⚠ 要求内部矛盾，须澄清
- §4.7 / §4.8 写"公开 GitHub 仓库 / GitHub Actions"；
- §五清单第 6 项写"CI 配置（`.gitlab-ci.yml`），必须包含名为 `unit-test` 的 job"，且"通过同一个 NJU Git 仓库链接提交"。
- **暂定执行**：主仓库用 NJU GitLab（GitLab CI，`.gitlab-ci.yml`，含 `unit-test` job）；若同时在 GitHub 镜像，则另配 `.github/workflows/*.yml`。**此项需向助教澄清后回填本文件。**

## 9. 交付物清单（§五 + A.7）

通过同一个 NJU Git 仓库链接提交：
1. `SPEC.md`、`PLAN.md`、`SPEC_PROCESS.md`。
2. 完整源代码（规范 commit / PR 历史，无任何真实凭据）。源码须含**自己实现的 harness 内核** + 覆盖这些机制的 **mock-LLM 单测**。
3. 分发产物与说明（`Dockerfile` / 二进制构建脚本 / 打包配置）；README 写清获取、运行、key 安全配置、已知限制。
4. `README.md`：项目简介、安装、运行、分发命令、目录结构、安全边界说明（**这些章节必须齐**）。
5. `AGENT_LOG.md`：按时间序记录关键节点（时间戳 + task 编号 + 触发的 Superpowers 技能 + 关键 prompt/context 配置 + subagent 输出片段或 commit hash + 人工干预 + 教训）。
6. CI 配置（`.gitlab-ci.yml`），**必须**含 `unit-test` job。
7. CI/CD 执行记录，**最后一次必须 pass**。
8. `REFLECTION.md`（1500–2500 字，本人撰写，禁止 AI 代写，可 AI 辅助润色但需标注）。
9. 线上部署 URL，**必须**提供可访问 WebUI 接口。
10. §A.6 机制演示。

## 10. SPEC.md 必含结构（§4.2 + A.5）

1. 问题陈述（解决什么 / 目标用户 / 为何值得做）
2. 用户故事（≥5 个，INVEST 原则）
3. 功能规约（按模块：输入 / 行为 / 输出 / 边界 / 错误处理）
4. 非功能性需求（性能 / 安全含凭据威胁模型 / 可用性 / 可观测性）
5. 系统架构（组件图 / 数据流 / 外部依赖含 LLM 供应商）
6. 数据模型（实体 / 字段 / 关系 / 约束）
7. 凭据与分发设计（key 存储方案与录 / 更 / 清流程；分发形态 / 平台 / 目标机 key 配置）
8. 技术选型与理由（语言 / 框架 / LLM 供应商 / 分发部署；含前端须说明 Open Design 设计系统与 skill —— 本项目 WebUI 如需 UI 可考虑）
9. 验收标准（每功能客观判定）
10. 风险与未决问题（可能让智能体出问题的环节）
11. **领域与机制设计（A.5 专属）**：coding 领域的反馈信号 / 危险动作 / 所需工具 / 记忆需求；哪个维度作重点、为什么；这些机制如何编码实现（呼应 A.4）。

## 11. 技术选型（待 brainstorming 阶段确定并回填）

- **开发智能体 / Superpowers 宿主**：Claude Code。Superpowers v6.1.1 已安装并启用（user 作用域，14 技能齐全）。
- 语言 / 框架：[待定] —— 任选，需在 SPEC 说明理由。
- LLM 供应商：[待定] —— 任选，需在 SPEC 说明理由；harness 通过抽象层接入，单测用 mock。
- 重点深入维度：[待定]
- 分发形态：[待定]
- 部署平台：[待定]

## 12. 学术规范

- 自己手写的核心代码（如主循环、护栏、校验器）在该文件 / 函数顶部明确注释标注。
- 第三方代码遵守许可证，README 列出。
- `REFLECTION.md` 本人撰写，禁止 AI 代写（可辅助润色，需标注）。

## 13. 当前状态与下一步

- [x] 读完通用要求 + A 类专属要求，建立本一致性基准。
- [x] 确认开发智能体 = Claude Code，Superpowers v6.1.1 已安装启用。
- [x] 初始化 git 仓库（本地 `main`）。GitHub 账号暂未登录 → 全流程本地跑；账号恢复后再加 remote 推送。
- [x] CI 配置（`.gitlab-ci.yml` 含 `unit-test` job）与"最后一次 CI pass"为最终交付硬要求，可后补。
- [x] brainstorming → `SPEC.md`（Probe: Java 可行性验证 harness；重点=反馈闭环，次要=代码地图）。
- [x] writing-plans → `PLAN.md`（29 个 TDD task）。
- [x] 冷启动验证（§4.5）：用 **Codex**（不同类型 agent）零背景跑 T12+T17，暴露 4 个缺陷（D1 多余 import / D2 分类规则优先级与 validator 消歧未定 / D3 pydantic 未钉死 / D4 classify_report mutate），已修订 SPEC/PLAN 并写 `SPEC_PROCESS.md`。证据分支 `coldstart/codex` 保留不合入。
- [x] 实现：`subagent-driven-development` —— 29 个 task 全部完成（每 task 一个 implementer subagent + 内联快审/独立 reviewer；T17/T18/T23/T27 用独立 reviewer）。**113 测试全绿**。整支 code review APPROVED：A.4 自实现✅、机制代码化✅、凭据安全✅、集成✅、测试非空断言✅、路径围栏✅、pydantic 一致✅。`REFLECTION.md` 已写。
- [ ] **待远程条件补齐**（用户 GitHub 账号暂不可用，已约定后补）：
  - 推送到 NJU GitLab / GitHub remote；
  - `.gitlab-ci.yml` 的 `unit-test` job 实际跑一次并 pass（本地 `make test` 已 113 passed 绿）；
  - `docker build .` 手动验证（本机 daemon 未运行）；
  - 部署到 Fly.io/Render 取得公网 WebUI URL（`fly.toml` 已就绪）。
- [x] 已知限制（见 REFLECTION §已知限制）：`RunShell shell=True` 仅 Guardrail 单围栏；仅 Maven 深度支持；demo 反馈因果在 offline mock 下无法严格证明。

> 工作纪律：凡涉及"做什么 / 做对了吗"的判断，由我（学生）主导；Superpowers 守住"怎么做"的流程脚手架。不要把题目原封不动交给智能体再把结果原封不动交上来。
