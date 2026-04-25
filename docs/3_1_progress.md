# OrionStack 第三阶段推进状态

> 状态：**设计基线已冻结，待按迭代实现**
> 对应设计文档：`docs/designs/3_system_design.md`
> 配套职责文档：`docs/3_2_file_responsibilities.md`
> 配套字段文档：`docs/3_3_field_definitions.md`
> 前置收口：Phase 2 已关闭（见 `docs/2_1_progress.md §10`）
> 目标：把外部 SaaS 导出数据安全、可控、可追溯地接入知识问答系统
> 原则：**先静态知识副本层，再 action link，再动态查询，最后抽取自动化**
> 边界：当前仓库默认示例使用 DashScope `qwen-plus` 与 `MockAdapter`；`OdooAdapter` 是显式可选外部系统示例。Phase 3 目标是可替换 provider / adapter，不把 Qwen + Odoo 写成架构绑定

---

## 1. 当前目标

本阶段只解决一件事：

**在"现有 SaaS 只提供数据导出、不直接接入原系统 API 执行动作"的前提下，把导出资料接入智能 FAQ 产品，并解决新鲜度、删除传播、权限漂移、可追溯、抽取漂移 5 个核心工程问题。**

本文档不承担以下职责：

- 不重写 `3_system_design.md` 的系统设计正文
- 不替代 `3_2_file_responsibilities.md` 的文件职责边界
- 不替代 `3_3_field_definitions.md` 的字段语义解释

---

## 2. 核心工程问题

从 `3_system_design.md §3` 提取的 5 个问题：

| # | 问题 | 一句话总原则 |
|---|---|---|
| 1 | 新鲜度 | 静态知识允许延迟同步，动态状态不长期固化，每条带 freshness 字段 |
| 2 | 删除与撤权传播 | 先逻辑失效再物理清理，tombstone 机制传播 |
| 3 | 权限漂移 | 问答层最小权限裁剪，动态查询运行时二次判权 |
| 4 | 可追溯与版本 | 所有发布单元可回溯到原始来源记录 |
| 5 | 结构化抽取漂移 | LLM 只产候选不直接上线，候选与发布分层 |

---

## 3. 落地顺序

按 `3_system_design.md §14` 锁定的最小落地顺序：

### Step 1：静态知识副本层（必做）

优先做：

- `SourceRecord` 对象与 repo
- `KnowledgeUnit` 扩展字段（`tenant_id` / `source_record_id` / `unit_version` / `fresh_until` / `stale_after` / `published_at`）
- `ExtractionCandidate` 对象与 repo
- `ImportBatch` 对象与 repo
- tombstone 机制
- freshness 判定
- 最小 access scope 判定

目标：

- 先把 SourceRecord → KnowledgeUnit 的"导入 → 审核 → 发布 → 入 ES"最小链路跑通
- 不急着接 ActionLink / DynamicQuery

当前状态：

- **设计基线已冻结**
- 代码实现尚未启动

### Step 2：action link（次做）

优先做：

- `ActionLink` 对象与 repo
- 为 FAQ / 知识单元绑定原系统入口
- 支撑"答 + 引 + 跳"体验

当前状态：

- 设计基线已冻结
- 依赖 Step 1 完成

### Step 3：最小动态查询（次做）

优先做：

- `DynamicQuery` 对象与 repo
- 只接审批进度 / 余额等少量高价值状态
- 运行时判权
- 当前参考实现包含 `OdooAdapter` / `MockAdapter`，但适配器协议不绑定单一系统

当前状态：

- **已完成**（43 测试：39 个 DynamicQuery 基础测试 + 4 个 adapter 双模式 smoke）
- 默认 adapter 为 `mock`，OdooAdapter 需要通过配置显式选择

实现要点：

1. `DynamicQueryService` 只负责 pattern 检测、repo 判权、adapter 调用和结果清洗
2. `SystemAdapter.fetch(resource_type, params)` 的 `params` 由具体 adapter 解释，通用层不注入 Odoo XML-RPC `domain`
3. OdooAdapter 内部负责 `resource_type -> Odoo model/fields` 映射，Odoo 字段差异停留在 adapter 内
4. MockAdapter 是默认本地/demo adapter，避免无配置启动时隐式依赖 Odoo
5. P2.1 双模式 smoke 已固化：默认 `mock` 路径不得触碰 Odoo；显式 `odoo` 配置才进入 Odoo adapter 分支，且测试不发真实 XML-RPC 请求

