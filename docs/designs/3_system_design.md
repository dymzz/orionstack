# OrionStack 第三阶段系统设计：SaaS 知识副本层 v1

> 状态：**阶段设计基线**
> 目标方向：**在不直连原 SaaS API 的前提下，把导出数据变成带版本、带权限、带新鲜度、带追溯的知识副本层**
> 使用场景：**多来源 SaaS 数据接入智能 FAQ 产品**
> 与 `1_system_design.md` / `2_system_design.md` 的关系：
> - `1_system_design.md`：当前真实实现基线（FAQ / 文档问答主链路）
> - `2_system_design.md`：第二阶段检索链路升级（已完成，Planner / Hybrid / Rerank / Evidence / Clarification 全落地）
> - `3_system_design.md`：第三阶段目标设计，解决外部 SaaS 导出数据如何安全、可控、可追溯地接入知识问答系统

---

## 1. 文档定位

### 1.1 文档目标

本文档只解决一件事：

**在"现有 SaaS 只提供数据导出、不直接接入原系统 API 执行动作"的前提下，如何把导出的单团队 / 单域资料接入到智能 FAQ 产品中，并解决以下 5 个核心工程问题：**

1. 新鲜度问题 — 导入数据变旧怎么办
2. 删除与撤权传播 — 原系统删除/停用后怎么同步
3. 权限漂移 — 原系统权限变化后怎么不暴露越权内容
4. 可追溯与版本 — 答错时怎么追到来源
5. 结构化抽取漂移 — LLM 抽 FAQ / action link 时抽偏了怎么办

### 1.2 与已有设计的职责分工

- `1_system_design.md`：当前 FAQ / 文档问答主链路的实现基线
- `2_system_design.md`：检索链路升级设计（已完成落地）
- `document_ingestion_boundary.md`：原始文档进入问答主链路前的接入与清洗边界
- `document_library/`：业务域文档库标准
- `3_system_design.md`（本文）：外部 SaaS 导出数据如何安全接入知识系统

### 1.3 本文不承担的职责

- 不讨论替代现有 SaaS / OA / ERP 的重型产品路线
- 不设计全平台 API 统一层
- 不设计全权限细节与全工作流语义
- 不把所有外部系统都接成实时真相源

---

## 2. 设计边界

### 2.1 当前前提

当前系统假设：

- 现有 SaaS 可以导出本域所需资料
- 本工程不直接代替原系统执行业务动作
- 本工程只负责：
  - FAQ / 文档问答
  - 引用与证据
  - 跳转原系统入口
  - 少量高价值动态状态查询（如后续需要）
- 导入的数据会进入：
  - 结构化知识单元层（`KnowledgeUnit`，已在 `2_system_design.md` 中落地）
  - Elasticsearch 检索层
  - 向量检索层
- 运行时主链为：
  - Query Planner
  - Retrieval
  - Rerank / Evidence
  - Clarification
  - Hard Cases / Trace
- LLM 提取与外部系统接入都应走可替换接口
  - 当前仓库默认示例：DashScope `qwen-plus` + `MockAdapter`；OdooAdapter 是可选外部系统示例
  - 架构目标：provider / adapter 可替换，不把单一厂商或单一系统写死为边界

### 2.2 核心定位

本系统不是"原 SaaS 的替代者"，而是：

**一个带版本、带权限裁剪、带追溯能力的知识副本层（knowledge replica layer）。**

也就是说：

- 原 SaaS 仍是业务动作真相源
- 本系统是问答与知识入口层
- 导出数据进入本系统后，形成"可检索、可引用、可回放"的副本
- 本系统不追求绝对实时真相，而追求"可控延迟的一致性"

---

## 3. 五个核心工程问题与总原则

### 3.1 新鲜度问题

原系统更新后，FAQ / 文档 / 引用 / 跳转信息可能在本系统里变旧。

总原则：

- 静态知识允许延迟同步
- 动态状态不长期固化到知识副本中
- 每条数据带 freshness 字段
- 运行时按 freshness 决定是否可答、是否需提示、是否需跳原系统

### 3.2 删除与撤权传播

原系统删除内容、停用内容、撤销可见性后，本系统不应继续答、继续引、继续跳。

总原则：

- 先逻辑失效，再后台清理
- 运行时只检索 `active` 数据
- 用 tombstone 机制传播删除与撤权

