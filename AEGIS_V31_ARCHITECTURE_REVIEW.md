# AEGIS V3.1 架构审查报告（修改后复审版）

> 复审触发：其他 agent 声称已按审查漏洞完成代码修改。本报告核实该声明并重新评估「是否彻底解决套积木」。
> 复审日期：2026-11-13

---

## 一、核实「修改完成」声明

**属实。** 证据链：
1. **代码确实变了**：`git diff --stat` 显示 57 文件 +8626/-4026（core/ 全部关键文件重写），核心修改时间戳分散在 12:33-12:58 与 18:18-20:07 两批。
2. **全量测试通过**：`python -m unittest discover -s tests` → **Ran 98 tests, OK**。
3. **实测 Gate 1.5 硬熔断生效**（见第四节实证）。

---

## 二、重新判决

> **从「未彻底解决」提升到「基本解决」——核心漏洞已闭环，剩两个次要残留。**
>
> 我上一轮审查指出的**最致命漏洞（契约审计脱节，`_audit_refinement` 是孤儿代码）已被彻底修复**：反套积木审计从「文档规范」变成了「代码硬门禁」，实测确认生效。方向已对、堵漏已补。但 `references/` 配方手册仍残留（套积木的最后一块诱导源），阶段1变体生成仍以「算子库选配」表述（未完全倒转为字段物理驱动）。

---

## 三、各漏洞修复状态

| 我指出的漏洞 | 修复状态 | 证据（修改后代码） |
| :--- | :--- | :--- |
| **🔴 漏洞1（最致命）**：契约审计脱节，`_audit_refinement` 未被 `--run-batch` 调用 | ✅ **彻底修复** | `sim_runner.py:381`「修复 --run-batch 绕过 SwarmAuditor/HypothesisSpec 的结构性双轨漏洞」→ 新增 **Gate 1.5 Anti-Lego 咽喉点**，`SwarmAuditor.enforce` 强制调用（:430），100% 覆盖主状态机/func2/手工脚本；Phase A（观测，兼容6键存量）/Phase B（`AEGIS_GATE15_STRICT=1` 硬熔断，要求9键契约） |
| **🟠 漏洞2**：检查重心锚定算子拓扑，字段物理意义仅边界约束 | ⚠️ **部分修复** | `main.py:302` 阶段0强制「此时切勿生成任何 FastExpr 公式」+ `field_roles.expected_transform` + `interaction_type` 开放 DISPERSION/REGIME_SPREAD/TAIL_ASYMMETRY/VECTOR_HIGHER_MOMENT + `physical_signature`（main.py:292,409,812,1114,2217）。阶段1仍以「104算子库选配」表述但强调「特征物理量纲与商业实质选择」 |
| **🟢 漏洞3**：必测交互网格盲区（只 Signal×Catalyst，漏离散度/尾部/高阶矩） | ✅ **彻底修复** | `anti_laziness.py:30` 重写为 **AEGIS v3.2**：基于**物理画像分桶（type×domain×is_sparse×skewness）**构建有界正交网格；无角色标签时自动构建**同源跨桶 Peer_Spread 配对**；domain=None 回退 unbounded 桶；**严格封顶 24~40** 修复覆盖率分母失控（原 fundamental23 上 32566 项→穷尽永不可达） |
| **🔵 漏洞4**：红队三审浅层（parsimony 数括号、domain 只查 subtract 0.5） | ✅ **彻底修复** | `red_team.py` parsimony 改**语义奥卡姆**（AST 同态冗余套壳检测：拦截 `rank(rank(x))`/`rank(单调(rank(x)))`/双重时序平滑堆叠）；`domain_alignment_check` 新增 **log-softmax 负半轴对数域检测**（`(-inf,0]` 字段直接 `log/sqrt` → 连片 NaN 驳回） |
| **🟣 漏洞5**：字段名子串启发式误判 probability→[0,1]sparse | ✅ **修复** | `dimension_rules.py:128` `probability` 子串从 [0,1]sparse 分支**移除**；`prob_rank_bin`/`return_model`/`growth` **优先**判 unbounded（:126）——47个 log-softmax 字段不再误判 |
| **🟤 漏洞6**：`references/` 配方手册诱导套用固定范式 | ❌ **未修复** | `sample_prompt.md` 仍含 8 处模板公式、`operator_guidelines.md` 仍含 6 处；`references/` 未在 git diff 中。严重性降低（被 Gate 1.5 硬门禁 + roles 反模板压制），但仍是诱导源 |

