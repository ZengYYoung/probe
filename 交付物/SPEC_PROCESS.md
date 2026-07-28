# SPEC_PROCESS.md — 与 Superpowers 协作生成 spec/plan 的过程

> 本文档记录 brainstorming → writing-plans 的关键节点，以及 §4.5"陌生 agent 冷启动试运行"的客观证据。按 §4.4/§4.5 要求整理。

## 一、brainstorming 关键节点

主开发智能体 = Claude Code（Superpowers v6.1.1，宿主接 njusehub glm-5.2）。`brainstorming` 技能按"一次一问、优先选择题"推进，分节设计逐节签字。

### 1.1 智能体追问了哪些好问题（迫使我修正原设想）

| 节点 | 追问 | 我原设想 | 修正后 |
|---|---|---|---|
| Q1 | "重点深入维度选哪个？" | 模糊地想"可行性验证辅助审查"，三者缠在一起 | 收敛为**反馈闭环**（反馈信号→分类→回灌→自修正），其余降为最低实现 |
| Q2/Q3 | "目标语言范围？" | "python和java？"两者都要 | 改为**只做 Java**，深度优先；架构留适配器口 |
| Q4 | "agent 主运转模式？" | 偏审查辅助 | 改为**自主自修正 + 报告**——否则反馈闭环深度不成立（光产报告不需 agent 主循环） |
| 方案选择 | "A/B/C 哪个？" | 倾向 C（加代码地图） | 采纳 C，但确认"不挤占反馈闭环主深度"为硬约束 |

**关键修正**：Q4 让我意识到"辅助人审查"若做成纯报告工具，agent 主循环与反馈闭环就成了空壳——主深度必须落在"agent 收到失败反馈后改变下一步动作"这个闭环上。这是 brainstorming 逼出来的最重要的一次自我校正。

### 1.2 关键迭代（≥3 轮）

- **迭代 1（语言范围）**：我在 Q3 回"python和java？"带问号——其实是想问"能不能两个都要"。智能体没有直接答应或拒绝，而是给出"两语言=两套解析器、摊薄深度"的权衡，并提了一个折中（共享 taxonomy + 适配器）。我最终选择只做 Java，比"两者都要"更符合深度优先。**采纳了智能体的权衡分析，推翻了自己"全都要"的初始倾向。**
- **迭代 2（运转模式）**：智能体在 Q4 明确指出"光产出报告不需要 agent 主循环，反馈闭环深度不足"。我据此把主模式从"纯审查辅助"改为"自主自修正 + 报告"。**采纳。**
- **迭代 3（代码地图粒度）**：用户提议"提供包图/类图"，智能体把它并入第 3 节为 `DiagramRenderer`，并设了"静态、保守、不做完整 UML 语义"的边界——避免范围爆炸。**采纳智能体设的边界。**

### 1.3 哪些建议是 AI 提出而我采纳 / 推翻的

- 采纳：六维度"基础完整 + 一个深入"的取舍（§A.4-D）、反馈闭环作为重点维度（最契合 §A.4-C 判据）、Docker 分发 + 容器内 Keychain 不可用退回 `.env`、CI 只跑 mock 单测。
- 推翻/修正：智能体最初把"代码理解呈现"列为独立方案 C，我把它从"等价深度"改写为"次要深度，不挤占反馈闭环"，并加硬边界；智能体默认 spec 路径 `docs/superpowers/specs/`，我按作业要求改写到仓库根 `SPEC.md`（技能允许用户自定义覆盖）。

### 1.4 反思：brainstorming 在本项目里做得好与不满

- **好**：一次一问 + 选择题，逼我把含糊的"可行性验证"拆成了"反馈闭环/影响面预评估/代码理解"三件可区分的事，并强制选一个重点——避免了"什么都做一点"的常见失控。
- **不满**：分节设计签字时，第 2 节（反馈闭环）的 taxonomy 我"故意留了一些模糊"想留给实现阶段——结果正是这里被冷启动戳穿（见 §二 D2）。说明 brainstorming 阶段就该把规则的优先级与消歧写死，而非留到 writing-plans。下次会把"看似是实现细节"的判定逻辑也纳入设计签字。

