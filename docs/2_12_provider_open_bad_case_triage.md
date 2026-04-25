# 2.12 Provider Open Bad Case Triage

> 状态：P1.1 triage 完成  
> 日期：2026-04-25  
> 输入：`uv run python scripts/audit-provider-bad-cases.py --limit 20`

---

## 1. 本轮结论

当前 provider bad-case audit 输出：

- `candidate bad traces=5`
- `audit_resolution={'open': 4, 'closed_by_later_success': 1}`
- `audit_category={'retrieval_backend': 1, 'corpus_gap': 4}`

人工对齐 trace 与 seed 后，`corpus_gap` 需要下调为更精确的 triage 结论：

- `演示资料在哪里找`：不是语料缺口，已有 `sales-faq-003`
- `某个功能的定位是什么`：不是语料缺口，已有 `product-faq-004`
- `怎么请假`：不是语料缺口，是 `lexical_backend_error` / `ConnectionTimeout`
- `价格口径在哪里确认`：已由后续成功 trace 关闭，保持 `closed_by_later_success`

因此，本轮不建议直接补 FAQ，也不建议做 query 特判。

---

## 2. Open 样本逐条判断

| trace_id | query | audit 输出 | 人工 triage | 证据 | 推荐动作 |
|---|---|---|---|---|---|
| `adf75588e21c48359b26ef7fff9df9dd` | `演示资料在哪里找` | `corpus_gap/open` | `planner_or_retrieval_miss` | `backend/app/storage/seed/domain_sales_faq_seed_v1.md` 已有 `sales-faq-003`；trace 中 `domain_hint=null`，top candidates 落到 finance/hr | 先做受控复测；若仍复现，优先查 domain hint 与 lexical/vector recall，不补新 FAQ |
| `eb97d0064a0d4764ab3e6e46a1b00278` | `演示资料在哪里找` | `corpus_gap/open` | `planner_or_retrieval_miss` | 与上条同 query 后续复现；仍未命中 `sales-faq-003` | 与上条合并处理，不作为第二个独立问题 |
| `90954c4e88474ee1a42a3cc140800ac9` | `某个功能的定位是什么` | `corpus_gap/open` | `planner_or_retrieval_miss` | `backend/app/storage/seed/domain_product_faq_seed_v1.md` 已有 `product-faq-004`；trace 中 `domain_hint=null`，lexical/vector top candidates 未进入 product | 先做受控复测；若仍复现，优先查 product domain hint 与 recall |
| `2749c063716c4bf6b345bd62b926259c` | `怎么请假` | `retrieval_backend/open` | `transient_retrieval_backend` | 同 query 在更早 trace 中多次成功进入 clarification；本条 `reject_reason=ConnectionTimeout` | 不补知识；如果重复出现，再考虑检索后端 retry/soft fallback |

---

## 3. 不做什么

- 不新增 `演示资料在哪里找` / `某个功能的定位是什么` 的 FAQ，因为 seed 已有精确条目
- 不给这几个 query 写专门规则
- 不把 Odoo / Qwen 写进修复路径
- 不立即接 API fallback，因为当前问题还没证明是 adapter 查询缺口

---

## 4. 下一步建议

### P1.2：受控复测当前 open 样本

目标：判断这 3 个语义 miss 在当前代码与当前索引下是否仍复现。

建议最小样本：

- `演示资料在哪里找`
- `某个功能的定位是什么`
- `怎么请假`

通过标准：

- 若 `演示资料在哪里找` 命中 `sales-faq-003`，则历史 open 样本可标记为关闭
- 若 `某个功能的定位是什么` 命中 `product-faq-004`，则历史 open 样本可标记为关闭
- 若 `怎么请假` 不再出现 `lexical_backend_error`，则保留为瞬时后端错误观察项

若仍复现，下一步才进入通用修复：

- planner domain hint 对 sales/product 专属词识别不足
- lexical keyword exact phrase 支持不足
- vector candidate window / index freshness 不足
- retrieval backend timeout 缺少 retry 或 soft fallback

---

## 5. P1.2 受控复测结果

执行方式：

- 直接调用 `ChatService.ask(..., debug_enabled=True)`，不走 `/api/chat/ask`，避免写入正式 trace JSONL
- 读取当前 `.env` 配置：`ORIONSTACK_SEARCH_BACKEND=elasticsearch`，`ORIONSTACK_PLANNER_PROVIDER=qwen_api`
- 额外用当前 ES 索引验证 `sales-faq-003` / `product-faq-004` 是否存在

复测结果：

| query | 当前 ChatService 结果 | 结论 |
|---|---|---|
| `演示资料在哪里找` | `fallback`，`lexical_backend_error`，`reject_reason=ConnectionTimeout`，`domain_hint=null` | 仍未关闭；不是缺知识，是无 domain 宽搜导致的 retrieval miss / timeout 风险 |
| `某个功能的定位是什么` | `fallback`，`lexical_backend_error`，`reject_reason=ConnectionTimeout`，`domain_hint=null` | 仍未关闭；不是缺知识，是无 domain 宽搜导致的 retrieval miss / timeout 风险 |
| `怎么请假` | `ok`，进入 clarification，命中 `hr-faq-001` / `hr-faq-003` | 当前已恢复预期行为；保留为历史瞬时后端错误观察项 |

索引确认：

