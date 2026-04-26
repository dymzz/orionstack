# OrionStack Phase 3 契约审计 P3.0

> 状态：已完成第一轮审计
> 日期：2026-04-26
> 审计依据：`docs/designs/3_system_design.md`、`docs/3_1_progress.md`、`docs/3_2_file_responsibilities.md`、`docs/3_3_field_definitions.md`
> 非依据：`HANDOFF.md` 只作为交接摘要，不作为本审计的目标定义来源
> P3.1 更新：已补齐 SourceRecord tombstone 到 ActionLink / DynamicQuery 的运行时入口层传播；KnowledgeUnit / ES 清理仍保留为后续 provenance / sync 闭环
> P3.2 更新：已补齐 DynamicQuery 最小运行时判权；无 principal、租户不匹配、用户/角色不满足时不会触发 adapter
> P3.3 更新：已补齐 provenance 字段从 KnowledgeUnit / ES / lexical / vector / hybrid hit 到 trace / hard case 的最小穿透链路

---

## 1. 审计目标

本轮只回答一个问题：

**Phase 3 第一轮代码是否真实守住第三阶段设计中的 5 个知识副本层契约。**

这 5 个契约来自 `3_system_design.md §3`：

| 契约 | 设计要求 | 本轮结论 |
|---|---|---|
| 新鲜度 | 静态知识允许延迟同步，过期内容不应强确定回答 | 部分满足 |
| 删除与撤权传播 | 原系统删除/撤权后，本系统不可继续答、引、跳 | 部分闭环 |
| 权限漂移 | 问答层最小权限裁剪，动态查询运行时二次判权 | 动态查询已闭环 |
| 可追溯与版本 | 答案、trace、hard case 能追到来源与版本 | 基本闭环 |
| 抽取漂移 | LLM 只产候选，审核后才发布 | 基本满足 |

---

## 2. 总结论

Phase 3 第一轮不是没有落地；对象、repo、adapter、抽取、trace 字段和基础测试都已经存在。

但当前实现仍是**最小骨架闭环**，不是完整契约闭环。下一步不应直接扩展更多外部系统，也不应先做完整认证系统或生产数据库，而应优先补齐安全边界：

1. **删除/撤权传播闭环**：P3.1 已先补 ActionLink / DynamicQuery 运行时入口层
2. **动态查询最小运行时判权**：P3.2 已补 principal + scope 判权

接下来应转向 stale / sync 到发布层的闭环，避免过期知识仍强答或 SourceRecord 状态没有真正传播到知识发布层。

---

## 3. 契约审计明细

### 3.1 新鲜度契约：部分满足

设计要求：

- `now <= fresh_until`：正常回答
- `fresh_until < now <= stale_after`：可回答但提示可能过期
- `now > stale_after`：不直接给强确定答案，优先跳原系统、触发刷新或 clarification

当前实现：

- `check_freshness()` 已实现三态判定：`fresh / warning / stale`
- `ChatService._check_hit_freshness()` 已在 ES 命中后读取 `fresh_until / stale_after`
- 命中 warning/stale 时，当前会在答案后追加提示

缺口：

- 当前 stale 仍然会返回原答案，只追加“已过期，建议核实最新版本”的后缀
- 这弱于设计中的“不直接给强确定答案”
- 本地链路 `_search_local()` 没有 freshness 判定

证据：

- `backend/app/sync/freshness.py`
- `backend/app/services/chat_service.py`
- `backend/tests/test_phase3_freshness.py`

结论：**P1 修正**。它不是最高风险的泄露问题，但会让过期知识仍被当成答案返回。

---

### 3.2 删除与撤权传播契约：部分闭环

设计要求：

- 来源记录被删除/撤权时，先逻辑失效
- 同步传播到 `KnowledgeUnit / ActionLink / DynamicQuery`
- 运行时只检索 active 数据
- ES / 向量物理清理由后台异步处理

当前实现：

- `SourceRecordRepo.update_status()` 能更新 SourceRecord 状态
- `handle_tombstone()` 会更新 SourceRecord 状态
- P3.1 已补：`handle_tombstone()` 可传播到 `ActionLinkRepo`
- P3.1 已补：`handle_tombstone()` 可传播到 `DynamicQueryRepo`
- 检索侧默认过滤 `lifecycle_status == active`
- `ActionLinkRepo` 与 `DynamicQueryRepo` 都有 `update_status()`

已关闭：

- SourceRecord 撤权 / 删除后，关联 action link 不再被 `list_by_source_record()` 返回
- SourceRecord 撤权 / 删除后，关联 dynamic query 不再 match，也不会触发 adapter fetch
- `deleted` SourceRecord 对 DynamicQuery 映射为 `revoked`，因为 DynamicQuery 当前枚举只支持 `active / revoked`

剩余缺口：

- 当前 `KnowledgeUnitRepository` 没有持久化发布层 repo，也没有按 `source_record_id` 批量失效 KnowledgeUnit 的能力
- ES 索引没有按 `source_record_id` 失效或清理的入口
- 现有检索链仍依赖 `lifecycle_status == active`，还没有接 SourceRecord tombstone 反查