## 二、冷启动试运行（§4.5 客观证据）

### 2.1 设置

- **主开发智能体**：Claude Code（glm-5.2 via njusehub）。
- **第二个智能体**：**OpenAI Codex CLI**（类型不同，满足 §4.5）。
- **条件**：全新 session、不导入任何会话/memory、只给 `SPEC.md` + `PLAN.md`，不补充口头解释。
- **指定 task**：PLAN 的 Task 12（Failure/FailureReport/signature）→ Task 17（FailureClassifier）。
- **纪律**：遇不确定即暂停询问、不凭猜测继续；产出 `COLDSTART_FEEDBACK.md`。
- **证据分支**：`coldstart/codex`（commit `4a06d15` + `1e9ffc9`），不合入 main，作为物证保留。

### 2.2 Codex 实际跑出了什么

- T12：完成并 commit（`4a06d15`）。实现了 `probe/validators/base.py` + 测试，测试通过。
- T17：开始写 `probe/validators/classifier.py` + 测试，但**测试失败**（`test_assertion_failure` 红），未提交，停在让测试变绿这一步。
- **未产出 `COLDSTART_FEEDBACK.md`**：Codex 卡在实现层、没回到文档层写反馈。这是它对 prompt 的执行偏差，但**它的代码本身就是受阻点的物证**，足以提炼缺陷。

### 2.3 受阻点与暴露的 SPEC/PLAN 缺陷

| # | 受阻点（Codex 行为） | 是 spec 写错还是读错？ | 暴露的缺陷 |
|---|---|---|---|
| **D1** | Codex 的 T12 测试里写了 `from probe.tools.base import Action  # imported per PLAN but unused`，并为此**自建了 `probe/tools/base.py` stub** | **PLAN 写错** | PLAN T12 测试含一行多余的 `from probe.tools.base import Action`，但 T12 不用 Action、且 `tools/base.py` 要到 Task 6 才创建。冷读者忠实照搬 → import 必炸 → 被迫自建 stub。 |
| **D2** | Codex 的 `classify` 把规则 `("expected"→COMPILE_SYNTAX)` 排在 `("expected.*but was"→TEST_FAILURE)` **前面**，且**完全忽略 `validator` 字段**，导致 `test_assertion_failure`（`message="expected [1] but was [2]"`）误判为 `COMPILE_SYNTAX` | **SPEC+PLAN 写错** | SPEC §3.5 与 PLAN T17 既没规定规则**优先级/precedence**，也没说明 `validator` 字段是否参与消歧。冷读者无从得知"特化规则须先于泛化""validator 字段作主消歧信号"。 |
| **D3** | Codex 用 `dataclass` 而非 `pydantic` 实现 `Failure` 等，测试照过 | **PLAN 一致性缺陷** | PLAN T12 Step 3 说"pydantic 模型"，但测试代码用普通构造、`dataclass` 也能过——spec 没把"用 pydantic"钉成可验证约束，冷读者选了更轻的 dataclass。 |
| **D4** | Codex 的 `classify_report` 直接 mutate 入参（`f.category = ...; report.signature = ...`） | **PLAN 措辞缺陷** | PLAN T17 写"就地填 category/hint"，"就地"一词推动冷读者走向 in-place mutation，是有副作用的设计。 |

> 注：D2 是最关键的——它正是设计第 2 节"故意留了一些模糊"的地方。冷启动证明：留给实现阶段的模糊，会被冷读者以"能跑就行"的方式填掉，且填错。模糊必须在 spec 阶段就写死。

### 2.4 产出与预期差距

