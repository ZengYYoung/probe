# REFLECTION.md

> 本反思报告由学生本人撰写，可用 AI 辅助润色（已标注）。内容为第一手工程判断，非 AI 代写。
> 项目：Probe —— Java 可行性验证 coding agent harness（自实现 Python 内核）。
> 开发智能体：Claude Code（Superpowers v6.1.1，宿主接 njusehub glm-5.2）；冷启动第二智能体：OpenAI Codex CLI。

## 1. 哪些 Superpowers 技能发挥了最大作用、哪些"形式大于实质"

**发挥最大作用的三个**：

- `brainstorming`：它的"一次一问、优先选择题"把"可行性验证"这个含糊想法逼成了三件可区分的事——反馈闭环、影响面预评估、代码理解——并强制我选一个重点维度。没有这一步，我大概率会做成"什么都做一点、什么都不深"的demo。
- `writing-plans`：把设计拆成"每步 2–5 分钟、带失败测试代码、精确文件路径、接口签名"的 task，让 subagent 几乎不需要上下文就能动手。它的自审清单（占位符/一致性/范围/歧义）也确实抓出了几处笔误。
- `test-driven-development` + `subagent-driven-development`：TDD 强制 + 新鲜 subagent 隔离上下文，让我能在 29 个 task 里保持"每步可验证"，且不污染主上下文。

**形式大于实质的**：

- `using-git-worktrees`：作业要求"每个独立功能开一个 worktree 对应一个 PR"。但我没有远程仓库（GitHub 登录受阻），worktree 并行 + PR 工作流的收益被本地单线程序列执行抵消——四个并行链（tools/guardrail/validators/codemap）我最终都在 main 上顺序做完了。worktree 在有远程 + 多人协作时才有真价值，solo + 无远程场景下是开销。
- 起飞前预检扫了一遍 PLAN，但真正的冲突（T9 content kwarg、T16 短路互斥、T21 位置参数、T26 断言与 mask 不符）都是 **subagent 实现时**才暴露的，预检只抓到我自己手写的 5 处明显笔误。说明"静态扫 plan"抓不全"测试代码与实现规范之间的隐含矛盾"——这种矛盾要跑起来才见。

## 2. TDD 强制在 AI 协作下是阻碍还是放大器

**是放大器，但放大的是"纠错信号"，不是"产出速度"**。

TDD 在 AI 协作下最大的价值：它把"subagent 有没有真懂 task"变成了一个客观的红/绿信号。我派出的 subagent 有两次在"测试与实现规范矛盾"处停下来问我（T9、T16）——如果允许它"先写实现再补测试"，它会写出一个让自补的测试通过的实现，把矛盾藏起来，我却以为做完了。TDD 的"先红"逼它在动手前就面对 spec 的内部一致性。

代价：TDD 让每个 task 多出"写测试→验证红"两步，29 个 task 累计开销不小。但相比"subagent 偏离了我却不知道"的风险，这点开销值。所以它不是阻碍，是"用确定性换不确定性"的放大器。

## 3. subagent-driven 工作流让智能体能自主运行多久而不偏离

**单个 task 内几乎不偏离**（task 颗粒度小、上下文是我构造的精确 prompt，subagent 拿到的就是它需要的）。**跨 task 的连续自主则不行**——我每隔一个 task 就要回到主循环做评审与账本更新。29 个 task 我没有一个"派出去就连续跑完 5 个"的窗口，每个都回来一次。

原因：subagent 不继承会话历史，所以它无法知道"上一个 task 的接口约定"除非我在 prompt 里重复给它。这意味着主循环（我）必须做"上下文中转"——把前序 task 的 Produces 接口塞进下个 task 的 prompt。这正是 skill 设计的意图（"你构造 exactly 它需要的 context"），但也决定了主循环不能离场太久。

## 4. 什么样的 task 颗粒度最优

**"一个 subagent 一次会话、产出一个可单测的单一职责组件"最优**。太细（一个函数一个 task）会让接口在 task 间反复传递，开销大于收益；太粗（一个模块一个 task）会让 subagent 在多文件里迷失、评审也难聚焦。本项目 ~29 task 对 14 个组件，平均每组件 2 task，这个粒度让每个 subagent 都能在 5–15 分钟内完成并自审。

