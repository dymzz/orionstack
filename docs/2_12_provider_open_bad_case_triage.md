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