### 3.3 权限漂移

原系统权限变化后，本系统不应长期沿用旧权限快照。

总原则：

- 问答层只做最小权限裁剪
- 动态查询运行时二次判权
- 知识单元与 action link 都必须携带 access scope

### 3.4 可追溯与版本问题

答错时必须能追到：

- 来源系统
- 来源记录
- 导出批次
- 导入批次
- 抽取版本
- 当前单元版本

总原则：

- 所有发布单元都能回溯到原始来源记录
- 所有抽取结果都能回溯到模型版本和 prompt 版本
- trace 能串起"来源 → 单元 → 回答"

### 3.5 结构化抽取漂移

LLM 从资料里抽 FAQ / action link / 动态查询候选时，可能抽偏、抽多、抽错。

总原则：

- LLM 只产候选，不直接上线
- 候选与发布分层
- 候选必须可审核、可回滚、可重跑

---

## 4. 数据分层

为了同时控制新鲜度与复杂度，导入数据必须分层，而不能混为一个知识池。

### 4.1 `knowledge_static`

适用内容：

- FAQ
- 制度摘要
- 帮助文档
- SOP
- 页面说明

特征：

- 允许分钟 / 小时级同步
- 可入 ES / 向量检索
- 可做 citation / evidence

### 4.2 `action_link`

适用内容：

- 去请假系统
- 去审批记录页
- 去工资条页面
- 去原 SaaS 某功能页面

特征：

- 不作为核心答案知识本体
- 作为回答后的下一步动作入口
- 同样需要版本与权限控制

### 4.3 `state_query`

适用内容：

- 审批进度
- 余额
- 个人状态
- 少量高价值实时查询

特征：

- 不长期固化到知识池
- 优先运行时查询
- 可以短缓存，但不应长期入 ES / 向量库作为静态真相

---

## 5. 核心对象设计

### 5.1 `SourceRecord`

表示从原系统导入的原始记录。

职责：

- 承接原系统导出数据
- 成为所有发布单元与抽取候选的来源锚点
- 提供版本、批次、状态与权限快照

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `source_record_id` | string | 是 | 本系统内原始来源记录 ID |
| `tenant_id` | string | 是 | 租户 |
| `source_system` | string | 是 | 来源系统标识，如 `dingtalk_hr` / `zendesk_help` |
| `source_object_type` | string | 是 | 来源对象类型，如 `faq_doc` / `kb_article` / `help_page` |
| `external_id` | string | 是 | 原系统记录 ID |
| `source_locator` | string | 是 | 回源定位信息 |
| `title` | string | 是 | 标题 |
| `raw_content` | text | 是 | 原始内容 |
| `content_hash` | string | 是 | 内容哈希 |
| `source_updated_at` | datetime | 是 | 来源系统更新时间 |
| `export_batch_id` | string | 是 | 导出批次 |
| `import_batch_id` | string | 否 | 导入批次 |
| `access_scope` | string | 是 | 问答层最小权限范围 |
| `status` | enum | 是 | `active / revoked / deleted / superseded` |
| `synced_at` | datetime | 是 | 导入完成时间 |

### 5.2 `KnowledgeUnit`（扩展）

当前 `2_system_design.md` 中已定义的 `KnowledgeUnit` 需要扩展以下字段以支撑知识副本层：

| 新增字段 | 类型 | 说明 |
|---|---|---|
| `tenant_id` | string | 租户 |
| `source_record_id` | string | 对应来源记录 |
| `unit_version` | integer | 单元版本 |
| `fresh_until` | datetime | 正常可答上限 |
| `stale_after` | datetime | 过期阈值 |
| `published_at` | datetime | 发布时间 |

运行时规则：

- `lifecycle_status != active` 的单元不参与检索
- `now <= fresh_until`：正常可答
- `fresh_until < now <= stale_after`：可答，但可选提醒
- `now > stale_after`：不直接答，优先跳原系统或触发刷新

### 5.3 `ActionLink`

表示"跳"到原系统的入口。

职责：