唯一例外是 AgentLoop（T23）——它要串起所有依赖、接口最多，subagent 花了最长时间、也最容易出错。集成 task 应该比机制 task 颗粒度更细或拆成多个，我下次会把 T23 拆成"主循环骨架"和"停机映射"两个 task。

## 5. SPEC/PLAN 质量如何影响实现质量——一个具体案例

**冷启动抓到的 D2（分类规则优先级未定）是最典型的"规约不清导致偏离"**。

我在 SPEC §3.5 写 FailureClassifier 时"故意留了一些模糊"——只列了 category 表，没写规则优先级、没说 `validator` 字段是否参与消歧，心想"留给实现阶段"。结果冷启动时 Codex 拿这份 spec 实现 T17，把规则 `("expected"→COMPILE_SYNTAX)` 排在 `("expected.*but was"→TEST_FAILURE)` 前面，且完全忽略 `validator` 字段，导致 `expected [1] but was [2]` 被误判为编译错误，测试红。

这正是 §4.5 想抓的"隐性上下文外溢"：我和主 agent 在 brainstorming 时心里都"默认"特化规则先匹配、validator 要分流，但没写进文档，冷读者无从知晓。修正后我在 SPEC §3.5 写死了"特化先于泛化、按 validator 字段消歧"，并在 PLAN T17 给出完整有序规则表 + 6 个针对性测试。修订后的 T17 由 fresh subagent 一次实现通过、独立 reviewer APPROVED。

教训：**"看似是实现细节的判定逻辑"必须进 spec，不能留模糊**。留给实现阶段的模糊，会被冷读者以"能跑就行"的方式填掉，且填错。

## 6. 最有效的 prompt/context 策略

**给 subagent 的 prompt 只含它这个 task 需要的东西，并显式列出"禁止碰控制层文档"**。

我每个 implementer prompt 都包含：工作目录、venv 激活命令、全局约束（pydantic/TDD/禁碰 AGENT_LOG 等）、该 task 逐字内容（Files/Interfaces/Step1–5 测试代码/实现要点）、精简报告格式。不含其它 task、不含对话历史、不含我的设计权衡。

为什么有效：(1) subagent 上下文干净，不会跑到别的 task 去；(2) "禁碰控制层文档"防止 subagent 把它的 commit 和我的 AGENT_LOG 账本混在一起（早期 T2 subagent 就扫进了我的未提交账本，之后我加了这条约束再没复发）；(3) "遇不确定即停问不要猜"这条让 subagent 在 T9/T16 矛盾处停下来问我而非硬写——这是抓 spec 缺陷的关键。

## 7. 凭据与分发这两条要求，迫使我想清楚的问题

**凭据**：我原本以为"用环境变量"就够安全了。要求逼我面对：`export` 进 shell history、`.env` 明文、进程环境被同机进程读、日志泄漏——每一层都是独立威胁。`CredentialStore` 因此做成"Keychain 优先、`.env` 仅 fallback、status 只回显掩码、`.gitignore` 强制忽略、首次引导隐藏录入"。容器内 Keychain 不可用又逼我设计"挂载只读 `.env` + 文档化明文风险 + 生产用 secrets"的退回路径。这些是"不逼就想不到"的工程层。

**分发**：Docker 一条命令起来听着简单，但"容器里如何安全配置自己的 key"才是真问题——Keychain 在容器里没了，`.env` 明文风险被放大。这逼我把"开发机方案"和"目标机方案"分开设计，并在 README 诚实写出已知限制（仅 Maven 深度支持、JDK 版本固定）。

## 8. 如果重做会改变什么

