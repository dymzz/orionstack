# 2.10 Provider 主链真实坏例审计与闭环线（启动记录）

> 状态：**收口 / 可执行**  
> 对应决策：`docs/2_9_next_line_decision.md`  
> 目的：在 `2_8` planner provider 验证线收口后，开始对 **当前配置的 provider 主链** 的真实 bad case 做审计与闭环；DashScope/Qwen 只是已验证后端之一

---

## 1. 本线回答的问题

> 在当前 `provider backend -> planner -> hybrid -> rerank/evidence -> clarification -> trace/hard_cases` 主链已经具备可观测性后，真实运行里还剩哪些坏例？这些坏例分别属于哪一层？

本线不回答：

- 本地 fallback 质量
- LocalRule 深化
- 单 query / 单词的定向补丁规则

---

## 2. 启动时的第一手现状

### 2.1 当前存量 trace / hard case 还不能直接当“provider 主链画像”

启动审计前先看了两份现有数据源：

- `backend/app/storage/retrieval_traces/retrieval_traces.jsonl`
- `backend/app/storage/hard_cases/hard_cases.jsonl`

得到三个关键事实：

1. `retrieval_traces.jsonl` 历史存量以 `2026-04-19 ~ 2026-04-20` 为主，`2026-04-21` 仅 8 条；它混合了早期本地 planner、OpenAI-compatible provider 和其他演进阶段的数据，不能未经筛选直接拿来代表当前 provider 主链
2. `hard_cases.jsonl` 当前仅 8 条，且大多是旧 trace 派生的 down-vote / `no_evidence` 记录，不能直接代表当前 provider 主链的坏例面
3. 启动时 `retrieval_trace` **未持久化 `router_used`**；这意味着即便 trace 中已有 `domain_hint / retrieval_mode / rerank_score` 等字段，也无法直接从存量文件把 `query_planner_openai_compatible`（历史兼容别名：`query_planner_qwen_api`）与 `query_planner_local` / `rule_parser` 样本切开

### 2.2 现有 `hard_cases` 的主要问题是“历史性”，不是“数量少”

当前 `hard_cases.jsonl` 的值不在于统计显著性，而在于它里面夹着：

- 早期 local planner 样本
- 语料尚未补齐时的旧坏例
- 当前已被关闭的问题（例如 `生产变更` 早期误命中 admin）

所以如果不先把 trace 观测补齐，新线会在第一步就把“历史坏例”和“当前 provider 坏例”混在一起，审计结果不可信。

---

## 3. 启动结论

本线的**第一子任务**不是立刻调 retrieval，而是先补一格观测：

### 3.1 已执行：`retrieval_trace` 持久化 `router_used`

现在 `backend/app/api/routes/chat.py::_build_retrieval_trace_record()` 已新增：

- `router_used`

并同步传入由 trace 派生的 `hard_cases` 记录。

意义：

- 后续可以直接按 `router_used == "query_planner_<provider>"` 筛 provider 主链样本；旧数据兼容 `query_planner_qwen_api`
- 不再需要靠 `domain_hint != None` 或时间段做不可靠代理筛选
- `hard_cases` 也能区分它是 provider 主链坏例，还是旧本地路径残留

### 3.2 当前这一步仍然不算“新阶段”

这次补的是观测能力，不是改 Phase 2 目标链本身；因此仍然属于 `docs/2_9_next_line_decision.md` 定义的新线启动动作。

---

## 4. 第一轮样本审计（2026-04-22）

在补齐 `router_used` 后，先用当前 `openai_compatible` provider 主链重跑了一批“旧 hard case + 高风险泛问法”样本，共 12 条：

- `请假`
- `如何上传文档？`
- `如何申请年假？`
- `生产变更`
- `生产变更需要怎么申请`
- `报销`
- `什么叫请假`
- `值班安排`
- `账号`
- `请假咋整`
- `系统权限`
- `VPN无法连接怎么办`

### 4.1 总览统计

- `router_used == query_planner_openai_compatible`（或历史别名 `query_planner_qwen_api`）：12 / 12
- `final_status == ok`：12 / 12
- `fallback_reason == conflict_requires_clarification`：5 / 12
- `retrieval_mode == hybrid_rerank`：7 / 12
- `retrieval_mode == clarification`：5 / 12
- `no_evidence / system_error`：0 / 12

### 4.2 当前分类结果

#### A. 稳定直答（当前无异常）

- `如何上传文档？` -> `faq-001`
- `如何申请年假？` -> `hr-faq-001`
- `生产变更` -> `ops-faq-003`
- `生产变更需要怎么申请` -> `ops-faq-003`
- `值班安排` -> `ops-faq-002`
- `系统权限` -> `it-faq-012`
- `VPN无法连接怎么办` -> `it-faq-003`

这些样本当前没有暴露出 planner / retrieval / rerank 的真实坏例；其中 `VPN无法连接怎么办` 也已随着 ASCII 大小写恢复规则关闭了 `B2` 风险。

#### B. 预期澄清（当前更像正确行为，不算坏例）

- `请假`
- `报销`
- `什么叫请假`
- `账号`
- `请假咋整`

这五条的共同特征是：

- planner 已正确进入 provider 主链
- retrieval 能召回多条相关 FAQ
- rerank `accept=True`
- 最终触发 clarification，而不是误答或 `no_evidence`

当前更合理的解释是“**泛问法 / 多候选竞争下的预期澄清**”，而不是坏例。

### 4.3 第一轮审计结论

**第一轮没有筛出需要立即修复的 provider 主链 blocker。**