证据：

- `backend/app/sync/tombstone_handler.py`
- `backend/app/storage/repositories/action_link_repo.py`
- `backend/app/storage/repositories/dynamic_query_repo.py`
- `backend/app/storage/repositories/knowledge_unit_repo.py`
- `backend/tests/test_phase3_sync.py`

结论：**P0 已部分修正**。运行时入口层已先阻断，KnowledgeUnit / ES 清理进入 P3.3 / P3.5。

---

### 3.3 权限漂移契约：动态查询已闭环

设计要求：

- 静态知识按 `access_scope` 做最小权限裁剪
- 动态查询运行时必须二次判权
- 判权至少考虑 `tenant_id / user_id / role / scope_type`

当前实现：

- ES lexical/vector 检索支持按 `access_scope` 过滤
- 动态查询 repo 保存了 `tenant_id / scope_type / status / action / allowed_roles`
- `DynamicQueryService.is_allowed(query_key, principal)` 会拒绝未知 query、非 active/read query、无 principal、租户不匹配、用户上下文缺失或角色不匹配
- `DynamicQueryService.execute()` 会在 adapter fetch 前重复判权，未授权时直接返回 `None`
- `ChatAskRequest` 透传最小运行时上下文：`tenant_id / user_id / roles`
- adapter 收到的是通用 `tenant_id / user_id / roles` 参数，不接收通用层拼出的 Odoo domain
- 默认 adapter 是 `mock`，显式 `odoo` 才进入 Odoo adapter 分支

缺口：

- 静态知识当前主要是 `access_scope` 字段过滤，还不是基于用户上下文的权限判断
- 当前 `RuntimePrincipal` 来自请求 payload，后续接入真实认证中间件时需要替换为可信身份来源

证据：

- `backend/app/runtime/dynamic_query_service.py`
- `backend/app/storage/repositories/dynamic_query_repo.py`
- `backend/tests/test_dynamic_query.py`
- `backend/tests/test_dynamic_query_adapter_modes.py`

结论：**P0 已修正 DynamicQuery 部分**。动态查询面对运行时状态数据，当前已先做到最小 principal 判权；静态知识的用户级权限仍留在后续权限体系阶段。

---

### 3.4 可追溯与版本契约：基本闭环

设计要求：

- 最终答案可追到 `unit_id / unit_version / source_record_id / source_locator / import_batch_id / source_updated_at`
- trace 能串起来源、单元、回答
- hard case 能区分来源问题、抽取问题、检索问题、evidence 问题

当前实现：

- `DebugInfo` 支持 `source_record_id / import_batch_id / unit_version / dynamic_query_key / freshness_status`
- retrieval trace 会写入这些字段
- hard case item 会携带 provenance 字段与 `issue_category`
- `KnowledgeUnit` 和 ES doc/mapping 已包含 `import_batch_id`
- lexical / vector / hybrid hit 会从 ES `_source` 透传 `source_record_id / import_batch_id / unit_version / fresh_until / stale_after`
- `ChatService` 对选中命中始终写入 `unit_version`，包括 `unit_version = 1`
- hard case 分类优先看 `fallback_reason / reject_reason`，不再仅凭 `source_record_id` 归类为 `extraction_drift`

剩余缺口：

- `source_updated_at` 仍主要保留在 SourceRecord，尚未进入 KnowledgeUnit / ES hit
- hard case 的 source/sync/revocation 子分类还没有真实 SourceRecord 状态反查
- 本地检索链只透传已有 item 字段，不做 SourceRecord 反查

证据：

- `backend/app/api/routes/chat.py`
- `backend/app/storage/repositories/knowledge_unit_repo.py`
- `backend/app/retrieval/lexical_retriever.py`
- `backend/app/retrieval/vector_retriever.py`
- `backend/app/retrieval/hybrid_retriever.py`
- `backend/app/indexing/elastic_indexer.py`
- `backend/tests/test_phase2_retrieval.py`
- `backend/tests/test_phase3_trace_hard_cases.py`

结论：**P1 已修正最小闭环**。答案 trace 已能追到单元版本、来源记录和导入批次；更深的 SourceRecord 状态反查留到 sync/发布层闭环。

---

### 3.5 抽取漂移契约：基本满足

设计要求：

- LLM 只写入 `ExtractionCandidate`
- 候选必须保留 provenance
- 审核通过后才发布到 `KnowledgeUnit / ActionLink / DynamicQuery`

当前实现：

- `ExtractionService.extract_from_record()` 调用可替换抽取 provider
- `extract_candidates()` 创建 `ExtractionCandidate`
- 候选默认 `review_status="pending"`
- `review_candidate()` 执行审核状态流转
- `publish_candidate()` 按 candidate_type 发布到 FAQ / ActionLink / DynamicQuery

保留观察：

- `--auto-approve` 是可用能力，适合 demo 或受控导入，不应被描述成生产默认
- `candidate_type="mixed"` 依赖 payload 内部的 `candidate_type` 分发，当前可工作，但后续如果做审核 UI，需要显示更直观的候选类型

证据：