### Step 4：抽取候选自动化（后做）

- LLM 生成 FAQ / action link / dynamic query 候选
- 人工审核
- 发布
- 当前仓库默认示例使用 DashScope `qwen-plus`，但抽取链路目标是可替换 provider

当前状态：

- 设计基线已冻结
- 依赖 Step 1 完成

### Step 5：trace / hard cases 收敛（最后做）

- 用真实 bad cases 追查来源 / 抽取 / 检索 / evidence 问题
- 扩展 trace 以串联 `source_record_id` / `import_batch_id` / `unit_version`
- 扩展 hard case 以携带 provenance + issue_category 自动分类

当前状态：

- **已完成**（9 测试）
- 依赖 Step 1-4 部分完成

实现要点：

1. **Trace 扩展**：`_build_retrieval_trace_record` 新增 `source_record_id` / `import_batch_id` / `unit_version` / `dynamic_query_key` 四个 Phase 3 字段
2. **DebugInfo 扩展**：`DebugInfo` model 新增同上四个可选字段，`_build_debug_info` 透传
3. **Hit 链路透传**：`LexicalHit` / `HybridHit` 新增 `source_record_id` / `unit_version`，从 ES `_source` 读取并透传到 `chat_service`
4. **Hard case provenance**：`_build_hard_case_item` 新增 `source_record_id` / `import_batch_id` / `unit_version` / `dynamic_query_key` / `issue_category`
5. **Issue 自动分类**：`_infer_issue_category` 根据 `fallback_reason` + `source_record_id` 自动判定问题类型（`retrieval_miss` / `evidence_weak` / `extraction_drift` / `retrieval_ambiguous` / `routing_mismatch` / `unknown`）
6. **Hard case 触发范围扩大**：`_record_hard_case_from_response` 现在捕获所有 `fallback` 状态响应（不再限于 `no_evidence`）

---

## 4. 暂缓事项

以下内容当前明确不纳入 Phase 3 第一轮：

- 全自动发布（不经过人工审核的候选直接上线）
- 全平台同步（同时接入所有外部系统）
- 复杂审批 / 工作流语义
- 全权限继承（RBAC / ABAC）
- 实时真相源（直连原系统 API）

---

## 5. 与 Phase 2 已落地能力的关系

Phase 3 不重新实现 Phase 2 已落地的能力，而是**在现有链路上扩展**：

| Phase 2 已落地 | Phase 3 扩展方向 |
|---|---|
| `KnowledgeUnit`（固定字段集） | 扩展 `tenant_id` / `source_record_id` / `unit_version` / `fresh_until` / `stale_after` / `published_at` |
| `retrieval_trace.py` | 扩展 trace 以串联 `source_record_id` / `import_batch_id` / `unit_version` |
| `elastic_indexer.py` | 扩展 ES mapping 以包含新字段 |
| `knowledge_unit_repo.py` | 扩展以支持从 `SourceRecord` → `ExtractionCandidate` → `KnowledgeUnit` 的发布流程 |
| `chat_service.py` | 扩展 freshness 判定，在回答中附带 action link 和 stale 提示 |

---

## 6. 当前推进状态

| 事项 | 状态 |
|---|---|
| `3_system_design.md` 设计基线 | 已冻结 |
| `3_1_progress.md` 推进状态 | 已更新（本文） |
| `3_2_file_responsibilities.md` 文件职责 | 已更新（含运行时适配层 + 抽取层） |
| `3_3_field_definitions.md` 字段定义 | 已更新（含 SystemAdapter Protocol） |
| Step 1 代码实现 | 已完成（27 测试） |
| Step 2 代码实现（ActionLink） | 已完成（15 测试） |
| Step 3 代码实现（DynamicQuery） | 已完成（43 测试，含 adapter-neutral 边界回归 + 双模式 smoke） |
| Step 4 代码实现（抽取候选自动化） | 已完成（18 测试 + E2E 验证通过） |
| Step 5 代码实现 | 已完成（9 测试） |

---

## 7. 一句话收口

Phase 3 的推进以 `3_system_design.md` 为设计基线，按 Step 1 → 5 顺序逐层落地，每一步都在 Phase 2 已落地的链路上扩展，不重新实现已有能力。