- 预期：Codex 完成 T12+T17、全绿、产出 `COLDSTART_FEEDBACK.md`。
- 实际：T12 绿、T17 红、无反馈文件。
- 差距根因：**不是 Codex 能力不足**，而是 SPEC/PLAN 在分类规则优先级这一"机制核心"上欠定义——这正是 §4.5 想抓的"隐性上下文外溢"：我和主 agent 在 brainstorming 时心里都"默认"特化规则先匹配、validator 字段要分流，但没写进文档，冷读者无从知晓。

### 2.5 据此对 SPEC / PLAN 的修订（关键 diff）

**修订 D1 — PLAN T12 测试**（删除多余 import）：
```diff
 from probe.validators.base import Failure, FailureReport, signature, Category
-from probe.tools.base import Action
 def test_signature_stable_regardless_of_order():
```

**修订 D3 — PLAN T12 Step 3**（钉死 pydantic）：
```diff
-- [ ] Step 3: 实现 — base.py：pydantic 模型；signature 排序 ...
+- [ ] Step 3: 实现 — base.py：用 pydantic v2 BaseModel（不得用 dataclass，
+      与 SPEC §6 一致）定义 Category(str Enum)、Failure、FailureReport、Validator ABC；
+      signature 排序 ...
```
并在 SPEC §6 末尾补：`> 全部数据模型用 pydantic v2 BaseModel（统一校验与 JSON 序列化）；Category/Status/State 用 str Enum。Failure/FailureReport 等值对象不得用 dataclass 替代。`

**修订 D2 — SPEC §3.5**（写死优先级与 validator 消歧）：
```diff
-- 行为：按确定性规则映射到 category + 生成 hint。
+- 行为：按有序规则表映射。规则 = (validator_scope, pattern, category, hint)；
+  匹配当且仅当 validator_scope is None or == failure.validator 且 pattern 命中
+  "{message} {raw}"。首条匹配胜出；无匹配→UNKNOWN。
+- 规则优先级（冷启动修正）：先按 validator 字段消歧——test 只在 TEST_*、
+  compile 只在 COMPILE_*/DEPENDENCY_MISSING/BUILD_CONFIG_ERROR、lint 只在
+  LINT_VIOLATION 中匹配；更具体的 pattern 必须排在更泛化之前
+  （expected.*but was 须排在 expected 之前）。
```
PLAN T17 同步重写：给出完整有序规则表 + 6 个测试用例，含
`test_validator_field_disambiguates_same_text` 与 `test_specific_pattern_beats_generic`，直接断言"同文本不同 validator 流到不同类""特化先于泛化"。

**修订 D4 — PLAN T17**（不可变）：
```diff
-- classify_report(report) -> FailureReport（就地填 category/hint，重算 signature）
+- classify_report(report) -> FailureReport（返回新对象，不 mutate 入参与其中
+  Failure；重算 signature/summary）
```
并加测试 `test_classify_report_does_not_mutate_input` 断言入参与返回值非同一对象、入参字段未变。

### 2.6 一句话总评

Codex 没能跑通 T17，但**这恰好是规约的失败、不是 agent 的失败**——它把 SPEC/PLAN 在"分类机制核心"上的欠定义精确地暴露成了红测试。这次冷启动抓到了 4 个真实缺陷（其中 D2 是设计阶段有意留下的模糊），全部已修订进 SPEC/PLAN。修订后的 PLAN 在分类规则上不再依赖任何隐性上下文，可由冷读者直接实现。

## 三、过程纪律自检

- ✅ 在 SPEC+PLAN 完成、冷启动验证通过前，未写任何实现代码（main 分支只有文档 commit；Codex 的代码在隔离的 `coldstart/codex` 分支，不合入）。
- ✅ 第二个 agent 类型不同（Codex vs Claude Code），全新 session，仅给 SPEC+PLAN。
- ✅ 偏离记录：Codex 未按 prompt 产出 `COLDSTART_FEEDBACK.md`，改为从其代码提交提炼受阻点——已在 §2.2 说明，不构成 §4.5 实质偏离（仍是不-同-类-型、零背景的冷启动）。
- ✅ 修订全部带 diff（§2.5）。