- `backend/app/extract/extraction_service.py`
- `backend/app/extract/llm_extractor.py`
- `backend/app/extract/candidate_reviewer.py`
- `backend/tests/test_extraction.py`

结论：**P2 观察**。不是当前最高风险。

---

### 3.6 Adapter 解耦契约：基本满足

设计要求：

- 动态查询通过 `SystemAdapter` Protocol 解耦
- 通用层不假设 Odoo XML-RPC 方言
- Odoo 只是当前实现之一，不是架构目标

当前实现：

- `SystemAdapter` Protocol 已存在
- `adapter_factory` 支持注册 adapter
- 默认 adapter 是 `mock`
- 显式配置 `odoo` 才创建 OdooAdapter
- 双模式 smoke 覆盖默认 mock 与显式 odoo

缺口：

- 文档与示例数据里仍有较多 Odoo action link seed，但这是样例数据问题，不是架构绑定
- 新增 adapter 仍需改 `adapter_factory` 注册分支；已有 `register_adapter()`，但还没有插件式自动发现

证据：

- `backend/app/runtime/system_adapter.py`
- `backend/app/runtime/adapter_factory.py`
- `backend/tests/test_dynamic_query_adapter_modes.py`

结论：**P2 保持**。不要继续为了“多系统”先写钉钉/飞书；先补安全契约。

---

## 4. 推荐修复顺序

### P3.1：tombstone 传播闭环（P0，已完成入口层）

已完成：

- `handle_tombstone()` 支持注入并更新 `ActionLinkRepo / DynamicQueryRepo`
- `DynamicQuery` 增加可选 `source_record_id`
- `publish_candidate()` 发布 dynamic query 时写入 `source_record_id`
- 增加按 `source_record_id` 找到并失效 action links 的测试
- 增加按 `source_record_id` 失效 dynamic queries 的测试
- KnowledgeUnit 当前没有独立发布层 repo，因此 P3.1 的最小策略是先阻断 action link 与 dynamic query，后续再补 ES/source_record_id 清理

验收：

- 撤权/删除 SourceRecord 后，关联 action link 不再被返回
- 关联 dynamic query 不再被执行
- 测试覆盖 `revoked / deleted`

### P3.2：DynamicQuery 最小运行时判权（P0，已完成）

已完成：

- 引入最小 `RuntimePrincipal`
- `is_allowed(query_key, principal)` 按 `tenant_id / scope_type / role` 判定
- `self` 查询必须有当前用户标识
- `role` 查询必须命中角色
- 无上下文时直接拒绝动态查询
- `execute()` 在 adapter fetch 前重复判权
- adapter 只接收通用身份参数，不接收通用层拼出的外部系统方言参数

验收：

- 无 principal 不执行 `self/org/role` 动态查询
- tenant 不匹配不执行
- role 不匹配不执行
- adapter 不收到未授权请求
- 调用方传入的 `tenant_id / user_id / roles` 参数不能覆盖 principal

### P3.3：provenance 链路补齐（P1，已完成最小闭环）

已完成：

- ES doc/mapping 增加 `import_batch_id`
- Lexical/Vector/Hybrid hit 都透传 `source_record_id / import_batch_id / unit_version / freshness`
- trace 中始终记录 `unit_version`
- hard case 分类不要仅因 `source_record_id` 存在就归为 `extraction_drift`

验收：

- vector-only 命中也能带 provenance
- trace 可追到 `source_record_id / import_batch_id / unit_version`
- hard case 会优先按 fallback/evidence/retrieval 分类；source/sync/revocation 子分类留到 SourceRecord 状态反查阶段

### P3.4：stale 不强答（P1）

目标：

- `stale` 命中不直接返回原答案
- 优先返回 action link、刷新提示或 clarification
- `warning` 仍可回答但必须提示

验收：

- stale hit 的 response 不包含原答案正文
- freshness_status 写入 trace
- 有 action link 时返回跳转入口

### P3.5：sync 到发布层/索引闭环（P1）

目标：

- `SyncService` 不只停在 SourceRecord/ImportBatch
- 内容变更后能驱动候选重抽或发布层版本更新
- 删除/撤权与 ES/向量索引清理形成最小可测试入口

验收：

- 新增/更新/删除三类同步结果都有发布层或索引侧可见效果
- `ImportBatch.record_count` 与状态能反映 partial failure

---

## 5. 本轮不建议做

以下方向不是下一优先级：

- 不先写更多具体外部系统 adapter
- 不先把 Odoo 示例继续扩深
- 不先做完整 RBAC / ABAC
- 不先替换 JSONL 为生产数据库
- 不先改 `HANDOFF.md` 作为实时路线图

原因：这些都会扩大面，但不会先关闭 Phase 3 已承诺的安全契约缺口。

---

## 6. P3.0 收口判断

P3.0 的结论是：

**Phase 3 第一轮完成的是功能骨架，下一步必须从“更多能力”切回“契约闭环”。**

最高优先级不是新系统接入，也不是完整生产化，而是：

1. 删除/撤权不泄露
2. 动态查询不越权
3. provenance 真正可追