- 把问答结果和原系统操作入口衔接起来
- 支撑"答 + 引 + 跳"的体验

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `action_link_id` | string | 是 | 链接 ID |
| `tenant_id` | string | 是 | 租户 |
| `source_record_id` | string | 是 | 来源记录 |
| `label` | string | 是 | 展示文案 |
| `system_type` | string | 是 | 来源系统类型 |
| `url` | string | 是 | 跳转链接 |
| `resource_type` | string | 是 | 目标资源类型 |
| `access_scope` | string | 是 | 可见范围 |
| `status` | enum | 是 | `active / revoked / deleted` |
| `fresh_until` | datetime | 否 | 有效期 |
| `published_at` | datetime | 是 | 发布时间 |

### 5.4 `DynamicQuery`

表示运行时允许查询的少量动态状态定义。

职责：

- 承接"查"能力
- 约束哪些实时状态允许被查询
- 不把全部业务 API 暴露给问答层

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `dynamic_query_id` | string | 是 | 查询定义 ID |
| `tenant_id` | string | 是 | 租户 |
| `query_key` | string | 是 | 查询标识 |
| `resource_type` | string | 是 | 资源类型 |
| `action` | string | 是 | 允许动作，如 `read` |
| `scope_type` | string | 是 | `self / org / role` |
| `status` | enum | 是 | `active / revoked` |
| `description` | text | 是 | 说明 |

约束：

- 不长期作为静态知识单元进入索引
- 运行时必须二次判权
- 只开放少量高价值查询

### 5.5 `ExtractionCandidate`

表示 LLM 结构化抽取后的候选对象。

职责：

- 承接 LLM 从资料中抽取出的候选 FAQ / action link / 动态查询定义
- 将候选与发布分层
- 为人工审核和回滚提供中间层

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `candidate_id` | string | 是 | 候选 ID |
| `tenant_id` | string | 是 | 租户 |
| `source_record_id` | string | 是 | 来源记录 |
| `candidate_type` | string | 是 | `faq` / `action_link` / `dynamic_query` |
| `payload_json` | json | 是 | 候选内容 |
| `extractor_model` | string | 是 | 抽取模型 |
| `prompt_version` | string | 是 | prompt 版本 |
| `source_span` | string | 是 | 来源片段定位 |
| `source_span_hash` | string | 是 | 来源片段哈希 |
| `review_status` | enum | 是 | `pending / approved / rejected` |
| `reviewed_by` | string | 否 | 审核人 |
| `reviewed_at` | datetime | 否 | 审核时间 |
| `created_at` | datetime | 是 | 创建时间 |

原则：

- LLM 只写入 `ExtractionCandidate`
- 审核通过后才生成 `KnowledgeUnit` / `ActionLink` / `DynamicQuery`

### 5.6 `ImportBatch`

表示一次同步 / 导入任务。

职责：

- 承接同步任务元信息
- 记录导入范围、状态、错误与批次级追溯

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `import_batch_id` | string | 是 | 导入批次 ID |
| `tenant_id` | string | 是 | 租户 |
| `source_system` | string | 是 | 来源系统 |
| `mode` | string | 是 | `full` / `incremental` |
| `started_at` | datetime | 是 | 开始时间 |
| `finished_at` | datetime | 否 | 结束时间 |
| `status` | enum | 是 | `running / success / partial_success / failed` |
| `record_count` | integer | 否 | 处理记录数 |
| `error_summary` | text | 否 | 错误摘要 |

---

## 6. 同步与版本策略

### 6.1 批次同步

同步以批次为单位执行。最小流程：

1. 创建 `ImportBatch`
2. 读取导出文件
3. 解析为 `SourceRecord`
4. 对比 `content_hash`
5. 判定新增 / 更新 / 删除 / 不变
6. 更新对应 `KnowledgeUnit` / `ActionLink` / `DynamicQuery`
7. 写入 ES / 向量存储
8. 关闭批次并记录结果

### 6.2 版本策略

- `SourceRecord` 层：记录来源内容版本
- `KnowledgeUnit` 层：记录发布单元版本
- `ExtractionCandidate` 层：记录抽取版本与 prompt 版本
- `ImportBatch` 层：记录批次维度版本

### 6.3 内容哈希

- 对每个 `SourceRecord` 计算 `content_hash`
- 对比 hash 决定是否需要重抽取、重建单元、重写 ES / 向量

---

## 7. 新鲜度控制设计

### 7.1 freshness 字段

每个发布对象（`KnowledgeUnit` / `ActionLink`）都至少带：

- `fresh_until`
- `stale_after`

### 7.2 运行时判定