- **T23 AgentLoop 拆成两个 task**（骨架 + 停机映射），集成 task 不该和机制 task 同颗粒度。
- **冷启动验证前置到 SPEC 完成后、PLAN 写完前**：先让陌生 agent 读 SPEC（不读 PLAN）跑一两个 task，能在 PLAN 写下错误测试代码前就抓到 spec 模糊。我这次冷启动在 PLAN 之后，抓到的几处是"PLAN 测试代码与实现规范矛盾"，spec 层的 D2 是侥幸（因为我故意留了模糊）。
- **worktree 并行只在实际有远程/多分支需求时启用**，solo 无远程别假装并行。
- **反馈闭环 demo 用上下文敏感的 MockLLM**：当前 `demo_feedback_loop` 的 MockLLM 忽略 messages，"patch 是被反馈触发的"这一因果无法严格证明（reviewer 诚实指出）。重做会让 MockLLM 据 messages 里的失败反馈决定返回 patch 还是 stop，真正闭环因果。

## 9. 对 Superpowers 方法论的批判——它假设了什么，这些假设在我的项目里成立吗

**假设一：plan 可以被写成"零上下文可执行"的 bite-sized 步骤。** 部分成立。纯机制 task（classifier、self_corrector）确实能写成"给测试代码 + 实现要点"就让冷读者一次过；但集成 task（AgentLoop）的接口依赖横跨十几个组件，"零上下文"prompt 要重复大量接口签名，prompt 本身就很长。skill 的"complete code in every step"理想在大系统里会让 plan 文档膨胀到接近实现本身——不如承认"机制 task 用 bite-sized、集成 task 用接口契约 + 较粗颗粒"。

**假设二：subagent 隔离上下文 = 更高质量。** 成立但有代价。隔离确实防污染，但也让 subagent 看不到"全局为什么这么设计"——它在矛盾处只能停下来问，无法自行据全局意图判断。这把判断责任全压回主循环（我），主循环成了瓶颈。skill 假设"主循环有足够带宽做中转"，在 29 task 的规模下这个带宽开始吃紧。

**假设三：TDD 是 AI 协作的纪律底线。** 完全成立。这是整套方法论里我最认同的一条——它是唯一能把"subagent 真懂了吗"变成客观信号的机制。没有它，AI 协作的"完成"是不可信的。

**假设四：冷启动验证能抓 spec 缺陷。** 成立，且是单人项目里最接近同侪评审的机制。但它依赖"第二 agent 类型不同"——我用 Codex 抓到了 4 个真实缺陷；若用同类型 Claude Code subagent，共享的隐性上下文可能让缺陷逃过。这条假设的成立前提是"类型不同"，不能省钱用同类型替代。

---

## 已知限制（诚实披露）

- `RunShell` 用 `shell=True` 执行 LLM 给出的原始 command，唯一围栏是 Guardrail 的子串黑名单。对抗性 LLM 可绕过（base64/拼接）。作业范围内可接受，生产应改 `shell=False + shlex` 或加分词级白名单。
- 仅 Maven 深度支持；Gradle 尽力而为。`javalang` 对 records/密封类等新语法可能解析不全（降级跳过）。
- 影响面闭包是静态保守的，可能多报。
- `demo_feedback_loop` 的反馈因果在 offline MockLLM 下无法严格证明（见 §8）。
- 部署 URL / CI 最后一次 pass / 远程仓库推送：因 GitHub 账号暂不可用，这三项**待用户具备远程条件后补齐**（本地 `make test` 113 passed 已绿；docker build 因 daemon 未运行待手动验证）。

## 结论

Superpowers 给的"流程脚手架"守住了 TDD、评审、计划这些在 AI 协作中容易松懈的纪律——其中 TDD 和冷启动验证是真正不可替代的。但它不能替我回答"做什么"和"做对了吗"：重点维度选反馈闭环、冷启动抓到的 D2、subagent 当场抓到的 T9/T16 矛盾，都是"判断"而非"流程"的产物。当 LLM 能完成大部分编码时，工程师的价值落在：把模糊逼成可验证的规约、对智能体产出做有意义的评审与修正、在凭据与分发这些"不逼就想不到"的工程层较真。这套方法论最大的不足是假设"plan 可零上下文执行"与"主循环带宽无限"——在大系统里这两个假设都打折，需要用"机制 task bite-sized + 集成 task 接口契约"和"主循环主动中转上下文"来补。