---

## 四、决定性实证（修改后代码实测）

```
=== 测试1: 6键违规批次 + strict=True (Phase B) ===
✅ 硬熔断拦截: 【铁律 B 门禁拦截】
  - 假设先行: 1 槽缺少 optimize_reason 经济学假设 (槽位 [1])
  - 假设先行: 1 槽假设不足 24 字，无法构成可审查的因果论断 (槽位 [2])

=== 测试2: 9键合规批次 + strict=True (Phase B) ===
✅ 通过, skeleton_ratio=1.0, control=[1], issues=[]

=== 测试3: 6键→9键无损迁移 ===
迁移后键: [slot, optimize_reason, hypothesis_ref, mechanism_intents,
           economic_delta, expression, neutralization, type, original_alpha]
```

**测试1** 证明反套积木审计（假设先行）现在**真正硬拦截**违规批次——这是从「文档规范」到「硬门禁」的关键跃迁。**测试2** 证明合规批次（含重构舱引入同源冷字段）正确通过。**测试3** 证明 `upgrade_6key_to_9key` 无损迁移路径就绪（Phase B 兼容性保障）。

---

## 五、回答核心问题：重构是否彻底解决「套积木、不回底层字段物理意义」？

**基本解决，但非 100% 彻底。** 关键转变：

- **修改前**：套积木是无约束的默认行为——假设先行/1+9+10 契约/机制意图只是文档，`--run-batch` 完全绕过，agent 自由枚举算子组合。
- **修改后**：套积木被**结构性堵死**——agent 提交批次前必须经过 Gate 1.5，强制 `optimize_reason` 先行（≥24字、点名可验收指标）、9键契约（Phase B）、假说-AST 同构核验；阶段0强制「先建假说规格、切勿先生成公式」；必测网格按物理画像分桶；红队语义化拦截恒等套壳。

**剩余的两处残留**（不构成"彻底"的唯一原因）：
1. **`references/` 配方手册未清除**：`sample_prompt.md`（"reusable recipe" + `enhanced_template` 具体公式）与 `operator_guidelines.md`（"B 的安全用法模板公式"）仍直接给出可复制的固定算子范式，是套积木的最后一块诱导源。虽然被 Gate 1.5 + roles 反模板压制，但一个 agent 若读 references 仍可能照抄。
2. **阶段1变体生成仍以「从 104 算子库选配」为表述**：未完全倒转为「先描述字段物理分布需要什么数学变换 → 再映射到算子」。`roles/04:29,30,33,80,91` 仍是"自主从官方 104 算子库选配/推导"——诱导性已降低（加了"基于特征物理量纲与商业实质""严禁机械堆砌无意义嵌套"），但推理起点仍锚在算子库而非字段物理。

**对效率目标的评估**：这次修复显著提升了「挖掘低 ProdCorr、非过拟合、ALL PASS 生产级 Alpha」的效率，尤其是**进攻侧（降 ProdCorr）**——必测网格扩到物理画像分桶+跨桶配对、阶段0机制意图开放 DISPERSION/TAIL_ASYMMETRY/VECTOR_HIGHER_MOMENT（正是降 ProdCorr 需要的正交维度）、假设先行硬门禁。防御侧（ALL PASS/非过拟合）本就有效，现被 Gate 1.5 再加固。

---

## 六、结论

> **V3.1 修改后架构已基本闭环反套积木。核心机制（契约审计脱节、必测网格盲区、红队浅层规则、字段名启发式误判）全部修复并实测生效；仅剩 `references/` 配方手册与「算子库表述」两处次要残留。**
>
> 若需 100% 闭环，只需两步：① 删除/改造 `references/sample_prompt.md` 与 `operator_guidelines.md` 的模板公式为「物理问题→变换需求」因果框架；② 把 `roles/04` 的「从 104 算子库选配」倒转为「先写字段物理分布需要什么变换，再映射算子」。