| 区间 | 条件 | 处理 |
|---|---|---|
| 正常可答 | `now <= fresh_until` | 正常检索、正常答复 |
| 警戒区间 | `fresh_until < now <= stale_after` | 允许回答，可选提示"内容可能已更新，请以原系统为准"，可优先带 action link |
| 过期区间 | `now > stale_after` | 不直接给强确定答案，优先触发跳原系统 / 手动刷新 / clarification |

### 7.3 动态状态策略

动态状态不进入长期 freshness 管理，而采用：

- 运行时现查
- 或极短 TTL 缓存

不应把审批进度、余额等状态长期固化到 `KnowledgeUnit` 中。

---

## 8. 删除与撤权传播设计

### 8.1 tombstone 机制

当原系统记录被删除、撤权、停用时：

1. 来源同步识别该记录状态变化
2. 对应 `SourceRecord.status` 更新为 `revoked / deleted`
3. 关联 `KnowledgeUnit / ActionLink` 状态同步变更
4. 运行时检索过滤非 `active`
5. 后台异步清理 ES 文档与向量存储

### 8.2 两阶段删除

| 阶段 | 优先级 | 动作 |
|---|---|---|
| 第一阶段：逻辑失效 | 最高 | 确保运行时不可见 |
| 第二阶段：物理清理 | 异步 | 删除 ES 文档、删除向量索引条目、清理缓存 |

保证系统不会因物理删除流程阻塞而继续暴露错误结果。

---

## 9. 权限裁剪设计

### 9.1 问答层最小权限模型

问答层只保留最小权限范围：

- `public`
- `internal`
- `tenant`
- `org`
- `role`
- `self`

### 9.2 静态知识权限

`KnowledgeUnit` / `ActionLink` 在导入与发布时就携带 `access_scope`。

运行时判定：

- 当前用户是否满足该 `access_scope`
- 若不满足，则不返回该单元 / 链接

### 9.3 动态查询权限

动态查询不得只依赖导入快照。必须在运行时做二次判权：

- 当前 `tenant_id`
- 当前 `user_id`
- 当前 `role`
- 当前 `scope_type`

避免"自己能问别人的状态"。

---

## 10. 可追溯设计

### 10.1 从答案追到来源

任何最终答案都应能追溯到：

- `unit_id`
- `unit_version`
- `source_record_id`
- `source_locator`
- `import_batch_id`
- `source_updated_at`

### 10.2 trace 串联

运行时 trace 至少串联：

- `trace_id`
- `query`
- `retrieval_mode`
- `retrieved_unit_ids`
- `chosen_unit_id`
- `unit_version`
- `evidence_spans`
- `final_status`

### 10.3 bad case 复盘

hard case 必须能反查：

- 命中的单元是哪版
- 这版来自哪次导入
- 候选 FAQ / action link 是哪次抽取生成的
- 是原文问题、抽取问题、检索问题还是 evidence 问题

---

## 11. 结构化抽取漂移控制

### 11.1 候选层与发布层分离

**候选层**

- `ExtractionCandidate`
- 由 LLM 自动生成
- 可多版本重跑
- 不直接进入生产问答链

**发布层**

- `KnowledgeUnit`
- `ActionLink`
- `DynamicQuery`
- 必须经过审核或自动规则校验后发布

### 11.2 provenance 字段

每条候选必须至少保留：

- `source_record_id`
- `source_span`
- `source_span_hash`
- `extractor_model`
- `prompt_version`

### 11.3 可重跑

重抽取原则：

- 原始来源内容不改
- 模型 / prompt 升级后可整批重抽
- 新旧候选可比较
- 审核通过后再替换发布层对象

---

## 12. 运行时主链如何使用这些对象

### 12.1 FAQ / 文档问答

1. 查询进入 planner
2. retrieval 检索 `KnowledgeUnit`（只检索 `lifecycle_status == active` 且 `now <= stale_after` 的单元）
3. rerank / evidence 对候选重排
4. clarification 决定是否追问
5. answer composer 生成答案
6. citations 回到 `KnowledgeUnit.source_locator`
7. 如有 `ActionLink`，一并返回
8. 如 `fresh_until < now <= stale_after`，附带提示

### 12.2 动态状态查询

1. FAQ 路由低置信度时，尝试动态查询检测
2. `DynamicQueryService.match_query_key()` 正则识别查询意图
3. `DynamicQueryService.is_allowed()` 通过 repo 判权
4. `DynamicQueryService.execute()` 通过 `SystemAdapter.fetch()` 获取实时数据
5. 返回 `DynamicQueryResultItem` + 关联 `ActionLink`

