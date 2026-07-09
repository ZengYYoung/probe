# AGENT_LOG.md

> 按时间顺序记录关键节点。每条：时间戳 + task 编号 + 触发的 Superpowers 技能 + 关键 prompt/context 配置 + subagent 输出片段或 commit hash + 人工干预 + 教训。

## 进度账本

| Task | 状态 | implementer commit | reviewer 结论 | 备注 |
|---|---|---|---|---|
| T1 scaffold | ✅ | c49c593 | 内联快审✅ | 纯脚手架小 diff，按 model-selection 原则内联审；types/pyproject/Makefile 复核、make test 1 passed；deviation: 加 [build-system] 段（pip install -e . 必需，合理） |
| T2 config | ✅ | c6eef08 | 内联快审✅ | pydantic Config + load(path|None,env)；4 passed；dangerous_patterns 表按 §3.8 扩充(含路径越界/网络/破坏性SQL)，T10 可复用 |
| T3 credentials | ✅ | 4032ece | 内联快审✅ | keychain/file backend + mask；8 passed；file 后端原子写+chmod600；keychain 分支只抛 CredentialBackendUnavailable |
| T4 llm_base+mock | ✅ | 9bc887d | 内联快审✅ | pydantic LLM 抽象 + MockLLM 末帧钳位；9 passed；complete 返回 LLMResponse（修正了 PLAN 元组歧义） |
| T5 openai_compat | ✅ | 24a5015 | 内联快审✅ | OpenAICompatibleClient + _post 隔离；12 passed；异常 LLMError/LLMAuthError 放本文件；5xx重试路径未单测(YAGNI) |
| T6 toolbase | ✅ | 68465a8 | 内联快审✅ | ToolResult(pydantic)+Tool ABC+safe_path 围栏；16 passed；复用现有 Action 不重定义 |
| T7 fs | ✅ | 3befe10 | 内联快审✅ | Read/Write/Patch/ListFiles + safe_path 透传 PermissionError；21 passed |
| T8 shell | ✅ | 5492295 | 内联快审✅ | RunShell subprocess+timeout meta；25 passed |
| T9 registry | ✅ | f65e1f9 | 内联快审✅ | ToolRegistry.for_repo+dispatch；29 passed；**PLAN 笔误**：T9 测试把 content 当 Action 顶层 kwarg（pydantic 丢 extra）→ 改用 params={"content":..}（与 T5 一致），PLAN 文本待同步 |
| T10 guardrail | ✅ | 2ed40eb | 内联快审✅ | guardrail(action,cfg) 纯函数+Verdict；36 passed；文件类越界保守静态判定(绝对/含..)，safe_path 兜底 |
| T11 hitl | ✅ | bb16a67 | 内联快审✅ | State/Event str Enum + transition 纯函数非法抛 ValueError；40 passed；blocked 保留枚举无入迁移(后续扩展) |
| T12 valbase | ✅ | 8797385 | 内联快审✅ | pydantic Category(10)/Failure/FailureReport/Validator ABC + signature(sha1,用 category.value)；44 passed；冷启动 D1(无多余 Action import)+D3(pydantic)已落实 |
| T13 compile | ✅ | 4b8adf2 | 内联快审✅ | CompileValidator 解析 javac `[ERROR] file:[line] error:`；47 passed；runner 注入；UNAVAILABLE 分支 |
| T14 testval | ✅ | d3d2a7a | 内联快审✅ | TestValidator 解析 surefire TEST-*.xml(failure/error/skipped)；51 passed；__test__=False 抑制 pytest 误收 |
| T15 lint | ✅ | c5694b8 | 内联快审✅ | LintValidator 解析 checkstyle-result.xml；54 passed；产物缺失/runner异常→UNAVAILABLE |
| T16 pipeline | ✅ | c48435c | 内联快审✅ | ValidatorPipeline 短路+合并重算 signature+config 门控 lint；57 passed；**PLAN 矛盾**：test3 与短路互斥→方案1 改 compile PASS；pydantic 位置参数→关键字 |
| T17 classifier | ✅ | 7b316c1 | 独立 reviewer APPROVED | 冷启动修正版落地：validator 消歧+特化优先+不可变；63 passed；reviewer 确认规则顺序与不可变性；Minor: 冗余测试/缺 summary 断言(不阻塞) |
| T18 self_corrector | ✅ | 42f550c | 独立 reviewer APPROVED | 判据顺序 SUCCESS→BUDGET→NO_PROGRESS→CONTINUE；history[-K:].count；68 passed；reviewer 确认纯函数无 mutate |
| T19 codemap_graph | ✅ | bc1b7ac | 内联快审✅ | javalang 建图+extends/implements/associates/depends/imports 边+mtime 增量缓存+解析异常跳过；71 passed |
| T20 retriever | ✅ | 2b8df18 | 内联快审✅ | dependents/dependencies/affected_set BFS 反向闭包/responsibility 启发式；75 passed |
| T21 renderer | ✅ | 2f0379c | 内联快审✅ | 包图(聚合)/类图(extends实线+implements虚线) DOT + layout(dot)；79 passed；**PLAN 笔误**：CodeGraph 位置参数→关键字(pydantic v2) |
| T22 memory | ✅ | f54b7a7 | 内联快审✅ | Memory JSON 存(.probe/memory.json)，append/recent/conventions；84 passed；自实现不接框架 |
| T23 agentloop | ✅ | fd58444 | 独立 reviewer APPROVED | 自实现 while 循环串全链路+停机映射+guardrail 不执行危险动作；88 passed；Minor: pipeline changed_files=None/_build_tools 空/异常吞(后续改进) |
| T24 report | ⏳ | — | — | |
| T25 web | ⏳ | — | — | |
| T26 cli | ⏳ | — | — | |
| T27 demo | ⏳ | — | — | |
| T28 dockerfile+ci | ⏳ | — | — | |
| T29 readme+deploy | ⏳ | — | — | |

## 时间线

- **2026-07-08** brainstorming → SPEC.md（commit 85e7b6a）
- **2026-07-08** writing-plans → PLAN.md（commit b69beba）
- **2026-07-09** §4.5 冷启动（Codex，不同类型 agent）暴露 D1–D4，修订 SPEC/PLAN，写 SPEC_PROCESS.md（commit 3f93030）；CLAUDE.md 状态更新（9c90c48）
- **2026-07-09** 起飞前预检修复 5 处 PLAN 不一致（T2/T11/T15/T16/T25-T28）
- **2026-07-09** 开始 subagent-driven-development 实现