当前真正缺的不是“再调一轮 retrieval 常量”，而是：

1. 继续积累更自然的 provider 主链 trace
2. 等待真实 `down-vote` / `no_evidence` / 错答样本沉淀
3. 再按层级分类是否属于：
   - 语料缺口
   - clarification 边界误触发
   - rerank / evidence 阈值问题
   - planner 真实边界

换句话说：**现在已经具备了审计能力，但还没有积累到足够多的“当前 provider 真实坏例”。**

### 4.4 为下一轮补的最小工具

为了避免后续每轮都手工翻 `jsonl`，已新增：

- `scripts/audit-provider-bad-cases.py`

职责：

- 从 `retrieval_traces.jsonl` 与 `hard_cases.jsonl` 中筛当前 provider router 的样本，并兼容旧路由名 `query_planner_qwen_api`
- 输出 provider 主链的：
  - `final_status` 分布
  - `fallback_reason` 分布
  - `retrieval_mode` 分布
  - `audit_category` 分布
  - `audit_resolution` 分布：`open` / `closed_by_later_success`
  - 候选 bad traces
  - 同一路由下的 hard cases

默认用法：

```powershell
uv run python scripts/audit-provider-bad-cases.py
```

### 4.5 已执行：补必要样本并跑 seeded audit

为了避免完全被动等待自然流量，又新增：

- `scripts/generate-provider-audit-samples.py`

它会主动通过 `chat_route.ask_chat()` 打一批经过挑选的 provider 主链样本，自动落 trace。当前样本共 28 条，分三组：

- stable direct
- expected clarification
- boundary / normalization

首轮 seeded run 结果：

- `router_used == query_planner_openai_compatible`（或历史别名 `query_planner_qwen_api`）：28 / 28
- `final_status == ok`：28 / 28
- `fallback_reason == conflict_requires_clarification`：11 / 28
- `hard_cases on same router`：0
- `candidate bad traces`：0

结论：

- 这批“必要样本”仍未筛出 provider 主链 blocker
- 但它们提供了两类**值得继续观察的 clarification 边界样本**：
  - `报销单据怎么提交`：finance 域内出现多候选竞争，进入 clarification；暂不视为错误，但可作为“具体问法是否过度澄清”的观察点
  - `什么叫HR`：planner 正确给 `domain_hint=hr`，但仍进入 clarification；暂不视为错误，可作为“缩写/缩略词是否应走更直接解释”的观察点

这两条目前都不足以触发代码修复，更适合作为下一轮 provider 样本积累时的 watchlist。

### 4.6 2026-04-25 收口运行结果

当前 provider-neutral 审计工具已能把“当前仍 open 的坏例”和“历史坏例后来已成功”分开。

```powershell
uv run python scripts/audit-provider-bad-cases.py --limit 8
```

当前真实 JSONL 汇总：

- `traces=246`
- `hard_cases=4`
- `candidate bad traces=5`
- `audit_category={'retrieval_backend': 1, 'corpus_gap': 4}`
- `audit_resolution={'open': 4, 'closed_by_later_success': 1}`

解释：

- `closed_by_later_success` 表示同一 query 后续已有成功 trace，不应再当作当前 blocker
- `open` 表示仍需人工 triage，不能直接做 query 特判；应先判断是语料缺口、检索后端、evidence 阈值还是 planner 边界
- 当前工具完成的是审计边界，不直接修改检索策略或知识内容

---

## 5. 下一步执行顺序

在 `router_used` 已进 trace 之后，本线下一轮按以下顺序推进：

1. 累积一批新的 provider 主链 trace
2. 只筛当前 provider router 的样本，并兼容旧路由名 `query_planner_qwen_api`
3. 继续运行：
   - `uv run python scripts/generate-provider-audit-samples.py`
   - `uv run python scripts/audit-provider-bad-cases.py`
4. 再按以下层级分类真实坏例：
   - 语料缺口
   - clarification 边界
   - rerank / evidence 阈值
   - planner 真实边界
5. 仅考虑通用修复；若只能靠 query 特判关闭，则记录但不做

---

## 6. 启动检查点

本次启动完成后，满足：

- [x] 决策文档已明确：开新线，不开新阶段
- [x] 新线启动文档已落地
- [x] `retrieval_trace` 已持久化 `router_used`
- [x] `hard_cases` 已继承 `router_used`
- [x] 已完成第一轮 provider 主链样本分类审计
- [x] 已补一批必要样本并完成 seeded audit
- [x] 已新增 provider-neutral 审计入口，并保留旧 cloud 脚本兼容入口
- [x] 已新增 `audit_resolution`，区分 `open` 与 `closed_by_later_success`
- [x] 已完成当前 open provider 坏例 triage：见 `docs/2_12_provider_open_bad_case_triage.md`
- [x] 已完成受控复测：`演示资料` / `功能定位` 不是语料缺口，主要暴露无 domain 宽搜的 recall / timeout 风险
- [x] 已完成 P1.3 通用稳定性修复：hybrid 检索单侧 backend 失败时可 soft fallback 到另一侧
- [x] 已完成 P1.4 通用召回 / 重排修复：补 provider-neutral 领域约定、合并保护性 lexical terms、扩大无 domain rerank 候选池并保留跨域候选
- [x] 已完成 P1.4 受控复测：在 `domain_hint=null` 下 `演示资料` 命中 `sales-faq-003`，`功能定位` 命中 `product-faq-004`
- [ ] 下一步重新运行 provider bad-case audit，确认历史 open miss 是否已被 later success 关闭