动态状态不应绕过判权，不应长期固化进 FAQ 单元。

### 12.3 外部系统适配器架构

动态查询不直连具体外部系统，而是通过抽象接口解耦：

```text
SystemAdapter (Protocol)            ← 抽象接口
  .name -> str                      ← 适配器名称标识
  .fetch(resource_type, params)     ← 统一查询入口
      -> list[dict[str, Any]]       ← 标准化行数据
      params 由具体 adapter 解释      ← 通用层不假设外部系统方言
  │
  ├── OdooAdapter                   ← 当前已实现的 Odoo XML-RPC 适配器
  │     model_fields_map 可配置     ← resource_type → (model, fields) 映射
  │
  ├── MockAdapter                   ← 测试用，fixtures 可注入
  │
  └── (未来 DingTalkAdapter 等)     ← 只需实现 Protocol
```

#### 适配器选择

由 `adapter_factory.create_adapter()` 根据 `settings.dynamic_query_adapter` 选择实例：

| 环境变量 | 可选值 | 说明 |
|---|---|---|
| `ORIONSTACK_DYNAMIC_QUERY_ADAPTER` | `mock`（默认）/ `odoo` / 自定义 | 选择适配器实现 |
| `ORIONSTACK_ODOO_URL` | URL | Odoo 服务地址 |
| `ORIONSTACK_ODOO_DB` | string | Odoo 数据库名 |
| `ORIONSTACK_ODOO_UID` | int | Odoo 用户 ID |
| `ORIONSTACK_ODOO_PASSWORD` | string | Odoo 用户密码，需通过环境变量注入 |

#### 如何新增适配器

1. 在 `backend/app/runtime/` 下新建适配器文件
2. 实现 `SystemAdapter` Protocol：提供 `name` 属性和 `fetch(resource_type, params)` 方法
3. 在 `adapter_factory.py` 注册新适配器分支
4. 在 `settings.py` 添加该适配器所需的环境变量（如有）
5. 在 `DynamicQueryRepo` 种子数据中注册该适配器支持的 `resource_type`

#### OdooAdapter 的 model_fields_map

OdooAdapter 通过 `model_fields_map` 配置将 `resource_type` 映射到 Odoo 模型和字段：

```python
_MODEL_FIELDS_MAP: dict[str, tuple[str, list[str]]] = {
    "leave_status": (
        "hr.leave",
        ["name", "holiday_status_id", "date_from", "date_to", "state", "number_of_days"],
    ),
    "expense_status": (
        "hr.expense",
        ["name", "total_amount", "state", "date"],
    ),
    "attendance_balance": (
        "hr.attendance",
        ["check_in", "check_out", "worked_hours"],
    ),
    "crm_pipeline": (
        "crm.lead",
        ["name", "expected_revenue", "stage_id", "probability"],
    ),
}
```

此映射可通过构造参数 `model_fields_map` 覆盖，实现不同 Odoo 实例的模型差异适配。

### 12.4 抽取候选自动化管线

从原始文档到可检索知识的全自动管线：

```text
任意文档 (.txt / .md)
       ↓ pipeline_cli import
  SourceRecord (raw_content)
       ↓ ExtractionService → 当前配置的抽取 provider
  LLM 返回 JSON 候选
       ↓ parse_extraction_response()
  ExtractionCandidate (pending)
       ↓ review_candidate() — 人工或 --auto-approve
  approved → publish_candidate()
       ↓ 按 candidate_type 分发
  ┌─────────────────┬──────────────────┬──────────────────┐
  │ faq             │ action_link      │ dynamic_query    │
  │ → KnowledgeUnit │ → ActionLinkRepo │ → DynamicQueryRepo│
  └─────────────────┴──────────────────┴──────────────────┘
```

#### 使用方式

**方式一：CLI 管线（推荐）**

```bash
# 一步完成：导入 → 抽取 → 自动审核 → 发布
python -m scripts.pipeline_cli import \
  --file path/to/policy.md \
  --title "制度文档标题" \
  --source-system wiki \
  --auto-approve

# 分步执行（推荐，可人工审核）
python -m scripts.pipeline_cli import --file doc.md --title "标题"
python -m scripts.pipeline_cli extract --source-record-id sr-xxx
python -m scripts.pipeline_cli list --status pending
python -m scripts.pipeline_cli review --candidate-id ec-xxx --approve
```

