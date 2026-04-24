# 2.11 Clarification 边界审计（通用规则视角）

> 状态：**第一轮审计完成**  
> 前置文档：`docs/2_10_provider_bad_case_audit_kickoff.md`  
> 目的：回答当前 provider 主链下，clarification 的触发边界是否表现稳定、是否出现通用性过宽

---

## 1. 本文回答的问题

> 当前 clarification 是按什么通用规则触发的？这些规则在真实 provider 主链样本上表现如何？有没有出现“看起来过宽，但还不够构成 bug”的边界样本？

本文不回答：

- 单 query 的定向修复
- 本地 fallback clarification 行为
- 最终要不要立刻改阈值

---

## 2. 当前 clarification 的通用规则

代码位置：`backend/app/services/chat_service.py::_build_clarification_response()`

当前触发 clarification 的条件非常简单，且完全是**通用规则**：

1. `reranked_hits` 中至少有 2 个候选满足：
   - `accept == True`
   - `source_kind == "faq"`
   - `evidence_spans` 非空
   - 有 `answer` 或 `body_text`
2. 只看前 2 个候选
3. `top_candidate.rerank_score - second_candidate.rerank_score <= 0.15`
4. 两个候选的 `question` 不相同

也就是说，clarification 当前**不显式参考**以下信号：

- `planner_confidence`
- query 是否包含更具体的复合词
- `domain_hint` 是否已经成功缩域
- lexical top1 是否明显强于其他 lexical 候选

这些都只会间接通过 `rerank_score` 竞争结果体现。

---

## 3. 现有边界保护带

当前仓库里已经有一条明确的 clarification 边界保护线：

### 3.1 已锁定“该澄清”的泛问法

见 `backend/tests/test_phase2_retrieval.py`：

- `请假`
- `怎么请假`
- `如何请假`
- `什么叫请假`
- `请假怎么走`
- `请假流程`

这些样本都要求进入 clarification。

### 3.2 已锁定“该直答”的具体问法

同文件已锁定不会误触 clarification 的具体问法：

- `如何申请年假？`
- `病假材料`
- `请假进度怎么看`
- `入职第一天需要办理什么手续？`
- `调休余额在哪里看？`

这条保护线说明：

> 当前 clarification 不是“默认分支”，而是已经对一批 HR 泛问法与具体问法做了正反向边界锁定。

---

## 4. Cloud 主链第一轮样本结果

基于 `scripts/generate-provider-audit-samples.py` + `scripts/audit-provider-bad-cases.py`，当前已补 28 条 provider 主链样本。

结果：

- `28/28 ok`
- `11` 条进入 clarification
- `0` 条进入 hard case
- `0` 条 candidate bad trace

这说明：

- 当前 clarification 行为整体稳定
- 第一轮没有筛出明确 blocker

---

## 5. 当前样本分类

### 5.1 预期澄清，行为合理

以下 query 当前进入 clarification，且从通用规则角度看是合理的：

- `请假`
- `怎么请假`
- `如何请假`
- `什么叫请假`
- `报销`
- `账号`
- `密码`
- `请假咋整`

这些 query 的共同特征是：

- 语义仍然偏泛
- 同域内会稳定召回多个 FAQ
- 两个 FAQ 都能提供可接受证据
- top2 的 `rerank_score` gap 不足以压出一个唯一答案

这与当前 clarification 规则是对齐的。

### 5.2 稳定直答，行为合理

以下 query 当前稳定直答，说明 clarification 没有泛滥到所有 domain：

- `系统权限`
- `如何申请系统权限开通`
- `门禁权限怎么申请`
- `VPN无法连接怎么办`
- `如何安装办公软件`
- `生产变更`
- `生产变更需要怎么申请`
- `值班安排`
- `如何上传文档？`
- `病假材料`
- `请假进度怎么看`
- `如何提交日常报销`
- `报销流程`
- `账号被锁`
- `账号被锁定后怎么处理`
- `忘记登录密码怎么办`
- `邮箱签名怎么修改`

这些样本表明：

- 具体问法并不会天然被 clarification 吞掉
- 当前系统已经能在 HR / IT / Admin / Ops / Finance 多域给出稳定直答

---

## 6. 当前 watchlist（不是 bug，先观察）

第一轮审计里有两类 query 值得继续盯，但还不够判成 bug。

### 6.1 `报销单据怎么提交`

现象：

- `domain_hint = finance`
- 进入 clarification
- 当前引用的是 `finance-faq-003` 与 `finance-faq-007`

为什么值得观察：

- 从用户感受看，它像一个**比较具体**的财务问法
- 但在当前种子语料里，它同时靠近：
  - 差旅报销提交
  - 报销退回后处理
- 两者都能拿到可接受证据，导致 gap 不足以直答

当前判断：

- **暂不判 bug**
- 更像“具体问法落在了语料语义边界上”
- 如果未来出现更多 finance 具体问法被同类澄清，才说明 clarification 规则对 finance 具体问法可能偏宽

### 6.2 `什么叫HR` / `HR是什么`

现象：

- planner 正确给 `domain_hint = hr`
- 但仍进入 clarification

为什么值得观察：

- 这类 query 使用缩写，词面很短
- 当前 `lexical_terms` 也很稀疏（如只剩 `HR`）
- 在现有种子里，多个 HR FAQ 都可能被缩写牵引

当前判断：

- **暂不判 bug**
- 更像“缩写查询天然信息不足”
- 如果未来我们明确产品希望“部门缩写解释类 query 必须直答”，那需要一套**通用的缩写解释策略**，而不是对 `HR` 单独打补丁

---

## 7. 第一轮审计结论

### 7.1 当前没有足够证据支持立即改 clarification 通用规则

原因：

- 预期澄清样本表现稳定
- 具体问法直答样本已覆盖多个 domain
- 当前 watchlist 数量少，且都能用现有通用规则自洽解释

### 7.2 当前最合理的动作不是改代码，而是继续积累同类样本

下一轮重点看：

1. finance 具体问法是否成簇地落入 clarification
2. acronym / 缩写问法是否成簇地落入 clarification
3. 是否出现“用户明显更像要单一答案，却被反复澄清”的 provider hard case

只有这些模式开始成簇出现，才值得进入规则级讨论。

---

## 8. 后续判定门槛

以下任一情况出现，再进入 clarification 规则改造讨论：

1. 同一类具体问法在一个 domain 中持续误触 clarification
2. provider 主链下出现 clarification 相关的真实 down-vote / hard case
3. `scripts/audit-provider-bad-cases.py` 开始稳定筛出与 clarification 相关的 candidate bad traces

在此之前，clarification 线维持**审计继续、规则不动**。