- `sales-faq-003` 存在，`business_domain=sales`，问题为 `演示资料在哪里找？`
- `product-faq-004` 存在，`business_domain=product`，问题为 `某个功能的定位是什么？`
- `hr-faq-001` 存在，`business_domain=hr`

受控检索对比：

| query | domain filter | top 结论 |
|---|---|---|
| `演示资料在哪里找` | 无 | top candidates 漂到 finance/hr，未进入 `sales-faq-003` |
| `演示资料在哪里找` | `sales` | top1 为 `sales-faq-003` |
| `某个功能的定位是什么` | 无 | top candidates 漂到 finance/admin/it/hr，未进入 `product-faq-004` |
| `某个功能的定位是什么` | `product` | `product-faq-004` 进入 product 候选，但 top1 是 `product-faq-009` |

P1.2 结论：

- 这不是语料缺口，也不是 Odoo/API fallback 问题
- 当前主要问题是 **planner domain hint 缺失时，宽域检索容易漂移且可能触发 ES timeout**
- `演示资料` 的通用修复方向更清楚：provider 应识别 sales 域，或 retrieval 应在无 domain 时更好利用 keyword exact phrase
- `功能定位` 需要更谨慎：即使加 `product` domain filter，`product-faq-004` 也不是 top1，说明还涉及 product 域内 rerank/evidence 区分

下一优先级建议：

1. P1.3：先修无 domain 宽搜的通用稳定性，优先考虑检索后端 retry / timeout soft fallback，降低 `lexical_backend_error`
2. P1.4：再评估 planner domain hint 是否应把 `演示资料` 归 sales、`功能定位` 归 product
3. 暂不进入 API fallback；当前证据不足以说明这是外部系统查询缺口

---

## 6. P1.3 通用稳定性修复结果

实现内容：

- `HybridRetriever` 在 lexical / vector 单侧 backend 失败时，不再立即让整个 hybrid 检索失败
- 如果 lexical 失败但 vector 可用，则使用 vector 结果继续走 fusion / rerank
- 如果 vector 失败但 lexical 可用，则使用 lexical 结果继续走 fusion / rerank
- 如果两侧都失败，仍返回 backend error fallback
- `ChatService` 会在 debug 中记录 `*_backend_soft_fallback`，用于后续 trace 审计

专项测试：

- `test_hybrid_retriever_soft_fallbacks_to_vector_when_lexical_backend_fails`
- `test_hybrid_retriever_raises_backend_error_when_both_branches_fail`
- `test_chat_service_uses_hybrid_soft_fallback_when_lexical_branch_times_out`

受控复测：

| query | P1.3 后结果 | 结论 |
|---|---|---|
| `演示资料在哪里找` | `fallback=no_evidence`，不再是 `lexical_backend_error` | backend error 已收敛；仍需处理 domain hint / recall |
| `某个功能的定位是什么` | `fallback=no_evidence`，不再是 `lexical_backend_error` | backend error 已收敛；仍需处理 product domain hint / rerank |
| `怎么请假` | `ok`，进入 clarification | 当前稳定 |

P1.3 结论：

- `lexical_backend_error` 不再是这 3 个样本的主要 blocker
- 当前剩余问题已从“检索后端异常”收敛为“无 domain hint 时的宽域 recall / rerank”
- 下一步应进入 P1.4：provider/domain hint 或 retrieval recall 的通用修复，不做 query 特判

---

## 7. P1.4 无 domain hint 的宽域召回 / 重排修复

实现内容：

- Provider prompt 的业务域约定补充 `product` / `sales` 的领域词，不绑定具体后端；`Qwen` 只是当前可用 provider 之一
- `ChatService` 不再只信任 provider 返回的 `lexical_terms`，会合并本地保护性检索词，避免 provider 漏掉可由知识库关键词命中的短词
- 无 `domain_hint` 的 hybrid 检索把 rerank 候选池从 5 扩大到 12；有明确 `domain_hint` 时仍保持 5，避免已收窄场景过度扩张
- `HybridRetriever` 在无 domain filter 时保留跨业务域候选，避免前几个高分同域噪声把其他域候选完全挤出 rerank
- live planner smoke 增加 `sales` / `product` 领域样本，默认测试仍跳过 live API

新增专项测试：

- `test_hybrid_retriever_keeps_domain_diverse_candidates_when_unscoped`
- `test_chat_service_augments_unscoped_planner_terms_before_hybrid_search`

P1.4 结论：

- 这一步修的是“候选进入 rerank 的机会”和“provider 领域约定”，不是补单条 FAQ
- 若 provider 正确给 `domain_hint`，系统走窄域检索
- 若 provider 仍返回 `domain_hint=null`，系统也会用更稳的宽域候选池把跨域候选带入 rerank
- 受控复测中强制 `ORIONSTACK_PLANNER_PROVIDER=local`，也就是保持 `domain_hint=null`，两条 open miss 已从 `no_evidence` 收敛为直答

受控复测结果：

| query | P1.4 后结果 | 结论 |
|---|---|---|
| `演示资料在哪里找` | `ok`，`hybrid_rerank`，命中 `sales-faq-003` | 历史 open miss 可关闭 |
| `某个功能的定位是什么` | `ok`，`hybrid_rerank`，命中 `product-faq-004` | 历史 open miss 可关闭 |
| `怎么请假` | `ok`，进入 clarification，命中 `hr-faq-001` / `hr-faq-003` | 仍是合理澄清 |