**方式二：API 端点**

```bash
# 抽取
curl -X POST http://localhost:8000/api/extraction/extract \
  -H "Content-Type: application/json" \
  -d '{"source_record_id": "sr-xxx"}'

# 审核 + 发布
curl -X POST http://localhost:8000/api/extraction/review \
  -H "Content-Type: application/json" \
  -d '{"candidate_id": "ec-xxx", "approved": true}'

# 列出候选
curl http://localhost:8000/api/extraction/candidates?status=pending
```

#### LLM 抽取三类候选

| 候选类型 | LLM 输出字段 | 发布目标 |
|---|---|---|
| `faq` | question, answer, keywords, business_domain | KnowledgeUnit → ES 索引 |
| `action_link` | label, url, resource_type | ActionLinkRepo |
| `dynamic_query` | query_key, resource_type, scope_type, description | DynamicQueryRepo |

#### E2E 验证结果

| 测试文档 | 内容长度 | 抽取结果 |
|---|---|---|
| 员工考勤与请假管理制度 | 967 字 | 9 FAQ 候选 → 全部发布为 KnowledgeUnit |
| 差旅费用报销管理办法 | 509 字 | 8 FAQ + 2 ActionLink + 2 DynamicQuery → 全部发布 |

---

## 13. 最小实现建议

### 必做

- `SourceRecord`
- `KnowledgeUnit` 扩展字段
- `ExtractionCandidate`
- `ImportBatch`
- tombstone 机制
- freshness 判定
- 最小 access scope 判定

### 次做

- `ActionLink`
- `DynamicQuery`
- 候选审核流 UI / 工具

### 暂缓

- 全自动发布
- 全平台同步
- 复杂审批 / 工作流语义
- 全权限继承

---

## 14. 最小落地顺序

### 第一步：静态知识副本层

- 导入 FAQ / 文档
- 生成 `SourceRecord`
- 审核后发布 `KnowledgeUnit`
- 接入 ES / 向量检索

### 第二步：action link

- 为 FAQ / 知识单元绑定原系统入口
- 支撑"答 + 引 + 跳"

### 第三步：最小动态查询

- 只接审批进度 / 余额等少量高价值状态
- 运行时判权

### 第四步：抽取候选自动化（已完成）

- `pipeline_cli import` 导入任意文档为 SourceRecord
- `ExtractionService` 调用当前配置的抽取 provider 抽取候选（仓库默认示例为 DashScope `qwen-plus`）
- 支持 3 类候选：faq → KnowledgeUnit / action_link → ActionLink / dynamic_query → DynamicQuery
- `pipeline_cli review` 人工审核，或 `--auto-approve` 自动发布
- API 端点：`POST /api/extraction/extract` + `POST /api/extraction/review`
- E2E 验证通过：两份制度文档共抽取 21 条候选并全部成功发布

### 第五步：trace / hard cases 收敛

- 用真实 bad cases 追查：
  - 来源问题
  - 抽取问题
  - 检索问题
  - evidence 问题
- 实现已完成，具体变更：
  - `LexicalHit` / `HybridHit` 新增 `source_record_id` / `unit_version`，从 ES `_source` 读取
  - `DebugInfo` 新增 `source_record_id` / `import_batch_id` / `unit_version` / `dynamic_query_key`
  - `_build_retrieval_trace_record` 串联 Phase 3 provenance 字段到 trace 记录
  - `_build_hard_case_item` 携带完整 provenance + `issue_category` 自动分类
  - `_infer_issue_category` 根据 `fallback_reason` + `source_record_id` 推断问题类型
  - `_record_hard_case_from_response` 触发范围从仅 `no_evidence` 扩大到所有 `fallback` 响应
  - 9 个测试覆盖：provenance 透传、dynamic_query_key、issue 分类、反馈 upsert

---

## 15. 一句话总结

这套设计的核心不是"把导出的资料全塞进 ES 和向量库"，而是：

**把导出数据变成一层带版本、带权限、带新鲜度、带追溯、带候选审核机制的知识副本层。**

只有这样，FAQ 产品才能在"不直连原系统"的前提下保持可解释、可回放、可收敛。
